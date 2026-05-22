# Geo-Insight

**A command center for identifying the world's most overlooked crises.**

Humanitarian coordinators face hundreds of competing crises and limited time. The weekly question — which crises are most overlooked relative to documented need? — currently takes hours of cross-referencing OCHA's own data systems. Geo-Insight answers that question on demand: it ranks crises by how overlooked they appear, decomposes every ranking into the signals that drove it, attaches a confidence interval to every rank, and explains the result in language a coordinator can paste into a 9 AM briefing — grounded in the OCHA data they already trust.

![Triage screen — global map and ranked list of overlooked crises](docs/images/triage.png)

![Crisis Explorer — subnational drilldown, sector breakdown, and ranking decomposition](docs/images/crisis-explorer.png)

![Methodology screen — composite formula, validation evidence, and bootstrap intervals](docs/images/methodology.png)

## Five differentiators

1. **Overlooked is not the same as underfunded.** Media attention enters the composite score with a negative weight — a crisis can be severely underfunded yet not overlooked if it commands sustained coverage and advocacy.
2. **Chronic neglect is distinct from acute deterioration.** A multi-year temporal classification (`chronic_neglect`, `acute_deterioration`, `chronic_no_plan`, and more) is surfaced separately from the composite, with a Triage toggle between the two lenses.
3. **Aggregate funding hides sector-specific gaps.** Country rankings decompose to cluster level, surfacing the case where a country is broadly funded but a single sector — health, protection — is severely neglected.
4. **Geography matters.** Subnational analysis is the default where data supports it; ACLED conflict events drive spatial-temporal hotspot detection; geographic isolation acts as a need-multiplier.
5. **Every score is explainable.** A deterministic component decomposition sits alongside an LLM-generated explanation and a bootstrap confidence interval — defensible to a donor without reference to the language model.

## Quick links

- **Slide deck (PDF)** — [`deliverables/geo_insight_deck.pdf`](deliverables/geo_insight_deck.pdf)
- **Demo video** — _(link to be added before submission)_
- **Live app** — _(Databricks Apps URL, added on deployment)_
- **Methodology** — [`docs/methodology.md`](docs/methodology.md)

## What's in this repo

```
/
├── README.md            ← you are here
├── CLAUDE.md            ← contributor orientation and conventions
├── STATE.md             ← current project state
├── DECISIONS.md         ← append-only decision log
├── SUBMISSION.md        ← deliverable checklist
│
├── docs/                ← methodology, personas, glossary, prior art, schemas, architecture
├── notebooks/           ← Databricks notebooks: bronze → silver → gold, geo, agent, validation, evaluation
├── src/                 ← acquisition scripts, portable Python (src/lib), tests
├── frontend/            ← React + Tailwind + shadcn/ui app, deployed via Databricks Apps
├── data/               ← schema references and lineage notes (no raw data committed)
└── deliverables/        ← deck PDF, demo link, MLflow run links, Databricks artifact list
```

`CLAUDE.md` carries the long-form orientation: naming conventions, the medallion data layout, and the working protocol. No raw humanitarian data lives in this repo — data resides in Databricks; the repo carries schemas, references, and code only.

## How the ranking works

Each crisis is scored at country granularity (and admin1 where data supports it) by combining normalized component metrics: the **funding gap ratio** (requirements minus funding received, over requirements), the **severity rate** (people in need over population), **dollars per person in need**, a **chronic index** capturing multi-year underfunding, **sector imbalance**, **media attention** (negative-weighted), and **geographic isolation** (as a need-multiplier on severity). Each component is percentile-ranked within year before weighting, so countries with values that differ by orders of magnitude remain comparable.

The composite is **deterministic**. Scores, component breakdowns, and rankings are computed from structured data via auditable transformations. LLM agents in the system explain rankings; they never produce or alter a rank. Crises enter the ranking only after passing a severity gate (INFORM Severity 4–5, PIN above threshold, or an active response plan), and a multi-year temporal classification distinguishes chronic neglect from acute deterioration as a separate, un-blended label.

Every rank is reported with a 95% bootstrap confidence interval derived from perturbing the composite weights — *"Sudan is #2 with 95% CI [#1, #3]"* is honest; a bare decimal score is not. The full specification, including formulas, thresholds, and the multi-country flow allocation cascade, is in [`docs/methodology.md`](docs/methodology.md).

## How we know it's trustworthy

The ranking is validated against three independent benchmarks. **Layer 1** treats CERF Underfunded Emergencies (UFE) selections as labeled ground truth: OCHA's own twice-yearly determination of which crises are most underfunded. The most recent rounds are held out as a test set, and the model — recomputed using only data available before each round — is scored on precision and recall at K=15. **Layer 2** compares the top-N against two mature third-party lists, the DG ECHO Forgotten Crises Assessment and the NRC Most Neglected Displacement Crises, reporting set overlap and discussing where the model agrees, where it has blind spots, and where it surfaces novel insight.

**Layer 3** is internal robustness: the bootstrap confidence intervals on rank position, plus a `stable_top_n` flag for countries that remain in the top 10 across at least 90% of bootstrap samples. CIRV (the index that informs UFE selections) is deliberately excluded from the model so that validation against UFE is not artificially inflated. The validation procedures are implemented in [`notebooks/validation/`](notebooks/validation/).

## Responsible AI

The system surfaces patterns; it does not recommend allocations. The agent layer is instructed to refuse prescriptive framing — *"Should we cut funding to Yemen?"* is reframed analytically, while *"What does the data show about Yemen's funding situation?"* is answered. Missing data is treated as signal rather than silently imputed, and every ranked output carries data-freshness and coverage flags. Seven custom Responsible-AI judges run over a 30–50 query test set, one of which (`decision_support_framing`) explicitly tests the refusal-of-prescription boundary. The evaluation suite lives in [`notebooks/evaluation/`](notebooks/evaluation/).

## Project context

Geo-Insight was built for the **UN OCHA Geo-Insight challenge** on Databricks (May 2026), a hackathon run with Carnegie Mellon University's Heinz College. It is a solo project. The methodology and framing draw on the Day 1 briefing from Mary Keller (UN OCHA), with spatial-methodology guidance from Dr. Kurland (CMU) and Databricks workspace support from Elise. Thanks to all three.

## License and citation

Released under the [MIT License](LICENSE). © 2026 Kaitlin Moore.

If you build on this work, please cite:

```
Moore, K. (2026). Geo-Insight: A command center for identifying the world's
most overlooked crises. UN OCHA Geo-Insight Challenge, Carnegie Mellon
University Heinz College. https://github.com/<owner>/geo-insight-overlooked-crises
```
