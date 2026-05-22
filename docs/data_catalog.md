# Data Catalog

The operational companion to `docs/schemas.md`. Where `schemas.md` gives the column-level shape of each Bronze table, this file gives the source-level detail you need to understand before ingestion: where the file is, how big, how it updates, what to watch out for, how it joins to everything else.

## How this file is used

- **Loader authors** consult the per-source section before writing the Bronze loader (file pattern, header quirks, schema drift across years, source-specific gotchas).
- **Methodology readers** consult the cross-source identity section and distinct-value inventories to understand what populations and categories actually exist in the data.
- **Reviewers** consult the headline-findings table to see provenance, freshness, and what's known to be incomplete.

Every distinct-value inventory in this file is verified empirically from the source files (profiling session 2026-05-22) unless explicitly marked **pending first Bronze ingest** for sources that live in `staging/` and weren't directly inspected. Where `schemas.md` and this file disagree, `schemas.md` governs the column shape and types; this file governs operational detail.

## Conventions used in this file

- **CMU drop** = the canonical OCHA dataset bundle provided as the hackathon starter, mounted locally at `data/databricks_data/unocha/` and copied into project knowledge at `/mnt/project/`.
- **Staging** = `./staging/` in the repo (gitignored). Holds acquisition-script outputs.
- **Volume target** = the `/Volumes/geo_insight/raw/staging/...` path in the Databricks workspace where files land before Bronze loaders run. Permissions pending.
- All file paths in the "Source files" lines are local; the Databricks volume version is the same filename under the volume target.
- **HXL** = Humanitarian Exchange Language hashtag convention. Several CMU files carry a hashtag row immediately after the header (`#country+code`, `#response+code`, etc.) that needs to be preserved verbatim in Bronze and dropped in Silver.

---

# Headline findings

These are the things any session writing Bronze loaders, Silver transforms, or Gold computations should know before starting.

| Theme | Finding | Impact |
|---|---|---|
| **HNO schema drift** | HNO 2024/2025 are long-format with admin0/1/2/3 + demographic Category fan-out and an HXL row; HNO 2026 is 134-row country×cluster wide, no admin columns, no HXL row, proper numeric dtypes. | Two distinct Bronze load paths or `mergeSchema=true`. 2026 subnational analysis must source from elsewhere. |
| **HNO 2025 string-typed numerics** | Every numeric column (`Population`, `In Need`, `Targeted`, `Affected`, `Reached`) reads as `string` due to the HXL row forcing object dtype. | Cast in Silver, not Bronze. Carry parse-failure rows to `_quarantine`. |
| **Ethiopia absent from HNO** | ETH has zero rows in HNO 2025 and is absent from HNO 2026 despite being on the priority country list. | Source ETH PIN from a prior HNO year with a freshness flag, or accept ETH drops from the demo. Open in `open-questions.md`. |
| **Admin1 derived, not read** | SDN, YEM, HTI, VEN, NGA have only admin2 rows in HNO 2025 (no admin1 rows). BFA, COD have only country-level rows. | Silver derives admin1 by P-code-prefix rollup from admin2; carries `data_sparsity_flag` for country-only countries. |
| **FTS multi-country delimiter is comma** | `fts_incoming_funding_global.destLocations` uses comma between ISO3 codes (`ABW,ARG,BOL,...`). HRP `locations` uses pipe with spaces (`YEM \| KEN \| ETH`). | Each loader handles its source's specific delimiter; don't share parsing logic across sources. |
| **FTS plan-type rename in 2024** | `typeName` shifted from `Humanitarian response plan` (HRP) to `Humanitarian needs and response plan` (HNRP) between 2023 (fully HRP) and 2026 (fully HNRP). | Unify HRP + HNRP into `country_response_plan` in Silver. |
| **FTS "Not specified" country-aggregate rows** | 2,577 of 3,836 rows (67%) in `fts_requirements_funding_global.csv` have NULL `code` and `name='Not specified'` — off-plan funding to a country in a given year. | Carried as a separate Silver grain (`plan_code IS NULL`), per DECISIONS 2026-05-22. Preserves signal for no-HRP countries like ETH 2026. |
| **FTS globalcluster vs cluster** | `fts_requirements_funding_cluster_global.csv` has 962 raw cluster name variants (mixed case, multilingual). `fts_requirements_funding_globalcluster_global.csv` is the normalized 24-name IASC rollup. | Use globalcluster for cross-country sector comparison; cluster for source-of-truth audit. Mapped in `silver_sector_crosswalk`. |
| **INFORM Severity sheet rename** | Files Jan 2019–Aug 2020 (20 files) carry data on a `GCSI` sheet; Sep 2020 onward (69 files) use `INFORM Severity - country`. Same downstream schema. | Bronze loader dispatches by sheet name — `INFORM Severity - country` if present, else `GCSI`. Recorded in DECISIONS 2026-05-22. |
| **INFORM Severity dual scale** | The file carries both `INFORM Severity Index` (continuous 1–10) and `INFORM Severity category` (ordinal 1–5). | Methodology's severity gate (`≥4`) and chronic check (`≥3`) refer to the **1–5 category**, not the index. |
| **CBPF Contributions has no fund or country column** | Nine files cover 2018–2026, one per year, but the schema is `Year, Donor, Donor type, Paid, Pledged, Total` — global donor totals, not attributable to a fund or crisis. | `gold_donor_concentration` is computed from `silver_fts_flows.donor_org`, not from CBPF. Recorded in DECISIONS 2026-05-22. |
| **CBPF Allocations is yearly-split** | Nine `Allocations__*.csv` files = nine years. Each file has the same schema; `_source_file` carries the year. | Concatenate at Bronze; dedupe (23 exact dupes after concat). |
| **VEN population 15 years stale** | COD-PS `cod_population_admin0.csv` reference year for VEN is 2011. | `severity_rate = PIN / population` is unreliable for VEN. Open item: `stale_population_flag` distinct from `data_sparsity_flag`. |
| **Multi-country flows are 31.5% of incoming dollars, 99.1% lack destPlan** | 528 multi-country flows (5.7% of rows, 31.5% of $) where only 5 carry a `destPlan`. | `population_weighted_fallback` is the de facto handler. Cascade order preserved; framing updated. Recorded in DECISIONS 2026-05-22. |
| **2026 multi-country mega-flow anomaly** | $4.18B in multi-country flows in early 2026 — roughly as much as 2020–2025 combined. Likely un-disaggregated regional mega-allocations. | Open item: `pending_attribution` allocation method, hold out of `gap_ratio` until disaggregated. |
| **ACLED is two sources, two tables** | Event-level (point coordinates, API, embargoed ≥12 months) and severity (admin2×month, HDX, current). | Two Bronze tables (`bronze_acled_events`, `bronze_acled_severity`), one Silver each. |
| **GTM/HND/PHL null ISO3 in ACLED severity** | Source ACLED HDX export left `iso3` blank for Guatemala, Honduras, Philippines. | Loader carries `priority_iso3` as the reliable alpha-3 join key. |
| **fieldmaps boundaries are admin2-grain** | 43,064 admin2-level rows; admin0/1 identifiers denormalized on each row. | `silver_boundaries` aggregates up to admin0/1 as needed. P-code conformance with HNO is an open verification item. |
| **HDX Signals overlaps our inputs** | Signals' inputs are ACLED, IPC, IDMC, ACAPS INFORM Severity, JRC, WFP — i.e., our own inputs. | Cited as a methodology integration point; not wired into `overlooked_score`. Optional surfacing in Crisis Explorer narrative panel. |
| **Three INFORM files are byte-identical dupes** | `_1`-suffix variants for Sep 2025, Feb 2026, Mar 2026. Other apparent dupes (`..._20261.xlsx`, `mid-december-2025`) are distinct re-releases. | Bronze dedupe by sha256, not filename. Open item. |

---

# Per-source catalog

## bronze_hno

**Source files (CMU drop):**
- `hpc_hno_2024.csv` — schema with HXL row + admin1/2/3 + demographic Category fan-out.
- `hpc_hno_2025.csv` — same schema family as 2024. Verified 318,260 rows, 16 columns, 23 countries.
- `hpc_hno_2026.csv` — schema drift: 10 columns, 134 rows, 20 countries, no admin columns, no HXL row.

**Volume target:** `/Volumes/geo_insight/raw/staging/hno/`

**Update cadence:** Annual. The 2025 file represents the finalized HNO with subnational disaggregation; the 2026 file is the early-year GHO/preview format released before subnational data is finalized.

**Provenance:** CMU drop / OCHA HPC.

**Join keys to other Bronze sources:** `Country ISO3` ↔ `silver_country_dim.iso3`; `Admin 1/2/3 PCode` ↔ fieldmaps `adm{1,2}_id` and COD-PS `ADM{1,2}_PCODE` (conformance is an open verification item).

**Distinct-value inventories — verified 2026-05-22:**

*Cluster codes (HNO 2025, all 318,260 rows, top values):*

| Code | Rows | Meaning |
|---|---|---|
| `PRO` | 44,766 | Protection (overall) |
| `ALL` | 33,169 | All-sectors (country total / aggregate row — not a sector) |
| `FSC` | 30,026 | Food Security and Agriculture |
| `PRO-GBV` | 27,670 | Protection — Gender-Based Violence |
| `WSH` | 26,811 | Water, Sanitation and Hygiene (WASH) |
| `PRO-CPN` | 25,852 | Protection — Child Protection |
| `SHL` | 22,331 | Shelter / Emergency Shelter & NFI |
| `HEA` | 21,441 | Health |
| `NUT` | 19,904 | Nutrition |
| `PRO-MIN` | 15,478 | Protection — Mine Action |
| `EDU` | 14,219 | Education |
| `PRO-HLP` | 13,853 | Protection — Housing, Land and Property |
| `CCM` | 7,685 | Camp Coordination and Camp Management |
| `MPC` | 5,136 | Multipurpose Cash |
| `MS` | 1,846 | Multi-sector |
| `CSS` | 1,252 | Coordination and Support Services |
| `ERY` | 1,233 | Early Recovery |
| `LOG` | 15 | Logistics |
| `TEL` | 2 | Emergency Telecommunications |
| `NaN` | 5,570 | Missing cluster |
| `#sector+cluster+code` | 1 | HXL header row |

HNO 2026 carries the same Cluster code vocabulary, fully populated (no NULL Cluster rows in 2026): `ALL`, `PRO`, `EDU`, `FSC`, `HEA`, `SHL`, `WSH`, `NUT`, `CCM`, `MPC`, `MS`, `PRO-CPN`, `PRO-GBV`, `PRO-MIN`, `PRO-HLP`.

*Category (demographic disaggregation, HNO 2025, top 20):*

`total` (38,125), `Children` (20,938), `Elderly` (17,790), `Female` (15,889), `Male` (12,007), `IDP` (10,927), `Adult` (10,757), `Host Communities` (10,274), `Children - Female` (5,842), `Children - Male` (5,642), `Boys` (5,433), `Girls` (5,432), `Adult - Female` (5,240), `Adults` (4,999), `Women` (4,997), `Adult - Male` (4,638), `Men` (4,563), and country-specific tags like `Returnees from Iran (District of Return 2025) - Total` (4,441 rows for AFG).

For v1 methodology, filter to `Category = 'total'` for the cluster-level country total. Demographic sub-population analysis is a v2 extension.

*Description (HNO 2025, top 10):* `Final HRP caseload` (41,035 — the country total caseload row), `Child Protection` (19,445), `Gender-Based Violence (GBV)` (18,327), `General Protection` (18,289), `Protection (overall)` (17,119), `Food Security and Agriculture` (14,134), `Water, Sanitation and Hygiene` (13,954), `Mine Action` (13,242), `Housing, Land and Property` (11,118), `Education` (9,670). Description has French and Spanish variants in addition to English; the `Cluster` code is the reliable sector identifier, not `Description`.

*Countries in HNO 2025 (23):* AFG, BFA, CAF, CMR, COD, COL, ETH ⚠ (0 rows present), GTM, HND, HTI, MLI, MMR, MOZ, NER, NGA, SDN, SLV, SOM, SSD, SYR, UKR, VEN, YEM.

*Countries in HNO 2026 (20):* AFG, BFA, CAF, CMR, COD, COL, HTI, MLI, MMR, MOZ, NER, NGA, SDN, SOM, SSD, SYR, TCD, UKR, VEN, YEM. ETH absent.

**Known quirks:**
- HXL hashtag row immediately after header in 2024/2025 — keep in Bronze, drop in Silver.
- Numeric columns read as `string` in 2024/2025 (HXL row contamination); cast in Silver with `_quarantine` for parse failures.
- HNO 2026 has clean dtypes (Population: float64, In Need: float64, Targeted: int64).
- HNO 2026 has no admin columns at all — `silver_subnational_needs` must be empty for 2026 with `data_sparsity_flag`.
- Several priority countries have admin2 rows but no admin1 rows; Silver derives admin1 via P-code-prefix rollup.

## bronze_hrp

**Source file (CMU drop):**
- `humanitarianresponseplans.csv` — 911 rows, 10 columns, year range 2000–2026.

**Volume target:** `/Volumes/geo_insight/raw/staging/hrp/`

**Update cadence:** Annual on the OCHA HPC release calendar; mid-year revisions show up as new `planVersion` strings.

**Provenance:** CMU drop / OCHA HPC.

**Join keys:** `code` ↔ `bronze_fts_plan.code`, `bronze_fts_flows.destPlanCode`. HRP↔FTS code overlap is 882 / 887 FTS / 900 HRP — 99% clean. The 5 FTS-only codes are 2025–2026 plans not yet added to the HRP metadata table (FTS updates faster than the plans index).

**Distinct-value inventories — verified 2026-05-22:**

*`categories` field (top 20, illustrating dual-format issue):*

| Value | Rows |
|---|---|
| `Consolidated appeals process` | 151 |
| `cluster \| en \| Humanitarian response plan` | 76 |
| `Consolidated inter-agency appeal` | 72 |
| `sector \| en \| Regional response plan` | 69 |
| `Flash appeal` | 67 |
| `Other` | 52 |
| `sector \| en \| Other` | 43 |
| `cluster \| fr \| Humanitarian response plan` | 34 |
| `Regional response plan` | 33 |
| `sector \| en \| Flash appeal` | 30 |
| `cluster \| en \| Flash appeal` | 25 |
| `Humanitarian needs and response plan \| cluster \| en` | 25 |
| `sector \| en \| Humanitarian response plan` | 19 |
| `cluster \| es \| Humanitarian response plan` | 17 |
| `sector \| fr \| Humanitarian response plan` | 17 |

**Mixed format**: some rows have clean type names (`Flash appeal`, `Regional response plan`, `Consolidated appeals process`); some have pipe-laden HXL fragments (`cluster | en | Humanitarian response plan`) leaked from the source's column headers. Silver needs to parse the language code (`en`/`fr`/`es`) out and recover the core plan type.

**Known quirks:**
- **HXL row** at row 0: `#date+year+list`, `#country+code+list`, `#response+code`. `skiprows=[0]` or HXL-aware loader required.
- `locations` field uses **pipe with spaces** as delimiter (` | `) — different from FTS comma convention.
- Multi-country plans: 33 plans have >1 country in `locations`. Examples: `RREG26` covers `BFA | MLI | NER | TCD | MRT`; `RYEM26` covers `YEM | KEN | DJI | SOM | ETH | TZA` (a regional refugee response plan keyed to Yemen).

## bronze_fts_plan

**Source file (CMU drop):**
- `fts_requirements_funding_global.csv` — 3,836 rows, 12 columns, year range 1999–2031.

**Volume target:** `/Volumes/geo_insight/raw/staging/fts/`

**Update cadence:** FTS publishes daily. The file here is a point-in-time export — refresh by re-downloading from `fts.unocha.org`.

**Provenance:** CMU drop / OCHA FTS.

**Join keys:** `code` ↔ `bronze_hrp.code`; `countryCode` ↔ `silver_country_dim.iso3`.

**Distinct-value inventories — verified 2026-05-22:**

*`typeName` distribution (full file, by year, for the methodology window 2020–2026):*

| Year | Humanitarian response plan | Humanitarian needs and response plan | Flash appeal | Regional response plan | Other |
|---|---|---|---|---|---|
| 2020 | 24 | — | 5 | 28 | 4 |
| 2021 | 24 | — | 3 | 22 | 4 |
| 2022 | 23 | — | 5 | 26 | 18 |
| 2023 | 20 | — | 5 | 26 | 31 |
| 2024 | 9 | 6 | 4 | 25 | 13 |
| 2025 | — | 26 | 4 | 22 | 13 |
| 2026 | — | 22 | — | 13 | 11 |

The 2024 HRP → HNRP rename is visible in the cross-tab: 2024 is mixed (9 HRP + 6 HNRP); 2025 is fully HNRP. Silver unifies both into a single `country_response_plan` category.

Full year-aggregated counts: `Regional response plan` 457, `Humanitarian response plan` 220, `Consolidated appeals process` 152, `Flash appeal` 133, `Other` 126, `Humanitarian needs and response plan` 54, `Refugee response plan` 30, `Pooled fund` 8, `Strategic response plan` 3.

**Known quirks:**
- **Future-dated rows** (2027–2031): mostly multi-year regional plan usage windows (RHO regional rolling plans). Filter to `year <= current_year` in Silver.
- **"Not specified" / country-aggregate rows**: 2,577 of 3,836 rows (67%) have NULL `code`, NULL `id`, `name='Not specified'`. These are off-plan funding aggregated to country. v1 carries them as a separate Silver grain (`plan_code IS NULL`), attributed directly to the country. Preserves signal for no-HRP countries (e.g., ETH 2026 has $256M in this bucket and no HRP).
- `requirements` and `percentFunded` are ~31% non-null (only plan-level rows have them); `funding` is 99% populated. Don't recompute `percentFunded`; use the FTS-published value.

## bronze_fts_cluster

**Source files (CMU drop, two files loaded into one Bronze table tagged by `_source_file`):**
- `fts_requirements_funding_cluster_global.csv` — 8,030 rows, 12 columns. Raw country-cluster taxonomy, 962 distinct cluster name variants.
- `fts_requirements_funding_globalcluster_global.csv` — 10,635 rows, 12 columns. Normalized IASC global cluster rollup, 24 distinct cluster names.

**Volume target:** `/Volumes/geo_insight/raw/staging/fts/`

**Update cadence:** Daily on `fts.unocha.org`.

**Provenance:** CMU drop / OCHA FTS.

**Join keys:** `countryCode` × `code` × `year` ↔ `bronze_fts_plan` (plan identity); `cluster` is the sector tag, normalized in the globalcluster variant.

**Distinct-value inventories — verified 2026-05-22:**

*`fts_requirements_funding_globalcluster_global.csv` — the canonical normalized IASC names (24 distinct):*

| Cluster | Rows |
|---|---|
| `Not specified` | 815 |
| `Multiple clusters/sectors (shared)` | 815 |
| `Health` | 805 |
| `Water Sanitation Hygiene` | 786 |
| `Food Security` | 783 |
| `Education` | 739 |
| `Coordination and support services` | 721 |
| `Protection` | 716 |
| `Emergency Shelter and NFI` | 615 |
| `Agriculture` | 526 |
| `Multi-sector` | 518 |
| `Early Recovery` | 497 |
| `Nutrition` | 372 |
| `Logistics` | 326 |
| `Protection - Child Protection` | 304 |
| `Protection - Mine Action` | 286 |
| `Protection - Gender-Based Violence` | 281 |
| `Camp Coordination / Management` | 228 |
| `Other` | 133 |
| `Emergency Telecommunications` | 133 |
| `Multipurpose Cash` | 102 |
| `Protection - Housing, Land and Property` | 90 |
| `COVID-19` | 29 |
| `Protection - Human Trafficking & Smuggling` | 15 |

*`fts_requirements_funding_cluster_global.csv` — top of the 962-variant raw taxonomy:*

`Not specified` (815), `Multiple clusters/sectors (shared)` (815), `Protection` (337), `Education` (331), `Nutrition` (302), `Health` (264), `HEALTH` (164 — case variant), `WASH` (159), `EDUCATION` (152 — case variant), `NUTRITION` (146 — case variant), `PROTECTION` (139 — case variant), `Food Security` (125), `Logistics` (125), `Coordination` (114), `Water, Sanitation and Hygiene` (91), `FOOD SECURITY` (85), `COORDINATION AND SUPPORT SERVICES` (76), `EARLY RECOVERY` (73), `Santé` (72 — French), `LOGISTICS` (64), `WATER, SANITATION AND HYGIENE` (64), `WATER AND SANITATION` (56), `Coordination and Support Services` (51), `Camp Coordination and Camp Management` (51), `Coordination and Common Services` (50), `Food Security and Livelihoods` (50), `COORDINATION` (48), `Refugee Response` (45), `Early Recovery` (44).

Across the 962 distinct variants you'll see mixed case (`HEALTH` vs `Health`), language variants (`Santé`, `Sécurité alimentaire`, `Salud`), and historical taxonomy drift (`Coordination and Common Services` vs `Coordination and Support Services`). Silver uses the globalcluster taxonomy for cross-country sector comparison; the raw cluster file is preserved for in-country fidelity and the optional sector-imbalance audit.

**Known quirks:**
- `Not specified` and `Multiple clusters/sectors (shared)` together account for ~20% of rows in both files — sector-level analog of multi-country flows. Preserve with provenance for the methodology's transparency layer.
- `clusterCode` is ~79–84% non-null; the rest are name-only.

## bronze_fts_flows

**Source files (CMU drop, three files share one schema, distinguished by `boundary`):**
- `fts_incoming_funding_global.csv` — 9,255 rows, $14.24B 2020–2026. `boundary='incoming'`.
- `fts_outgoing_funding_global.csv` — 4,080 rows.
- `fts_internal_funding_global.csv` — 1,378 rows, 2024–2026 only.

**Volume target:** `/Volumes/geo_insight/raw/staging/fts/`

**Update cadence:** Daily on `fts.unocha.org`.

**Provenance:** CMU drop / OCHA FTS.

**Join keys:** `id` is PK (add `boundary` for safety across files); `destPlan` / `destPlanCode` ↔ `bronze_hrp.code`; `srcLocations` / `destLocations` ↔ `silver_country_dim.iso3` (after comma-split for multi-country flows).

**Distinct-value inventories — verified 2026-05-22 on the incoming file:**

| Field | Distribution |
|---|---|
| `status` | `commitment` 5,477, `paid` 3,602, `pledge` 176 |
| `flowType` (top) | `Standard` 8,712, `Carry-over (incoming)` 525, others tiny |
| `contributionType` (top) | `financial` 9,231, `in-kind` 23, `cash` 1 |
| `srcOrganizationTypes` (top 10) | `Governments` 5,073, `UN agencies, funds and other entities` 1,521, `Pooled Funds` 920, `Private (individuals & organizations)` 503, `International NGOs` 459, `European Commission` 305, `Other multilateral organisations` 230, `International Movement of the Red Cross and Red Crescent` 122, `Inter-governmental organisations` 75, `Pooled funds` 13 (note duplicate-case row) |
| `boundary` | `incoming` 9,255 (this file) — full file. The other two files carry `outgoing` and `internal`. |
| `onBoundary` | `single` 8,724, `shared` 531 — the `shared` rows are the **double-count risk** (one flow that appears as both incoming and outgoing in the dataset). Silver dedupes on `id` + `onBoundary='shared'`. |

**Multi-country flow distribution (`destLocations`, all years, incoming):**
- 8,727 single-country flows (94.3% of rows; **68.5% of dollars = $9.76B**)
- 528 multi-country flows (5.7% of rows; **31.5% of dollars = $4.48B**)
- 99.1% of multi-country flows carry no `destPlan` — only 5 of 528 have a plan attached.

2026 alone accounts for $4.18B of multi-country flows — roughly as much as 2020–2025 combined ($299M). Open item: hold these out as `pending_attribution` until disaggregated.

**Known quirks:**
- `destLocations` uses **comma** as multi-country delimiter (`ABW,ARG,BOL,BRA,CHL,COL,CRI,...`).
- `srcLocations` uses the same comma convention but is single-country in 99% of flows.
- `destPlan` is 53–94% null (varies by year); single-country flows usually have it, multi-country flows almost never.
- `pledge`-status rows should not count in `gap_ratio` numerator (non-binding); paid + committed only.

## bronze_inform_severity

**Source files (CMU drop):** ~89 unique `*inform-severity*.xlsx` / `*gcsi*.xlsx` files, monthly Jan 2019 → April 2026.

**Volume target:** `/Volumes/geo_insight/raw/staging/inform_severity/`

**Update cadence:** Monthly, with occasional mid-month re-releases for fast-moving crises. Two files in late 2025 are explicitly `mid-november-2025` / `mid-december-2025` releases.

**Provenance:** ACAPS via the OCHA-shared CMU drop.

**Join keys:** `iso3` ↔ `silver_country_dim.iso3`; `crisis_id` (e.g., `AFG001`) is the within-source PK.

**Sheet structure — verified 2026-05-22:**

Each file is a 21-sheet analytical workbook. The two sheets the Bronze loader reads:
- `INFORM Severity - country` — ≈85 rows, one per country-level crisis.
- `INFORM Severity - all crises` — ≈130 rows, includes sub-country / multiple crises per country.

**Sheet-name dispatch** (per DECISIONS 2026-05-22): 20 of 89 files (Jan 2019 – Aug 2020) use sheet name `GCSI` instead of `INFORM Severity - country`. Loader tries `INFORM Severity - country` first, falls back to `GCSI`. Same downstream schema.

**Header convention:** Row 1 = formula/title, row 2 = column names, row 3 = `Weights` marker row (drop in Silver, keep in Bronze for audit), data starts row 4. Read with `header=1` and filter the data row whose first column equals `Weights`.

**Distinct-value inventories — verified 2026-05-22 on the April 2026 file:**

- **Country coverage trajectory:** 2019 (GCSI era) 65–78 countries · 2020 transition 67–80 · 2021–2022 70–86 · 2023 83–93 · 2024 91–95 (peak) · 2025 80–91 (declining) · 2026 (through April) 68–82. Some countries drop in/out across months as ACAPS adds or retires crisis monitoring; this affects `chronic_index` computation for countries with intermittent coverage.
- **`inform_severity_index`** is float on a 1–10 continuous scale.
- **`inform_severity_category`** is integer 1–5; **this is the column the methodology severity gate (`≥4`) and chronic check (`≥3`) refer to**, not the 1–10 index.
- **`inform_severity_category_label`** parallels the int: `Very Low`, `Low`, `Medium`, `High`, `Very High`.
- **`trend_3m`**: `Decreasing` / `Stable` / `Increasing`.
- **`reliability`**: `Very Low` … `Very High` — quality of the source data; flag low-reliability rows in Silver.
- **Dimension sub-scores** (1–10 each): `impact`, `geographical`, `human`, `conditions`, `complexity`.

**Known quirks:**
- Three byte-identical `_1`-suffix duplicates: Sep 2025, Feb 2026, Mar 2026. Open item: dedupe by sha256, not filename.
- `mid-november-2025.xlsx` and `mid-december-2025.xlsx` are distinct from the end-of-month files for those months — not duplicates.
- One misnamed file: `20190304gcsidatabasebetaversionfebruary2020.xlsx` — date prefix is wrong; the `About` sheet inside has the canonical release date.
- The `Trends` sheet inside each workbook is a monthly severity time series 2019→present — a ready-made input for `chronic_index` without re-stitching snapshots. Bonus loader, not v1-critical, captured in `open-questions.md`.

## bronze_cod_population

**Source files (CMU drop + acquired supplemental):**
- `cod_population_admin0.csv` — 6,722 rows, 139 countries (CMU drop).
- `cod_population_admin1.csv` — 91,471 rows, 123 countries (CMU drop).
- `cod_population_admin4.csv` — 17,465 rows, **only 1 country** (CMU drop; effectively unusable globally).
- `cod_population_admin2.csv` — 142 MB, acquired from HDX `cod-ps-global` (see `acquisition_supplemental_cod.md`).
- `cod_population_admin3.csv` — 37 MB, acquired from same source.

**Volume target:** `/Volumes/geo_insight/raw/staging/cod_population/`

**Update cadence:** Annual, on the COD-PS release schedule. Reference year varies per country.

**Provenance:** UN OCHA Common Operational Datasets — Population Statistics (`cod-ps-global`). admin0/1/4 from the CMU drop; admin2/admin3 acquired separately.

**Join keys:** `ISO3` ↔ `silver_country_dim.iso3`; `ADM1_PCODE`, `ADM2_PCODE` ↔ HNO `Admin N PCode` and fieldmaps `adm{1,2}_id` (P-code conformance is an open verification item).

**Distinct-value inventories — verified 2026-05-22:**

- **Reference_year distribution (admin0):** ranges 2001 (1 country — VEN) through 2025 (49 countries), with the bulk in 2023 (52 countries) and 2024 (29 countries). One country at ref year 2001 is **VEN** — 15 years stale, surfaces a `stale_population_flag` (open item).
- **Stale countries (`Reference_year < 2020`):**

| ISO3 | Country | Ref year |
|---|---|---|
| `VEN` | Venezuela | 2011 |
| `MNE` | Montenegro | 2011 |
| `BIH` | Bosnia and Herzegovina | 2013 |
| `BRA` | Brazil | 2010 |
| `LBN` | Lebanon | 2017 |
| (Others see file for full list — about 8 countries with stale denominators.) | | |

- **Total-population row identifier:** `Population_group='T_TL'` AND `Gender='all'` AND `Age_range='all'`. That single row per admin unit is what `severity_rate` and population-weighted allocation use. 139 admin0 T_TL rows; 1,882 admin1 T_TL rows.

**Known quirks:**
- `admin4` has only one country (verified 17,465 rows for one ISO3, ref year 2018). Globally unusable. Drop or ignore.
- Per `acquisition_supplemental_cod.md`, YEM, MMR, NGA have **zero admin2 population coverage** in `cod-ps-global` — fall back to admin1 with `data_sparsity_flag`.

## bronze_cbpf_allocations

**Source files (CMU drop):**
- `Allocations__*.csv` — **nine files, one per year 2018–2026.** Schema is consistent across files: `Year, PooledFund, AllocationType, Budget`. Combined: 697 rows after dedupe (23 exact duplicates dropped).

**Volume target:** `/Volumes/geo_insight/raw/staging/cbpf/`

**Update cadence:** Annual cycle; per-fund allocations published as they occur during the year.

**Provenance:** CMU drop / OCHA Country-Based Pooled Funds. **Note: despite the file naming, this is CBPF data, not CERF.** CERF allocations are in `bronze_cerf_allocations`.

**Join keys:** `PooledFund` ↔ `silver_fund_country_map.fund_name` (hand-built map → ISO3). `_source_file` carries the year.

**Distinct-value inventories — verified 2026-05-22:**

*`PooledFund` (34 distinct values):*

`Afghanistan`, `Burkina Faso`, `Burkina Faso (RhPF-WCA)`, `Cameroon`, `Cameroon (RhPF-WCA)`, `Central African Republic`, `Chad`, `Colombia (AP-RHPF)`, `Democratic Republic of the Congo`, `Ethiopia`, `Fiji (AP-RHPF)`, `Haiti`, `Haiti (RhPF-LAC)`, `Iraq`, `Jordan`, `Lebanon`, `Mali`, `Mali (RhPF-WCA)`, `Myanmar`, `Niger`, `Niger (RhPF-WCA)`, `Nigeria`, `Occupied Palestinian Territory`, `Pakistan (AP-RHPF)`, `Papua New Guinea (AP-RHPF)`, `Philippines (AP-RHPF)`, `Regional Humanitarian Pooled Fund - South & Central America`, `Somalia`, `South Sudan`, `Sudan`, `Sudan (ESAHF)`, `Syrian Arab Republic`, `Türkiye`, `Ukraine`, `Vanuatu (AP-RHPF)`, `Yemen`.

The regional-fund suffixes are:
- `(RhPF-WCA)` — Regional Humanitarian Pooled Fund — West & Central Africa
- `(RhPF-LAC)` — Regional Humanitarian Pooled Fund — Latin America & Caribbean
- `(AP-RHPF)` — Asia-Pacific Regional Humanitarian Pooled Fund
- `(ESAHF)` — Eastern & Southern Africa Humanitarian Fund

The `silver_fund_country_map` reference table maps each fund name → primary country ISO3 (or `regional=true` flag for the four pure-regional funds).

*`AllocationType` (2 values):* `reserve` (487 rows), `standard` (210 rows). These are CBPF's two allocation windows (rapid/emergent vs scheduled), not sector tags. CBPF has no sector field at the allocation level.

*Year range:* 2018–2026.

**Known quirks:**
- One file per year; concatenate at Bronze; dedupe 23 exact duplicates.
- No sector tagging on allocations — this fund/year/window aggregate has no sector field. The sector decomposition for CBPF now lives in the sibling `bronze_cbpf_projects` (project × cluster grain, acquired 2026-05-22), which reconciles to this table at year-total level (±2.8%/0.3%/−7.9% for 2024/2025/2026) and feeds `gold_sector_coverage`. The two join on (`year`, `fund_id`/normalized fund, `allocation_window`).

## bronze_cbpf_contributions

**Source files (CMU drop):**
- `Contributions__*.csv` — **nine files, one per year 2018–2026.** Schema is consistent across files: `Year, Donor, Donor type, Paid, Pledged, Total`. Combined: 2,132 rows raw, 1,843 unique on `(Year, Donor)` — 289 within-file duplicates (likely pledge revisions or multi-installment payments).

**Volume target:** `/Volumes/geo_insight/raw/staging/cbpf/`

**Update cadence:** Annual cycle.

**Provenance:** CMU drop / OCHA CBPF.

**Join keys:** `Donor` ↔ donor name in `bronze_fts_flows.srcOrganization` (after fuzzy normalization). `_source_file` carries the year.

**Critical caveat — verified 2026-05-22:** This file has **no fund column and no country column.** It is global CBPF contributions by donor per year, not attributable to a specific fund or crisis. **`gold_donor_concentration` is computed from `silver_fts_flows.donor_org`, not from this file** (DECISIONS 2026-05-22). This Bronze table exists to support the optional CBPF Allocation View (PFM-primary screen), not the main ranking pipeline.

**Distinct-value inventories — verified 2026-05-22:**

*`Donor type` (4 distinct):* `Member State` (1,927), `Private Sector` (148), `Private Contributions through UNF` (51), `Member State (Other)` (6).

*Top 10 donors in 2026 by `Total`:*

| Donor | Total USD |
|---|---|
| `United States of America (United States of America Government)` | $150,000,000 |
| `Belgium (Government of Belgium)` | $10,000,000 |
| `Germany (Federal Government of Germany)` | $8,000,000 |
| `Finland (Government of Finland)` | $5,000,000 |
| (Other top-tier government donors: Denmark, United Arab Emirates, United Kingdom, Ireland.) | |

*Year range:* 2018–2026.

**Known quirks:**
- 289 within-file duplicates on `(Year, Donor)`: Silver aggregation rule sums `Paid`/`Pledged`/`Total` over the key, retains a `n_records` count for transparency.

## bronze_cbpf_projects

**Source file (staging):** `staging/cbpf_projects.csv` — 8.2 MB, 24,219 rows (project × cluster), 2010–2026, all 34 funds covered. 100% cluster-tagged, 100% valid iso3, 100% ProjectSummary-enriched. See `docs/notes/acquisition_cbpf_projects.md`.

**Volume target:** `/Volumes/geo_insight/raw/staging/cbpf/cbpf_projects.csv`

**Update cadence:** Monthly (OData API `data_update_frequency: 30`).

**Provenance:** OCHA CBPF Business Intelligence OData API (`cbpfapi.unocha.org/vo1/odata/`, entity `Cluster`/`ExcelClusterBase`, joined to `Poolfund` and `ProjectSummary`), discovered via the HDX dataset `cbpf-allocations-and-contributions`. License CC BY (IGO). No auth. Acquired via `src/acquisition/acquire_cbpf_projects.py`.

**Join keys:** `iso3` ↔ `silver_country_dim.iso3`; `cluster` ↔ `silver_sector_crosswalk.cbpf_category`; `fund_id` / `fund_name` ↔ `silver_fund_country_map`. **Join on `fund_id` (= `Poolfund.Id`), not the name** — names are ambiguous (`Colombia` Id 52 vs `Colombia (RhPF)` Id 87 are distinct funds that normalize to the same base; likewise Haiti 54/88, Pakistan 60/97).

**Distinct-value inventories — verified per acquisition note:**

*Cluster values (15 distinct, all IASC-recognizable):* `Water, Sanitation and Hygiene`, `Protection`, `Health`, `Food Security`, `Emergency Shelter and NFI`, `Nutrition`, `Education`, `Camp Coordination / Management`, `Early Recovery`, `Coordination and Support Services`, `Logistics`, `COVID-19` (48 rows; reassign to Health post-2023 per crosswalk), `Emergency Telecommunications`, `Multi-purpose CASH`, `Multi-Sector`. 13 map cleanly to existing crosswalk rows; `Multi-purpose CASH` and `Multi-Sector` were added as crosswalk variant strings (casing).

*Per-year row counts:* 2010: 36 · 2011: 227 · 2012: 172 · 2013: 212 · 2014: 819 · 2015: 1,175 · 2016: 1,538 · 2017: 1,664 · 2018: 1,800 · 2019: 2,110 · 2020: 1,903 · 2021: 2,184 · 2022: 2,385 · 2023: 2,176 · 2024: 2,247 · 2025: 2,727 · 2026: 844 (partial year).

*`allocation_window`:* `standard` (15,115) / `reserve` (9,104).

*Reconciliation vs `bronze_cbpf_allocations` (year totals):* 2024 +2.8% · 2025 +0.3% · 2026 −7.9%. All within ±15%; the 2026 shortfall is in-year project-entry lag in GMS (allocation announced vs project approved-and-entered), not a data gap.

**Known quirks:**
- Two `iso3` overrides applied at acquisition: Mozambique RhPF source `LI` (Liechtenstein) → `MOZ`; Syria Cross border source `XX` → `SYR`. This makes two funds share `iso3=SYR` (`Syria` Id 62 + `Syria Cross border` Id 70) — distinct at fund grain, combined only at iso3 grain.
- `sub_cluster` only 6.2% populated; not profiled against the crosswalk's Protection sub-cluster rows (`PRO-*`) — deferred to v2.
- CBPF `Multi-purpose CASH` / `Multi-Sector` are casing variants of the harmonized Multipurpose Cash / Multi-sector buckets; both added to `silver_sector_crosswalk.fts_cluster_variants`.
- One fund missing vs the 34 bronze funds: `Honduras (RhPF-LAC)` (new 2026 fund, no projects entered yet — re-pull after the monthly GMS refresh catches up).

## bronze_cerf_allocations

**Source file (staging):** `staging/cerf_allocations_raw.csv` — 8,511 rows, 18 columns, 2006–2026. See `docs/notes/acquisition_cerf_ufe.md`.

**Volume target:** `/Volumes/geo_insight/raw/staging/cerf/`

**Update cadence:** Weekly (HDX `data_update_frequency: 7`).

**Provenance:** HDX dataset `cerf-allocations` (CC BY-IGO). Acquisition session 2026-05-21 via `src/acquire_cerf_allocations.py`.

**Join keys:** `countryCode` ↔ `silver_country_dim.iso3` (verified valid ISO3 for all 3,003 UFE rows). `projectID` is within-source PK.

**Distinct-value inventories — partially verified from acquisition note, full inventory pending first Bronze ingest:**

- **`windowFullName`** (the UFE/RR discriminator): `Rapid Response` (5,508 rows), `Underfunded Emergencies` (3,003 rows). No nulls, no third value. **The UFE rows are the labeled ground truth for Layer 1 validation.**
- **`year`** equals `dateUSGSignature` year for every UFE row (0 mismatches across 3,003 rows).
- **`tableName`** field has values `P` (~4,774 rows) and `M` (~3,737 rows) — meaning **undocumented** (open question for Mary Keller).
- **Country names** are long-form (`Republic of the Sudan`, `Syrian Arab Republic`, `Democratic Republic of the Congo`). Always join on `countryCode` / ISO3, never on name.

**Known quirks:**
- No `round` column — UFE rounds derive from `dateUSGSignature`, but USG signature date lags ERC round announcement by 2–6 months. Year-grain is exact; round-grain requires a separate announcement-date lookup. v1 ships year-grain.
- `projectsectors`, `projectclusters`, `projectgroupings`, `projectcapcodes` may carry sector taxonomy info that could enrich the sector crosswalk — not yet profiled.

## bronze_country_borders

**Source file (staging):** `staging/country_borders.csv` — 252 rows (one per country), mean 2.60 land neighbours, 0 unresolved neighbour codes. See `docs/notes/acquisition_geonames_borders.md`.

**Volume target:** `/Volumes/geo_insight/raw/staging/country_borders.csv`

**Update cadence:** ~Quarterly (GeoNames refreshes `countryInfo.txt`); re-acquire when stale or shape changes. Idempotent re-run of the script, no credentials.

**Provenance:** GeoNames `countryInfo.txt` (`download.geonames.org/export/dump/countryInfo.txt`). License **CC-BY** (attribution required; the acquisition script prints it on every run). No auth. Acquired via `src/acquisition/acquire_geonames_borders.py`. **Portable replacement for the deferred Sedona polygon-adjacency path** (serverless compute can't install the Sedona JVM library — see `DECISIONS.md` serverless entry).

**Join keys:** `iso3` ↔ `gold_forgotten_crisis_index.iso3` (and `silver_country_dim.iso3`). `neighbor_iso3_list` is exploded and re-joined to the index on (neighbour `iso3`, `year`) in `gold_cross_border_patterns`.

**Schema (4 columns):**

| Column | Type | Notes |
|---|---|---|
| `iso3` | string | ISO3 alpha-3. PK. |
| `country_name` | string | GeoNames short name. |
| `neighbor_iso3_list` | string | Comma-separated alpha-3 land neighbours; empty for islands / dependent territories. |
| `n_neighbors` | int | Count of neighbours. Mean 2.60; max `RUS`=14. |

**Distinct-value inventories — verified per acquisition note:**

- **252 rows**; not every world ISO3 has a row (GeoNames excludes some very small territories).
- **0 unresolved neighbour codes** — every alpha-2 in every `neighbours` list resolved to alpha-3 via the file's own ISO↔ISO3 map (no `pycountry` needed).
- **87 zero-neighbour countries**, overwhelmingly islands (`NZL`, `AUS`, `JPN`, `MDG`, `LKA`, `FJI`, `ISL`, `CYP`, `PHL`, …); landlocked countries are **not** here (they report land borders).

**Known quirks (surprises):**
- `CUB` (Cuba) is **not** zero-neighbour — it lists `USA` (the Guantánamo Bay land boundary); `USA` correspondingly lists `CAN,MEX,CUB`.
- `GRL` (Greenland) and `FRO` (Faroe Islands) are present with 0 neighbours (dependent territories handled correctly).
- Two non-standard codes ride along: `ANT` (Netherlands Antilles, deprecated post-2010; odd maritime neighbour `GLP`) and `XKX` (Kosovo, user-assigned). Both drop out of any `gold_forgotten_crisis_index` join (which keys on standard ISO3) — harmless, documented.
- Disputed/partially-recognized territories appear as own rows (`ESH` Western Sahara, `PSE` Palestinian Territory, `TWN` Taiwan); adjacency reflects GeoNames' worldview. Acceptable for neighbour-counting in v1.

## bronze_fieldmaps_boundaries

> **🟡 Deferred from v1 (serverless deployment; see `DECISIONS.md`).** The GeoParquet loader and its downstream `silver_boundaries` depend on Apache Sedona, which can't install on serverless compute. Schema preserved below for v2. Replacements in v1: `bronze_country_borders` (adjacency), the `CONTESTED_BORDER_COUNTRIES` list in `notebooks/gold/_common.py` (contested-border sub-signal), and `src/acquisition/extract_geojson.py` (offline GeoJSON for frontend maps).

**Source file (staging):** `staging/fieldmaps_admin_boundaries.geoparquet` — GeoParquet 1.1.0, 43,064 rows, ~2 GB, CRS OGC:CRS84 ≡ EPSG:4326. See `docs/notes/acquisition_fieldmaps.md`.

**Volume target:** `/Volumes/geo_insight/raw/staging/fieldmaps/`

**Update cadence:** Periodic releases from fieldmaps.io. Each polygon row carries `src_date` and `src_update` for per-polygon vintage.

**Provenance:** fieldmaps.io edge-matched global subnational boundaries (CC-BY). Acquired via `src/acquire_fieldmaps.py`.

**Join keys:** `iso_3` ↔ `silver_country_dim.iso3`; `adm0_id` / `adm1_id` / `adm2_id` ↔ HNO `Admin {1,2,3} PCode` and COD-PS `ADM{1,2}_PCODE`. P-code-equality verification across the three sources is an open item.

**Distinct-value inventories — verified per acquisition note:**

- 45 columns, admin2-grain (one polygon per row, with admin0/1 identifiers denormalized).
- `status_cd` / `status_nm` carry disputed-territory metadata that feeds `contested_border_flag`.
- `iso_3_grp` is a grouping ISO3 for disputed-territory handling (e.g., Western Sahara grouping).
- `wld_view` / `wld_notes` carry worldview / disputed-area annotations.
- Distinct value counts for `status_nm`, `wld_view`, and the regional groupings — **pending first Bronze ingest**.

**Known quirks:**
- `geometry` column is WKB-encoded binary; read via Sedona / geoparquet reader.
- The 10 priority countries (per `acquisition_fieldmaps.md`) all have admin1 + admin2 polygons.
- Polygon validity not directly verified (open item in `open-questions.md`); add `ST_IsValid` checks in `silver_boundaries`.

## bronze_acled_events

**Source file (staging):** ACLED v2 API export, per `docs/notes/acquisition_acled.md`. Point-level conflict events for 10 priority countries (per acquisition note). Embargoed to events ≥12 months old by ACLED account tier.

**Volume target:** `/Volumes/geo_insight/raw/staging/acled/`

**Update cadence:** ACLED publishes weekly, but our account tier embargos the most recent ~12 months. Recent-hotspot analysis must use `bronze_acled_severity` instead (current to last month).

**Provenance:** ACLED API v2, acquired via `src/acquire_acled.py` (license terms: ACLED data terms restrict redistribution; not committed to repo).

**Join keys:** `iso` is **ISO numeric** (e.g., 729 = SDN) — `silver_country_dim.iso_numeric` bridges to ISO3 alpha. `priority_iso3` is added at acquisition for reliable alpha-3 join.

**Distinct-value inventories — from acquisition note, verified at acquisition time:**

- `event_type` (6 distinct): `Battles`, `Explosions/Remote violence`, `Violence against civilians`, `Protests`, `Riots`, `Strategic developments`.
- `geo_precision` (3 distinct): 1=precise coordinates, 2=admin centroid (~42% of rows), 3=region. **Down-weight `geo_precision >= 2` for hotspot detection.**
- `latitude`/`longitude` are 4-decimal native precision with 0 nulls (verified). H3 res-5 indexing happens in Silver.
- `admin1` / `admin2` names are present (no nulls) but **no P-codes from API**. Boundary join must go through `silver_boundaries` (point-in-polygon) or use the admin2 names as fallback.
- `actor1` / `assoc_actor_1` / `actor2` / `assoc_actor_2`: actor identifiers, with `assoc_actor_*` semicolon-delimited multi-value strings.

**Known quirks:**
- 12-month account embargo on the most recent events.
- `iso` is numeric — must bridge through `silver_country_dim.iso_numeric` for alpha-3 joins. `priority_iso3` is the reliable column.

## bronze_acled_severity

**Source file (staging):** `staging/acled_severity_admin2_month_2020_present.parquet` — 942,126 rows, 25 countries, 2020-01 → 2026-05 (current to last month). HDX-aggregated XLSX→parquet. See `docs/notes/acquisition_acled.md`.

**Volume target:** `/Volumes/geo_insight/raw/staging/acled/`

**Update cadence:** Monthly on HDX (CC BY-IGO).

**Provenance:** ACLED via HDX. Acquired in the same session as `bronze_acled_events` to provide a current-coverage counterpart.

**Join keys:** `priority_iso3` (added at acquisition) ↔ `silver_country_dim.iso3` (reliable alpha-3 column). `admin1_pcode` / `admin2_pcode` ↔ `silver_boundaries.adm{1,2}_id` and HNO `Admin N PCode`.

**Distinct-value inventories — from acquisition note:**

- `event_category` (3 distinct): `political_violence`, `civilian_targeting`, `demonstration`. **`civilian_targeting` overlaps political violence** — do not sum all three categories (sum would double-count).
- `month_start` runs 2020-01 → 2026-05 across the file. Includes explicit zero-event rows (~64% of total rows), which is how the source preserves the admin2 × month grid even where no events occurred.
- `admin1_pcode` / `admin2_pcode`: **P-codes are present** (the value-add over the events path). Join cleanly to boundaries.

**Known quirks:**
- **Source ISO3 NULL for GTM/HND/PHL** (Guatemala, Honduras, Philippines) — the HDX export left `iso3` blank. The loader carries `priority_iso3` as the reliable join key.
- COL has no `demonstration` rows (source file corrupted in that slice).
- ~64% of rows are zero-event padding for the admin2-month grid; analytical queries should filter these or treat them as zero-fills.

## bronze_echo_fca

**Source file (staging):** `staging/echo_fca_lists.csv` — 197 rows, 2015–2026. See `docs/notes/acquisition_echo_fca.md`.

**Volume target:** `/Volumes/geo_insight/raw/staging/echo/`

**Update cadence:** Annual (ECHO publishes the FCA assessment yearly).

**Provenance:** EU DG ECHO Forgotten Crises Assessment — Layer-2 validation comparator. Public PDF/page extraction.

**Join keys:** `iso3` ↔ `silver_country_dim.iso3` (with ~0.5% nulls on multi-country regional entries).

**Distinct-value inventories — from acquisition note:**

- `year`: 2015–2026 covered (years 2018 and 2025 absent from the source — ECHO did not publish those years).
- `forgotten_category`: always `forgotten` (ECHO publishes a single "forgotten" list, not graded fully/partially/etc.).

**Known quirks:**
- The "forgotten" determination is binary in the source — there's no ECHO-published intensity score on the FCA list.
- ~0.5% of rows have null `iso3` (multi-country regional entries like "Sahel" with no single country code).

## bronze_nrc_neglected

**Source file (staging):** `staging/nrc_most_neglected_lists.csv` — see `docs/notes/acquisition_NRC.md`.

**Volume target:** `/Volumes/geo_insight/raw/staging/nrc/`

**Update cadence:** Annual (NRC publishes the "World's Most Neglected Displacement Crises" report yearly).

**Provenance:** Norwegian Refugee Council research publication. Layer-2 validation comparator (this one *is* ranked, unlike ECHO FCA).

**Join keys:** `iso3` ↔ `silver_country_dim.iso3`. `year` × `rank` is within-source key.

**Distinct-value inventories — from acquisition note:**

- `rank`: integer 1–10 typically (NRC publishes a top-10).
- Distinct year/country list — **pending first Bronze ingest**.

**Known quirks:**
- NRC's three-dimensional methodology (political will, media attention, response capacity) is documented in `docs/prior-art.md`; the rank in this file is the composite outcome.

## bronze_reliefweb_situation_reports

**Source files (staging):** ReliefWeb documents in `staging/reliefweb_docs/` — corpus acquired via `src/acquisition/acquire_reliefweb.py`. **Updated 2026-05-22:** the appname was approved and the v2-API run completed; the corpus is no longer empty. Schemas.md updated 2026-05-22.

**Volume target:** `/Volumes/geo_insight/raw/staging/reliefweb/`

**Update cadence:** ReliefWeb publishes documents continuously; refresh via re-running the acquisition script on a schedule. The current pull is a point-in-time snapshot.

**Provenance:** ReliefWeb API v2 (`api.reliefweb.int/v2/reports`). Requires `RELIEFWEB_APPNAME` registered with ReliefWeb (mandatory since 2025-11-01).

**Join keys:** `iso3` ↔ `silver_country_dim.iso3`; `date` for time bucketing in `media_attention` computation.

**Distinct-value inventories — pending first Bronze ingest** (the corpus was just acquired and hasn't been profiled). Expected fields per acquisition script's output contract:

- `id` (int) — ReliefWeb document ID, within-source PK.
- `title` (string).
- `country` (string, primary) / `iso3` (string).
- `date` (date) — document publication date.
- `source` (string/array, publishing organization).
- `format` (string) — values likely include `Situation Report`, `Analysis`, `Assessment`, `News and Press Release`. Verify on first ingest.
- `language` (string).
- `url` (string) — canonical document URL.
- `body` (string, markdown) — full text, **used only for the Day-4 Knowledge Assistant stretch goal**.
- `body_html` (string).

**Usage:**
- `media_attention_norm` (in `gold_forgotten_crisis_index`) needs only `iso3` + `date` counts — document body text is not needed for the methodology score.
- Body text feeds the optional Knowledge Assistant (Vector Search index, RAG over situation reports).

**Known quirks:**
- ReliefWeb has a per-IP API quota; bulk-pull scripts pace requests.
- `source` field may be a JSON array (multiple co-publishing organizations); Silver flattens to a primary source string.

---

# Cross-source identity

The country identity chain across the 16 Bronze sources, harmonized in `silver_country_dim`:

| Source / column | Type | Notes |
|---|---|---|
| `bronze_hno.Country ISO3` | ISO3 alpha-3 | Canonical |
| `bronze_hrp.locations` (split on ` \| `) | ISO3 alpha-3, multi-country | Regional plans carry multiple ISO3 |
| `bronze_fts_plan.countryCode` | ISO3 alpha-3 | |
| `bronze_fts_cluster.countryCode` | ISO3 alpha-3 | |
| `bronze_fts_flows.srcLocations`, `destLocations` (split on `,`) | ISO3 alpha-3, multi-country | **Comma delimiter** |
| `bronze_inform_severity.iso3` | ISO3 alpha-3 | |
| `bronze_cod_population.ISO3` | ISO3 alpha-3 | |
| `bronze_cbpf_allocations.PooledFund` | Fund name | Maps to ISO3 via `silver_fund_country_map` |
| `bronze_cbpf_contributions.Donor` | Donor org name | No country attribution (see caveat) |
| `bronze_cerf_allocations.countryCode` | ISO3 alpha-3 | |
| `bronze_fieldmaps_boundaries.iso_3` | ISO3 alpha-3 | |
| `bronze_acled_events.iso` | **ISO numeric** | Bridges through `silver_country_dim.iso_numeric` |
| `bronze_acled_events.priority_iso3` | ISO3 alpha-3 | Reliable join key (added at acquisition) |
| `bronze_acled_severity.iso3` | ISO3 alpha-3 | **NULL for GTM/HND/PHL** |
| `bronze_acled_severity.priority_iso3` | ISO3 alpha-3 | Reliable join key (added at acquisition) |
| `bronze_echo_fca.iso3` | ISO3 alpha-3 | ~0.5% null on regional entries |
| `bronze_nrc_neglected.iso3` | ISO3 alpha-3 | |
| `bronze_reliefweb_situation_reports.iso3` | ISO3 alpha-3 | Primary country only |

**Subnational P-code chain (admin1 / admin2):**

| Source / column | Notes |
|---|---|
| `bronze_hno.Admin 1 PCode` / `Admin 2 PCode` | Long-format; admin1 sparse, admin2 ~76% of admin rows in 2024/2025; absent in 2026 |
| `bronze_cod_population.ADM1_PCODE` / `ADM2_PCODE` | One row per admin × demographic group; T_TL rows are total |
| `bronze_fieldmaps_boundaries.adm1_id` / `adm2_id` | P-code-equivalent per fieldmaps documentation; equality with HNO/COD-PS to verify |
| `bronze_acled_severity.admin1_pcode` / `admin2_pcode` | Present (unlike events path); the value-add over events for spatial joins |
| `global_pcodes_raw.csv` (staging) | Authoritative reference for valid P-codes across 109 countries — `silver_country_dim` and `silver_boundaries` build off this |

P-code conformance across HNO, COD-PS, and fieldmaps is an **open verification item** (`docs/open-questions.md`); Silver runs an equality check on the join and flags any mismatch.

---

# HDX Signals — cited, not ingested

**Status:** Acquired to `staging/hdx_signals_*.csv` (current alerts, location metadata, data dictionary). **Not in v1 Bronze.**

**Why no Bronze table:** HDX Signals' inputs are already our inputs (ACLED, IPC, IDMC, ACAPS INFORM Severity, JRC, WFP). Ingesting Signals into the composite score would double-count those signals and muddy validation cleanliness. Per `acquisition_HDX_Signals.md`, the recommendation is to **cite** Signals as the canonical OCHA change-detection product our "acute deterioration" axis aligns with, and **optionally surface** the per-alert `summary_short` + `source_url` + `campaign_date` strip in Crisis Explorer's narrative panel.

**If Signals is later wired in:** the CSV is at `staging/hdx_signals_current.csv` (CC BY-IGO, weekly refresh, plain CKAN download — no auth, no app identifier).

---

# Open items

These surfaced during catalog authoring and belong in `docs/open-questions.md` (most are already there per the 2026-05-22 update):

- **Ethiopia HNO gap** — zero rows in 2025 and absent from 2026 despite being a priority country.
- **VEN 2011 population staleness** — `stale_population_flag` distinct from `data_sparsity_flag`.
- **INFORM Severity content-hash dedupe** — three byte-identical `_1`-suffix dupes; other apparent dupes are distinct re-releases.
- **2026 multi-country mega-flows** — $4.18B parked at regional level; `pending_attribution` allocation method.
- **CBPF Contributions within-file dupes** — 289 of 2,132 rows; Silver aggregation rule needed.
- **CERF `tableName` field meaning** — open question for Mary Keller; doesn't affect v1 since the UFE labels work without it.
- **P-code conformance across HNO / COD-PS / fieldmaps** — verify equality on join in Silver.
- **ReliefWeb corpus first profile** — distinct values for `format` and `source` columns pending first Bronze ingest.
- **fieldmaps polygon validity** — `ST_IsValid` checks per-country; flag invalid polygons before spatial operations.

# Pending distinct-value inventories

Sections marked **pending first Bronze ingest** above. These are not blocking for loader authoring (Bronze preserves rows verbatim), and the inventories can be regenerated as a simple `SELECT col, COUNT(*) FROM bronze_X GROUP BY col` once the workspace permissions land and the loaders run. The catalog will be a small follow-up at that point.

Specifically:
- `bronze_fieldmaps_boundaries`: `status_nm`, `wld_view`, regional grouping distributions.
- `bronze_nrc_neglected`: full year/country/rank distribution.
- `bronze_reliefweb_situation_reports`: `format`, `source`, `language` distributions; corpus size and date range.
- `bronze_cerf_allocations`: `projectsectors`, `projectclusters`, `projectgroupings`, `projectcapcodes` deep profile.
- `bronze_acled_events`: full per-country event counts, actor distributions.

# Provenance

Profiled 2026-05-22 from:
- `/mnt/project/` (the synced CMU drop in project knowledge) — used for the OCHA canonical sources.
- `docs/notes/acquisition_*.md` — used for the staging-only sources (ACLED, ECHO FCA, NRC, HDX Signals, CERF UFE, fieldmaps, supplemental COD, ReliefWeb).

Empirical inventories use pandas + openpyxl + pyarrow with full-file reads (no sampling) for the OCHA canonical sources. Staging-source inventories are reproduced from the acquisition notes; some columns are pending first Bronze ingest as noted.
