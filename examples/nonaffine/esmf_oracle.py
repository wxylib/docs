"""ESMF's conservative regridding (esmpy) as a second oracle for the
world-space clip (examples/nonaffine/README.md).

The grid is the source, in Cartesian coordinates, with corners taken from
the cell outlines; each polygon ring is the destination, as a mesh of
triangles (ESMF meshes have no holes, so a hole's fractions are
subtracted, as xESMF's SpatialAverager does). ESMF's source fraction
field (frac_a) is then the fraction of each cell the ring covers. Cells
are the four corners joined by straight lines (line type CART).

    python3 esmf_oracle.py nonaffine.json > esmf.csv
"""

import json
import sys

import esmpy
import numpy as np

esmpy.Manager(debug=False)

def ear_clip(ring):
    """A simple ring (closed) as triangles, anticlockwise."""
    pts = [tuple(p) for p in ring[:-1]]
    a = sum(pts[i][0]*pts[(i+1)%len(pts)][1]-pts[(i+1)%len(pts)][0]*pts[i][1] for i in range(len(pts)))
    if a < 0: pts = pts[::-1]
    idx = list(range(len(pts))); tris = []
    def cross(o,a,b): return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    def inside(p,a,b,c): return cross(a,b,p)>0 and cross(b,c,p)>0 and cross(c,a,p)>0
    while len(idx) > 3:
        for k in range(len(idx)):
            i0,i1,i2 = idx[k-1],idx[k],idx[(k+1)%len(idx)]
            A,B,C = pts[i0],pts[i1],pts[i2]
            if cross(A,B,C) <= 0: continue
            if any(inside(pts[j],A,B,C) for j in idx if j not in (i0,i1,i2)): continue
            tris.append((A,B,C)); idx.pop(k); break
        else: raise RuntimeError("ear clip failed")
    tris.append(tuple(pts[i] for i in idx))
    return tris

def mesh_of(tris):
    m = esmpy.Mesh(parametric_dim=2, spatial_dim=2, coord_sys=esmpy.CoordSys.CART)
    nodes = []; conn = []
    for t in tris:
        for p in t:
            conn.append(len(nodes)); nodes.append(p)
    n = len(nodes)
    m.add_nodes(n, np.arange(1, n+1), np.array(nodes).ravel(), np.zeros(n, dtype=np.int32))
    ne = len(tris)
    m.add_elements(ne, np.arange(1, ne+1), np.full(ne, esmpy.MeshElemType.TRI), np.array(conn, dtype=np.int32))
    return m

def fracs(case, ring):
    h, w = case["shape"]
    out = np.array([q for q in case["outlines"]])  # (h*w, 8, 2)
    out = out.reshape(h, w, 8, 2)
    cx = np.zeros((w+1, h+1)); cy = np.zeros((w+1, h+1))
    # corner (col c, row r) is the top left of cell (r, c), outline point 0;
    # the last column and row take the other corners of their cells
    for r in range(h+1):
        for c in range(w+1):
            if r < h and c < w: p = out[r, c, 0]
            elif r < h: p = out[r, w-1, 6]
            elif c < w: p = out[h-1, c, 2]
            else: p = out[h-1, w-1, 4]
            cx[c, r], cy[c, r] = p
    g = esmpy.Grid(np.array([w, h]), staggerloc=[esmpy.StaggerLoc.CENTER, esmpy.StaggerLoc.CORNER], coord_sys=esmpy.CoordSys.CART)
    gx = g.get_coords(0, staggerloc=esmpy.StaggerLoc.CORNER); gy = g.get_coords(1, staggerloc=esmpy.StaggerLoc.CORNER)
    gx[...] = cx; gy[...] = cy
    ccx = g.get_coords(0, staggerloc=esmpy.StaggerLoc.CENTER); ccy = g.get_coords(1, staggerloc=esmpy.StaggerLoc.CENTER)
    ccx[...] = out[..., 0].mean(axis=2).T; ccy[...] = out[..., 1].mean(axis=2).T
    src = esmpy.Field(g, staggerloc=esmpy.StaggerLoc.CENTER)
    m = mesh_of(ear_clip(ring))
    dst = esmpy.Field(m, meshloc=esmpy.MeshLoc.ELEMENT)
    sf = esmpy.Field(g, staggerloc=esmpy.StaggerLoc.CENTER)
    esmpy.Regrid(src, dst, regrid_method=esmpy.RegridMethod.CONSERVE, line_type=esmpy.LineType.CART,
                 unmapped_action=esmpy.UnmappedAction.IGNORE, src_frac_field=sf)
    return np.array(sf.data).T.copy()  # (h, w)

doc = json.load(open(sys.argv[1]))
print("case,polygon,max_diff_world_vs_esmf,max_diff_dense_vs_esmf")
for case in doc["cases"]:
    h, w = case["shape"]
    for k, poly in enumerate(case["polygons"]):
        f = fracs(case, poly[0]) - sum(fracs(case, r) for r in poly[1:])
        def grid(cov):
            a = np.zeros((h, w))
            for r, c, v in cov: a[r, c] = v
            return a
        print(f"{case['name']},{k},{np.abs(grid(case['cover_world'][k]) - f).max():.2e},{np.abs(grid(case['cover_dense'][k]) - f).max():.2e}")
