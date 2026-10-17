# Live testing brief

For Michael's machine. This covers installing the `wxy` command line tool
and the R and Python spikes, then running them on real data and comparing
each result with GDAL. Every run says what to expect. Anything that differs
from the expectation is worth reporting back (section 4).

Status as of 2026-10-17: core main has stage S5's kernel scaling and
overview selection, and stage S4b (sources with more dims than y and x,
streamed slice by slice). Warping matches GDAL's warper cell for cell with
nearest, bilinear and cubic, at any ratio of target to source resolution,
on every fixture case.

Overviews: when the target is coarser than the source, gdalwarp reads an
overview if the file has one (`-ovr AUTO`, its default). `wxy warp` now
chooses the same level by the same rule (`--overview auto`, its default),
so the commands below leave both at their defaults. To compare without
overviews, pass `-ovr NONE` to gdalwarp and `--overview none` to wxy; to
force a level, `-ovr 1` and `--overview 1`.

The fixtures were checked against GDAL's library warper one band at a time
(rasterio's `reproject`), which is what `wxy` follows. The gdalwarp command
line can split a target into different chunks (it sizes them by its output
file's blocks and warps all bands together), and chunk edges move kernel
scales and the approximate transformer's scanlines. So where a run below
says "expect 0", a small number of cells differing by 1 is still worth
reporting, but isn't a surprise; many cells, or large differences, are.

## 1. What you need

- Rust stable 1.95 or later (`rustup update stable`).
- GDAL 3.12 or later on the command line (`gdalwarp`), for the reference
  results.
- Python 3.9+ with `numpy`, `zarr` (3.x) and `rasterio`, for
  [compare.py](compare.py). The R package needs no R dependencies.
- Network access for the OISST run (section 3.3), which reads the public
  NOAA bucket over HTTPS.

## 2. Install

```sh
# the command line tool, from core main
cargo install --git https://github.com/wxylib/core wxy-cli
wxy --version          # wxy 0.0.1
wxy warp --help

# a core checkout, for the OISST example and the fixtures
git clone https://github.com/wxylib/core
git clone https://github.com/wxylib/fixtures

# R spike (needs cargo on PATH)
R -e 'remotes::install_github("wxylib/r")'

# Python spike
pip install maturin
pip install git+https://github.com/wxylib/py
```

`wxy warp` reads a local tiled GeoTIFF or COG (deflate, zstd or LZW, with
or without predictor; stripped TIFFs are refused for now, so use
`gdal_translate -co TILED=YES` first) or a local Zarr v3 store
georeferenced by the GeoZarr `spatial:` and `proj:` conventions. It writes
a GeoZarr store. `--crs` takes `EPSG:NNNN` codes only for now. Remote
reads go through the library (`open_store`), not the CLI, so download
files first.

## 3. Runs

Each run pairs a `wxy` command with the `gdalwarp` command for the same
grid, then compares the two:

```sh
python compare.py out.zarr ref.tif
```

`compare.py` prints both grids, the number of cells that differ, the
largest difference, and where the differences are.

A note on longitude wrapping. For a lon/lat source that spans 360 degrees,
`wxy` wraps longitude by default: a cell centred exactly on the
antimeridian, or on a pole, reads the source. gdalwarp leaves those cells
empty for a -180..180 source. Add `--no-wrap` to match gdalwarp exactly.
For a 0..360 source both tools wrap, so leave the flag off.

### 3.1 A COG of your own, 1:1

Pick any COG you use, in any projected CRS, and warp it to lon/lat at
about its own resolution. Replace the bounds and size to suit.

```sh
wxy warp in.tif out.zarr --crs EPSG:4326 \
  --extent 147.0 -43.44 147.036 -43.424 --size 290 180 -r cubic
gdalwarp -t_srs EPSG:4326 -te 147.0 -43.44 147.036 -43.424 -ts 290 180 \
  -r cubic -et 0.125 in.tif ref.tif
python compare.py out.zarr ref.tif
```

Expect 0 differing cells for `near`, `bilinear` and `cubic`. Then try a
target three or four times coarser (divide `--size` and `-ts` by 4): that
exercises the scaled kernels, and should also give 0. Also note how long
`wxy` takes compared with gdalwarp. Nothing has been tuned yet, but the
timing is useful as a baseline. `wxy warp --plain` is the older one-pass
route, for comparison; it differs from GDAL on coarse targets.

### 3.2 Global lon/lat to south polar stereographic

A global lon/lat GeoTIFF of your own (for example a GEBCO or ETOPO
extract), to EPSG:3031.

```sh
wxy warp world.tif out.zarr --crs EPSG:3031 \
  --extent -4e6 -4e6 4e6 4e6 --size 400 400 --no-wrap
gdalwarp -t_srs EPSG:3031 -te -4e6 -4e6 4e6 4e6 -ts 400 400 -r near \
  world.tif ref.tif
python compare.py out.zarr ref.tif
```

- With `-r near` and `--no-wrap`, expect 0 differing cells.
- Without `--no-wrap`, expect only the cells on the antimeridian and pole
  to differ, where gdalwarp has nodata and `wxy` has values.
- With `-r bilinear` or `-r cubic` (on both sides), expect 0 as well,
  whether the target is finer or coarser than the source.

### 3.3 OISST from the byte-reference table (network)

Thirty days of NOAA OISST v2.1 (September 1981), read through an
mdim-refs table as Icechunk virtual references, straight from the NOAA
bucket.

```sh
cd core
cargo run --release -p wxy-virtual --example oisst_refs -- \
  ../fixtures/mdimrefs/oisst-198109 day30-3031.bin
```

- Expect each array to report a SHA-256 match with what GDAL read from the
  source netCDF.
- `day30-3031.bin` is day 30 `sst` warped to EPSG:3031 (400 x 400, 20 km,
  nearest, raw little-endian int16). Compare it with:

```sh
gdalwarp -t_srs EPSG:3031 -te -4e6 -4e6 4e6 4e6 -ts 400 400 -r near -ot Int16 \
  'NETCDF:"/vsicurl/https://noaa-cdr-sea-surface-temp-optimum-interpolation-pds.s3.amazonaws.com/data/v2.1/avhrr/198109/oisst-avhrr-v02r01.19810930.nc":sst' \
  -of ENVI ref.bin
```

```python
import numpy as np
a = np.fromfile("day30-3031.bin", "<i2"); b = np.fromfile("ref.bin", "<i2")
print((a != b).sum(), "of", a.size)
```

Expect 0. This is a 0..360 source, so both tools wrap. If GDAL flips the
south-up rows differently, the count will be near the full size; report
that and we'll look into it.

### 3.3b A whole month, streamed (stage S4b)

`wxy warp` now takes any number of dims before y and x and streams them
through one plan, a batch of source chunks at a time. A month of OISST as
one local Zarr store (time x zlev x lat x lon) is a good real test:

```python
import xarray as xr
url = "https://noaa-cdr-sea-surface-temp-optimum-interpolation-pds.s3.amazonaws.com/data/v2.1/avhrr/198109/oisst-avhrr-v02r01.198109{:02d}.nc"
# packed int16, as gdalwarp reads it
ds = xr.open_mfdataset([url.format(d) + "#mode=bytes" for d in range(1, 31)],
                       mask_and_scale=False)
ds[["sst"]].chunk({"time": 5}).to_zarr("oisst-198109.zarr", zarr_format=3, mode="w")
```

```sh
wxy warp oisst-198109.zarr month-3031.zarr --source-array /sst \
  --crs EPSG:3031 --extent -4e6 -4e6 4e6 4e6 --size 400 400 -r bilinear
```

- Expect a (30, 1, 400, 400) output with dims `time, zlev, y, x`, written
  batch by batch (memory stays near one batch, not the month).
- Any one day should match gdalwarp of that day's file as in 3.3, with
  `-r bilinear` on both sides. The fixture `cf/oisst-like.zarr` imitates
  this layout (packed int16, float32 1D lat ascending, lon 0 to 360) and
  matches GDAL in CI, so a failure here is something the imitation
  misses: report the error and the store's `sst/zarr.json`.

### 3.3c A curvilinear store (stage S5b)

`wxy warp` takes CF 2D coordinates: lon and lat arrays beside the data
(named in its `coordinates` attribute), placed by cell centres as GDAL's
netCDF driver does, or by CF cell bounds with `--bounds`. Any swath or
ocean-model grid written to Zarr by xarray will do, for example a NEMO or
ROMS output subset:

```sh
wxy warp model.zarr model-3031.zarr --source-array /temp \
  --crs EPSG:3031 --extent -4e6 -4e6 4e6 4e6 --size 400 400 -r bilinear
```

- Compare with `gdalwarp -geoloc` on the same variable read from the
  original netCDF (`NETCDF:"file.nc":temp`), `-r bilinear -et 0.125`.
- Leading dims (time, depth) stream as in 3.3b.

### 3.4 Zarr in, Zarr out

Use the output of 3.2 as a source to check Zarr input end to end.

```sh
wxy warp out.zarr back.zarr --crs EPSG:4326 --extent -180 -90 180 -60 --size 720 60
```

Then check:

- Does `back.zarr` open in your usual tools, such as GDAL (`gdalinfo
  'ZARR:"back.zarr":/data'`), zarr-python and xarray?
- Do they see the georeferencing? GDAL may not read the GeoZarr `spatial:`
  attributes yet, so record what each tool reports.

If you have a GeoZarr store of your own with `spatial:` and `proj:`
attributes, warp it too. A store georeferenced only by CF coordinate
arrays will be refused, because CRS-from-CF isn't read yet.

### 3.5 R and Python

Run the README examples in [wxylib/r](https://github.com/wxylib/r) and
[wxylib/py](https://github.com/wxylib/py), then warp a matrix of your own
and compare it with `terra::project()` or `rasterio.warp.reproject()` on
the same grid. Both take in-memory arrays only. File reading comes with
stage S6.

## 4. What to report back

Please post in the project, as a short table if you can:

- your machine and OS, plus `rustc --version`, `gdalinfo --version` and
  `wxy --version`;
- for each run: the command, the differing-cell count from `compare.py`
  (with its row and column ranges when it is not 0), and the time taken by
  `wxy` and by gdalwarp;
- anything that failed to install, crashed, was refused, or gave an error
  message you couldn't act on. Paste the message as is;
- any file of yours that `wxy` should have read but didn't, with what
  `gdalinfo` says about it (compression, tiling, predictor, CRS).
