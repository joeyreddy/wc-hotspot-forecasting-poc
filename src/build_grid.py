"""Build a 500 m grid over the populated Western Cape and assign people and police stations.

Population: Census 2011 sub-places (scaled to Stats SA 2022 ward totals in the dashboard data),
spread evenly within each sub-place (areal weighting). Land below 50 people/km2 is not gridded:
each station gets one "rural" pseudo-cell for its sparsely populated remainder.

Needs the CrimeStats repository (set CRIMESTATS_ROOT; default ../crimestats) for boundaries
and sub-place population. Its output is committed, so you only rerun this to rebuild the grid.

Output: data/inputs/cells.parquet  (cell id, x, y, lon, lat, station, pop, rural flag)
"""
import json
import re

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from common import CELL, CRIMESTATS, CRS, INPUTS, MIN_DENSITY, PROVINCE

ROOT = CRIMESTATS
DATA = CRIMESTATS / "data"


def main():
    html = (ROOT / "dashboard" / "index.html").read_text()
    i = html.find("MF=")
    MF, _ = json.JSONDecoder().raw_decode(html, i + 3)
    sub = json.loads((ROOT / "dashboard" / "suburbs.json").read_text())["rows"]
    pop = {r[0]: float(r[7] or 0) for r in sub if r[5] == PROVINCE}
    feats = []
    for k, idx in MF.items():
        if k.startswith(PROVINCE + "|"):
            feats += json.loads((ROOT / "dashboard" / "sb" / f"m{idx}.json").read_text())["features"]
    sp = gpd.GeoDataFrame.from_features(feats, crs=4326).to_crs(CRS)
    sp["geometry"] = sp.buffer(0)
    sp = sp[~sp.geometry.is_empty & sp.geometry.notna()]
    sp["pop"] = sp["c"].map(pop).fillna(0)
    sp["dens"] = sp["pop"] / (sp.area / 1e6)
    dense = sp[sp.dens >= MIN_DENSITY]

    # lattice cells covering dense sub-places
    cells = set()
    for g in dense.geometry:
        x0, y0, x1, y1 = g.bounds
        for x in range(int(x0 // CELL), int(x1 // CELL) + 1):
            for y in range(int(y0 // CELL), int(y1 // CELL) + 1):
                cells.add((x, y))
    cl = pd.DataFrame(sorted(cells), columns=["ix", "iy"])
    grid = gpd.GeoDataFrame(cl, geometry=[box(a * CELL, b * CELL, (a + 1) * CELL, (b + 1) * CELL)
                                          for a, b in zip(cl.ix, cl.iy)], crs=CRS)
    pieces = gpd.overlay(grid, dense[["pop", "geometry"]].assign(spa=dense.area), how="intersection", keep_geom_type=True)
    pieces["p"] = pieces["pop"] * pieces.area / pieces["spa"]
    cp = pieces.groupby(["ix", "iy"])["p"].sum()
    grid = grid.set_index(["ix", "iy"])
    grid["pop"] = cp.reindex(grid.index).fillna(0)
    grid = grid[grid["pop"] >= 1].reset_index()

    # station of each cell: precinct containing the cell centre
    P = gpd.read_file(DATA / "interim" / "precincts.geojson").to_crs(CRS)
    geo = pd.read_csv(DATA / "out" / "station_geography.csv")
    wc = set(geo[geo.province == PROVINCE].station)
    P = P[P.station.isin(wc)]
    P["geometry"] = P.buffer(0)
    cen = grid.copy()
    cen["geometry"] = grid.geometry.centroid
    j = gpd.sjoin(cen, P[["station", "geometry"]], predicate="within", how="left").drop_duplicates(["ix", "iy"])
    grid["station"] = j["station"].values
    grid = grid[grid.station.notna()]

    # rural remainder per station
    sp_all_pop = sp.copy()
    sp_all_pop["geometry"] = sp.representative_point()
    sj = gpd.sjoin(sp_all_pop[sp_all_pop.dens < MIN_DENSITY], P[["station", "geometry"]], predicate="within")
    rural_pop = sj.groupby("station")["pop"].sum()
    rows = []
    for _, p in P.iterrows():
        rp = rural_pop.get(p.station, 0.0)
        if rp > 0 or p.station not in set(grid.station):
            pt = p.geometry.representative_point()
            rows.append({"ix": -1, "iy": -1, "pop": max(rp, 1.0), "station": p.station, "geometry": pt.buffer(1)})
    rural = gpd.GeoDataFrame(rows, crs=CRS)
    allc = pd.concat([grid.assign(rural=False), rural.assign(rural=True)], ignore_index=True)
    allc = gpd.GeoDataFrame(allc, geometry="geometry", crs=CRS)
    c = allc.geometry.centroid
    ll = gpd.GeoSeries(c, crs=CRS).to_crs(4326)
    out = pd.DataFrame({"cell": np.arange(len(allc)), "ix": allc.ix, "iy": allc.iy, "x": c.x, "y": c.y,
                        "lon": ll.x.round(5), "lat": ll.y.round(5), "station": allc.station,
                        "pop": allc["pop"].round(1), "rural": allc.rural})
    out.to_parquet(INPUTS / "cells.parquet")
    print(f"{(~out.rural).sum():,} grid cells ({(~out.rural).sum() * CELL * CELL / 1e6:,.0f} km2), "
          f"{out.rural.sum()} rural cells, {out.station.nunique()} stations, population {out['pop'].sum():,.0f}")


if __name__ == "__main__":
    main()
