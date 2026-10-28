"""Run a warp twice with a byte cache and show what each run fetched.

Needs the wxy binary (WXY, default `wxy` on PATH), DuckDB for Python, and
a wxylib/fixtures checkout beside this repository (or set WXY_FIXTURES)
for the source COG. A URL works as SOURCE too."""
import json, os, shutil, subprocess, sys
import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
WXY = os.environ.get("WXY", "wxy")
FIX = os.environ.get("WXY_FIXTURES", os.path.join(HERE, "..", "..", "..", "fixtures"))
SOURCE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    FIX, "cog", "world-int16-deflate.tif")
WORK = os.path.join(HERE, "work")
CACHE = os.path.join(WORK, "cache")
GRID = ["--crs", "EPSG:3031", "--extent", "-4000000", "-4000000", "4000000",
        "4000000", "--size", "400", "400", "-r", "bilinear", "--cache", CACHE]

def wxy(*args):
    r = subprocess.run([WXY, "warp", *GRID, *args], check=True,
                       capture_output=True, text=True)
    return r.stdout + r.stderr

def plan():
    return json.loads(wxy("--dry-run", SOURCE, os.path.join(WORK, "plan.zarr")))["fetch"]

shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(WORK)
for run in (1, 2):
    c = plan()["cache"]
    print(f"run {run}, planned: {c['held']} chunks held ({c['held_bytes']} bytes), "
          f"{c['missing']} to fetch ({c['missing_bytes']} bytes)")
    print(f"run {run}, done:    " + wxy(SOURCE, os.path.join(WORK, f"out{run}.zarr")).strip())

same = subprocess.run(["diff", "-r", os.path.join(WORK, "out1.zarr"),
                       os.path.join(WORK, "out2.zarr")]).returncode == 0
print("outputs identical:", same)
print(duckdb.sql(f"""
    select "offset", size, validator, checked_by, fetched
    from read_parquet('{CACHE}/**/*.parquet') order by "offset" """))
