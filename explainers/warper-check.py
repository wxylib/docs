"""Check for explainers/warper.md: a warp that GDAL splits into many chunks
gives GDAL's numbers from `wxy warp`, cell for cell.

The fixture oracle cases split into at most 16 chunks; this check takes a
larger split: the polar stereographic fixture to a 3000 x 600 lon/lat
grid, which GDAL's warper (`gdal raster reproject`, through osgeo.gdal)
splits into 44 chunks at its default 64 MB memory limit because the
source windows of the larger chunks are mostly empty.

    cargo build --release -p wxy-cli    # in wxylib/core
    python warper-check.py ../../fixtures/cog/polar-f32-zstd-bigtiff.tif \
        ../../core/target/release/wxy

Needs GDAL's Python bindings (osgeo), numpy and zarr.
"""

import re
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import zarr
from osgeo import gdal

gdal.UseExceptions()
SRC, WXY = sys.argv[1], sys.argv[2]
CRS = "EPSG:4326"
EXTENT = (-180.0, -90.0, 180.0, -50.0)
WIDTH, HEIGHT = 3000, 600

logs = []
gdal.PushErrorHandler(lambda cls, no, msg: logs.append(msg))
pat = re.compile(r"Src=\d+,\d+,\d+x\d+ Dst=\d+,\d+,\d+x\d+")
tmp = tempfile.mkdtemp()
try:
    for name, alg in [("near", "nearest"), ("bilinear", "bilinear"),
                      ("cubic", "cubic")]:
        logs.clear()
        gdal.SetConfigOption("CPL_DEBUG", "ON")
        want = gdal.Run("raster", "reproject", input=SRC, output="",
                        output_format="MEM", dst_crs=CRS, bbox=list(EXTENT),
                        size=[WIDTH, HEIGHT], resampling=alg,
                        num_threads=1).Output().ReadAsArray()
        gdal.SetConfigOption("CPL_DEBUG", None)
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
