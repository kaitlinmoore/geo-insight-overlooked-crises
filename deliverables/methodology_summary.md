# Methodology Summary

Condensed version of `docs/methodology.md`. Two-page reading; covers the composite construction, the validation framework, and the data-handling choices that determine what the ranking does and does not claim.

For the full version with all sub-signal definitions, edge-case handling, and the calibration roadmap, see `docs/methodology.md`.

## What the ranking measures

A composite **`overlooked_score`** per (country, year), normalized to a within-year percentile rank. Seven components contribute:

| Component | Direction | What it captures |
|---|---|---|
| `gap_ratio` | + | Funded paid ÷ requirement — the headline funding gap |
| `severity_rate` | + | INFORM severity category × population-affected denominator |
| `chronic_index` | + | Sustained gap depth over a 5-year window (chronic-vs-acute distinguisher) |
| `dollars_per_pin_inv` | + | Inverse of dollars-per-person-in-need (low $/PIN raises the score) |
| `sector_imbalance` | + | Std-dev of sector-level coverage shares (uneven funding raises the score) |
| `media_attention` | **−** | ReliefWeb report volume (high media attention LOWERS the overlooked-ness score) |
| `geographic_isolation` | + | Three sub-signals: data sparsity, inverse ACLED density, contested-border flag |

The minus-signed `media_attention` component is the methodological backbone of the "overlooked" framing. A country with a wide funding gap that gets a lot of media coverage is *underfunded*, not overlooked. A country with the same gap and minimal coverage is overlooked.

### How components combine

Each component is normalized to a within-year percentile rank (0 to 1), weighted, and summed. Missing components renormalize the weights of the remaining components so a country with one missing sub-signal isn't unfairly advantaged or penalized. The seven-component decomposition is stored as `gold_explanation_features` per country/year; the contributions sum to the `overlooked_score` by construction, enforced as a self-check at Gold build time.

Weights for v1 are set from humanitarian-domain priors. Empirical weight calibration from UFE selections on held-out years is a v2 work item.

## Three-layer validation

The ranking is checked against three independent benchmarks. None alone is sufficient; together they bound what the ranking can claim.

### Layer 1: UFE precision

The Central Emergency Response Fund's Underfunded Emergencies window allocations are humanitarian convention's clearest signal of overlooked-ness. Train on UFE rounds 2009-2023; test precision and recall at K=15 on 2024-2025 rounds. Stored in `gold_ufe_validation`.

Held-out validation is the strongest test we can run with the available data.

### Layer 2: ECHO FCA + NRC overlap

Two independent published lists name the most-neglected crises annually: DG ECHO's Forgotten Crises Assessment (binary list) and the Norwegian Refugee Council's Most Neglected Displacement Crises (ranked top-10). Compare the top-15 against both. Stored in `gold_external_overlap`.

This catches systematic regional bias or methodology blind spots — if our top-15 has zero overlap with ECHO's list, something is wrong with the methodology or wrong with ECHO's list, and we need to investigate which.

### Layer 3: Bootstrap stability

Resample weight schemes 500 times within plausible bounds (each weight perturbed ±20%); track which countries stay in the top-N across configurations. A country whose ranking is highly weight-sensitive gets `stable_top_n = false`; one whose ranking holds across the bootstrap gets `stable_top_n = true`. Stored in `gold_bootstrap_ci`; surfaced in the agent's responses via the `rank_ci_low`/`rank_ci_high` columns.

The frontend and the agent never report a rank without the CI. That's the agreement with the user: the rank is a point estimate over a methodology with chosen weights; the CI is the volume of plausible rankings under reasonable variants of those weights.

## Data handling choices that matter

### Multi-country flow cascade

FTS flow records often span multiple recipient countries (`destLocations` is a comma-delimited ISO3 list). At the methodology pass, these flows get allocated across countries via a cascade:

1. **Requirements-weighted** if all destinations have HRP requirements (the modal case, ~68.5% of flow dollars).
2. **Population-weighted fallback** if some destinations lack requirements.
3. **`regional_unattributed`** if no allocation info is available — preserved as a side-output (`gold_regional_unattributed`) so the dollars aren't dropped silently. 2026 has $4.18B parked at regional level via this path.

### Chronic vs. acute

A crisis is `chronic_neglect` if `gap_ratio >= 0.6` for 5+ consecutive years AND `severity_category_max >= 3`. A crisis is `acute_deterioration` if the year-over-year gap widened by ≥15 percentage points. A crisis lacking an HRP plan is flagged `chronic_no_plan` (the most operationally invisible category — no plan means no advocacy substrate). Stored as `neglect_class` on `gold_forgotten_crisis_index`.

### Subnational handling

Admin1 rankings are computed where data permits. Three constraints determine availability:

1. HNO 2026 dropped admin-level columns — subnational analysis for 2026 falls back to admin1 P-code rollup from earlier years where available.
2. Yemen, Myanmar, Nigeria have zero admin2 population in COD-PS — the pipeline degrades to admin1 + `data_sparsity_flag`.
3. Admin1 funding is **inferred** (PIN-proportional from country-paid funding), not observed. The `is_inference_flagged` column is always true on `gold_subnational_index` to surface this.

The agent's `get_subnational_breakdown` UC Function returns empty for countries lacking subnational data rather than fabricating, and the frontend Crisis Explorer shows a data-sparsity callout instead of a misleading admin1 view.

## Responsible AI

Seven custom judges run via `mlflow.evaluate()` against a 40-case eval set (`notebooks/evaluation/eval_set.json`):

1. `grounded_numerics` — every numeric claim traces to a Gold row
2. `citation_completeness` — every fact carries a (iso3, year, table) citation
3. `honest_uncertainty` — "I don't know" surfaces when data is missing or out of scope
4. `geographic_fairness` — consistent explanatory depth across regions
5. `counterfactual_stability` — small input perturbations produce small output changes
6. `driver_disclosure` — ranking responses include top 3 contributing features
7. `decision_support_framing` — output never recommends specific allocation actions

The RAI Scorecard on the Methodology screen reads aggregate scores from the MLflow experiment. Judge prompts at `notebooks/evaluation/judges/`.

The seventh judge is the one that constrains the system's role most directly: this is a triage and explanation tool, not an allocation advisor. The agent presents evidence; humans decide.

## What this methodology does NOT claim

- **Not predictive.** The ranking is descriptive of the present state given observed data. It does not forecast which crises will get worse next year. Trend analysis surfaces direction; not forecast.
- **Not causal.** A wide funding gap reflects donor decisions, not recipient-country attributes. The methodology does not attribute the gap to governance, geopolitics, or any other causal factor.
- **Not exhaustive.** The seven components capture the methodology team's best operational definition of "overlooked" given the available data. Other reasonable definitions exist; the methodology is transparent and the weights are exposed so any operator can re-run with their own definition.
- **Not real-time.** Data freshness varies by source: HNO is annual, FTS is daily, INFORM Severity is monthly, ACLED events have a 12-month account-tier embargo (the companion `acled_severity` HDX feed is current to last month). The Methodology screen surfaces data-freshness indicators.

## v1 limitations to know about

Documented in detail at `/deliverables/databricks_artifacts.md` and in the slide deck's limitations slide. Headlines:

- **Serverless trial deployment.** Spatial operations via Apache Sedona deferred; boundary geometry served as static GeoJSON; contested-border sub-signal uses a curated reference list instead of computed polygon adjacency. No methodology change from a classic-compute deployment.
- **HNO 2026 subnational gap.** 2026 HNO data is country-only; subnational coverage for 2026 falls back where possible.
- **CBPF Contributions are global donor totals.** Source has no country attribution. Donor identity for the per-country `donor_concentration` analysis comes from FTS only.
- **Weights are priors, not empirical calibration.** Bootstrap CIs quantify the ranking's sensitivity to weight choices; the calibration itself is v2.

## What v2 looks like

- Empirical weight calibration from UFE on held-out windows
- Knowledge Assistant: RAG over the ReliefWeb situation-report corpus (corpus acquired, endpoint provisioned, index not populated)
- Alert subscriptions: time-versioned Gold tables already support the architectural hook
- Reactivated boundary pipeline if classic compute becomes available
- IPC food security as a second independent severity signal

Each v2 item has a specific architectural hook already in place. The path from v1 to v2 isn't a rewrite — it's an extension.
