# Acquisition findings: CERF UFE allocations

> **Source of these findings.** Captured from a Claude Code acquisition session on 2026-05-21. Findings are the session's verified observations on the downloaded dataset, not inferences from documentation. Marked clearly where facts were verified vs. where they were sampled vs. where they remain open. Promoted into `docs/data-catalog.md` and `docs/schemas.md` when those are written.

## What was acquired

- **Dataset**: HDX dataset slug `cerf-allocations`
- **Publisher**: OCHA / CERF
- **License**: CC BY-IGO
- **Refresh cadence**: `data_update_frequency: 7` (weekly)
- **Resources available**: plain CSV, HXLated CSV (HXL tags on row 2), JSON feed at `cerfgms-webapi.unocha.org`. The plain CSV used here is a published Google Sheet export.
- **Output**: `./staging/cerf_allocations_raw.csv` (full unfiltered dataset), `./staging/ufe_labels.csv` (derived labels)

## Schema (18 columns, 8511 rows, 2006-2026)

```
agencyName
continentName
countryCode
countryName
dateUSGSignature
emergencyTypeName
projectCode
projectID
projectTitle
regionName
tableName
totalAmountApproved
windowFullName
year
projectsectors
projectclusters
projectgroupings
projectcapcodes
```

## Verified facts (directly checked, not inferred)

- **`windowFullName` is the UFE / RR discriminator.** Values: `Rapid Response` (5508 rows), `Underfunded Emergencies` (3003 rows). No nulls, no third value, no synonyms.
- **`countryCode` is ISO3.** For all 3003 UFE rows it's a valid 3-letter code with zero anomalies. *Note: not validated across the 5508 RR rows yet.*
- **`dateUSGSignature` is ISO `YYYY-MM-DD`** with zero missing among UFE rows.
- **`year` equals signature year for every UFE row** (0 mismatches out of 3003). The `year` column is the signing year, not a separate fiscal or appeal year.
- **`totalAmountApproved` is numeric USD**, parses cleanly to float.

## Quirks worth knowing about

These are facts about the data that affect how we use it downstream. Capture in `docs/schemas.md` for Silver layer reference.

**No `round` column.** UFE rounds are not labeled in the source data. Round must be derived from `dateUSGSignature`. However: **the USG signature date lags the ERC's round announcement by 2-6 months**, so simple date-based H1/H2 bucketing drifts. Examples:

- Syria 2024 Round 1 was signed entirely in August → lands in H2 if you bucket on signature date
- Round 1 stragglers can leak into H2 generally
- Year-grain is exact (2024: 17 of 17 UFE allocations correctly attributed to 2024)
- Round-grain requires joining on a separate announcement-date table

For v1 validation: year-grain UFE labels are sufficient. If we later need round-grain, we need to find or build an announcement-date lookup.

**Country names are long-form.** `Republic of the Sudan`, `Syrian Arab Republic`, `Democratic Republic of the Congo`, `Central African Republic`, etc. **Always join on `iso3` (= `countryCode`), never on name.**

**`tableName` field is unexplained.** Values `P` (4774 rows) and `M` (3737 rows). Does **not** correspond to the window (which is what `windowFullName` does). Meaning was not determined during acquisition.

- Possible candidates: P = Project / M = Modification? P = Primary / M = Modified?
- **Action**: ask Mary Keller via Slack, or look it up in CERF documentation, before relying on this field

**Multi-value delimited fields, frequently empty.** `projectsectors`, `projectclusters`, `projectgroupings`, `projectcapcodes` appear to be multi-value (delimited) fields. They are frequently empty. **These were not profiled in this acquisition.** If we want to use them for sector-aware analysis, a dedicated profiling pass is needed first.

**2026 has 77 rows but zero UFE allocations.** The first 2026 UFE round typically signs in Feb-May. UFE labels in `ufe_labels.csv` therefore stop at 2025. This is timing, not a bug.

## What `ufe_labels.csv` contains

Derived from the raw allocations, filtered to `windowFullName = 'Underfunded Emergencies'`:

```
iso3, country_name, year, round, ufe_selected, allocation_usd_total
```

The `round` value is derived from `dateUSGSignature` using H1/H2 bucketing — see the round caveat above. Year-grain labels are reliable; round-grain labels carry the documented derivation drift.

## Implications for downstream layers

- **Silver**: `silver_cerf_allocations` joins to `silver_country_dim` on `iso3`. The `tableName` field is carried through but not used until we understand it.
- **Gold**: `gold_ufe_validation` consumes `ufe_labels.csv` (after upload to Bronze) joined against the ranking output for held-out precision/recall. Use year-grain joins for v1.
- **Validation logic**: predictions and labels both keyed on (iso3, year) for v1.

## Open questions

- Meaning of `tableName` field (P vs M).
- RR-row schema integrity — only UFE rows were spot-checked for ISO3 validity. RR rows haven't been verified.
- Multi-value field schemas (`projectsectors` etc.) — delimiter, common values, null pattern not yet profiled.
- Whether to derive round-grain labels for v2 via announcement-date lookup, or stay at year-grain.
