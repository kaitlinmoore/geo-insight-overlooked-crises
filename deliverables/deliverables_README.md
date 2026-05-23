# Deliverables

Submitted artifacts and pointers for the UN OCHA × Databricks × Carnegie Mellon University Heinz College Hackathon (May 2026).

## What's in this directory

| File | Purpose |
|---|---|
| `geo_insight_deck.pdf` | The 8-slide pitch deck, PDF export of the working deck |
| `demo_video_link.md` | URL to the unlisted YouTube upload of the ~15-minute demo |
| `databricks_artifacts.md` | Inventory of Unity Catalog assets, Mosaic AI components, MLflow experiments, and Vector Search endpoint that back the submission |
| `mlflow_runs.md` | MLflow experiment URLs for the eval run and production traces |
| `methodology_summary.md` | 2-page condensed version of `docs/methodology.md` for fast reading |

## What's elsewhere in the repo

The deliverables in this directory are the front door. The full technical substance lives elsewhere:

- **The methodology** — `docs/methodology.md` (full version) or `methodology_summary.md` here (condensed)
- **The architecture** — `docs/architecture.md`
- **The data inventory** — `docs/data_catalog.md` and `docs/schemas.md`
- **The decision log** — `DECISIONS.md`
- **Open questions** — `docs/open-questions.md`
- **The pipeline notebooks** — `notebooks/bronze/`, `notebooks/silver/`, `notebooks/gold/`
- **The agent code** — `notebooks/agent/`
- **The frontend** — `frontend/`
- **The eval set + RAI judges** — `notebooks/evaluation/`
- **Verification artifacts** — `/evidence/` (workspace exports for reviewers without trial workspace access)

## How to read this submission

1. **The deck** (`geo_insight_deck.pdf`) is the front door. Three minutes if you're skimming, ten if you're reading.
2. **The demo video** is the experience. Fifteen minutes of how the product actually works.
3. **`databricks_artifacts.md`** is the proof. Forty-five seconds to confirm the system is real.
4. **The repo** is the long-form. Go deep on whatever interested you in the deck.

## Submission scope

What's included in v1 (this submission):

- Eight-slide pitch deck with five accessible differentiators, methodology framing, validation results, and honest limitations
- Live, working frontend over real OCHA data
- Mosaic AI supervisor agent with 11 UC Function tools and 3 Genie spaces
- MLflow Tracing instrumentation on every agent call
- Seven custom RAI judges over a 40-case eval set
- Bootstrap confidence intervals for ranking stability
- Three-layer validation framework (UFE precision, ECHO/NRC overlap, bootstrap stability)
- Transparent methodology with the composite weights, the multi-country flow cascade, the chronic-vs-acute distinction, and the data sparsity handling all documented

What's deferred to v2 (named in `docs/open-questions.md`):

- Knowledge Assistant over the ReliefWeb situation-report corpus (corpus acquired, endpoint provisioned, retrieval index not populated)
- Alert subscriptions (architecture supports it; delivery layer not built)
- Empirical weight calibration from UFE selections on held-out years
- Spatial boundary operations via Apache Sedona (deferred due to serverless trial deployment constraint; full replacements documented)

## Repository hygiene

- Repo is public (or, in some review states, invite-only with reviewer GitHub handles added before deadline)
- No API keys, tokens, or credentials in any commit
- No raw humanitarian data in commits; data lives on the Databricks volume and is acquired by the scripts in `src/acquisition/`
- LICENSE: MIT
