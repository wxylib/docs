"""Figure img/cog-tiles.png: one GHRSST MUR COG tile decoded by hand, from
its byte range to values, through the two codec steps that every view of
the store has to name. Uses examples/ghrsst/mur_table.py (MUR_STORE,
MUR_HOST as there)."""
import os, sys
import numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "examples", "ghrsst"))
from mur_table import Table

T = Table()
t, cy, cx = 0, 24, 64          # 1 January 2024, off Sydney (34-39S, 152-157E)
row = T.by_key.loc[(t * T.nchunks[1] + cy) * T.nchunks[2] + cx]
values = T.chunk(t, cy, cx)
diffs = np.diff(values, axis=-1, prepend=np.int16(0))   # what the tile stores
fig, axs = plt.subplots(1, 3, figsize=(12, 4.4), constrained_layout=True)
c0 = 400                       # an ocean stretch of row 256
xs = np.arange(c0, c0 + 64)
axs[0].bar(xs, diffs[256, c0:c0 + 64], color="#e07b00")
axs[0].set_ylabel("stored difference (raw units)", color="#e07b00")
ax2 = axs[0].twinx()
ax2.plot(xs, values[256, c0:c0 + 64], color="#1f5fa8", lw=1.8)
ax2.set_ylabel("value (raw int16)", color="#1f5fa8")
axs[0].set_title(f"row 256, cells {c0} to {c0 + 63}", fontsize=10)
axs[0].grid(alpha=.3)
lim = np.percentile(np.abs(diffs[:, 1:]), 99)
axs[1].imshow(diffs, cmap="RdBu_r", vmin=-lim, vmax=lim)
axs[1].set_title("after ZSTD: differences along each row", fontsize=10)
v = T.degc(values)
im = axs[2].imshow(v, cmap="turbo")
axs[2].set_title("after the running sum: degrees C", fontsize=10)
fig.colorbar(im, ax=axs[2], shrink=.8)
for a in axs[1:]:
    a.set_xticks([]); a.set_yticks([])
fig.suptitle(f"One 512 x 512 tile: {row['size']:,} bytes at offset {row['offset']:,} "
             f"of a {os.path.basename(row['path'])[:8]} COG", fontsize=11)
fig.savefig(os.path.join(HERE, "img", "cog-tiles.png"), dpi=100)
