"""Figures for examples/bran: the BRAN2023 store through its byte table.

Exercise 1 reads only the table; exercises 2 to 4 read data, each chunk by
one range request (bran_table.py). The store is a parameter (BRAN_STORE);
while it is keyed, AWS_* must be set, with AWS_S3_ENDPOINT and
AWS_VIRTUAL_HOSTING=NO for the AAD transfer endpoint.

    python3 make_figures.py
"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bran_table import Table
import numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
T = Table()
r = T.refs

# 1. The byte table is a map: nothing but the table is read.
# st_ocean (m), from the store's arrays.json
depth = [2.5,7.5,12.5,17.5,22.7,28.2,34.2,41.0,48.5,56.7,65.7,75.2,85.0,95,105,115,125,135,145,155,165,175,185,195,205.2,217.1,233.2,255.9,286.6,325.9,373.2,427.1,485.2,545.5,610.4,685.9,775.9,880.4,995.5,1115.3,1238.4,1368.2,1507.7,1658.2,1818.4,1985.3,2165.2,2431.1,2894.8,3603.1,4509.2]
EMPTY = r["size"].min()   # an all-fill chunk compresses to this
fig = plt.figure(figsize=(11, 6.4), constrained_layout=True)
gs = fig.add_gridspec(2, 3)
for i, z in enumerate([0, 33, 45]):
    ax = fig.add_subplot(gs[0, i])
    d = r[(r.dim_0 == 0) & (r.dim_1 == z)]
    g = np.full((5, 12), np.nan); g[d.dim_2, d.dim_3] = d["size"] / 1e3
    im = ax.imshow(g, origin="lower", cmap="Blues", vmin=0, vmax=100,
                   extent=[0, 360, -75, 75])
    for (y, x), v in np.ndenumerate(g):
        ax.text(x * 30 + 15, y * 30 - 60, f"{v:.0f}", ha="center", va="center",
                fontsize=6.5, color="white" if v > 55 else "#333")
    ax.set_title(f"depth {depth[z]:g} m, 1 Jan 2010", fontsize=10)
    ax.set_xticks([0, 90, 180, 270, 360]); ax.set_yticks([-60, -30, 0, 30, 60])
    ax.tick_params(labelsize=8)
fig.colorbar(im, ax=fig.axes, shrink=0.6, label="compressed chunk size (kB)")
ax = fig.add_subplot(gs[1, 0:2])
t = r[r.dim_0 == 0].groupby("dim_1")["size"]
ax.plot(t.sum() / 1e6, depth, color="#1f5fa8", lw=2, label="bytes per depth level (MB)")
ax.set_yscale("log"); ax.set_ylim(5000, 2)
ax.set_ylabel("depth (m)"); ax.set_xlabel("MB per level, one day (60 chunks)")
ax2 = fig.add_subplot(gs[1, 2])
land = r[r.dim_0 == 0].assign(e=lambda d: d["size"] == EMPTY).groupby("dim_1")["e"].mean()
ax2.plot(land * 100, depth, color="#1f5fa8", lw=2)
ax2.set_yscale("log"); ax2.set_ylim(5000, 2)
ax2.set_xlabel(f"% chunks of {EMPTY} bytes (all land)"); ax2.set_ylabel("depth (m)")
for a in (ax, ax2):
    a.grid(alpha=.3); a.tick_params(labelsize=8)
fig.suptitle("BRAN2023 temp from its reference table alone: 1,116,900 rows, 60 GB referenced, no data read", fontsize=11)
fig.savefig("bytes-map.png", dpi=110)

lon = 0.05 + 0.1 * np.arange(3600); lat = -74.95 + 0.1 * np.arange(1500)
log = {}
def timed(name, f):
    b0, t0 = T.bytes_fetched, time.time(); v = f()
    log[name] = dict(seconds=round(time.time() - t0, 1),
                     MB=round((T.bytes_fetched - b0) / 1e6, 1)); print(name, log[name]); return v

# 2. One day's global surface: 60 chunks
sfc = timed("surface", lambda: T.degc(T.window([0, 0, 0, 0], [1, 1, 1500, 3600]))[0, 0])
fig, ax = plt.subplots(figsize=(10, 4.6), constrained_layout=True)
im = ax.imshow(sfc, origin="lower", extent=[0, 360, -75, 75], cmap="inferno", vmin=-2, vmax=31)
for x in range(30, 360, 30): ax.axvline(x, color="white", lw=0.4, alpha=.5)
for y in range(-45, 75, 30): ax.axhline(y, color="white", lw=0.4, alpha=.5)
ax.set_title(f"Surface temperature, 1 Jan 2010: 60 range requests, {log['surface']['MB']} MB from 5 GB of netCDF (chunk grid drawn)", fontsize=10)
fig.colorbar(im, ax=ax, label="degrees C", shrink=.8); fig.savefig("surface.png", dpi=110)

# 3. a section along the equator, every depth: 51 x 12 chunks, one row kept from each
y0 = int(np.argmin(abs(lat - 0)))
sec = timed("section", lambda: T.degc(T.window([0, 0, y0, 0], [1, 51, 1, 3600]))[0, :, 0, :])
fig, ax = plt.subplots(figsize=(10, 4.2), constrained_layout=True)
m = ax.pcolormesh(lon, depth, sec, cmap="inferno", vmin=0, vmax=31, shading="nearest")
ax.set_ylim(500, 0); ax.set_xlabel("longitude (degrees E)"); ax.set_ylabel("depth (m)")
ax.set_title(f"Along the equator ({lat[y0]:.2f}N), top 500 m, 1 Jan 2010: 612 chunks, {log['section']['MB']} MB, to keep 0.6% of what was decoded", fontsize=10)
fig.colorbar(m, ax=ax, label="degrees C"); fig.savefig("section.png", dpi=110)

# 4. a year at one place, four depths: 365 chunks per depth
px, py = int(np.argmin(abs(lon - 152.0))), int(np.argmin(abs(lat - -34.0)))
zs = [0, 14, 26, 33]
ts = timed("timeseries", lambda: np.stack(
    [T.degc(T.window([0, z, py, px], [365, 1, 1, 1]))[:, 0, 0, 0] for z in zs], axis=1))
fig, ax = plt.subplots(figsize=(10, 4), constrained_layout=True)
cols = ["#0b3c5d", "#328cc1", "#d9a441", "#a33b20"]
days = np.arange(365)
for i, (z, c) in enumerate(zip(zs, cols)):
    ax.plot(days, ts[:, i], color=c, lw=1.6, label=f"{depth[z]:g} m")
    ax.text(366, ts[-1, i], f"{depth[z]:g} m", color="#333", fontsize=8, va="center")
ax.set_xlim(0, 400); ax.set_xlabel("day of 2010"); ax.set_ylabel("degrees C"); ax.grid(alpha=.3)
ax.legend(loc="upper left", fontsize=8, ncols=4, frameon=False)
ax.set_title(f"East Australian Current off Sydney ({lon[px]:.2f}E, {lat[py]:.2f}N), daily 2010: {log['timeseries']['MB']} MB for {365*len(zs)} values", fontsize=10)
fig.savefig("timeseries.png", dpi=110)
