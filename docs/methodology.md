# Methodology

How the project computes the mismatch between documented humanitarian need and funding coverage, ranks crises by how overlooked they appear, and provides defensible evidence for those rankings.

> **Note on scope.** This document specifies the analytical methodology — the formulas, thresholds, and design choices that govern ranking. Implementation details (table schemas, function signatures) live in `docs/schemas.md` and `docs/architecture.md`. Decision provenance is in `DECISIONS.md`.

## Conceptual framework

The challenge brief, the Day 1 framing from Mary Keller (UN OCHA Information Management Officer), and the prior humanitarian-financing literature converge on a multi-dimensional definition of "overlooked." The system operationalizes that definition rather than collapsing it to a single funding gap.

Mary Keller's framing identifies four reasons crises become overlooked:

- **Donor fatigue.** A crisis that has continued for years sees attention and resources drift away even as need persists.
- **Media attention moving on.** When coverage subsides, advocacy and political pressure weaken.
- **Weak advocacy.** Some crises lack institutional champions and are systematically under-resourced relative to their scale.
- **Where they are located.** Geographic isolation, contested borders, and political marginality all reduce visibility.

A defensible ranking captures the first three through structured signals (chronic neglect, media attention, sector-specific gaps) and the fourth through subnational and spatial analysis.

The ranking operates at country granularity by default and admin1 granularity where data supports it. The composite score combines:

- **Need.** Documented humanitarian need: people in need (PIN), severity, population at risk.
- **Coverage.** Funding received as a fraction of documented requirements.
- **Attention.** Media presence as a proxy for visibility and advocacy. Lower attention amplifies overlooked-ness; higher attention reduces it.
- **Persistence.** Whether the underfunded state is chronic (multi-year) or acute (recent deterioration). Surfaced as a separate classification rather than blended into the composite.
- **Context.** Geographic and contextual factors that amplify or mitigate the headline signal — sector imbalance, donor concentration, geographic isolation.

The ranking is **deterministic.** The composite score, component breakdowns, and confidence intervals are all computed from structured data via auditable transformations. LLM agents in the system explain rankings in natural language; they do not produce or alter ranks.

## Source data

The mismatch ranking draws on six primary OCHA data sources.

**HNO (Humanitarian Needs Overview).** Annual people-in-need figures by country, sector, and (where available) admin1. Source of the PIN denominator and severity dimension.

**HRP (Humanitarian Response Plan).** Plan-level funding requirements; the "asked for" denominator in `gap_ratio`. Provides plan codes that join HNO to FTS.

**FTS (Financial Tracking Service).** Flow-level funding records with status (paid, committed, pledged). Numerator in `gap_ratio`. Multi-country flows are allocated to specific countries in Silver (see Multi-country flow allocation below).

**CBPF (Country-Based Pooled Funds).** Audited OCHA-controlled allocations and contributions. Source for pooled-fund-specific analysis and the optional CBPF Allocation View.

**CERF (Central Emergency Response Fund).** OCHA's global emergency fund, with Rapid Response (RR) and Underfunded Emergencies (UFE) windows. UFE selections are used as labeled ground truth for validation (see Validation strategy).

**INFORM Severity (formerly GCIS).** Monthly composite severity index from ACAPS, 0-5 scale across 35 indicators. Provides multi-year severity tracking for the chronic_index.

Two enrichment sources supplement the OCHA primary data:

**ACLED (Armed Conflict Location and Event Data).** Geocoded conflict events from an independent academic project. Used for the independent severity signal (breaking OCHA-only circularity) and spatial-temporal hotspot detection.

**ReliefWeb situation reports.** OCHA's humanitarian information portal. Used for media presence as a visibility proxy (negative-weighted in the composite) and, as a Day 4 stretch goal, narrative context via Knowledge Assistant.

Two reference and boundary sources support geographic and demographic analysis:

**COD-PS Population.** UN Common Operational Dataset, population by admin level. Denominator for severity_rate and population-weighted multi-country flow allocation fallback.

**fieldmaps.io GeoParquet boundaries.** Edge-matched subnational admin boundaries with UN p-codes that join cleanly to HNO admin data.

Validation comparators (Layer 2; see Validation strategy):

**ECHO Forgotten Crises Assessment.** DG ECHO's annual list of forgotten crises.

**NRC Most Neglected Displacement Crises.** Norwegian Refugee Council's annual NGO list.

The CIRV (Compound Index of Risk and Vulnerability) is **deliberately excluded** from the ranking model. CIRV informs CERF UFE selections, which the system uses as labeled ground truth; including CIRV as a feature would artificially inflate validation agreement. See `DECISIONS.md` entry 2026-05-21.

## Severity gate

Crises enter the ranking only if they meet at least one of three documented-need thresholds:

- INFORM Severity Index 4 or 5 (national level), OR
- PIN above a minimum threshold (initial value: 100,000 people; configurable), OR
- Active Humanitarian Response Plan in the year of analysis

Crises that fail all three gates are excluded from the headline ranking but logged in a separate `excluded_with_signal` table for transparency. This list is itself a signal: countries with low documented need *and* low coverage may simply have data gaps rather than actual low need.

A second-pass severity check captures countries with no HRP but persistent INFORM Severity ≥ 3 across multiple years. These flow into the `chronic_no_plan` classification (see Temporal classification).

## Component metrics

Component metrics are computed at country × year granularity (and country × year × sector where indicated). Each is a documented value pulled from primary sources, with no smoothing or imputation beyond what is explicitly noted.

### Funding gap ratio

The core mismatch signal:

```
gap_ratio = (HRP_requirement_usd − FTS_funding_paid_usd) / HRP_requirement_usd
```

Range: 0 (fully funded) to 1 (no funding received). Higher values indicate larger funding gaps.

Implementation notes: use `paid` status from FTS as the headline numerator; `committed` and `pledged` flows are carried as separate columns for the optional three-stage funnel view. Where `HRP_requirement_usd` is zero or null, `gap_ratio` is undefined and the country falls into the `chronic_no_plan` or `well_funded` bucket depending on other signals.

### Dollars per person in need

A cross-crisis fairness signal that captures per-capita investment level:

```
dollars_per_pin = FTS_funding_paid_usd / HNO_people_in_need
```

Complementary to `gap_ratio`. A country can have a low `gap_ratio` (most of what was asked for arrived) but low `dollars_per_pin` (because what was asked for was modest relative to need). The composite uses `1 - normalized(dollars_per_pin)` so that low dollars-per-PIN contributes to higher overlooked scores.

### Severity rate

Need normalized by population:

```
severity_rate = HNO_people_in_need / COD_PS_population
```

Captures the intensity of crisis relative to country scale. A 5-million PIN figure means very different things in a country of 30 million versus a country of 8 million.

### Sector imbalance

Within-country sectoral neglect — captures the case Mary Keller explicitly named ("a country can have a lot of money, but almost nothing's been allocated to health care"):

```
sector_gap_i      = (sector_requirement_i − sector_funding_i) / sector_requirement_i
sector_imbalance  = std_dev(sector_gap_i across all reported sectors)
```

Higher values indicate uneven sector coverage. A country with uniform 50% coverage across all sectors has low sector_imbalance; a country with 90% coverage in food security but 15% in health has high sector_imbalance.

### Chronic index

Multi-year structural neglect (powers the bonus task):

```
chronic_years_count = COUNT(years in last 5 where gap_ratio > 0.5)
mean_chronic_gap    = MEAN(gap_ratio over those chronic_years_count years)
chronic_index       = chronic_years_count × mean_chronic_gap
```

Range: 0 (never significantly underfunded in last 5 years) to ~5 (consistently severely underfunded). The 0.5 threshold is a placeholder, configurable and reported in the methodology slide.

This formulation distinguishes:

- A country with one year of 95% gap (chronic_index ≈ 0.95) — acute, not chronic
- A country with four years averaging 60% gap (chronic_index ≈ 2.4) — chronic

### Media attention

Visibility proxy from ReliefWeb situation reports:

```
media_attention = COUNT(ReliefWeb situation reports about country in last 12 months)
```

Range varies by data window. Normalized to 0-1 within year via percentile rank across all in-scope countries.

The composite applies this signal with **weight magnitude 0.10 and a negative sign** (`overlooked_score = … − 0.10 × media_attention_norm + …`). The negative sign is the operationalization of "overlooked" — a crisis with high media attention is not overlooked, no matter how underfunded. A crisis can be severely underfunded and yet not overlooked if it commands sustained advocacy and coverage; conversely, a crisis can be moderately underfunded but truly overlooked because no one is talking about it.

### Geographic isolation

A bounded need-multiplier capturing Mary Keller's "where they are located" dimension. The isolation score combines:

- Distance from in-country population centroids to the country's largest urban center (greater distance increases isolation)
- ACLED event density within and adjacent to the area (higher density reduces the "no advocacy" component because conflict draws monitoring)
- Subnational data sparsity in HNO and INFORM (lack of data is itself a signal of low visibility)
- Adjacency to contested or marginal borders (presence of OCHA-flagged contested-territory boundaries)

```
geographic_isolation = weighted_combination(
  normalized_distance_to_urban_center,
  inverse_normalized_acled_density,
  normalized_data_sparsity,
  contested_border_flag
)
```

Range 0 to 1. The weighted combination is calibrated empirically on a small reference set (initial weights are placeholders). Used as a need-multiplier in the composite rather than as a separate vote — isolated places have less visible need *for the same underlying scale*, so the composite amplifies the gap signal in those contexts.

This is the most novel and least battle-tested component. The methodology slide explicitly notes it as a v1 contribution with calibration to be validated against historical UFE selections (do isolated countries appear more often in UFE than less-isolated countries with similar gap_ratios?).

## Composite overlooked score

The overlooked_score combines normalized component metrics with bootstrap-stabilized weights:

```
overlooked_score = w1 × norm(gap_ratio)
                 + w2 × norm(severity_rate)
                 + w3 × norm(1 - dollars_per_pin)
                 + w4 × norm(chronic_index)
                 + w5 × norm(sector_imbalance)
                 - w6 × norm(media_attention)
                 + w7 × norm(geographic_isolation) × norm(severity_rate)

Initial illustrative weights (placeholders, to calibrate):
w1 ≈ 0.30  (funding gap — primary signal)
w2 ≈ 0.20  (severity rate)
w3 ≈ 0.10  (per-capita investment)
w4 ≈ 0.15  (chronic index — bonus task contribution)
w5 ≈ 0.10  (sector imbalance)
w6 ≈ 0.10  (media attention — magnitude 0.10, applied with negative sign)
w7 ≈ 0.05  (geographic isolation, as need multiplier)
```

The seventh term is the geographic isolation interaction — isolation amplifies the severity signal because the same severity is more concerning when fewer people are watching.

### Normalization: within-year percentile rank

Each component is **percentile-ranked within year** across all in-scope countries before weighting. This is DataNation's robustness move and is methodologically important: raw values vary by orders of magnitude across countries (Sudan's PIN figure isn't directly comparable to Haiti's in absolute terms), but percentile rank within year is robust to scale differences.

```
norm(metric_i) = percentile_rank_within_year(metric_i)
```

Range 0 to 1. The country with the highest gap_ratio that year is at percentile 1.0 on that component; the lowest is at percentile 0.0.

### Bootstrap uncertainty

The composite score is reported with a 95% bootstrap confidence interval on rank position. The procedure:

1. Sample weight perturbations from a Dirichlet distribution centered on the nominal weights, with small variance (~0.05).
2. Recompute the ranking under each sampled weight vector.
3. For each country, the 95% CI on rank position is the [2.5%, 97.5%] percentile range across bootstrap samples (500 samples in v1).

A country with a stable rank ("Sudan is #2 with 95% CI [#1, #3]") is high-confidence. A country with a wide CI ("Burkina Faso is #15 with 95% CI [#7, #28]") is reported with its uncertainty visible.

The agent never reports ranks without uncertainty. This is a hard rule from the brief: "surface uncertainty clearly and avoid presenting gap scores with false precision."

### Stability flag

A country carries `stable_top_n = TRUE` if it appears in the top 10 across at least 90% of bootstrap samples. This is the strongest evidence that a country's rank is robust to methodological choices, matching DataNation's robustness check and extending it.

## Temporal classification

Independent of the headline overlooked_score, every country receives a `neglect_class` label that distinguishes patterns of underfunded-ness over time:

- `chronic_neglect` — `chronic_years_count` ≥ 3 in the last 5 years
- `acute_deterioration` — `chronic_years_count` < 3 but current-year `gap_ratio` ≥ 0.5
- `improving` — `gap_ratio` has decreased monotonically over the last 3 years and current year ≤ 0.3
- `well_funded` — `chronic_years_count` = 0 AND current-year `gap_ratio` ≤ 0.3
- `chronic_no_plan` — country has had no HRP for 3+ consecutive years but INFORM Severity ≥ 3 or PIN ≥ 100,000 in those years (need exists without a plan to address it)

The classification is presented separately from the composite score, not blended. The Triage screen exposes a toggle: rank by current mismatch (overlooked_score) or rank by structural neglect (`chronic_neglect` plus `chronic_no_plan` filter, sub-sorted by chronic_index).

This directly answers the brief's bonus question: structural and acute neglect deserve different framing and different advocacy. The deck slide on the bonus task includes a short example of how the ranking changes under each lens.

## Multi-country flow allocation

FTS records funding flows at the plan level, but some plans cover multiple countries (Syria 3RP covers SYR + LBN + JOR + TUR + IRQ; Sahel Response covers BFA + MLI + NER + TCD + MRT). These multi-country flows must be allocated to specific countries for country-level ranking. The allocation cascade, applied in Silver:

1. **Flow has a country tag in the source record** → use the tag. Method: `country_tagged`.
2. **Multi-country plan with per-country requirements documented** → allocate proportional to each country's HRP requirement within the plan. Method: `requirements_weighted`.
3. **Multi-country plan without per-country requirements** → allocate proportional to country population from COD-PS. Method: `population_weighted_fallback`.
4. **No country tag and no country list** → exclude from country-level analysis, report in aggregate. Method: `regional_unattributed`.

Each split row in `silver_fts_flows` carries `allocation_method`, `allocation_weight`, and `source_flow_id` for full lineage back to `bronze_fts_flows`. The methodology slide reports the fraction of total flow value falling into each method as a transparency measure.

Why this cascade order: plans are negotiated bottom-up with per-country requirements that reflect humanitarian need, so where a `destPlan` is attached and per-country requirements are documented, `requirements_weighted` is the most defensible split. In practice this is rare — profiling of FTS incoming flows (`docs/notes/data_profiling.md`) finds that 99% of multi-country flows carry no `destPlan`, so the de facto handler for multi-country attribution is `population_weighted_fallback`. The cascade preserves the theoretically preferred method as the first applicable step while acknowledging that the operative method for ~30% of incoming dollars is population-weighted. Each `silver_fts_flows` row carries its `allocation_method`, and the Methodology screen reports the share of total flow value by method as transparency. Equal-split is rejected as a fallback because population, even where weak, uses more information.

## Sector-level analysis

The composite ranking is country-level, but every country in the ranking is decomposable to sector level via `gold_sector_coverage`. A country whose top-line `gap_ratio` is low may still have severe sector-specific gaps. The Crisis Explorer screen surfaces these:

```
sector_gap_i = (sector_requirement_i − sector_funding_i) / sector_requirement_i
```

Sectors are flagged in the Crisis Explorer when `sector_gap_i > 0.7` AND that sector's contribution to PIN is ≥ 10% of country total.

Sector taxonomy: HNO cluster names, FTS sector codes, and CBPF categorizations don't align exactly. A small crosswalk CSV (~20 rows) harmonizes them in Silver. The crosswalk is documented in `docs/data-catalog.md` (to be generated from Bronze profiling).

## Geographic methodology

Geographic analysis operates at two levels and contributes three additional signals.

### Subnational ranking

Where HNO subnational data exists (admin1 PIN, INFORM Severity at admin1), the system computes admin1-level rankings via `gold_subnational_index`. Country-level ranks are aggregations of subnational results, with explicit visibility into which admin1 areas drive a country's national score.

For countries without machine-readable admin1 HNO data, the system carries a `data_sparsity_flag` and ranks at country level only. The Crisis Explorer screen surfaces this flag explicitly: a country may rank high because of one severely affected admin1 area or because of widespread moderate need across all admin1 areas. These are different situations and deserve different framing.

### Subnational funding inference

Country-level FTS funding doesn't disaggregate to admin1 in source data. The system infers admin1 funding proportional to admin1 PIN share:

```
admin1_inferred_funding = country_total_funding × (admin1_PIN / country_total_PIN)
```

This is an estimate, explicitly flagged as such in the UI and methodology. It's defensible because humanitarian response within a country generally tracks need distribution; the inference is wrong only when sector or geographic targeting deviates from PIN distribution.

Dr. Kurland touchpoint: validate this inference methodology against any published OCHA subnational tracking for select countries.

### ACLED spatial-temporal hotspot detection

ACLED events are H3-indexed (resolution 5) and clustered spatially and temporally to identify emerging hotspots:

- Spatial: H3 cells with event density > 2σ above country mean
- Temporal: trailing 90-day window, with new hotspots flagged when density jumps > 50% from prior 90 days

Hotspots are surfaced as overlays on the Crisis Explorer map and feed the `subnational_hotspots(country, threshold)` agent tool. They enable acute-deterioration detection ahead of annual HNO updates — addressing Mary's "sudden onset emergency" framing.

### Cross-border patterns

The `gold_cross_border_patterns` table (Day 4 if time allows) identifies admin1 areas in country A that are adjacent to overlooked admin1 areas in country B. This surfaces regional dynamics that country-level rankings hide — the Sahel, the Horn of Africa, Lake Chad Basin, Northern Central America.

Adjacency is computed once from `silver_boundaries` (fieldmaps.io GeoParquet). Cross-border crisis classification flags admin1 pairs where both are in the top 30% of `overlooked_score` and share a boundary.

### Boundary and projection conventions

- Boundary source: fieldmaps.io GeoParquet, preferred over GADM because it uses UN p-codes that join cleanly to HNO admin data, and preferred over per-country COD-AB because it's edge-matched globally.
- Storage CRS: EPSG:4326 (WGS84).
- Display CRS for web tiles: EPSG:3857 (Web Mercator).
- Disputed territories (Western Sahara, Kosovo, Crimea) follow fieldmaps.io conventions, which generally track OCHA's operational treatment. Edge cases are listed in `docs/open-questions.md` for Dr. Kurland's review.

## Validation strategy

The ranking is validated against three independent benchmarks, in service of jury criterion #2 ("relevance and defensibility of the ranking").

### Layer 1 — UFE selections as labeled ground truth

CERF Underfunded Emergencies selections constitute OCHA's twice-yearly institutional answer to "which crises are most underfunded." Validating against UFE asks: does our ranking, computed independently, align with OCHA's own determination?

Procedure:

1. Build a labeled dataset: country × year × UFE round, binary `ufe_selected ∈ {0, 1}`.
2. Hold out the most recent rounds (2024-2025, ~4 rounds × ~15 countries = ~60 country-round labels) as the test set.
3. For each held-out round, compute our ranking at that point in time using only data available before the round.
4. Report precision (top-K predictions that are UFE-selected) and recall (UFE-selected countries that appear in our top-K) at K=15.

The historical window from 2009 onward provides additional context and stability evidence, but the headline number is the held-out precision/recall.

### Layer 2 — Multi-source comparators

Compare top-N against the DG ECHO Forgotten Crises Assessment annual list and the NRC Most Neglected Displacement Crises list. These are independent, mature, third-party benchmarks.

Procedure:

1. For each year (2015-2025), compare our top-15 against ECHO FCA top-15 and NRC top-10.
2. Report Jaccard overlap or set overlap (number of countries in both lists).
3. Discuss exceptions: countries in ECHO/NRC but not ours (potential blind spots), countries in ours but not ECHO/NRC (potential novel insights).

### Layer 3 — Internal robustness

Bootstrap CIs on the overlooked_score (see Composite overlooked score above). The stability flag (`stable_top_n`) is reported per country.

### CIRV circularity caveat

UFE selections are partly determined by CIRV (CERF's Compound Index of Risk and Vulnerability). A model that uses CIRV as a feature and is validated against UFE would inflate agreement artificially. The system uses CIRV-free features in the ranking model. CIRV is explicitly excluded; see `DECISIONS.md` entry 2026-05-21.

## Honesty commitments

These are not stylistic preferences; they are hard requirements from the brief that shape every output.

### No false precision

Composite scores are not reported with decimal-place precision that exceeds the bootstrap CI. "Sudan is ranked #2 with 95% CI [#1, #3]" is honest; "Sudan's overlooked score is 0.8347" is not.

Percentages in the UI round to whole numbers ("83% unfunded"), not decimal fractions.

### Surfaced uncertainty

Every ranked output carries:

- Bootstrap CI on rank position
- Data freshness indicators (when was HNO last updated for this country)
- Coverage flags (no HRP, no recent INFORM update, missing sector data, data sparsity at admin1)

Crises with high uncertainty are not silently dropped or rolled into "low confidence" buckets. They're shown with their uncertainty visible, because crises with the most uncertain data are often the most overlooked.

### Missing data is signal

Countries with no HRP, stale PIN, or partial INFORM coverage receive `chronic_no_plan` or `data_sparsity` classifications rather than being excluded. The system explicitly flags these as situations where the absence of documentation may itself indicate neglect.

### Decision support, not decision making

The system surfaces patterns. It does not recommend allocations. The agent layer is instructed to refuse prescriptive framing ("Should we cut funding to Yemen?" — refused; "What does the data show about Yemen's funding situation?" — answered). One of the seven Responsible-AI judges explicitly tests this boundary (`decision_support_framing`).

The Briefing agent output uses analytical language ("Yemen's response is currently funded at 32% of requirements, with the largest gap in the health sector") rather than recommendation language ("Yemen should receive additional funding").

### Explainability is graded

Every ranked country is accompanied by:

- The composite score with bootstrap CI
- The component breakdown (which signals drove this ranking)
- A deterministic decomposition ("Crisis X scores 0.87: gap_ratio contributes 0.35, severity_rate 0.21, chronic_index 0.18, donor_concentration 0.13")
- LLM-generated natural-language explanation as a complement, never a replacement
- The neglect_class classification
- Data freshness and coverage flags

A humanitarian analyst should be able to defend the ranking in front of donors using the deterministic decomposition alone; the LLM explanation is for readability.

## Open methodological questions

These are flagged here for transparency and tracked in `docs/open-questions.md`.

- **Composite weight calibration.** The illustrative weights given above are starting values, not final. Empirical calibration against UFE selections may justify different weights. The methodology slide explicitly notes weights as configurable.
- **Geographic isolation calibration.** The four-component isolation score requires empirical validation. Initial reference set is the 10-15 countries that have appeared most often in UFE rounds; the test is whether high-isolation countries are over-represented relative to their gap_ratio percentile.
- **Subnational HNO coverage.** Which countries have machine-readable admin1 HNO data is determined at Bronze profiling time; the methodology supports graceful degradation to country level with `data_sparsity_flag`.
- **Sector taxonomy crosswalk.** The HNO/FTS/CBPF sector mapping is built from public documentation and reference cases. Edge cases (e.g., Protection as a cross-cutting cluster, not a single sector) are documented in `docs/data-catalog.md`.
- **Chronic threshold (gap_ratio > 0.5).** Placeholder; may be calibrated empirically. The methodology slide reports the threshold and notes it as configurable.

## References

The methodology builds on and differs from established humanitarian-financing analyses.

**NRC "World's Most Neglected Displacement Crises"** — the closest precedent for our composite framing. Combines need, coverage, and attention into an annual ranking. NRC publishes the methodology; our composite extends to multi-year tracking, sector decomposition, and held-out validation.

**ECHO Forgotten Crises Assessment** — uses INFORM + media monitoring + FTS per-capita + qualitative ECHO assessment. Methodology not publicly detailed, but the list is published. Used as a Layer 2 comparator.

**CIRV** (Rost, Ham, Kaffes, 2026) — OCHA's own composite index for CERF UFE selections. Published February 2026 in *Journal of International Humanitarian Action*. Excluded from our model to preserve validation cleanliness.

**DataNation Forgotten Crisis Index** (2026 CMU datathon winner) — used percentile-rank within year on a single funding-gap signal. Our methodology extends to multi-dimensional composite, multi-year temporal classification, geographic depth, and external validation.

**ACAPS INFORM Severity** — methodology documented at acaps.org. Source of our severity data; multi-year trend feeds chronic_index.

The hackathon brief itself is the authoritative source for the project's goals; see `UNOCHA_Challenge.pdf` and Mary Keller's Day 1 framing in `Day_1__Databricks___UN_OCCHA___Heinz_Ha__Transcript.txt`.
