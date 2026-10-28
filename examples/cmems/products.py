"""Readers for four estimates of the ocean's temperature, cut to one region.

- BRAN2023 `temp` (CSIRO Bluelink reanalysis, 0.1 degree, 51 levels): its
  mdim-refs byte table, read by ../bran/bran_table.py (no netCDF library).
- GHRSST MUR v4.1 `analysed_sst` (0.01 degree, foundation SST): daily COGs
  on source.coop, read by osgeo.gdal over /vsicurl/.
- Copernicus Marine ARCO Zarr (Zarr v2, `timeChunked.zarr`, buckets that
  refuse listing): GLORYS12 `thetao`, `so`, `zos` (global physics
  reanalysis, 1/12 degree, 50 levels) and OSTIA `analysed_sst` (0.05
  degree), read by osgeo.gdal multidim on ZARR:"/vsicurl/...".

Every reader returns (values, lon, lat[, depth]) as float32 in degrees C
(or the variable's own unit), NaN where there is no ocean, with latitude
increasing.
"""
import os, re, sys, threading
from datetime import datetime, timedelta

import numpy as np
from osgeo import gdal

gdal.UseExceptions()
gdal.SetConfigOption("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
gdal.SetConfigOption("GDAL_HTTP_MAX_RETRY", "4")
gdal.SetConfigOption("GDAL_HTTP_RETRY_DELAY", "2")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bran"))

# Copernicus Marine ARCO stores, from the catalogue in hypertidy/cmemsarco
ARCO = "https://s3.waw3-1.cloudferro.com"
CMEMS = {
    "glorys": f"{ARCO}/mdl-arco-time-025/arco/GLOBAL_MULTIYEAR_PHY_001_030/"
              "cmems_mod_glo_phy_my_0.083deg_P1D-m_202311/timeChunked.zarr",
    "ostia": f"{ARCO}/mdl-arco-time-046/arco/SST_GLO_SST_L4_REP_OBSERVATIONS_010_011/"
             "METOFFICE-GLO-SST-L4-REP-OBS-SST_202003/timeChunked.zarr",
}
MUR = ("https://s3.us-west-2.amazonaws.com/us-west-2.opendata.source.coop/"
       "ausantarctic/ghrsst-mur-v2/{d:%Y/%m/%d}/{d:%Y%m%d}090000-JPL-L4_GHRSST-"
       "SSTfnd-MUR-GLOB-v02.0-fv04.1_analysed_sst.tif")

# BRAN2023 st_ocean (m), from the store's arrays.json
BRAN_DEPTH = np.array([2.5,7.5,12.5,17.5,22.7,28.2,34.2,41.0,48.5,56.7,65.7,75.2,85.0,95,105,115,125,135,145,155,165,175,185,195,205.2,217.1,233.2,255.9,286.6,325.9,373.2,427.1,485.2,545.5,610.4,685.9,775.9,880.4,995.5,1115.3,1238.4,1368.2,1507.7,1658.2,1818.4,1985.3,2165.2,2431.1,2894.8,3603.1,4509.2])
BRAN_LON = 0.05 + 0.1 * np.arange(3600)
BRAN_LAT = -74.95 + 0.1 * np.arange(1500)
BRAN_YEAR = 2010


def _span(coord, lo, hi):
    """Index range [i0, i1) of an increasing coordinate within [lo, hi]."""
    i = np.nonzero((coord >= lo) & (coord <= hi))[0]
    return int(i[0]), int(i[-1]) + 1


# ---- BRAN2023: the byte table ---------------------------------------------

_bran = None


def bran_table():
    global _bran
    if _bran is None:
        from bran_table import Table
        _bran = Table()
    return _bran


def bran(day, bbox, z=(0, 1)):
    """temp on `day` (a date in 2010) over bbox (lon0, lon1, lat0, lat1),
    depth levels z[0]..z[1]-1: (t, z, y, x) collapsed to (z, y, x)."""
    T = bran_table()
    t = (day - datetime(BRAN_YEAR, 1, 1).date()).days
    x0, x1 = _span(BRAN_LON, bbox[0], bbox[1])
    y0, y1 = _span(BRAN_LAT, bbox[2], bbox[3])
    raw = T.window([t, z[0], y0, x0], [1, z[1] - z[0], y1 - y0, x1 - x0])
    return T.degc(raw)[0], BRAN_LON[x0:x1], BRAN_LAT[y0:y1], BRAN_DEPTH[z[0]:z[1]]


# ---- MUR: daily COGs -----------------------------------------------------

def mur(day, bbox, res=None):
    """analysed_sst on `day` over bbox, in degrees C. With `res` (degrees),
    read at that resolution (GDAL picks the COG overview), else 0.01."""
    ds = gdal.Open("/vsicurl/" + MUR.format(d=day))
    gt = ds.GetGeoTransform()
    b = ds.GetRasterBand(1)
    c0 = int(np.floor((bbox[0] - gt[0]) / gt[1]))
    c1 = int(np.ceil((bbox[1] - gt[0]) / gt[1]))
    r0 = int(np.floor((bbox[3] - gt[3]) / gt[5]))
    r1 = int(np.ceil((bbox[2] - gt[3]) / gt[5]))
    nx, ny = c1 - c0, r1 - r0
    bx, by = (nx, ny) if res is None else (round(nx * gt[1] / res), round(ny * -gt[5] / res))
    v = b.ReadAsArray(c0, r0, nx, ny, buf_xsize=bx, buf_ysize=by,
                      resample_alg=gdal.GRIORA_Average).astype("f4")
    nd = b.GetNoDataValue()
    if nd is not None:
        v[v == nd] = np.nan
    v = v * (b.GetScale() or 1) + (b.GetOffset() or 0)
    if b.GetUnitType().lower().startswith("k") or np.nanmean(v) > 200:
        v = v - 273.15
    sx, sy = nx * gt[1] / bx, ny * -gt[5] / by
    lon = gt[0] + c0 * gt[1] + sx * (np.arange(bx) + 0.5)
    lat = gt[3] + r0 * gt[5] - sy * (np.arange(by) + 0.5)
    return v[::-1], lon, lat[::-1]


# ---- Copernicus Marine ARCO Zarr -----------------------------------------

_arco = {}


def _times(arr):
    units = arr.GetUnit() or ""
    for a in arr.GetAttributes():
        if a.GetName() == "units":
            units = a.Read()
    m = re.match(r"(\w+) since (.+)", units)
    step = {"seconds": 1, "minutes": 60, "hours": 3600, "days": 86400}[m.group(1)]
    origin = datetime.fromisoformat(m.group(2).strip().replace("Z", "").split(".")[0])
    v = np.asarray(arr.ReadAsArray(), "f8")
    return [origin + timedelta(seconds=float(s) * step) for s in v]


def arco(name):
    """The root group of a Copernicus ARCO store and its coordinates, one
    per thread: a GDAL dataset is not safe to read from two threads at once
    (shared, a threaded series gets other days' values on some days)."""
    key = (name, threading.get_ident())
    if key not in _arco:
        url = CMEMS.get(name, name)
        ds = gdal.OpenEx(f'ZARR:"/vsicurl/{url}"', gdal.OF_MULTIDIM_RASTER)
        g = ds.GetRootGroup()
        co = {"ds": ds, "root": g, "url": url}
        names = g.GetMDArrayNames()
        for k in ("longitude", "latitude", "depth"):
            if k in names:
                co[k] = np.asarray(g.OpenMDArray(k).ReadAsArray(), "f8")
        # GLORYS12 (202311) has no depth: its vertical axis is "elevation",
        # negative and deepest first. Keep depth surface first, and the
        # store's own axis name for the reads.
        co["zdim"] = "depth"
        if "depth" not in co and "elevation" in names:
            co["depth"] = -np.asarray(g.OpenMDArray("elevation").ReadAsArray(), "f8")[::-1]
            co["zdim"] = "elevation"
        co["time"] = _times(g.OpenMDArray("time"))
        _arco[key] = co
    return _arco[key]


def cmems(name, var, day, bbox, z=None):
    """`var` on `day` over bbox from ARCO store `name` ("glorys", "ostia" or a
    URL), depth levels z[0]..z[1]-1 when the variable has depth."""
    co = arco(name)
    a = co["root"].OpenMDArray(var)
    dims = [d.GetName() for d in a.GetDimensions()]
    t = min(range(len(co["time"])), key=lambda i: abs(co["time"][i].date() - day))
    x0, x1 = _span(co["longitude"], bbox[0], bbox[1])
    y0, y1 = _span(co["latitude"], bbox[2], bbox[3])
    start, count = [t], [1]
    zdim = co["zdim"] in dims
    if zdim:
        z = z or (0, 1)
        nz = len(co["depth"])
        z0 = z[0] if co["zdim"] == "depth" else nz - z[1]
        start.append(z0); count.append(z[1] - z[0])
    start += [y0, x0]; count += [y1 - y0, x1 - x0]
    v = np.frombuffer(a.Read(array_start_idx=start, count=count,
                             buffer_datatype=gdal.ExtendedDataType.Create(gdal.GDT_Float64)),
                      "f8").reshape(count).astype("f4")
    nd = a.GetNoDataValueAsDouble()
    if nd is not None and not np.isnan(nd):
        v[v == nd] = np.nan
    v = v * (a.GetScale() or 1) + (a.GetOffset() or 0)
    if var == "analysed_sst" and np.nanmean(v) > 200:
        v = v - 273.15
    v = v[0]
    if zdim and co["zdim"] == "elevation":
        v = v[::-1]
    lon, lat = co["longitude"][x0:x1], co["latitude"][y0:y1]
    if zdim:
        return v, lon, lat, co["depth"][z[0]:z[1]]
    return v, lon, lat
