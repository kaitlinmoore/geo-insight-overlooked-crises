"""One-off verification of the fieldmaps edge-matched admin boundary file.

Confirms CRS, schema, ISO3 presence, and coverage at adm0/adm1/adm2 for the
priority crisis countries. Run after staging/fieldmaps_admin_boundaries.geoparquet
is downloaded.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import pyarrow.parquet as pq
from shapely.validation import explain_validity

PATH = Path(__file__).resolve().parents[1] / "staging" / "fieldmaps_admin_boundaries.geoparquet"
TARGETS = ["SDN", "YEM", "MMR", "BFA", "HTI", "COL", "VEN", "COD", "NGA", "ETH"]
ADM2_DEEP_DIVE = ["SDN", "YEM"]


def _fmt(ok: bool) -> str:
    return "OK " if ok else "FAIL"


def main() -> int:
    if not PATH.exists():
        print(f"FAIL  file not found: {PATH}")
        return 1

    size_gb = PATH.stat().st_size / 1e9
    print(f"File: {PATH}")
    print(f"Size: {size_gb:.2f} GB\n")

    pf = pq.ParquetFile(PATH)
    geo_meta = json.loads(pf.schema_arrow.metadata[b"geo"].decode())
    primary = geo_meta["primary_column"]
    crs_field = geo_meta["columns"][primary].get("crs")

    print("--- GeoParquet metadata ---")
    print(f"Version: {geo_meta.get('version')}")
    print(f"Primary geometry column: {primary}")
    if crs_field is None:
        print("CRS: not set -> defaults to OGC:CRS84 (lon/lat, equivalent to EPSG:4326)")
    else:
        print(f"CRS: {crs_field if isinstance(crs_field, str) else crs_field.get('id', crs_field)}")
    print(f"Row count: {pf.metadata.num_rows:,}")
    print(f"Row groups: {pf.metadata.num_row_groups}")

    print("\n--- Column schema ---")
    for f in pf.schema_arrow:
        print(f"  {f.name:18s} {f.type}")

    cols = [f.name for f in pf.schema_arrow]
    iso3_col = "iso_3" if "iso_3" in cols else ("iso3" if "iso3" in cols else None)
    print(f"\nISO3 column: {iso3_col!r}  {_fmt(iso3_col is not None)}")
    if iso3_col is None:
        return 2

    print("\n--- Reading rows for target countries (filtered) ---")
    gdf = gpd.read_parquet(
        PATH,
        filters=[(iso3_col, "in", TARGETS)],
        columns=[iso3_col, "adm0_id", "adm0_name", "adm1_id", "adm1_name", "adm2_id", "adm2_name", "geometry"],
    )
    print(f"Rows loaded: {len(gdf):,}")
    print(f"CRS at read time: {gdf.crs}")

    print("\n--- Coverage per country (adm2 rows / unique adm1 / unique adm0) ---")
    print(f"{'iso3':6s} {'adm2 rows':>10s} {'adm1 ids':>10s} {'adm0 ids':>10s}  status")
    all_ok = True
    for iso in TARGETS:
        sub = gdf[gdf[iso3_col] == iso]
        n_adm2 = sub["adm2_id"].notna().sum()
        n_adm1 = sub["adm1_id"].dropna().nunique()
        n_adm0 = sub["adm0_id"].dropna().nunique()
        ok = (len(sub) > 0) and (n_adm0 >= 1) and (n_adm1 >= 1)
        all_ok &= ok
        print(f"{iso:6s} {n_adm2:>10d} {n_adm1:>10d} {n_adm0:>10d}  {_fmt(ok)}")

    print("\n--- Polygon validity (sample of 200 geoms across targets) ---")
    sample = gdf.sample(min(200, len(gdf)), random_state=0)
    invalid = sample[~sample.geometry.is_valid]
    print(f"Invalid in sample: {len(invalid)} / {len(sample)}")
    for _, row in invalid.head(5).iterrows():
        print(f"  {row[iso3_col]} {row.get('adm2_name')}: {explain_validity(row.geometry)[:120]}")

    print("\n--- adm0 dissolve check (admin0 polygons) ---")
    adm0 = gdf.dissolve(by=iso3_col, aggfunc="first")
    print(f"adm0 polygons produced: {len(adm0)} (expected {len(TARGETS)})")
    for iso in TARGETS:
        present = iso in adm0.index
        geom = adm0.loc[iso].geometry if present else None
        valid = bool(geom is not None and geom.is_valid and not geom.is_empty)
        print(f"  {iso}: {_fmt(present and valid)} area={geom.area if valid else 0:.4f}")

    print("\n--- adm1 dissolve check (state/province polygons per country) ---")
    adm1 = gdf.dissolve(by=[iso3_col, "adm1_id"], aggfunc="first")
    for iso in TARGETS:
        try:
            n = len(adm1.loc[iso])
        except KeyError:
            n = 0
        print(f"  {iso}: {n} adm1 polygons  {_fmt(n >= 1)}")

    print("\n--- adm2 deep-dive (district polygons for SDN, YEM) ---")
    for iso in ADM2_DEEP_DIVE:
        sub = gdf[(gdf[iso3_col] == iso) & gdf["adm2_id"].notna()]
        valid = sub.geometry.is_valid.sum()
        print(f"  {iso}: {len(sub)} adm2 rows, {valid} valid geoms  {_fmt(len(sub) >= 1)}")

    print(f"\nOverall: {_fmt(all_ok)}")
    return 0 if all_ok else 3


if __name__ == "__main__":
    sys.exit(main())
