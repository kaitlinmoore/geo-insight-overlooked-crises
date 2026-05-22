# Open Questions

Unresolved items being actively watched, organized by category and urgency. This document is the catchment for threads that don't fit neatly into `DECISIONS.md` (which is for closed decisions) or `STATE.md` (which is for immediate next actions). When an item here resolves, it moves to `DECISIONS.md` and is removed from here.

## How items are flagged

- **Blocking** — work cannot proceed until resolved
- **Active** — work proceeds in parallel but the answer affects ongoing build choices
- **Deferred** — explicitly out of scope for v1; documented for the roadmap claim

## Blocking

These prevent specific workstreams from moving until resolved.

**Databricks `CREATE SCHEMA` and `CREATE VOLUME` permissions.** Requested in both the original shared workspace and the new dedicated workspace; pending grant. Without these, the Bronze layer cannot be created (no destination tables), the volume cannot be populated (no upload target), Genie spaces cannot be configured against our catalog, and UC Functions cannot be registered in `geo_insight.gold`. *Owner: user via OCHA / CMU support channels.* Local profiling and frontend scaffolding continue in parallel while waiting.

## Active during the build

Resolution matters during Day 3 / Day 4 but isn't blocking initial progress.

**Composite weight calibration.** The seven weights in `overlooked_score` (gap_ratio 0.30, severity_rate 0.20, dollars_per_pin 0.10, chronic_index 0.15, sector_imbalance 0.10, media_attention -0.10, geographic_isolation interaction 0.05) are illustrative placeholders. Empirical calibration against UFE selections may justify different weights. *Resolution path: once Gold tables exist, run weight sensitivity analysis with bootstrap CIs and compare precision against UFE under different weight schemes. Owner: Claude Code in the validation notebooks.*

**Geographic isolation calibration.** The four-component isolation score (distance to urban center, inverse ACLED density, data sparsity, contested-border flag) requires empirical weights. *Resolution path: validate against historical UFE selections — do high-isolation countries appear more often in UFE than less-isolated countries with similar gap_ratios? Owner: Claude Code with Dr. Kurland touchpoint on the spatial methodology choice.*

**Chronic threshold (gap_ratio > 0.5).** Placeholder threshold defining when a year counts toward `chronic_years_count`. May be calibrated empirically. *Resolution path: report sensitivity in the methodology slide — show how the chronic vs. acute classification shifts at 0.4, 0.5, 0.6 thresholds. Owner: Claude Code.*

**Demo crisis selection.** Which 2-3 crises to feature in the demo video. Tentatively: one well-known (Yemen or Sudan), one our model surfaces as overlooked that may be less famous, one structural-neglect example. *Resolution path: needs decision by Day 4 morning, ideally informed by what the actual ranking output looks like. Owner: user with help from execution chat.*

**Submission deadline (extended date).** Original deadline 2026-05-21 23:59 EST. Extension granted per Tanvir; specific extended date pending confirmation. Update `STATE.md` working notes when confirmed. *Owner: user.*

**Subnational HNO data coverage by country.** v1 ships partial subnational coverage with a `data_sparsity_flag` on countries lacking machine-readable admin1 PIN/severity data. The exact coverage map (which countries support admin1, admin2) is determined at Bronze profiling time. *Resolution path: Claude Code profiles HNO files and produces a coverage matrix; informs which crises are demo candidates.*

**Genie REST API smoke test.** Before wiring the Ask screen to the Genie REST API, run an end-to-end test: create a Genie space, call `/api/2.0/genie/spaces/{id}/start-conversation` from outside Databricks, verify the response shape matches our React rendering plan. Replaces the iframe-embed spike that was on the Day 3 morning checklist. *Owner: user in the Databricks setup chat or as a small Claude Code session, ~30 minutes.*

**Meaning of CERF `tableName` field.** Values `P` (4774 rows) and `M` (3737 rows) appear in the CERF UFE data; the meaning is undocumented in the source. *Resolution path: ask Mary Keller via Slack. Lightweight question; expect quick answer. Don't rely on this field in Silver until resolved.*

**2026 multi-country mega-flows.** FTS incoming flows in early 2026 include ~$4.18B in multi-country flows — roughly as much as the prior five years combined (~$299M, 2020-2025). Likely a small number of regional mega-allocations parked at the regional level pending disaggregation by FTS. Applying the population-weighted fallback today would over-attribute funding to large countries (NGA, ETH) that may not actually be receiving it. *Resolution path: introduce a `pending_attribution` allocation_method distinct from `regional_unattributed` for recent (<6-month) multi-country flows with more than N countries; hold them out of `gap_ratio` until they disaggregate. Decision on N and the recency threshold needed before Silver is written.*

**Ethiopia missing from HNO 2025 and 2026.** ETH is on the priority country list (`docs/notes/acquisition_fieldmaps.md`) but appears in `hpc_hno_2025.csv` with zero rows and is absent entirely from `hpc_hno_2026.csv`. Without a PIN for ETH in the current analysis year, it cannot be ranked against other countries. *Resolution path: source PIN from an earlier HNO year (2024 if available) and carry forward with a freshness flag, OR accept that ETH drops out of the demo until 2026 data lands. Decide before demo crisis selection.*

**Venezuela population reference year is 2011.** COD-PS (`cod_population_admin0.csv`, `_admin1.csv`) reports VEN with Reference_year 2011 — 15 years stale. The `severity_rate = PIN / population` denominator is therefore unreliable for VEN. *Resolution path: add a `stale_population_flag` column to `gold_forgotten_crisis_index` distinct from the existing `data_sparsity_flag`, triggered when `Reference_year < year - 5`. Decide on the threshold and whether stale-pop countries are ranked normally with the flag or held out.*

**INFORM Severity dedupe by content hash, not filename.** Three pairs of files are byte-identical with a `_1` suffix (Sep 2025, Feb 2026, Mar 2026) and should be deduplicated. Other apparent duplicates (`202604informseverityapril2026.xlsx` vs `202604informseverityapril20261.xlsx`, `202512informseveritydecember2025.xlsx` vs `202512_inform_severity_mid_december_2025.xlsx`) are **not** dupes — they're distinct mid-month vs end-of-month releases. *Resolution path: Bronze loader hashes file content (sha256) and drops second-and-later copies, while keeping releases with distinct content for the same target month with a `_release_tag` derived from filename and the `About` sheet's release date.*

**CBPF Contributions within-file duplicates.** The combined Contributions files have 2,132 rows but only 1,843 unique `(Year, Donor)` pairs — 289 duplicates. Likely multiple line items per donor-year (pledge revisions, multi-installment payments, currency conversions). *Resolution path: Silver aggregation rule for `silver_cbpf_contributions` — sum `Paid`/`Pledged`/`Total` over `(Year, Donor)` keys, retain a count column for transparency. Low urgency — the CBPF Allocation View is the optional sixth screen.*

**INFORM Severity snapshot-date source-of-truth.** The Bronze loader (`bronze_inform_severity.py`) parses `snapshot_date` from the filename, preferring the spelled-out month name where present. At least one file is known-misnamed (`20190304gcsidatabasebetaversionfebruary2020.xlsx` — date prefix from 2019, contents are Feb 2020). The `About` sheet inside each workbook carries the canonical release date. Bronze keeps rows verbatim; the date correction belongs in Silver. *Resolution path: `silver_inform_severity` reads the `About` sheet from each `_source_file` and overrides `snapshot_date` where the parsed value disagrees with the About-sheet release date. Flag any disagreements to `_quarantine`. Low priority — affects 1 known file out of 89; impact on `chronic_index` is bounded to one month-country pair in early 2020.*

**`ANT` (Netherlands Antilles, dissolved 2010) and `XKX` (Kosovo, user-assigned) appear in `bronze_country_borders` with non-standard ISO3 codes.** Both pass through harmlessly because they won't match `silver_country_dim` / `gold_forgotten_crisis_index`. *Decide whether to filter or remap if ever joined.*

**`gold_cross_border_patterns` cluster labels are hardcoded with first-listed-wins precedence** (NER and TCD resolve to `sahel_g5` rather than `lake_chad`). *v2 candidate: compute clusters dynamically via spectral clustering on the GeoNames adjacency matrix.*

**Gold schema vs. UC Function spec drift.** The UC Function registration session (2026-05-22) surfaced ~11 small discrepancies between `docs/schemas.md` and what `gold_*` tables actually carry. `notebooks/agent/register_uc_functions.py` handles each via aliases / joins / drops; the workarounds are documented in the notebook. Two warrant future cleanup: (a) `gold_change_indicators` is under-specified for `get_ranking_delta` (lacks `rank_from` / `rank_to` / `score_change`); (b) `gold_explanation_features` carries `media_attention_norm` but not the raw `report_count_annual` (the agent would narrate better with the raw count). Neither is blocking for v1.

## Methodological calibration items

These are placeholder parameters that need empirical confirmation once real data flows through the pipeline.

**PIN minimum threshold (100,000) for the severity gate.** The threshold at which a country enters the ranking based on PIN alone. May need adjustment if it excludes crises that should be ranked or includes crises that shouldn't be. *Owner: Claude Code in validation notebooks; sensitivity reported on methodology slide.*

**ACLED H3 resolution (5).** Resolution 5 cells are ~200km², appropriate for country-level hotspot detection. Resolution 6 (~30km²) is finer; would support admin2 work but increases compute and may dilute the signal in sparser-event countries. *Resolution path: profile the ACLED data and report event density per H3 cell at resolutions 4, 5, 6 for the priority countries. Choose the resolution that gives good hotspot signal without too-sparse cells.*

**Bootstrap N samples (500).** Standard for bootstrap CI computation. May reduce to 200 if compute is constrained, or increase to 1000 if stability is in question. *Owner: Claude Code, no urgency.*

**Stability flag threshold (top-10 in ≥90% of bootstrap samples).** Tunable based on what produces a useful number of "stable" countries — too lenient and the flag is meaningless; too strict and no country gets the flag. *Owner: Claude Code in validation notebooks.*

## Acquisition completion items

These resolve by completing the remaining acquisition prompts.

**ECHO Forgotten Crises Assessment completeness across 2015-2025.** Some years may have no published list or have format changes that make extraction unreliable. *Resolution path: prompt 4 (Claude Code session); document gaps in the findings note.*

**NRC Most Neglected Displacement Crises list completeness across 2015-2025.** Same shape as ECHO. *Resolution path: prompt 5.*

**ACLED API rate limits in practice.** API documentation indicates rate limits; how restrictive in practice for a multi-year pull across all countries TBD. *Resolution path: prompt 2 (once API credentials are sorted).*

**ReliefWeb document quality and volume per country.** Will affect Knowledge Assistant feasibility on Day 4. *Resolution path: prompt 6; quality check on body text length and content per country.*

**HDX Signals accessibility.** Whether it's accessible via HAPI or only via dashboard. Affects whether we can integrate or just cite it. *Resolution path: optional prompt 7.*

**RR-row schema integrity in CERF data.** The CERF acquisition spot-checked 3003 UFE rows for ISO3 validity but not the 5508 RR rows. Likely fine; worth a quick check before Silver layer for CERF runs. *Owner: Claude Code in the CERF Silver layer notebook.*

**Multi-value field schemas in CERF data.** `projectsectors`, `projectclusters`, `projectgroupings`, `projectcapcodes` are delimited multi-value fields, frequently empty. Not yet profiled. *Resolution path: only matters if we want to do sector-level analysis on CERF allocations specifically. Likely defer to v2 — our sector analysis runs against HNO/FTS, not CERF.*

**Fieldmaps column inventory beyond join key.** Acquisition confirmed `iso_3` as the join column but did not enumerate the full schema. *Resolution path: run `verify_boundaries.py` (already exists) or have Claude Code do an extended profile before Silver layer for boundaries.*

**Fieldmaps polygon validity.** Self-intersections, slivers, edge-matching quality not directly verified. *Resolution path: ST_IsValid checks in the Silver boundary notebook. Investigate any country with high invalidity rates before using its boundaries for spatial operations.*

**P-code naming convention between fieldmaps and HNO.** Whether fieldmaps' p-codes match HNO's p-codes one-to-one for join purposes. *Resolution path: cross-check during Silver layer for both sources.*

## Mentor touchpoints

Open invitations for expert input. None are blocking; all would improve the project if scheduled.

**Dr. Kurland (GIS / spatial methodology).** Three specific questions waiting: (1) subnational funding inference — distributing country-level FTS to admin1 proportional to PIN, with uncertainty caveats. Is this defensible methodologically? (2) Geographic isolation score — does the 4-component combination look right? (3) Boundary edge cases — Western Sahara, Kosovo, disputed territories. *Outreach: TBD by user.*

**Mary Keller (OCHA framing).** Two specific questions: (1) Meaning of CERF `tableName` field. (2) When can she review the demo recording before submission? *Outreach: Slack channel available; user contacts directly.*

**Elise (Databricks workspace logistics).** Permissions grants if they don't move on the standard channel. *Outreach: TBD by user if escalation needed.*

## Architectural micro-decisions

Small choices to resolve during implementation. Most are revisable cheaply if the initial call is wrong.

**CBPF fund uniqueness keys on `fund_id`, not `fund_iso3`.** Two iso3 values carry multiple distinct funds: SYR (`fund_id` 62 Syria + `fund_id` 70 Syria Cross border) and PAK (`fund_id` 60 Pakistan + `fund_id` 97 Pakistan AP-RHPF). Any Gold-layer aggregation that assumes one fund per country will silently double-count these. Key on `fund_id` (canonical, populated for all funds with projects) with `fund_iso3` as a country-attribution column, not a fund key. Documented in `silver_fund_country_map`.

**Map rendering library.** Currently planning MapLibre (free Mapbox alternative). Alternatives: deck.gl (more spatial-analytic, harder to learn), Leaflet (simpler, less polished). *Owner: frontend dev session. Easy to swap if the initial choice doesn't suit.*

**Number of Genie spaces (3 vs 4).** Currently planning three: Severity & Needs, Funding & Coverage, Mismatch & Ranking. Geospatial could be its own space or subsumed. *Resolution path: start with three; promote Geospatial to a separate space if query patterns warrant it during evaluation.*

**Chat UI scope on the Ask screen.** Chat history persistence (across sessions? in-memory only?), feedback mechanism (thumbs + comment? thumbs only?), example query suggestions (hardcoded? Genie-generated?). *Resolution path: frontend dev session; defaults to in-memory history, thumbs-only feedback writing to a Delta table, hardcoded example queries.*

**SQL Connector vs. Databricks REST API for frontend data reads.** SQL Connector is faster to develop with; REST API might be needed for tables behind row-level security. *Resolution path: SQL Connector for v1 unless permissions surface a need for the REST API.*

**Authentication flow for the Databricks App.** Databricks handles workspace auth automatically. Whether the FastAPI backend needs to validate tokens itself or trust the Databricks-injected user context. *Resolution path: frontend dev session; likely trust the Databricks injection.*

## Deferred / Roadmap (explicitly NOT in v1)

Documented for the deck's roadmap claim. Each has architectural support so the eventual addition is contained.

**Knowledge Assistant integration.** Day 4 stretch; if it doesn't land, it's roadmap. Supervisor architecture, document acquisition, and the narrative panel design all preserve the door. See `DECISIONS.md` 2026-05-21.

**Email / Slack alert subscriptions.** Architecture supports (time-versioned Gold tables, `get_ranking_delta` UC Function, change indicators on Triage). Delivery layer (scheduled job, subscription store, SMTP/Slack integration) is roadmap.

**Round-grain UFE validation.** Year-grain ships in v1. Round-grain requires joining on ERC announcement-date table; not yet built. Either acquire that lookup separately or stay year-grain.

**CIRV as baseline comparator.** Excluded from v1 ranking features to preserve validation cleanliness. Could be added as a separate "baseline" column in `gold_ufe_validation` post-deadline to show how our model compares against OCHA's own institutional index.

**Expanded vector-indexed corpus.** v1 KA stretch indexes ReliefWeb situation reports for top-25 countries. v2 could expand to ACAPS humanitarian briefs, HRP narrative sections, IFRC analyses, and more.

**IPC food security phases.** ACLED ships as the independent severity signal in v1; IPC is Day 4 stretch. If neither lands, IPC is roadmap.

**HDX Signals integration.** Architecture cites Signals as a relevant tool; runtime integration is roadmap. Possible v2 path: subscribe to Signals updates as a trigger for our internal ranking refresh.

**Public dashboards beyond Databricks Apps.** A Vercel-hosted version of the React app for portfolio purposes. v1 ships only the Databricks Apps version.

**Cross-border patterns view as a standalone screen.** The `gold_cross_border_patterns` table may be built in v1; the dedicated UI screen is Day 4 stretch. If not built, the data still feeds the agent's Geospatial Genie space.

**Simultaneous-comparison visualization for the bonus task.** Quadrant chart of acute vs. chronic. Methodologically valuable; Day 4 stretch goal. The classification + ranking toggle ships in v1 either way (see `DECISIONS.md` 2026-05-21 bonus-task entry).

**Geographic isolation distance-to-urban-centroid sub-signal.** Currently 3 of 4 planned sub-signals (`data_sparsity`, `inverse_acled_density`, `contested_border`). Distance-to-urban-centroid deferred — no urban-center reference table acquired (GHS-UCDB or equivalent). For v1 the remaining three sub-weights are renormalized to sum to 1. *Resolution path: acquire GHS Urban Centre Database (or equivalent global urban-center reference); add to Bronze; compute distance per country centroid; calibrate the four-component weighting against expert review.*

**`gold_change_indicators` quarter-grain support.** `schemas.md` describes `(iso3, period)` PK with `2026-Q1`-style period values; current implementation is year-grain only. *Resolution path: introduce intra-year index snapshots — incremental Gold runs at quarter boundaries with snapshot date in PK; refresh `gold_change_indicators` from the snapshot history rather than from a single annual run. Out of scope for v1.*

## Resolved during synthesis

These were open at the start of the synthesis and are now closed. Pointers to where each resolution is recorded:

- *Frontend stack* → React + Tailwind + shadcn/ui (DECISIONS.md 2026-05-19)
- *Architecture pattern* → Multi-agent supervisor (DECISIONS.md 2026-05-19)
- *Validation strategy* → Three layers: UFE + ECHO/NRC + bootstrap CIs (DECISIONS.md 2026-05-21)
- *Independent severity signal* → ACLED primary, IPC stretch (DECISIONS.md 2026-05-21)
- *CIRV inclusion* → Deferred for v1 (DECISIONS.md 2026-05-21)
- *Bonus task scope* → Medium tier with classification + UI toggle (DECISIONS.md 2026-05-21)
- *Knowledge Assistant placement* → Day 4 stretch with architecture preserved (DECISIONS.md 2026-05-21)
- *Alert subscriptions* → Deferred with architecture preserved (DECISIONS.md 2026-05-21)
- *AI/BI Dashboard placement* → Originally embedded inside React; superseded by API-based approach (DECISIONS.md 2026-05-21)
- *Multi-country flow allocation* → Requirements-weighted cascade (DECISIONS.md 2026-05-21)
- *Pitch framing* → Use-case-led with five differentiators (DECISIONS.md 2026-05-21)
- *GeoAI scope* → Configuration A modified (DECISIONS.md 2026-05-21)
- *Persona structure* → HC primary, HAO + PFM secondary, Donor Advisor tertiary (DECISIONS.md 2026-05-21)
- *Embedding feasibility* → Iframe embedding unavailable; replaced with API consumption (DECISIONS.md 2026-05-21)
