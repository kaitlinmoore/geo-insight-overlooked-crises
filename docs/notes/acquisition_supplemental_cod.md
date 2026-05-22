# Acquisition findings: supplemental COD datasets

> **Source of these findings.** Captured from a Claude Code acquisition session on
> 2026-05-22, acting on the three "acquire" recommendations in
> `docs/notes/cod_audit.md`. Findings are the session's verified observations on the
> downloaded files (profiled with pandas), marked clearly where facts were verified vs.
> sampled vs. left open. Per the scope carve-out in `claude.md`, this is one-off
> acquisition work: `STATE.md` and `DECISIONS.md` were **not** edited. Promote into
> `docs/data-catalog.md` / `docs/schemas.md` when those are written.
>
> **No raw data committed.** All outputs landed in gitignored `./staging/`. The three
> acquisition scripts (`src/acquire_global_pcodes.py`, `src/acquire_cod_population.py`,
> `src/acquire_country_taxonomy.py`) are reproducible and safe to commit.
>
> **Tooling note.** HDX blocks WebFetch (Cloudflare 403); the scripts download with a
> browser `User-Agent` header and resolve resource URLs live via the CKAN API so they
> survive resource-id rotation.

## What was acquired

| Dataset | HDX slug / source | Staging output | Size | Script |
|---|---|---|---|---|
| Global P-code List | `global-pcodes` | `global_pcodes_raw.csv` | 13.8 MB | `src/acquire_global_pcodes.py` |
| P-code length reference | `global-pcodes` (resource) | `global_pcode_lengths.csv` | 1.6 KB | (same) |
| COD-PS admin2 population | `cod-ps-global` (resource) | `cod_population_admin2.csv` | 142 MB | `src/acquire_cod_population.py` |
| COD-PS admin3 population | `cod-ps-global` (resource) | `cod_population_admin3.csv` | 37 MB | (same) |
| OCHA Countries & Territories taxonomy | OCHA C&T MVP Google-Sheets feed | `country_taxonomy_raw.csv` | 95 KB | `src/acquire_country_taxonomy.py` |

Dataset metadata snapshots were also written to `staging/_global_pcodes_meta.json` and
`staging/_cod_ps_global_meta.json` for the audit trail.

---

## A. Global P-code List (`global_pcodes_raw.csv`)

**Verified schema** (7 columns, 265,199 rows, 109 countries/territories):

```
Location        # ISO3 (the join key; column is named "Location", not iso3)
Admin Level     # integer 1..5
P-Code          # the p-code string
Name            # admin unit name (Latin where available)
Parent P-Code   # p-code of the parent unit (admin0 = ISO3 for admin1 rows)
Valid from date # ISO YYYY-MM-DD
Version         # e.g. v03
```

**Verified facts:**

- **Rows per admin level:** adm1 = 1,874 · adm2 = 20,846 · adm3 = 81,222 · adm4 = 159,785 · adm5 = 1,472.
- **Parent-p-code integrity is clean:** 0 of 20,846 admin2 rows have a parent that is not a
  valid admin1 p-code (0.00% orphans). The `Parent P-Code` column gives a free
  admin2 → admin1 → admin0 rollup hierarchy.
- **All 10 priority countries have admin1 + admin2 p-codes.** Admin-depth varies:

  | iso3 | adm1 | adm2 | adm3 | max level |
  |------|-----:|-----:|-----:|:---------:|
  | SDN | 19 | 189 | 0 | 2 |
  | YEM | 22 | 335 | 0 | 2 |
  | MMR | 18 | 5 | 255 | 5 |
  | BFA | 17 | 47 | 351 | 3 |
  | HTI | 10 | 140 | 570 | 3 |
  | COL | 33 | 1,122 | 31,799 | 3 |
  | VEN | 24 | 335 | 1,134 | 3 |
  | COD | 26 | 164 | 519 | 3 |
  | NGA | 37 | 774 | 714 | 3 |
  | ETH | 15 | 107 | 1,148 | 3 |

**Quirks worth knowing (capture in `docs/schemas.md`):**

- **P-code prefix convention is NOT uniform across countries.** Most use an ISO2-style
  alpha prefix (`SD01`, `YE11`, `BF13`, `HT01`, `CO05`, `VE01`, `CD10`, `ET01`); a few use
  an ISO3-style prefix (`MMR001`, `NG001`). **Do not assume `<ISO3><digits>`.** The
  companion `global_pcode_lengths.csv` documents, per country, the prefix length
  (`Country Length` = 2 or 3) and the total p-code length at each admin level — this is the
  authoritative spec for any HNO p-code format-validation check. The methodology's earlier
  assumption that admin1 p-codes follow `<ISO3><admin1_num>` (docs/methodology.md follow-up
  notes) is **only true for some countries**; validate against the lengths table, not a
  hardcoded pattern.
- **MMR is structurally unusual:** only 5 admin2 p-codes but 255 admin3 (Myanmar's
  district/township hierarchy). If HNO publishes Myanmar at township level, that maps to
  admin3 here, not admin2.
- **`Location` is the ISO3 column name** — not `iso3` or `iso_3` (cf. fieldmaps' `iso_3`).
  Rename on ingest for consistency with `silver_country_dim`.

**Implications for downstream layers:**

- Lands as `bronze_global_pcodes` → `silver_pcode_reference`. Ship `global_pcode_lengths.csv`
  alongside as `silver_pcode_format_spec`.
- Validation use: join HNO (iso3, admin-level, p-code) against this reference; flag p-codes
  absent from the reference (typos / stale / non-standard) and p-codes whose length violates
  the per-country spec. This is the lightweight conformance gate that resolves the
  fieldmaps↔HNO p-code join question without parsing 2 GB of geometry.

---

## B. COD-PS admin2 + admin3 population

### B1. `cod_population_admin2.csv` — 1,001,583 rows

**Verified schema** (19 columns): `ISO3, Country, ADM1_PCODE, ADM1_NAME, ADM2_PCODE,
ADM2_NAME, ADM3_PCODE, ADM3_NAME, ADM4_PCODE, ADM4_NAME, Population_group, Gender,
Age_range, Age_min, Age_max, Population, Reference_year, Source, Contributor`.

**Verified facts:**

- **The global rollup is LONG-format and age/sex disaggregated** — *not* totals-only as the
  COD audit assumed. `Gender ∈ {f, m, all}`; `Age_range` has 61 distinct values (5-year
  bands plus single-year and open-ended like `100+`); `Population_group` carries the COD
  cohort codes (`F_00_04`, `M_TL`, `T_TL`, …). **This means the age/sex disaggregation the
  audit deferred to v2 is already in hand** for the admin levels covered.
- **Total-population denominator convention:** filter `Population_group == 'T_TL'`
  (equivalently `Gender == 'all'` & all-ages). 19,017 `T_TL` rows. Sanity check (sum of
  admin2 `T_TL`): SDN ≈ 47.5M, COL ≈ 53.2M, ETH ≈ 102.5M — all plausible.
- **Coverage is partial: 77 of 109 countries have admin2 population.**
- **Three priority countries are MISSING admin2 population entirely: YEM, MMR, NGA.** Their
  boundaries/p-codes exist (see section A) but admin2 population does not in this rollup —
  they presumably carry admin1 population only. These must fall back to admin1 denominators
  and carry a `data_sparsity_flag` at admin2 (exactly the methodology's graceful-degradation
  case).

  | iso3 | admin2 units w/ pop | reference year |
  |------|--------------------:|:--------------:|
  | SDN | 188 | 2024 |
  | BFA | 45 | 2024 |
  | HTI | 140 | 2024 |
  | COL | 1,122 | 2025 |
  | VEN | 335 | **2011** |
  | COD | 189 | 2020 |
  | ETH | 92 | 2022 |
  | YEM | 0 | — |
  | MMR | 0 | — |
  | NGA | 0 | — |

- **Reference years vary widely and some are stale.** Notably **VEN = 2011 (15 years old)**;
  COD = 2020; ETH = 2022. Carry `Reference_year` through to Gold to drive the data-freshness
  indicators the honesty commitments require.

### B2. `cod_population_admin3.csv` — 241,962 rows

- **Only 19 countries have admin3 population.** Of the priority set, **only ETH** (1,084
  admin3 units, ref year 2022). Confirms the audit's call that admin3 is low-priority — it's
  a bonus for the handful of countries that have it, not a general capability.

**Implications for downstream layers:**

- `bronze_cod_population_admin2` / `_admin3` → Silver population dims keyed on
  (iso3, ADMn_PCODE). For the `severity_rate` denominator, pre-aggregate `T_TL` to one row
  per admin unit; keep the disaggregated rows available for any future demographic feature.
- **admin2 `severity_rate` is computable for 7 of 10 priority countries** (SDN, BFA, HTI,
  COL, VEN, COD, ETH). YEM, MMR, NGA degrade to admin1 with `data_sparsity_flag`.
- Reference-year column feeds the per-country data-freshness flag; VEN especially should be
  surfaced as low-confidence.

---

## C. OCHA Countries & Territories taxonomy (`country_taxonomy_raw.csv`)

**Verified facts** (256 rows; 249 with a valid ISO3; 197 flagged `Independent == Y`):

- **All 10 priority countries are present with the full UN M49 regional hierarchy**
  (`Region Name/Code`, `Sub-region Name/Code`, `Intermediate Region Name/Code`). Examples:
  SDN → Africa / Northern Africa; COD → Africa / Sub-Saharan Africa / Middle Africa; COL →
  Americas / Latin America & Caribbean / South America; YEM → Asia / Western Asia. This
  directly supplies the grouping `rank_crises(scope=...)` and the cross-border view need.
- **Bonus columns beyond the audit's expectation**, useful as `silver_country_dim`
  attributes and ranking context:
  - `Has HRP` (20 countries flagged Y) and `In GHO` (54 flagged Y) — directly relevant to
    the severity gate's "active HRP" criterion and to scoping the in-ranking universe.
  - `World Bank Income Level`, `Currency`, national centroid `Latitude`/`Longitude`
    (a candidate urban/centroid anchor for `geographic_isolation`), `m49 numerical code`,
    `HPC Tools API ID`, `RW ID` (ReliefWeb), multilingual official names.
  - **`Regex` column = ready-made name matcher.** It solves the CERF/FTS long-form-name
    reconciliation flagged in the CERF UFE notes. Verified examples:
    - SDN regex matches "Republic of the Sudan" and excludes "South Sudan".
    - COD regex matches "Democratic Republic of the Congo", "DRC", "Zaire", "Kinshasa", …
    - SYR → `syria`; CAF → `\bcentral.african.rep`.

**Quirks / caveats:**

- **`Has HRP` is current-state only and has gaps.** ETH shows `Has HRP = nan` here despite an
  active response context — treat this flag as a hint, not ground truth, and prefer HPC Tools
  / actual HRP records for the severity gate. For multi-year `chronic_no_plan` logic you need
  historical HRP presence, which this single snapshot does not provide.
- **Source is a published Google-Sheets "MVP" feed**, not a versioned HDX dataset. It's the
  same feed the official `hdx-python-country` library uses, but treat it as a living document
  and re-pull periodically; pin a copy in Bronze for reproducibility.
- 256 rows includes territories and non-independent entities; filter on `Independent` /
  valid ISO3 as needed.

**Implications for downstream layers:**

- Lands as `bronze_country_taxonomy` → `silver_country_dim`. Use `ISO 3166-1 Alpha 3-Codes`
  as PK; expose `Region/Sub-region/Intermediate Region` for scoping, `Regex` for name
  normalization of CERF/FTS/HNO variants, and `Has HRP`/`In GHO`/income as context columns.
- Per `claude.md` ("don't add dependencies casually"), the static CSV is sufficient for v1;
  `hdx-python-country` remains an optional convenience (FX rates, fuzzy admin-name matching)
  if needed later.

---

## Net effect on the project (summary)

- **P-code validation is now unblocked.** We have a canonical 109-country p-code reference
  plus a per-country format spec — enough to validate HNO p-codes once HNO is acquired.
- **Subnational severity_rate is computable at admin2 for 7 of 10 priority countries.**
  YEM, MMR, NGA degrade to admin1 with a documented sparsity flag — a known, honest gap.
- **`silver_country_dim` has a rich, ready source** including region scoping and a name-matching
  regex that resolves the long-form-name joins the CERF work flagged.
- **Bonus vs. the audit:** the COD-PS global rollup turned out to carry full age/sex
  disaggregation, so the age/sex capability the audit deferred to v2 is already available for
  covered countries.

## Open questions / recommended follow-ups

1. **Confirm admin1 population for YEM, MMR, NGA.** This session pulled only admin2/admin3
   (the recommended top-up). The admin1 fallback denominator for these three should be
   verified present in `cod_population_admin1.csv` (already held per the audit). If admin1 is
   also missing for any, the country degrades to national-level only.
2. **Test the HNO ↔ global p-code join** once HNO is acquired: do HNO p-codes match the
   reference per (iso3, level, p-code), and do their lengths satisfy `global_pcode_lengths.csv`?
   Deferred until HNO lands.
3. **MMR admin-level mapping:** Myanmar has 5 admin2 but 255 admin3 p-codes. Verify which level
   HNO uses for Myanmar before joining (likely admin1 + admin3, skipping admin2).
4. **Taxonomy `Has HRP` reconciliation:** ETH shows blank; decide the authoritative HRP-presence
   source for the severity gate (HPC Tools API vs HRP records) rather than this snapshot flag.
5. **VEN population staleness (2011):** flag explicitly in the UI/data-freshness layer; consider
   whether a more recent estimate should override for the severity_rate denominator.
6. **`tableName` of the global p-codes `Version` column** is informational; decide whether to
   retain version/`Valid from date` for time-versioned boundary lineage.
