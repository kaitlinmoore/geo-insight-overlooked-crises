# Project State

> **Read at the start of every session. Update at the end of every session.**

## Current focus

Execution phase. Bootstrap documentation updates underway. Data acquisition partially complete (CERF UFE and fieldmaps boundaries done; ACLED, ECHO FCA, NRC, ReliefWeb still pending). Databricks environment partially provisioned (Vector Search endpoint up and Online; schema and volume creation blocked on permissions). Embedding constraint surfaced: workspace assets cannot be iframe-embedded into Databricks Apps; architecture shifted to API-based consumption.

## Last meaningful action

2026-05-21 — Smoke tests in the dedicated Databricks workspace surfaced two issues:

1. Workspace assets (Genie spaces, AI/BI Dashboards) cannot be iframe-embedded inside Databricks Apps. Architecture pivoted to Genie REST API + custom React visualizations over the Databricks SQL Connector. Logged in `DECISIONS.md`.
2. `CREATE SCHEMA` and `CREATE VOLUME` permissions not yet granted in either the original shared workspace or the new dedicated workspace. Requested; pending.

Acquisition sessions for CERF UFE and fieldmaps boundaries completed; findings captured in `docs/notes/acquisition_cerf_ufe.md` and `docs/notes/acquisition_fieldmaps.md`.

## Project posture going into the build

**Pitch line (anchors the deck):** *"A command center for identifying the world's most overlooked crises."* Built around five accessible differentiators:

1. Overlooked is not the same as underfunded — operationalizes Mary Keller's multi-dimensional definition of overlooked, including media attention as a negative-weighted component.
2. Chronic neglect is distinct from acute deterioration — multi-year classification rather than blended composite.
3. Aggregate funding hides sector-specific gaps — country-level rankings are decomposable to cluster level.
4. Geography matters — where a crisis is located is part of why it's overlooked. Subnational analysis is the default where data supports it.
5. Every score is explainable — deterministic decomposition surfaced alongside LLM explanation, with uncertainty visible.

**Architecture.** Mosaic AI supervisor agent (ChatAgent pattern) routing between Genie spaces (text-to-SQL over Gold) and UC Functions (composite scoring, ranking, spatial tools, validation). Knowledge Assistant deferred to Day 4 stretch goal; supervisor architecture and document acquisition proceed regardless to keep the door open. MLflow Tracing on every agent call. Seven custom Responsible-AI judges over a 30–50 query test set.

**Frontend.** React + Tailwind + shadcn/ui hosted on Databricks Apps, with a FastAPI backend. Custom React across all six screens (Triage, Crisis Explorer, Compare, Ask, Methodology, optional CBPF Allocation View). Genie consumed via REST API from the FastAPI backend and rendered in a custom chat UI showing the question, generated SQL, results, and natural-language response. Methodology and other data-exploration visualizations built directly with Recharts or D3 over the Databricks SQL Connector. Iframe embedding of workspace assets confirmed unavailable in Databricks Apps; the API-based pattern replaces it (see `DECISIONS.md` 2026-05-21).

**Data pipeline.** Medallion with full Unity Catalog lineage. Bronze (raw, append-only, audit-grade) → Silver (cleaned, DLT-expectation-tested, multi-country flows allocated) → Gold (seven country-level tables, one subnational table, one change-indicators table). Each Gold table is the substrate for one or more agent tools exposed as UC Functions.

**Validation.** Three layers: UFE selections as labeled ground truth (precision/recall on held-out window), ECHO Forgotten Crises Assessment and NRC Most Neglected as comparators (top-N overlap analysis), bootstrap confidence intervals on rankings (internal robustness with stability flag).

**GeoAI emphasis.** Subnational analysis as default where data supports it (admin1 globally, admin2 for deep dives). ACLED spatial-temporal hotspot detection. Geographic isolation flag. Cross-border / regional pattern view. Map-forward information architecture, with the Triage hero as a global map.

## Next actions

In rough priority order, given current blockers:

1. **Commit bootstrap docs and existing work to git.** `STATE.md`, `DECISIONS.md`, `claude.md`, `docs/`, `src/`, `.gitignore`, `.env.example` are all untracked. **High priority** — provides the safety net we just learned we need (parallel sessions overwriting each other with no baseline to recover from). *Owner: human, ~2 minutes.*

2. **Resolve Databricks `CREATE SCHEMA` / `CREATE VOLUME` permissions.** Currently blocking the Bronze layer, Genie space configuration, UC Function registration, and Vector Search indexing. *Owner: human via OCHA/CMU support channels.*

3. **Continue Bronze data acquisition** — prompts 2 (ACLED), 4 (ECHO FCA), 5 (NRC), 6 (ReliefWeb), and optional 7 (HDX Signals). All outputs to local `./staging/`. Independent of the workspace permissions blocker. *Owner: human supervising Claude Code.*

4. **Local data profiling.** Pandas / Polars / PyArrow against staged files. Generates findings that feed `docs/data-catalog.md` and `docs/schemas.md` regardless of where the data lands later. *Owner: Claude Code or local analysis.*

5. **React frontend scaffolding.** Now elevated to a higher-priority parallel track given the expanded custom-UI scope (custom chat UI, custom visualizations). TypeScript + React + Tailwind + shadcn/ui setup, routing, component shells, mocked-data versions of each screen. No Databricks dependency in scaffolding phase. *Owner: Claude Code / Cursor; human reviews design.*

6. **Continue bootstrap docs** — SUBMISSION.md, open-questions.md, glossary.md, prior-art.md, README.md updates. Then create the new docs (schemas.md, architecture.md). *Owner: synthesis chat → human commits.*

7. **Day 3 evening / Day 4 work** — sequencing depends on when permissions land. Bronze loaders → Silver DLT → Gold → validation → agent layer → frontend integration → demo recording → deck assembly all follow once the workspace is unblocked.

## Open questions

Most pressing (active, may surface during build):

- **Databricks schema/volume creation permissions** — when granted, who grants. Blocking the Bronze layer until resolved.
- **Subnational HNO data coverage** — which countries have machine-readable admin1 PIN/severity data. v1 ships partial subnational coverage with a `data_sparsity_flag` on countries that lack it.
- **Subnational funding inference methodology** — distribute country-level FTS to admin1 proportional to PIN, with uncertainty caveats. Dr. Kurland touchpoint candidate.
- **Demo crisis selection** — which 2–3 crises to feature in the demo video. Likely one well-known (Yemen or Sudan), one our model surfaces as overlooked that may be less famous, one structural-neglect example.
- **Composite weights** — placeholder weights for v1 `overlooked_score` may need empirical calibration once Gold is computed and bootstrap CIs reveal which weight configurations are stable.
- **Meaning of CERF `tableName` field** — values P (4774 rows) and M (3737 rows), purpose undocumented. Ask Mary via Slack.

See `docs/open-questions.md` for the full list. Resolved questions recorded in `DECISIONS.md`.

## Recent decisions

See `DECISIONS.md` for the full append-only log. Most recent (2026-05-21, newest first):

- **Genie and AI/BI Dashboards consumed via API, not embedded.** Iframe embedding of workspace assets confirmed unavailable in Databricks Apps. All screens now custom React; Genie called via REST API; visualizations built against Gold tables via the SQL Connector. Likely net-improvement for visual consistency and portfolio quality.
- **GeoAI Configuration A modified** — substantial spatial intelligence (subnational ranking, ACLED hotspots, geographic isolation, cross-border view) integrated as a first-class differentiator, in service of the overlooked-crises ranking rather than replacing it.
- **Knowledge Assistant deferred to Day 4 stretch goal** — supervisor pattern and ReliefWeb document acquisition proceed regardless, leaving architectural door open.
- **Use-case-led pitch with five accessible differentiators** — UFE precision becomes a supporting verification beat, not the deck headline.
- **Multi-country flow allocation cascade** — requirements-weighted primary, population-weighted fallback, `regional_unattributed` for no-info cases.
- **Bonus task at medium tier** — classification column (`neglect_class`) plus ranking toggle. N=3 years for chronic threshold; no-HRP crises flagged as `chronic_no_plan`.
- **Alert subscriptions deferred to roadmap** — architectural choices preserved (time-versioned Gold, `get_ranking_delta` UC Function, change indicators on Triage).
- **Three-layer validation** — UFE precision on held-out window, ECHO FCA / NRC overlap analysis, bootstrap CIs.
- **ACLED as primary independent severity signal** — IPC food security phases as Day 4 stretch.
- **CIRV deferred for v1** — UFE selections sufficient as labeled ground truth; CIRV-free features used in the ranking to preserve validation cleanliness.

## Working notes

- **Workspace status**: Dedicated team workspace provisioned. Vector Search endpoint provisioned and Online. **Schema and volume creation permissions pending** — requested via OCHA/CMU support; blocking the Bronze layer until granted.
- **Embedding constraint**: Databricks Apps cannot iframe-embed workspace assets (Genie spaces, AI/BI Dashboards). Pattern shifted to API-based consumption (see `DECISIONS.md` 2026-05-21). All visualization work is now custom React.
- **Acquisition status**: Prompts 1 (CERF UFE) and 3 (fieldmaps boundaries) complete; findings captured in `docs/notes/`. Prompts 2 (ACLED), 4 (ECHO FCA), 5 (NRC), 6 (ReliefWeb), and 7 (HDX Signals, optional) pending.
- **Git state**: Bootstrap docs, `src/`, and `docs/` are **not yet committed** to git. Only `.gitignore`, `README.md`, and `LICENSE` are tracked. Highest-priority next action is establishing the git baseline.
- **Submission deadline**: Extended from the original Thursday May 21 23:59 EST. Specific extended deadline per Tanvir's communication — update this line when confirmed.
- **Working solo.** No team coordination overhead.
- **Mentors and points of contact**: Dr. Kurland (GIS / spatial methodology questions), Elise (Databricks workspace logistics), Mary Keller (OCHA framing, available via Slack channel).
- **Tooling**: Cursor + Claude Code via student subscription. Cowork available for asset orchestration. Databricks CLI configured under profile `hackathon` at `~/.databrickscfg`.
- **Conversation orchestration**: The synthesis chat (long, comprehensive) is completing bootstrap docs and will hand off to a fresh "Geo-Insight execution" chat once docs sync to the repo and project knowledge. Spin-off chats currently active: Databricks setup (ongoing). Completed: two Claude Code acquisition sessions (CERF UFE, fieldmaps boundaries).
- **Esri / GIS access** available for visualization or analysis where it adds value.
- **No raw humanitarian data committed to the repo.** Data lives in Databricks; the repo carries schemas, references, and code only.
