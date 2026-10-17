"""Curvilinear vignette: a polar 2D lon/lat grid with a time axis, warped to
south polar stereographic by `wxy warp`, every time step under one plan.

Writes curvilinear.zarr (an xarray-style CF store: data(time, y, x) with 2D
lon and lat), runs the wxy CLI on it, and draws curvilinear.png.

Needs numpy, xarray, zarr (3.x), matplotlib, and the wxy binary (build it
in wxylib/core with `cargo build --release -p wxy-cli`; pass its path as
WXY or put it on PATH). Run from this folder: python run.py
"""

import json
import os
import shutil
import subprocess

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
import zarr

WXY = os.environ.get("WXY", "wxy")
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "curvilinear.zarr")
OUT = os.path.join(HERE, "warped.zarr")

# A ring of cells round Antarctica: 180 columns of longitude that cross the
# antimeridian, 50 rows from 60S to 85S, each row sheared east a little so
# the grid is curvilinear rather than a rectilinear lon/lat grid.
ny, nx, nt = 50, 180, 3
j, i = np.meshgrid(np.arange(ny), np.arange(nx), indexing="ij")
lon = -180.0 + 360.0 * (i + 0.5) / nx + 0.2 * j
lon = (lon + 180.0) % 360.0 - 180.0
lat = -60.0 - 25.0 * (j + 0.5) / ny

# A field that moves with time: a wave train round the pole that rotates
# 40 degrees a step, over a gradient from the coast out.
days = np.arange(nt)
data = np.stack([
    np.cos(np.radians(3 * (lon - 40 * t))) * (j / ny) + 0.5 * (1 - j / ny)
    for t in days
]).astype("float32")

ds = xr.Dataset(
    {"data": (("time", "y", "x"), data)},
    coords={
        "time": ("time", days.astype("float64"), {"units": "days since 2026-01-01"}),
        "lon": (("y", "x"), lon, {"standard_name": "longitude", "units": "degrees_east"}),
        "lat": (("y", "x"), lat, {"standard_name": "latitude", "units": "degrees_north"}),
    },
)
ds["data"].attrs["coordinates"] = "lon lat"
shutil.rmtree(SRC, ignore_errors=True)
ds.to_zarr(SRC, zarr_format=3, mode="w", consolidated=False)

# The warp: EPSG:3031, 400 x 400 cells of 15 km, bilinear. First the plan
# only (--dry-run reads no data), then the warp itself.
extent = ["-3000000", "-3000000", "3000000", "3000000"]
args = [WXY, "warp", SRC, OUT, "--crs", "EPSG:3031", "--extent", *extent,
        "--size", "400", "400", "-r", "bilinear", "--source-array", "/data", "--overwrite"]
plan = subprocess.run(args + ["--dry-run"], check=True, capture_output=True, text=True)
with open(os.path.join(HERE, "plan.json"), "w") as f:
    f.write(plan.stdout)
subprocess.run(args, check=True)

warped = zarr.open_group(OUT, mode="r")["data"][:]
print("warped shape", warped.shape)

fig, ax = plt.subplots(2, nt, figsize=(3.2 * nt, 6.4), constrained_layout=True)
for t in days:
    ax[0, t].imshow(data[t], cmap="viridis", vmin=0, vmax=1, aspect="auto")
    ax[0, t].set_title(f"day {t}: source cells (x, y)", fontsize=9)
    ax[1, t].imshow(warped[t], cmap="viridis", vmin=0, vmax=1)
    ax[1, t].set_title(f"day {t}: warped to EPSG:3031", fontsize=9)
for a in ax.flat:
    a.set_xticks([])
    a.set_yticks([])
fig.savefig(os.path.join(HERE, "curvilinear.png"), dpi=110)
