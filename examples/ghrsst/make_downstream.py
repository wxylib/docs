"""Figure downstream.png: a product built on the COGs. trend.sst aggregates
every daily MUR COG (and OISST) to an S2 cell grid as sufficient statistics;
its published regional series are drawn here as they are, from series.json.

    python3 make_downstream.py
"""
import json, urllib.request
import numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt

URL = "https://raw.githubusercontent.com/mdsumner/trend.sst/main/docs/data/series.json"
d = json.load(urllib.request.urlopen(URL))
fig, axs = plt.subplots(2, 1, figsize=(11, 5.8), sharex=True, constrained_layout=True)
for src, c in [("oisst", "#9a9a9a"), ("ghrsst", "#1f5fa8")]:
    s = d["sources"][src]
    t = np.array(s["dates"], dtype="datetime64[D]")
    for ax, reg in zip(axs, ["cr", "so60"]):
        v = np.array(s[reg], float)
        ax.plot(t, v, lw=0.6, color=c, label=f"{src.upper()} ({len(t):,} days)")
for ax, reg in zip(axs, ["cr", "so60"]):
    ax.set_title(d["regions"][reg], fontsize=10, loc="left")
    ax.set_ylabel("degrees C"); ax.grid(alpha=.3)
axs[0].legend(fontsize=9, loc="upper left")
axs[1].set_xlim(np.datetime64("2002-01-01"), np.datetime64("2027-01-01"))
fig.suptitle("Downstream: daily area-weighted mean SST from trend.sst "
             "(S2 level 5 sums over every MUR COG)", fontsize=11)
fig.savefig("downstream.png", dpi=100)
