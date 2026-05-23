# Decision Log

Architectural and methodological decisions for this project. Append-only. Newest entries at the top.

## Format

```
## YYYY-MM-DD — Short title

**Decision:** What was decided.

**Alternatives considered:** What was rejected and why.

**Rationale:** Why this choice.

**Revisit if:** Conditions under which this should be reconsidered.
```

---

## 2026-05-22 — openpyxl via notebook-scoped %pip on serverless

**Decision:** Databricks serverless ships pandas without `openpyxl`, so notebooks that read `.xlsx` inputs install it via notebook-scoped `%pip install openpyxl` at the top of the notebook. v1 workaround; not a cluster library or workspace-installed dependency.

**Revisit if:** Serverless adds `openpyxl` to its baseline image, OR a workspace-installed library policy supersedes the per-notebook approach.

---

## 2026-05-22 — UC Function design conventions

**Decision:** Eleven Unity Catalog Functions in `geo_insight.agent.*` back the Mosaic AI supervisor's tool calls (see `notebooks/agent/register_uc_functions.py` and `notebooks/agent/README.md`). Three convention decisions:

1. **`COMMENT` strings drive tool selection** and avoid apostrophes for SQL-quoting cleanliness — the supervisor's tool selector reads the function `COMMENT`, so each one names the user-facing question type, gives example phrasings, and calls out the bounds/caveats the agent must respect when formatting answers.
2. **`compare_countries` accepts a comma-separated ISO3 string** (e.g. `"SDN,BFA,YEM"`) rather than `ARRAY<STRING>`. A one-string parameter is more robust to LLM tool-call formatting than an array — revisit if traces show the agent mis-quoting.
3. **`get_score_decomposition` splits each weight into `ABS(weight)` + `sign` (+1 / -1)`** for unambiguous narration — the agent can say "weight 0.10 applied negatively" without parsing a signed scalar.

**Alternatives considered:** `ARRAY<STRING>` for `compare_countries` — rejected for v1 on LLM-robustness grounds (CSV is one less thing for the agent to format wrong); signed `weight` column with no separate `sign` — rejected because it conflates magnitude and direction in agent narration.

**Rationale:** The functions are the supervisor's tool surface; design choices that make tool selection more accurate and answer formatting more reliable are worth small SQL-side overhead (CSV split, weight/sign decomposition).

**Revisit if:** evaluation traces show the agent mis-quoting the CSV in `compare_countries` (then move to `ARRAY<STRING>`); or if a new convention emerges (e.g. structured docstring with `<example>` tags) that the tool selector handles better than free-text COMMENTs.

---

## 2026-05-22 — Serverless deployment

v1 deploys on Databricks serverless, which can't install the Sedona JVM library. The boundary path (`bronze_fieldmaps_boundaries` → `silver_boundaries`) is deferred; portable replacements adopted: `bronze_country_borders` (GeoNames, CC-BY) for adjacency, the `CONTESTED_BORDER_COUNTRIES` reference list in `notebooks/gold/_common.py` for the contested-border sub-signal, and `src/acquisition/extract_geojson.py` for frontend maps. `gold_cross_border_patterns` rebuilt at country grain. **Revisit if** classic compute becomes available (reactivate the boundary loaders without methodology change).

---

## 2026-05-22 — gap_ratio numerator is paid-only as headline

**Decision:** The headline `gold_forgotten_crisis_index.overlooked_score` derives from `gap_ratio = (requirement − paid) / requirement` (paid-only). The `gap_ratio_paid_committed` variant is computed and emitted alongside as a sibling column for sensitivity analysis but is not the headline. Affected: `notebooks/gold/_common.py:GAP_NUMERATOR = "paid"`. Both `gap_ratio` (paid-only headline) and `gap_ratio_paid_committed` (variant) land in `gold_forgotten_crisis_index` and `gold_explanation_features`.

**Alternatives considered:** paid+committed as the headline numerator — rejected because it risks over-counting committed-but-never-paid funds (historical FTS data shows commitments don't always materialize). Preserved as the `gap_ratio_paid_committed` sibling column for sensitivity analysis rather than discarded.

**Rationale:** `methodology.md` and `schemas.md` both specify paid-only; the validation slide content assumes paid-only in its formulas; UFE selection criteria align with stricter interpretations of "underfunded." The variant is preserved for the methodology slide's sensitivity analysis and any future calibration work.

**Revisit if:** sensitivity analysis on the variant shows the paid-only headline materially distorts rankings, or stakeholder framing of "underfunded" shifts to include committed funds.

---

## 2026-05-22 — overlooked_score true range is [−0.10, 0.90]

**Decision:** The composite formula's negative `media_attention` weight (magnitude 0.10) combined with absolute weights summing to 1.0 bounds the raw `overlooked_score` to **[−0.10, 0.90]**, not [0, 1] as the original `schemas.md` DQ note implied. No rescaling applied to the raw column. Affected: `schemas.md` DQ check updated from `score_in_unit_interval` to `score_in_signed_unit_range` with the [−0.10, 0.90] expression. Frontend reads the rank, not the raw score, so no UI change needed.

**Alternatives considered:** rescaling the raw score back into [0, 1] — rejected because the faithful formula is correct and the DQ note was the inconsistent artifact; rescaling would distort the signed contribution of the media-attention term.

**Rationale:** Bootstrap CIs are computed on rank position, not on the raw score, so the asymmetric range is academic for the UI — rank + CI is the headline per the no-false-precision rule.

**Revisit if:** the raw `overlooked_score` ever becomes user-facing, or the component weights change such that the bound shifts.

---

## 2026-05-22 — Missing-component imputation is neutral 0.5 percentile

**Decision:** When a country lacks a raw input for a normalized component (e.g., no INFORM severity reading, no ReliefWeb attention data, no admin1 PIN), the within-year percentile-rank normalization assigns **0.5** (neutral midpoint). The `data_sparsity_flag` is carried through to `gold_forgotten_crisis_index.inputs_freshness` to surface the imputation to users. Affected: `notebooks/gold/_common.py` — both `composite_score_expr` (coalesce defaults) and `dirichlet_bootstrap_rank_ci` (fillna defaults). The sparsity flag display is a frontend concern; the contract already exposes `data_sparsity_flag` per `inputs_freshness`.

**Alternatives considered:** (a) the default behavior (norm ≈ 0 via Spark's nulls-first ordering in `percent_rank()`) — rejected because it understates data-sparse countries by treating missing data as "least overlooked on that dimension," contradicting the project's *missing data is signal* commitment. (b) an explicit penalty for missing data — rejected because it is harder to defend, ranking countries by what we *don't know*.

**Rationale:** Neutral imputation preserves rank ordering for measurable components without penalizing sparse countries, while the carried-through `data_sparsity_flag` keeps the imputation visible rather than silent.

**Revisit if:** validation shows neutral imputation systematically advantages or disadvantages a class of data-sparse countries, or a defensible explicit-penalty scheme emerges.

---

## 2026-05-22 — gap_ratio denominator is per-country requirements, not plan-total

**Decision:** `gap_ratio` denominator is per-country requirements, not plan-total. Profiling found that multi-country plan totals (HRP `revisedRequirements`) would over-attribute to each constituent country if used directly per-country. `bronze_fts_plan.requirements` is already at country × plan grain and is the correct per-country denominator. HRP `revisedRequirements` ÷ country_count is the fallback when FTS lacks a per-country breakdown.

---

## 2026-05-22 — Three schema/methodology refinements following local data profiling

**Decision:** Three concrete adjustments to `docs/schemas.md` and `docs/methodology.md` following profiling of the CMU drop (see `docs/notes/data_profiling.md`). None of these change the core methodology or overturn a prior DECISIONS entry; they reconcile documented design with what the actual data supports.

1. **Multi-country flow cascade — framing refined, order unchanged.** The four-step cascade (`country_tagged` → `requirements_weighted` → `population_weighted_fallback` → `regional_unattributed`) is preserved. But "requirements-weighted as the primary method" is reframed: in the actual incoming-flow data (9,255 rows, $14.24B 2020-2026), 94.3% of rows / 68.5% of $ are single-country (`country_tagged`); 5.7% of rows / 31.5% of $ are multi-country, of which 99.1% carry no `destPlan`. So `requirements_weighted` fires on ~5 of 528 multi-country flows; `population_weighted_fallback` is the de facto handler for ~30% of incoming dollars. The cascade order is methodologically right where the data exists; the framing in `methodology.md` overstated how often the primary leg applies. Updated to acknowledge the empirical distribution; the Methodology slide will show the share-by-method table as a transparency feature.

2. **`Not specified` / country-aggregate FTS rows retained as a Silver grain.** `fts_requirements_funding_global.csv` has 2,577 rows (67%) where `code` is NULL and `name='Not specified'` — country-aggregate rows carrying off-plan funding (e.g. ETH 2026 has $256M in this bucket and no HRP at all). The previously-documented v1 approach ("use plan-level rows joined to `bronze_hrp`") would silently drop these, zeroing out funding for any country without a current plan and emptying the `chronic_no_plan` category the bonus-task decision created. Silver now carries both grains: plan-level rows attributed via the cascade, and country-aggregate `Not specified` rows attributed directly to the country with `plan_code IS NULL`.

3. **INFORM Severity Bronze loader dispatches on sheet name.** 20 of 89 INFORM Severity files (Jan 2019 – Aug 2020) use the legacy sheet name `GCSI`; 69 (Sep 2020 onward) use `INFORM Severity - country` — same downstream schema after the row-3 `Weights` drop. Without dispatch, the 2019-2020 history wouldn't load, breaking 20 months of the chronic_index substrate.

**Alternatives considered:**

- (1a) Re-order the cascade so population-weighted is "primary": rejected because requirements-weighted is still the methodologically preferred method where the data supports it; the cascade order is right, the framing was misleading.
- (2a) Drop the `Not specified` rows and exclude no-HRP countries from the ranking: rejected because that silently makes the `chronic_no_plan` category empty for countries that don't have plans in the analysis year — exactly the population the category was designed to surface.
- (3a) Only load the post-2020 INFORM files: rejected because the chronic_index needs the longest defensible time series; 20 months of leading history is worth a sheet-name conditional.

**Rationale:** Each adjustment reconciles documented design with the data that exists. None invalidates earlier decisions; all three keep the methodology coherent and the audit trail honest.

**Revisit if:** ACLED account upgrade or FTS multi-country attribution improvements change the cascade distribution materially; CBPF data evolves to include fund-level attribution.

---

## 2026-05-22 — Table schemas formalized in docs/schemas.md; ACLED split into two Bronze tables

**Decision:** Authored `docs/schemas.md` as the canonical Bronze/Silver/Gold schema reference, profiled from the actual CMU drop and staging outputs. Three schema choices in it materially touch methodology and are recorded here:

1. **ACLED ingests as two Bronze tables, not one.** `bronze_acled_events` (point-level, from the API; H3-indexable; but embargoed to ≥12 months old) and `bronze_acled_severity` (admin2 × month aggregates, from HDX; current to last month; carries P-codes). They feed `silver_acled_events` (hotspots) and `silver_acled_severity` (the independent severity signal / `gold_change_indicators`) respectively. The original plan assumed one event-level ACLED table; the HDX-vs-API data divergence forced the split (see `docs/notes/acquisition_acled.md`).

2. **`donor_concentration` uses FTS donor identity, not CBPF contributions.** `bronze_cbpf_contributions` turned out to be global donor totals per year with no fund/country column, so it cannot attribute donors to crises. `gold_donor_concentration` is computed from `silver_fts_flows.donor_org` instead.

3. **INFORM severity gate keys on the 1–5 category, not the 1–10 index.** INFORM publishes both scales; `methodology.md`'s "Severity ≥ 4" gate and "≥ 3" chronic check refer to the ordinal **category**. Recorded to prevent a silent off-by-scale bug in the gate.

**Alternatives considered:** (1) Single ACLED table — rejected: no single source has both point coordinates and current recency. (2) Deriving CBPF country attribution from allocations to approximate contributions by crisis — rejected for v1 as out-of-scope and lossy; FTS already provides per-flow donor identity. (3) Using the 1–10 index in the gate — rejected as inconsistent with the documented threshold semantics.

**Rationale:** The dual-ACLED design preserves both the spatial-hotspot capability and a current severity signal; documenting the recency/coverage trade-offs keeps the Silver layer honest. The CBPF and INFORM clarifications prevent two concrete data bugs.

**Revisit if:** ACLED elevated/academic access lifts the 12-month API embargo (then a single current event-level table could serve both paths); or CBPF publishes fund-attributed contributions.

---

## 2026-05-21 — Genie and AI/BI Dashboards consumed via API, not embedded

**Decision:** Databricks Apps cannot embed workspace assets (Genie spaces, AI/BI Dashboards) via iframe — confirmed through smoke testing during workspace setup. Replace the planned iframe-embedding pattern with API-based consumption:

- **Ask screen**: Genie REST API (`/api/2.0/genie/spaces/{id}/...`) called from the FastAPI backend; responses rendered in a custom React chat UI showing the question, the SQL Genie generated, the result set, and the natural-language answer.
- **Methodology screen**: custom React visualizations against Gold tables via the Databricks SQL Connector. Recharts or D3 handles rendering. Data lineage callouts ("this chart reads from `geo_insight.gold.gold_forgotten_crisis_index`, last updated X") replace what AI/BI's auto-rendering would have provided.
- **CBPF Allocation View (if built)**: same pattern as Methodology — custom React over the SQL Connector.

Genie spaces are still configured in the workspace (instructions, joins, sample queries) and called via API; we don't show Genie's native UI but the agent still benefits from the Genie space's curated data context. The supervisor agent architecture is unchanged.

**Alternatives considered:**

- *Continue with iframe embedding*: rejected because the Databricks security model blocks this pattern entirely for workspace assets inside Databricks Apps. Not a configuration issue we could work around within the time budget.
- *Link out to dashboards in a new tab*: rejected because it breaks the unified product experience. The deck framing emphasizes a "world-class, not hackathon" feel; bouncing the user to a separate workspace dashboard tab undercuts that.
- *Skip Genie and AI/BI entirely*: rejected because the Databricks platform showcase narrative still wants both visible in the architecture. We get them as backend services rather than UI components.

**Rationale:** What initially read as a setback may be the better architecture on net:

1. **Visual consistency across all screens.** One coherent React design language across Triage / Crisis Explorer / Compare / Ask / Methodology beats a mix of embedded native UIs and custom components. This matters disproportionately for the "world-class, not hackathon" framing.
2. **No iframe auth / CORS / mobile fragility** to manage.
3. **SQL transparency is preserved.** The Genie-generated SQL is rendered in our own code-block component — the "no hallucination, traceable answers" deck story is intact, we just render the evidence ourselves.
4. **Cleaner portfolio artifact.** A self-contained React app deployable anywhere is a stronger artifact than one with iframe dependencies on a specific workspace.
5. **Better mobile responsiveness.** Embedded iframes were going to be brittle on mobile regardless.

Time cost: ~6-12 additional hours of frontend work (custom chat UI for Ask, custom visualizations for Methodology, optional CBPF View). Partially offset by removing the iframe-embedding work and the 30-minute embed-verification spike originally on the Day 3 morning checklist.

**Revisit if:** Databricks releases an embedding pattern that works for Databricks Apps within the hackathon timeframe (unlikely), OR the time cost of the custom UI work exceeds ~12 hours and threatens the must-have shipping list — at which point we'd cut scope from the affected screens (e.g., fewer Methodology visualizations) rather than reverting the architectural choice.

---

## 2026-05-21 — GeoAI as a substantial differentiator (Configuration A modified)

**Decision:** Treat geographic intelligence as a first-class differentiator in service of the overlooked-crises ranking. Subnational analysis becomes the default where data supports it (admin1 globally, admin2 for deep dives). ACLED feeds spatial-temporal hotspot detection. Geographic isolation is a need-multiplier signal. A cross-border / regional pattern view surfaces dynamics that country-level rankings hide. Information architecture is map-forward, with the Triage hero as a global map. Geography is positioned as one of five differentiators, not as the project's sole frame.

**Alternatives considered:**
- *Tier 1 — visual GIS only (map in Crisis Explorer as side panel)*: rejected because it doesn't earn the project's name and underweights the user's distinctive capability.
- *Tier 3 — spatial intelligence as the project's sole frame*: rejected because it risks distorting the brief's central question (mismatch and ranking) into a spatial-analysis tool, and because 4 days is not enough to deliver Tier 3 ambition without sacrificing ranking quality.

**Rationale:** Mary Keller's framing of overlooked explicitly includes "where they are located" as a dimension. GeoAI is a capability the user has institutional advantage in (Heinz GIS background, Dr. Kurland mentorship, Esri access) and that few other teams can credibly deliver in this timeframe. Tier 2 surfaces GIS as a distinguishing differentiator while keeping the ranking engine as the unmistakable center of the submission.

**Revisit if:** Subnational data coverage proves too sparse to support the default-subnational architecture across the demo crises, or if spatial agent tools don't land in time for Day 4 morning.

---

## 2026-05-21 — Knowledge Assistant deferred to Day 4 stretch goal

**Decision:** Vector Search endpoint provisioning happens immediately to surface permission / quota issues early. Knowledge Assistant configuration and ReliefWeb document indexing are deferred to Day 4 afternoon as a stretch goal. Architectural choices made in v1 (supervisor pattern from the start, ReliefWeb documents acquired into Bronze regardless, Crisis Explorer narrative panel designed as an optional add-in) keep the door open for late addition without forcing a rewrite.

**Alternatives considered:**
- *Build KA into v1 critical path*: rejected because the substrate (supervisor + Genie + UC Functions) covers the agentic story without it, and the time cost (~6-8 hours) competes with higher-differentiation GeoAI work.
- *Drop KA entirely, including document acquisition*: rejected because the user wants to retain optionality and may incorporate post-deadline; the ~2-hour acquisition cost is low insurance.

**Rationale:** KA is valuable but not the project's distinctive capability. Other teams can replicate the KA pattern from the Day 2 presentation; few can credibly attempt the spatial intelligence work. Deferring KA with the door held open is the right risk-reward tradeoff.

**Revisit if:** Day 4 afternoon arrives with substantial schedule slack AND all must-haves are green AND the ReliefWeb corpus quality looks sufficient.

---

## 2026-05-21 — Use-case-led pitch with five accessible differentiators

**Decision:** The deck's anchoring claim is *"A command center for identifying the world's most overlooked crises,"* targeted at humanitarian coordinators and donor advisors as the primary audience. Five differentiators organize the rest of the deck: overlooked-vs-underfunded (negative weight on media attention), chronic-vs-acute (multi-year classification), sector-aware (sub-country granularity), geography matters (subnational + spatial intelligence), and explainable (deterministic decomposition + LLM explanation + uncertainty surfacing). UFE precision becomes a supporting verification beat on the methodology slide, not the deck headline.

**Alternatives considered:**
- *UFE-precision-led narrative*: rejected because committing the deck headline to a precision number not measurable until late in the build creates psychological weight during the build, may underperform expectations, and is sterile storytelling for the UN OCHA audience.
- *Architecture-led pitch*: rejected because the primary audience is UN leadership, not Databricks engineering judges. Architecture is appendix material.
- *Methodology-led pitch*: rejected because it competes with DataNation's prior work on the same axis without obvious differentiation.

**Rationale:** The primary audience is UN OCHA leadership, who care first about workflow fit and decision support, second about technical depth. Use-case-led framing speaks to them first. Five differentiators are accessible because each is stated in operational language and operationalizes something Mary Keller named in her Day 1 framing. UFE precision can be elevated to the headline if the number is strong by Day 4 morning, but the pitch does not depend on it.

**Revisit if:** Mary's review of the demo recording suggests a different framing lands harder, OR if UFE precision is so strong (≥85%) that it deserves the headline slot.

---

## 2026-05-21 — Multi-country flow allocation cascade

**Decision:** FTS flows tagged to multi-country regional plans are allocated to specific countries via a four-step cascade:

1. Flow has a country tag → use the tag (method: `country_tagged`)
2. Multi-country plan with per-country requirements documented → allocate proportional to each country's HRP requirement within the plan (method: `requirements_weighted`)
3. Multi-country plan without per-country requirements but with country list known → allocate proportional to country population from COD-PS (method: `population_weighted_fallback`)
4. No country tag and no country list → exclude from country-level analysis, report in aggregate (method: `regional_unattributed`)

All splits happen in Silver. Each split row preserves `allocation_method`, `allocation_weight`, and `source_flow_id` for lineage. The methodology slide reports the fraction of total flow value falling into each method.

**Alternatives considered:**
- *Equal split as fallback*: rejected because population is a real (though weak) signal where requirements are unavailable, and population-weighted uses more information than equal split while remaining transparently flagged.
- *Population-weighted as primary*: rejected because per-country requirements within a plan are negotiated specifically to reflect humanitarian need; population alone systematically distorts allocation for refugee-hosting countries and concentrated-need regions.

**Rationale:** Requirements-weighted is self-consistent with our `gap_ratio` denominator (we compare funding-received to requirements-needed; allocating regional flows by per-country requirements respects that negotiation). The cascade preserves transparency by flagging less-defensible methods rather than smuggling them in. DataNation did not address multi-country flow attribution, so this is a documented methodological differentiator.

**Revisit if:** The methodology audit reveals that the `population_weighted_fallback` method covers more than ~5% of total flow value, suggesting a systemic data gap worth surfacing more prominently.

---

## 2026-05-21 — Bonus task: structural vs acute neglect at medium tier

**Decision:** Implement the bonus task at "medium" scope. Build a `neglect_class` column on `gold_funding_trend` with values `chronic_neglect`, `acute_deterioration`, `improving`, `well_funded`, and `chronic_no_plan` (for countries without HRPs that nonetheless show persistent unmet need). Default chronic threshold is N=3 consecutive years; documented as configurable. Add a ranking-lens toggle in the UI that switches between "ranked by current mismatch" and "ranked by structural neglect."

A simultaneous-comparison visualization (quadrant chart) is a Day 4 stretch goal if time allows.

**Alternatives considered:**
- *Skip the bonus task entirely*: rejected because the bonus question explicitly maps to Mary's framing of donor fatigue and multi-year patterns; skipping leaves a documented hackathon ask on the table when "originality of the approach" is one of the five jury criteria.
- *Minimum tier — classification column only, no UI exposure*: rejected because building the classification without surfacing it does not actually answer the PDF's bonus question ("how should ranking change").
- *Maximum tier — dedicated simultaneous-comparison visualization as a core feature*: rejected because the additional visualization competes with GeoAI and frontend polish; preserved as a stretch goal.

**Rationale:** Medium tier delivers a substantive answer to the bonus question at low marginal cost — the multi-year FTS aggregation needed for `chronic_index` already exists, classification logic adds minimal compute, and the UI toggle is small. The structural / acute distinction surfaces separately from the composite score, consistent with the Day 1 synthesis principle that chronic and acute are distinct signals, not blended.

**Revisit if:** Composite weight calibration reveals chronic and acute signals interact in ways that warrant a single combined ranking, OR if the no-HRP edge case is more common than expected and requires methodology refinement.

---

## 2026-05-21 — Three-layer validation strategy

**Decision:** Validate the ranking using three independent layers:

1. **UFE selections as labeled ground truth.** CERF Underfunded Emergencies selections back to 2009 as binary labels (country × year × round). Hold out recent rounds (2024-2025 as the floor; broader train/test split as the stretch). Report precision and recall on the held-out window.
2. **Multi-source comparators.** Cross-check top-N against the DG ECHO Forgotten Crises Assessment annual list and the Norwegian Refugee Council Most Neglected Displacement Crises list. Report overlap analysis.
3. **Internal robustness.** Bootstrap confidence intervals on rankings by resampling weight schemes. Carry a stability flag for countries staying in top-N across many configurations.

CIRV-free features are used in the model to preserve validation cleanliness (UFE selections are informed by CIRV; using CIRV as a feature would artificially inflate agreement).

**Alternatives considered:**
- *Internal robustness only (no external validation)*: rejected because that is essentially what DataNation did, insufficient for the "defensibility" jury criterion.
- *UFE precision as the deck headline*: see the use-case-led pitch decision — UFE precision is supporting evidence, not headline.

**Rationale:** UFE selections are OCHA's institutional answer to "which crises are most underfunded" — the strongest possible validation target. ECHO FCA and NRC are mature comparators that the PDF's "supplement with public sources where it improves analysis" guidance explicitly invites. Bootstrap CIs match DataNation's robustness move while extending to held-out-label validation, which is methodologically stronger.

**Revisit if:** UFE data acquisition fails or proves messier than expected (fallback: narrow-window 2024-2025 only validation). If a precision result is exceptionally strong (≥85%), promote to pitch headline.

---

## 2026-05-21 — Independent severity signal: ACLED primary, IPC stretch

**Decision:** ACLED conflict event data is the primary independent severity signal added to the pipeline. It serves two purposes: methodological hygiene (breaking the OCHA-only circularity in the severity dimension) and substrate for the GeoAI spatial-temporal hotspot detection work. IPC food security phases are a Day 4 stretch addition if time allows.

**Alternatives considered:**
- *IPC first*: rejected because while IPC is highly relevant for hunger-driven crises, ACLED has broader applicability across all crisis types and feeds the spatial intelligence work as well.
- *Both equally weighted in v1*: rejected because doing both well in the timeframe risks doing neither well.
- *Neither — stay OCHA-only*: rejected because the PDF explicitly invites ACLED / IPC / UNHCR as enrichment, and methodological circularity is a known weakness if all severity signals come from OCHA itself.

**Rationale:** ACLED is geocoded event data from an independent academic project; it directly supports both ranking enrichment and the GeoAI capabilities. Its API is well-behaved. IPC is added later because the project can stand without it; ACLED cannot be cleanly replaced.

**Revisit if:** ACLED API access proves difficult or rate-limited beyond what the build window absorbs; if Day 4 morning has unexpected slack, IPC integration is the next stretch task.

---

## 2026-05-21 — CIRV deferred for v1

**Decision:** Do not ingest or recompute the CERF Compound Index of Risk and Vulnerability (CIRV) for v1. UFE selections alone serve as labeled ground truth for the validation layer. The composite ranking uses CIRV-free features only.

**Alternatives considered:**
- *Recompute CIRV from primary inputs* (INFORM Risk + INFORM Severity + food insecurity + conflict + early warning): rejected because the engineering lift (~6-10 hours) reproduces published OCHA work and competes with higher-differentiation work.
- *Ingest published CIRV scores from CERF methodology notes (PDFs)*: rejected because the parsing effort isn't justified by the marginal benefit in v1; CIRV's primary value would be as a baseline comparator next to our model's UFE precision, and that comparison can be added post-deadline if interesting.

**Rationale:** CIRV is OCHA's own composite index informing UFE selections. Including it as a feature would inflate validation agreement artificially (circularity); excluding it preserves clean validation. The architectural cost of skipping is low (CIRV would have been a single Bronze table plus a Silver feature).

**Revisit if:** Time permits post-deadline, OR if reviewers ask for a baseline comparison to OCHA's own institutional index.

---

## 2026-05-21 — Alert subscriptions deferred to roadmap

**Decision:** Do not build email / Slack alert subscriptions in v1. Three architectural choices are made now to keep the eventual addition cheap:

1. Gold tables carry a temporal dimension (not collapsed to a single "current" snapshot)
2. A `get_ranking_delta(country, from_period, to_period)` UC Function is built in v1 and exposed as an agent tool
3. Change indicators on the Triage screen (↑5 positions, NEW to top 10, ↓3) are computed from the same substrate alerts would consume

Methodology documentation explicitly notes alerts as a planned extension with the specific additional components required (scheduled Workflow, subscription store, delivery integration).

**Alternatives considered:**
- *Build alerts in v1*: rejected because the infrastructure required (scheduled job runner, subscription store, SMTP / Slack integration, last-notified state) is large compared to the deck's actual need (credible roadmap mention).
- *Claim alerts as roadmap without architectural support*: rejected because that is marketing, not engineering. The point of preserving the door architecturally is that the claim is credible.

**Rationale:** The synthesis identified opt-in alerts as a meaningful extension beyond HDX Signals. Building the full feature is out of scope for the time available; the three design choices listed make the eventual addition a contained extension. The change indicators on Triage serve as visible proof that the temporal substrate exists.

**Revisit if:** Post-deadline iteration moves to building user-facing alerts, OR if user feedback on the change indicators suggests they want subscription functionality.

---

## 2026-05-21 — AI/BI Dashboards embedded inside React (not parallel deliverable)

**Decision:** Use Databricks AI/BI Dashboards as embedded iframes inside the React Databricks App where they add value (Methodology screen primarily; optionally the CBPF Allocation View). Do not build a parallel AI/BI Dashboards-only surface. Custom React remains the primary frontend; embedded AI/BI Dashboards and embedded Genie are leveraged inside React where each is natively powerful.

**Alternatives considered:**
- *Build a parallel AI/BI Dashboards deliverable*: rejected because it doubles the surface count to maintain and judges aren't looking for two parallel products.
- *Skip AI/BI Dashboards entirely*: rejected because embedding selectively lets us showcase more of the Databricks platform with low marginal cost while keeping React polish on the front-of-house screens.

**Rationale:** Embedded Genie handles the Ask screen natively (transparent SQL generation, built-in feedback mechanisms). Embedded AI/BI Dashboards handle the Methodology screen naturally (data lineage exploration, auto-rendered visualizations of Gold tables). This pattern reduces React build work AND adds platform coverage. A 30-minute iframe auth / CORS spike on Day 3 morning verifies the embedding pattern works.

**Revisit if:** Iframe auth fails for embedded Genie or AI/BI (fallback: SDK-based integration with custom React chat UI, ~4-6 hours of additional work). *(Note: superseded 2026-05-21 by the Genie/AI-BI-via-API decision above. Embedding turned out not to be supported for Databricks Apps; the API-based approach replaces it.)*

---

## 2026-05-21 — Persona reconciliation: HC primary, HAO + PFM secondary, Donor Advisor tertiary

**Decision:** Update the persona structure from the original "HC primary, PFM + Donor Advisor secondary" to align with the PDF's reference structure and the IA's natural mapping:

- **Primary:** Humanitarian Coordinator (HC) — drives the default Triage UX, ~5-minute sessions, top-line decisions
- **Secondary:** Humanitarian Affairs Officer (HAO, the analyst archetype) — primary user of Crisis Explorer, Compare, Ask. ~1-hour deep-dive sessions.
- **Secondary:** Pooled Funds Manager (PFM) — primary user of the optional CBPF Allocation View. ~15-30 minute allocation sessions.
- **Tertiary** (should not be hostile to, but not optimized for): Donor Advisor — external to OCHA, uses similar analysis with different incentives and information context.

User stories in `docs/personas.md` updated to reflect the cascade.

**Alternatives considered:**
- *Keep original structure (HC + PFM + Donor Advisor)*: rejected because the PDF's reference section explicitly names HAO with a job link, and the IA (Triage / Crisis Explorer / Compare / Ask / Methodology / CBPF) maps more cleanly to HC + HAO + PFM.
- *Drop Donor Advisor entirely*: rejected because the PDF mentions donor advisors explicitly in the audience framing, and the tool's outputs should remain usable by them.

**Rationale:** HAO replaces Donor Advisor as a secondary persona because the analyst archetype is who actually drives the ~1-hour deep-dive sessions on Crisis Explorer; the PDF's job link to HAO confirms this is OCHA's recognized role. Donor Advisor remains a tertiary persona — usable but not optimized for.

**Revisit if:** Mary's feedback on the demo indicates the persona framing isn't accurate to OCHA workflow, OR if a donor advisor user test reveals significant usability gaps.

---

## 2026-05-19 — Frontend: React + Tailwind + shadcn/ui on Databricks Apps

**Decision:** Build the primary frontend in React + Tailwind + shadcn/ui, hosted via Databricks Apps with a FastAPI backend serving the React build. Streamlit was considered and rejected as the primary surface.

**Alternatives considered:**
- *Streamlit on Databricks Apps*: rejected because Streamlit's default visual identity is recognizable as "hackathon" and the polish ceiling matters for the demo recording.
- *External Vercel deployment of Next.js*: deferred as a possible portfolio-only public preview if time permits, but not the primary submission surface.
- *Next.js + shadcn external with Databricks SQL Connector*: rejected for the hackathon timeframe because integration overhead (auth, environment, CORS, deployment) consumes design time.

**Rationale:** Polish matters per the "world-class" framing emphasized in the Day 2 working session. React + Tailwind + shadcn provides a higher polish ceiling than Streamlit while keeping the frontend hostable on the same workspace as the data and agent layer. Embedded Genie and embedded AI/BI Dashboards inside the React app provide Databricks platform showcase without sacrificing design control. *(Note: the embedded-inside-React part was superseded 2026-05-21 by the API-based approach.)*

**Revisit if:** Iframe embedding for Genie or AI/BI Dashboards proves unworkable, forcing additional SDK-based integration work that exceeds the time budget. *(Note: confirmed unworkable 2026-05-21; see the Genie/AI-BI-via-API entry above for the replacement approach.)*

---

## 2026-05-19 — Multi-agent supervisor architecture

**Decision:** Build a supervisor agent (Mosaic AI ChatAgent pattern) that routes between specialist agents:

- Genie spaces (text-to-SQL over Gold tables, configured by topic: Severity & Needs, Funding & Coverage, Mismatch & Ranking, Geospatial)
- UC Functions (the seven Gold-table-backed analytical tools plus spatial tools)
- (Day 4 stretch) Knowledge Assistant for unstructured ReliefWeb situation reports

Even with only Genie and UC Functions as specialists in v1, the supervisor pattern is the architectural choice from the start. This matches the Day 2 reference architecture and keeps KA addition cheap if Day 4 has slack.

**Alternatives considered:**
- *Single chat agent with all tools registered directly*: rejected because it loses the multi-agent narrative for the deck and makes adding KA later a rewrite.
- *Direct Genie iframe with no supervisor* (just for the Ask screen): considered, but the supervisor is needed for cross-cutting queries that combine structured and unstructured reasoning, and is the foundation for the KA addition path.

**Rationale:** The supervisor architecture is the Day 2 reference architecture and is judge-flattering for the technical evaluation. It future-proofs the system for KA addition without rework. The cost of building a supervisor for just two specialist types in v1 is small (1-2 hours setup) compared to the architectural debt of a flat agent design that would need to be rewritten if KA lands as a stretch goal.

**Revisit if:** Routing logic proves too brittle on the v1 test set (fallback: simplify to direct tool invocation with the supervisor logic encoded as routing examples).

---

## 2026-05-18 — Bootstrap documentation structure

**Decision:** Adopt a tiered documentation structure with `STATE.md` and `DECISIONS.md` as Tier 1 (update every session), `claude.md` and `docs/methodology.md`, `docs/data-catalog.md`, and `docs/open-questions.md` as Tier 2 (update when relevant), and `docs/glossary.md`, `docs/personas.md`, `docs/prior-art.md`, `SUBMISSION.md` as Tier 3 (mostly write-once).

**Alternatives considered:** Wiki-style structure (rejected — adds tooling overhead), single design document (rejected — too coarse for separate update cadences), no documentation discipline (rejected — defeats the multi-surface workflow).

**Rationale:** Each surface (Claude.ai, Claude Code, the human developer) needs a single source of truth. Tiered documents with clear update protocols minimize drift across surfaces and sessions, especially since Claude Code sessions are stateless.

**Revisit if:** Documentation overhead becomes a friction point relative to the value it provides.

---

## 2026-05-18 — Primary persona: Humanitarian Coordinator (default)

**Decision:** The Humanitarian Coordinator is the primary persona for the system. UI, output formats, and user stories will be optimized for this role first.

**Alternatives considered:** Pooled Funds Manager (narrower workflow, more transactional), Donor Advisor (external to OCHA, different incentives and information environment).

**Rationale:** The Humanitarian Coordinator role most closely matches the vantage point of the mentor (Mary Keller, Information Management Officer at OCHA) and represents the broadest practical analytical workflow. Coordinator-level outputs can typically be adapted for the other two personas more readily than the reverse.

**Revisit if:** Mentor feedback indicates a different persona is more impactful, or a clear differentiation opportunity emerges for another role. *(Note: refined 2026-05-21 to add HAO as a second secondary persona; see entry above.)*

---

## 2026-05-18 — Slide deck in PowerPoint

**Decision:** Build the final deliverable deck in PowerPoint. Working copy lives in Google Drive; final PDF exports into the repo on submission.

**Alternatives considered:** Marp (markdown-to-slides, code-versioned), Reveal.js (programmable HTML), Gamma or Pitch (AI-assisted generation).

**Rationale:** PowerPoint aligns with UN OCHA institutional culture, handles mixed media (charts from notebooks, map exports, screenshots) cleanly, and has strong presenter-view support for the demo recording. Code-based slide tools would optimize for reproducibility at the cost of visual flexibility, which the deliverable rewards more.
