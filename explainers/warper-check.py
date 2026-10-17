"""Check for explainers/warper.md: a warp that GDAL splits into many chunks
gives GDAL's numbers from `wxy warp`, cell for cell.

The fixture oracle cases split into at most 16 chunks; this check takes a
larger split: the polar stereographic fixture to a 3000 x 600 lon/lat
grid, which GDAL's warper (through rasterio) splits into 44 chunks at its
default 64 MB memory limit because the source windows of the larger
chunks are mostly empty.

    cargo build --release -p wxy-cli    # in wxylib/core
    python warper-check.py ../../fixtures/cog/polar-f32-zstd-bigtiff.tif \
        ../../core/target/release/wxy

Needs rasterio, numpy and zarr.
"""

import logging
import re
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import rasterio
import zarr
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, reproject

SRC, WXY = sys.argv[1], sys.argv[2]
CRS = "EPSG:4326"
EXTENT = (-180.0, -90.0, 180.0, -50.0)
WIDTH, HEIGHT = 3000, 600

logs = []


class Grab(logging.Handler):
    def emit(self, record):
        logs.append(record.getMessage())


log = logging.getLogger("rasterio")
log.setLevel(logging.DEBUG)
log.addHandler(Grab())

with rasterio.open(SRC) as src:
    a = src.read(1)
    nodata = src.nodata
    src_transform, src_crs = src.transform, src.crs

pat = re.compile(r"Src=\d+,\d+,\d+x\d+ Dst=\d+,\d+,\d+x\d+")
tmp = tempfile.mkdtemp()
try:
    for name, alg in [("near", Resampling.nearest),
                      ("bilinear", Resampling.bilinear),
                      ("cubic", Resampling.cubic)]:
        logs.clear()
        want = np.full((HEIGHT, WIDTH), nodata, a.dtype)
        with rasterio.Env(CPL_DEBUG="ON"):
            reproject(a, want, src_transform=src_transform, src_crs=src_crs,
                      dst_transform=from_bounds(*EXTENT, WIDTH, HEIGHT),
                      dst_crs=CRS, resampling=alg, src_nodata=nodata,
                      dst_nodata=nodata)
        chunks = sum(1 for m in logs if pat.search(m))
        out = f"{tmp}/{name}.zarr"
        subprocess.run(
            [WXY, "warp", SRC, out, "--crs", CRS,
             "--extent", *map(str, EXTENT), "--size", str(WIDTH), str(HEIGHT),
             "-r", name, "--no-wrap", "--overview", "none"],
            check=True, capture_output=True)
        got = np.asarray(zarr.open_group(out, mode="r")["data"])
        got = got.reshape(want.shape)
        differ = int(((got != want) & ~(np.isnan(got) & np.isnan(want))).sum())
        print(f"{name:8s} GDAL chunks: {chunks:3d}  "
              f"cells differing: {differ} of {want.size}")
finally:
    shutil.rmtree(tmp)
