"""Zonal statistics: time and peak memory of `wxy zonal` against GDAL's
dense rasterize and exactextract, on synthetic rasters and polygons.

    python3 bench.py data      # write rasters and polygons to $WXY_BENCH
    python3 bench.py run       # time every method, write results.csv
    python3 bench.py check     # compare the methods' statistics

Each method runs as its own process; its time is wall-clock and its
memory the peak resident set (ru_maxrss), with the files already in the
page cache. Needs rasterio, numpy, exactextract and a `wxy` binary
(`WXY`, default `wxy` on PATH).
"""

import csv
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("WXY_BENCH", HERE / "data"))
WXY = os.environ.get("WXY", "wxy")
CRS = "EPSG:32755"
CELL = 30.0
X0, Y0 = 300000.0, 6400000.0
NODATA = -9999.0

# rasters (side in cells) for the scaling runs, and polygon counts on the
# largest one for the sparse runs
SIDES = [4096, 8192, 16384, 32768]
COUNTS = [10, 100, 1000, 10000]
METHODS = ["wxy-centre", "wxy-all-touched", "wxy-coverage", "dense", "exactextract"]


def raster(side):
    import rasterio
    from rasterio.windows import Window

    path = DATA / f"r{side}.tif"
    if path.exists():
        return path
    profile = dict(
        driver="GTiff", width=side, height=side, count=1, dtype="float32",
        crs=CRS, transform=rasterio.Affine(CELL, 0, X0, 0, -CELL, Y0),
        tiled=True, blockxsize=512, blockysize=512, compress="deflate",
        nodata=NODATA, BIGTIFF="YES",
    )
    rng = np.random.default_rng(side)
    x = np.arange(side) / side
    with rasterio.open(path, "w", **profile) as dst:
        for r0 in range(0, side, 512):
            y = (np.arange(r0, r0 + 512) / side)[:, None]
            v = (100 * np.sin(7 * x) * np.cos(5 * y) + 50 * y
                 + rng.normal(0, 2, (512, side))).astype("float32")
            # a lake of nodata
            v[(x - 0.3) ** 2 + (y - 0.6) ** 2 < 0.01] = NODATA
            dst.write(v, 1, window=Window(0, r0, side, 512))
    return path


def star(cx, cy, r, rng, n=64, hole=False):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    rr = r * (0.7 + 0.3 * rng.random(n))
    ring = [[cx + a * math.cos(b), cy + a * math.sin(b)] for a, b in zip(rr, t)]
    rings = [ring + [ring[0]]]
    if hole:
        h = [[cx + 0.3 * r * math.cos(b), cy + 0.3 * r * math.sin(b)] for b in t[::-4]]
        rings.append(h + [h[0]])
    return rings


def polygons(name, centres, r, seed):
    path = DATA / f"{name}.geojson"
    if path.exists():
        return path
    rng = np.random.default_rng(seed)
    feats = [
        {"type": "Feature", "id": f"z{k}", "properties": {"zone": k},
         "geometry": {"type": "Polygon",
                      "coordinates": star(cx, cy, r, rng, hole=k % 4 == 0)}}
        for k, (cx, cy) in enumerate(centres)
    ]
    path.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    return path


def tiling(side, n=32, seed=0):
    """n x n polygons over a raster of `side` cells, about half its area."""
    rng = np.random.default_rng(seed)
    step = side * CELL / n
    c = [(X0 + (i + 0.5) * step + rng.normal(0, step / 20),
          Y0 - (j + 0.5) * step + rng.normal(0, step / 20))
         for j in range(n) for i in range(n)]
    return polygons(f"tile{side}", c, step * 0.45, seed)


def scattered(side, count, r=1500.0, seed=1):
    """`count` polygons of about 1.5 km radius scattered over the raster."""
    rng = np.random.default_rng(seed + count)
    span = side * CELL - 4 * r
    c = [(X0 + 2 * r + rng.random() * span, Y0 - 2 * r - rng.random() * span)
         for _ in range(count)]
    return polygons(f"scatter{side}-{count}", c, r, seed)


def cases():
    big = SIDES[-1]
    for side in SIDES:
        yield "scaling", side, 1024, raster(side), tiling(side)
    for count in COUNTS:
        yield "sparse", big, count, raster(big), scattered(big, count)


# --- the methods, each a process: argv after `bench.py method` ---------


def dense(tif, gj, out):
    """The usual raster workflow: burn zone ids into a raster the size of
    the source with GDAL's rasterizer, read the whole source, reduce."""
    import rasterio
    from rasterio import features

    feats = json.loads(Path(gj).read_text())["features"]
    with rasterio.open(tif) as src:
        zones = features.rasterize(
            ((f["geometry"], k + 1) for k, f in enumerate(feats)),
            out_shape=(src.height, src.width), transform=src.transform,
            fill=0, dtype="int32")
        v = src.read(1)
    ok = (zones > 0) & (v != NODATA)
    z, x = zones[ok], v[ok].astype("float64")
    n = len(feats) + 1
    count = np.bincount(z, minlength=n)
    total = np.bincount(z, weights=x, minlength=n)
    lo = np.full(n, np.inf)
    hi = np.full(n, -np.inf)
    np.minimum.at(lo, z, x)
    np.maximum.at(hi, z, x)
    with open(out, "w") as f:
        f.write("feature,count,sum,min,max\n")
        for k, ft in enumerate(feats):
            f.write(f"{ft['id']},{count[k + 1]},{total[k + 1]},{lo[k + 1]},{hi[k + 1]}\n")


def exact(tif, gj, out):
    import rasterio
    from exactextract import exact_extract

    feats = json.loads(Path(gj).read_text())["features"]
    with rasterio.open(tif) as src:
        df = exact_extract(src, feats, ["count", "sum", "min", "max"],
                           include_cols=["zone"], output="pandas")
    df.to_csv(out, index=False)


def measure(argv, stdout):
    t = time.perf_counter()
    with open(stdout, "w") as f:
        p = subprocess.Popen(argv, stdout=f)
        _, status, use = os.wait4(p.pid, 0)
    if status != 0:
        raise SystemExit(f"failed: {' '.join(map(str, argv))}")
    return time.perf_counter() - t, use.ru_maxrss / 1024  # MiB


def command(method, tif, gj, out):
    if method.startswith("wxy"):
        argv = [WXY, "zonal", str(tif), str(gj), "--crs", CRS]
        argv += {"wxy-centre": [], "wxy-all-touched": ["--all-touched"],
                 "wxy-coverage": ["--coverage"]}[method]
        return argv, out
    return [sys.executable, __file__, method, str(tif), str(gj), str(out)], os.devnull


def run():
    rows = []
    for exp, side, count, tif, gj in cases():
        for m in METHODS:
            out = DATA / f"{exp}-{side}-{count}-{m}.csv"
            argv, stdout = command(m, tif, gj, out)
            if m == "dense" and exp == "scaling" and side > 16384:
                # source, zones and the in-zone copies pass 15 GiB here
                continue
            measure(argv, stdout)  # warm the page cache and the binary
            secs, mib = min(measure(argv, stdout) for _ in range(2))
            rows.append(dict(experiment=exp, side=side, cells=side * side,
                             polygons=count, method=m,
                             seconds=round(secs, 3), peak_mib=round(mib, 1)))
            print(rows[-1], flush=True)
    with open(HERE / "results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)


def alone(tif, geom):
    """GDAL's centre burn of one polygon by itself: its cells with a value."""
    import rasterio
    from rasterio import features
    from rasterio.windows import from_bounds

    xy = np.array(geom["coordinates"][0])
    with rasterio.open(tif) as src:
        w = from_bounds(*xy.min(0), *xy.max(0), src.transform)
        c0, r0 = max(0, math.floor(w.col_off) - 1), max(0, math.floor(w.row_off) - 1)
        c1 = min(src.width, math.ceil(w.col_off + w.width) + 1)
        r1 = min(src.height, math.ceil(w.row_off + w.height) + 1)
        win = rasterio.windows.Window(c0, r0, c1 - c0, r1 - r0)
        v = src.read(1, window=win)
        m = features.rasterize([(geom, 1)], out_shape=v.shape,
                               transform=src.window_transform(win), dtype="uint8")
    return int(((m == 1) & (v != NODATA)).sum())


def check():
    """Centre burns agree with GDAL's: with the dense burn where zones do
    not overlap, and with GDAL burning each zone alone where they do (a
    zone raster holds one zone per cell, so overlaps go to the last zone).
    Coverage agrees with exactextract."""
    import pandas as pd

    for exp, side, count, tif, gj in cases():
        if exp == "scaling" and side > 16384:
            continue
        p = lambda m: DATA / f"{exp}-{side}-{count}-{m}.csv"
        wc = pd.read_csv(p("wxy-centre"))
        d = pd.read_csv(p("dense"))
        differ = np.nonzero(wc["count"].values != d["count"].values)[0]
        feats = json.loads(Path(gj).read_text())["features"]
        wrong = [k for k in differ if alone(tif, feats[k]["geometry"]) != wc["count"][k]]
        cov = pd.read_csv(p("wxy-coverage"))
        ee = pd.read_csv(p("exactextract")).sort_values("zone")
        dc = np.nanmax(np.abs(cov["count"].values - ee["count"].values))
        has = ee["count"].values > 0
        dm = np.max(np.abs(cov["mean"].values[has] - (ee["sum"] / ee["count"]).values[has]))
        print(f"{exp} {side} {count}: centre == dense for {len(wc) - len(differ)} zones,"
              f" overlapping {len(differ)} == GDAL alone: {len(differ) - len(wrong)};"
              f" coverage vs exactextract: count {dc:.1e}, mean {dm:.1e}")


if __name__ == "__main__":
    what = sys.argv[1]
    if what == "data":
        DATA.mkdir(parents=True, exist_ok=True)
        for c in cases():
            print(*c[:3], flush=True)
    elif what == "run":
        run()
    elif what == "check":
        check()
    elif what == "dense":
        dense(*sys.argv[2:5])
    elif what == "exactextract":
        exact(*sys.argv[2:5])
