"""Extract browser-ready GeoJSON boundaries from the fieldmaps GeoParquet.

One-time, idempotent, reproducible. Reads the ~43k-polygon admin2 GeoParquet
(`staging/fieldmaps_admin_boundaries.geoparquet`, see
docs/notes/acquisition_fieldmaps.md), dissolves to admin0 (one polygon per
ISO3) and admin1 (per priority country), simplifies for browser delivery, and
writes:

  frontend/public/maps/admin0.geojson          one feature per ISO3   (<2 MB target)
  frontend/public/maps/admin1/{iso3}.geojson   per priority country   (<500 KB each)
  frontend/public/maps/admin1_centroids.json   pcode/name/lat/lon per admin1

The centroids file is consumed by the FastAPI mock (`server/mock_data.py`) to
place ACLED hotspots at real interior points and to key subnational fixtures to
real admin1 P-codes, so the choropleth join works against actual geography.

Method: stream the parquet in batches (the file holds 4,307 tiny row groups and
~2 GB of WKB, so a single read risks OOM), pre-simplify each batch immediately
to bound peak memory, accumulate, then dissolve. Topology-preserving Douglas-
Peucker simplification (shapely, tolerance in degrees). Output coordinates are
rounded to 4 decimals (~11 m) — ample for choropleth display, and the dominant
size lever.

Run:  python src/acquisition/extract_geojson.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyarrow.parquet as pq
import shapely
from shapely.geometry import MultiPolygon

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "staging" / "fieldmaps_admin_boundaries.geoparquet"
OUT = REPO / "frontend" / "public" / "maps"

# fieldmaps join/label columns (see acquisition_fieldmaps.md + profiling).
#   iso_3     clean ISO3 alpha  (adm0_id is "<ISO3>-<date>", not clean)
#   adm0_name country long name
#   adm1_id   fieldmaps admin1 P-code, e.g. "SDN-20230404-01"
#   adm1_name admin1 long name
COLS = ["iso_3", "adm0_name", "adm1_id", "adm1_name", "geometry"]

# 25 priority countries (docs/notes/acquisition_reliefweb.md).
PRIORITY = [
    "SDN", "YEM", "MMR", "BFA", "MLI", "NER", "TCD", "COD", "SSD", "COL",
    "VEN", "HTI", "AFG", "ETH", "SOM", "NGA", "SYR", "UKR", "PSE", "PHL",
    "HND", "GTM", "CMR", "CAF", "MOZ",
]

# Pipeline order is critical: union admin2 at FULL resolution (shared borders
# cancel exactly -> clean solid polygons, no slivers), prune tiny islands, THEN
# simplify. Simplifying BEFORE the union perturbs shared edges and the union
# can no longer merge them, leaving hundreds of thousands of sliver polygons
# that Douglas-Peucker cannot reduce (a 4-vertex ring is already minimal).
# Tolerances/areas in degrees (admin0 = world view, coarser; admin1 = zoomed).
ADMIN0_TOL = 0.05        # ~5.5 km — world-view country outlines
ADMIN0_MIN_AREA = 0.05   # deg^2 (~600 km^2) — drop islands smaller than this (keep each country's largest part)
ADMIN1_TOL = 0.01        # ~1.1 km — country-view admin1 outlines
ADMIN1_MIN_AREA = 0.0005 # deg^2 (~6 km^2) — drop only micro-islands in admin1 (keep largest part)
COORD_PRECISION = 4      # decimal places in output GeoJSON
GRID = 1e-6              # union precision grid (~0.1 m) — robust against GEOS topology errors
BATCH = 2000


def _round_coords(obj, nd: int):
    """Recursively round GeoJSON coordinate floats in place."""
    if isinstance(obj, float):
        return round(obj, nd)
    if isinstance(obj, list):
        return [_round_coords(x, nd) for x in obj]
    if isinstance(obj, dict):
        return {k: _round_coords(v, nd) for k, v in obj.items()}
    return obj


def _write_geojson(gdf: gpd.GeoDataFrame, path: Path) -> int:
    """Write a GeoDataFrame as compact, coordinate-rounded GeoJSON. Returns bytes."""
    fc = json.loads(gdf.to_json())
    fc = _round_coords(fc, COORD_PRECISION)
    text = json.dumps(fc, separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))


def _fmt_size(n: int) -> str:
    return f"{n / 1_048_576:.2f} MB" if n >= 1_048_576 else f"{n / 1024:.0f} KB"


def load_full() -> tuple[gpd.GeoDataFrame, int]:
    """Stream the parquet at FULL resolution (no pre-simplify — that would break
    shared borders), make_valid each batch, accumulate. Returns the GeoDataFrame
    and the total vertex count (for the simplification-ratio audit)."""
    pf = pq.ParquetFile(SRC)
    parts: list[gpd.GeoDataFrame] = []
    orig_verts = 0
    seen = 0
    for batch in pf.iter_batches(batch_size=BATCH, columns=COLS):
        tbl = batch.to_pydict()
        geoms = shapely.from_wkb(tbl["geometry"])
        orig_verts += int(shapely.get_num_coordinates(geoms).sum())
        geoms = shapely.make_valid(geoms)  # source has self-intersections -> union fails without this
        gdf = gpd.GeoDataFrame(
            {
                "iso_3": tbl["iso_3"],
                "adm0_name": tbl["adm0_name"],
                "adm1_id": tbl["adm1_id"],
                "adm1_name": tbl["adm1_name"],
            },
            geometry=gpd.GeoSeries(geoms),
            crs="EPSG:4326",
        )
        parts.append(gdf)
        seen += len(gdf)
        if seen % 10000 < BATCH:
            print(f"  ... streamed {seen:,}/{pf.metadata.num_rows:,} polygons")
    gdf = pd.concat(parts, ignore_index=True)
    return gpd.GeoDataFrame(gdf, geometry="geometry", crs="EPSG:4326"), orig_verts


def _prune_islands(geom, min_area: float):
    """Drop polygon parts below `min_area`, always keeping the largest part.
    Removes micro-islands/slivers that bloat the file without being visible."""
    if geom.geom_type != "MultiPolygon":
        return geom
    parts = list(geom.geoms)
    largest = max(parts, key=lambda p: p.area)
    keep = [p for p in parts if p.area >= min_area or p is largest]
    return MultiPolygon(keep) if len(keep) > 1 else keep[0]


def _dissolve(gdf: gpd.GeoDataFrame, by: str, keep: list[str], log_every: int = 25) -> gpd.GeoDataFrame:
    """Group by `by`, union each group at full resolution. Shared admin2 edges
    cancel exactly, so the merged geometry is a clean solid polygon (no slivers).
    No simplify here — callers prune + simplify after. `keep` columns take the
    first value.

    Uses `coverage_union_all` (orders of magnitude faster than `union_all` for
    non-overlapping tiling polygons like admin2). Falls back to grid-snapped
    `union_all` per group if coverage assumptions fail (near-coincident edges).
    """
    geom_col = gdf.geometry.name
    groups = list(gdf.groupby(by, sort=False))
    records = []
    geoms = []
    t0 = time.time()
    for i, (key, sub) in enumerate(groups, 1):
        vals = sub[geom_col].values
        try:
            merged = shapely.coverage_union_all(vals)
        except Exception:
            merged = shapely.union_all(vals, grid_size=GRID)
        geoms.append(merged)
        rec = {by: key}
        for c in keep:
            rec[c] = sub[c].iloc[0]
        records.append(rec)
        if i % log_every == 0 or i == len(groups):
            print(f"  ... dissolved {i}/{len(groups)} ({by}={key}, {len(vals)} parts, {time.time()-t0:.1f}s)", flush=True)
    return gpd.GeoDataFrame(records, geometry=gpd.GeoSeries(geoms), crs="EPSG:4326")


def build_admin0(gdf: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, int, int]:
    """Dissolve to one clean feature per ISO3; prune small islands and simplify
    for the world view."""
    diss = _dissolve(gdf, by="iso_3", keep=["adm0_name"])
    pruned = gpd.GeoSeries([_prune_islands(g, ADMIN0_MIN_AREA) for g in diss.geometry], crs="EPSG:4326")
    out = gpd.GeoDataFrame(
        {"iso3": diss["iso_3"], "country_name": diss["adm0_name"]},
        geometry=pruned.simplify(ADMIN0_TOL, preserve_topology=True),
        crs="EPSG:4326",
    )
    return out, len(out), int(shapely.get_num_coordinates(out.geometry.values).sum())


def build_admin1(gdf: gpd.GeoDataFrame, iso3: str) -> tuple[gpd.GeoDataFrame | None, int]:
    """Dissolve one country's admin2 polygons to clean admin1 outlines; drop
    micro-islands and simplify for the country view."""
    sub = gdf[gdf["iso_3"] == iso3]
    if sub.empty:
        return None, 0
    diss = _dissolve(sub, by="adm1_id", keep=["adm1_name", "adm0_name"])
    pruned = gpd.GeoSeries([_prune_islands(g, ADMIN1_MIN_AREA) for g in diss.geometry], crs="EPSG:4326")
    out = gpd.GeoDataFrame(
        {
            "iso3": iso3,
            "admin1_pcode": diss["adm1_id"],
            "admin1_name": diss["adm1_name"],
            "country_name": diss["adm0_name"],
        },
        geometry=pruned.simplify(ADMIN1_TOL, preserve_topology=True),
        crs="EPSG:4326",
    )
    return out, len(out)


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Missing input: {SRC}\nAcquire it first (see acquisition_fieldmaps.md).")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "admin1").mkdir(parents=True, exist_ok=True)

    print(f"Reading {SRC.name} ({SRC.stat().st_size / 1_073_741_824:.2f} GB) at full resolution in batches of {BATCH} ...")
    gdf, orig_verts = load_full()
    print(f"Loaded {len(gdf):,} polygons; {orig_verts:,} source vertices (dissolved + simplified below).\n")

    # --- admin0 ---
    print("Dissolving admin0 (per ISO3) ...")
    a0, n0, a0_verts = build_admin0(gdf)
    a0_path = OUT / "admin0.geojson"
    size0 = _write_geojson(a0, a0_path)
    over0 = " ** OVER 2 MB BUDGET **" if size0 > 2 * 1_048_576 else ""
    print(f"admin0.geojson: {n0} countries, {a0_verts:,} vertices, {_fmt_size(size0)}{over0}\n")

    # --- admin1 (priority countries) + centroids ---
    print("Dissolving admin1 (priority countries) ...")
    centroids: dict[str, list[dict]] = {}
    rows = []
    for iso3 in PRIORITY:
        a1, n1 = build_admin1(gdf, iso3)
        if a1 is None:
            print(f"  {iso3}: NOT FOUND in source — skipped")
            rows.append((iso3, 0, 0, 0, 0.0))
            continue
        path = OUT / "admin1" / f"{iso3}.geojson"
        size1 = _write_geojson(a1, path)
        a1_verts = int(shapely.get_num_coordinates(a1.geometry.values).sum())
        # representative_point() is guaranteed inside the polygon (centroid is not)
        reps = a1.geometry.representative_point()
        centroids[iso3] = [
            {
                "admin1_pcode": pc,
                "admin1_name": nm,
                "lat": round(float(pt.y), 4),
                "lon": round(float(pt.x), 4),
            }
            for pc, nm, pt in zip(a1["admin1_pcode"], a1["admin1_name"], reps)
        ]
        rows.append((iso3, n1, a1_verts, size1, size1 / 1_048_576))

    cpath = OUT / "admin1_centroids.json"
    cpath.write_text(json.dumps(centroids, separators=(",", ":")), encoding="utf-8")

    # --- audit table ---
    print("\n=== AUDIT ===")
    print(f"{'iso3':<6}{'admin1s':>9}{'vertices':>12}{'size':>12}   flag")
    for iso3, n1, verts, size1, _mb in rows:
        if n1 == 0:
            print(f"{iso3:<6}{'—':>9}{'—':>12}{'—':>12}   missing")
            continue
        flag = " ** OVER 500 KB **" if size1 > 512_000 else ""
        print(f"{iso3:<6}{n1:>9}{verts:>12,}{_fmt_size(size1):>12}{flag}")
    print(f"\nadmin0.geojson: {_fmt_size(size0)} ({n0} countries){over0}")
    print(f"admin1_centroids.json: {_fmt_size(cpath.stat().st_size)} "
          f"({sum(len(v) for v in centroids.values())} admin1 areas across {len(centroids)} countries)")
    print(f"\nWrote outputs under {OUT}")


if __name__ == "__main__":
    main()
