# Databricks Workspace Artifacts

Inventory of the Unity Catalog assets, Mosaic AI components, MLflow experiments, and Vector Search endpoint that back this submission. Each entry includes a brief description, the reproduction path (the notebook or script that creates it), and a verification query where applicable.

The submission ran on a personal Databricks trial workspace; reviewers can't access it directly. Verification artifacts — MLflow run exports, schema snapshots, screenshots, demo video — are packaged at `/evidence/` for offline review.

---

## Catalog

**Name:** `geo_insight`
**Metastore:** AWS us-east-2
**Storage:** Default Storage (workspace-scoped)
**Created by:** `register_catalog_and_schemas` (one-time provisioning; documented in `STATE.md`)

### Schemas

| Schema | Purpose | Table count |
|---|---|---|
| `raw` | Volume for staging files (`geo_insight.raw.staging`) | n/a (volume) |
| `bronze` | Verbatim, append-only loaders from `geo_insight.raw.staging` | 19 |
| `silver` | DLT-managed cleaned + harmonized tables with quality contracts | 16 |
| `gold` | Methodology computation outputs in transparent SQL | 12 |
| `agent` | Unity Catalog Functions backing the supervisor agent's tool calls | 11 |

### Verification queries

```sql
-- Catalog exists
SHOW CATALOGS LIKE 'geo_insight';

-- Schemas
SHOW SCHEMAS IN geo_insight;

-- Bronze table count
SELECT COUNT(*) FROM information_schema.tables
WHERE table_catalog = 'geo_insight' AND table_schema = 'bronze';

-- Should return 19 (or 18 with bronze_fieldmaps_boundaries deferred per
-- serverless adaptation; see DECISIONS.md).
```

---

## Bronze layer — verbatim source ingestion

19 loader notebooks at `notebooks/bronze/`. Each reads from `geo_insight.raw.staging/` (Unity Catalog volume) and writes append-only to `geo_insight.bronze.bronze_<source>`.

| Table | Source | Rows | Loader |
|---|---|---|---|
| `bronze_hno` | HPC HNO 2024-2026 | TBD | `bronze_hno.py` |
| `bronze_hrp` | OCHA HRP plans | ~900 | `bronze_hrp.py` |
| `bronze_fts_plan` | FTS plan-level requirements + funding | ~3,800 | `bronze_fts_plan.py` |
| `bronze_fts_cluster` | FTS country-cluster (962 cluster name variants) | ~8,000 | `bronze_fts_cluster.py` |
| `bronze_fts_globalcluster` | FTS IASC global cluster taxonomy | ~10,600 | `bronze_fts_globalcluster.py` |
| `bronze_fts_flows` | FTS incoming + outgoing + internal flows | ~14,700 | `bronze_fts_flows.py` |
| `bronze_inform_severity` | ACAPS INFORM Severity monthly snapshots | TBD | `bronze_inform_severity.py` |
| `bronze_cod_population` | UN COD admin0 + admin1 population (long format) | ~98,000 | `bronze_cod_population.py` |
| `bronze_cod_population_admin2` | UN COD admin2 population (cod-ps-global) | ~1M | `bronze_cod_population_admin2.py` |
| `bronze_cbpf_allocations` | CBPF outflow allocations 2018-2026 | ~700 | `bronze_cbpf_allocations.py` |
| `bronze_cbpf_contributions` | CBPF donor contributions 2018-2026 | ~2,100 | `bronze_cbpf_contributions.py` |
| `bronze_cbpf_projects` | CBPF project × cluster grain from OCHA OData API | ~24,200 | `bronze_cbpf_projects.py` |
| `bronze_cerf_allocations` | CERF allocations 2006-2026 (RR + UFE) | ~8,500 | `bronze_cerf_allocations.py` |
| `bronze_acled_events` | ACLED point-level conflict events 2020-present | ~736,600 | `bronze_acled_events.py` |
| `bronze_acled_severity` | ACLED admin2 × month aggregates 2020-present | ~942,100 | `bronze_acled_severity.py` |
| `bronze_echo_fca` | DG ECHO Forgotten Crises Assessment lists 2015-2026 | ~200 | `bronze_echo_fca.py` |
| `bronze_nrc_neglected` | NRC Most Neglected Displacement Crises lists | ~90 | `bronze_nrc_neglected.py` |
| `bronze_reliefweb_situation_reports` | ReliefWeb situation reports (+ metadata + media attention) | 500 docs + 47K metadata + 900 attention cells | `bronze_reliefweb_situation_reports.py` |
| `bronze_country_borders` | GeoNames country adjacency (CC-BY) | 252 | `bronze_country_borders.py` |

**Deferred from v1 (serverless adaptation):** `bronze_fieldmaps_boundaries`. Sedona JVM library required; not available on serverless trial. Boundary geometry served to frontend as static GeoJSON via `src/acquisition/extract_geojson.py`; country adjacency via GeoNames `bronze_country_borders` above. See `DECISIONS.md` "Serverless deployment" entry.

### Bronze contracts

Every Bronze table carries:
- `_ingested_at` (timestamp) — load wall-clock
- `_source_file` (string) — originating source file path

Bronze is append-only and verbatim: no filtering, no HXL-row removal, no type-casting. Silver handles those.

---

## Silver layer — cleaned + harmonized

16 DLT-managed tables at `notebooks/silver/`. Single triggered DLT pipeline (`geo_insight_silver`) runs them all with declarative `@dlt.expect` quality contracts.

Notable tables:

| Table | Purpose |
|---|---|
| `silver_country_dim` | Country dimension with iso3 ↔ iso_numeric ↔ name ↔ region |
| `silver_fund_country_map` | CBPF fund_name ↔ iso3 mapping (manual + OData-validated) |
| `silver_sector_crosswalk` | Harmonize HNO cluster ↔ FTS sector ↔ CBPF cluster |
| `silver_fts_flows` | Multi-country flow cascade (requirements-weighted, population-weighted fallback) |
| `silver_severity` | INFORM annual rollup (max severity_index, modal category_max) |
| `silver_acled_events` | H3 res-5 indexed point events |
| `silver_acled_severity` | Admin2 × month conflict aggregates (current-coverage) |
| `silver_subnational_needs` | Admin1 P-code rollup from HNO admin2 |
| `silver_media_attention` | ReliefWeb annual report counts, within-year percentile rank |
| `silver_cbpf_projects` | Country × year × harmonized_sector CBPF funding |

**Deferred from v1:** `silver_boundaries` (Sedona dependency). Stub at `notebooks/silver/silver_boundaries.py` documents the deferment.

### DLT pipeline

- **Name:** `geo_insight_silver`
- **Mode:** Triggered
- **Compute:** Serverless
- **Source notebooks:** `/Workspace/Users/<kmoore>/geo-insight-overlooked-crises/notebooks/silver/`
- **Target schema:** `geo_insight.silver`
- **Channel:** Current
- **Quality contracts:** `@dlt.expect_or_drop` (invalid rows dropped), `@dlt.expect` (warn-and-keep / quarantine), `@dlt.expect_or_fail` (halt pipeline on contract violation)

---

## Gold layer — methodology computation

12 notebooks at `notebooks/gold/`. Each writes a Delta table with the methodology's output for one analytical question.

| Table | Purpose | Reads |
|---|---|---|
| `gold_forgotten_crisis_index` | Headline ranking with composite score + bootstrap CI + neglect_class | All Silver |
| `gold_funding_funnel` | Four-stage funding funnel (required → pledged → committed → paid) per country/year | `silver_fts_flows` |
| `gold_sector_coverage` | Per-sector funding coverage with critical-gap flag | `silver_fts_globalcluster`, `silver_cbpf_projects`, `silver_subnational_needs` |
| `gold_funding_trend` | Multi-year funding trend per country with chronic_index | `silver_fts_flows` |
| `gold_donor_concentration` | Top-3 share + HHI per country/year (from FTS donor identity) | `silver_fts_flows` |
| `gold_explanation_features` | Seven-component decomposition per country/year | Multiple Silver |
| `gold_change_indicators` | Year-over-year rank delta | `gold_forgotten_crisis_index` |
| `gold_subnational_index` | Admin1-level simplified ranking | `silver_subnational_needs` |
| `gold_cross_border_patterns` | Regional crisis cluster groupings | `bronze_country_borders`, `gold_forgotten_crisis_index` |
| `gold_ufe_validation` | Layer-1 validation: UFE precision/recall on held-out window | `gold_forgotten_crisis_index`, `silver_ufe_label` |
| `gold_external_overlap` | Layer-2 validation: ECHO FCA + NRC overlap analysis | `gold_forgotten_crisis_index`, `bronze_echo_fca`, `bronze_nrc_neglected` |
| `gold_bootstrap_ci` | Layer-3 validation: 500-resample bootstrap CIs per country | Multiple Silver |

### Gold contracts

- **Self-check:** `gold_explanation_features` contributions sum to `gold_forgotten_crisis_index.overlooked_score` per row (enforced at build time)
- **DQ assertions:** every Gold notebook calls `assert_expectations` post-write
- **Time-versioning:** Delta time-travel preserved; supports future alert subscriptions (deferred)

---

## Agent layer — Unity Catalog Functions

11 UC Functions at `notebooks/agent/register_uc_functions.py` in `geo_insight.agent.*`. Each function wraps a parameterized SQL query against Gold; the supervisor agent reads function COMMENT strings to decide which tool fires for a given user question.

| Function | Backs |
|---|---|
| `get_country_ranking(iso3, year)` | Single-country ranking + CI lookups |
| `list_top_overlooked(year, limit, region)` | Top-N headline triage |
| `get_funding_funnel(iso3, year)` | Four-stage funnel detail |
| `get_sector_coverage(iso3, year, only_flagged)` | Per-sector coverage; critical-gap filter |
| `get_funding_trend(iso3, start_year, end_year)` | Multi-year trend, chronic-vs-acute |
| `get_score_decomposition(iso3, year)` | Seven-component decomposition (the explainability backbone) |
| `get_donor_concentration(iso3, year)` | Per-donor + HHI + top-3 share |
| `compare_countries(iso3_csv, year)` | Side-by-side comparison |
| `get_ranking_delta(iso3, from_year, to_year)` | Year-over-year change |
| `get_regional_cluster(iso3, year)` | Regional cluster (sahel_g5, horn_of_africa, etc.) |
| `get_subnational_breakdown(iso3, year)` | Admin1 breakdown when available |

### Verification

```sql
SHOW FUNCTIONS IN geo_insight.agent;
DESCRIBE FUNCTION EXTENDED geo_insight.agent.get_country_ranking;
```

Documented at `notebooks/agent/README.md` with question-to-function mapping.

---

## Supervisor agent — Mosaic AI

**Endpoint name:** `geo_insight_supervisor`
**Framework:** Mosaic AI Agent Framework (ChatAgent)
**Tools:** the 11 UC Functions above + 3 Genie spaces (below)
**Tracing:** MLflow Tracing on every invocation
**Reproduction:** `notebooks/agent/build_supervisor.py` (TBD if not yet built)

The supervisor selects between Genie (open-ended natural language → SQL) and UC Functions (structured tool calls) based on the user's question. Tool selection is driven by the COMMENT strings.

---

## Genie spaces

Three spaces, each scoped to a specific analytical domain. Each is a Databricks-native natural-language-to-SQL surface over the relevant Gold + Silver tables.

| Space | Scope | Backing tables |
|---|---|---|
| `geo_insight_rankings` | Composite scores, rankings, neglect classifications | `gold_forgotten_crisis_index`, `gold_explanation_features` |
| `geo_insight_funding` | Funding gaps, funnels, sector coverage, donor identity | `gold_funding_funnel`, `gold_sector_coverage`, `gold_donor_concentration`, `silver_fts_flows` |
| `geo_insight_context` | Severity, conflict events, population, subnational | `silver_severity`, `silver_acled_severity`, `silver_population`, `gold_subnational_index` |

Each space is configured with curated example queries, table descriptions, and synonyms. Configuration at `notebooks/agent/genie_spaces/` (TBD if not yet committed).

---

## Vector Search endpoint

**Endpoint:** `geo_insight_kb` (deferred — Day 4 stretch)
**State:** Provisioned and Online
**Used by:** Knowledge Assistant over ReliefWeb situation reports (`bronze_reliefweb_situation_reports`)
**Status:** Endpoint up; index not yet populated. KA deferred per `DECISIONS.md`; corpus available for v2 activation.

---

## MLflow

**Experiment:** `/Workspace/Users/<kmoore>/geo_insight_eval`
**Runs of interest:** see `/deliverables/mlflow_runs.md`

Two run types:
1. **Eval runs** — `mlflow.evaluate()` against the seven RAI judges on the eval set (`notebooks/evaluation/eval_set.json`). Aggregated scores feed the Methodology screen's RAI Scorecard.
2. **Production traces** — every supervisor agent invocation generates an MLflow Trace. Captured during the demo recording session for evidence.

---

## Reproduction order

To rebuild this workspace from the repo:

1. Provision a Databricks workspace (any tier with Unity Catalog + Mosaic AI).
2. Run `bash` against the repo's `infra/provision_catalog.sh` (or equivalent — the catalog/schema/volume creation block from the trial setup chat history).
3. Upload `staging/` and `data/databricks_data/unocha/` contents to the volume via `databricks fs cp -r`.
4. Reorganize the volume into subdirectories matching loader widget defaults (run `notebooks/utils/reorganize_staging_volume.py`).
5. Run `notebooks/utils/run_all_bronze.py`. ~20-45 minutes serverless.
6. Run the Silver DLT pipeline (`geo_insight_silver`). ~10-15 minutes.
7. Run Gold notebooks via `notebooks/utils/run_all_gold.py` (TBD if not yet committed) or open them individually. Order: `gold_sector_coverage` → `gold_forgotten_crisis_index` → others. ~20-30 minutes.
8. Register UC Functions: run `notebooks/agent/register_uc_functions.py`. ~30 seconds.
9. Configure Genie spaces from `notebooks/agent/genie_spaces/`. UI-driven; ~10 minutes.
10. Deploy supervisor agent: run `notebooks/agent/build_supervisor.py`. ~5 minutes (Model Serving spin-up).
11. Run eval: `notebooks/evaluation/run_eval.py`. ~5-10 minutes.

Total reproduction: ~90 minutes from a fresh Databricks workspace.

---

## Workspace IDs and identifiers

For reviewers verifying via `/evidence/` packaging:

- **Catalog ID:** ababc8e3-b785-4ee0-9efa-f6ff613f7a4b (per UC metastore)
- **Metastore ID:** 3606a07d-5b09-438a-9e7b-fade6d5ca1af (AWS us-east-2)
- **Volume ID:** 403c66bc-f379-4299-8636-c46ab446fd7e
- **Storage path:** `s3://dbstorage-prod-qguob/uc/.../volumes/403c66bc.../`

These identifiers persist across schema dumps in `/evidence/` so reviewers can verify the artifact is the one this writeup describes.
