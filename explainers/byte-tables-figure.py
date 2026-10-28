"""Figure img/byte-tables.png: the BRAN2023 temp fixture table (32 days,
97,920 chunk rows over two monthly netCDF4 files) seen three ways: the
chunk grid of one slice as byte ranges, where those ranges sit in their
file, and which file supplies each day. Reads
fixtures/mdimrefs/bran2023-temp-201001/refs_temp.parquet from a wxylib/fixtures
checkout beside this repository (or set WXY_FIXTURES)."""
import os
import numpy as np, matplotlib
import pyarrow.parquet as pq
matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.environ.get("WXY_FIXTURES", os.path.join(HERE, "..", "..", "fixtures"))
t = pq.read_table(os.path.join(FIX, "mdimrefs", "bran2023-temp-201001",
                               "refs_temp.parquet")).to_pandas()
t["file"] = t["path"].str.extract(r"ocean_temp_(\d{4}_\d{2})\.nc")[0]

fig, axs = plt.subplots(1, 3, figsize=(13, 4.2), constrained_layout=True,
                        gridspec_kw={"width_ratios": [1.5, 1.2, 1]})

# (a) one day, one depth: 5 x 12 chunks of 300 x 300 cells
s = t[(t.dim_0 == 0) & (t.dim_1 == 0)]
grid = np.full((s.dim_2.max() + 1, s.dim_3.max() + 1), np.nan)
grid[s.dim_2, s.dim_3] = s["size"] / 1024
im = axs[0].imshow(grid, origin="lower", cmap="viridis")
for (r, c), v in np.ndenumerate(grid):
    axs[0].text(c, r, f"{v:.0f}", ha="center", va="center", fontsize=7, color="w")
axs[0].set_title("1 Jan 2010, surface: one row per chunk\n(compressed size, KB)",
                 fontsize=10)
axs[0].set_xlabel("chunk column (dim_3)"); axs[0].set_ylabel("chunk row (dim_2)")
fig.colorbar(im, ax=axs[0], shrink=.7)

# (b) where the January rows sit in their file
j = t[t.file == "2010_01"]
sc = axs[1].scatter(j["offset"] / 1e6, j.dim_0 + 1, c=j.dim_1, s=1,
                    cmap="plasma", rasterized=True)
axs[1].set_xlabel("offset in ocean_temp_2010_01.nc (MB)")
axs[1].set_ylabel("day of January")
axs[1].set_title("The same rows' offsets: days in order,\ndepths within a day",
                 fontsize=10)
fig.colorbar(sc, ax=axs[1], shrink=.7, label="depth level (dim_1)")

# (c) the plan: which file each day of the array comes from
days = t.groupby("dim_0")["file"].first()
cols = {"2010_01": "#1f5fa8", "2010_02": "#e07b00"}
axs[2].bar(days.index, 1, color=[cols[f] for f in days], width=1)
from matplotlib.patches import Patch
handles = [Patch(color=c, label=f"ocean_temp_{f}.nc") for f, c in cols.items()]
axs[2].set_yticks([]); axs[2].set_xlabel("time index in the array (dim_0)")
axs[2].set_title("The placements: 31 days from one file,\nday 32 from the next",
                 fontsize=10)
axs[2].legend(handles=handles, loc="upper center", bbox_to_anchor=(.5, -.25), fontsize=8)
fig.suptitle(f"One byte table: {len(t):,} rows, {t.path.nunique()} files, "
             f"{t['size'].sum() / 1e9:.1f} GB referenced, none copied", fontsize=11)
fig.savefig(os.path.join(HERE, "img", "byte-tables.png"), dpi=100)
