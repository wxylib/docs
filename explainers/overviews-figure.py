"""Figure and check for explainers/overviews.md: which overview gdalwarp's
-ovr AUTO reads, and which one `wxy warp` reads.

Warps the world fixture (wxylib/fixtures cog/world-int16-deflate.tif,
720 x 360 with overviews of 360, 180 and 90 columns) to global lon/lat
grids of 30 to 1000 columns. For each, the level real gdalwarp selects
(GDALWarp in the libgdal that rasterio bundles, called through ctypes,
read from its debug log) and the level `wxy warp --dry-run` plans.

    cargo build --release -p wxy-cli    # in wxylib/core
    python overviews-figure.py ../../fixtures ../../core/target/release/wxy

Needs rasterio, numpy and matplotlib.
"""

import ctypes
import glob
import json
import os
import re
import subprocess
import sys
import tempfile

import matplotlib.pyplot as plt
import numpy as np
import rasterio

ROOT, WXY = sys.argv[1], sys.argv[2]
SRC = os.path.join(ROOT, "cog/world-int16-deflate.tif")

libs = os.path.join(os.path.dirname(rasterio.__file__), os.pardir, "rasterio.libs")
gdal = ctypes.CDLL(glob.glob(os.path.join(libs, "libgdal*.so*"))[0])
vp = ctypes.c_void_p
gdal.GDALAllRegister()
gdal.GDALOpen.restype = vp
gdal.GDALOpen.argtypes = [ctypes.c_char_p, ctypes.c_int]
gdal.GDALClose.argtypes = [vp]
gdal.GDALWarpAppOptionsNew.restype = vp
gdal.GDALWarpAppOptionsNew.argtypes = [ctypes.POINTER(ctypes.c_char_p), vp]
gdal.GDALWarpAppOptionsFree.argtypes = [vp]
gdal.GDALWarp.restype = vp
gdal.GDALWarp.argtypes = [ctypes.c_char_p, vp, ctypes.c_int, ctypes.POINTER(vp),
                          vp, ctypes.POINTER(ctypes.c_int)]
gdal.CPLSetConfigOption.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
HANDLER = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_int, ctypes.c_char_p)
gdal.CPLPushErrorHandler.argtypes = [HANDLER]
logs = []
handler = HANDLER(lambda cls, no, msg: logs.append(msg.decode()))
gdal.CPLPushErrorHandler(handler)
gdal.CPLSetConfigOption(b"CPL_DEBUG", b"WARP")


def gdalwarp_level(args):
    """The level gdalwarp reads: 0 full resolution, k overview k - 1."""
    logs.clear()
    argv = (ctypes.c_char_p * (len(args) + 1))(*[a.encode() for a in args], None)
    opts = gdal.GDALWarpAppOptionsNew(argv, None)
    h = gdal.GDALOpen(SRC.encode(), 0)
    err = ctypes.c_int(0)
    out = gdal.GDALWarp(b"/vsimem/ovr.tif", None, 1, (vp * 1)(h), opts,
                        ctypes.byref(err))
    gdal.GDALClose(out)
    gdal.GDALClose(h)
    gdal.GDALWarpAppOptionsFree(opts)
    for m in logs:
        r = re.search(r"Selecting overview level (\d+)", m)
        if r:
            return int(r.group(1)) + 1
    return 0


def wxy_level(extent, size, tmp):
    out = subprocess.run(
        [WXY, "warp", SRC, os.path.join(tmp, "o.zarr"), "--crs", "EPSG:4326",
         "--extent", *map(str, extent), "--size", *map(str, size),
         "--no-wrap", "--dry-run"],
        check=True, capture_output=True, text=True)
    return json.loads(out.stdout)["source"]["level"]


with rasterio.open(SRC) as s:
    widths = [s.width] + [s.width // f for f in s.overviews(1)]

extent = (-180.0, -90.0, 180.0, 90.0)
cols = sorted(set(np.unique(np.geomspace(30, 1000, 70).astype(int)))
              | {72, 80, 90, 180, 240, 360, 480, 720})
rows = []
with tempfile.TemporaryDirectory() as tmp:
    for w in cols:
        size = (w, max(1, w // 2))
        args = ["-t_srs", "EPSG:4326", "-te", *map(str, extent),
                "-ts", *map(str, size), "-r", "near"]
        rows.append((w, gdalwarp_level(args), wxy_level(extent, size, tmp)))
same = sum(g == x for _, g, x in rows)
print(f"{same} of {len(rows)} targets: wxy reads the level gdalwarp reads")
for w, g, x in rows:
    if g != x:
        print(f"  {w} columns: gdalwarp level {g}, wxy level {x}")

INK, MUTED, G, X = "#0b0b0b", "#52514e", "#eb6834", "#2a78d6"
fig, ax = plt.subplots(figsize=(9, 3.8))
fig.patch.set_facecolor("#fcfcfb")
ratio = np.array([widths[0] / w for w, _, _ in rows])
ax.step(ratio, [x for _, _, x in rows], where="post", color=X, lw=2,
        label="wxy warp (--dry-run)")
ax.plot(ratio, [g for _, g, _ in rows], "o", color=G, ms=5,
        label="gdalwarp -ovr AUTO")
for k, wk in enumerate(widths):
    r = widths[0] / wk
    ax.axvline(r, color=MUTED, lw=0.6, ls=":")
    ax.text(r * 1.02, 0.45, f"{wk} columns" if k else "720 columns",
            rotation=90, va="bottom", ha="left", fontsize=8, color=MUTED)
ax.set_xscale("log")
ax.set_xticks([0.75, 1, 1.5, 2, 3, 4, 6, 8, 12, 16, 24])
ax.set_xticklabels(["0.75", "1", "1.5", "2", "3", "4", "6", "8", "12", "16", "24"])
ax.minorticks_off()
ax.set_yticks(range(len(widths)))
ax.set_yticklabels(["full"] + [f"overview {k}" for k in range(len(widths) - 1)])
ax.set_xlabel("source cells per target cell (720 / target columns)",
              color=MUTED, fontsize=9)
ax.set_title(f"Level read for a global lon/lat target: {same} of {len(rows)} "
             "targets agree", color=INK, fontsize=11, loc="left")
ax.legend(frameon=False, fontsize=9, labelcolor=MUTED, loc="lower right")
ax.tick_params(colors=MUTED, labelsize=8)
for sp in ("top", "right"):
    ax.spines[sp].set_visible(False)
fig.tight_layout()
fig.savefig("img/overviews.png", dpi=110, facecolor=fig.get_facecolor())
