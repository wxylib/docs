"""Figure views.png: one set of bytes (the daily COGs), one byte-reference
table, several projections of it, and who reads each."""
import matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

STATUS = {"published": "#1f5fa8", "built": "#e07b00", "coming": "#9a9a9a"}
fig, ax = plt.subplots(figsize=(12, 6.2))
ax.set_xlim(0, 12); ax.set_ylim(0, 6.7); ax.axis("off")


def box(x, y, w, h, title, sub="", status=None, fc="#f4f6fa"):
    ec = STATUS.get(status, "#555")
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=fc, ec=ec, lw=2.2 if status else 1.2))
    ax.text(x + w / 2, y + h - 0.2, title, ha="center", va="top", fontsize=10, weight="bold")
    if sub:
        ax.text(x + w / 2, y + h - 0.5, sub, ha="center", va="top", fontsize=8, color="#333",
                linespacing=1.35)


def arrow(x0, y0, x1, y1, label="", color="#555"):
    ax.annotate("", (x1, y1), (x0, y0), arrowprops=dict(arrowstyle="-|>", color=color, lw=1.3))
    if label:
        ax.text((x0 + x1) / 2, (y0 + y1) / 2 + 0.1, label, ha="center", fontsize=7.5,
                color="#333", style="italic")


box(0.1, 3.9, 2.2, 2.4, "daily COGs", "source.coop\nausantarctic/ghrsst-mur-v2\n8,914 days x 5 variables\n512 x 512 tiles\nZSTD + TIFF predictor 2", "published")
box(0.1, 0.5, 2.2, 2.5, "STAC GeoParquet", "one row per day\nstatus: final,\npreliminary, nrt_only\nfile:checksum, file:size", "published")
arrow(1.2, 3.9, 1.2, 3.0, "index")
box(3.0, 3.9, 2.4, 2.4, "mdim VRT (the plan)", "ghrsst-mur-v2.vrt\none Source per day,\nwith SourceSlab counts\nrebuilt daily from\nthe STAC index", "published")
arrow(2.3, 1.7, 3.6, 3.9, "build")
box(3.0, 0.5, 2.4, 2.5, "byte-ref table", "mdim-refs, flat Parquet\none row per tile:\npath, offset, size\nharvested from COG headers\n(the middle stage)", "built")
arrow(4.2, 3.9, 4.2, 3.0, "harvest")
views = [("kerchunk Parquet", "Zarr v2 view\nzstd + imagecodecs_delta", "built", 4.7),
         ("Icechunk", "Zarr v3 view, versioned\nzstd + HorizontalDeltaCodec", "built", 3.05),
         ("flat Parquet", "the table itself\narrays.json + refs_*.parquet", "built", 1.4)]
for name, sub, st, y in views:
    box(6.2, y - 0.1, 2.4, 1.4, name, sub, st)
    arrow(5.4, 1.75, 6.2, y + 0.6, "render" if name == "Icechunk" else "")
readers = [("GDAL, osgeo.gdal, gdalxarray", 5.65, ["vrt", "kerchunk*"]),
           ("zarr-python, xarray", 4.55, ["kerchunk", "icechunk"]),
           ("wxy (Rust, CLI, R, Python)", 3.45, ["kerchunk", "icechunk", "flat"]),
           ("DuckDB, Arrow, Polars", 2.35, ["flat"]),
           ("a short script, a browser", 1.25, ["flat"])]
ys = {"vrt": 5.1, "kerchunk": 5.3, "kerchunk*": 5.3, "icechunk": 3.65, "flat": 2.0}
for name, y, srcs in readers:
    ax.text(9.35, y, name, fontsize=9, va="center",
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#888"))
    for s in srcs:
        if s == "vrt":   # over the top of the views, not through them
            ax.plot([5.4, 6.0, 8.8, 9.3], [6.0, 6.4, 6.4, y], color="#bbb", lw=0.9, zorder=0)
            continue
        ax.plot([8.6, 9.3], [ys[s], y], color="#bbb", lw=0.9, zorder=0,
                ls=":" if s == "kerchunk*" else "-")
for i, (k, c) in enumerate(STATUS.items()):
    lab = {"published": "published", "built": "built and checked for 2024; public store coming",
           "coming": "coming"}[k]
    if k == "coming":
        continue
    ax.add_patch(FancyBboxPatch((0.15 + i * 2.2, 0.05), 0.3, 0.2, boxstyle="round,pad=0.01",
                                fc="white", ec=c, lw=2.2))
    ax.text(0.55 + i * 2.2, 0.15, lab, fontsize=8, va="center")
ax.text(9.3, 0.15, "* kerchunk to GDAL needs a filter plugin", fontsize=7.5, va="center",
        color="#555")
ax.set_title("GHRSST MUR: one set of bytes, one table of where they are, several views of it",
             fontsize=12)
fig.tight_layout()
fig.savefig("views.png", dpi=100)
