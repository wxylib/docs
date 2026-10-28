"""Figure bytemap.png: the 2024 analysed_sst byte table alone (935,496 rows,
one per COG tile). No tile is read.

    MUR_STORE=.../out python3 make_bytemap.py
"""
import os, sys
import numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mur_table import Table

T = Table()
r = T.refs
n = T.nchunks
# A tile of one constant value (all land, or all -1.8 C under sea ice)
# compresses to the most common size; the bottom row of padded edge tiles
# is smaller still.
CONST = int(r["size"].mode()[0])
day = r.groupby("dim_0")["size"].sum() / 1e6
print(f"{len(r):,} rows, {r['size'].sum() / 1e9:.1f} GB referenced; "
      f"constant tile {CONST} bytes ({(r['size'] == CONST).mean():.1%} of tiles); "
      f"largest {r['size'].max() / 1e3:.0f} kB; MB per day {day.min():.0f} to {day.max():.0f}")

fig = plt.figure(figsize=(11, 7.2), constrained_layout=True)
gs = fig.add_gridspec(2, 2, height_ratios=[1.25, 1])
for i, (t, lab) in enumerate([(0, "1 January 2024"), (182, "1 July 2024")]):
    ax = fig.add_subplot(gs[0, i])
    d = r[r.dim_0 == t]
    g = np.full(n[1:], np.nan); g[d.dim_1, d.dim_2] = d["size"] / 1e3
    im = ax.imshow(g, cmap="Blues", vmin=0, vmax=np.nanpercentile(g, 99.5),
                   extent=[-180, 180.4, -92.1, 90], interpolation="nearest")
    ax.set_title(f"compressed tile size, {lab}", fontsize=10)
    ax.set_xticks([-180, -90, 0, 90, 180]); ax.set_yticks([-60, -30, 0, 30, 60])
    ax.tick_params(labelsize=8)
fig.colorbar(im, ax=fig.axes[:2], shrink=.7, label="kB per 512 x 512 tile")
ax = fig.add_subplot(gs[1, 0])
dates = np.datetime64("2024-01-01") + np.arange(len(day)).astype("timedelta64[D]")
ax.plot(dates, day.values, color="#1f5fa8", lw=1.5)
ax.set_ylabel("MB of tiles per day"); ax.grid(alpha=.3); ax.tick_params(labelsize=8)
ax.set_title("bytes per day (2,556 tiles each)", fontsize=10)
ax = fig.add_subplot(gs[1, 1])
ax.hist(r["size"] / 1e3, bins=120, color="#1f5fa8")
ax.set_yscale("log"); ax.set_xlabel("kB per tile"); ax.set_ylabel("tiles in 2024")
ax.set_title(f"tile sizes: {(r['size'] == CONST).mean():.0%} are {CONST} bytes "
             "(one constant value)", fontsize=10)
ax.grid(alpha=.3); ax.tick_params(labelsize=8)
fig.suptitle("MUR analysed_sst 2024 from its byte table alone: 935,496 rows, "
             f"{r['size'].sum() / 1e9:.0f} GB referenced, nothing read", fontsize=11)
fig.savefig("bytemap.png", dpi=105)
