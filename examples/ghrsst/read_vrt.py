"""GDAL reads the published multidimensional VRT (ghrsst-mur-v2.vrt) with
osgeo.gdal: the 2024 manifest windows (at the VRT's time offset for
2024-01-01), the latest day around Tasmania (vrt-tasman.png), and a year of
daily values at one place, timed against the byte table (mur_table.py).

    python3 read_vrt.py [manifest.json]

MUR_HOST replaces https://data.source.coop/ in the VRT and the table when
that host cannot be reached directly; the VRT is then rewritten to a local
copy first.
"""
import hashlib, json, os, sys, time, urllib.request
import numpy as np
from osgeo import gdal
import matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt

gdal.UseExceptions()
gdal.SetConfigOption("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
gdal.SetConfigOption("GDAL_HTTP_MULTIPLEX", "YES")
HOST = os.environ.get("MUR_HOST", "https://data.source.coop/")
VRT = "https://data.source.coop/ausantarctic/ghrsst-mur-v2/ghrsst-mur-v2.vrt"

if HOST == "https://data.source.coop/":
    dsn = "/vsicurl/" + VRT
else:
    dsn = "ghrsst-mur-v2-local.vrt"
    if not os.path.exists(dsn):
        txt = urllib.request.urlopen(VRT.replace("https://data.source.coop/", HOST)).read()
        open(dsn, "wb").write(txt.replace(b"https://data.source.coop/", HOST.encode()))

t0 = time.time()
ds = gdal.OpenEx(dsn, gdal.OF_MULTIDIM_RASTER)
root = ds.GetRootGroup()
sst = root.OpenMDArray("analysed_sst")
time_ = root.OpenMDArray("time").ReadAsArray()
y = root.OpenMDArray("y").ReadAsArray(); x = root.OpenMDArray("x").ReadAsArray()
print(f"open + coordinates: {time.time() - t0:.1f} s; shape",
      [d.GetSize() for d in sst.GetDimensions()])

# 1. The 2024 manifest windows: 2024-01-01 is 19723 days since 1970-01-01
t2024 = int(np.searchsorted(time_, 19723))
man = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "manifest.json"))
for name, w in man["oracle"].items():
    t0 = time.time()
    st = [w["start"][0] + t2024] + w["start"][1:]
    raw = sst.ReadAsArray(array_start_idx=st, count=w["count"]).astype("<i2")
    h = hashlib.sha256(raw.tobytes()).hexdigest()
    print(f"{name:20s} {'equal' if h == w['sha256'] else 'DIFFERS'}  {time.time() - t0:.1f} s")

# 2. The latest day around Tasmania and the Tasman Sea
last = len(time_) - 1
r0, r1 = int(np.abs(y + 32).argmin()), int(np.abs(y + 48).argmin())
c0, c1 = int(np.abs(x - 140).argmin()), int(np.abs(x - 160).argmin())
t0 = time.time()
m = sst.GetUnscaled().ReadAsArray(array_start_idx=[last, r0, c0],
                                  count=[1, r1 - r0, c1 - c0])[0]
day = np.datetime64("1970-01-01") + np.timedelta64(int(time_[last]), "D")
print(f"Tasmania window {m.shape} on {day}: {time.time() - t0:.1f} s")
fig, ax = plt.subplots(figsize=(9, 7.4), constrained_layout=True)
im = ax.imshow(m, cmap="turbo", extent=[x[c0], x[c1], y[r1], y[r0]],
               vmin=np.nanpercentile(m, 1), vmax=np.nanpercentile(m, 99))
ax.set_facecolor("#d9d9d9")
fig.colorbar(im, ax=ax, shrink=.8, label="analysed_sst (degrees C)")
ax.set_title(f"MUR SST {day}, 0.01 degree, from ghrsst-mur-v2.vrt "
             f"(time step {last + 1:,} of {len(time_):,})", fontsize=10)
fig.savefig("vrt-tasman.png", dpi=100)

# 3. A year at one place: the VRT opens one COG per day, the table does not
row, col = int(np.abs(y + 44).argmin()), int(np.abs(x - 150).argmin())
t0 = time.time()
v1 = sst.ReadAsArray(array_start_idx=[t2024, row, col], count=[366, 1, 1]).ravel()
tv = time.time() - t0
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mur_table import Table
T = Table()
t0 = time.time()
v2 = T.window([0, row, col], [366, 1, 1]).ravel()
tt = time.time() - t0
print(f"2024 at 44S 150E: VRT {tv:.0f} s, table {tt:.0f} s "
      f"({T.bytes_fetched / 1e6:.1f} MB in 366 range requests); identical: {np.array_equal(v1, v2)}")
