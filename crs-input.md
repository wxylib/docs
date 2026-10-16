# CRS input: which strings work where

A short guide to the ways a CRS can be written, which of them wxylib takes
today, and how they map to Rust Geodesy's pipeline syntax. The evidence
behind every backend claim is
[rust-proj-capability](https://github.com/mdsumner/rust-proj-capability),
which runs the same fixtures through each crate and judges them against
PROJ 9.9.

## The forms

| Form | Example |
|------|---------|
| Authority code | `EPSG:3031`, `ESRI:102020`, `OGC:CRS84` |
| PROJ string | `+proj=stere +lat_0=-90 +lat_ts=-71 +lon_0=0 +datum=WGS84 +units=m` |
| WKT2 | `PROJCRS["WGS 84 / Antarctic Polar Stereographic", ...]` |
| PROJJSON | `{"type": "ProjectedCRS", ...}` |
| Geodesy pipeline | `inv utm zone=55 south \| laea ...` (an operation, not a CRS) |

The first four describe a CRS. A Geodesy pipeline describes the steps from
one set of coordinates to another, so it replaces a *pair* of CRSs, and
you write the datum step yourself.

## What wxylib accepts today

`wxy warp --crs` and `wxy_warp::GridSpec` take one string, and the backend
is rwarp's pure-Rust proj4rs, so in practice:

| Input | `wxy warp --crs` |
|-------|------------------|
| `EPSG:NNNN` | works, for codes in the bundled `crs-definitions` table |
| PROJ string | warps, but the GeoZarr writer then refuses it ("has no proj: form") |
| WKT2, PROJJSON | refused by proj4rs ("Unrecognized format") |
| `ESRI:`, `OGC:CRS84`, other authorities | refused |

So use an EPSG code for now. (The CLI help says "AUTH:CODE, WKT2 or
PROJJSON"; that is what GeoZarr can record, not what the backend parses.)

On the way in, GeoTIFF sources give `EPSG:NNNN` from their GeoKeys
(user-defined GeoTIFF CRSs are not read yet), and Zarr sources give the
GeoZarr `proj:code`, `proj:wkt2` or `proj:projjson` string, of which only
the code works with proj4rs.

In the browser the plan is PROJ itself through proj-wasm: rwarp-wasm takes
the coordinate transform as a JavaScript callback, so every form PROJ
accepts will work there.

## What each backend accepts

| | EPSG code | PROJ string | WKT2 / PROJJSON | Geodesy pipeline | Datum shifts |
|---|---|---|---|---|---|
| PROJ (`proj` crate, proj-wasm) | yes, and ESRI, IAU, IGNF | yes (add `+type=crs`) | yes | no | full: Helmert, grids, operation choice |
| `proj-core` | yes (embedded registry) | strict | only with an EPSG ID | no | Helmert and NTv2 picked from the registry |
| `proj4rs` (used now) | via `crs-definitions` | yes | WKT1 only, via `proj4wkt` | no | `+towgs84` through WGS84, local NTv2 |
| Rust Geodesy | no | `parse_proj` keeps the projection, drops datum, units and ellipsoid | no | yes | you write `cart \| helmert \| inv cart` |

## Side by side

UTM zone 55 south, WGS84 (EPSG:32755):

```text
EPSG:32755
+proj=utm +zone=55 +south +datum=WGS84 +units=m +no_defs
utm zone=55 south ellps=WGS84
```

Swiss LV95 (EPSG:2056), where the datum step matters (164 m without it):

```text
EPSG:2056
+proj=somerc +lat_0=46.9524055555556 +lon_0=7.43958333333333 +k_0=1
  +x_0=2600000 +y_0=1200000 +ellps=bessel
  +towgs84=674.374,15.056,405.346,0,0,0,0 +units=m +no_defs
```

and from WGS84 longitude and latitude in Geodesy, the same thing as one
pipeline (exact against PROJ):

```text
cart ellps=WGS84
  | inv helmert x=674.374 y=15.056 z=405.346 rx=0 ry=0 rz=0 s=0 convention=position_vector
  | inv cart ellps=bessel
  | somerc lat_0=46.9524055555556 lon_0=7.43958333333333 k_0=1 x_0=2600000 y_0=1200000 ellps=bessel
```

Between two projected CRSs in Geodesy, undo the first and apply the
second: `inv utm zone=55 south ellps=WGS84 | laea lat_0=-42 lon_0=147 ellps=WGS84`.

## Gotchas

- **Axis order.** EPSG:4326 is latitude, longitude by the authority's
  definition. wxylib, rwarp and every pure-Rust crate work in longitude,
  latitude (x, y) order; the `proj` crate normalises to that. `proj-core`
  rejects authority order rather than swapping it.
- **Degrees or radians.** wxylib and rwarp take degrees. Geodesy and
  proj4rs work in radians for angular coordinates; rwarp converts for
  proj4rs, and you convert yourself for Geodesy.
- **`+towgs84` is the datum.** A PROJ string without it treats the datum as
  WGS84, silently. PROJ's own exports add it only when one Helmert
  transformation is the obvious choice, and leave it off for OSGB36
  (EPSG:27700), ED50 and GDA94, which then come out 1.5 m to 172 m off in
  any port.
- **Grid shifts** (NAD27, NZGD49, geoids) need grid files. Nothing in
  wxylib loads them yet, and no pure-Rust crate fetches them from the
  network.
- **Geodesy is not CRS software.** No codes, WKT or PROJJSON; no `stere`
  operator, so no polar stereographic (EPSG:3031, UPS); and wrong results
  for south polar `laea` and inverse `somerc`. An unknown `ellps=` panics,
  and `helmert` needs `convention=` spelled out. Its pipelines are
  for steps you have already designed.
- **PROJ strings in libproj** need `+type=crs` to be read as a CRS rather
  than an operation; rwarp adds it.

## Is there a helper?

Not in wxylib. The nearest thing is the `geodesy+bound` adapter in
rust-proj-capability
([harness/src/adapters/geodesy_ad.rs](https://github.com/mdsumner/rust-proj-capability/blob/main/harness/src/adapters/geodesy_ad.rs)):
it turns a pair of PROJ strings (with `+towgs84`) into a Geodesy pipeline
like the LV95 one above, and takes Geodesy from 9 to 27 exact fixtures out
of 93. Lifting it into a small function (PROJ string pair in, Geodesy
pipeline out) is a suggestion, not built.
