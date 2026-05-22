# Acquisition findings: fieldmaps.io admin boundaries

> **Source of these findings.** Captured from a Claude Code acquisition session on 2026-05-21. Findings are based on the session's verification report and the artifacts it produced (`src/verify_boundaries.py`, `staging/fieldmaps_admin_boundaries.geoparquet`, `staging/_hdx_edge_matched.json`). Less detail than the CERF UFE notes because only structural verification was performed; deeper profiling can be obtained by running `src/verify_boundaries.py` against the downloaded file. Promoted into `docs/data-catalog.md` and `docs/schemas.md` when those are written.

## What was acquired

- **Dataset**: fieldmaps.io "Global Edge-matched Subnational Boundaries (Humanitarian)" from HDX
- **Resource downloaded**: `adm2_polygons.parquet` (the all-levels-included variant)
- **Format**: GeoParquet 1.1.0
- **Size**: ~2.05 GB
- **Row count**: 43,064 polygons
- **Output**: `./staging/fieldmaps_admin_boundaries.geoparquet` + metadata at `./staging/_hdx_edge_matched.json`

## Verified facts

- **CRS**: OGC:CRS84 (≡ EPSG:4326 in axis order semantics — WGS84 longitude/latitude).
- **ISO3 join column**: `iso_3` (note underscore, not concatenated). Use this for joining to the rest of the country-level dimensional model.
- **Coverage at adm0 / adm1 / adm2** confirmed for the ten priority countries: SDN, YEM, MMR, BFA, HTI, COL, VEN, COD, NGA, ETH (the list passed to the acquisition prompt).

## What was NOT verified during acquisition

- Full column inventory of the parquet file — only the join column (`iso_3`) and coverage at three admin levels were inspected. The complete column schema is in the file but not enumerated in these notes.
- Polygon validity (no `ST_IsValid` checks, no self-intersection checks).
- Edge-matching quality — fieldmaps' value proposition is that boundaries are edge-matched across countries (no slivers, no gaps), but this was not directly verified.
- P-code column naming and coverage — fieldmaps uses UN p-codes (we believe), but the specific column names (`adm1_pcode`, `adm2_pcode`, etc.) were not enumerated.
- Disputed-territory treatment (Western Sahara, Kosovo, Crimea, etc.) — fieldmaps generally follows OCHA operational conventions but specific handling not verified in this session.
- Geometry encoding details (WKB vs GeoArrow native; precision; whether `geometry` is a single column or per-admin-level).

## Implications for downstream layers

- **Silver**: `silver_boundaries` reads from the geoparquet using Spark's `geoparquet` reader (or via Apache Sedona if installed). H3 indexing happens here. Join key is `iso_3`.
- **Subnational analysis**: `gold_subnational_index` joins HNO admin1 data to boundary polygons for choropleth rendering. Verify p-code column names match between fieldmaps and HNO before relying on them.
- **Storage CRS**: EPSG:4326 / OGC:CRS84 is what we want for storage. Web Mercator (EPSG:3857) reprojection happens at the tile layer in the frontend, not in the data layer.

## Recommended follow-up before Silver layer work

A short verification notebook should run against `staging/fieldmaps_admin_boundaries.geoparquet` to enumerate:

1. Full column schema
2. Distinct values for admin levels (`adm0_pcode`, `adm1_pcode`, `adm2_pcode` or whatever the actual columns are named)
3. P-code conformance to UN p-code conventions (`<iso3><admin1_num>`, etc.)
4. Polygon validity counts
5. Row counts per ISO3 to confirm the global coverage claim

This can be done by running `src/verify_boundaries.py` (already exists from acquisition) and possibly extending it. Findings get appended here or promoted to `docs/data-catalog.md`.

## Open questions

- Column schema beyond `iso_3` and the geometry column.
- P-code naming convention (do they match HNO's p-codes one-to-one for join purposes?).
- Polygon validity at the level needed for spatial operations (point-in-polygon, adjacency).
- How disputed-territory edge cases are encoded (e.g., is Western Sahara a separate admin0, part of Morocco's admin0, or both via overlapping polygons?).
- Whether the parquet contains all three admin levels in one file (43,064 rows suggests yes — that's roughly the global count of admin2 areas, with admin0 and admin1 likely accessible by filtering) or only adm2.
