"""Figures from the cuts fetch.py keeps in work/. A product not yet cut is
left out of each figure (and named in its title)."""
import os
from datetime import date, timedelta

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import fetch as F

W = F.WORK
NAMES = {"bran": "BRAN2023 temp, 2.5 m", "glorys": "GLORYS12 thetao, 0.5 m",
         "ostia": "OSTIA analysed_sst", "mur": "MUR analysed_sst"}
COLOURS = {"bran": "#1f5fa8", "glorys": "#c2452d", "ostia": "#2e8b57", "mur": "#7a4fa3"}
ORDER = ["bran", "glorys", "ostia", "mur"]


def load(k):
    p = os.path.join(W, k + ".npz")
    return np.load(p) if os.path.exists(p) else None


def missing(kind):
    return [NAMES[k].split()[0] for k in ORDER if load(f"{k}_{kind}") is None]


def note(kind):
    m = missing(kind)
    return f" (not yet: {', '.join(m)})" if m else ""


# 1. one day, four maps on one colour scale, and each minus MUR
maps = {k: load(f"{k}_map") for k in ORDER}
maps = {k: v for k, v in maps.items() if v is not None}
fig, axs = plt.subplots(2, len(maps), figsize=(3.6 * len(maps), 7), squeeze=False,
                        constrained_layout=True)
vmin, vmax = 17, 27
mur = maps.get("mur")


def on_mur_grid(m):
    """Nearest value of map m at each 0.1 degree cell centre of the box."""
    lon = np.arange(F.BBOX[0] + 0.05, F.BBOX[1], 0.1)
    lat = np.arange(F.BBOX[2] + 0.05, F.BBOX[3], 0.1)
    ix = np.clip(np.searchsorted(m["lon"], lon), 0, len(m["lon"]) - 1)
    iy = np.clip(np.searchsorted(m["lat"], lat), 0, len(m["lat"]) - 1)
    return m["v"][np.ix_(iy, ix)], lon, lat


for j, (k, m) in enumerate(maps.items()):
    ax = axs[0, j]
    im = ax.pcolormesh(m["lon"], m["lat"], m["v"], cmap="turbo", vmin=vmin, vmax=vmax,
                       shading="nearest", rasterized=True)
    ax.set_title(f"{NAMES[k]}\n{m['v'].shape[1]} by {m['v'].shape[0]} cells", fontsize=9)
    ax.set_aspect(1 / np.cos(np.deg2rad(-32.5)))
    ax = axs[1, j]
    if mur is not None and k != "mur":
        a, lon, lat = on_mur_grid(m)
        b, _, _ = on_mur_grid(mur)
        d = a - b
        dm = ax.pcolormesh(lon, lat, d, cmap="RdBu_r", vmin=-2, vmax=2, shading="nearest",
                           rasterized=True)
        ax.set_title(f"minus MUR: mean {np.nanmean(d):+.2f}, sd {np.nanstd(d):.2f} C",
                     fontsize=9)
        ax.set_aspect(1 / np.cos(np.deg2rad(-32.5)))
    else:
        ax.axis("off")
fig.colorbar(im, ax=axs[0, :], shrink=0.8, label="degrees C")
if mur is not None and len(maps) > 1:
    fig.colorbar(dm, ax=axs[1, :], shrink=0.8, label="difference from MUR (C)")
fig.suptitle(f"Tasman Sea, {F.DAY:%d %B %Y}{note('map')}", fontsize=11)
fig.savefig("maps.png", dpi=110)

# 2. a year of the box mean, daily
days = [date(2010, 1, 1) + timedelta(d) for d in range(365)]
fig, (ax, bx) = plt.subplots(2, 1, figsize=(10, 6.5), sharex=True,
                             gridspec_kw={"height_ratios": [2, 1]}, constrained_layout=True)
ser = {k: load(f"{k}_series") for k in ORDER}
ser = {k: s for k, s in ser.items() if s is not None}
for k, s in ser.items():
    ax.plot(days, s["v"], color=COLOURS[k], lw=1.4, label=f"{NAMES[k]} ({float(s['seconds']):.0f} s)")
    if "mur" in ser and k != "mur":
        bx.plot(days, s["v"] - ser["mur"]["v"], color=COLOURS[k], lw=1.2)
ax.set_ylabel("box mean (C)"); ax.legend(fontsize=8, frameon=False)
bx.axhline(0, color="#999", lw=0.8); bx.set_ylabel("minus MUR (C)")
ax.set_title(f"Daily mean over {F.BBOX[0]:g}-{F.BBOX[1]:g}E, {-F.BBOX[3]:g}-{-F.BBOX[2]:g}S, "
             f"2010, area weighted{note('series')}", fontsize=10)
fig.savefig("series.png", dpi=110)

# 3. a section across the East Australian Current
secs = {"bran": load("bran_section"), "glorys": load("glorys_section")}
panels = [("bran", "v", "BRAN2023 temp", "inferno", (2, 26)),
          ("glorys", "thetao", "GLORYS12 thetao", "inferno", (2, 26)),
          ("glorys", "so", "GLORYS12 so", "viridis", (34.3, 35.8))]
panels = [p for p in panels if secs[p[0]] is not None]
fig, axs = plt.subplots(1, len(panels), figsize=(max(4.4 * len(panels), 7), 4), squeeze=False,
                        sharey=True, constrained_layout=True)
for ax, (k, var, title, cmap, lim) in zip(axs[0], panels):
    s = secs[k]
    m = ax.pcolormesh(s["lon"], s["depth"], s[var], cmap=cmap, vmin=lim[0], vmax=lim[1],
                      shading="nearest", rasterized=True)
    ax.set_title(f"{title}, {float(s['lat']):.2f}N", fontsize=9)
    ax.set_xlabel("longitude (E)")
    fig.colorbar(m, ax=ax, shrink=0.85, label="psu" if var == "so" else "C")
axs[0, 0].set_ylim(F.SECTION_DEPTH, 0); axs[0, 0].set_ylabel("depth (m)")
gone = [NAMES[k].split()[0] for k in secs if secs[k] is None]
fig.suptitle(f"Across the EAC at {-F.SECTION_LAT:g}S, {F.DAY:%d %b %Y}"
             + (f" (not yet: {', '.join(gone)})" if gone else ""),
             fontsize=11)
fig.savefig("section.png", dpi=110)
