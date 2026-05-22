# Claude Code Orientation

This file orients a new Claude Code session to the project. **Read this first.** Then read `STATE.md` to learn what the current state is and what to do next.

## What this project is

An agentic command center for identifying humanitarian crises most overlooked relative to documented need and funding coverage. Built for the UN OCHA Geo-Insight challenge on Databricks, May 2026. The user is the sole developer; there are no other human contributors to coordinate with.

The project's anchoring claim — written for the UN audience, used in the deck:

> *A command center for identifying the world's most overlooked crises.*

Five differentiators organize the work:

1. **Overlooked is not the same as underfunded** — negative weight on media attention in the composite score
2. **Chronic neglect is distinct from acute deterioration** — multi-year temporal classification with a UI toggle
3. **Aggregate funding hides sector-specific gaps** — country rankings decomposable to cluster level
4. **Geography matters** — subnational analysis as default where data supports it; ACLED hotspots; geographic isolation as a need multiplier
5. **Every score is explainable** — deterministic decomposition + LLM explanation + bootstrap uncertainty

## Documentation reading order

For most sessions:

1. **`claude.md`** (this file) — orientation and conventions
2. **`STATE.md`** — what's done, what's next, current focus

Read additionally based on what you're doing:

- Touching ranking logic, composite scores, or anything that produces a number for a country → **`docs/methodology.md`**
- Touching humanitarian terminology, sector names, acronyms → **`docs/glossary.md`**
- Touching agent code or routing → **`docs/architecture.md`** (when it exists)
- Touching table schemas → **`docs/schemas.md`** (when it exists)
- Architectural or methodological choices → **`DECISIONS.md`** (append-only log)
- User persona language for UI or content → **`docs/personas.md`**

## Repo layout

```
/
├── README.md                ← public-facing project description
├── LICENSE                  ← MIT
├── claude.md                ← you are here
├── STATE.md                 ← read at start of every session
├── DECISIONS.md             ← append-only decision log
├── SUBMISSION.md            ← deliverable checklist
├── .gitignore               ← gitignored: staging/, .env, node_modules/, etc.
├── .env                      ← (gitignored) API credentials; add new required vars here
│
├── docs/
│   ├── methodology.md       ← scoring formulas, validation, geographic methodology
│   ├── glossary.md          ← humanitarian terms (HRP, HNO, FTS, CBPF, etc.)
│   ├── personas.md          ← HC primary; HAO + PFM secondary; Donor Advisor tertiary
│   ├── prior-art.md         ← existing methodologies (NRC, ECHO, CIRV, DataNation)
│   ├── open-questions.md    ← unresolved items
│   ├── data-catalog.md      ← auto-generated from Bronze profiling
│   ├── schemas.md           ← Bronze / Silver / Gold table schemas
│   └── architecture.md      ← system diagram, supervisor agent design
│
├── notebooks/               ← Databricks notebooks (synced via Git folder)
│   ├── bronze/              ← raw → Delta loaders, one per source
│   ├── silver/              ← cleaning, DLT pipelines, multi-country allocation
│   ├── gold/                ← composite scoring, ranking, subnational, sector
│   ├── geo/                 ← ACLED H3 indexing, hotspot detection, cross-border
│   ├── agent/               ← supervisor agent, Genie configs, UC Functions
│   ├── validation/          ← UFE precision/recall, ECHO/NRC overlap, bootstrap CIs
│   └── evaluation/          ← test set, RAI judges, MLflow eval runs
│
├── src/
│   ├── acquisition/         ← Python scripts to fetch external data sources
│   ├── lib/                 ← shared portable Python (no Databricks dependencies)
│   └── tests/               ← pytest-based tests for portable Python
│
├── frontend/                ← React + Tailwind + shadcn/ui app
│   ├── src/                 ← React components
│   ├── public/              ← static assets
│   ├── package.json
│   ├── tailwind.config.ts
│   └── README.md            ← frontend-specific dev instructions
│
├── staging/                 ← (gitignored) local staging for acquisition outputs
└── data/                    ← schema references and lineage notes (NO raw data committed)
```

## Conventions

### Code locations

- **Databricks notebooks** (`notebooks/`): assume Databricks Runtime, `dbutils`, `display()`, Spark, Unity Catalog. Will not run in plain Jupyter without shims. Synced to the workspace via Git folder integration.
- **Portable Python** (`src/lib/`): standard Python modules with no Databricks-specific dependencies. Should run with `pip install -e .` and pass `pytest`.
- **Acquisition scripts** (`src/acquisition/`): one Python script per external data source. Outputs to `./staging/` (gitignored). Designed for local execution.
- **React frontend** (`frontend/`): TypeScript + React + Tailwind + shadcn/ui. Deployed via Databricks Apps. Reads Gold tables via Databricks SQL Connector; calls the supervisor agent via HTTP. Embedded Genie iframe inside the Ask screen; embedded AI/BI Dashboard inside the Methodology screen.

### Naming conventions

**Databricks namespace:**

- Catalog: `geo_insight`
- Schemas: `raw`, `bronze`, `silver`, `gold`
- Volume: `geo_insight.raw.staging`

**Delta tables** (within their schema):

- Bronze: `bronze_<source_name>` (e.g., `bronze_hno`, `bronze_fts_flows`)
- Silver: `silver_<entity_name>` (e.g., `silver_country_dim`, `silver_fts_flows`)
- Gold: `gold_<analytical_view>` (e.g., `gold_funding_funnel`, `gold_forgotten_crisis_index`)

**UC Functions** (registered in `geo_insight.gold` near their owning Gold table):

- Snake case, descriptive verb: `rank_crises`, `get_funding_funnel`, `compare_to_ufe`, `subnational_hotspots`, `get_ranking_delta`

**Files:**

- Notebooks: `01_bronze_hno`, `02_bronze_hrp` — numbered prefix indicates execution order within schema folder
- Acquisition scripts: `acquire_cerf_ufe.py`, `acquire_acled.py` — `verb_source` naming
- React components: PascalCase (`TriageHero.tsx`, `CrisisExplorerMap.tsx`)

### Data handling

- **No raw humanitarian data in the repo.** Data lives in Databricks. The `data/` directory contains schemas, lineage notes, and references only.
- **Local staging is gitignored.** Acquisition outputs go to `./staging/`; never committed. Upload to the Databricks volume via:
  ```
  databricks fs cp ./staging/<file> dbfs:/Volumes/geo_insight/raw/staging/<file> --profile hackathon
  ```
- **API credentials in `.env`.** Use `python-dotenv`. Add new required variables directly to `.env` as needed. `.env` is gitignored.

### Documentation discipline

- **Markdown for all prose docs.** Not Word, not PDF.
- **Append-only decision log.** Any architectural or methodological choice gets a `DECISIONS.md` entry at the top (newest first). Existing entries are never edited; refinements are new entries that reference the older one.
- **`STATE.md` updated every session.** What you did, what's next, any new open questions. (See scope note below.)

## Working protocol

### Start of every session

1. Read `claude.md` (this file)
2. Read `STATE.md`
3. Read the doc most relevant to what you're doing (see "Documentation reading order" above)

### During a session

- Before writing code that touches scoring logic, read `docs/methodology.md` for the relevant formulas.
- Before writing code that touches humanitarian data structures, read `docs/glossary.md` for terminology.
- Use placeholder weights and thresholds from `docs/methodology.md` exactly as documented; do not invent values.
- If a methodology question arises that the documentation doesn't answer, stop and ask the human; do not improvise.

### End of every session

1. Update `STATE.md` with what was done, what's next, any new open questions
2. If a decision was made, append to `DECISIONS.md` (top of file, newest first)
3. Update the relevant `docs/` file if domain content changed
4. Do not commit and push the changes. Let me know you have finished so I can audit first. I will make commits and push.

**Scope of the end-of-session protocol.** This protocol applies when the work substantively changes the project's state — new pipelines, new Gold tables, new agent tools, new architectural choices, methodology changes, schema decisions. For one-off utility tasks (data acquisition into local staging, profiling scripts, debugging snippets, exploratory analysis), do **not** edit `STATE.md` or `DECISIONS.md`. Report findings in chat and let the human integrate them into the appropriate docs. If you're unsure whether your work qualifies as substantive, ask the human before editing.

### Notebook patterns

**Reading from the volume:**

```python
df = spark.read.csv(
    "dbfs:/Volumes/geo_insight/raw/staging/<file.csv>",
    header=True,
    inferSchema=True
)
```

For Excel files (Spark doesn't natively read xlsx):

```python
import pandas as pd
pdf = pd.read_excel("/Volumes/geo_insight/raw/staging/<file.xlsx>")
df = spark.createDataFrame(pdf)
```

**Writing to Bronze:**

```python
from pyspark.sql.functions import current_timestamp, lit

(df
  .withColumn("_ingested_at", current_timestamp())
  .withColumn("_source_file", lit("<filename>"))
  .write
  .mode("overwrite")
  .saveAsTable("geo_insight.bronze.bronze_<source_name>")
)
```

**Silver with DLT expectations:**

```python
import dlt
from pyspark.sql.functions import *

@dlt.table(name="silver_fts_flows")
@dlt.expect_or_drop("valid_status", "status IN ('paid','committed','pledged')")
@dlt.expect_or_drop("non_negative_amount", "amount_usd >= 0")
@dlt.expect_or_drop("valid_iso3", "iso3 IS NOT NULL AND LENGTH(iso3) = 3")
def silver_fts_flows():
    return (
        dlt.read("bronze_fts_flows")
        # ... cleaning, multi-country flow allocation, etc.
    )
```

**UC Function registration (SQL):**

```sql
CREATE OR REPLACE FUNCTION geo_insight.gold.rank_crises(
  scope STRING DEFAULT 'global',
  year INT DEFAULT 2026,
  top_n INT DEFAULT 10
)
RETURNS TABLE(
  iso3 STRING,
  country_name STRING,
  overlooked_score DOUBLE,
  rank_position INT,
  rank_ci_low INT,
  rank_ci_high INT
)
RETURN
  SELECT iso3, country_name, overlooked_score, rank_position, rank_ci_low, rank_ci_high
  FROM geo_insight.gold.gold_forgotten_crisis_index
  WHERE year = rank_crises.year
    AND (rank_crises.scope = 'global' OR region = rank_crises.scope)
  ORDER BY rank_position ASC
  LIMIT rank_crises.top_n;
```

For UC Functions with more complex logic (e.g., bootstrap CI computation, geographic isolation scoring), Python UC Functions are also supported; choose SQL for simple table reads and Python where computation is non-trivial.

## What NOT to do

- **Do not commit raw humanitarian data files.** Schemas and references only. Local files stay in `./staging/` and on the Databricks volume.
- **Do not invent or hardcode methodological values.** Composite weights, thresholds, and normalization choices all live in `docs/methodology.md`. If you can't find a value there, stop and ask.
- **Do not present mismatch scores with false precision.** Bootstrap CIs accompany every rank. *"Sudan is #2 with 95% CI [#1, #3]"* is honest; *"Sudan's overlooked_score is 0.8347"* is not.
- **Do not silently impute missing data.** Crises with no HRP or stale data are flagged (`chronic_no_plan`, `data_sparsity_flag`), not silently dropped or filled.
- **Do not produce prescriptive output.** The agent says *"the data suggests..."*, not *"fund X."* This is a hard rule from the brief and Mary Keller's framing. One of the seven Responsible-AI judges (`decision_support_framing`) tests this boundary.
- **Do not name specific crises in commit messages in ways that could be misread as advocacy.** *"Updated Sudan ranking logic"* is fine; *"Sudan is being systematically ignored"* is not.
- **Do not change methodology without an entry in `DECISIONS.md` and an update to `docs/methodology.md`.** Documentation and code stay in sync.
- **Do not edit `STATE.md` or `DECISIONS.md` for one-off utility work.** See "Scope of the end-of-session protocol" above. When in doubt, ask.
- **Do not add new Python dependencies casually.** Check whether existing libraries can do the job. New dependencies should be justified.
- **Do not build Knowledge Assistant in the v1 critical path.** It's a Day 4 stretch goal. The supervisor architecture, ReliefWeb document acquisition, and an optional narrative panel in Crisis Explorer are the v1 commitments that keep the door open.

## When to ask the human

The user wants Claude Code to be autonomous where possible but to stop and ask in these specific cases:

- A methodology question that documentation doesn't answer (don't improvise scoring logic)
- An ambiguous data interpretation (e.g., a column meaning unclear, a join producing unexpected duplicates, a NULL pattern that could be either "missing" or "zero")
- A trade-off between architectural choices not covered by `DECISIONS.md`
- A potentially destructive action (dropping a table, force-pushing, deleting a notebook)
- A request that conflicts with `DECISIONS.md` or `docs/methodology.md`
- Uncertainty about whether the current work qualifies as substantive (and therefore whether to update `STATE.md` and `DECISIONS.md`)

For acquisition tasks, asking for API credentials is expected. The user will provide them via `.env` based on instructions you give for each source.

## Project status reference

For "where are we now," always defer to `STATE.md`. The state changes; this orientation document is more stable. If `claude.md` and `STATE.md` ever conflict on current state, `STATE.md` is canonical.
