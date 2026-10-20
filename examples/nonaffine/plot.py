"""Oracle and figures for polygon coverage on grids that are not a regular
lattice (examples/nonaffine/README.md).

The Rust example in wxylib/core writes every case as JSON: cell outlines
in the polygon's CRS, the polygons, their index-space rings, and the
coverage each method gives. This script checks the world-space method
cell by cell against OGR (GEOS intersection areas of each cell outline
with each polygon), writes oracle.csv, and draws the figures.

    cargo run --release -p wxy-warp --example nonaffine_cover -- nonaffine.json
    python3 plot.py nonaffine.json
"""

import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import PolyCollection
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from osgeo import ogr

HERE = Path(__file__).resolve().parent
BLUES = LinearSegmentedColormap.from_list(
    "blues", ["#ffffff", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])
DIVERGE = LinearSegmentedColormap.from_list(
    "diverge", ["#b8461b", "#eb6834", "#f5f4f0", "#3987e5", "#1c5cab"])
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#c9c8c0"
TITLES = {
    "rotated": "rotated affine",
    "rect-edges": "rectilinear,\nwalls given",
    "rect-centres": "rectilinear,\ncentres given",
    "fan-centres": "curvilinear sector,\ncentres given",
    "fan-edges": "curvilinear sector,\ncorners given",
}

plt.rcParams.update({
    "font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.titlesize": 10,
    "axes.titlecolor": INK,
})


def ring_geom(rings):
    g = ogr.Geometry(ogr.wkbPolygon)
    for r in rings:
        lr = ogr.Geometry(ogr.wkbLinearRing)
        for x, y in r:
            lr.AddPoint_2D(float(x), float(y))
        lr.CloseRings()
        g.AddGeometry(lr)
    return g


def as_grid(cover, shape):
    a = np.zeros(shape)
    for r, c, f in cover:
        a[r, c] = f
    return a


def oracle(case):
    """OGR's fraction of every cell under each polygon, as arrays."""
    h, w = case["shape"]
    cells = [ring_geom([q]) if q else None for q in case["outlines"]]
    out = []
    for p in case["polygons"]:
        poly = ring_geom(p)
        env = poly.GetEnvelope()
        a = np.zeros((h, w))
        for i, cell in enumerate(cells):
            if cell is None:
                continue
            e = cell.GetEnvelope()
            if e[0] > env[1] or e[1] < env[0] or e[2] > env[3] or e[3] < env[2]:
                continue
            a.flat[i] = poly.Intersection(cell).GetArea() / cell.GetArea()
        out.append(a)
    return out


def cell_polys(case):
    return [np.array(q) for q in case["outlines"]]


def draw_world(ax, case, values, cmap, norm, line=INK, lw=1.0):
    pc = PolyCollection(cell_polys(case), array=values.ravel(), cmap=cmap, norm=norm,
                        edgecolors=GRID, linewidths=0.3)
    ax.add_collection(pc)
    for p in case["polygons"]:
        for r in p:
            r = np.array(r)
            ax.plot(r[:, 0], r[:, 1], color=line, lw=lw)
    ax.autoscale_view()
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    return pc


def main(path):
    doc = json.load(open(path))
    cases = doc["cases"]
    rows = []
    covers = {}
    for case in cases:
        shape = case["shape"]
        truth = oracle(case)
        covers[case["name"]] = truth
        for k, t in enumerate(truth):
            row = {"case": case["name"], "polygon": k, "cells": int((t > 1e-6).sum())}
            for m in ["world", "dense", "index"]:
                got = as_grid(case[f"cover_{m}"][k], shape)
                row[f"max_diff_{m}"] = f"{np.abs(got - t).max():.2e}"
            rows.append(row)
            print(row)
    with open(HERE / "oracle.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)

    # 1. every grid, cells shaded by the world-space fraction
    fig, axes = plt.subplots(2, 3, figsize=(11, 7))
    axes = axes.ravel()
    axes[5].axis("off")
    norm = plt.Normalize(0, 1)
    for ax, case in zip(axes, cases):
        f = sum(covers[case["name"]])
        pc = draw_world(ax, case, np.clip(f, 0, 1), BLUES, norm)
        ax.set_title(TITLES[case["name"]])
    cb = fig.colorbar(pc, ax=axes[5], orientation="horizontal", fraction=0.5, aspect=12)
    cb.set_label("fraction of cell covered", color=INK)
    fig.savefig(HERE / "grids.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # 2. the two spaces for the curvilinear sector
    case = next(c for c in cases if c["name"] == "fan-centres")
    h, w = case["shape"]
    fig, (a0, a1, a2) = plt.subplots(1, 3, figsize=(13, 4.6))
    world = sum(covers[case["name"]])
    draw_world(a0, case, np.clip(world, 0, 1), BLUES, norm)
    a0.set_title("polygon's CRS: cells interpolated from\nthe coordinates, clipped by the polygon")
    for ax, key, title in [
        (a1, "index_vertices", "index space, vertices moved:\nedges stay straight"),
        (a2, "index_dense", "index space, densified:\nedges follow the grid"),
    ]:
        cov = "cover_index" if key == "index_vertices" else "cover_dense"
        f = sum(as_grid(c, (h, w)) for c in case[cov])
        ax.imshow(np.clip(f, 0, 1), cmap=BLUES, norm=norm, extent=(0, w, h, 0),
                  interpolation="nearest")
        for v in range(w + 1):
            ax.axvline(v, color=GRID, lw=0.3)
        for v in range(h + 1):
            ax.axhline(v, color=GRID, lw=0.3)
        for p in case[key]:
            for r in p:
                r = np.array(r)
                ax.plot(r[:, 0], r[:, 1], color=INK, lw=1.0)
        if key == "index_dense":
            for p in case["index_vertices"]:
                for r in p:
                    r = np.array(r)
                    ax.plot(r[:, 0], r[:, 1], color=SERIES[1], lw=0.8, ls="--")
        ax.set_xlim(0, w)
        ax.set_ylim(h, 0)
        ax.set_aspect("equal")
        ax.set_xlabel("pixel")
        ax.set_ylabel("line")
        ax.set_title(title)
    a2.plot([], [], color=SERIES[1], ls="--", label="vertices only")
    a2.legend(loc="lower right", frameon=False, fontsize=8)
    fig.savefig(HERE / "two-spaces.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # 3. where index-space fractions (densified) differ from world ones
    fig, axes = plt.subplots(2, 3, figsize=(11, 7))
    axes = axes.ravel()
    axes[5].axis("off")
    lim = 0.02
    dnorm = TwoSlopeNorm(vmin=-lim, vcenter=0, vmax=lim)
    for ax, case in zip(axes, cases):
        d = sum(as_grid(c, case["shape"]) for c in case["cover_dense"]) - sum(covers[case["name"]])
        pc = draw_world(ax, case, np.clip(d, -lim, lim), DIVERGE, dnorm, line=MUTED, lw=0.4)
        ax.set_title(f"{TITLES[case['name']]}: largest {np.abs(d).max():.3f}")
    cb = fig.colorbar(pc, ax=axes[5], orientation="horizontal", fraction=0.5, aspect=12,
                      extend="both")
    cb.set_label("index (densified) minus world fraction", color=INK)
    fig.savefig(HERE / "difference.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # 4. densify sweep and cost
    fig, (a0, a1) = plt.subplots(1, 2, figsize=(11, 3.8))
    for i, case in enumerate(cases):
        pts = [(s["densify"], s["max_cell_diff"]) for s in case["sweep"] if s["densify"]]
        x = [p[0] for p in pts]
        y = [max(p[1], 1e-7) for p in pts]
        a0.plot(x, y, marker="o", ms=4, lw=1.5, color=SERIES[i], label=TITLES[case["name"]])
    a0.set_xscale("log")
    a0.set_yscale("log")
    a0.invert_xaxis()
    a0.set_xlabel("densify (longest edge, in cells)")
    a0.set_ylabel("largest cell fraction difference\nfrom the world-space clip")
    a0.legend(frameon=False, fontsize=8)
    a0.grid(True, color=GRID, lw=0.4)
    t = doc["timing"]
    cells = [r["cells"] for r in t]
    for i, (key, label) in enumerate([
        ("index", "index, vertices moved"),
        ("dense", "index, densified 0.25"),
        ("world", "world-space clip"),
    ]):
        a1.plot(cells, [r[key] * 1000 for r in t], marker="o", ms=4, lw=1.5,
                color=SERIES[i], label=label)
    a1.set_xscale("log")
    a1.set_yscale("log")
    a1.set_xlabel("cells in the curvilinear grid")
    a1.set_ylabel("milliseconds (two polygons)")
    a1.legend(frameon=False, fontsize=8)
    a1.grid(True, color=GRID, lw=0.4)
    fig.tight_layout()
    fig.savefig(HERE / "densify.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else HERE / "nonaffine.json")
