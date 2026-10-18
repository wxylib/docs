# A map of a COG in any projection, in the browser

**The question people keep asking:** how do I get a pole-centred (or
otherwise non-Web-Mercator) view of a raster without a tile server, a
pre-rendered copy, or loading the whole file? See
[Pole centric map with Raster?](https://r-mailing-lists.thecoatlessprofessor.com/lists/r-sig-geo/msg/msg-82d7bcfcfed9)
on r-sig-geo, and the many "reproject on the fly" threads around
[OpenLayers reprojection](https://openlayers.org/en/latest/examples/reprojection.html)
and [deck.gl-raster](https://developmentseed.org/deck.gl-raster/docs/intro/).

**What wxylib does:** the browser demo in
[wxylib/web](https://github.com/wxylib/web) compiles `wxy-tiff` and
`wxy-warp` to WebAssembly. The canvas is the target grid. Each view is a
fresh warp with the same code `wxy warp` runs on the command line (GDAL's
chunked warp, its kernels, and `gdalwarp -ovr AUTO` overview choice), and
only the tiles that view touches are fetched by HTTP range request.

## Try it

Each link opens the live demo with a source and a target CRS already set.
Drag to pan, scroll to zoom; the status line reports cells, time, the
overview read and the bytes fetched.

| View | Live |
|------|------|
| Sentinel-2 true colour over Hobart (UTM 55S), on south polar stereographic | [open](https://wxylib.github.io/web/cog.html?url=https%3A%2F%2Fsentinel-cogs.s3.us-west-2.amazonaws.com%2Fsentinel-s2-l2a-cogs%2F55%2FG%2FEN%2F2024%2F2%2FS2B_55GEN_20240203_0_L2A%2FTCI.tif&crs=EPSG%3A3031) |
| The same scene on a Lambert azimuthal centred on Hobart | [open](https://wxylib.github.io/web/cog.html?url=https%3A%2F%2Fsentinel-cogs.s3.us-west-2.amazonaws.com%2Fsentinel-s2-l2a-cogs%2F55%2FG%2FEN%2F2024%2F2%2FS2B_55GEN_20240203_0_L2A%2FTCI.tif&crs=%2Bproj%3Dlaea%20%2Blat_0%3D-42.9%20%2Blon_0%3D147.3%20%2Bdatum%3DWGS84) |
| A synthetic world grid seen from a geostationary satellite over 140E | [open](https://wxylib.github.io/web/cog.html?crs=%2Bproj%3Dgeos%20%2Bh%3D35785831%20%2Blon_0%3D140%20%2Bdatum%3DWGS84) |
| Your own COG: put its URL after `?url=` (the server must allow CORS and Range) | [open](https://wxylib.github.io/web/cog.html) |

![A Sentinel-2 scene over Hobart, in UTM zone 55S, warped in the browser to
south polar stereographic](https://github.com/wxylib/web/raw/main/docs/img/hobart-3031.png)

That first view took 144 ms and five range requests (the header, the image
directories and the coarsest overview's tiles, 0.74 MB). Zoomed in, the
warp moves to full resolution and fetches only the tiles in view.

## Sentinel-2 on a web map, no tile server

[s2.html](https://wxylib.github.io/web/s2.html) searches Earth Search's STAC
for the map view, lists scenes, and draws the one you pick from its raw
uint16 band COGs: three bands warped from UTM onto the map's own Web
Mercator pixel grid each time the map stops moving, then stretched to
colour in the page. A date range can go in the link, for example
[summer 2024](https://wxylib.github.io/web/s2.html?from=2024-01-01&to=2024-02-29).

![Hobart at 10 m, three bands warped from UTM 55S to the map
grid](https://github.com/wxylib/web/raw/main/docs/img/s2-hobart.jpg)

## Limits

- CRS strings go through proj4rs (EPSG codes and PROJ strings, no datum
  grids). Some projections are missing there: polar Lambert azimuthal and
  azimuthal equidistant among them (see [CRS input](../../crs-input.md)).
- GeoTIFF only in the browser for now; Zarr follows.
- A COG on a server without CORS will not open from the page. Most public
  buckets (sentinel-cogs, raw.githubusercontent.com) allow it.
