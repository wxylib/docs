"""Compare a wxy GeoZarr output with a GDAL GeoTIFF on the same grid.

    python compare.py out.zarr ref.tif [--array /data]

Prints the grid check, how many cells differ, the largest difference, and
where the differences sit (row and column ranges), which is what to report
back. Needs numpy, zarr (3.x) and rasterio.
"""

import argparse
import json
import os

import numpy as np
import rasterio
import zarr


def main():
    p = argparse.ArgumentParser()
    p.add_argument("zarr")
    p.add_argument("tif")
    p.add_argument("--array", default="/data")
    a = p.parse_args()

    z = zarr.open_array(a.zarr, path=a.array.strip("/"), mode="r")
    ours = np.asarray(z[:])
    with open(os.path.join(a.zarr, a.array.strip("/"), "zarr.json")) as f:
        attrs = json.load(f)["attributes"]
    with rasterio.open(a.tif) as r:
        ref = r.read()
        gt = r.transform.to_gdal()
        nodata = r.nodata
    if ours.ndim == 2:
        ours = ours[None]
    print("shape  ours", ours.shape, "gdal", ref.shape)
    print("gt     ours", attrs.get("spatial:transform"), "(a, b, c, d, e, f)")
    print("       gdal", [gt[1], gt[2], gt[0], gt[4], gt[5], gt[3]])
    print("crs    ours", attrs.get("proj:code"))
    if ours.shape != ref.shape:
        print("SHAPES DIFFER")
        return
    same = (ours == ref) | (np.isnan(ours.astype(float)) & np.isnan(ref.astype(float)))
    n = int((~same).sum())
    print("differ %d of %d cells" % (n, same.size))
    if n:
        d = np.abs(ours.astype(float) - ref.astype(float))[~same]
        print("max abs difference", np.nanmax(d))
        b, rows, cols = np.nonzero(~same)
        print("rows %d..%d, cols %d..%d" % (rows.min(), rows.max(), cols.min(), cols.max()))
        if nodata is not None:
            print("of which ours nodata", int((ours[~same] == nodata).sum()),
                  "gdal nodata", int((ref[~same] == nodata).sum()))


if __name__ == "__main__":
    main()
