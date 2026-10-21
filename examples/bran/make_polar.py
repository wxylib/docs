"""Figure for the "Another coordinate system" section of examples/bran.

Twelve days of BRAN2023 surface temperature (the first of each month of
2010) around the Amery Ice Shelf and Prydz Bay, warped by `wxy warp` to
Antarctic polar stereographic (EPSG:3031).

`wxy warp` takes every slice of the leading dimensions, so the table is cut
first: the rows for those twelve days at the top level, renumbered, with an
arrays.json to match. Cutting a table is a few lines of Parquet; the chunks
it names are untouched, still in the netCDF files on THREDDS.

    WXY=path/to/wxy python3 make_polar.py    # same environment as make_figures.py
"""
import copy, json, os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bran_table import Table
import numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
import pyarrow as pa, pyarrow.parquet as pq
import zarr

T = Table()
WXY = os.environ.get("WXY", "wxy")
DAYS = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]   # 1st of each month
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
cut, out = "cut-amery", "amery.zarr"

# The cut: same chunks, fewer rows, a smaller shape.
r = T.refs[T.refs.dim_0.isin(DAYS) & (T.refs.dim_1 == 0)].copy()
r["dim_0"] = r.dim_0.map({d: i for i, d in enumerate(DAYS)})
r = r.drop(columns="key").sort_values(["dim_0", "dim_1", "dim_2", "dim_3"])
os.makedirs(cut, exist_ok=True)
schema = pa.schema([(f"dim_{i}", pa.int64()) for i in range(4)] + [
    ("present", pa.int8()), ("path", pa.string()), ("offset", pa.int64()), ("size", pa.int64())])
pq.write_table(pa.Table.from_pandas(r, schema=schema, preserve_index=False), f"{cut}/refs_temp.parquet")
meta = copy.deepcopy(T.arrays_json)
for a in meta["arrays"]:
    if a["array"] == "temp":
        a["shape"][:2] = [len(DAYS), 1]
    elif a["array"] == "Time":
        t0, dt = a["affine"]["start"], a["affine"]["step"]
        a.update(storage="inline", affine=None, shape=[len(DAYS)], chunks=[len(DAYS)],
                 values=[t0 + dt * d for d in DAYS])
    elif a["array"] == "st_ocean":
        a.update(shape=[1], chunks=[1], values=a["values"][:1])
json.dump(meta, open(f"{cut}/arrays.json", "w"), indent=1)
print(f"cut: {len(r)} of {len(T.refs)} rows")

# The warp: about 3 km cells over Prydz Bay and the Amery Ice Shelf.
ext = [1.5e6, -0.2e6, 3.3e6, 1.6e6]
t0 = time.time()
subprocess.run([WXY, "warp", cut, out, "--source-array", "/temp", "--crs", "EPSG:3031",
                "--extent", *map(str, ext), "--size", "600", "600", "-r", "bilinear",
                "--overwrite"], check=True)
secs = time.time() - t0
plan = json.loads(subprocess.run(
    [WXY, "warp", cut, out, "--source-array", "/temp", "--crs", "EPSG:3031",
     "--extent", *map(str, ext), "--size", "600", "600", "-r", "bilinear", "--dry-run"],
    check=True, capture_output=True).stdout)
nchunks = plan["fetch"]["chunks"]
print(f"warp: {secs:.1f} s, {nchunks} chunks")

raw = zarr.open_group(out, mode="r")["data"][:]
v = np.where(raw == T.fill, np.nan, raw * T.scale + T.offset)[:, 0]
fig, axs = plt.subplots(3, 4, figsize=(10, 8.2), constrained_layout=True)
for i, ax in enumerate(axs.flat):
    im = ax.imshow(v[i], extent=[ext[0], ext[2], ext[1], ext[3]], origin="upper",
                   cmap="inferno", vmin=-2, vmax=3)
    ax.set_title(f"1 {MONTHS[i]}", fontsize=9); ax.set_xticks([]); ax.set_yticks([])
fig.colorbar(im, ax=axs, shrink=0.6, label="degrees C")
fig.suptitle(f"Prydz Bay and the Amery Ice Shelf, surface, 2010, polar stereographic: "
             f"{nchunks} chunks for twelve days, {secs:.0f} s by wxy warp", fontsize=10)
fig.savefig("polar-amery.png", dpi=110)
