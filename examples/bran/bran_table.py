"""Read BRAN2023 temp straight from its mdim-refs byte table: no netCDF
library, no GDAL, no Zarr. A chunk is a row (path, offset, size); its bytes
are one HTTP range request, then zlib, then a 2-byte unshuffle."""
import json, os, sys, time, zlib, urllib.request
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pyarrow.parquet as pq
import pyarrow.fs as pafs

STORE = os.environ.get(
    "BRAN_STORE", "s3://aadc-transfer/michae_sum/e2e/bran2023-daily-temp")


def _fs(url):
    if url.startswith("s3://"):
        ep = os.environ.get("AWS_S3_ENDPOINT")
        fs = pafs.S3FileSystem(
            endpoint_override=ep, region=os.environ.get("AWS_REGION", "us-east-1"),
            force_virtual_addressing=os.environ.get("AWS_VIRTUAL_HOSTING", "YES") != "NO",
            anonymous="AWS_ACCESS_KEY_ID" not in os.environ)
        return fs, url[5:]
    return pafs.LocalFileSystem(), url


class Table:
    def __init__(self, store=STORE, array="temp"):
        fs, root = _fs(store)
        with fs.open_input_stream(f"{root}/flat/arrays.json") as f:
            meta = json.loads(f.read())
        self.meta = next(a for a in meta["arrays"] if a["array"] == array)
        t = pq.read_table(f"{root}/flat/refs_{array}.parquet", filesystem=fs,
                          columns=["dim_0", "dim_1", "dim_2", "dim_3",
                                   "present", "path", "offset", "size"])
        self.refs = t.to_pandas()
        self.shape, self.chunks = self.meta["shape"], self.meta["chunks"]
        self.nchunks = [s // c for s, c in zip(self.shape, self.chunks)]
        n = self.nchunks
        self.refs["key"] = ((self.refs.dim_0 * n[1] + self.refs.dim_1) * n[2]
                            + self.refs.dim_2) * n[3] + self.refs.dim_3
        self.by_key = self.refs.set_index("key")
        self.scale = self.meta["attrs"]["scale_factor"]
        self.offset = self.meta["attrs"]["add_offset"]
        self.fill = int(self.meta["fill"])
        self.bytes_fetched = 0

    def url(self, path):
        return path.removeprefix("/vsicurl/")

    def chunk(self, t, z, cy, cx):
        """One chunk as raw int16, (300, 300)."""
        n = self.nchunks
        r = self.by_key.loc[((t * n[1] + z) * n[2] + cy) * n[3] + cx]
        ch = self.chunks[2:]
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
        b = np.frombuffer(zlib.decompress(raw), np.uint8)
        # HDF5 shuffle, element size 2: all first bytes, then all second bytes
        return b.reshape(2, -1).T.copy().view("<i2").reshape(ch)

    def window(self, start, count, workers=16):
        """Raw int16 for a 4-d window, fetching each chunk it touches once."""
        c = self.chunks
        out = np.empty(count, np.int16)
        lo = [s // k for s, k in zip(start, c)]
        hi = [(s + n - 1) // k for s, n, k in zip(start, count, c)]
        jobs = [(t, z, y, x) for t in range(lo[0], hi[0] + 1)
                for z in range(lo[1], hi[1] + 1)
                for y in range(lo[2], hi[2] + 1)
                for x in range(lo[3], hi[3] + 1)]
        with ThreadPoolExecutor(workers) as ex:
            for key, a in zip(jobs, ex.map(lambda k: self.chunk(*k), jobs)):
                t, z, y, x = key
                # chunk origin and its overlap with the window
                o = [t * c[0], z * c[1], y * c[2], x * c[3]]
                a = a.reshape(c)
                sl_src, sl_dst = [], []
                for d in range(4):
                    a0 = max(start[d], o[d]); a1 = min(start[d] + count[d], o[d] + c[d])
                    sl_src.append(slice(a0 - o[d], a1 - o[d]))
                    sl_dst.append(slice(a0 - start[d], a1 - start[d]))
                out[tuple(sl_dst)] = a[tuple(sl_src)]
        return out

    def degc(self, raw):
        v = raw.astype("f4") * self.scale + self.offset
        v[raw == self.fill] = np.nan
        return v


if __name__ == "__main__":
    # The two windows the wxy reader and GDAL agree on (design repo,
    # commit-criteria.md): print their SHA-256 for comparison.
    import hashlib
    T = Table()
    print(len(T.refs), "references")
    for name, s, c in [("chunk-t0-z0-y4-x0", [0, 0, 1200, 0], [1, 1, 300, 300]),
                       ("row-tlast-z10-y750", [364, 10, 750, 0], [1, 1, 1, 3600])]:
        a = T.window(s, c)
        print(name, hashlib.sha256(a.astype("<i2").tobytes()).hexdigest())
