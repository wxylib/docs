"""Read GHRSST MUR analysed_sst straight from its mdim-refs byte table: no
TIFF, Zarr or GDAL library. A chunk is a row (path, offset, size): one HTTP
range request, ZSTD, then undo the TIFF horizontal predictor (a running sum
along each row of 512 values).

The store is a directory or URL holding flat/arrays.json and
flat/refs_analysed_sst.parquet (MUR_STORE). Source paths in the table are
https://data.source.coop/...; MUR_HOST replaces that host when it cannot be
reached directly (for example the same objects on
https://s3.us-west-2.amazonaws.com/us-west-2.opendata.source.coop/).

    python3 mur_table.py [manifest.json]

prints the SHA-256 of each window in a manifest of GDAL hashes.
"""
import hashlib, json, os, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pyarrow.parquet as pq
from numcodecs import Zstd

STORE = os.environ.get("MUR_STORE", "ghrsst-mur-v2-20240101-20241231/out")
HOST = os.environ.get("MUR_HOST", "https://data.source.coop/")


class Table:
    def __init__(self, store=STORE, array="analysed_sst"):
        meta = json.load(open(f"{store}/flat/arrays.json"))
        self.meta = next(a for a in meta["arrays"] if a["array"] == array)
        self.refs = pq.read_table(
            f"{store}/flat/refs_{array}.parquet",
            columns=["dim_0", "dim_1", "dim_2", "present", "path", "offset",
                     "size"]).to_pandas()
        self.shape, self.chunks = self.meta["shape"], self.meta["chunks"]
        self.nchunks = [-(-s // c) for s, c in zip(self.shape, self.chunks)]
        n = self.nchunks
        r = self.refs
        r["key"] = (r.dim_0 * n[1] + r.dim_1) * n[2] + r.dim_2
        self.by_key = r.set_index("key")
        a = self.meta["attrs"]
        self.scale, self.offset = a["scale_factor"], a["add_offset"]
        self.fill = int(self.meta["fill"])
        self.bytes_fetched = 0
        self.zstd = Zstd()

    def url(self, path):
        return path.removeprefix("/vsicurl/").replace(
            "https://data.source.coop/", HOST)

    def chunk(self, t, cy, cx):
        """One chunk as raw int16, (512, 512); edge chunks are padded."""
        n = self.nchunks
        r = self.by_key.loc[(t * n[1] + cy) * n[2] + cx]
        ch = self.chunks[1:]
        if not r["present"]:
            return np.full(ch, self.fill, np.int16)
        req = urllib.request.Request(self.url(r["path"]), headers={
            "Range": "bytes=%d-%d" % (r["offset"], r["offset"] + r["size"] - 1)})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=60) as f:
                    raw = f.read()
                if len(raw) != r["size"]:
                    raise IOError(f"short read: {len(raw)} of {r['size']}")
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
        self.bytes_fetched += len(raw)
        v = np.frombuffer(self.zstd.decode(raw), "<i2").reshape(ch)
        # TIFF predictor 2: each value is stored as the difference from its
        # left neighbour, so a cumulative sum along the row restores it
        # (int16 arithmetic wraps exactly as the encoder's did).
        return np.cumsum(v, axis=-1, dtype=np.int16)

    def window(self, start, count, workers=16):
        """Raw int16 for a (time, y, x) window, each chunk fetched once."""
        c = self.chunks
        out = np.empty(count, np.int16)
        lo = [s // k for s, k in zip(start, c)]
        hi = [(s + m - 1) // k for s, m, k in zip(start, count, c)]
        jobs = [(t, y, x) for t in range(lo[0], hi[0] + 1)
                for y in range(lo[1], hi[1] + 1) for x in range(lo[2], hi[2] + 1)]
        with ThreadPoolExecutor(workers) as ex:
            got = dict(zip(jobs, ex.map(lambda j: self.chunk(*j), jobs)))
        for (t, y, x), v in got.items():
            sl_src, sl_dst = [], []
            for d, (i, b) in enumerate(zip((y, x), (1, 2))):
                g0 = max(i * c[b], start[b]); g1 = min((i + 1) * c[b], start[b] + count[b])
                sl_src.append(slice(g0 - i * c[b], g1 - i * c[b]))
                sl_dst.append(slice(g0 - start[b], g1 - start[b]))
            out[(t - start[0], *sl_dst)] = v[tuple(sl_src)]
        return out

    def degc(self, raw):
        v = raw.astype(np.float32) * self.scale + self.offset
        v[raw == self.fill] = np.nan
        return v


if __name__ == "__main__":
    man = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "manifest.json"))
    T = Table()
    for name, w in man["oracle"].items():
        t0 = time.time()
        raw = T.window(w["start"], w["count"])
        h = hashlib.sha256(raw.astype("<i2").tobytes()).hexdigest()
        print(f"{name:20s} {h} {'equal' if h == w['sha256'] else 'DIFFERS'}"
              f"  {time.time() - t0:.1f} s")
