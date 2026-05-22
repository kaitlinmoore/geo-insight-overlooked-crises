# Schemas

The canonical reference for Bronze, Silver, and Gold table schemas. Companion to `docs/methodology.md` (the analytical formulas) and `docs/architecture.md` (the agent/system design). Where this file and `methodology.md` describe the same computed column, `methodology.md` governs the formula and this file governs the storage shape.

> **Status legend.** ✅ **profiled** — schema derived from the actual local file (types are real). 🟡 **partial** — some columns profiled, some inferred. 📋 **planned** — data not yet acquired; schema is the intended target and the source is named.
>
> **Profiling provenance.** Bronze types below were profiled on 2026-05-22 from the CMU drop in `data/databricks_data/unocha/` and from `staging/` acquisition outputs, by sampling (≤4,000 rows/file) with pandas + pyarrow + openpyxl. Non-null fractions are from the sample, not the full file. See the per-table notes.

## Conventions

### Namespace

- **Catalog**: `geo_insight`
- **Schemas**: `raw`, `bronze`, `silver`, `gold`
- **Volume**: `geo_insight.raw.staging` (raw uploads land here before Bronze loaders run)

### Lineage / audit columns (every Bronze table)

| Column | Type | Notes |
|---|---|---|
| `_ingested_at` | `timestamp` | `current_timestamp()` at load |
| `_source_file` | `string` | Originating filename — **load-bearing** for several sources (CBPF year, INFORM snapshot month) |

Bronze is append-only and audit-grade: **one row = one source-file row, kept verbatim** (including HXL hashtag rows and demographic-split rows). All cleaning, type-casting, deduplication, and HXL-row removal happen in Silver.

### ISO / join-key conventions

- Country grain keys on **ISO3 alpha-3** everywhere except: **ACLED events** (source `iso` is ISO *numeric*; carry `priority_iso3` alpha-3) and **fieldmaps** (`iso_3`).
- Subnational joins use **UN P-codes**. HNO exposes `Admin N PCode`; fieldmaps exposes `adm{1,2}_id` (P-code-equivalent — see `silver_boundaries` note); COD-PS exposes `ADMn_PCODE`. P-code conformance across these three is an open verification item (`docs/open-questions.md`).

### Scale conventions worth fixing up front

- **INFORM Severity has two scales**: `INFORM Severity Index` (continuous **1–10**) and `INFORM Severity category` (ordinal **1–5**, with a parallel text label Very Low→Very High). The methodology's severity gate ("INFORM Severity ≥ 4") and chronic second-pass ("≥ 3") refer to the **1–5 category**, not the 1–10 index. Both are carried into Silver.
- **FTS `status`** ∈ {`paid`, `commitment`, `pledge`} drives the three-stage funding funnel. `paid` is the headline numerator in `gap_ratio`.
- **All USD** in FTS/CBPF/CERF is current USD as reported; no inflation adjustment in v1.

---

# Bronze

Raw → Delta loaders, one notebook per source under `notebooks/bronze/`. Schemas below omit the two audit columns (`_ingested_at`, `_source_file`) for brevity — they are present on every table.

## bronze_hno  ✅ profiled (🟡 schema drift across years)

People-in-Need / needs figures from the HPC HNO exports.

- **Source**: `hpc_hno_2024.csv`, `hpc_hno_2025.csv`, `hpc_hno_2026.csv`
- **Grain (2024/2025)**: country × admin (0/1/2) × sector(`Cluster`) × demographic `Category` × measure. **Grain (2026)**: country × sector × `Category` (no admin breakdown).
- **PK**: none in raw (long format with repeated keys); Silver derives one.

**⚠️ Two schema realities — handle both:**

| | 2024 & 2025 | 2026 |
|---|---|---|
| Columns | 16 | 10 |
| HXL hashtag row | **Yes** (first data row = `#country+code`, `#inneed`, …) | **No** |
| Admin 1/2/3 PCode+Name | **Yes** (admin2 ~76% populated → subnational present) | **Absent** |
| Value dtypes as read | all `object` (HXL row forces string) | numeric (`int64`/`float64`) |

**Columns (2024/2025 superset):**

| Column | Type (raw) | Nullable | Notes |
|---|---|---|---|
| `Country ISO3` | string | no | ISO3 alpha. First data row holds `#country+code` (HXL) — drop in Silver. |
| `Admin 1 PCode` / `Admin 1 Name` | string | yes (~11%) | UN P-code / name. Sparse: most rows are country- or admin2-level. |
| `Admin 2 PCode` / `Admin 2 Name` | string | yes (~76%) | Subnational PIN where present. |
| `Admin 3 PCode` / `Admin 3 Name` | string | yes (~0%) | Header present, effectively empty. |
| `Description` | string | no | Sector description, e.g. `Education`. Value `Plan caseload` / `Final HRP caseload` / `Final HNRP Caseload` marks the **country total caseload** row. |
| `Cluster` | string | no | Cluster code: `ALL`, `EDU`, `FSC`, `CSS`, … `ALL` = all-sectors total. |
| `Category` | string | yes (~99%) | Demographic split (`Adults`, `Boys`, `Girls`, …). Rows are demographic-disaggregated; the sector/country total is the aggregate `Category`. |
| `Population` | string→int | yes | Baseline population for the unit. Sparse in 2024 (~0.1%), better in 2026 (~15%). |
| `In Need` | string→int | no | **People in Need (PIN)** — the headline `HNO_people_in_need`. |
| `Targeted` | string→int | yes (~95%) | People targeted by the plan. |
| `Affected` / `Reached` / `Info` | string | yes (~0%) | Headers present, near-empty. |

**Bronze rule**: keep all rows verbatim (HXL row included), append `_source_year` derived from `_source_file`. Do **not** cast types here.

## bronze_hrp  ✅ profiled

Plan-level dimension + requirements totals.

- **Source**: `humanitarian-response-plans.csv`
- **Grain**: one row per response plan (× version). **PK**: `code` (+ `internalId`).

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `code` | string | no | Plan code, e.g. `HHTI26`, `RREG26`. Join key to FTS `code`/`destPlanCode`. HXL row = `#response+code`. |
| `internalId` | string→int | no | OCHA HPC plan id. |
| `startDate` / `endDate` | string→date | no | ISO `YYYY-MM-DD`. |
| `planVersion` | string | no | Plan display name (may be French/Spanish), e.g. *Haiti Besoins Humanitaires…2026*. |
| `categories` | string | no | Pipe-delimited type tags, e.g. `Humanitarian needs and response plan \| cluster \| fr`. |
| `locations` | string | yes (~98%) | **Pipe-delimited ISO3 list** — multi-country plans, e.g. `YEM \| KEN \| DJI \| SOM \| ETH \| TZA`. Drives the multi-country allocation cascade. |
| `years` | string | no | Pipe-delimited year list. |
| `origRequirements` | string→int | no | Original requirement USD. |
| `revisedRequirements` | string→int | no | Revised requirement USD — **the `HRP_requirement_usd` denominator**. |

## bronze_fts_plan  ✅ profiled

Plan/appeal-level requirements vs funding by country.

- **Source**: `fts_requirements_funding_global.csv`
- **Grain**: country × plan (× year). **PK**: composite (`countryCode`, `code`, `year`); `code` null for aggregate rows.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `countryCode` | string | no | ISO3. |
| `id` | float→int | yes (~33%) | Plan id; **null on country-aggregate rows** (`name`=`Not specified`). |
| `name` | string | no | Plan name or `Not specified`. |
| `code` | string | yes (~33%) | Plan code (`HAFG26`). Null = country-aggregate row. |
| `typeId` / `typeName` | float / string | yes | Appeal type (`Humanitarian response plan`, `Flash appeal`, …). |
| `startDate` / `endDate` | string→date | yes | Plan window. |
| `year` | int | no | Appeal year. **Quirk**: future years (2027–2029) appear — multi-year usage windows. |
| `requirements` | float | yes (~31%) | Requirement USD. |
| `funding` | float | yes (~99%) | Funding received USD. |
| `percentFunded` | float | yes (~31%) | OCHA-computed % (whole number). |

**Quirk**: rows split between *plan-level* (has `code`) and *country-aggregate* (`code` null, `name='Not specified'`). v1 carries both grains downstream — see `silver_requirements` and the 2026-05-22 DECISIONS entry. The country-aggregate rows are attributed directly to the country (not via cascade) and tagged `plan_code IS NULL` so they don't double-count with plan-level rows.

## bronze_fts_cluster  ✅ profiled

Sector/cluster-level requirements vs funding — the **country-specific cluster** taxonomy (the raw, ~962-variant set of country-defined cluster names). Loaded by `notebooks/bronze/bronze_fts_cluster.py`. The harmonized global-cluster file is a sibling table, `bronze_fts_globalcluster` (below), not folded in here.

- **Source**: `fts_requirements_funding_cluster_global.csv` (country-specific clusters; ~962 distinct cluster names)
- **Grain**: country × plan × cluster × year. **PK**: (`countryCode`, `code`, `clusterCode`, `year`).

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `countryCode` | string | no | ISO3. |
| `id`, `name`, `code` | int/string | no | Plan identity (fully populated here, unlike `bronze_fts_plan`). |
| `startDate`/`endDate`/`year` | date/int | no | Plan window. |
| `clusterCode` | float | yes (~79–84%) | Cluster id. |
| `cluster` | string | no | Cluster name (`Education`, `Health`, …). Feeds the sector crosswalk. |
| `requirements` | float | yes (~76–78%) | Sector requirement USD → `sector_requirement_i`. |
| `funding` | float | yes (~89–92%) | Sector funding USD → `sector_funding_i`. |
| `percentFunded` | float | yes (~67–70%) | OCHA % funded. |

**Note**: the country-cluster file and the global-cluster file differ in taxonomy. Prefer `bronze_fts_globalcluster` (below) for cross-country sector comparison and this `bronze_fts_cluster` table for in-country fidelity. Keep both; Silver chooses per use.

## bronze_fts_globalcluster  ✅ profiled

Sector/cluster-level requirements vs funding — the **harmonized global cluster** (IASC) taxonomy (the normalized ~24-name rollup). Loaded by `notebooks/bronze/bronze_fts_globalcluster.py`. Schema columns are identical to `bronze_fts_cluster`; only the source file and cluster taxonomy differ.

- **Source**: `fts_requirements_funding_globalcluster_global.csv` (harmonized global clusters; ~24 IASC cluster names)
- **Grain**: country × plan × cluster × year. **PK**: (`countryCode`, `code`, `clusterCode`, `year`).

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `countryCode` | string | no | ISO3. |
| `id`, `name`, `code` | int/string | no | Plan identity (fully populated here, unlike `bronze_fts_plan`). |
| `startDate`/`endDate`/`year` | date/int | no | Plan window. |
| `clusterCode` | float | yes (~79–84%) | Cluster id. |
| `cluster` | string | no | Cluster name (`Education`, `Health`, …). Feeds the sector crosswalk. |
| `requirements` | float | yes (~76–78%) | Sector requirement USD → `sector_requirement_i`. |
| `funding` | float | yes (~89–92%) | Sector funding USD → `sector_funding_i`. |
| `percentFunded` | float | yes (~67–70%) | OCHA % funded. |

**Note**: preferred input for cross-country sector decomposition (`gold_sector_coverage`) because the 24-name IASC taxonomy is comparable across countries, unlike the ~962-variant `bronze_fts_cluster`.

## bronze_fts_flows  ✅ profiled

Flow-level funding records — the richest FTS table (37 columns). **Three source files share one schema**, distinguished by `boundary`.

- **Source**: `fts_incoming_funding_global.csv` (`boundary=incoming`), `fts_outgoing_funding_global.csv` (`outgoing`), `fts_internal_funding_global.csv` (`internal`)
- **Grain**: one funding flow. **PK**: `id` (+ `boundary` to be safe across files).

Selected columns (all 37 retained in Bronze):

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | int | no | Flow id. |
| `date` | string→date | no | Flow date. |
| `budgetYear` | float | yes (~92–99%) | Budget year. |
| `amountUSD` | int | no | Flow amount, USD. |
| `description` | string | no | Free text (internal file embeds project/emergency metadata in description). |
| `srcOrganization` / `srcOrganizationTypes` | string | no | Donor + type (`Governments`, `Pooled Funds`, …) → feeds `gold_donor_concentration`. |
| `srcLocations` | string | yes | Source country ISO3(s). |
| `destPlan` / `destPlanCode` / `destPlanId` | string/string/float | yes (~53–94%) | Destination plan → join to `bronze_hrp`. |
| `destOrganization` / `destOrganizationTypes` | string | yes (~99%) | Recipient + type. |
| `destGlobalClusters` | string | yes (~79–85%) | Destination cluster(s). |
| `destLocations` | string | yes | **Comma-delimited destination ISO3 list** (e.g. `AFG,AGO,BDI,…`) → **drives multi-country allocation cascade**. |
| `contributionType` | string | no | `financial` / `in kind`. |
| `flowType` | string | no | `Standard` / `Parked` / `Pass through`. |
| `boundary` | string | no | `incoming` / `outgoing` / `internal` (the file discriminator). |
| `onBoundary` | string | no | `single` / `shared`. **⚠️ `shared` flows risk double-counting** across boundaries — Silver dedupes (see `silver_fts_flows`). |
| `status` | string | no | `paid` / `commitment` / `pledge` → funnel stages. |
| `firstReportedDate` / `decisionDate` | string→date | yes | Reporting dates. |
| `keywords` | string | yes (~12–16%) | Comma-ish tags (`Multiyear`, `Earthquake`, …). |
| `originalAmount` / `originalCurrency` / `exchangeRate` | float/string/float | yes | Pre-USD amount + FX. |
| `refCode` | string | yes (~95%) | External reference (CBPF flows carry `CBPF-…` codes). |
| `createdAt` / `updatedAt` | string→date | no | Record audit dates. |

## bronze_cbpf_allocations  ✅ profiled

CBPF outflows (allocations to projects), pre-aggregated by fund.

- **Source**: `Allocations__*.csv` — **9 files = 9 years (2018–2026), one file per year.** `_source_file` is not load-bearing here (each file carries `Year`), but retain it.
- **Grain**: year × pooled fund × allocation type. **PK**: (`Year`, `PooledFund`, `AllocationType`).

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `Year` | int | no | 2018–2026. |
| `PooledFund` | string | no | Fund name — **mostly a country** (`Afghanistan`, `Sudan`) but some regional (`Fiji (AP-Rhpf)`, `Pakistan (AP-RHPF)`). Needs fund→ISO3 mapping in Silver. 17–25 funds/year. |
| `AllocationType` | string | no | `standard` / `reserve`. |
| `Budget` | int | no | Allocation amount, USD. |

## bronze_cbpf_contributions  ✅ profiled

CBPF inflows (donor contributions into the pooled-fund system).

- **Source**: `Contributions__*.csv` — **9 files = 9 years (2018–2026).**
- **Grain**: year × donor. **PK**: (`Year`, `Donor`).
- **⚠️ No fund/country column** — these are **global** CBPF contributions by donor per year, not attributable to a specific fund or crisis. Use for global pooled-fund context, **not** for country-level `donor_concentration` (which comes from `bronze_fts_flows.srcOrganization`).

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `Year` | int | no | 2018–2026. |
| `Donor` | string | no | Contributor (`Australia`, …). |
| `Donor type` | string | no | `Member State` / `Private` / `Private Contributions through UNF`. |
| `Paid` | int | no | Paid USD. |
| `Pledged` | int | no | Pledged USD. |
| `Total` | int | no | Paid + Pledged. |

## bronze_cbpf_projects  ✅ acquired (was "needed" — landed via the OCHA CBPF OData API)

CBPF allocations at **project × cluster** grain — the sector-tagged CBPF source that `bronze_cbpf_allocations` (fund/year/window aggregate, no sector) lacks. Closes the CBPF leg of the sector crosswalk.

- **Source**: `staging/cbpf_projects.csv` (8.2 MB, 24,219 rows, 2010–2026, all 34 funds, 100% cluster-tagged, 100% valid iso3). OCHA CBPF Business Intelligence OData API, discovered via HDX `cbpf-allocations-and-contributions`. CC BY-IGO, monthly refresh, no auth. See `docs/notes/acquisition_cbpf_projects.md`.
- **Grain**: project × cluster (a project covering N clusters yields N rows; `amount_usd` is that cluster's slice). **PK**: (`project_code`, `cluster`).

| Column | Type | Notes |
|---|---|---|
| `year` | int | Allocation year (`Cluster.AllocationYear`). 2010–2026. |
| `fund_id` | int | `Cluster.PooledFundId`; the stable join key to the fund (unambiguous, unlike the name). |
| `fund_name` | string | `Cluster.PooledFundName`; 34 distinct. Aligns with `bronze_cbpf_allocations.PooledFund` after suffix normalization. |
| `iso3` | string | Derived from `Poolfund.CountryCode` (alpha-2→alpha-3); 2 source overrides (see Quirk). 100% valid. |
| `country_name` | string | pycountry canonical from `iso3`. |
| `cluster` | string | `Cluster.Cluster` — IASC cluster. 15 distinct, 0 null. Join key to `silver_sector_crosswalk.cbpf_category`. |
| `sub_cluster` | string | `Cluster.SubCluster`. Sparse (6.2% populated); v1 unused (see Quirk). |
| `cluster_percentage` | float | Cluster's share of the project budget. |
| `amount_usd` | float | `Cluster.ClusterBudget` — this cluster's USD slice. 0 null. |
| `allocation_window` | string | `standard` (15,115) / `reserve` (9,104). Joins to `bronze_cbpf_allocations.AllocationType`. |
| `project_code` | string | `Cluster.ChfProjectCode` — unique project key (e.g. `SSD-18/HSS10/SA2/FSL/UN/10025`). |
| `chf_id` | int | `Cluster.ChfId` — internal project id (per-fund, not globally unique). |
| `project_title` | string | `ProjectSummary.ProjectTitle`. 100% filled. |
| `recipient_organization` | string | `ProjectSummary.OrganizationName`. 100% filled. |
| `recipient_organization_type` | string | UN Agency / International NGO / National NGO / RedCross-RedCrescent. |
| `project_status` | string | e.g. Project Closed, Project Closure, Ongoing. |
| `actual_start_date` | string→date | `YYYY-MM-DD`; empty where source carries the `0001-01-01` null sentinel. |
| `actual_end_date` | string→date | Same null handling. |

**Notes**: Joins to `silver_sector_crosswalk` on `cluster` → `cbpf_category` (populated for 15 of 25 crosswalk rows after the 2026-05-22 crosswalk update). Joins to `silver_fund_country_map` on `fund_name`/`fund_id`; `iso3` carries two documented source overrides (`LI`→`MOZ` for Mozambique RhPF, `XX`→`SYR` for Syria Cross border). Year-total budgets reconcile to `bronze_cbpf_allocations` within ±15% (verified 2024 +2.8% / 2025 +0.3% / 2026 −7.9%; the 2026 shortfall is in-year project-entry lag, not a data gap).

**Quirk**: `sub_cluster` is only 6.2% populated and was **not** profiled against the crosswalk's Protection sub-cluster rows (`PRO-CPN`, `PRO-GBV`, `PRO-MIN`, `PRO-HLP`, `PRO-HTS`); v1 uses the parent `cluster` field only. Two `Poolfund.CountryCode` values are wrong/placeholder at source (`LI`→`MOZ`, `XX`→`SYR`); both are corrected at acquisition. Note this makes two funds share `iso3=SYR` (`Syria` + `Syria Cross border`) — distinct at fund grain, combined only at iso3 grain.

## bronze_inform_severity  ✅ profiled (🟡 multi-sheet workbook)

Monthly INFORM Severity snapshots (ACAPS). The hardest Bronze source — each file is a 21-sheet analytical workbook full of cross-sheet formulas.

- **Source**: ~60 `*inform-severity*.xlsx` / `*gcsi*.xlsx` files in `data/databricks_data/unocha/`, ~monthly 2019→2026. The pre-2020 files use the older **GCSI** branding (same lineage).
- **Bronze strategy**: read **two sheets** per workbook into long form, deriving `snapshot_date` from `_source_file` (filename encodes the month, e.g. `202601_inform_severity_-_january_2026`):
  - `INFORM Severity - country` (≈85 rows) — one row per country-level crisis.
  - `INFORM Severity - all crises` (≈130 rows) — includes sub-country / multiple crises per country.
- **Grain**: snapshot_month × crisis. **PK**: (`snapshot_date`, `CRISIS ID`).
- **Header quirk**: real headers are on the **2nd row**; rows labelled `Weights` and the `(1-10)`/`(1-5)` range annotations sit above the data — skip them on read.
- **⚠️ Sheet-name dispatch**: 20 of 89 files (Jan 2019 – Aug 2020) carry the data on the `GCSI` sheet rather than `INFORM Severity - country`. Bronze loader reads `INFORM Severity - country` if present, otherwise falls back to `GCSI`. Downstream schema is identical after dropping the row-3 `Weights` marker row.

| Column (cleaned) | Type | Notes |
|---|---|---|
| `crisis` | string | Crisis name. |
| `crisis_id` | string | e.g. `AFG001` (country ISO3 + ordinal). |
| `country` | string | Country name. |
| `iso3` | string | ISO3 alpha — join key. |
| `drivers` | string | Comma-delimited driver tags (`Conflict/Violence,Political/economic…`). |
| `inform_severity_index` | float | **1–10** continuous. |
| `inform_severity_category` | int | **1–5** ordinal — used by the severity gate (`≥4`) and chronic check (`≥3`). |
| `inform_severity_category_label` | string | `Very Low`…`Very High`. |
| `trend_3m` | string | `Decreasing` / `Stable` / `Increasing`. |
| `reliability` | string | `Very Low`…`Very High`. |
| `impact` / `geographical` / `human` / `conditions` / `complexity` | float | Dimension sub-scores (1–10). |

**Bonus sheets worth a follow-up loader (not v1-critical):** `Trends` (monthly severity time-series per crisis, 2019→present — a ready-made input to `chronic_index` without re-stitching snapshots) and `Crisis info` (crisis start date, duration, region, drivers). Flagged in `docs/open-questions.md`.

## bronze_cod_population  ✅ profiled

UN Common Operational Dataset population, long format by demographic — the **national (admin0) + admin1** levels (the denominators used at the global and admin1 ranking layers). Loaded by `notebooks/bronze/bronze_cod_population.py`. The admin2 deep-dive level is a sibling table, `bronze_cod_population_admin2` (below). admin3 is acquired but ETH-only and admin4 is essentially unusable (only 1 country); both are excluded from the v1 named scope and can be added later with the same loader pattern.

- **Source**: `cod_population_admin0.csv`, `cod_population_admin1.csv` — the two CMU-drop files (each populates `ADM1..ADMn` columns up to its level). `_admin_level` (0/1) is derived on load.
- **Grain**: admin-unit × population_group × gender × age_range. **PK**: (deepest `ADMn_PCODE` or `ISO3` at admin0, `Population_group`).

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `ISO3` | string | no | ISO3. |
| `Country` | string | no | Name. |
| `ADM1_PCODE`/`ADM1_NAME` | string | level-dependent | P-code + name; null on admin0 rows. |
| `Population_group` | string | no | `T_TL` (total), `M_TL`, `F_TL`, age-band codes. |
| `Gender` | string | no | `all` / `m` / `f`. |
| `Age_range` | string | no | `all`, `0-4`, `5-9`, … |
| `Age_min` / `Age_max` | float | yes | Age bounds (null for `all`). |
| `Population` | int | no | Count. |
| `Reference_year` | int | no | Census/projection year (varies by country). |
| `Source` / `Contributor` | string | no | Provenance. |

**Total-population row** = `Population_group='T_TL'` AND `Gender='all'` AND `Age_range='all'`. That single row per admin unit is what `severity_rate` and population-weighted allocation use.

## bronze_cod_population_admin2  ✅ profiled

UN COD population at **admin2** — the subnational deep-dive denominator. A distinct, more-complete source than the CMU-drop admin2 file: the `cod-ps-global` supplemental pull (see `docs/notes/acquisition_supplemental_cod.md`). Loaded by `notebooks/bronze/bronze_cod_population_admin2.py`.

- **Source**: `cod_population_admin2.csv` (the `cod-ps-global` pull, 1,001,583 rows, 19 columns). `_admin_level` (2) is derived on load.
- **Grain**: admin2-unit × population_group × gender × age_range. **PK**: (`ADM2_PCODE`, `Population_group`).
- **Coverage**: long-format, age/sex disaggregated; 77 of 109 countries have admin2 population. Of the priority set, **YEM, MMR, NGA have zero admin2 population** → degrade to admin1 + `data_sparsity_flag` in Silver. `Reference_year` varies and some are stale (VEN = 2011); carried through for the data-freshness indicators. Schema columns match `bronze_cod_population` plus the full `ADM2_*`/`ADM3_*`/`ADM4_*` p-code+name set (populated to admin2). admin3 (`cod_population_admin3.csv`) is acquired but ETH-only and excluded from v1 named scope.

**Total-population row** convention is identical to `bronze_cod_population` (`Population_group='T_TL'` AND `Gender='all'` AND `Age_range='all'`).

## bronze_cerf_allocations  ✅ profiled

CERF allocations (RR + UFE windows). Already documented in `docs/notes/acquisition_cerf_ufe.md`; schema reproduced here.

- **Source**: `staging/cerf_allocations_raw.csv` (HDX `cerf-allocations`, full 2006→2026, 8,511 rows).
- **Grain**: one allocation (agency × project). **PK**: `projectID` (+ `projectCode`).

| Column | Type | Notes |
|---|---|---|
| `countryCode` | string | ISO3 (validated for all UFE rows). |
| `countryName` | string | Long-form (`Republic of the Sudan`) — **join on `countryCode`, not name**. |
| `year` | int | = signature year. |
| `dateUSGSignature` | string→date | ISO date; lags round announcement 2–6 months. |
| `windowFullName` | string | **`Rapid Response` / `Underfunded Emergencies`** — the UFE discriminator (feeds `silver_ufe_label`). |
| `totalAmountApproved` | float | USD. |
| `agencyName` | string | Implementing agency. |
| `emergencyTypeName` | string | `Drought`, `Multiple Emergencies`, … |
| `continentName`/`regionName` | string | Geography. |
| `tableName` | string | `P` / `M` — **meaning unresolved** (ask Mary; see acquisition note). |
| `projectsectors`/`projectclusters` | string | Sector tags. |
| `projectgroupings`/`projectcapcodes` | string | Sparse (~3% / 6%) multi-value grouping codes. |

## bronze_acled_events  ✅ acquired (was "planned")

Point-level conflict events. **Acquired this session** via the ACLED OAuth API — see `docs/notes/acquisition_acled.md`.

- **Source**: `staging/acled_events_2020_present.parquet` (736,648 rows, 25 priority countries, 2020-01-01 → 2025-05-22).
- **Grain**: one event. **PK**: `event_id_cnty`.
- **⚠️ Two acquisition constraints baked into the data**: (1) the account carries a **12-month recency embargo** — no events newer than ~12 months; (2) `iso` is **ISO numeric** — `priority_iso3` (alpha-3) added for joining.

| Column | Type | Notes |
|---|---|---|
| `event_id_cnty` | string | PK. |
| `event_date` | date | 2020-01-01 → 2025-05-22 (embargo ceiling). |
| `year` | Int64 | |
| `time_precision` | Int64 | 1=exact day … 3=month/year. |
| `disorder_type` / `event_type` / `sub_event_type` | string | ACLED taxonomy. `event_type` ∈ {Battles, Explosions/Remote violence, Violence against civilians, Protests, Riots, Strategic developments}. |
| `actor1`/`assoc_actor_1`/`actor2`/`assoc_actor_2` | string | Actors; `assoc_actor_*` are **semicolon-delimited** multi-value. |
| `iso` | Int64 | **ISO numeric** (729=SDN). |
| `priority_iso3` | string | Alpha-3, added — **join key**. |
| `country`/`admin1`/`admin2`/`admin3`/`location` | string | Admin names (no P-codes from API). 0% null admin1/2. |
| `latitude`/`longitude` | float64 | 4-decimal native precision; **0 nulls**. H3 res-5 indexing happens in Silver. |
| `geo_precision` | Int64 | 1=precise, 2=admin centroid (~42%), 3=region. **Down-weight ≥2 for hotspots.** |
| `source`/`source_scale` | string | Reporting source + scale. |
| `notes` | string | Free-text event description. |
| `fatalities` | Int64 | |
| `tags` | string | `key=value` tags, ~9% empty. |

## bronze_acled_severity  ✅ acquired (NEW table — see DECISIONS 2026-05-22)

Admin2 × month conflict aggregates — the current-coverage counterpart to `bronze_acled_events`. Not in the original task list; added to reflect the dual-source ACLED design.

- **Source**: `staging/acled_severity_admin2_month_2020_present.parquet` (942,126 rows, 25 countries, 2020-01 → **2026-05**, current). HDX aggregated XLSX.
- **Grain**: country × admin2 × month × event_category. **PK**: (`priority_iso3`, `admin2_pcode`, `month_start`, `event_category`).

| Column | Type | Notes |
|---|---|---|
| `iso3` | string | Source ISO3 — **NULL for GTM/HND/PHL** (ACLED left it blank). |
| `priority_iso3` | string | Alpha-3, added — **reliable join key**. |
| `country`/`admin1`/`admin2` | string | Names. |
| `admin1_pcode`/`admin2_pcode` | string | **P-codes — the value-add over the event path** (join to boundaries). |
| `event_category` | string | `political_violence` / `civilian_targeting` / `demonstration`. **`civilian_targeting` overlaps political violence — do not sum all three.** COL has no `demonstration` (source file corrupt). |
| `year`/`month_name`/`month_num`/`month_start` | int/str/int/date | Month grain; includes explicit **zero-event rows** (~64%). |
| `events` / `fatalities` | int | Counts. |

## bronze_echo_fca  ✅ acquired (was "planned")

DG ECHO Forgotten Crises Assessment lists — Layer-2 validation comparator. **Acquired this session.**

- **Source**: `staging/echo_fca_lists.csv` (197 rows, 2015–2026).
- **Grain**: year × crisis. **PK**: (`year`, `iso3`, `crisis_name`).

| Column | Type | Notes |
|---|---|---|
| `year` | int | 2015–2026 (2018, 2025 absent — see acquisition note). |
| `iso3` | string | ISO3; ~0.5% null (multi-country regional entries). |
| `country_name` | string | |
| `crisis_name` | string | ECHO crisis label. |
| `forgotten_category` | string | Always `forgotten` — ECHO publishes no fully/partially split. |
| `source_url` | string | PDF/page provenance. |

## bronze_nrc_neglected  ✅ acquired (was "planned")

NRC "World's Most Neglected Displacement Crises" — Layer-2 comparator (this one **is** ranked).

- **Source**: `staging/nrc_most_neglected_lists.csv`.
- **Grain**: year × rank. **PK**: (`year`, `iso3`).

| Column | Type | Notes |
|---|---|---|
| `year` | int | |
| `rank` | int | NRC published rank (1 = most neglected). |
| `iso3` | string | |
| `country_name` | string | |
| `source_url` | string | |

## bronze_reliefweb_situation_reports  ✅ acquired (was "planned")

ReliefWeb situation-report body-text corpus — the Day-4 Knowledge Assistant stretch goal. **Acquired this session** via the ReliefWeb v2 API (appname approved) — see `docs/notes/acquisition_reliefweb.md`.

- **Source**: JSON corpus at `staging/reliefweb_docs/{iso3}/{YYYY-MM-DD}_{report_id}.json` — 500 docs, ~3.4 MB on disk (25 priority countries × the 20 most-recent docs each).
- **Grain**: one document. **PK**: `report_id`.

| Column | Type | Notes |
|---|---|---|
| `report_id` | int | PK. |
| `iso3` | string | Primary country ISO3. |
| `country_name` | string | |
| `title` | string | |
| `publication_date` | string→date | |
| `format` | string | `Situation Report` / `Analysis` / `Assessment`. |
| `source_organization` | string | Publishing org. |
| `report_url` | string | ReliefWeb permalink. |
| `body_text` | string | Stripped plain-text body — the KA ingestion input. |
| `body_html` | string | Raw HTML body, kept as provenance. |
| `body_word_count` | int | 45 docs < 100 words (attachment-only stubs), 1 empty — Silver drops `< 100` before embedding. |
| `all_countries` | array<string> | Every country the report is tagged to (inferred as array). |
| `scraped_at` / `scraper_version` | string | Acquisition audit fields. |

- **Note**: the body-text corpus is for the Day-4 KA stretch goal; the load-bearing v1 `media_attention` signal comes from the sibling `bronze_reliefweb_attention` table (below), not from this one.

## bronze_reliefweb_metadata  ✅ acquired

The full per-report metadata index across the acquisition window — the substrate for report-volume profiling and the source the attention grid is derived from. Same v2-API acquisition as the corpus above.

- **Source**: `staging/reliefweb_metadata.csv` — 47,339 rows, 36-month window (`2023-06-08 → 2026-05-22`), 25 priority countries.
- **Grain**: one report per row. **PK**: `report_url` (or composite `iso3` × `publication_date` × `report_url`).

| Column | Type | Notes |
|---|---|---|
| `iso3` | string | Country ISO3 (inclusive tagging — a report can appear once per tagged country). |
| `country_name` | string | |
| `title` | string | |
| `publication_date` | string→date | |
| `format` | string | `Situation Report` / `Analysis` / `Assessment`. |
| `source_organization` | string | Publishing org. |
| `report_url` | string | ReliefWeb permalink — PK. |

- **Format distribution**: Situation Report 28,138 · Analysis 15,057 · Assessment 4,144.

## bronze_reliefweb_attention  ✅ acquired

The per-country × month report-count grid — **the table that feeds `media_attention_norm` in `gold_forgotten_crisis_index`**. Derived from `bronze_reliefweb_metadata` at acquisition time as a dense grid.

- **Source**: `staging/reliefweb_media_attention.csv` — 900 rows (25 countries × 36 months), dense (explicit zeros for months with no reports, so no gap-filling is needed downstream).
- **Grain**: country × month. **PK**: (`iso3`, `year_month`).

| Column | Type | Notes |
|---|---|---|
| `iso3` | string | Country ISO3. |
| `year_month` | string | `YYYY-MM`. |
| `report_count` | int | Reports tagged to the country that month. |

- **Note**: Silver computes the within-year percentile-rank normalization and applies the **negative** weight (per `methodology.md`). `report_count` is **per-country by design** — do **not** sum it across countries to form a global denominator (21.3% of reports are multi-country tagged, attributed inclusively at acquisition time, so a global sum would double-count).

## bronze_fieldmaps_boundaries  ✅ profiled

Edge-matched global subnational boundaries.

- **Source**: `staging/fieldmaps_admin_boundaries.geoparquet` (GeoParquet 1.1.0, 43,064 rows, ~2 GB; CRS OGC:CRS84 ≡ EPSG:4326). See `docs/notes/acquisition_fieldmaps.md`.
- **Grain**: one polygon (admin2-level rows, with admin0/1 identifiers denormalized on each). **PK**: `fid` (or `adm2_id`).

Selected of 45 columns:

| Column | Type | Notes |
|---|---|---|
| `fid` | int64 | PK. |
| `adm2_id` / `adm1_id` / `adm0_id` | string | **P-code-equivalent identifiers** — the subnational join keys (verify equality with HNO `Admin N PCode`). |
| `adm2_name` / `adm1_name` / `adm0_name` (+ `_name1`/`_name2` alternates) | string | Names + alternate-language names. |
| `iso_3` | string | **ISO3 join key.** |
| `iso_2` / `iso_cd` | string / int64 | ISO2 / ISO numeric. |
| `iso_3_grp` | string | Grouping ISO3 (disputed-territory handling). |
| `src_lvl` | int64 | Source admin depth. |
| `src_date` / `src_update` | date32 | Source vintage. |
| `src_name` / `src_url` / `src_lic` | string | Provenance + licence. |
| `status_cd` / `status_nm` | int64 / string | **Disputed-territory status** (feeds `contested_border_flag`). |
| `wld_view` / `wld_notes` | string | Worldview / disputed-area notes. |
| `region{1,2,3}_cd` / `_nm` | int64 / string | Regional groupings. |
| `geometry` | binary | **WKB-encoded** polygon (read via Sedona/geoparquet reader). |
| `geometry_bbox` | struct<xmin,ymin,xmax,ymax: float> | Bounding box for fast spatial filtering. |

---

# Silver

Cleaned, conformed, DLT-tested. Notebooks under `notebooks/silver/`. Each table lists schema, key transformations, and DLT expectations (`@dlt.expect_or_drop` / `@dlt.expect`). Conventions: snake_case columns; types cast; HXL rows dropped; ISO3 conformed.

## silver_country_dim  🟡

Country reference dimension — the spine every country-grain table joins to.

- **Source**: `staging/country_taxonomy_raw.csv` (+ `pycountry` for numeric↔alpha); `staging/global_pcodes_raw.csv` for P-code prefixes.
- **Grain**: one country. **PK**: `iso3`.
- **Columns**: `iso3` (string), `iso_numeric` (int — bridges ACLED `iso`), `iso2` (string), `country_name` (string, canonical), `region` (string), `subregion` (string), `pcode_prefix` (string), `is_in_scope` (bool, passes severity gate in any year).
- **Transforms**: dedupe to one row/ISO3; attach numeric code for ACLED joins; attach OCHA region for `rank_crises(scope=...)`.
- **DLT**: `expect_or_drop` valid_iso3 (`LENGTH(iso3)=3`); `expect_or_drop` unique `iso3`; `expect` non-null `country_name`.

## silver_fts_flows  🟡 (multi-country allocation cascade applied here)

Cleaned, country-attributed funding flows.

- **Source**: `bronze_fts_flows` (all three boundaries) + `bronze_hrp` (per-plan country requirements) + `silver_population` (fallback weights).
- **Grain**: one **allocated** flow-share (a source flow may fan out to multiple country rows). **PK**: (`source_flow_id`, `iso3`).

| Column | Type | Notes |
|---|---|---|
| `source_flow_id` | int | = `bronze_fts_flows.id`, lineage back to Bronze. |
| `iso3` | string | Allocated destination country. |
| `plan_code` | string | `destPlanCode`. |
| `amount_usd` | double | Allocated share = `amountUSD × allocation_weight`. |
| `status` | string | `paid`/`commitment`/`pledge`. |
| `cluster` | string | `destGlobalClusters` (first/normalized). |
| `donor_org` / `donor_type` | string | `srcOrganization(Types)`. |
| `flow_date` | date | |
| `boundary` / `on_boundary` | string | Carried for dedupe transparency. |
| `allocation_method` | string | `country_tagged` / `requirements_weighted` / `population_weighted_fallback` / `regional_unattributed`. |
| `allocation_weight` | double | Fraction of source flow assigned to this country (Σ over splits = 1). |

- **Transforms**: (1) dedupe `onBoundary='shared'` flows so a shared incoming/outgoing pair isn't counted twice; (2) explode `destLocations` comma-list; (3) apply the 4-step allocation cascade from `methodology.md`; (4) cast USD to double, dates to date.
  - **Cascade distribution (profiled)**: in the profiled data, the cascade distribution is approximately 68.5% `country_tagged` (single-country flows), <0.1% `requirements_weighted`, ~31% `population_weighted_fallback`, with a small `regional_unattributed` tail. Surface this distribution on the Methodology screen as transparency about how multi-country flows are allocated.
- **DLT**: `expect_or_drop` valid_status (`status IN ('paid','commitment','pledge')`); `expect_or_drop` non_negative (`amount_usd >= 0`); `expect_or_drop` valid_iso3; `expect` weights_sum_to_one (per `source_flow_id`, Σ`allocation_weight` ≈ 1); `expect` no_shared_double_count.

## silver_needs  🟡 (country × year × sector from HNO)

- **Source**: `bronze_hno` (2024/2025/2026). **Grain**: country × year × cluster. **PK**: (`iso3`, `year`, `cluster`).
- **Columns**: `iso3`, `year`, `cluster` (code), `cluster_name`, `people_in_need` (long→bigint), `targeted` (bigint), `population` (bigint, nullable), `pin_total_country` (bigint, the `Cluster='ALL'` caseload), `has_subnational` (bool).
- **Transforms**: drop HXL hashtag row; cast strings→numeric; collapse demographic `Category` splits to the aggregate per (country, year, cluster); isolate the `ALL`/caseload row as `pin_total_country`; set `year` from `_source_file`.
- **DLT**: `expect_or_drop` valid_iso3; `expect_or_drop` non_negative_pin; `expect` pin_not_exceeding_population (warn-only — PIN can exceed baseline pop for refugee-hosting).

## silver_subnational_needs  🟡 (admin1 × sector from HNO where available)

- **Source**: `bronze_hno` 2024/2025 admin rows only (2026 has none). **Grain**: country × year × admin1 × cluster. **PK**: (`admin1_pcode`, `year`, `cluster`).
- **Columns**: `iso3`, `year`, `admin1_pcode`, `admin1_name`, `admin2_pcode` (nullable), `cluster`, `people_in_need` (bigint), `targeted` (bigint), `admin1_derived` (boolean — `true` when `admin1_pcode` was derived by P-code-prefix rollup from admin2 rows (SDN, YEM, HTI, VEN, NGA in HNO 2025), `false` when read directly from HNO. Carried for provenance).
- **Transforms**: keep rows with non-null `Admin 1 PCode`; aggregate admin2→admin1 where finer; emit `data_sparsity_flag` upstream for countries absent here.
- **DLT**: `expect_or_drop` non_null_admin1_pcode; `expect` pcode_prefix_matches_iso3 (warn).
- **⚠️ Coverage note**: HNO 2026 dropped subnational columns entirely, so 2026 subnational needs are unavailable from HNO — `gold_subnational_index` for 2026 must fall back or carry `data_sparsity_flag`.

## silver_requirements  🟡 (country × year from HRP)

- **Source**: `bronze_hrp` + `bronze_fts_plan`. **Grain**: country × year × plan. **PK**: (`iso3`, `year`, `plan_code`).
- **Columns**: `iso3`, `year`, `plan_code`, `plan_name`, `plan_type`, `requirement_usd` (double — see sourcing note below), `is_multi_country` (bool), `country_list` (array<string>, from pipe-split `locations`), `start_date`, `end_date`.
- **Transforms**: pipe-split `locations`→array; mark multi-country; unify the HRP/HNRP plan-type rename into a single `country_response_plan`.
  - **`requirement_usd` sourcing**: primary source is `bronze_fts_plan.requirements` (already at country × plan grain), with `bronze_hrp.revisedRequirements` (plan-total, divided by country count) → `origRequirements` as fallback when the FTS plan lacks a per-country breakdown. Per-country is the correct denominator for a per-country `gap_ratio` — using the plan-total directly would over-attribute to each constituent country in a multi-country plan. (Because `bronze_fts_plan` is natively country × plan grain, this sourcing needs no allocation cascade and introduces no dependency on `silver_fts_flows`.)
  - **Dual grain**: carry two row types: (a) plan-level rows joined `bronze_fts_plan` ↔ `bronze_hrp` on `code`, attributed to country via the multi-country cascade where the plan covers multiple countries; (b) country-aggregate rows from `bronze_fts_plan` where `code IS NULL` and `name='Not specified'`, attributed directly to `countryCode` with `plan_code = NULL`. Both flow into `gold_funding_funnel` and `gold_forgotten_crisis_index` so no-HRP countries retain their off-plan funding signal.
- **DLT**: `expect_or_drop` non_negative_requirement; `expect_or_drop` valid_dates (`end_date >= start_date`); `expect` plan_code_unique_per_year.

## silver_severity  🟡 (country × year from INFORM)

- **Source**: `bronze_inform_severity`. **Grain**: country × year (collapse monthly snapshots to annual). **PK**: (`iso3`, `year`).
- **Columns**: `iso3`, `year`, `severity_index_mean` (double, 1–10, mean of monthly), `severity_index_max` (double), `severity_category_max` (int, 1–5), `trend_modal` (string), `reliability_modal` (string), `n_snapshots` (int), `latest_snapshot_date` (date).
- **Transforms**: derive `snapshot_date` from `_source_file`; collapse the multiple crisis rows per country (take max severity); aggregate snapshots within a year.
- **DLT**: `expect_or_drop` severity_index_in_range (`BETWEEN 0 AND 10`); `expect_or_drop` category_in_range (`BETWEEN 1 AND 5`); `expect` valid_iso3.

## silver_population  🟡 (country × year from COD-PS)

- **Source**: `bronze_cod_population` (admin0 file for national; admin1 for subnational weights). **Grain**: country (× admin1). **PK**: `iso3` (national) / `admin1_pcode` (sub).
- **Columns**: `iso3`, `admin1_pcode` (nullable), `population_total` (bigint, the `T_TL`/`all`/`all` row), `reference_year` (int), `source` (string).
- **Transforms**: filter to `Population_group='T_TL' AND Gender='all' AND Age_range='all'`; one total per unit.
- **DLT**: `expect_or_drop` positive_population; `expect_or_drop` one_total_row_per_unit; `expect` valid_iso3.

## silver_cbpf_allocations  🟡

- **Source**: `bronze_cbpf_allocations` + fund→ISO3 map. **Grain**: year × fund × allocation_type. **PK**: (`year`, `fund_iso3`, `allocation_type`).
- **Columns**: `year` (int), `fund_name` (string), `fund_iso3` (string, mapped; null for genuinely regional funds), `is_regional_fund` (bool), `allocation_type` (string), `budget_usd` (bigint).
- **Transforms**: map `PooledFund`→ISO3 (strip ` (AP-RHPF)` suffixes; flag regional); keep regional funds with null ISO3 + flag.
- **DLT**: `expect_or_drop` non_negative_budget; `expect` allocation_type_valid (`IN ('standard','reserve')`).

## silver_cbpf_contributions  🟡

- **Source**: `bronze_cbpf_contributions` (2,132 raw rows, 1,843 unique on `(Year, Donor)`).
- **Grain**: year × donor. **PK**: (`year`, `donor`).
- **Columns**: `year` (int), `donor` (string), `donor_type` (string), `paid_usd` (long), `pledged_usd` (long), `total_usd` (long), `n_records` (int — count of source rows aggregated; transparency for the 289 within-file dupes).
- **Transforms**: aggregate sum over `(year, donor)`; preserve `n_records` for audit.
- **DLT**: `expect_or_drop` non_negative_total; `expect` valid_year (warn).
- **Note**: No country attribution available in source — CBPF Contributions are global donor totals per year. Used for the optional CBPF Allocation View screen (PFM persona); NOT used for `gold_donor_concentration` (that comes from `silver_fts_flows.donor_org` per DECISIONS 2026-05-22).

## silver_cbpf_projects  🟡 (country × year × harmonized_sector from CBPF projects)

- **Source**: `bronze_cbpf_projects` + `silver_sector_crosswalk` (cluster→`cbpf_category`) + `silver_fund_country_map`. **Grain**: country × year × harmonized_sector. **PK**: (`iso3`, `year`, `harmonized_sector_id`).
- **Columns**: `iso3`, `year`, `harmonized_sector_id`, `harmonized_sector`, `cbpf_funding_usd` (double — sum of `amount_usd` over project×cluster rows), `project_count` (distinct projects), `fund_count` (distinct funds).
- **Transforms**: join `bronze_cbpf_projects.cluster` to `silver_sector_crosswalk.cbpf_category` (**case-sensitive** — the CBPF taxonomy uses specific casing like `Multi-purpose CASH`); aggregate to country × year × harmonized_sector. Unresolved clusters are routed to a `_quarantine` (NULL `harmonized_sector_id` bucket surfaced by `crosswalk_resolved`) rather than silently dropped.
- **DLT**: `expect_or_drop` valid_iso3, non_negative_funding; `expect` crosswalk_resolved (warn — catches new CBPF cluster names that need crosswalk additions); `expect` sub_cluster_dropped_v1 (warn — surfaces sector-groups whose source rows carried non-null `sub_cluster` dropped in v1, for v2 audit).
- **v2**: profile `sub_cluster` (6.2% populated) against the crosswalk's Protection sub-cluster rows (`PRO-CPN`, `PRO-GBV`, `PRO-MIN`, `PRO-HLP`, `PRO-HTS`). CBPF `COVID-19` maps to harmonized `COVID-19` here; the crosswalk's "reassign to Health post-2023" rule is applied at Gold, not in this Silver aggregation.

## silver_cerf_allocations  🟡

- **Source**: `bronze_cerf_allocations`. **Grain**: one allocation. **PK**: `project_id`.
- **Columns**: snake_case of Bronze (`iso3`←`countryCode`, `window` ← `windowFullName`, `amount_usd`, `signature_date`, `year`, `agency`, `emergency_type`, `sectors`). `tableName` carried, unused.
- **Transforms**: cast; validate ISO3.
- **DLT**: `expect_or_drop` valid_window (`IN ('Rapid Response','Underfunded Emergencies')`); `expect_or_drop` non_negative_amount; `expect_or_drop` valid_iso3.

## silver_ufe_label  🟡 (country × year × round, binary)

- **Source**: `staging/ufe_labels.csv` (derived) / `silver_cerf_allocations` filtered to UFE. **Grain**: country × year × round. **PK**: (`iso3`, `year`, `round`).
- **Columns**: `iso3` (string), `country_name` (string), `year` (int), `round` (string `H1`/`H2`), `ufe_selected` (boolean), `allocation_usd` (double).
- **Transforms**: filter `window='Underfunded Emergencies'`; H1/H2 from signature date (carries the documented 2–6 month lag — year-grain reliable, round-grain approximate).
- **DLT**: `expect_or_drop` valid_iso3; `expect` round_in_set (`IN ('H1','H2')`); `expect` boolean_label.

## silver_acled_events  🟡 (geocoded, H3-indexed)

- **Source**: `bronze_acled_events`. **Grain**: one event. **PK**: `event_id_cnty`.
- **Columns**: Bronze columns + `iso3` (string, mapped from numeric `iso` via `silver_country_dim`, or `priority_iso3`), `h3_r5` (string, H3 resolution-5 index from lat/lon), `event_month` (date).
- **Transforms**: H3 res-5 index; numeric→alpha ISO; keep `geo_precision`/`time_precision` for hotspot weighting.
- **DLT**: `expect_or_drop` valid_coords (`latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180`); `expect_or_drop` non_null_h3; `expect` geo_precision_flagged (precision ≥2 retained but flagged); `expect` non_negative_fatalities.
- **⚠️ Recency**: bounded at ~12 months stale (account embargo). Hotspot logic must treat the max event_date as the analysis "now," not the calendar date.

## silver_acled_severity  🟡 (admin2 × month) — companion to events

- **Source**: `bronze_acled_severity`. **Grain**: country × admin2 × month × category. **PK**: (`iso3`, `admin2_pcode`, `month_start`, `event_category`).
- **Columns**: cleaned Bronze + `iso3` coalesced from `priority_iso3` (fills GTM/HND/PHL nulls).
- **Transforms**: coalesce ISO3; optionally drop zero rows for analytic views (keep in base).
- **DLT**: `expect_or_drop` non_negative_events; `expect` valid_category; `expect` iso3_present_after_coalesce.

## silver_media_attention  🟡

- **Source**: `bronze_reliefweb_attention` (900 rows, 25 countries × 36 months dense grid).
- **Grain**: country × year. **PK**: (`iso3`, `year`).
- **Columns**: `iso3` (string), `year` (int), `report_count_annual` (int — sum of monthly report counts for the year), `media_attention_norm` (double — within-year percentile rank, 0–1; **input to the negative-weight component in `gold_forgotten_crisis_index`**).
- **Transforms**: aggregate monthly `report_count` to annual; within-year percentile-rank normalization; flag countries with zero coverage in the analysis year via `report_count_annual = 0` (the dense grid preserves zeros explicitly — these are real, not missing data).
- **DLT**: `expect_or_drop` valid_iso3, non_negative_count; `expect` norm_in_unit_interval (warn).
- **Note**: Per `acquisition_reliefweb.md`, don't sum `report_count` across countries to form a global denominator — 21.3% of reports are multi-country-tagged and the signal is per-country by design.

## silver_boundaries  🟡 (geoparquet, admin0/1/2)

- **Source**: `bronze_fieldmaps_boundaries`. **Grain**: one polygon. **PK**: `adm2_id`.
- **Columns**: `iso3` (←`iso_3`), `adm0_id`/`adm1_id`/`adm2_id` (P-codes), names, `status_nm` (disputed flag), `contested_border_flag` (bool, derived from `status_cd`/`wld_notes`), `geometry` (geometry type via Sedona), `h3_cells_r5` (array<string>, optional precompute), `centroid_lon`/`centroid_lat`.
- **Transforms**: read WKB→geometry (Sedona); validate polygons; derive centroids; precompute adjacency for `gold_cross_border_patterns`.
- **DLT**: `expect_or_drop` valid_geometry (`ST_IsValid`); `expect_or_drop` valid_iso3; `expect` pcode_join_coverage (warn if `adm1_id` doesn't match HNO P-codes).
- **Open item**: confirm `adm{1,2}_id` ≡ HNO `Admin N PCode` (acquisition note open question).

---

# Gold

Analytical, business-ready, and the substrate for agent tools (UC Functions). Notebooks under `notebooks/gold/`. Each is time-versioned by `year` so `get_ranking_delta` can diff. Data-quality assertions are stated as DLT `expect`s or post-write checks.

## gold_forgotten_crisis_index  🟡 (the headline ranking)

The composite `overlooked_score` with uncertainty and classification.

- **Sources**: `silver_needs`, `silver_requirements`, `silver_fts_flows`, `silver_severity`, `silver_population`, `gold_explanation_features` (component metrics), media counts from `bronze_reliefweb_situation_reports`, `geographic_isolation` from `silver_boundaries` + `silver_acled_events`.
- **Grain**: country × year. **PK**: (`iso3`, `year`).

| Column | Type | Source / formula (see methodology.md) |
|---|---|---|
| `iso3`, `year` | string, int | PK. |
| `country_name` | string | `silver_country_dim`. |
| `overlooked_score` | double | Weighted sum of normalized components. |
| `rank_position` | int | Dense rank of `overlooked_score` within year/scope. |
| `rank_ci_low` / `rank_ci_high` | int | 95% bootstrap CI on rank (500 Dirichlet samples). |
| `stable_top_n` | boolean | In top-10 across ≥90% of bootstrap samples. |
| `gap_ratio` | double | `(req − paid)/req`. |
| `severity_rate` | double | `pin / population`. |
| `dollars_per_pin` | double | `paid / pin`. |
| `chronic_index` | double | `chronic_years × mean_chronic_gap`. |
| `sector_imbalance` | double | std-dev of sector gaps. |
| `media_attention_norm` | double | percentile-rank of ReliefWeb count (negative weight). |
| `geographic_isolation` | double | bounded 0–1 multiplier. |
| `neglect_class` | string | `chronic_neglect`/`acute_deterioration`/`improving`/`well_funded`/`chronic_no_plan`. |
| `data_sparsity_flag` | boolean | No machine-readable admin1 / stale inputs. |
| `passed_severity_gate` | boolean | Entered ranking vs `excluded_with_signal`. |
| `inputs_freshness` | struct | Per-source last-updated dates. |

- **Transforms**: within-year percentile-rank normalization of each component; weighted composite; Dirichlet bootstrap for CIs.
- **Side output**: `silver_excluded_with_signal` — countries failing the severity gate, written to a separate Delta table for transparency. Despite the `silver_` prefix, it is computed during the Gold build, not by a Silver DLT.
- **DQ**: `expect` score_in_signed_unit_range (`overlooked_score BETWEEN -0.10 AND 0.90`); `expect` rank_ci_low ≤ rank_position ≤ rank_ci_high; `expect` no_silent_drop (every gated-out country present in `excluded_with_signal`); **no false precision** — score rounded for display downstream, CI always present.
- **Score range note**: the raw `overlooked_score` is bounded to **[−0.10, 0.90]**, not [0, 1]. The negative-signed `media_attention` term (magnitude 0.10) with the absolute component weights summing to 1.0 makes the range asymmetric: when every positive component is at its max and media at its min the score reaches +0.90, and the lone negative term floors it at −0.10. This is internal-only — **the UI leads with rank + bootstrap CI per the no-false-precision rule**, never the raw score — so the asymmetric range needs no rescaling.

## gold_funding_funnel  🟡 (country × year × stage)

- **Sources**: `silver_requirements`, `silver_fts_flows`.
- **Grain**: country × year × stage. **PK**: (`iso3`, `year`, `stage`).
- **Columns**: `iso3`, `year`, `stage` (`required`/`pledged`/`committed`/`paid`), `amount_usd` (double), `pct_of_requirement` (double).
- **Transforms**: pivot `silver_fts_flows.status` to stages; align to `requirement_usd`.
- **DQ**: `expect` paid ≤ committed ≤ pledged (warn — real data violates occasionally); `expect` non_negative amounts.

## gold_sector_coverage  🟡 (country × year × sector)

- **Sources**: `bronze_fts_globalcluster`, `silver_needs`, `silver_sector_crosswalk`.
- **Grain**: country × year × sector. **PK**: (`iso3`, `year`, `sector`).
- **Columns**: `iso3`, `year`, `sector` (harmonized), `requirement_usd`, `funding_usd`, `sector_gap` (double), `sector_pin` (bigint), `pin_share` (double), `is_flagged_gap` (bool: `sector_gap>0.7 AND pin_share≥0.10`).
- **Transforms**: crosswalk HNO cluster ↔ FTS cluster ↔ CBPF; compute per-sector gap.
- **DQ**: `expect` sector_gap_in_range (`<= 1`); `expect` crosswalk_resolved (warn on unmapped sectors).

## gold_funding_trend  🟡 (country × year × neglect_class)

- **Sources**: `gold_forgotten_crisis_index` history (multi-year), `silver_requirements`, `silver_fts_flows`.
- **Grain**: country × year. **PK**: (`iso3`, `year`).
- **Columns**: `iso3`, `year`, `gap_ratio`, `chronic_years_count` (int), `mean_chronic_gap` (double), `chronic_index` (double), `neglect_class` (string), `gap_ratio_yoy_delta` (double).
- **Transforms**: 5-year rolling window of `gap_ratio`; classify per the temporal-classification rules.
- **DQ**: `expect` chronic_years_count BETWEEN 0 AND 5; `expect` neglect_class_in_set.

## gold_donor_concentration  🟡 (country × year)

- **Sources**: `silver_fts_flows` (`donor_org`, `amount_usd`).
- **Grain**: country × year. **PK**: (`iso3`, `year`).
- **Columns**: `iso3`, `year`, `n_donors` (int), `hhi` (double, Herfindahl–Hirschman of donor shares), `top1_donor` (string), `top1_share` (double), `top3_share` (double).
- **Transforms**: aggregate paid flows by donor; compute HHI + top-share.
- **DQ**: `expect` hhi_in_unit_interval; `expect` shares_sum_to_one (per iso3/year).
- **Note**: uses **FTS** donor identity, **not** `bronze_cbpf_contributions` (which is global, un-attributable).

## gold_explanation_features  🟡 (country × year)

The deterministic decomposition substrate — every component metric and its normalized form, so the agent can explain a rank without recomputation.

- **Sources**: all country-grain Silver tables.
- **Grain**: country × year. **PK**: (`iso3`, `year`).
- **Columns**: raw + `*_norm` (percentile-ranked) versions of `gap_ratio`, `severity_rate`, `dollars_per_pin`, `chronic_index`, `sector_imbalance`, `media_attention`, `geographic_isolation`; plus `weight_*` (the weight vector used) and `contribution_*` (`weight × norm` per component, summing to `overlooked_score`).
- **DQ**: `expect` contributions_sum_to_score (Σ`contribution_*` ≈ `overlooked_score` within ε); `expect` norms_in_unit_interval.

## gold_ufe_validation  🟡 (country × year × prediction × label)

- **Sources**: `gold_forgotten_crisis_index` (prediction), `silver_ufe_label` (truth).
- **Grain**: country × year (× round). **PK**: (`iso3`, `year`, `round`).
- **Columns**: `iso3`, `year`, `round`, `predicted_rank` (int), `predicted_top_k` (bool, K=15), `ufe_selected` (bool), `is_true_positive`/`is_false_positive`/`is_false_negative` (bool), `evaluation_window` (string: `train`/`holdout`).
- **Transforms**: point-in-time ranking using only pre-round data; mark 2024–2025 rounds as holdout.
- **DQ**: `expect` no_leakage (prediction inputs predate round); `expect` label_present.

## gold_subnational_index  🟡 (admin1 × year)

- **Sources**: `silver_subnational_needs`, `silver_severity` (admin1 where available), inferred admin1 funding, `silver_boundaries`.
- **Grain**: admin1 × year. **PK**: (`admin1_pcode`, `year`).
- **Columns**: `iso3`, `admin1_pcode`, `admin1_name`, `year`, `admin1_pin` (bigint), `admin1_inferred_funding` (double, = country funding × PIN share), `admin1_overlooked_score` (double), `admin1_rank_in_country` (int), `is_inference_flagged` (bool), `data_sparsity_flag` (bool).
- **Transforms**: PIN-proportional funding inference (flagged as estimate); admin1 composite.
- **DQ**: `expect` pin_share_sums_to_one (per country); `expect` inference_flagged_true; **2026 caveat**: no HNO subnational → rows absent / sparsity-flagged.

## gold_change_indicators  🟡 (country × period × deltas)

- **Sources**: time-versioned `gold_forgotten_crisis_index`, `silver_acled_severity` (current month grain), `silver_severity`.
- **Grain**: country × period. **PK**: (`iso3`, `period`).
- **Columns**: `iso3`, `period` (string, e.g. `2026-Q1`), `rank_delta` (int), `gap_ratio_delta` (double), `severity_delta` (double), `acled_events_delta` (double), `direction` (string: `worsening`/`improving`/`stable`).
- **Transforms**: diff consecutive snapshots; ACLED uses `silver_acled_severity` (current) since events are embargoed.
- **DQ**: `expect` period_parseable; `expect` direction_in_set.

## gold_hotspots  📋 planned (Day-4 stretch)

Spatial-temporal conflict clusters.

- **Sources**: `silver_acled_events` (H3 res-5), `silver_boundaries`.
- **Grain**: H3 cell × period. **PK**: (`h3_r5`, `period`).
- **Planned columns**: `h3_r5` (string), `iso3` (string), `admin1_pcode` (string, via point-in-polygon), `period` (string), `event_count` (int), `fatalities` (int), `density_zscore` (double), `is_spatial_hotspot` (bool, >2σ above country mean), `density_jump_pct` (double), `is_emerging` (bool, >50% jump vs prior 90 days).
- **DQ (planned)**: `expect` valid_h3; `expect` period_window_90d.
- **⚠️ Recency**: limited by the ACLED 12-month embargo (`silver_acled_events`); "emerging" is relative to the data's max date.

## gold_cross_border_patterns  📋 planned (Day-4 stretch)

Adjacent overlooked admin1 areas across borders.

- **Sources**: `silver_boundaries` (adjacency), `gold_subnational_index`.
- **Grain**: admin1 pair. **PK**: (`admin1_pcode_a`, `admin1_pcode_b`).
- **Planned columns**: `admin1_pcode_a`/`_b`, `iso3_a`/`iso3_b`, `shares_boundary` (bool), `both_top_30pct` (bool), `region_label` (string: Sahel/Horn/Lake Chad/N. Central America), `combined_overlooked_score` (double).
- **DQ (planned)**: `expect` distinct_countries (`iso3_a <> iso3_b`); `expect` adjacency_verified.

---

# Reference / crosswalk tables (Silver-tier helpers)

| Table | Source | Purpose |
|---|---|---|
| `silver_sector_crosswalk` | hand-built CSV (25 rows) + `bronze_fts_globalcluster.cluster` + `bronze_cbpf_projects.cluster` + HNO `Cluster` | Harmonize HNO cluster ↔ FTS sector ↔ CBPF cluster. CBPF column populated 2026-05-22 from `bronze_cbpf_projects`; 15 of 25 crosswalk rows carry a CBPF cluster name (10 are FTS-only sub-clusters, the Agriculture sub-row, or `NOT_A_SECTOR_*` meta-rows). See `docs/notes/acquisition_cbpf_projects.md` for the mapping audit. |
| `silver_fund_country_map` | hand-built from `bronze_cbpf_allocations.PooledFund` distinct values | Map CBPF fund names → ISO3, flag regional funds. |

---

# Appendix: profiling provenance

- **Profiled 2026-05-22** from `data/databricks_data/unocha/` (CMU drop) and `staging/` via pandas (`nrows≤4000`), `pyarrow` (parquet schema), `openpyxl`/`python-calamine` (xlsx).
- Intermediate profile dumps: `staging/_schema_profile_{1,2,3}.json` (gitignored).
- **Acquired-this-session sources** (real schemas, not planned): ACLED events + severity (`acquisition_acled.md`), ECHO FCA, NRC, HDX Signals, CERF UFE, fieldmaps, ReliefWeb (`acquisition_reliefweb.md`).
- **Still planned**: the Day-4 stretch Gold tables (`gold_hotspots`, `gold_cross_border_patterns`).
- **Schema-drift / quirks to carry into Bronze loaders**: HNO 2026 (no subnational, no HXL row); FTS plan rows vs country-aggregate rows; FTS `onBoundary='shared'` double-count; CBPF contributions have no country; INFORM dual scale (1–10 vs 1–5) + multi-row headers; ACLED `iso` numeric + 12-month embargo + COL demonstration gap + GTM/HND/PHL null ISO3.
