"""Figure for explainers/points.md: reading values at points.

Left: the world fixture (wxylib/fixtures cog/world-int16-deflate.tif) with
its 128 x 128 tiles, and the fixture's 400 random points at GDAL's own
pixel and line positions (points/world-int16-deflate-4326-*.bin); each
tile is labelled with the number of points whose cells it holds, and is
fetched once however many that is. Right: the cells each method reads
around a point, on a small grid: the cell the point falls in (nearest),
the 2 x 2 and 4 x 4 cell centres around it (bilinear, cubic), and, next
to the edge, a cubic kernel whose outer column repeats the edge cells.

    python points-figure.py ../../fixtures
"""

import os
import sys

import matplotlib.patches as mp
import matplotlib.pyplot as plt
import numpy as np
from osgeo import gdal

ROOT = sys.argv[1]
CASE = "world-int16-deflate-4326"
TILE = 128

gdal.UseExceptions()
src = gdal.Open(os.path.join(ROOT, "cog/world-int16-deflate.tif"))
assert src.GetRasterBand(1).GetBlockSize() == [TILE, TILE]
a = src.ReadAsArray()
h, w = a.shape
px = np.fromfile(os.path.join(ROOT, f"points/{CASE}-pixel.bin"), "<f8")
py = np.fromfile(os.path.join(ROOT, f"points/{CASE}-line.bin"), "<f8")
found = np.fromfile(os.path.join(ROOT, f"points/{CASE}-found.bin"), "u1") == 1
px, py = px[found], py[found]

INK, MUTED = "#0b0b0b", "#52514e"
PT, NEAR, BIL, CUB = "#2a78d6", "#eb6834", "#1baf7a", "#6250d6"

fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(12, 4.4),
                               gridspec_kw=dict(width_ratios=[1.9, 1]))
fig.patch.set_facecolor("#fcfcfb")

# left: tiles and points (a bilinear kernel's cells, clamped to the file)
ax0.imshow(a, cmap="Greys", interpolation="nearest", alpha=0.55)
counts = {}
for x, y in zip(px, py):
    r0, c0 = int(np.floor(y - 0.5)), int(np.floor(x - 0.5))
    tiles = {(min(max(r, 0), h - 1) // TILE, min(max(c, 0), w - 1) // TILE)
             for r in (r0, r0 + 1) for c in (c0, c0 + 1)}
    for t in tiles:
        counts[t] = counts.get(t, 0) + 1
for r in range(0, h, TILE):
    ax0.axhline(r - 0.5, color=INK, lw=1)
for c in range(0, w, TILE):
    ax0.axvline(c - 0.5, color=INK, lw=1)
ax0.plot(px - 0.5, py - 0.5, ".", color=PT, ms=4)
for (tr, tc), n in counts.items():
    cx = min(tc * TILE + TILE / 2, (tc * TILE + w) / 2)
    cy = min(tr * TILE + TILE / 2, (tr * TILE + h) / 2)
    ax0.text(cx, cy, str(n), ha="center", va="center", fontsize=11,
             weight="bold", color=INK,
             bbox=dict(fc="#fcfcfb", ec="none", alpha=0.85, pad=1.5))
ax0.set_xlim(-0.5, w - 0.5)
ax0.set_ylim(h - 0.5, -0.5)
ax0.set_title(f"{len(px)} points on the file, {len(counts)} tiles: "
              "each tile fetched once\n(number: points whose bilinear "
              "cells the tile holds)", color=INK, fontsize=10, loc="left")
ax0.set_xticks([])
ax0.set_yticks([])

# right: kernels on a small grid
NX, NY = 12, 8
ax1.set_xlim(0, NX)
ax1.set_ylim(NY, 0)
ax1.set_aspect("equal")
for i in range(NY + 1):
    ax1.axhline(i, color=MUTED, lw=0.5)
for i in range(NX + 1):
    ax1.axvline(i, color=MUTED, lw=0.5)
cx, cy = np.meshgrid(np.arange(NX) + 0.5, np.arange(NY) + 0.5)
ax1.plot(cx.ravel(), cy.ravel(), ".", color=MUTED, ms=3)


def box(c, r, color, repeated=False):
    ax1.add_patch(mp.Rectangle((c + 0.08, r + 0.08), 0.84, 0.84, fc=color,
                               alpha=0.3, ec=color, lw=1.2,
                               ls="--" if repeated else "-"))


def kernel(x, y, k, color):
    back = (k - 2) // 2
    r0 = int(np.floor(y - 0.5)) - back
    c0 = int(np.floor(x - 0.5)) - back
    for r in range(r0, r0 + k):
        for c in range(c0, c0 + k):
            cc, rr = min(max(c, 0), NX - 1), min(max(r, 0), NY - 1)
            box(cc, rr, color, (cc, rr) != (c, r))
    ax1.plot(x, y, "*", color=INK, ms=11)


def label(x, y, text):
    ax1.text(x, y, text, color=INK, fontsize=8.5, ha="center", va="center",
             bbox=dict(fc="#fcfcfb", ec="none", alpha=0.9, pad=1))


box(1, 0, NEAR)
ax1.plot(1.7, 0.6, "*", color=INK, ms=11)
label(1.5, 1.5, "nearest")
kernel(4.8, 0.9, 2, BIL)
label(5.0, 2.5, "bilinear")
kernel(2.3, 4.6, 4, CUB)
label(2.0, 7.5, "cubic")
kernel(11.6, 4.4, 4, CUB)
label(9.5, 6.5, "cubic at the edge")
ax1.set_title("Cells read per method (dashed: an edge\ncell repeated beyond the edge)",
              color=INK, fontsize=10, loc="left")
ax1.set_xticks([])
ax1.set_yticks([])

for ax in (ax0, ax1):
    for sp in ax.spines.values():
        sp.set_color(MUTED)
fig.tight_layout()
fig.savefig("img/points.png", dpi=110, facecolor=fig.get_facecolor(),
            bbox_inches="tight")
