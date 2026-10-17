# A curvilinear grid with a time axis, to a polar map

**The question:** "I have a NetCDF file on a curvilinear grid (2D latitude
and longitude), with several time steps. How do I get it onto a regular
map grid, all time steps at once?" Asked on
[Scientific Python](https://discuss.scientific-python.org/t/reprojecting-a-netcdf-file-from-curvilinear-to-regular-lat-lon-grid-in-python/1815)
(unanswered), as [rioxarray #47](https://github.com/corteva/rioxarray/issues/47),
and in R as [stars #513](https://github.com/r-spatial/stars/issues/513) and
[stars #618](https://github.com/r-spatial/stars/issues/618), where the warp
leaves gaps and objects with several time slices fail, so people warp one
slice at a time.

**What wxylib does:** `wxy-zarr` finds the 2D `lon` and `lat` arrays the
way CF says to (the `coordinates` attribute, then `standard_name`, `units`
or the usual names). `wxy-warp` places the cells with a port of GDAL's
geolocation-array transformer (see the [explainer](../../explainers/geoloc.md)),
and streams every slice of the leading dimensions under one plan: the
backmap is built once, and each source chunk is fetched once.

## The run

[run.py](run.py) writes a small xarray-style Zarr store: `data(time, y, x)`
with 2D `lon(y, x)` and `lat(y, x)`, a ring of 50 x 180 cells round
Antarctica whose longitudes cross the antimeridian, and a pattern that
rotates 40 degrees a day for three days. Then:

```sh
wxy warp curvilinear.zarr warped.zarr --source-array /data \
  --crs EPSG:3031 --extent -3000000 -3000000 3000000 3000000 \
  --size 400 400 -r bilinear
```

All three days are warped in one command, and the output store keeps the
`time` axis:

![Top: the three days in source cell order. Bottom: the same days warped
to south polar stereographic](curvilinear.png)

Add `--dry-run` and the same command prints the plan instead of reading
anything. Here it is one chunk of 108 KB (the whole small store) and the
target grid it lands on. For a large store, that JSON shows which chunks
a warp will fetch and how many bytes, before it runs.

## What to notice

- **The hole at the pole** is real: the grid stops at 85S.
- **The ragged wedge below the pole** is where the ring closes, between
  the last column (near 180E) and the first (near 180W). The geolocation
  transformer treats the grid as a sheet with two edges, so target cells
  in that seam find no source cell to interpolate from. GDAL's warper does
  the same thing, and wxylib matches it value for value in the
  [fixtures](https://github.com/wxylib/fixtures/tree/main/curvilinear).
  A wrap-aware option (joining the first and last columns) would close it.
  That is a candidate feature that would go beyond GDAL parity.

## Limits

- The input has to be Zarr. A netCDF file can be read through a
  byte-reference table today (see the [OISST walk-through](../../oisst-virtual.md)),
  but not opened directly. That is the most common blocker between the
  forum questions above and this command.
- 1D CF bounds are not read yet; 2D bounds are (`--bounds`).
- The R and Python packages do not run this yet: they warp in-memory
  arrays only.
- Values at points on the same store need no warp at all:
  `echo 150,-70 | wxy points curvilinear.zarr` gives one value per day.
