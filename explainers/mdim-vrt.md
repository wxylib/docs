# Multidimensional VRT views: what GDAL opens on a read

A byte-reference store in wxylib is published in several views, and one of
them is a multidimensional VRT (`mdim.vrt`): an XML file that places many
source files into one array, so that `gdal mdim`, osgeo.gdal and the
gdalxarray backend can read the whole series as a single cube. A VRT of a
long series reads fast only when every source says how much of the array it
covers. Without that, GDAL opens sources to find out, and the cost of a read
grows with the length of the series. This page explains why, the rule a
producer follows, and the check that enforces it.

The GDAL code is `VRTMDArraySourceFromArray` in
`frmts/vrt/vrtmultidim.cpp` (GDAL 3.12). The issue is
[hypertidy/vrtstack#3](https://github.com/hypertidy/vrtstack/issues/3), and
the measurements below come from
[mdsumner/raad.virtualize#14](https://github.com/mdsumner/raad.virtualize/pull/14).

## A source in a multidimensional VRT

Each `<Source>` in an `<Array>` names a file and says where its values go:

```xml
<Source>
  <SourceFilename>/vsicurl/https://.../20240101..._analysed_sst.tif</SourceFilename>
  <SourceBand>1</SourceBand>
  <SourceTranspose>-1,0,1</SourceTranspose>
  <SourceSlab offset="0,0,0" count="1,17999,36000" step="1,1,1"/>
  <DestSlab offset="0,0,0"/>
</Source>
```

- `SourceArray` (a multidimensional source, such as a netCDF variable) or
  `SourceBand` (a classic 2D band, such as one COG per day) names what is
  read.
- `SourceTranspose -1,0,1` gives a 2D band a new leading axis of length 1,
  so a daily COG becomes one time step of a (time, y, x) array.
- `SourceSlab` is the part of the source that is used: `offset`, `count`
  and `step` per axis.
- `DestSlab` is where that part starts in the VRT array.

`SourceSlab` is optional in the VRT format. Left out, the whole source is
used, which is correct, but GDAL does not know the source's size until it
opens it.

## What a read does

For each source, a read first tries to skip it without opening the file.
The source can be skipped when the request ends before the source's
`DestSlab` offset, or when the request starts after offset plus count. The
second test needs the count. Without a `SourceSlab` count only the first
test is possible, so every source whose `DestSlab` offset lies at or before
the end of the request is opened, to learn its shape, even when none of its
values are wanted.

For a time series of daily files, where source *i* starts at time step *i*,
a read of step *t* opens sources 0 to *t*. That gives the pattern seen on
the GHRSST MUR store: a read of 1 January was quick, a read late in the
year took about two minutes, and the cost grew with the time index. Over
/vsicurl/, each open costs a HEAD request and a header GET, about one
second on a remote daily COG. Across the full 8,909-day MUR series, one
chunk read took hours.

`AdviseRead()` does not avoid these opens. With the count written:

| Read | Sources opened, no count | Sources opened, with count |
|---|---|---|
| 3 days from 69 synthetic COGs | 91 | 3 |

The 69-source VRT holds more than one array, so the total without counts
is more than 69.

A second, separate cause of wide reads is in xarray: a sparse selection
over the time axis used to be widened into one read from the first selected
step to the last. gdalxarray reads only the selected steps since
[hypertidy/gdalxarray#39](https://github.com/hypertidy/gdalxarray/pull/39).
With both fixes, three scattered days read three steps from three files.

## The rule for producers

Every `<Source>` in an `mdim.vrt` carries a `SourceSlab` with a `count`.
The producer already knows the grid size when it writes the VRT, so the
count costs nothing:

- a classic 2D band with `SourceTranspose` adding *k* leading axes:
  `count` is 1 on each added axis, then the band's rows and columns;
- a multidimensional source: its own shape, or the part of it placed.

`gdal mdim mosaic` writes counts for the sources it places. Hand-written
and script-written VRTs are where they go missing: the GHRSST 2024 VRTs
from the raad.virtualize COG-stack plan and the VRTs from vrtstack's
`gdal_mdim_stack()` both lacked them.

## The check

`scripts/m17_contract.py` in [wxylib/design](https://github.com/wxylib/design)
(the store description check of design note m17) takes an `mdim.vrt` as
input and reports one item per array, `source_counts`. It reports
`missing` when any source has no count, and then exits with status 1, so a
publish step can stop on it:

```
$ python scripts/m17_contract.py ghrsst-mur-v2-20240101-20241231/out/mdim.vrt

ghrsst-mur-v2-20240101-20241231/out/mdim.vrt  [vrt]  analysed_sst
  source_counts    missing    366 of 366 sources have no SourceSlab count
                              (each is opened on every read), first: ...
```

To see which files GDAL opens, run a read with `CPL_DEBUG=ON` (and
`CPL_CURL_VERBOSE=YES` for remote sources) and count the opens. A read of
one step should open one file.

## How this affects wxylib

wxy's readers do not read `mdim.vrt`. They read the byte references
directly (the flat table, kerchunk or Icechunk view), so this cost does not
apply to them. It applies to every GDAL-side consumer of the VRT view:
`gdal mdim`, osgeo.gdal, gdalxarray and the GDAL xarray backend.
