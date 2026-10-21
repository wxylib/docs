"""Cut the region and year from each product and keep the cuts in work/.

    python fetch.py [bran] [mur] [glorys] [ostia]

With no argument, all four. Each cut is one .npz per product and shape of
read (map, series, section), with the requests' wall time; make_figures.py
reads only these.
"""
import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import numpy as np

import products as P

# Tasman Sea and the East Australian Current, 2010 (the BRAN store's year)
BBOX = (147.0, 162.0, -40.0, -25.0)
DAY = date(2010, 1, 15)
DAYS = [date(2010, 1, 1) + timedelta(d) for d in range(365)]
SECTION_LAT, SECTION_LON = -34.0, (150.0, 158.0)
SECTION_DEPTH = 1000.0
WORK = os.path.join(P.HERE, "work")


def save(name, **kw):
    os.makedirs(WORK, exist_ok=True)
    np.savez_compressed(os.path.join(WORK, name), **kw)


def timed(f, *a, **k):
    t0 = time.time()
    r = f(*a, **k)
    return r, time.time() - t0


def area_mean(v, lat):
    w = np.cos(np.deg2rad(lat))[:, None] * np.isfinite(v)
    return float(np.nansum(np.nan_to_num(v) * w) / w.sum())


def section_box():
    return (SECTION_LON[0], SECTION_LON[1], SECTION_LAT - 0.06, SECTION_LAT + 0.06)


def series(read, workers=8):
    with ThreadPoolExecutor(workers) as ex:
        return np.array(list(ex.map(read, DAYS)))


def do_bran():
    (v, lon, lat, _), s = timed(P.bran, DAY, BBOX)
    T = P.bran_table()
    save("bran_map", v=v[0], lon=lon, lat=lat, seconds=s, bytes=T.bytes_fetched)
    T.bytes_fetched = 0
    t0 = time.time()
    m = series(lambda d: area_mean(P.bran(d, BBOX)[0][0], lat), workers=4)
    save("bran_series", v=m, seconds=time.time() - t0, bytes=T.bytes_fetched)
    nz = int(np.searchsorted(P.BRAN_DEPTH, SECTION_DEPTH)) + 1
    T.bytes_fetched = 0
    (v, lon, lat, z), s = timed(P.bran, DAY, section_box(), z=(0, nz))
    k = int(np.argmin(abs(lat - SECTION_LAT)))
    save("bran_section", v=v[:, k, :], lon=lon, depth=z, lat=lat[k], seconds=s,
         bytes=T.bytes_fetched)


def do_mur():
    (v, lon, lat), s = timed(P.mur, DAY, BBOX)
    save("mur_map", v=v, lon=lon, lat=lat, seconds=s)
    t0 = time.time()
    m = series(lambda d: area_mean(*P.mur(d, BBOX, res=0.1)[::2]))
    save("mur_series", v=m, seconds=time.time() - t0)


def do_cmems(name, var, depth):
    (r, s) = timed(P.cmems, name, var, DAY, BBOX)
    v, lon, lat = r[:3]
    save(f"{name}_map", v=v[0] if depth else v, lon=lon, lat=lat, seconds=s)
    t0 = time.time()
    first = lambda r: r[0][0] if depth else r[0]
    m = series(lambda d: area_mean(first(P.cmems(name, var, d, BBOX)), lat))
    save(f"{name}_series", v=m, seconds=time.time() - t0)
    if depth:
        z = P.arco(name)["depth"]
        nz = int(np.searchsorted(z, SECTION_DEPTH)) + 1
        out = {}
        for var2 in ("thetao", "so"):
            (v, lon, lat, zz), s = timed(P.cmems, name, var2, DAY, section_box(), z=(0, nz))
            k = int(np.argmin(abs(lat - SECTION_LAT)))
            out[var2] = v[:, k, :]
            out[var2 + "_seconds"] = s
        save(f"{name}_section", lon=lon, depth=zz, lat=lat[k], **out)


JOBS = {
    "bran": do_bran,
    "mur": do_mur,
    "glorys": lambda: do_cmems("glorys", "thetao", True),
    "ostia": lambda: do_cmems("ostia", "analysed_sst", False),
}

if __name__ == "__main__":
    for k in sys.argv[1:] or JOBS:
        t0 = time.time()
        JOBS[k]()
        print(f"{k}: {time.time() - t0:.0f} s", flush=True)
