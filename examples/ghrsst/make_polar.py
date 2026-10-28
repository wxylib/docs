"""Figure polar.png: `wxy warp` from the 2024 byte table to Antarctic polar
stereographic (EPSG:3031), two days.

`wxy warp` warps every slice of the leading dimension, so the table is cut
first: the rows of the chosen days, renumbered, with an arrays.json whose
shape and time coordinate match. The cut names the same tiles in the same
COGs; nothing is copied.

    MUR_STORE=.../out WXY=wxy python3 make_polar.py [remap-target]
"""
import copy, json, os, subprocess, sys, time
import numpy as np, pyarrow as pa, pyarrow.parquet as pq
import matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mur_table import Table, STORE
import zarr

T = Table()
WXY = os.environ.get("WXY", "wxy")
remap = sys.argv[1:2]                  # such as s3direct, a mirror of source.coop
DAYS = {60: "1 March 2024", 244: "1 September 2024"}
cut, out = "cut-polar", "polar.zarr"

r = T.refs[T.refs.dim_0.isin(list(DAYS))].copy()
r["dim_0"] = r.dim_0.map({d: i for i, d in enumerate(DAYS)})
r = r.drop(columns="key").sort_values(["dim_0", "dim_1", "dim_2"])
os.makedirs(cut, exist_ok=True)
schema = pa.schema([(f"dim_{i}", pa.int64()) for i in range(3)] + [
    ("present", pa.int8()), ("path", pa.string()), ("offset", pa.int64()), ("size", pa.int64())])
pq.write_table(pa.Table.from_pandas(r, schema=schema, preserve_index=False),
               f"{cut}/refs_analysed_sst.parquet")
meta = json.load(open(f"{STORE}/flat/arrays.json"))
for a in meta["arrays"]:
    if a["array"] == "analysed_sst":
        a["shape"][0] = len(DAYS)
    elif a["array"] == "time":
        t0, dt = a["affine"]["start"], a["affine"]["step"]
        a.update(storage="inline", affine=None, shape=[len(DAYS)], chunks=[len(DAYS)],
                 values=[t0 + dt * d for d in DAYS])
json.dump(meta, open(f"{cut}/arrays.json", "w"), indent=1)
print(f"cut: {len(r)} of {len(T.refs)} rows")

ext = [-4.2e6, -4.2e6, 4.2e6, 4.2e6]
args = [WXY, "warp", cut, out, "--source-array", "/analysed_sst", "--crs", "EPSG:3031",
        "--extent", *map(str, ext), "--size", "1050", "1050", "-r", "bilinear"]
if remap:
    args += ["--remap", remap[0]]
plan = json.loads(subprocess.run(args + ["--dry-run"], check=True,
                                 capture_output=True).stdout)
t0 = time.time()
subprocess.run(args + ["--overwrite"], check=True)
secs = time.time() - t0
nchunks = plan["fetch"]["chunks"]
print(f"warp: {secs:.1f} s, {nchunks} tiles")

raw = zarr.open_group(out, mode="r")["data"][:]
v = np.where(raw == T.fill, np.nan, raw * T.scale + T.offset)
fig, axs = plt.subplots(1, 2, figsize=(11, 5.6), constrained_layout=True)
for ax, (i, lab) in zip(axs, enumerate(DAYS.values())):
    im = ax.imshow(v[i], extent=[ext[0], ext[2], ext[1], ext[3]], origin="upper",
                   cmap="turbo", vmin=-2, vmax=20)
    ax.set_facecolor("#d9d9d9"); ax.set_title(lab, fontsize=10)
    ax.set_xticks([]); ax.set_yticks([])
fig.colorbar(im, ax=axs, shrink=0.8, label="analysed_sst (degrees C)")
fig.suptitle(f"MUR SST, the Southern Ocean in polar stereographic at 8 km, by wxy warp "
             f"from the byte table: {nchunks} tiles for two days, {secs:.0f} s", fontsize=10)
fig.savefig("polar.png", dpi=100)
