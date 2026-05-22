# Architecture

The system that ranks humanitarian crises by overlooked-ness, from raw data ingestion through user-facing experience. This document describes *how* the system is built. The *why* lives in `DECISIONS.md`; the *what it computes* lives in `docs/methodology.md`.

## System overview

The system is a four-layer agentic command center hosted on Databricks. Data flows up through medallion processing into analytical Gold tables. An agent layer exposes those tables to users through both structured (Genie) and functional (UC Functions) interfaces, orchestrated by a supervisor. A React frontend hosts six screens, calling the agent via HTTP and reading Gold tables directly via the Databricks SQL Connector. MLflow Tracing observes every agent call; seven Responsible-AI judges score outputs against rubrics.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Frontend — React + Tailwind + shadcn/ui (Databricks App, FastAPI)      │
│                                                                          │
│  ┌────────┐ ┌──────────────┐ ┌─────────┐ ┌──────┐ ┌───────────┐ ┌─────┐ │
│  │ Triage │ │Crisis Explorer│ │ Compare │ │ Ask  │ │Methodology│ │CBPF │ │
│  └────────┘ └──────────────┘ └─────────┘ └──────┘ └───────────┘ └─────┘ │
└──────────┬──────────────────────────────────────────────┬───────────────┘
           │ HTTP                          SQL Connector  │
           │                                              │
┌──────────▼──────────────────────────────┐               │
│  Supervisor Agent (Mosaic AI ChatAgent)  │               │
│  Model Serving endpoint                  │               │
└────┬──────────────┬──────────────┬───────┘               │
     │              │              │                       │
┌────▼─────┐  ┌────▼─────────┐  ┌─▼──────────────┐         │
│  Genie   │  │ UC Functions │  │ Knowledge      │         │
│  Spaces  │  │  (7+ tools)  │  │ Assistant      │         │
│  (3-4)   │  │              │  │  (Day 4 stretch)│        │
└────┬─────┘  └────┬─────────┘  └─┬──────────────┘         │
     │             │              │                        │
     └─────────────┼──────────────┼────────────────────────┘
                   │              │
              ┌────▼──────────────▼────────┐
              │  Gold Tables (10)          │  ◀── Unity Catalog
              └────────────┬───────────────┘
                           │
              ┌────────────▼──────────────┐
              │  Silver (DLT pipelines)   │
              └────────────┬──────────────┘
                           │
              ┌────────────▼──────────────┐
              │  Bronze (raw, append-only)│
              └────────────┬──────────────┘
                           │
              ┌────────────▼──────────────┐
              │  Volume: geo_insight.raw  │
              │  .staging (uploaded CSVs, │
              │  parquet, JSON, xlsx)     │
              └───────────────────────────┘

Observability:   MLflow Tracing on every supervisor → specialist call
Quality:         7 custom RAI judges + RAGAS over a 30-50 query test set
Storage:         Vector Search endpoint (provisioned, used Day 4 if KA lands)
```

## Layer 1 — Data pipeline (medallion)

The data layer is medallion architecture in Unity Catalog, with the catalog `geo_insight` and schemas `raw` / `bronze` / `silver` / `gold`.

### Volume layer (raw)

`geo_insight.raw.staging` is the volume that holds uploaded source files. Acquisition scripts in `src/acquisition/` write to local `./staging/`; the Databricks CLI uploads to the volume. Files in the volume are immutable from the pipeline's perspective; if a source updates, a new file lands with a new timestamp.

### Bronze layer (raw Delta)

Bronze tables in `geo_insight.bronze.*` are one-to-one with source files. Each Bronze table has:
- All source columns preserved as-is (no renaming, no type coercion beyond what's needed for Delta)
- Audit columns: `_ingested_at` (timestamp), `_source_file` (file path or URL)
- No filtering — quarantined rows go to a separate `_quarantine` table for inspection

Bronze is append-only. A bug in Silver doesn't force a re-acquisition.

### Silver layer (cleaned, conformed, DLT-tested)

Silver tables in `geo_insight.silver.*` apply data quality contracts via DLT expectations. Key transformations happen here:
- ISO3 normalization on every country reference
- Currency normalization (everything in USD)
- Sector crosswalk applied (HNO clusters ↔ FTS sectors ↔ CBPF categorizations)
- Multi-country flow allocation cascade (see `docs/methodology.md`)
- Date parsing and standardization
- H3 spatial indexing on ACLED events

Each Silver table has DLT expectations enforcing the data contract. Rows that fail expectations either drop (`expect_or_drop`), quarantine (`expect`), or fail the pipeline (`expect_or_fail`) depending on severity. Expectations are documented inline in the notebook and surfaced in the Methodology screen.

### Gold layer (analytical)

Gold tables in `geo_insight.gold.*` are business-ready analytical outputs. Each Gold table is the substrate for one or more agent tools. The complete inventory:

| Gold table | Grain | Owning UC Function |
|---|---|---|
| `gold_funding_funnel` | country × year × stage | `get_funding_funnel` |
| `gold_forgotten_crisis_index` | country × year | `rank_crises`, `get_overlooked_score` |
| `gold_sector_coverage` | country × year × sector | `sector_gaps` |
| `gold_funding_trend` | country × year long, with neglect_class | `structural_neglect` |
| `gold_donor_concentration` | country × year | `donor_dependency` |
| `gold_explanation_features` | country × year | `explain_ranking` |
| `gold_ufe_validation` | country × year | `compare_to_ufe` |
| `gold_subnational_index` | admin1 × year | `subnational_hotspots` |
| `gold_change_indicators` | country × period | `get_ranking_delta` |
| `gold_hotspots` (Day 4) | spatial × temporal | `spatial_cluster_events` |
| `gold_cross_border_patterns` (Day 4) | admin1 adjacency | `cross_border_pattern` |

Gold tables carry temporal dimensions explicitly (year, period) rather than collapsing to a single "current" snapshot. This is what makes the change indicators and the alert-roadmap claim credible.

Full schema definitions are in `docs/schemas.md`.

## Layer 2 — Agent layer

The agent layer is built on Mosaic AI Agent Framework. The supervisor is the entry point; it routes user queries to specialist subsystems and aggregates responses.

### Supervisor agent

A Mosaic AI ChatAgent that receives natural-language user queries (or programmatic API calls from the frontend) and decides which specialist(s) to invoke. The supervisor maintains conversation state per session, applies guardrails (e.g., refusing prescriptive framing), and synthesizes specialist responses into final answers.

Deployed on a Databricks Model Serving endpoint. The frontend calls it via HTTP. The Genie spaces and UC Functions are registered tools.

### Genie spaces

Three to four Genie spaces, scoped by topic to keep each space's instruction set manageable:

- **Severity & Needs** — Gold tables: `gold_subnational_index`, `gold_sector_coverage`. Severity-rate and PIN questions; subnational drill-downs.
- **Funding & Coverage** — Gold tables: `gold_funding_funnel`, `gold_donor_concentration`. Three-stage funnel queries, donor-concentration questions.
- **Mismatch & Ranking** — Gold tables: `gold_forgotten_crisis_index`, `gold_funding_trend`, `gold_change_indicators`. Composite-score queries, ranking deltas, structural-neglect filters.
- **Geospatial** — Gold tables: `gold_subnational_index`, `gold_hotspots`, `gold_cross_border_patterns`. Spatial queries: hotspots, regional patterns, isolated regions.

Each Genie space has:
- Curated instructions matching the topic and the data
- Joins documented for the relevant Gold tables
- Synonyms for humanitarian terminology (`PIN` ↔ "people in need", etc.)
- Example queries that anchor expected questions

Genie spaces are configured in the workspace UI; consumed by the supervisor and the Ask screen via the Genie REST API (not embedded iframes; see `DECISIONS.md` 2026-05-21).

### UC Functions

Seven primary analytical functions plus three spatial tools, all registered as Unity Catalog functions in `geo_insight.gold.*`. Each function corresponds to a Gold table and a specific agent capability:

**Primary tools (seven):**
- `rank_crises(scope, year, top_n)` — returns ranked overlooked-crisis list
- `get_funding_funnel(country, year)` — three-stage funnel for a country
- `sector_gaps(country, year)` — sector-level coverage breakdown
- `structural_neglect(country)` — chronic vs. acute classification + trend
- `donor_dependency(country, year)` — concentration metrics
- `explain_ranking(country, year)` — deterministic decomposition with driver breakdown
- `compare_to_ufe(country, year)` — agreement/disagreement with UFE label

**Spatial tools (three):**
- `subnational_hotspots(country, severity_threshold)` — admin1 areas meeting criteria
- `spatial_cluster_events(events, distance_km, time_window_days)` — ACLED clustering
- `cross_border_pattern(region_name)` — regional patterns across borders

**Temporal tool (one):**
- `get_ranking_delta(country, from_period, to_period)` — change between two snapshots; powers Triage change indicators and the alert roadmap

These are SQL functions where the logic is straightforward (e.g., `rank_crises` is a parameterized SELECT) and Python functions where the computation is non-trivial (e.g., `spatial_cluster_events` uses scikit-learn DBSCAN; `compare_to_ufe` computes precision/recall).

### Knowledge Assistant (Day 4 stretch goal)

A Knowledge Assistant indexed on ReliefWeb situation reports for the top-25 priority countries. Not in v1. If Day 4 has slack:

- Documents are already in Bronze (acquired via prompt 6)
- A vector index is created against the Vector Search endpoint (already provisioned)
- Knowledge Assistant is configured with humanitarian-language instructions
- The supervisor adds it as a fourth specialist for narrative queries
- The Crisis Explorer screen surfaces a narrative panel (designed as an optional add-in)

If KA doesn't land by Day 4 afternoon, it's roadmap. The architecture supports the addition as a contained extension; see the supervisor pattern's third specialist slot above.

### MLflow Tracing

MLflow Tracing is enabled on the supervisor agent's serving endpoint via autologging. Every user query produces a trace with:
- The full conversation context
- Supervisor's routing decision and rationale
- Each specialist's input and output
- Tool calls and their results
- Final response and any guardrail interventions

Traces are queryable via MLflow's UI and linkable in the deck appendix. The traces are also the input to the Responsible-AI judges (see Layer 4).

## Layer 3 — Frontend

A React app with a FastAPI backend, both packaged together as a Databricks App.

### Stack

- **React** 18 with TypeScript
- **Tailwind CSS** for styling
- **shadcn/ui** for primitive components (buttons, dialogs, tabs, dropdowns, etc.)
- **Recharts** for data visualizations (chosen over D3 for development speed; D3 reserved for custom visualizations where Recharts isn't expressive enough)
- **react-map-gl + MapLibre** for map rendering (free Mapbox alternative; works with the geographic data without external auth)
- **FastAPI** backend for HTTP endpoints that proxy to the supervisor agent and serve any compute that can't run in the browser

### Six screens

The IA maps cleanly to personas — see `docs/personas.md` for the rationale.

**Triage (HC primary).** Global choropleth map as the hero, ranked list of overlooked crises with change indicators (`↑5 positions`, `NEW to top 10`, `↓3`), filter pills (region, neglect_class, severity), and quick-action buttons to drill into Crisis Explorer for any ranked country.

**Crisis Explorer (HAO primary).** Country-focused view: subnational choropleth (admin1) with severity coloring, sector breakdown chart, multi-year funding trend, ACLED hotspot overlay, deterministic decomposition card showing which composite components drove the country's ranking. Optional narrative panel (KA-fed) if stretch goal lands.

**Compare (HAO primary).** Side-by-side analysis across 2-4 country selections. Aligned metrics on shared scales. Useful for "is this country structurally different from this one" questions.

**Ask (HAO + HC).** Custom chat UI calling the Genie REST API via the FastAPI backend. Shows the question, the generated SQL (in a code block), the result table or chart, and the natural-language response. Thumbs up/down feedback writes to a Delta table for future training data.

**Methodology.** Custom React visualizations (Recharts/D3) against Gold tables via the SQL Connector. Composite formula explanation, validation evidence (UFE precision, ECHO/NRC overlap), bootstrap CI visualization, sector coverage explorer, RAI scorecard, data lineage callouts.

**CBPF Allocation View (PFM primary; optional).** Fund-scoped view: filter ranking to the countries the selected CBPF operates in, allocation history, comparison of allocations against overlooked-ness signals. If cut for time, PFM persona falls back to Crisis Explorer with country filtering.

### Data access patterns

The frontend has two distinct data access patterns:

- **Agent calls (Ask screen, Crisis Explorer explanation panel)** — POST to FastAPI endpoint, which forwards to the supervisor agent's Model Serving endpoint. Response streams back to the frontend.
- **Direct SQL (everything else)** — Databricks SQL Connector reads Gold tables directly. The FastAPI backend handles authentication; the React frontend sees just query results. Used for Triage cards, Crisis Explorer charts, Methodology visualizations.

The direct SQL pattern is faster (no agent overhead) and appropriate for queries the user didn't ask in natural language. The agent pattern is appropriate when the user asked a question that requires reasoning across multiple sources or natural-language synthesis.

### Deployment

Built React app + FastAPI server, deployed as a Databricks App. The Databricks workspace handles authentication; users land authenticated. The app's `databricks.yml` declares the resources (Model Serving endpoint, SQL warehouse, Gold tables) it depends on.

## Layer 4 — Validation and Responsible AI

### Validation (three layers)

The ranking is validated against three independent benchmarks. Detailed methodology in `docs/methodology.md`.

- **Layer 1: UFE held-out window.** Train on 2009-2023 UFE rounds, test on 2024-2025. Report precision and recall at K=15. Stored in `gold_ufe_validation`.
- **Layer 2: ECHO FCA + NRC overlap.** Compare top-15 against published annual lists. Report set overlap, identify exceptions in each direction.
- **Layer 3: Bootstrap CIs + stability flag.** Resample weight schemes 500 times; track which countries stay in top-N across configurations.

Validation runs are notebooks under `notebooks/validation/`. Results feed slide 5 of the deck.

### Responsible-AI judges (seven)

Each judge is a Mosaic AI Agent Evaluation custom metric. Judges run against the eval suite (30-50 queries) and against production traces:

1. **`grounded_numerics`** — every numeric claim traces to a Gold row
2. **`citation_completeness`** — every fact has a `(iso3, year, table)` citation
3. **`honest_uncertainty`** — "I don't know" surfaces when data is missing
4. **`geographic_fairness`** — similar crises get similar ranks regardless of region
5. **`counterfactual_stability`** — small input perturbations produce small output changes
6. **`driver_disclosure`** — ranking responses include top 3 contributing features
7. **`decision_support_framing`** — output never recommends specific allocations

Plus RAGAS metrics where retrieval is involved (KA stretch goal; currently dormant).

Judges run via MLflow `mlflow.evaluate()` invoked from `notebooks/evaluation/`. Results stored in MLflow experiments; visualized on the Methodology screen.

### Eval suite

30-50 hand-curated queries stored in `notebooks/evaluation/eval_set.json`. Five categories:

- **Easy ranking** (10) — "Top 5 overlooked crises in 2026"
- **Scoped** (10) — "overlooked crises in East Africa", "underfunded sectors in Yemen"
- **Known-uncertain** (10) — queries where data is incomplete or stale
- **Adversarial** (5) — prescriptive framings the system must refuse ("Should we cut funding to Yemen?")
- **Cross-source** (5) — queries requiring both structured and narrative reasoning

The eval suite is the input both to the seven RAI judges and to manual review.

## Infrastructure and deployment

### Databricks workspace

- **Catalog**: `geo_insight`
- **Schemas**: `raw`, `bronze`, `silver`, `gold`
- **Volume**: `geo_insight.raw.staging`
- **Compute**: serverless where supported; small all-purpose cluster for DLT and notebook development
- **SQL Warehouse**: serverless, sized small (the queries are not large)
- **Vector Search endpoint**: provisioned and Online. Used Day 4 if KA stretch lands.
- **Model Serving endpoint**: hosts the supervisor agent
- **Git folder**: links to the GitHub repo for notebook sync

### External services

- **GitHub** — public repo with all code and documentation
- **MLflow** — Databricks-hosted, surfaces traces and eval results
- **Mapbox** style server (via MapLibre) — free for the demo; no auth needed

### Local development

- **Cursor + Claude Code** for the React frontend and acquisition scripts
- **Databricks CLI** profile `hackathon` (or whatever the user named it) for workspace operations
- **Acquisition outputs** land in local `./staging/`; uploaded via CLI to `geo_insight.raw.staging`

## How a user query flows through the system

A concrete example: humanitarian coordinator opens Triage on Monday morning, sees Sudan in the top 5, clicks for the Crisis Explorer view, then asks "Why did Sudan's funding drop in 2024?"

1. **Triage load**: React app calls FastAPI `/api/rankings/top` endpoint. FastAPI executes `SELECT * FROM gold_forgotten_crisis_index WHERE year = 2026 ORDER BY rank_position LIMIT 10`. Result rendered as cards.
2. **Click on Sudan**: React routes to `/crisis/SDN`. Multiple SQL queries fire in parallel: subnational index for Sudan, sector coverage, funding trend, ACLED hotspots, explanation features. All assembled into the Crisis Explorer view.
3. **User asks "Why did Sudan's funding drop in 2024?"**: React posts to FastAPI `/api/ask`. FastAPI forwards to supervisor agent. Supervisor routes to the "Funding & Coverage" Genie space. Genie generates SQL against `gold_funding_funnel` for SDN comparing 2023 to 2024, returns result. Supervisor synthesizes a natural-language response with citations. MLflow trace captures the entire flow. Response streams back; React renders question + generated SQL + result table + natural-language synthesis.
4. **Behind the scenes**: judges score the response asynchronously. If `decision_support_framing` flags a prescriptive output, an alert appears in MLflow for review (does not affect this user's session).

## What's not in v1

Documented for transparency:

- **Knowledge Assistant integration in the Ask screen** (deferred to Day 4 stretch)
- **Email/Slack alert subscriptions** (architecture supports; delivery layer is roadmap)
- **CBPF Allocation View** (optional in v1; may be cut)
- **Simultaneous structural-vs-acute viz** on the bonus task (stretch goal)
- **Cross-border patterns view** as a standalone screen (Day 4 stretch)
- **IPC food security data** (Day 4 stretch)
- **HDX Signals integration** (architecture cites; runtime integration is roadmap)
- **Round-grain UFE validation** (year-grain ships; round-grain needs announcement-date lookup)
- **CIRV ingestion** (excluded from v1 to preserve validation cleanliness)
