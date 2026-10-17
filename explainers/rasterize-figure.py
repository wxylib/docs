"""Figure for explainers/rasterize.md: which cells a polygon gets.

A star-shaped polygon with a hole on a 16 x 12 grid, burned by GDAL's
rasterizer (`gdal vector rasterize`, through osgeo.gdal) by cell centre and with
ALL_TOUCHED, and the fraction of each cell it covers (computed here with
shapely; wxylib's --coverage gets it from controlledburn). The centre
panel also shows the scanlines at row centres and where the polygon's
edges cross them.

    python rasterize-figure.py
"""

import matplotlib.pyplot as plt
import json

import numpy as np
import shapely
from matplotlib.colors import ListedColormap
from osgeo import gdal

gdal.UseExceptions()

W, H = 16, 12
rng = np.random.default_rng(7)
k = 11
a = (np.arange(k) + rng.uniform(0, 0.6, k)) * 2 * np.pi / k
r = 5.6 * rng.uniform(0.55, 1.0, k)
ext = list(zip(8 + r * np.cos(a), 6 + r * np.sin(a) * 0.95))
b = np.arange(6) * 2 * np.pi / 6 + 0.3
hole = list(zip(8.4 + 1.3 * np.cos(b), 6.2 + 1.3 * np.sin(b)))
poly = shapely.Polygon(ext, [hole])
# index space: x = column, y = row (down), one unit per cell. GDAL's grid
# is north up, so the polygon goes to it with y flipped: y' = H - y.
flipped = shapely.transform(poly, lambda c: np.column_stack([c[:, 0], H - c[:, 1]]))
gdal.FileFromMemBuffer("/vsimem/poly.geojson", json.dumps(
    {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {},
         "geometry": shapely.geometry.mapping(flipped)}]}))


def burn(all_touched):
    out = gdal.Run("vector", "rasterize", input="/vsimem/poly.geojson",
                   output="", output_format="MEM", burn=[1], init=[0],
                   extent=[0, 0, W, H], size=[W, H], output_data_type="Byte",
                   all_touched=all_touched)
    return out.Output().ReadAsArray()


centre, touched = burn(False), burn(True)
cover = np.zeros((H, W))
for row in range(H):
    for col in range(W):
        cover[row, col] = poly.intersection(shapely.box(col, row, col + 1, row + 1)).area

INK, MUTED, FILL, LINE = "#0b0b0b", "#52514e", "#2a78d6", "#eb6834"

fig, axs = plt.subplots(1, 3, figsize=(12.5, 3.9))
fig.patch.set_facecolor("#fcfcfb")
panels = [
    (centre, f"Cell centre (default): {int(centre.sum())} cells"),
    (touched, f"ALL_TOUCHED: {int(touched.sum())} cells"),
    (cover, f"Coverage: {cover.sum():.1f} cells of area"),
]
for ax, (img, title) in zip(axs, panels):
    if img is cover:
        ax.imshow(np.where(img > 0, img, np.nan), cmap="Blues", vmin=0,
                  vmax=1.15, extent=(0, W, H, 0), interpolation="nearest")
    else:
        ax.imshow(img, cmap=ListedColormap(["#fcfcfb", FILL]), alpha=0.55,
                  extent=(0, W, H, 0), interpolation="nearest")
    for i in range(W + 1):
        ax.axvline(i, color=MUTED, lw=0.4)
    for i in range(H + 1):
        ax.axhline(i, color=MUTED, lw=0.4)
    for ring in [poly.exterior, *poly.interiors]:
        x, y = ring.xy
        ax.plot(x, y, color=LINE, lw=1.6)
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(title, color=INK, fontsize=10, loc="left")
    for sp in ax.spines.values():
        sp.set_color(MUTED)

# scanlines at row centres, and the crossings, on the centre panel
ax = axs[0]
for row in range(H):
    yc = row + 0.5
    ax.axhline(yc, color=MUTED, lw=0.6, ls=":")
    xs = []
    for ring in [poly.exterior, *poly.interiors]:
        c = np.asarray(ring.coords)
        for (x0, y0), (x1, y1) in zip(c[:-1], c[1:]):
            lo, hi = min(y0, y1), max(y0, y1)
            if lo <= yc < hi and y0 != y1:
                xs.append(x0 + (yc - y0) * (x1 - x0) / (y1 - y0))
    ax.plot(xs, [yc] * len(xs), "o", color=INK, ms=3)
for ax in axs[2:]:
    for row in range(H):
        for col in range(W):
            v = cover[row, col]
            if 0.005 < v < 0.995:
                ax.text(col + 0.5, row + 0.5, f"{v:.2f}"[1:],
                        ha="center", va="center", fontsize=5.5, color=INK)
fig.tight_layout()
fig.savefig("img/rasterize.png", dpi=110, facecolor=fig.get_facecolor())
