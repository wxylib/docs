"""Figure for explainers/geoloc.md: how GDAL's geolocation-array
transformer turns a position back into a source cell.

Left: the swath fixture (wxylib/fixtures curvilinear/swath-120x160), its
cells placed by 2D longitude and latitude arrays, every tenth row and
column drawn. Middle: a close-up, with the quadrilaterals joining
neighbouring array points, a regular lattice like the backmap's, a target
point, and the quadrilateral that holds it. Right: what GDAL's warper
writes for the swath on a polar stereographic grid (the fixture oracle
swath-to-3031-bilinear), which wxy-warp matches cell for cell.

    python geoloc-figure.py ../../fixtures/curvilinear
"""

import json
import os
import sys

import matplotlib.patches as mp
import matplotlib.pyplot as plt
import numpy as np

D = sys.argv[1]
NY, NX = 120, 160
lon = np.fromfile(os.path.join(D, "swath-120x160-lon.bin"), "<f8").reshape(NY, NX)
lat = np.fromfile(os.path.join(D, "swath-120x160-lat.bin"), "<f8").reshape(NY, NX)
val = np.fromfile(os.path.join(D, "swath-120x160-values.bin"), "<f4").reshape(NY, NX)
case = [c for c in json.load(open(os.path.join(D, "manifest.json")))["cases"]
        if c["name"] == "swath-to-3031"][0]
warped = np.fromfile(os.path.join(D, "swath-to-3031-bilinear.bin"), "<f4")
warped = warped.reshape(case["height"], case["width"])

INK, MUTED = "#0b0b0b", "#52514e"
GRID, HIT, LATTICE = "#2a78d6", "#eb6834", "#52514e"

fig, axs = plt.subplots(1, 3, figsize=(12, 4.4),
                        gridspec_kw=dict(width_ratios=[1.25, 1, 1]))
fig.patch.set_facecolor("#fcfcfb")

# left: the swath in lon/lat
ax = axs[0]
ax.pcolormesh(lon, lat, val, cmap="Greys", shading="nearest")
for j in range(0, NY, 10):
    ax.plot(lon[j], lat[j], color=GRID, lw=0.6)
for i in range(0, NX, 10):
    ax.plot(lon[:, i], lat[:, i], color=GRID, lw=0.6)
j0, i0 = 60, 80
zoom = (lon[j0 - 2:j0 + 3, i0 - 2:i0 + 3], lat[j0 - 2:j0 + 3, i0 - 2:i0 + 3])
zx0, zx1 = zoom[0].min(), zoom[0].max()
zy0, zy1 = zoom[1].min(), zoom[1].max()
ax.add_patch(mp.Rectangle((zx0, zy0), zx1 - zx0, zy1 - zy0, fill=False,
                          ec=HIT, lw=1.5))
ax.set_title("Source: 120 x 160 cells placed by\n2D lon/lat arrays",
             color=INK, fontsize=10, loc="left")
ax.set_xlabel("longitude", color=MUTED, fontsize=9)
ax.set_ylabel("latitude", color=MUTED, fontsize=9)

# middle: close-up of the inverse
ax = axs[1]
for j in range(j0 - 2, j0 + 3):
    ax.plot(lon[j, i0 - 2:i0 + 3], lat[j, i0 - 2:i0 + 3], color=GRID, lw=1)
for i in range(i0 - 2, i0 + 3):
    ax.plot(lon[j0 - 2:j0 + 3, i], lat[j0 - 2:j0 + 3, i], color=GRID, lw=1)
ax.plot(lon[j0 - 2:j0 + 3, i0 - 2:i0 + 3].ravel(),
        lat[j0 - 2:j0 + 3, i0 - 2:i0 + 3].ravel(), "o", color=GRID, ms=4)
# a regular lattice at about the backmap's spacing
area = (lon.max() - lon.min()) * (lat.max() - lat.min())
size = np.sqrt(area / (NX * NY * 1.3))
gx = np.arange(np.floor(zx0 / size) * size, zx1 + size, size)
gy = np.arange(np.floor(zy0 / size) * size, zy1 + size, size)
for x in gx:
    ax.axvline(x, color=LATTICE, lw=0.4, ls=":")
for y in gy:
    ax.axhline(y, color=LATTICE, lw=0.4, ls=":")
# the target point: inside cell (j0, i0), at s = 0.3, t = 0.6
s, t = 0.3, 0.6
q = [(lon[j0, i0], lat[j0, i0]), (lon[j0, i0 + 1], lat[j0, i0 + 1]),
     (lon[j0 + 1, i0 + 1], lat[j0 + 1, i0 + 1]), (lon[j0 + 1, i0], lat[j0 + 1, i0])]
px = (1 - t) * ((1 - s) * q[0][0] + s * q[1][0]) + t * ((1 - s) * q[3][0] + s * q[2][0])
py = (1 - t) * ((1 - s) * q[0][1] + s * q[1][1]) + t * ((1 - s) * q[3][1] + s * q[2][1])
ax.add_patch(mp.Polygon(q, closed=True, fc=HIT, alpha=0.25, ec=HIT, lw=1.5))
ax.plot(px, py, "*", color=INK, ms=12)
ax.annotate("target point: 0.3 and 0.6 of the way\nacross array points 80-81 and 60-61\n(inverse bilinear)",
            (px, py), xytext=(-60, -78), textcoords="offset points",
            bbox=dict(fc="#fcfcfb", ec="none", alpha=0.9),
            color=INK, fontsize=8.5)
ax.set_xlim(zx0 - size / 2, zx1 + size / 2)
ax.set_ylim(zy0 - size / 2, zy1 + size / 2)
ax.set_title("Close-up: array points (blue), backmap\nlattice (dotted), the cell found",
             color=INK, fontsize=10, loc="left")
ax.set_xlabel("longitude", color=MUTED, fontsize=9)

# right: GDAL's warp
ax = axs[2]
ax.imshow(np.where(warped == 0, np.nan, warped), cmap="Greys",
          interpolation="nearest")
ax.set_title("Warped to polar stereographic:\nGDAL's output; wxy's is identical",
             color=INK, fontsize=10, loc="left")
ax.set_xticks([])
ax.set_yticks([])

for a in axs:
    a.tick_params(colors=MUTED, labelsize=8)
    for sp in a.spines.values():
        sp.set_color(MUTED)
fig.tight_layout()
fig.savefig("img/geoloc.png", dpi=110, facecolor=fig.get_facecolor())
