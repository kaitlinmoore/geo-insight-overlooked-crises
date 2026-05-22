# Acquisition findings: CBPF project × cluster allocations

> **Source of these findings.** Captured from a Claude Code acquisition session on 2026-05-22. Findings are the session's verified observations on the downloaded dataset, not inferences from documentation. Marked where facts were verified vs. sampled vs. open. Promote into `docs/data-catalog.md` / `docs/schemas.md` if the source is adopted.

## Bottom line

The cluster-level CBPF data we wanted **exists and is cleanly accessible** — and it comfortably clears every acceptance threshold. The OCHA CBPF Business Intelligence **OData API** (`cbpfapi.unocha.org/vo1/odata/`), discovered through the HDX dataset `cbpf-allocations-and-contributions`, exposes a `Cluster` entity giving a per-project, per-cluster budget split. Pulled **24,219 rows (project × cluster), 2010–2026, all 34 funds, 100 % cluster-tagged, 100 % valid iso3**, enriched 100 % with project title / organization / dates from the sibling `ProjectSummary` entity. Year-total budgets reconcile to `bronze_cbpf_allocations` within **+2.8 % / +0.3 % / −7.9 %** for 2024 / 2025 / 2026. No auth, no scraping, CC BY (IGO). **Recommendation: commit the script + this note; load as a new Bronze table `bronze_cbpf_projects`.**

## What was acquired

- **Source**: OCHA CBPF BI **OData v3 API** — `https://cbpfapi.unocha.org/vo1/odata/`
  - Primary entity: `Cluster` (`ExcelClusterBase`) — per-project, per-cluster budget split.
  - Joined: `Poolfund` (fund → recipient `CountryCode`) and `ProjectSummary` (project title / org / dates; 1:1 on project code).
- **Discovered via**: HDX dataset `cbpf-allocations-and-contributions` (`data.humdata.org/dataset/cbpf-allocations-and-contributions`), whose resource list publishes this same OData service plus a `global_cbpf_project_summary.csv` (project-grain but **no cluster column** — which is why the OData `Cluster` entity is the real source here).
- **Publisher**: OCHA CBPF. **License**: CC BY (IGO) (`license_id: cc-by`). **Refresh cadence**: `data_update_frequency: 30` (monthly). **Auth**: none.
- **Output**: `./staging/cbpf_projects.csv` (~8.2 MB, 24,219 rows). Metadata snapshot: `./staging/_cbpf_projects_meta.json` (CKAN `package_show` + OData lineage + fund-iso3 flags + counts).
- **Script**: `src/acquisition/acquire_cbpf_projects.py` (`--check`, `--no-enrich`).

## Verified schema (18 columns, 24,219 rows)

| Column | Source field | Type | Notes |
|---|---|---|---|
| `year` | `Cluster.AllocationYear` | int | Allocation year. 2010–2026. |
| `fund_id` | `Cluster.PooledFundId` | int | Stable join key to `Poolfund.Id`; unambiguous (unlike the name). |
| `fund_name` | `Cluster.PooledFundName` | string | 34 distinct; aligns with `bronze_cbpf_allocations.PooledFund` after suffix normalization (see quirks). |
| `iso3` | derived from `Poolfund.CountryCode` | string | alpha-2 → alpha-3 via pycountry; 2 overrides. 100 % valid. |
| `country_name` | pycountry canonical | string | From iso3. |
| `cluster` | `Cluster.Cluster` | string | IASC cluster. 15 distinct, 0 null. |
| `sub_cluster` | `Cluster.SubCluster` | string | Sparse (6.2 % populated) — normal; most CBPF lines are cluster-only. |
| `cluster_percentage` | `Cluster.Percentage` | float | Cluster's share of the project budget. |
| `amount_usd` | `Cluster.ClusterBudget` | float | **This cluster's USD slice** of the project budget. 0 null. |
| `allocation_window` | `Cluster.AllocationSourceName` | string | `standard` (15,115) / `reserve` (9,104) — joins back to `bronze_cbpf_allocations.AllocationType`. |
| `project_code` | `Cluster.ChfProjectCode` | string | Unique project key (e.g. `SSD-18/HSS10/SA2/FSL/UN/10025`). |
| `chf_id` | `Cluster.ChfId` | int | Internal project id (per-fund, not globally unique). |
| `project_title` | `ProjectSummary.ProjectTitle` | string | 100 % filled. |
| `recipient_organization` | `ProjectSummary.OrganizationName` | string | 100 % filled. |
| `recipient_organization_type` | `ProjectSummary.OrganizationType` | string | UN Agency / International NGO / National NGO / RedCross-RedCrescent. |
| `project_status` | `ProjectSummary.ProjectStatus` | string | e.g. Project Closed, Project Closure, Ongoing. |
| `actual_start_date` | `ProjectSummary.ActualStartDate` | date (YYYY-MM-DD) | Empty where source carries the `0001-01-01` null sentinel. |
| `actual_end_date` | `ProjectSummary.ActualEndDate` | date (YYYY-MM-DD) | Same null handling. |

## Verified facts (directly checked, not inferred)

- **Grain is project × cluster.** 24,219 rows over 16,796 distinct projects. A project split across N clusters yields N rows; `amount_usd` is the per-cluster slice and `cluster_percentage` its share.
- **Cluster non-null: 24,219 / 24,219 = 100.00 %.** (Threshold: ≥90 %.)
- **iso3 valid alpha-3: 24,219 / 24,219 = 100.00 %** with two overrides applied. (Threshold: ≥95 %.)
- **`amount_usd` non-null: 24,219 / 24,219.**
- **Fund coverage: 33 / 34** of the known `bronze_cbpf_allocations` funds appear (after name normalization). (Threshold: ≥30.) The only missing one is **`Honduras (RhPF-LAC)`** — a brand-new 2026 fund with a $63.2 M bronze allocation but **no projects yet entered** in GMS (timing, not a data gap).
- **ProjectSummary enrichment: 100 %.** Every `Cluster` row matched a `ProjectSummary` record (the 16,796 projects in `Cluster` are exactly the `ProjectSummary` set). `ProjectSummary` is **1:1 on `ChfProjectCode`** (8,000/8,000 unique in the verified sample).
- **Year coverage 2010–2026** (we only have 2018–2026 in bronze; this extends earlier).
- **15 cluster values, all IASC-recognizable** (see taxonomy alignment below).

### Year-total reconciliation vs `bronze_cbpf_allocations` (2024–2026)

Sum of `amount_usd` by year vs deduped `Budget` by `Year`:

| Year | bronze Budget | CBPF projects Σ | diff |
|---|---|---|---|
| 2024 | 915,947,123 | 941,917,192 | **+2.8 %** |
| 2025 | 1,027,341,831 | 1,030,637,077 | **+0.3 %** |
| 2026 | 2,074,528,200 | 1,911,522,187 | **−7.9 %** |

All within ±15 %. The 2026 shortfall is in-year incompleteness — see quirks.

## Quirks worth knowing about

**Fund names differ only by regional suffix.** `bronze_cbpf_allocations.PooledFund` uses regional-window suffixes the OData `PooledFundName` omits or styles differently. Same money, different string:

| bronze `PooledFund` | OData `PooledFundName` |
|---|---|
| `Bangladesh (AP-RHPF)` | `Bangladesh` |
| `Burkina Faso (RhPF-WCA)` | `Burkina Faso` |
| `Chad (RhPF-WCA)` | `Chad (RhPF)` |
| `Colombia (RhPF-LAC)` | `Colombia (RhPF)` |
| `Haiti (RhPF-LAC)` | `Haiti (RhPF)` |
| `Kenya (ESAHF)` | `Kenya` |
| `Mali (RhPF-WCA)` | `Mali` |
| `Mozambique (RhPF)` | `Mozambique (RhPF)` |
| `Niger (RhPF-WCA)` | `Niger` |
| `Uganda (ESAHF)` | `Uganda` |

**Join on `fund_id` (= `Poolfund.Id`), not the name.** The name is ambiguous: `Colombia` (Id 52, 2013–2017) and `Colombia (RhPF)` (Id 87, 2024–2026) are *different* funds that normalize to the same base; likewise `Haiti` (54) vs `Haiti (RhPF)` (88) and `Pakistan` (60) vs `Pakistan (AP-RHPF)` (97). For a `bronze` join with no id, a documented name-variant map is required.

**Two `Poolfund.CountryCode` values are wrong/placeholder at source** (overridden in the script, flagged in the meta json):
- `Mozambique (RhPF)` (Id 89) is coded `LI` (Liechtenstein) → corrected to **MOZ**.
- `Syria Cross border` (Id 70) carries `XX` → mapped to **SYR** (operated cross-border from Turkey; recipient population is Syrian). Note this makes **two funds share iso3 SYR** (`Syria` Id 62 + `Syria Cross border` Id 70) — keep them distinct at fund grain, combine only at iso3 grain.

**Per-fund (year, fund) discrepancies > ±15 % exist even where names match.** These are allocation-announced (bronze) vs project-approved-and-entered-in-GMS (this source) **timing differences**, concentrated in the current year:
- 2026 (mid-year as of acquisition): `Honduras`, `Mali`, `Pakistan`, `Venezuela` have bronze allocations but **0** entered projects; `Guatemala` −83.8 %, `CAR` −54.7 %, `Afghanistan` −20.0 %. This drives the −7.9 % year total.
- 2024–2025 residuals in the 15–27 % band: `Afghanistan` (−15.1 %), `Ethiopia` (+16.8 %), `oPt` (+26.7 %), `Syria` (−16.6 % / +21.1 %), `Ukraine` (+21.7 %), small `Colombia` fund (−18.8 % / −17.8 %). Allocation envelope vs sum of approved project budgets; revisions; rounding on small funds.

**Year-total reconciliation is clean (±2.8 %) once the per-fund timing noise nets out** — so the two sources cover the same money; they just differ on *when* a dollar moves from "announced" to "approved project."

**`amount_usd` is approved project budget, current USD, no inflation adjustment** — consistent with the FTS/CERF convention in `docs/schemas.md`.

## Sector taxonomy alignment with `silver_sector_crosswalk`

13 of 15 CBPF cluster names map cleanly to an existing crosswalk row (matching `fts_globalcluster_name` or a listed `fts_cluster_variants` value). **2 need a new variant string added** to the crosswalk's `fts_cluster_variants` (these are crosswalk additions, **not** data-quality issues), and the `cbpf_category` column — currently empty for every crosswalk row — can now be populated from this source.

| CBPF `cluster` | Maps to harmonized | Status |
|---|---|---|
| `Water, Sanitation and Hygiene` | WASH | clean (listed variant) |
| `Protection` | Protection | clean |
| `Health` | Health | clean |
| `Food Security` | Food Security | clean |
| `Emergency Shelter and NFI` | Shelter and NFI | clean (= `fts_globalcluster_name`) |
| `Nutrition` | Nutrition | clean |
| `Education` | Education | clean |
| `Camp Coordination / Management` | Camp Coordination and Camp Management | clean (= `fts_globalcluster_name`) |
| `Early Recovery` | Early Recovery | clean |
| `Coordination and Support Services` | Coordination and Support Services | clean (listed variant) |
| `Logistics` | Logistics | clean |
| `COVID-19` | COVID-19 | clean (crosswalk says reassign to Health post-2023; 48 rows here) |
| `Emergency Telecommunications` | Emergency Telecommunications | clean |
| `Multi-purpose CASH` | Multipurpose Cash | **add variant** `Multi-purpose CASH` (current variants: `Multipurpose Cash \| MPCA \| Multi-purpose cash assistance`) |
| `Multi-Sector` | Multi-sector | **add variant** `Multi-Sector` (current variants lack this exact casing) |

`sub_cluster` (6.2 % populated) was **not** profiled against the crosswalk's Protection sub-cluster rows (`PRO-CPN`, `PRO-GBV`, `PRO-MIN`, `PRO-HLP`, `PRO-HTS`); if sub-cluster granularity is wanted later, profile it then.

## Coverage tables

### Per year

| Year | rows | Σ amount_usd |
|---|---:|---:|
| 2010 | 36 | 19,895,425 |
| 2011 | 227 | 84,948,951 |
| 2012 | 172 | 89,707,880 |
| 2013 | 212 | 72,878,885 |
| 2014 | 819 | 333,101,680 |
| 2015 | 1,175 | 487,978,889 |
| 2016 | 1,538 | 719,048,265 |
| 2017 | 1,664 | 697,946,281 |
| 2018 | 1,800 | 836,907,056 |
| 2019 | 2,110 | 1,028,396,745 |
| 2020 | 1,903 | 913,386,730 |
| 2021 | 2,184 | 1,029,519,241 |
| 2022 | 2,385 | 1,213,416,554 |
| 2023 | 2,176 | 1,141,910,673 |
| 2024 | 2,247 | 941,917,192 |
| 2025 | 2,727 | 1,030,637,077 |
| 2026 | 844 | 1,911,522,187 (partial year; large new envelopes already approved) |

### Per fund (iso3, rows, Σ amount_usd, year span)

| fund_name | iso3 | rows | Σ amount_usd | years |
|---|---|---:|---:|---|
| Afghanistan | AFG | 1,592 | 1,078,683,042 | 2014–2026 |
| Bangladesh | BGD | 36 | 145,896,619 | 2026 |
| Burkina Faso | BFA | 338 | 72,479,210 | 2022–2025 |
| CAR | CAF | 1,064 | 296,372,254 | 2014–2026 |
| Chad (RhPF) | TCD | 67 | 107,888,999 | 2025–2026 |
| Colombia | COL | 81 | 9,055,308 | 2013–2017 |
| Colombia (RhPF) | COL | 97 | 101,438,987 | 2024–2026 |
| DRC | COD | 1,347 | 790,691,122 | 2013–2026 |
| El Salvador | SLV | 17 | 24,200,000 | 2026 |
| Ethiopia | ETH | 1,989 | 857,029,492 | 2013–2026 |
| Fiji | FJI | 1 | 350,000 | 2026 |
| Guatemala | GTM | 10 | 9,450,000 | 2026 |
| Haiti | HTI | 38 | 7,391,174 | 2013–2015 |
| Haiti (RhPF) | HTI | 69 | 130,183,258 | 2024–2026 |
| Iraq | IRQ | 560 | 367,412,945 | 2015–2022 |
| Jordan | JOR | 206 | 61,663,592 | 2015–2022 |
| Kenya | KEN | 23 | 48,481,145 | 2026 |
| Lebanon | LBN | 847 | 276,500,007 | 2015–2026 |
| Mali | MLI | 84 | 17,559,553 | 2023–2025 |
| Mozambique (RhPF) | MOZ | 67 | 80,087,877 | 2025–2026 |
| Myanmar | MMR | 1,256 | 349,261,608 | 2013–2026 |
| Niger | NER | 176 | 46,251,076 | 2021–2025 |
| Nigeria | NGA | 765 | 350,364,373 | 2017–2026 |
| Pakistan | PAK | 280 | 64,204,577 | 2013–2025 |
| Somalia | SOM | 2,302 | 842,009,817 | 2010–2025 |
| South Sudan | SSD | 1,958 | 794,137,167 | 2015–2026 |
| Sudan | SDN | 2,135 | 1,114,659,500 | 2013–2026 |
| Syria | SYR | 1,007 | 658,914,025 | 2015–2026 |
| Syria Cross border | SYR | 1,822 | 1,134,448,765 | 2014–2025 |
| Uganda | UGA | 22 | 72,899,993 | 2026 |
| Ukraine | UKR | 1,036 | 996,081,958 | 2019–2026 |
| Venezuela | VEN | 382 | 54,591,078 | 2021–2025 |
| Yemen | YEM | 1,678 | 1,181,157,918 | 2013–2025 |
| oPt | PSE | 867 | 411,323,274 | 2013–2025 |

**Missing vs the 34 bronze funds:** `Honduras (RhPF-LAC)` only (new 2026 fund, no projects entered yet). Bronze `Pakistan` and `Pakistan (AP-RHPF)` both collapse to OData `Pakistan` (Id 60); `Yemen` 2026 and `Venezuela`/`Mali` 2026 bronze allocations have no projects entered yet.

## Open questions

- **`Honduras (RhPF-LAC)`**: re-pull after GMS catches up (monthly refresh) once 2026 projects are entered; expect it to appear then.
- **bronze ↔ OData fund key**: bronze has no `fund_id`. Either (a) build the name-variant map above into `silver_fund_country_map`, or (b) prefer this OData source's `fund_id` as canonical and treat bronze as the legacy aggregate. (b) is cleaner if we adopt `bronze_cbpf_projects`.
- **`sub_cluster`** Protection sub-clusters not yet profiled against crosswalk `PRO-*` rows.
- **Per-fund > 15 % timing residuals** in 2024–2025 (`oPt`, `Ukraine`, `Syria`, `Ethiopia`): confirm with OCHA whether bronze `Budget` is the *announced envelope* and `ClusterBudget` the *approved-project* sum — that's the most likely explanation but unverified.

## Next steps (recommendation)

**Load as a new Bronze table `bronze_cbpf_projects`** (project × cluster grain), *not* a join into `bronze_cbpf_allocations` — the grains differ (this is per-project-per-cluster; that is per-fund-per-window-aggregate) and this source extends back to 2010 with far richer attribution. The existing `bronze_cbpf_allocations` stays as the fund/year/window aggregate; the two reconcile at year-total level and join on (`year`, `fund_id`/normalized fund, `allocation_window`).

Downstream: `silver_cbpf_projects` → crosswalk `cluster` to harmonized sector → feed `gold_sector_coverage` (CBPF's sectoral contribution per country/cluster) and the optional **CBPF Allocation View** screen. Refresh is a trivial monthly re-run of the script (no credentials).
