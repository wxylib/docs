"""Figures for the zonal statistics examples, from results.csv.

    python3 plot.py
"""

import csv
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.path import Path as MPath

HERE = Path(__file__).resolve().parent
STYLE = {
    "wxy-centre": dict(color="#1b6ca8", marker="o", label="wxy zonal (cell centres)"),
    "wxy-all-touched": dict(color="#5aa3d6", marker="s", label="wxy zonal --all-touched"),
    "wxy-coverage": dict(color="#0b3d63", marker="D", label="wxy zonal --coverage"),
    "dense": dict(color="#c0392b", marker="^", label="GDAL rasterize + whole read"),
    "exactextract": dict(color="#e08e0b", marker="v", label="exactextract (Python)"),
}


def load():
    rows = list(csv.DictReader(open(HERE / "results.csv")))
    out = defaultdict(lambda: defaultdict(list))
    for r in rows:
        out[r["experiment"]][r["method"]].append(
            (int(r["cells"]), int(r["polygons"]), float(r["seconds"]), float(r["peak_mib"])))
    return out


def panel(ax, series, xi, yi, xlabel, ylabel):
    for m, pts in series.items():
        pts = sorted(pts)
        ax.plot([p[xi] for p in pts], [p[yi] for p in pts], **STYLE[m])
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, which="both", alpha=0.3)


def results():
    data = load()
    for exp, xi, xlabel, title in [
        ("scaling", 0, "source cells", "1024 polygons over half the source, growing source"),
        ("sparse", 1, "polygons (1.5 km radius)", "scattered polygons on a 32768 x 32768 source"),
    ]:
        fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.2))
        panel(a, data[exp], xi, 2, xlabel, "wall time (s)")
        panel(b, data[exp], xi, 3, xlabel, "peak memory (MiB)")
        a.legend(fontsize=8)
        fig.suptitle(title)
        fig.tight_layout()
        fig.savefig(HERE / f"{exp}.png", dpi=110)
        plt.close(fig)


def star(cx, cy, r, n, rng):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    rr = r * (0.7 + 0.3 * rng.random(n))
    return np.c_[cx + rr * np.cos(t), cy + rr * np.sin(t)]


def idea():
    """What lazy rasterization keeps: spans of cells, and the chunks they
    cross; an illustration on a 48 x 48 grid of 12 x 12 chunks."""
    n, c = 48, 12
    rng = np.random.default_rng(3)
    outer = star(20, 26, 15, 40, rng)
    hole = star(21, 25, 5, 16, rng)[::-1]
    path = MPath.make_compound_path(MPath(np.r_[outer, outer[:1]], closed=True),
                                    MPath(np.r_[hole, hole[:1]], closed=True))
    po, ph = MPath(outer), MPath(hole)

    def inside(x, y):
        p = np.c_[x.ravel(), y.ravel()]
        return po.contains_points(p) & ~ph.contains_points(p)

    yy, xx = np.mgrid[0:n, 0:n] + 0.5
    centre = inside(xx, yy).reshape(n, n)
    k = 8  # covered fraction by k x k subsampling, for the picture only
    sy, sx = np.mgrid[0:n * k, 0:n * k] / k + 0.5 / k
    frac = inside(sx, sy).reshape(n * k, n * k)
    frac = frac.reshape(n, k, n, k).mean(axis=(1, 3))

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.6))
    titles = ["dense: a zone raster the size of the source",
              "lazy: row spans (cell centres)",
              "lazy: spans plus covered fractions on the edge"]
    for ax, t in zip(axes, titles):
        ax.set_xlim(0, n)
        ax.set_ylim(n, 0)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(t, fontsize=10)
    touched = {(r // c, q // c) for r, q in zip(*np.nonzero(frac > 0))}
    # dense: every cell held
    axes[0].imshow(np.where(centre, 1.0, 0.15), cmap="Reds", vmin=0, vmax=1.4,
                   extent=(0, n, n, 0))
    # spans
    for r in range(n):
        row = np.r_[False, centre[r], False].astype(int)
        d = np.diff(row)
        for a, b in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
            axes[1].add_patch(Rectangle((a, r + 0.15), b - a, 0.7, color="#1b6ca8"))
    # coverage: interior spans and edge fractions
    edge = (frac > 0) & (frac < 1)
    axes[2].imshow(np.where(edge, frac, np.nan), cmap="Blues", vmin=0, vmax=1.2,
                   extent=(0, n, n, 0))
    for r in range(n):
        row = np.r_[False, frac[r] >= 1, False].astype(int)
        d = np.diff(row)
        for a, b in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
            axes[2].add_patch(Rectangle((a, r + 0.15), b - a, 0.7, color="#0b3d63"))
    for ax in axes[1:]:
        for (cy, cx) in touched:
            ax.add_patch(Rectangle((cx * c, cy * c), c, c, fill=True,
                                   color="#f4d03f", alpha=0.25, zorder=0))
    for ax in axes:
        for v in range(0, n + 1, c):
            ax.axhline(v, color="0.4", lw=0.8)
            ax.axvline(v, color="0.4", lw=0.8)
        ax.add_patch(PathPatch(path, fill=False, lw=1.2, color="k"))
    fig.text(0.5, 0.02, "grey lines: source chunks; yellow: chunks fetched, each once",
             ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 0.97))
    fig.savefig(HERE / "idea.png", dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    idea()
    if (HERE / "results.csv").exists():
        results()
