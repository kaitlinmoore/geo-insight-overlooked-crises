# Agent tool inventory

The supervisor agent (Mosaic AI ChatAgent) routes user queries to specialist
subsystems: Genie spaces for natural-language SQL over Gold tables, and these
Unity Catalog Functions for parameterized analytical queries. The supervisor
selects a UC Function by reading its `COMMENT` string — quality of the COMMENTs
drives tool-selection accuracy.

All 11 functions live in `geo_insight.agent.*` (registered by
[register_uc_functions.py](register_uc_functions.py)). Each is a SQL function;
none requires Python execution. All are re-runnable (`CREATE OR REPLACE`).

## Quick reference

| # | Function | Gold table(s) | Sample question the agent should fire it on |
|---|---|---|---|
| 1 | `get_country_ranking(iso3, year)` | `gold_forgotten_crisis_index` (+ `silver_needs` for PIN) | *"Where does Sudan rank in 2026?"* / *"Is Yemen still overlooked?"* |
| 2 | `list_top_overlooked(year, limit_n, region)` | `gold_forgotten_crisis_index` (+ `silver_country_dim` for region) | *"What are the most overlooked crises right now?"* / *"Top 10 forgotten African crises."* |
| 3 | `get_funding_funnel(iso3, year)` | `gold_funding_funnel` | *"How much of Yemen's 2025 requirement was actually paid?"* |
| 4 | `get_sector_coverage(iso3, year, only_flagged)` | `gold_sector_coverage` | *"Which sectors are critically underfunded in DRC?"* / *"Is health funded in Sudan?"* |
| 5 | `get_funding_trend(iso3, start_year, end_year)` | `gold_funding_trend` + `gold_funding_funnel` | *"Has Yemen always been this underfunded?"* / *"When did Sudan's gap start widening?"* |
| 6 | `get_score_decomposition(iso3, year)` | `gold_explanation_features` (unpivoted) | *"Why does Burkina Faso rank where it does?"* / *"Which components drove Sudan's score?"* |
| 7 | `get_donor_concentration(iso3, year)` | `silver_fts_flows` (per-donor) + `gold_donor_concentration` (HHI/top-3) | *"Who's funding Yemen?"* / *"Is this crisis dependent on a single donor?"* |
| 8 | `compare_countries(iso3_csv, year)` | `gold_forgotten_crisis_index` (multi-iso) | *"How does Sudan compare to Burkina Faso and Yemen?"* |
| 9 | `get_ranking_delta(iso3, from_year, to_year)` | `gold_forgotten_crisis_index` (self-join) | *"Is Burkina Faso getting more or less overlooked?"* / *"Did Sudan move up the rankings since 2024?"* |
| 10 | `get_regional_cluster(iso3, year)` *(stretch)* | `gold_cross_border_patterns` | *"Is the Sahel crisis worse this year?"* / *"Are Burkina Faso's neighbours also overlooked?"* |
| 11 | `get_subnational_breakdown(iso3, year)` *(stretch)* | `gold_subnational_index` | *"Where in Sudan is the crisis worst?"* / *"Are some regions of Yemen more underfunded than others?"* |

## Design notes

**Tool-selection accuracy lives in the COMMENT.** The supervisor's tool
selector reads the function `COMMENT` (and the parameter `COMMENT`s where
present), not the schema name. Each COMMENT therefore (a) names the user-
facing question type, (b) gives one or two example phrasings, (c) calls out
the bounds and caveats the agent must respect when formatting the answer (CIs
on every rank; negative sign on `media_attention`; `is_inference_flagged` on
subnational funding).

**Some functions adapt the Gold-table shape.** A few of the agent surfaces
don't match a single Gold table column-for-column — the spec asks for a long-
form decomposition that is stored wide, or a per-donor breakdown where the
Gold table is the country-level aggregate. Those functions either UNPIVOT
(function 6) or recompute from Silver and join the aggregate back in
(function 7). The Gold tables themselves are unchanged.

**No "answer formatting" in the function.** The functions return numbers and
classifications — the agent decides whether to lead with rank or with score,
whether to flag the CI as narrow or wide, whether to format USD as millions.
A function that pre-baked phrasing would constrain the agent and risk
inconsistency across answers. Keep the surface declarative.

**SQL-only by design.** Every function here is a pure SQL `RETURN TABLE`.
Python UC Functions are reserved for the Day-4 stretch tools that need real
computation (e.g. ACLED DBSCAN clustering for `gold_hotspots`).

## Re-running

The notebook is fully re-runnable. `CREATE SCHEMA IF NOT EXISTS` is a no-op
when the schema exists; `CREATE OR REPLACE FUNCTION` overwrites in place. The
verification cells at the bottom list everything in `geo_insight.agent.*` and
print each function's `DESCRIBE FUNCTION EXTENDED` output — the COMMENT
strings should be reviewed there before any supervisor deployment.

## Open items

- **`compare_countries` parameter shape.** Currently takes a comma-separated
  string. `ARRAY<STRING>` is the Unity-Catalog-native alternative; see the
  notes in the registration session report.
- **`get_country_ranking` granularity.** Possible split into "ranking-only"
  vs. "ranking-plus-context" for finer supervisor tool selection — same
  report.
- **Pre-deployment**: Gold tables must exist and be populated. The
  `register_uc_functions.py` notebook will succeed against an empty Gold
  schema (it only registers function definitions), but every function will
  return zero rows until the upstream pipelines run.
