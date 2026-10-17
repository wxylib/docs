"""Figure for explainers/kernels.md: why the kernel is stretched when the
target is coarser than the source.

Top: GDAL's bilinear and cubic weights at 1:1 and stretched for a target
four times coarser. Bottom: a zone plate (rings that get finer away from
the centre) warped to a grid about ten times coarser with bilinear, by
GDAL's warper (`gdal raster reproject`, through osgeo.gdal), by
`wxy warp` (GDAL's chunked warp, stretched kernel) and by
`wxy warp --plain` (1:1 kernel).

    cargo build --release -p wxy-cli    # in wxylib/core
    python kernels-figure.py ../../core/target/release/wxy

Needs GDAL's Python bindings (osgeo), numpy, matplotlib and zarr.
"""

import os
import shutil
import subprocess
import sys
import tempfile

import matplotlib.pyplot as plt
import numpy as np
import zarr
from osgeo import gdal

gdal.UseExceptions()

WXY = sys.argv[1]
INK, MUTED = "#0b0b0b", "#52514e"
ONE, WIDE = "#2a78d6", "#eb6834"

# source: a zone plate in lon/lat, 2000 x 2000 cells of 0.005 degrees
N = 2000
SRC_BOUNDS = (145.0, -40.0, 155.0, -30.0)
yy, xx = np.mgrid[-1:1:N * 1j, -1:1:N * 1j]
plate = (np.cos(260 * (xx ** 2 + yy ** 2)) * 1000).astype("float32")

# target: UTM zone 56 south, 160 x 160 cells of 5 km, inside the source
DST_CRS = "EPSG:32756"
DST_BOUNDS = (-174000.0, 5722000.0, 626000.0, 6522000.0)
DW = DH = 160

tmp = tempfile.mkdtemp()
try:
    src_path = os.path.join(tmp, "plate.tif")
    d = gdal.GetDriverByName("GTiff").Create(src_path, N, N, 1, gdal.GDT_Float32,
                                             options=["TILED=YES"])
    x0, y0, x1, y1 = SRC_BOUNDS
    d.SetGeoTransform((x0, (x1 - x0) / N, 0.0, y1, 0.0, -(y1 - y0) / N))
    d.SetProjection("EPSG:4326")
    d.GetRasterBand(1).WriteArray(plate)
    d = None

    gdal_out = gdal.Run("raster", "reproject", input=src_path, output="",
                        output_format="MEM", dst_crs=DST_CRS,
                        bbox=list(DST_BOUNDS), size=[DW, DH],
                        resampling="bilinear", num_threads=1)
    gdal_vals = gdal_out.Output().ReadAsArray()

    def wxy(*extra):
        out = os.path.join(tmp, "out.zarr")
        shutil.rmtree(out, ignore_errors=True)
        subprocess.run([WXY, "warp", src_path, out, "--crs", DST_CRS,
                        "--extent", *map(str, DST_BOUNDS),
                        "--size", str(DW), str(DH), "-r", "bilinear",
                        "--overview", "none", *extra],
                       check=True, capture_output=True)
        return np.asarray(zarr.open_group(out, mode="r")["data"]).reshape(DH, DW)

    chunked, plain = wxy(), wxy("--plain")
finally:
    shutil.rmtree(tmp)

d_chunked = int((chunked != gdal_vals).sum())
d_plain = int((plain != gdal_vals).sum())
print(f"wxy warp vs GDAL: {d_chunked} of {gdal_vals.size} cells differ")
print(f"wxy warp --plain vs GDAL: {d_plain} of {gdal_vals.size} cells differ")


def bilinear(x):
    a = np.abs(x)
    return np.where(a <= 1, 1 - a, 0.0)


def cubic(x):
    a = np.abs(x)
    x2 = x * x
    return np.where(a <= 1, x2 * (1.5 * a - 2.5) + 1,
                    np.where(a <= 2, x2 * (-0.5 * a + 2.5) - 4 * a + 2, 0.0))


fig = plt.figure(figsize=(11, 7.2))
fig.patch.set_facecolor("#fcfcfb")
grid = fig.add_gridspec(2, 4, height_ratios=[1, 1.35], hspace=0.35)

x = np.linspace(-9, 9, 721)
for k, (name, f, r) in enumerate([("bilinear", bilinear, 1),
                                  ("cubic", cubic, 2)]):
    ax = fig.add_subplot(grid[0, 2 * k:2 * k + 2])
    s = 0.25
    w1, ws = f(x), f(x * s)
    ax.plot(x, w1 / w1.sum(), color=ONE, lw=2, label="1:1 (scale 1)")
    ax.plot(x, ws / ws.sum(), color=WIDE, lw=2,
            label=f"target 4x coarser (scale 0.25)")
    ax.axhline(0, color=MUTED, lw=0.6)
    ax.set_xlim(-9, 9)
    ax.set_xticks(range(-8, 9, 2))
    ax.set_yticks([])
    ax.set_xlabel("distance from the target cell centre, in source cells",
                  color=MUTED, fontsize=9)
    ax.set_title(f"{name}: {2 * r} taps at 1:1, {int(2 * r / s)} stretched",
                 color=INK, fontsize=11, loc="left")
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=8)
    if k == 0:
        ax.legend(frameon=False, fontsize=9, labelcolor=MUTED, loc="upper left")

panels = [
    (plate, "Source: 2000 x 2000 zone plate"),
    (gdal_vals, "GDAL bilinear, 160 x 160"),
    (chunked, f"wxy warp: {d_chunked} cells differ"),
    (plain, f"wxy warp --plain: {d_plain} differ"),
]
for k, (img, title) in enumerate(panels):
    ax = fig.add_subplot(grid[1, k])
    ax.imshow(img, cmap="Greys", vmin=-1000, vmax=1000,
              interpolation="nearest")
    ax.set_title(title, color=INK, fontsize=10, loc="left")
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_color(MUTED)

fig.savefig("img/kernels.png", dpi=110, facecolor=fig.get_facecolor(),
            bbox_inches="tight")
