"""Figure for explainers/warper.md: GDAL's chunk list for one warp, and
the source window each chunk reads.

Warps the world fixture (wxylib/fixtures cog/world-int16-deflate.tif) to a
2000 x 2000 south polar stereographic grid with GDAL's warper at a 1 MB
memory limit (gdalwarp -wm 1, through osgeo.gdal; the new `gdal raster
reproject` has no memory limit option), so that the chunking is visible
at a small size, and reads GDAL's chunk list from its debug log.
`wxy warp ... --wm 1 --dry-run` prints the same list.

    python warper-chunks.py ../../fixtures/cog/world-int16-deflate.tif

Needs GDAL's Python bindings (osgeo), numpy and matplotlib.
"""

import re
import sys

import matplotlib.patches as mp
import matplotlib.pyplot as plt
from osgeo import gdal

gdal.UseExceptions()
SIZE = 2000
EXTENT = (-8e6, -8e6, 8e6, 8e6)

logs = []
gdal.PushErrorHandler(lambda cls, no, msg: logs.append(msg))
gdal.SetConfigOption("CPL_DEBUG", "ON")
a = gdal.Open(sys.argv[1]).ReadAsArray()
dst = gdal.Warp("", sys.argv[1], format="MEM", dstSRS="EPSG:3031",
                outputBounds=EXTENT, width=SIZE, height=SIZE,
                resampleAlg="near", warpMemoryLimit=1).ReadAsArray()
gdal.SetConfigOption("CPL_DEBUG", None)

pat = re.compile(r"Src=(\d+),(\d+),(\d+)x(\d+) Dst=(\d+),(\d+),(\d+)x(\d+)")
chunks = [tuple(map(int, m.groups())) for m in map(pat.search, logs) if m]
chunks.sort(key=lambda c: (c[5], c[4]))
for c in chunks:
    print("src %4d %4d %4dx%-4d  dst %4d %4d %4dx%d" % c)

INK, MUTED = "#0b0b0b", "#52514e"
PART, FULL = "#2a78d6", "#eb6834"

fig, (ax0, ax1) = plt.subplots(
    1, 2, figsize=(11, 4.6), gridspec_kw=dict(width_ratios=[1, 1.6]))
fig.patch.set_facecolor("#fcfcfb")
ax0.imshow(dst, cmap="Greys", interpolation="nearest")
ax1.imshow(a, cmap="Greys", interpolation="nearest")
full = {}
for i, (sx, sy, sw, sh, dx, dy, dw, dh) in enumerate(chunks, 1):
    whole = sw == a.shape[1]
    col = FULL if whole else PART
    ax0.add_patch(mp.Rectangle((dx, dy), dw, dh, fc=col, alpha=0.25,
                               ec=col, lw=1.5))
    ax0.text(dx + dw / 2, dy + dh / 2, str(i), ha="center", va="center",
             color=INK, fontsize=10, weight="bold")
    ax1.add_patch(mp.Rectangle((sx, sy), sw, sh, fill=False, ec=col,
                               lw=1.5))
    if whole:
        full.setdefault((sy, sh), []).append(str(i))
    else:
        ax1.text(sx + 3, sy + 2, str(i), ha="left", va="top", color=INK,
                 fontsize=9, weight="bold")
for (sy, sh), ids in full.items():
    ax1.text(a.shape[1] - 4, sy + sh - 3, ", ".join(ids) + ": whole width",
             ha="right", va="bottom", color=INK, fontsize=9, weight="bold")
# only the southern rows are read
ax1.set_ylim(a.shape[0], 170)
ax1.set_aspect(2)
ax0.set_title("Target: 13 chunks of a polar stereographic grid",
              color=INK, fontsize=11, loc="left")
ax1.set_title("Source: the window each chunk reads\n(lon/lat, 0.5 degree cells, rows south of 5 N)",
              color=INK, fontsize=11, loc="left")
for ax in (ax0, ax1):
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color(MUTED)
ax1.legend(handles=[
    mp.Patch(fc="none", ec=PART, lw=1.5, label="window is part of the width"),
    mp.Patch(fc="none", ec=FULL, lw=1.5,
             label="window spans more than 90% of the width, so all of it")],
    loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=2, frameon=False,
    fontsize=9, labelcolor=MUTED)
fig.tight_layout()
fig.savefig("img/warper-chunks.png", dpi=110, facecolor=fig.get_facecolor())
