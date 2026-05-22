# Frontend → Databricks adapter handoff

> The frontend FastAPI layer at `frontend/server/` currently returns `mock_data.py` fixtures.
> The adapter session replaces those builders with Databricks SQL Connector queries returning the same Pydantic models.
> Read this doc once at the start of that session; it captures the eight contract items the adapter must honor.

## Scope

The frontend session (2026-05-22) wired six React screens to a typed FastAPI layer with eight `/api/v1/` endpoints, all returning Pydantic v2 models that mirror the TypeScript types in `frontend/src/lib/types.ts`. Every endpoint currently returns mock fixtures from `frontend/server/mock_data.py`.

The Databricks adapter session replaces every builder in `mock_data.py` with a Databricks SQL Connector query against the corresponding Gold (or Silver) table, returning the same Pydantic shape. The Pydantic models themselves don't change. What changes is the source of the data inside them.

This doc lists the contract items the adapter must honor — places where the frontend session resolved ambiguity in the original schema, made data-shape decisions beyond what `docs/schemas.md` specified, or built mock data that needs careful real-data assembly. Each item is small. None require methodology changes.

Reference for the adapter session:

- `frontend/server/models.py` — the Pydantic source of truth.
- `frontend/server/mock_data.py` — the current builder layer to swap.
- `frontend/server/main.py` — the eight FastAPI endpoints.
- `frontend/src/lib/types.ts` — the TypeScript mirror of the Pydantic models.
- `docs/schemas.md` — Gold table definitions.
- `docs/methodology.md` — the formulas.

## Endpoint ↔ Gold source map

| Endpoint | Pydantic response | Primary Gold / Silver sources |
|---|---|---|
| `GET /api/v1/rankings` | `RankingsResponse` | `gold_forgotten_crisis_index` + `gold_change_indicators` |
| `GET /api/v1/crisis/{iso3}` | `CrisisDetail` | `gold_forgotten_crisis_index` + `gold_sector_coverage` + `gold_funding_funnel` + `gold_funding_trend` + `gold_subnational_index` |
| `GET /api/v1/compare` | `CompareResponse` | `gold_forgotten_crisis_index` (per-country rows) + per-metric joins |
| `POST /api/v1/ask` | `AskExchange` | Genie REST API (separate session — see follow-up #2) |
| `GET /api/v1/methodology/cascade-distribution` | `CascadeResponse` | `silver_fts_flows.allocation_method` aggregate |
| `GET /api/v1/methodology/composite-weights` | `CompositeWeightsResponse` | Static — pull from `docs/methodology.md` |
| `GET /api/v1/cbpf/funds` | `CbpfResponse` | `silver_cbpf_allocations` + `silver_cbpf_projects` (for sector breakdown — see item 7) |
| `GET /api/v1/changes` | `ChangesResponse` | `gold_change_indicators` |

## Contract items

### 1. `SectorCoverage.is_flagged_gap` (not `flagged`)

The scaffold's `SectorCoverage.flagged` was renamed to `is_flagged_gap` to match the chart-spec name and the schemas.md column name. `gold_sector_coverage` should emit this column as `is_flagged_gap`. The flag fires when `sector_gap > 0.7 AND pin_share >= 0.10` per `docs/methodology.md`.

### 2. `FundingFunnelStage.stage` uses `"required"` (not `"requirement"`)

Standardized on `required` across the four stages: `required → pledged → committed → paid`. Also added `pct_of_requirement` per stage so the UI doesn't have to recompute it.

`gold_funding_funnel` should either expose `pct_of_requirement` per stage as a column, or the adapter computes it as `amount_usd / required_amount` per row at query time. Either works.

### 3. `score_history` (5-point sparkline series)

This is the most substantial adapter work item. The frontend renders per-country sparklines on the Triage screen showing `overlooked_score` history. The mock fixture invents a 5-point series; the real source is a time-windowed read of `gold_forgotten_crisis_index` filtered to one ISO3, one row per year, ordered ascending.

The adapter must materialize this per-country per request. Three options:

- **Inline subquery per row.** For each country in the rankings response, run `SELECT year, overlooked_score FROM gold_forgotten_crisis_index WHERE iso3 = ? AND year BETWEEN current_year - 4 AND current_year ORDER BY year`. Latency cost: N+1 queries where N is rankings list length (~10–25 countries).
- **Single batch query.** `SELECT iso3, year, overlooked_score FROM gold_forgotten_crisis_index WHERE iso3 IN (?, ?, ...) AND year BETWEEN ...`. One round-trip, group in Python.
- **Materialized view.** A `gold_score_history_5y` view that pre-rolls the trailing 5 years per country, refreshed nightly. Cheapest at request time but adds a Gold artifact.

Recommendation: start with the batch query (option 2), profile latency, then introduce a materialized view if needed. Don't pre-optimize.

### 4. `chronic_index` carries two units

The methodology defines `chronic_index` on a 0-to-~5 scale (`chronic_years × mean_chronic_gap`). The quadrant chart and the decomposition card both use the within-year percentile (0–1) from `components[]`, which is more visually comparable across countries.

The adapter should expose both:

- `CrisisRanking.components[]` includes a `ScoreComponent` with `key="chronic_index"` whose `percentile` is the within-year rank (0–1).
- The raw `chronic_index` (0–5) can be exposed separately if needed (e.g., as a tooltip or in the Methodology screen), but the UI's primary read is the percentile.

`gold_forgotten_crisis_index` already carries `chronic_index` as a `double` per `docs/schemas.md`. The percentile-rank normalization happens during composite assembly per `docs/methodology.md`. Both should land in the Pydantic response, with the percentile in `components[].percentile` and the raw value optionally exposed in a sibling field.

### 5. `CompareResponse.rankings`

The original spec for `/compare` returned `{countries, metrics}` — a per-country list and an aligned per-metric map. The frontend session added `rankings: list[CrisisRanking]` to the response because the quadrant scatter chart needs per-country scalars (PIN, gap_ratio, neglect_class) that aren't in the metric map.

The adapter should query `gold_forgotten_crisis_index` for the requested ISO3s and include the full `CrisisRanking` rows in the response. The existing `metrics` array stays alongside — the two serve different chart types on the Compare screen (metric-aligned bars vs the quadrant scatter).

### 6. CBPF `reserve_usd` / `standard_usd` split

The `CbpfAllocation` model splits allocated funding by the two `AllocationType` windows per `bronze_cbpf_allocations.AllocationType ∈ {reserve, standard}`. The adapter should aggregate `bronze_cbpf_allocations.Budget` over `(fund, year, iso3, AllocationType)` and surface the two windows as separate fields.

`silver_cbpf_allocations` already produces this aggregation per `docs/schemas.md`. The Gold layer for the CBPF view can be a thin SQL projection from Silver — no separate Gold table needed unless the Compare-style cross-fund metrics warrant one.

### 7. CBPF `sector_breakdown` — now data-recoverable

At frontend session time, `CbpfAllocation.sector_breakdown: list[Any] = []` was empty by design because CBPF carries no sector tags at the allocation level. That gap is now closed: the CBPF projects acquisition (2026-05-22) produced `bronze_cbpf_projects` with 24,219 project × cluster rows, and `silver_cbpf_projects` aggregates them to country × year × harmonized_sector via `silver_sector_crosswalk`.

The adapter should:

- Replace the `list[Any] = []` default with a real `CbpfSectorBreakdown` Pydantic model: `{harmonized_sector: str, harmonized_sector_id: str, funding_usd: float, project_count: int, share_of_total: float}`.
- Query `silver_cbpf_projects` for each fund-country pair, return the per-sector rows.
- Compute `share_of_total` as `funding_usd / sum(funding_usd)` over the parent `CbpfAllocation`.

The CBPF Allocation View screen for PFM personas becomes substantially richer at this point — instead of "Yemen Humanitarian Fund 2024: $X, 60% reserve / 40% standard," it shows the same plus per-sector breakdown ("$X across Health 30% / Food Security 25% / Protection 20% / …"). Methodology-side, this also unlocks the OCHA-vs-donors sector comparison story for the deck.

### 8. `overlooked_score` exposed but de-emphasized in UI

`CrisisRanking.overlooked_score` (the raw composite score) is present in the Pydantic response, but the UI leads with `rank_position` + `[rank_ci_low, rank_ci_high]` per the methodology's no-false-precision rule. The adapter should continue returning `overlooked_score`; the prominence decision is a frontend concern.

Practical note: if `overlooked_score` is ever surfaced in the UI (e.g., a methodology debug screen), it should be rounded to 3 decimal places at most. The bootstrap CIs on the rank are the headline uncertainty story; the score's precision is illusory.

## Operational notes for the adapter session

- Use Databricks SQL Connector (`databricks-sql-connector`); env vars for the workspace URL, HTTP path, and access token. Don't commit credentials.
- Mock-data builders in `frontend/server/mock_data.py` are deliberately structured one builder per endpoint. Swap one at a time; the typed contract makes each swap independently testable.
- Pydantic v2's `model_validate()` makes the SQL row → Pydantic conversion mechanical when column names align. Adopt a small helper: `Model.model_validate({**row, computed_field: ...})`.
- Add `mlflow.tracing.set_destination(...)` so adapter queries land in MLflow Traces for the eval suite.
- The Methodology endpoints (`/cascade-distribution`, `/composite-weights`) can stay partly-static; the cascade distribution numbers are from a `silver_fts_flows.allocation_method` aggregate (one query), and the composite weights are constants from `docs/methodology.md`.
- The frontend's React side does not change. The TypeScript types in `src/lib/types.ts` are the contract; they're already aligned with the Pydantic models.

## Out of scope for the adapter session

- The map screens (Triage choropleth, Crisis Explorer subnational map) are a separate session — they need GeoJSON extraction from `bronze_fieldmaps_boundaries` and react-map-gl wiring, neither of which is data-layer work.
- The Ask screen's Genie REST integration is its own session (the FastAPI `/ask` endpoint is currently keyword-routed mock).
- The Methodology screen's bootstrap CI visualization and the UFE/ECHO/NRC validation tables need Gold-validation tables (`gold_ufe_validation` and equivalents) — these are post-MVP if Day-4 time runs out.

## Glossary

- **Adapter** = the swap from `mock_data.py` builders to Databricks SQL queries. One builder per endpoint, returning the same Pydantic shape.
- **Pydantic contract** = `frontend/server/models.py`. The source of truth for response shapes.
- **TypeScript mirror** = `frontend/src/lib/types.ts`. Stays in sync with the Pydantic contract; the React app reads only from this file.
- **PFM** = Pooled Fund Manager persona (CBPF view primary audience per `docs/personas.md`).
- **No-false-precision rule** = the methodology principle that ranks are the visible artifact, not the underlying score. Bootstrap CIs are always shown.
