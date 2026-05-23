# Evidence package

Verification artifacts for reviewers who cannot access the personal Databricks trial workspace where this submission ran.

## Why this directory exists

The hackathon's intended provisioning of student Databricks workspaces did not materialize in time for submission. Deployment ran on a personal trial workspace, which is not granted to external reviewers by default. To preserve the verification path that a normal workspace deployment would offer — querying the actual tables, viewing MLflow traces, inspecting the agent's tool selection — this directory packages the equivalent artifacts in static form.

This is not a substitute for the running workspace. It is a substitute for *access* to a running workspace. Every artifact here was exported from the live workspace at the timestamps noted on each file.

## Contents

### `/evidence/schemas/`

JSON dumps of the Unity Catalog metadata for each schema. One file per schema:

- `geo_insight.bronze.json`
- `geo_insight.silver.json`
- `geo_insight.gold.json`
- `geo_insight.agent.json`

Each file lists every table or function in the schema with its column schema, row count, owner, and creation timestamp. Generated via `databricks tables list` and `databricks schemas describe`.

### `/evidence/mlflow_runs/`

Exported MLflow run artifacts:

- `eval_run_v1/` — full export of the seven-judge eval run against the 40-case eval set. Includes per-case judge scores, agent responses, retrieved context, aggregate metrics. Reproduces what the Methodology screen's RAI Scorecard reads.
- `production_traces/` — sampled MLflow traces from the demo session: supervisor decisions, tool calls, UC Function invocations, Genie space queries.

Generated via `mlflow.artifacts.download_artifacts()` and `mlflow.search_runs()` against the trial workspace's MLflow experiment. JSON-LD + Parquet format.

### `/evidence/screenshots/`

Static captures of the workspace UI views a reviewer would normally check:

- `unity_catalog/` — Catalog Explorer showing the geo_insight namespace
- `dlt_pipeline/` — Silver pipeline UI with quality contract scoreboard
- `model_serving/` — Supervisor agent endpoint config + invocation log
- `genie_spaces/` — Each Genie space's config + a sample query/answer
- `mlflow/` — Experiment tracking UI showing the eval run + traces
- `vector_search/` — Vector Search endpoint status

Captured immediately before submission; reviewers see what a workspace-authorized user would see.

### `/evidence/sample_queries.md`

Side-by-side: the user-facing question, the agent's response, and the underlying SQL or UC Function call. Demonstrates the agent's tool selection accuracy on a curated set of questions. ~15 examples.

### `/evidence/reproduction.md`

The reproduction protocol from `/deliverables/databricks_artifacts.md` repeated here with deployment-time notes. A reviewer running this from a fresh Databricks workspace should land at parity with the trial deployment.

### `/evidence/demo_video_link.md`

URL to the unlisted YouTube upload of the recorded demo. Also packaged as `.mp4` in this directory if the file size is acceptable for the repo (otherwise via the link only).

## How to verify a specific claim

Each numeric claim in the deck and demo cites a (table, query, year) tuple. To verify:

1. Find the claim in the deck or demo (e.g., "Sudan ranks 1st in 2025 with overlooked_score 0.81").
2. Open `/evidence/schemas/geo_insight.gold.json` and confirm the table cited (`gold_forgotten_crisis_index`) exists with the expected schema.
3. Run the equivalent query in your own Databricks workspace against the reproduced tables, OR check `/evidence/sample_queries.md` for the exact query and its result at the export timestamp.

If a number in the writeup doesn't match what `/evidence/` says, that's a real error — flag it. The evidence package is the ground truth.

## What's NOT in this directory

- **Raw humanitarian data.** Per OCHA / Databricks / ReliefWeb / ACLED licensing constraints, the source data files are not redistributed. The repo's `docs/notes/acquisition_*.md` files document the public-source acquisition steps.
- **Workspace credentials.** No API tokens, no service principal credentials, no PATs. The `databricks_artifacts.md` reproduction protocol uses OAuth + the user's own Databricks account.
- **Personal data.** No screenshots showing logged-in personal accounts, no PII in any captured query result.

## File size note

The full evidence package is several hundred MB if everything is included (MLflow run artifacts are the largest line item). If the repo size becomes an issue for cloning, the large items move to a release artifact or external storage with links from this README.

## Export timestamps

All files in this directory were exported on a single date (timestamped in each filename or in the file's metadata). The submission deck and demo reference the same point-in-time data. If the workspace continues to evolve after submission, this directory captures the submitted state.
