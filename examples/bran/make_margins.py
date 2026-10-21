"""Figures for the "Other margins" section of examples/bran.

The array is (time, depth, lat, lon) in chunks of (1, 1, 300, 300). Any two
dimensions can be the plane of a figure, with the other two held at one
index. This script prices all six planes from the table alone, then reads
three that cut across the chunking: depth by time at a point, latitude by
time along a meridian, and longitude by time along the equator.

    python3 make_margins.py      # same environment as make_figures.py
"""
import itertools, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bran_table import Table
import numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt

T = Table()
r = T.refs
nt, nz, ny, nx = T.shape
lon = 0.05 + 0.1 * np.arange(nx); lat = -74.95 + 0.1 * np.arange(ny)
# st_ocean (m), from the store's arrays.json
depth = np.array([2.5,7.5,12.5,17.5,22.7,28.2,34.2,41.0,48.5,56.7,65.7,75.2,85.0,95,105,115,125,135,145,155,165,175,185,195,205.2,217.1,233.2,255.9,286.6,325.9,373.2,427.1,485.2,545.5,610.4,685.9,775.9,880.4,995.5,1115.3,1238.4,1368.2,1507.7,1658.2,1818.4,1985.3,2165.2,2431.1,2894.8,3603.1,4509.2])
px, py = int(np.argmin(abs(lon - 152.0))), int(np.argmin(abs(lat + 34.0)))   # EAC off Sydney
mx = int(np.argmin(abs(lon - 180.0)))                                          # the date line
ey = int(np.argmin(abs(lat - 0.0)))                                            # the equator
held = {"time": 0, "depth": 0, "lat": py, "lon": px}

# 1. Price every plane from the table: which chunks, how many bytes, how
#    many values kept against how many decoded.
names = ["time", "depth", "lat", "lon"]
cdim = dict(zip(names, T.chunks))
rows = []
for a, b in itertools.combinations(names, 2):
    sel = np.ones(len(r), bool)
    for d, col in zip(names, ["dim_0", "dim_1", "dim_2", "dim_3"]):
        if d not in (a, b):
            sel &= (r[col] == held[d] // cdim[d]).values
    sub = r[sel]
    shape = dict(zip(names, T.shape))
    kept = shape[a] * shape[b]
    decoded = len(sub) * int(np.prod(T.chunks))
    rows.append(dict(plane=f"{a} x {b}", chunks=len(sub), MB=round(sub["size"].sum() / 1e6, 1),
                     values=kept, kept_pct=round(100 * kept / decoded, 2)))
for x in rows:
    print(x)
json.dump(rows, open("margins.json", "w"), indent=1)

log = {}
def timed(name, f):
    b0, t0 = T.bytes_fetched, time.time(); v = f()
    log[name] = dict(seconds=round(time.time() - t0, 1), MB=round((T.bytes_fetched - b0) / 1e6, 1))
    print(name, log[name]); return v

days = np.arange(nt)

# 2. Depth by time at one place: weekly, top 34 levels (to 545 m).
week = days[::7]; zs = np.arange(34)
dt = timed("depth-time", lambda: np.stack(
    [T.degc(T.window([t, 0, py, px], [1, 34, 1, 1]))[0, :, 0, 0] for t in week], axis=1))
fig, ax = plt.subplots(figsize=(10, 4.2), constrained_layout=True)
m = ax.pcolormesh(week, depth[zs], dt, cmap="inferno", vmin=7, vmax=26, shading="nearest")
ax.set_ylim(550, 0); ax.set_xlabel("day of 2010"); ax.set_ylabel("depth (m)")
ax.set_title(f"Depth by time at {lon[px]:.2f}E {lat[py]:.2f}N, weekly: {len(week) * 34} chunks, "
             f"{log['depth-time']['MB']} MB for {len(week) * 34} values", fontsize=10)
fig.colorbar(m, ax=ax, label="degrees C"); fig.savefig("margin-depth-time.png", dpi=110)

# 3. Latitude by time along the date line, surface: one chunk column a day.
lt = timed("lat-time", lambda: T.degc(T.window([0, 0, 0, mx], [nt, 1, ny, 1]))[:, 0, :, 0])
fig, ax = plt.subplots(figsize=(10, 4.2), constrained_layout=True)
m = ax.pcolormesh(days, lat, lt.T, cmap="inferno", vmin=-2, vmax=31, shading="nearest")
ax.set_xlabel("day of 2010"); ax.set_ylabel("latitude (degrees N)")
ax.set_title(f"Surface temperature along {lon[mx]:.2f}E through 2010: {nt * ny // 300} chunks, "
             f"{log['lat-time']['MB']} MB to keep one column of each", fontsize=10)
fig.colorbar(m, ax=ax, label="degrees C"); fig.savefig("margin-lat-time.png", dpi=110)

# 4. Longitude by time along the equator, surface: one chunk row a day.
xt = timed("lon-time", lambda: T.degc(T.window([0, 0, ey, 0], [nt, 1, 1, nx]))[:, 0, 0, :])
fig, ax = plt.subplots(figsize=(10, 5.2), constrained_layout=True)
m = ax.pcolormesh(lon, days, xt, cmap="inferno", vmin=22, vmax=31, shading="nearest")
ax.set_xlabel("longitude (degrees E)"); ax.set_ylabel("day of 2010"); ax.invert_yaxis()
ax.set_title(f"Surface temperature along the equator through 2010: {nt * nx // 300} chunks, "
             f"{log['lon-time']['MB']} MB to keep one row of each", fontsize=10)
fig.colorbar(m, ax=ax, label="degrees C"); fig.savefig("margin-lon-time.png", dpi=110)
json.dump(log, open("margins-reads.json", "w"), indent=1)
