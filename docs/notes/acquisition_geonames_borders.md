# Acquisition findings: GeoNames country-border adjacency

> **Source of these findings.** Captured from a Claude Code acquisition session on 2026-05-22. Findings are the session's verified observations on the downloaded dataset, not inferences from documentation. Marked where facts were verified vs. open. Promote into `docs/data_catalog.md` / `docs/schemas.md` if the source is adopted.

## Bottom line

A **portable, dependency-light replacement** for the deferred Sedona polygon-adjacency path (serverless Databricks can't install the Sedona JVM library — see `DECISIONS.md` serverless entry). GeoNames `countryInfo.txt` carries a per-country `neighbours` list out of the box; we convert it from alpha-2 to alpha-3 using the file's own ISO↔ISO3 mapping (no external country-code dependency). Pulled **252 rows, mean 2.60 land neighbours, 0 unresolved neighbour codes, 87 zero-neighbour countries (islands + a few dependent territories)**. No auth, CC-BY. **Recommendation: commit the script + this note; load as a new Bronze table `bronze_country_borders`; feed `gold_cross_border_patterns`.**

## What was acquired

- **Source**: GeoNames `countryInfo.txt` — `http://download.geonames.org/export/dump/countryInfo.txt`
  - Tab-separated reference table: ~50 lines of `#`-comment metadata, a `#ISO…` header row, then one data row per country.
  - The `neighbours` column (index 17) is a comma-separated list of **alpha-2** codes; converted to alpha-3 from the file's own ISO↔ISO3 mapping (every row maps its own alpha-2 → alpha-3).
- **Publisher**: GeoNames. **License**: **CC-BY** (attribution required; the script prints a one-line attribution to stdout on each run). **Refresh cadence**: GeoNames updates `countryInfo.txt` ~quarterly. **Auth**: none.
- **Output**: `./staging/country_borders.csv` (252 rows). Metadata snapshot: `./staging/_country_borders_meta.json` (source URL + acquisition date + counts + the zero-neighbour and unresolved-code lists).
- **Script**: `src/acquisition/acquire_geonames_borders.py` (`--check`).

## Verified schema (4 columns, 252 rows)

The CSV's first physical line is a `#`-comment provenance banner (source URL + acquisition date + license); the Bronze loader skips it via the Spark CSV `comment="#"` option, so the real header is line 2.

| Column | Type | Notes |
|---|---|---|
| `iso3` | string (3 chars) | ISO3 alpha-3 (from `countryInfo.txt` ISO3 column). PK. 252 distinct, sorted. |
| `country_name` | string | GeoNames short country name (`Afghanistan`, `Western Sahara`, …). |
| `neighbor_iso3_list` | string | Comma-separated alpha-3 neighbour codes; **empty** for islands / dependent territories with no listed land border (e.g. `NZL`, `AUS`, `JPN`, `MDG`, `LKA`, `GRL`, `FRO`). |
| `n_neighbors` | int | Count of resolved alpha-3 neighbours; matches the length of `neighbor_iso3_list`. |

## Verified facts (directly checked, not inferred)

- **252 output rows**; not every ISO3 in the world has a row (GeoNames excludes some very small territories). Comfortably the expected ~250.
- **0 unresolved neighbour codes** — every alpha-2 in every `neighbours` list resolved to an alpha-3 via the file's own map. (No `pycountry` needed.)
- **Mean `n_neighbors` = 2.60.** Max is **RUS = 14** (`GEO,CHN,BLR,UKR,KAZ,LVA,POL,EST,LTU,FIN,MNG,NOR,AZE,PRK`); landlocked and large countries report their full land borders (e.g. `ZMB` = 7, `AFG` = 6, `ZAF` = 6), confirming the list is land-border adjacency, not just coastal.
- **87 zero-neighbour countries** — overwhelmingly islands (`NZL`, `AUS`, `JPN`, `MDG`, `LKA`, `FJI`, `MUS`, `ISL`, `MLT`, `CYP`, `PHL`, …). Landlocked countries are **not** in this list (they still report land borders), exactly as expected.

## Quirks worth knowing about (surprises)

- **`CUB` (Cuba) is NOT zero-neighbour** — it lists `USA` as a single neighbour (`CUB,Cuba,USA,1`). GeoNames records the **Guantánamo Bay** land boundary between the US naval base and Cuba. Correspondingly `USA` lists `CAN,MEX,CUB`. This contradicts the naïve "Cuba is an island ⇒ 0 neighbours" expectation; it's correct per GeoNames, just non-obvious.
- **`GRL` (Greenland) and `FRO` (Faroe Islands)** are both in the file with **0 neighbours** — the dependent-territory case the brief flagged. They behave correctly (no spurious land border to Denmark).
- **Two non-standard ISO3 codes appear** and will simply not match `gold_forgotten_crisis_index` on join (harmless, but documented):
  - `ANT` — **Netherlands Antilles**, a deprecated ISO code (the entity dissolved in 2010); GeoNames still carries the row, with a single odd maritime neighbour `GLP` (Guadeloupe).
  - `XKX` — **Kosovo**, the user-assigned placeholder code (no official ISO3); neighbours `SRB,ALB,MKD,MNE`. Note Kosovo also appears as `XKX` inside `ALB`/`MKD`/`MNE`/`SRB` neighbour lists.
- **Disputed/partially-recognized territories are present as their own rows**: `ESH` (Western Sahara → `DZA,MRT,MAR`), `PSE` (Palestinian Territory → `JOR,ISR,EGY`), `TWN` (Taiwan → 0). Adjacency here is GeoNames' worldview, which may differ from OCHA's; for v1 cross-border clustering this is acceptable (we only use it to count ranked neighbours), but flag it if the table is ever used for boundary rendering.

## Use cases

- Loads as **`bronze_country_borders`** (single CSV, schema `iso3 string, country_name string, neighbor_iso3_list string, n_neighbors int`).
- Feeds **`gold_cross_border_patterns`**: explode `neighbor_iso3_list`, join back to `gold_forgotten_crisis_index` (same year) to compute neighbour overlooked-score aggregates and regional-cluster groupings.
- Does **not** replace the frontend choropleth maps — those come from the offline GeoJSON extraction (`src/acquisition/extract_geojson.py`), which is unchanged.

## Refresh cadence

GeoNames updates `countryInfo.txt` roughly **quarterly**. Re-acquire when the data is stale or the row shape changes — a trivial re-run of the script (no credentials). The output is idempotent (overwrites `country_borders.csv`); the header comment records the source URL + acquisition date.

## Open questions

- **`ANT` / `XKX`** — non-standard codes. They drop out of any `gold_forgotten_crisis_index` join (which keys on standard ISO3), so they're harmless to the cross-border aggregates, but if a future step joins `bronze_country_borders` to `silver_country_dim` we should decide whether to filter or remap them (`ANT` → drop; `XKX` → `XKX`/`KOS`? — match whatever `silver_country_dim` uses).
- **Maritime/base adjacencies** — `CUB↔USA` (Guantánamo) and `ANT↔GLP` are real in GeoNames but unusual; confirm they don't distort cross-border cluster aggregates if either appears in the index.
- **Worldview** — `ESH`/`PSE`/`TWN` adjacency reflects GeoNames' conventions, not necessarily OCHA's. Acceptable for neighbour-counting in v1; revisit if used for anything boundary-sensitive.
