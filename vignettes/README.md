# Vignettes

Each vignette starts from a question people have asked in public (on
r-sig-geo, Pangeo, Scientific Python, or a package's issue tracker), shows
what wxylib does about it with a command you can run or a live page you can
open, and says plainly where it stops.

| Vignette | Question it answers | Run it |
|----------|--------------------|--------|
| [A map of a COG in any projection, in the browser](browser/README.md) | A pole-centred or custom-projection view of a raster without a tile server or a full download | Live demo links |
| [A curvilinear grid with a time axis, to a polar map](curvilinear/README.md) | 2D lon/lat netCDF-style data onto a regular grid, all time steps at once ([stars #618](https://github.com/r-spatial/stars/issues/618), [Scientific Python](https://discuss.scientific-python.org/t/reprojecting-a-netcdf-file-from-curvilinear-to-regular-lat-lon-grid-in-python/1815)) | `python run.py` |
| [Values at points: which method did you use?](points/README.md) | Nearest versus interpolated sampling, and what it costs ([raster_sampling](https://github.com/uw-cryo/raster_sampling)) | `python run.py` |
| [Zonal statistics by lazy rasterization](../examples/zonal/README.md) | Zonal stats of a large raster over many polygons without running out of memory ([Pangeo](https://discourse.pangeo.io/t/advice-for-scalable-raster-vector-extraction/4129)) | `python bench.py` |
| [Polygons on grids that are not a regular lattice](../examples/nonaffine/README.md) | Coverage fractions on rotated, rectilinear and curvilinear grids: move the polygon to index space, or the cells to the polygon? | `python plot.py` |

The scripts need the `wxy` binary from [wxylib/core](https://github.com/wxylib/core)
(`cargo build --release -p wxy-cli`, then point `WXY` at
`target/release/wxy`) and numpy, matplotlib, plus xarray and zarr for the
curvilinear one.

The live demos are hosted on the [wxylib/web](https://github.com/wxylib/web)
Pages site. GitHub does not render embedded frames in markdown, so here
they are links. If these docs become a site of their own, the same demos
can sit inline in the page.
