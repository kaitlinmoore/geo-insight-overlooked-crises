# Geo-Insight

**Ranking the world's overlooked humanitarian crises with verifiable methodology**

> *Not just underfunded. Overlooked.*

The humanitarian sector publishes several "forgotten crises" rankings each
year — CERF's Underfunded Emergencies allocations, ECHO's Forgotten Crises
Assessment, NRC's Most Neglected Displacement Crises. None validate against
the others, none publish confidence intervals on their ranks, and most
conflate *underfunded* with *overlooked* — a distinction that matters
operationally.

Geo-Insight is an agentic command center for humanitarian programming that
does this differently. It ranks the world's most overlooked humanitarian
crises using **transparent methodology**, **three-layer validation against
the rankings above as comparators**, and **explainable composite scoring**
with **bootstrap-derived confidence intervals on every rank**. Built for UN
OCHA's Humanitarian Programme Cycle and pooled-fund (CBPF) management
workflows.

Built on Databricks: medallion data architecture (Bronze → Silver → Gold)
under Unity Catalog, Mosaic AI supervisor agent with Genie spaces and UC
Function tools, React frontend with admin0/admin1 choropleths and ACLED
conflict hotspot overlays. *Submitted as part of the [UN OCHA × Databricks ×
CMU Heinz College Hackathon](#built-for), May 2026.*

---

## What's different about this ranking

Five methodological commitments distinguish this work from confident-sounding
consensus rankings. Each commitment is implemented in code, each is testable
against external comparators, and each surfaces a class of crisis or
methodology bug that single-metric rankings miss.

### 1. Overlooked vs underfunded — the headline

A crisis in the news is not *overlooked*, no matter how underfunded. The
composite score has a **negative weight** on `media_attention` (magnitude
0.10) — the operationalization of "overlooked" as a concept distinct from
"underfunded."

*Burkina Faso* demonstrates this: 86% funding gap in 2026, low
English-language press coverage, *and* OCHA's own pooled fund (the BFA
Humanitarian Fund) cut allocations from $29.4M in 2022 to $9.0M in 2025 — a
69% decline that mirrors the bilateral donor pattern. The methodology
surfaces this; pure funding-gap rankings undercount it.

### 2. Chronic vs acute — the bonus task

Multi-year structural neglect is a different category of crisis from a
sudden spike. The `chronic_index` component and `neglect_class` label
(`chronic_neglect` / `acute_deterioration` / `chronic_no_plan` / `improving`
/ `well_funded`) capture and name the difference.

*Yemen* demonstrates chronic — five consecutive years of declining funding,
from ~37% funded in 2022 to 13% in 2026. *Sudan* demonstrates acute — a 2025
partial recovery (40% funded) erased in 2026 (collapsed to 21%). Both are
top-ranked overlooked crises, but they require different operational
responses.

### 3. Sector-aware — surfacing hidden imbalance

National funding rates hide sector-specific gaps. The `sector_imbalance`
component catches countries where one cluster is critically underfunded even
when overall funding looks adequate. `gold_sector_coverage` joins **FTS
bilateral funding** *and* **CBPF pooled fund** funding by sector,
exposing the **OCHA-vs-donors sector comparison** that's invisible to
either source alone.

BFA's CBPF is protection-heavy (Protection 88 / WASH 72 / Food Security 52
of 338 total project-cluster rows in 2022-2025), revealing where OCHA
prioritizes when bilateral donors pull back.

### 4. Geography matters — subnational reality

National rollups hide where the crisis actually is. Admin1 choropleths show
within-country disparities; ACLED conflict event hotspots surface the
worst-affected admin1 regions; the `geographic_isolation` component flags
countries operationally invisible to standard monitoring.

Sudan's Darfur vs. Khartoum, Yemen's Sana'a vs. Aden — these tell different
operational stories than the national fill. The Crisis Explorer screen
exposes them at runtime.

### 5. Explainable, with confidence intervals

Every rank carries a **95% confidence interval** from 500 Dirichlet
weight-perturbation bootstrap samples. The `stable_top_n` flag fires when a
country appears in the top-10 across ≥90% of bootstrap samples. The score
decomposition card shows each component's contribution per country (positive
and negative, summing to the score via self-check assertion). The
methodology cascade panel logs which attribution method fired for every
multi-country dollar.

We don't just publish answers; we show our work.

---

## Methodology overview

Three layers of methodology rigor, each detailed in
[`docs/methodology.md`](docs/methodology.md):

### Cascade transparency

Multi-country humanitarian funding is hard to attribute. Plans like the
Syria 3RP or the Sahel response cover several countries, and FTS records
the funding at the plan level. Most rankings drop these flows or split them
equally — both wrong. We use a four-step attribution cascade and **log
which method fired for every dollar**:

| Method | What it does | Share of $ |
|---|---|---|
| `country_tagged` | Single-country flow → use the country tag | **68.5%** ($9.76B) |
| `requirements_weighted` | Multi-country plan with per-country HRP requirements → split proportionally | <0.1% |
| `population_weighted_fallback` | Multi-country, no plan → split by COD-PS country population | **~31%** ($4.48B) |
| `regional_unattributed` | No country information → hold out of country-level analysis | <1% |
| `pending_attribution` *(new)* | Recent (<6 mo) multi-country flow with >5 destinations → quarantine from gap_ratio until OCHA finalizes | ~$4.18B in 2026 alone |

The methodology preserves the theoretically preferred cascade order while
honestly surfacing that population-weighting is the operative method for
~31% of all dollars. The Methodology screen exposes this distribution at
runtime; the deck shows it as a credibility beat about *doing the work*,
not just *claiming to*.

### Composite scoring — seven components, transparent weights

The `overlooked_score` is a deterministic weighted sum of seven
percentile-normalized components:

| Component | Weight | Captures |
|---|---|---|
| `gap_ratio` | **+0.30** | `(requirement − paid) / requirement` — the headline funding gap |
| `severity_rate` | +0.20 | `PIN / population` — crisis intensity per capita |
| `chronic_index` | +0.15 | `chronic_years × mean_chronic_gap` — multi-year structural pattern |
| `sector_imbalance` | +0.10 | std-dev of sector gaps within country — hidden sector neglect |
| `dollars_per_pin` | +0.10 | `paid / PIN` — funding intensity per person in need |
| `media_attention` | **−0.10** | percentile-rank of ReliefWeb mentions — *negative weight* |
| `geographic_isolation` | +0.05 | spatial isolation score (data sparsity, ACLED density, contested borders) |

Five of seven components carry positive weight on the overlooked-ness signal.
The negative weight on `media_attention` is what distinguishes our score
from a plain funding-gap ranking.

### Three-layer validation

| Layer | Source | What we report |
|---|---|---|
| **1. Labeled ground truth** | CERF Underfunded Emergencies allocations (OCHA's own selection of underfunded crises) | Precision@15 and recall@15 against UFE-designated countries, held-out by year |
| **2. Comparator rankings** | ECHO Forgotten Crises Assessment (binary); NRC Most Neglected Displacement Crises (top-10 ranked) | Top-N overlap with ECHO; Spearman rank correlation with NRC |
| **3. Robustness** | 500 Dirichlet weight-perturbation samples | 95% rank CI per country; `stable_top_n` flag |

Three independent comparators plus bootstrap robustness = we know what our
methodology gets right, where it disagrees with prior work, and how much
each rank depends on the weights we chose.

---

## What's in this repo

```
geo-insight/
├── docs/                          # The canonical methodology + reference docs
│   ├── methodology.md             # Formulas, weights, attribution cascade, validation
│   ├── schemas.md                 # Bronze/Silver/Gold table inventory
│   ├── architecture.md            # Medallion + Mosaic AI + frontend stack
│   ├── data_catalog.md            # Per-source data acquisition + quirks
│   ├── personas.md                # HAO / RMS / PFM user research
│   ├── prior-art.md               # Comparator ranking systems studied
│   ├── open-questions.md          # Active + deferred items
│   ├── glossary.md                # Project vocabulary
│   ├── demo_dossier.md            # Sudan / BFA / Yemen demo crisis dossier
│   ├── handoff/                   # Inter-session handoff docs
│   │   ├── synthesis_to_execution_handoff.md
│   │   └── frontend_to_databricks_adapter.md
│   └── notes/                     # Per-acquisition + per-task analysis
│       ├── acquisition_*.md       # Source-specific acquisition findings
│       └── data_profiling.md      # Cross-source profiling pass
├── notebooks/                     # Databricks notebooks (medallion pipeline)
│   ├── bronze/                    # 17 loaders + _common.py
│   ├── silver/                    # 17 DLT notebooks + _common.py
│   └── gold/                      # 12 computation notebooks + _common.py
├── src/                           # Portable Python (acquisition scripts, helpers)
│   └── acquisition/               # Data acquisition scripts
├── frontend/                      # React + FastAPI frontend
│   ├── server/                    # Pydantic models + FastAPI endpoints
│   └── src/                       # React + Tailwind + shadcn/ui + Recharts
├── data/                          # Hand-built reference CSVs (sector crosswalk, etc.)
├── CLAUDE.md                      # Working protocol for AI-assisted sessions
├── STATE.md                       # Current project state
├── DECISIONS.md                   # Locked decisions (newest-first chronology)
└── README.md                      # This file
```

---

## Status

**Current submission state:** *Proved on paper, pending execution.*

The Databricks workspace permissions required to materialize Bronze →
Silver → Gold tables remain pending across all hackathon teams as of
submission. Methodology, schemas, code, acquisition, frontend, and
documentation are all complete and committed; what's blocked is the
end-to-end pipeline run that produces the actual ranking numbers.

### What's complete

- ✅ **15 data sources acquired**, all CC-BY-licensed and version-pinned in `staging/` (FTS, HNO, HRP, INFORM, COD-PS, CBPF allocations + contributions + projects, CERF UFE, ECHO FCA, NRC, fieldmaps boundaries, ACLED events + severity, ReliefWeb metadata + corpus + attention)
- ✅ **17 Bronze loaders** drafted, parse-clean, with documented divergences from `schemas.md` where data reality diverged from initial schema design
- ✅ **17 Silver DLT notebooks** drafted with full expectations matrix; multi-country flow cascade implemented (4-method + pending_attribution); admin1 P-code rollup; fuzzy INFORM header resolution; Sedona for boundaries; H3 for events
- ✅ **12 Gold computation notebooks** drafted; bootstrap CI implementation (500 Dirichlet samples, α = 100×weight); composite scoring; severity gate + chronic-no-plan classification
- ✅ **Frontend** (FastAPI + React + Tailwind + Recharts) wired end-to-end across six screens against a typed Pydantic contract; build passes strict TypeScript; chart components implement methodology constraints (axis locks at [0,1] for cross-country comparability, descending bars for funnel to avoid visual exaggeration, chronic-threshold reference line, neglect-class color tokens)
- ✅ **25-row sector crosswalk** with HNO/FTS/CBPF three-way alignment, populated from real data
- ✅ **Documentation**: schemas, methodology, architecture, personas, prior art, open questions, acquisition notes per source, decisions log

### What's pending

- ⏳ **Databricks workspace permissions** (`CREATE SCHEMA` / `CREATE VOLUME`) — universal lockdown affecting all hackathon teams; resolution timeline outside our control
- ⏳ **End-to-end pipeline run** producing actual `gold_forgotten_crisis_index` rankings (blocked on above)
- ⏳ **Validation numbers** (Layer 1 precision/recall, Layer 2 ECHO/NRC overlap) — methodology drafted, execution pending
- ⏳ **Maps integration in frontend** — GeoJSON extraction script and react-map-gl wiring in progress as separate session
- ⏳ **UC Function registration + Genie space configuration** — specs drafted, registration blocked on permissions
- ⏳ **MLflow eval suite** (~30-50 RAI test queries against the agent) — drafted, execution blocked on permissions

Each pending item is methodologically and architecturally specified —
nothing depends on a research insight we haven't reached. What's blocked
is the wall-clock cost of running things, not the cost of figuring out
what to run.

### How we're handling the lockdown

We're submitting honestly: the work is done; the run is queued. Once
permissions land, the pipeline executes Bronze → Silver → Gold in
sequence (estimated 2–3 hours of cluster time), the frontend swap from
mock data to live SQL queries follows the contract documented in
[`docs/handoff/frontend_to_databricks_adapter.md`](docs/handoff/frontend_to_databricks_adapter.md),
and the validation numbers populate from `gold_ufe_validation` and the
ECHO/NRC overlap queries. The deck and demo recording use mock data with
plausible values consistent with the FTS-verified inputs (see the demo
dossier at [`docs/demo_dossier.md`](docs/demo_dossier.md)) until the live
numbers materialize.

---

## Demo

The demo walks through three crisis cases that each demonstrate a distinct
methodology beat:

- **Sudan** — anchor; the crisis everyone knows. Demonstrates
  `acute_deterioration` classification (2025 partial recovery, 2026
  collapse).
- **Burkina Faso** — surface; the model finds what humans missed. 86%
  funding gap *and* invisible in Western media *and* OCHA's own pooled
  fund pulling back. The negative-media-weight differentiator.
- **Yemen** — structure; the canonical chronic crisis. Five-year funding
  slope demonstrates the `chronic_index` and `chronic_neglect`
  classification.

Plus a methodology screen segment tying cascade transparency, composite
weights, and bootstrap CIs together. ~5 minutes total.

Full demo dossier with screen-by-screen narration and verified numbers:
[`docs/demo_dossier.md`](docs/demo_dossier.md).

---

## Documentation

| Document | What it covers |
|---|---|
| [`docs/methodology.md`](docs/methodology.md) | Composite formula, attribution cascade, validation methodology, weight calibration |
| [`docs/schemas.md`](docs/schemas.md) | Bronze/Silver/Gold table inventory with DQ expectations |
| [`docs/architecture.md`](docs/architecture.md) | Medallion + Mosaic AI + UC Functions + Genie + frontend stack |
| [`docs/data_catalog.md`](docs/data_catalog.md) | Per-source acquisition findings + quirks + reconciliation |
| [`docs/personas.md`](docs/personas.md) | HAO / RMS / PFM user research foundation |
| [`docs/prior-art.md`](docs/prior-art.md) | Comparator ranking systems studied (CERF UFE, ECHO FCA, NRC, INFORM, IRC EWS) |
| [`docs/open-questions.md`](docs/open-questions.md) | Active items, deferred items, methodology questions still alive |
| [`docs/demo_dossier.md`](docs/demo_dossier.md) | Sudan / BFA / Yemen demo dossier with verified numbers |
| [`docs/handoff/`](docs/handoff/) | Inter-session handoff documents (synthesis → execution; frontend → Databricks adapter) |
| [`docs/notes/acquisition_*.md`](docs/notes/) | Per-source acquisition findings (each external dataset has one) |
| [`DECISIONS.md`](DECISIONS.md) | Locked methodology + architecture decisions, newest first |
| [`STATE.md`](STATE.md) | Current focus + last meaningful action |

---

## Built for

**UN OCHA × Databricks × Carnegie Mellon University Heinz College Hackathon, May 2026.**

The challenge: surface the world's most overlooked humanitarian crises and
support resource-allocation decisions for the UN's Humanitarian Programme
Cycle.

Built solo across data acquisition, methodology design, medallion pipeline
authoring, frontend implementation, and documentation, with extensive use
of Claude (Anthropic) as a coding and reasoning partner under a documented
working protocol ([`CLAUDE.md`](CLAUDE.md)).

Special thanks to UN OCHA technical advisors, the Heinz College faculty
supporting the hackathon, and Databricks for the platform access and
hackathon hosting.

---

## License

Methodology, schemas, and code: MIT.
Data: per upstream source licenses (see [`docs/data_catalog.md`](docs/data_catalog.md) — all CC-BY-compatible).
Acquired data not redistributed via this repo; acquisition scripts in
`src/acquisition/` reproduce from upstream sources.

---

*Last updated: 2026-05-22. Submission state and pending items reflect the
status of the hackathon's universal Databricks lockdown; see
[`STATE.md`](STATE.md) for the most current detail.*
