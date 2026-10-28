"""Figure archive.png: the GHRSST MUR COG archive from its STAC GeoParquet
index alone (one row per day). No COG is read.

    python3 make_archive.py [ghrsst-mur-v2.parquet]

With no argument the index is fetched from source.coop.
"""
import os, sys, urllib.request
import numpy as np, pandas as pd, pyarrow.parquet as pq
import matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
import matplotlib.dates as mdates

HOST = os.environ.get("MUR_HOST", "https://data.source.coop/")
INDEX = HOST + "ausantarctic/ghrsst-mur-v2/ghrsst-mur-v2.parquet"

src = sys.argv[1] if len(sys.argv) > 1 else "ghrsst-mur-v2.parquet"
if not os.path.exists(src):
    urllib.request.urlretrieve(INDEX, src)
t = pq.read_table(src, columns=["datetime", "assets", "ghrsst:status",
                                "processing:datetime"]).to_pandas()
t["date"] = pd.to_datetime(t["datetime"]).dt.tz_localize(None)
t["made"] = pd.to_datetime(t["processing:datetime"]).dt.tz_localize(None)
t["lag"] = (t["made"] - t["date"]).dt.total_seconds() / 86400
t["anom"] = t.assets.map(lambda a: a.get("sst_anomaly") is not None)
st = t["ghrsst:status"]
print(len(t), t.date.min().date(), t.date.max().date())
print(st.value_counts().to_dict())
print("sst_anomaly days:", int(t.anom.sum()), "first", t.date[t.anom].min().date())
first = t.date[t.anom].min()
print("days since first sst_anomaly without it:", int((~t.anom & (t.date >= first)).sum()))

col = {"final": "#1f5fa8", "preliminary": "#e07b00", "nrt_only": "#c0392b"}
fig, (ax, ax2) = plt.subplots(2, 1, figsize=(11, 5.6), sharex=True,
                              gridspec_kw=dict(height_ratios=[4, 1]),
                              constrained_layout=True)
for k, c in col.items():
    d = t[st == k]
    ax.scatter(d.date, d.lag.clip(lower=0.1), s=4 if k == "final" else 14,
               color=c, label=f"{k} ({len(d):,} days)", lw=0)
ax.set_yscale("log"); ax.set_ylabel("days from date to MUR processing")
ax.set_yticks([1, 2, 5, 10, 30, 100, 365, 3650])
ax.set_yticklabels(["1", "2", "5", "10", "30", "100", "1 yr", "10 yr"])
ax.grid(alpha=.3); ax.legend(loc="upper right", fontsize=9, markerscale=2)
ax.set_title("GHRSST MUR v4.1 on source.coop: one COG set per day, "
             f"{t.date.min():%Y-%m-%d} to {t.date.max():%Y-%m-%d} ({len(t):,} days)",
             fontsize=11)
# which variables each day has
vars_ = ["analysed_sst", "analysis_error", "mask", "sea_ice_fraction", "sst_anomaly"]
for i, v in enumerate(vars_):
    have = t.assets.map(lambda a: a.get(v) is not None).to_numpy()
    ax2.scatter(t.date[have], np.full(have.sum(), i), marker="|", s=40,
                color="#1f5fa8", lw=0.4)
ax2.set_yticks(range(len(vars_))); ax2.set_yticklabels(vars_, fontsize=8)
ax2.set_ylim(-0.7, len(vars_) - 0.3); ax2.invert_yaxis()
ax2.xaxis.set_major_locator(mdates.YearLocator(2))
ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
fig.savefig("archive.png", dpi=110)
