# Four estimates of one sea: Copernicus Marine Zarr beside BRAN and MUR

The Tasman Sea, where the East Australian Current sheds its eddies, is
estimated daily by at least four public products, each served in a
different shape:

| Product | What it is | Served as | Read here by |
|---|---|---|---|
| BRAN2023 `temp` | CSIRO Bluelink ocean reanalysis, 0.1 degree, 51 levels | netCDF4 on NCI THREDDS, addressed by an mdim-refs byte table | [`../bran/bran_table.py`](../bran/bran_table.py): Parquet, range requests, zlib |
| GHRSST MUR v4.1 `analysed_sst` | JPL foundation SST analysis, 0.01 degree | daily COGs on source.coop (ZSTD, horizontal predictor) | osgeo.gdal over `/vsicurl/` |
| GLORYS12 `thetao`, `so` | Copernicus Marine global physics reanalysis, 1/12 degree, 50 levels (`GLOBAL_MULTIYEAR_PHY_001_030`) | ARCO Zarr v2, `timeChunked.zarr` | osgeo.gdal multidim on `ZARR:"/vsicurl/..."`; wxy (window check) |
| OSTIA `analysed_sst` | Met Office SST reanalysis, 0.05 degree (`SST_GLO_SST_L4_REP_OBSERVATIONS_010_011`) | ARCO Zarr v2, `timeChunked.zarr` | as GLORYS12 |

The region is 147-162E, 40-25S, and the year 2010 (the year the BRAN
reference store holds). The same box is a region of the MUR regional
daily series, so the two pages share one MUR curve.

## Copernicus Marine ARCO stores

Copernicus Marine serves each dataset twice as Zarr v2 with consolidated
metadata, in buckets on an S3-compatible endpoint that refuse listing:

- `https://s3.waw3-1.cloudferro.com/mdl-arco-time-NNN/arco/PRODUCT/DATASET_VERSION/timeChunked.zarr`,
  chunked for maps (one time step, a large spatial block);
- `.../mdl-arco-geo-NNN/.../geoChunked.zarr`, chunked for time series
  (many time steps, a small spatial block).

The bucket number varies by dataset. The catalogue of URLs here comes from
the R package [cmemsarco](https://github.com/hypertidy/cmemsarco), which
builds it from the Copernicus Marine STAC catalogue and also gives the
GDAL source string for each store. Nothing needs to list the bucket: GDAL,
zarr-python and wxy all go from the root URL to metadata and then to
chunk keys by the Zarr spec.

The two stores used here, as they are on the endpoint (October 2026):

| Store | Array | Shape | Chunk | Encoding |
|---|---|---|---|---|
| GLORYS12 `cmems_mod_glo_phy_my_0.083deg_P1D-m_202311` | `thetao`, `so` | time 12318 (1993-01-01 to 2026-09-22), elevation 50, latitude 2041, longitude 4320 | 1, 1, 512, 2048 | int16, scale and offset, blosc lz4 with shuffle |
| | `zos` | time, latitude, longitude | 1, 512, 2048 | as above |
| OSTIA `METOFFICE-GLO-SST-L4-REP-OBS-SST_202003` | `analysed_sst` | time 16344 (1981-10-01 to 2026-06-30), latitude 3600, longitude 7200 | 1, 1024, 1024 | as above, kelvin |

Two things about these stores matter to a reader:

- **A missing key is 403, not 404.** A bucket that refuses listing
  answers "access denied" for a key it does not hold. A Zarr v3 reader
  probes `zarr.json` first; on these v2 stores that probe is refused, and
  a reader that takes 403 as an error stops there. GDAL reads the 403 as
  absent (it warns, then goes on to the v2 metadata). wxy did not, and
  failed to open either store until it learned the same rule (wxylib/core
  PR #18). A chunk that was never written is also a 403.
- **GLORYS12's vertical axis is `elevation`, not `depth`.** It is
  negative and deepest first: index 0 is 5728 m, index 49 is the 0.49 m
  surface level. [`products.py`](products.py) turns it into a depth
  axis, surface first, and reads the reversed index range.

### wxy against GDAL on the live stores

wxy reads such a store by URL (`wxy_zarr::open_url`), and `wxy warp`,
`points` and `zonal` take the URL as their source. The window check, as
for the BRAN and MUR stores, records GDAL's SHA-256 of the raw values in
each window, then compares wxy's:

```sh
# GDAL's hashes (wxylib/fixtures); with no window given, two defaults
python scripts/oracle_zarr_windows.py $GLORYS thetao glorys-thetao.json \
  tasman-surface:6223,49,480,3924:1,1,181,181 \
  tasman-78m:6223,29,480,3924:1,1,181,181
# wxy's, compared (wxylib/core)
cargo run --release -p wxy-zarr --example zarr_windows -- $GLORYS \
  --manifest glorys-thetao.json
```

With GDAL 3.13.3, every window is identical:

| Store | Array | Windows (all identical to GDAL) |
|---|---|---|
| GLORYS12 | `thetao`, `so` | first chunk; one row at the last time step; the Tasman box (181 x 181, four chunks) at 0.49 m and at 78 m on 15 January 2010 |
| GLORYS12 | `zos` | first chunk; last-time row; Tasman box |
| OSTIA | `analysed_sst` | first chunk; last-time row; Tasman box (301 x 301, two chunks) |

The default windows of `thetao` and `so` hash the same, because both are
all fill: they sit at the deepest level, under the Antarctic shelf. The
Tasman windows are the ones that carry data. wxy opens each store in
about 5 s (metadata and the coordinate arrays) and reads a four-chunk
window in about 1.4 s.

Before the live stores were reachable, the same check ran on a local
Zarr v2 store written by xarray in the ARCO layout (blosc, NaN fill,
consolidated, served over HTTP). Two gaps showed up there, both closed:
wxy ignored the `_ARRAY_DIMENSIONS` attribute that names the dimensions
of a Zarr v2 array, so it found no longitude or latitude to place the
array by, and it had no way to open a Zarr hierarchy by URL.

## Running it

```sh
python fetch.py            # cuts the box from each product into work/
python make_figures.py     # the figures below, from work/ alone
```

[`products.py`](products.py) holds one reader per product, each returning
values, longitude and latitude (and depth) for a box and a day;
[`fetch.py`](fetch.py) takes the cuts (`python fetch.py bran mur` for
some of them). BRAN needs the store's read settings, as in
[the BRAN example](../bran/README.md).

Each product's reads are made from several threads. A GDAL dataset must
not be shared between threads, so `products.py` opens each ARCO store
once per thread; shared, a threaded series silently took some days'
values from other days.

## 1. One day

![Surface temperature on 15 January 2010 in each product, and each minus MUR](maps.png)

Over the box, each product minus MUR:

| Product | Cells | Mean | Spread (sd) |
|---|---|---|---|
| BRAN2023, 2.5 m | 150 x 150 | -0.02 C | 0.49 C |
| GLORYS12, 0.49 m | 181 x 181 | -0.08 C | 0.62 C |
| OSTIA | 300 x 300 | +0.07 C | 0.43 C |

The differences from the two reanalyses are eddy-shaped: a reanalysis
places the EAC's eddies close to where the observations put them, not
exactly there, and an eddy displaced by a few tens of kilometres leaves a
dipole of plus and minus a degree or two. GLORYS12's eddies are sharper
than BRAN's (finer grid), so its displaced fronts leave stronger dipoles.
OSTIA is itself an analysis of observations and differs from MUR in
smaller, noisier patches. MUR's 0.01 degree grid shows filaments that
none of the others can hold.

Cost: BRAN, 2 chunks (125 kB), 8 to 28 s across runs from THREDDS;
GLORYS12, 4 chunks (about 2.5 MB) in 10 s; OSTIA, 2 chunks (about 1.4 MB)
in 5 s; MUR, the full-resolution 1501 x 1501 window in 1.2 s.

## 2. A year of the box mean

![Daily box mean through 2010 for each product, and each minus MUR](series.png)

All four curves follow one seasonal cycle, from 24.7 C in February to
18.3 C in late August. Each minus MUR, over the 365 days:

| Product | Mean | Day-to-day sd | Range | Dec-Feb mean | Jun-Aug mean |
|---|---|---|---|---|---|
| BRAN2023 | +0.03 C | 0.10 C | -0.25 to +0.34 | +0.06 | +0.03 |
| GLORYS12 | +0.05 C | 0.12 C | -0.29 to +0.31 | +0.02 | +0.03 |
| OSTIA | +0.05 C | 0.11 C | -0.23 to +0.43 | +0.10 | +0.03 |

GLORYS12 minus BRAN is +0.02 C (sd 0.09), and OSTIA minus GLORYS12 is
0.00 C (sd 0.11): the three agree with each other more closely than any
of them agrees with MUR. MUR runs cool by a few hundredths of a degree
all year, and by 0.10 to 0.15 C in October to December, when all three rise
above it together. The earlier guess, that a shallow warm layer
seen by a 2.5 m model level explains the summer gap, does not hold on
its own: OSTIA, a foundation temperature analysis like MUR, shows the
same gap. Part of the offset is in how MUR is read here (see the
cross-check below). Each mean is cos(latitude) weighted over that
product's own ocean cells, so the coasts differ slightly.

Cost: BRAN, 730 chunks (46 MB) in 128 s from THREDDS; GLORYS12, 1460
chunks (about 0.9 GB) in 290 s; OSTIA, 730 chunks (about 0.5 GB) in
104 s; MUR, 365 reads at 0.1 degree, which GDAL serves from each COG's
overviews, in 28 s. A map-chunked store makes a box series pay for whole
512 x 2048 chunks to use a 181 x 181 corner of each; the geoChunked
stores are built for this read.

### MUR cross-check against the GHRSST regional series

The GHRSST COG store work keeps a daily regional series from the same
COGs (`regional_daily.csv`, region `eac_147e_162e`, the same box), read
at overview level 4 by nearest cell centre. Over 2010, this page's MUR
series (0.1 degree, GDAL average) minus that series is -0.044 C, with a
day-to-day sd of 0.008 C, a largest difference of 0.064 C, and a
correlation of 1.0000. The offset is the read resolution, not the data.
On 15 January the box mean at full resolution is 23.808 C; read at 0.02,
0.04, 0.08 and 0.16 degree it is 23.811, 23.815, 23.826 and 23.853 C; at
0.1 degree, as here, 23.827 C; and the regional series has 23.867 C.
Coarser reads let warmer offshore cells stand for the cool coastal
strip, so the mean drifts up as the cells get bigger. Against the
full-resolution mean, this page's MUR series is about 0.02 C warm, and
MUR's gap to the other three is smaller than the table shows by that
much.

## 3. A section across the current

![Temperature (and GLORYS12 salinity) along 34S, 150-158E, top 1000 m, 15 January 2010](section.png)

At 34S, in BRAN, a warm core sits off the shelf near 152.5E, its
isotherms pushed down to 400 m and more, and they rise again to the east
near 154E: the EAC and its eddies in one slice. GLORYS12 has the same
dome of cold water, near 154.3E, a little east of BRAN's. Its salinity
panel shows the dome as a column of fresher water drawn up from below
500 m, as in a cold-core (cyclonic) eddy. The BRAN reference store holds temperature only.

Cost: BRAN, 40 levels of 2 chunks each (3.6 MB) for 80 columns of one
row, in 4 s. GLORYS12, 36 levels of one chunk each per variable (about
1 MB each) for 97 columns of one row: `thetao` in 71 s and `so` in
41 s. The same pattern as the series: the ARCO time chunks are built for
whole maps, and a section uses a sliver of each.

## Still to run

- The same reads through xarray: `xarray.open_zarr` on the ARCO URL, and
  GDAL's xarray backend on the same `ZARR:` source string.
- The geoChunked stores for the box series and the section, where their
  chunking is the point, against the timings above.
- GLORYS12 `zos` (sea surface height) maps beside the EAC eddies.
