"""Points vignette: elevation along a line from Hobart's waterfront to the
summit of kunanyi / Mount Wellington, read from the Copernicus 30 m DEM by
`wxy points` with nearest, bilinear and cubic, and the plan it fetches by.

Downloads one DEM tile (42 MB) from the public copernicus-dem-30m bucket,
runs the wxy CLI, and draws points.png. Needs numpy, matplotlib and the
wxy binary (build it in wxylib/core with `cargo build --release -p
wxy-cli`; pass its path as WXY or put it on PATH). Run from this folder:
python run.py
"""

import csv
import io
import json
import os
import subprocess
import urllib.request

import matplotlib.pyplot as plt
import numpy as np

WXY = os.environ.get("WXY", "wxy")
HERE = os.path.dirname(os.path.abspath(__file__))
TILE = "Copernicus_DSM_COG_10_S43_00_E147_00_DEM"
URL = f"https://copernicus-dem-30m.s3.amazonaws.com/{TILE}/{TILE}.tif"
DEM = os.path.join(HERE, "dem.tif")
if not os.path.exists(DEM):
    urllib.request.urlretrieve(URL, DEM)

# 400 points, about 20 m apart, waterfront to summit.
a, b = (147.335, -42.885), (147.2365, -42.8960)
t = np.linspace(0, 1, 400)
x = a[0] + (b[0] - a[0]) * t
y = a[1] + (b[1] - a[1]) * t
lines = "".join(f"{xi:.6f},{yi:.6f}\n" for xi, yi in zip(x, y))
km = 111.32 * np.hypot((b[0] - a[0]) * np.cos(np.radians(a[1])), b[1] - a[1])
dist = t * km  # along the line, near enough at this scale

def run(*extra):
    out = subprocess.run([WXY, "points", DEM, *extra], input=lines,
                         check=True, capture_output=True, text=True).stdout
    return out

values = {}
for r in ["near", "bilinear", "cubic"]:
    rows = list(csv.DictReader(io.StringIO(run("-r", r))))
    values[r] = np.array([float(row["value"]) if row["value"] else np.nan for row in rows])

plan = json.loads(run("--dry-run"))
with open(os.path.join(HERE, "plan.json"), "w") as f:
    json.dump(plan, f, indent=2)
print("chunks fetched:", plan["fetch"]["fetches"], "of", plan["fetch"]["of"],
      "stored bytes:", plan["fetch"]["stored_bytes"])

for r in ["bilinear", "cubic"]:
    d = values[r] - values["near"]
    print(f"{r} - near: max |diff| {np.nanmax(np.abs(d)):.1f} m, mean |diff| {np.nanmean(np.abs(d)):.2f} m")

fig, ax = plt.subplots(2, 1, figsize=(8, 6), sharex=True, constrained_layout=True,
                       gridspec_kw={"height_ratios": [2, 1]})
ax[0].plot(dist, values["near"], drawstyle="steps-mid", lw=1, label="near (gdallocationinfo)")
ax[0].plot(dist, values["bilinear"], lw=1, label="bilinear")
ax[0].plot(dist, values["cubic"], lw=1, ls="--", label="cubic")
ax[0].set_ylabel("elevation (m)")
ax[0].legend(frameon=False)
ax[0].set_title("Hobart waterfront to kunanyi summit, Copernicus DEM 30 m")
ax[1].axhline(0, color="0.7", lw=0.8)
ax[1].plot(dist, values["bilinear"] - values["near"], lw=1, color="C1", label="bilinear - near")
ax[1].plot(dist, values["cubic"] - values["near"], lw=1, ls="--", color="C2", label="cubic - near")
ax[1].set_ylabel("difference (m)")
ax[1].set_xlabel("distance along the line (km)")
ax[1].legend(frameon=False)
fig.savefig(os.path.join(HERE, "points.png"), dpi=110)
