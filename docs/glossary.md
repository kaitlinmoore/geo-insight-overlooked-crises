# Glossary

Terms used across the project, for two kinds of reader: a humanitarian-domain reader who may not know the Databricks vocabulary, and a Databricks-domain reader who may not know the OCHA acronyms. Definitions are scoped to how each term is used *here*; consult the cited source for the canonical definition.

Cross-references use *see also*. Source tags identify the originating institution or framework.

## 1. OCHA core concepts

**CBPF (Country-Based Pooled Fund).** OCHA-managed humanitarian funds that pool donor contributions at the country level and allocate them to response activities within that country. Audited allocation and contribution records feed the optional CBPF Allocation View. *See also* CERF, FTS. *Source: OCHA term.*

**CERF (Central Emergency Response Fund).** OCHA's global emergency fund, operating two windows: Rapid Response (RR) and Underfunded Emergencies (UFE). *See also* RR, UFE, CIRV. *Source: OCHA term.*

**Cluster system.** The coordination structure that groups humanitarian response by sector (e.g., Health, Protection, Food Security, WASH). HNO need and FTS funding are both reported by cluster, enabling sector-level gap analysis. *See also* sector_imbalance, sector taxonomy crosswalk. *Source: OCHA / IASC term.*

**FTS (Financial Tracking Service).** OCHA's record of humanitarian funding flows, each tagged with a status (paid, committed, pledged). The paid amount is the numerator in `gap_ratio`. Multi-country flows are split to specific countries in Silver. *See also* gap_ratio, multi-country flow allocation cascade. *Source: OCHA term.*

**HNO (Humanitarian Needs Overview).** Annual OCHA assessment of people in need by country, sector, and where available admin1. Source of the PIN figures and the severity dimension. *See also* PIN, HRP, admin1. *Source: OCHA term.*

**HRP (Humanitarian Response Plan).** The annual costed plan stating funding requirements for a crisis. Its requirement figure is the "asked for" denominator in `gap_ratio`; its plan codes join HNO need to FTS funding. *See also* HNO, FTS, gap_ratio. *Source: OCHA term.*

**PIN (People in Need).** The estimated number of people requiring humanitarian assistance, drawn from the HNO. Denominator for `dollars_per_pin` and `severity_rate`. *See also* HNO, severity_rate. *Source: OCHA term.*

**RR (Rapid Response).** The CERF window that funds sudden-onset or rapidly deteriorating emergencies, as distinct from the UFE window. *See also* CERF, UFE. *Source: OCHA term.*

**UFE (Underfunded Emergencies).** The CERF window that allocates funding to chronically underfunded crises, selected twice yearly. UFE selections are used as labeled ground truth for validation. *See also* CERF, CIRV, held-out validation. *Source: OCHA term.*

## 2. Severity and risk frameworks

**CIRV (Compound Index of Risk and Vulnerability).** CERF's composite index informing UFE selections (Rost, Ham, Kaffes, 2026). Deliberately **excluded** from this project's ranking model, because using it as a feature while validating against UFE would inflate agreement. *See also* UFE, held-out validation. *Source: OCHA / CERF.*

**GCIS (Global Crisis Severity Index).** The predecessor naming for what is now the INFORM Severity Index. References to GCIS and INFORM Severity denote the same ACAPS product. *See also* INFORM Severity Index. *Source: ACAPS framework.*

**INFORM Risk Index.** A forward-looking composite measuring a country's risk of humanitarian crisis from hazard, exposure, and coping-capacity dimensions. Distinct from INFORM Severity, which measures current severity. *Source: INFORM / JRC.*

**INFORM Severity Index.** A monthly composite severity score from ACAPS, on a 0–5 scale across 35 indicators, measuring the current severity of a crisis. Drives the severity gate and the multi-year `chronic_index`. Formerly GCIS. *See also* GCIS, severity gate, chronic_index. *Source: ACAPS framework.*

## 3. External data

**ACLED (Armed Conflict Location and Event Data).** An independent academic project providing geocoded conflict-event records. Used as an OCHA-independent severity signal and for spatial-temporal hotspot detection. *See also* H3 indexing, geographic_isolation. *Source: ACLED.*

**COD (Common Operational Dataset).** UN-curated reference datasets used across humanitarian responses. This project uses COD-PS (population statistics) as a denominator and COD-AB (administrative boundaries) as a comparator. *See also* COD-PS, p-code. *Source: OCHA term.*

**COD-PS.** The population-statistics Common Operational Dataset, giving population by administrative level. Denominator for `severity_rate` and for the population-weighted fallback in flow allocation. *See also* COD, severity_rate. *Source: OCHA term.*

**DG ECHO.** The European Commission's Directorate-General for European Civil Protection and Humanitarian Aid Operations. Publisher of the Forgotten Crises Assessment. *See also* ECHO FCA. *Source: European Commission.*

**ECHO FCA (Forgotten Crises Assessment).** DG ECHO's annual list of forgotten crises, built from INFORM, media monitoring, FTS per-capita data, and qualitative assessment. Used as a Layer 2 validation comparator. *See also* DG ECHO, NRC, held-out validation. *Source: DG ECHO.*

**fieldmaps.io.** Source of edge-matched subnational administrative boundaries in GeoParquet format, carrying UN p-codes that join cleanly to HNO admin data. Preferred over GADM and per-country COD-AB. *See also* p-code, COD. *Source: fieldmaps.io.*

**IPC (food security phases).** The Integrated Food Security Phase Classification, a five-phase scale of food-insecurity severity. A Day 4 stretch signal in this project. *Source: IPC Global Partners.*

**NRC (Norwegian Refugee Council).** An NGO that publishes the annual "World's Most Neglected Displacement Crises" list, the closest published precedent for this project's composite framing. Used as a Layer 2 validation comparator. *See also* ECHO FCA, held-out validation. *Source: NRC.*

**p-code (place code).** A standardized identifier for an administrative unit, enabling reliable joins across datasets that name the same place differently. Used to join fieldmaps.io boundaries to HNO admin data. *See also* fieldmaps.io, admin1. *Source: OCHA term.*

**ReliefWeb.** OCHA's humanitarian information portal. Situation-report counts serve as the `media_attention` visibility proxy; full documents are a Day 4 Knowledge Assistant input. *See also* media_attention, Knowledge Assistant. *Source: OCHA term.*

## 4. Project-internal terms

**chronic_index.** Multi-year structural-neglect metric: `chronic_years_count × mean_chronic_gap`, where the count is the number of the last 5 years with `gap_ratio > 0.5`. Ranges ~0 to ~5. *See also* gap_ratio, neglect_class. *Source: project term (`docs/methodology.md`).*

**chronic_no_plan.** A `neglect_class` label for countries with no HRP for 3+ consecutive years but persistent documented need (INFORM Severity ≥ 3 or PIN ≥ 100,000) — need without a plan to address it. *See also* neglect_class, data_sparsity_flag. *Source: project term.*

**data_sparsity_flag.** A flag marking countries that lack machine-readable admin1 data and are therefore ranked at country level only. Treated as signal (low visibility), not silently dropped. *See also* admin1, chronic_no_plan. *Source: project term.*

**dollars_per_pin.** Per-capita investment metric: `FTS_funding_paid_usd / HNO_people_in_need`. Enters the composite as `1 − normalized(dollars_per_pin)` so low investment raises overlooked-ness. *See also* gap_ratio, PIN. *Source: project term.*

**gap_ratio.** The core mismatch signal: `(HRP_requirement − FTS_paid) / HRP_requirement`, ranging 0 (fully funded) to 1 (nothing received). Undefined where the requirement is zero or null. *See also* HRP, FTS, overlooked_score. *Source: project term.*

**geographic_isolation.** A bounded 0–1 need-multiplier combining distance to urban centers, inverse ACLED density, subnational data sparsity, and contested-border adjacency. Amplifies the severity signal in the composite. *See also* overlooked_score, ACLED. *Source: project term.*

**media_attention.** Visibility proxy: count of ReliefWeb situation reports about a country in the last 12 months, percentile-ranked within year. **Negatively** weighted — more attention means less overlooked. *See also* ReliefWeb, overlooked_score. *Source: project term.*

**neglect_class.** A temporal classification label assigned independently of the composite score: one of `chronic_neglect`, `acute_deterioration`, `improving`, `well_funded`, or `chronic_no_plan`. Powers the Triage ranking toggle. *See also* chronic_index, chronic_no_plan. *Source: project term.*

**overlooked_score.** The composite ranking score: a weighted sum of normalized `gap_ratio`, `severity_rate`, inverse `dollars_per_pin`, `chronic_index`, and `sector_imbalance`, minus `media_attention`, plus a `geographic_isolation × severity_rate` interaction. Deterministic and decomposable. *See also* percentile rank within year, bootstrap CI. *Source: project term.*

**sector_imbalance.** Within-country sectoral-neglect metric: the standard deviation of per-sector gap ratios across reported sectors. High values mean uneven coverage (e.g., funded food security, unfunded health). *See also* Cluster system, gap_ratio. *Source: project term.*

**severity_rate.** Need normalized by population: `HNO_people_in_need / COD_PS_population`. Captures crisis intensity relative to country scale. *See also* PIN, COD-PS. *Source: project term.*

**stability_flag (`stable_top_n`).** TRUE when a country appears in the top 10 across at least 90% of bootstrap samples — the strongest evidence its rank is robust to weight choices. *See also* bootstrap CI. *Source: project term.*

## 5. Architecture terms

**Bronze / Silver / Gold (medallion).** The three-layer Databricks data architecture: Bronze (raw, append-only, audit-grade), Silver (cleaned, expectation-tested, multi-country flows allocated), Gold (analytical tables that back the agent tools and UI). *See also* UC Function, DLT. *Source: Databricks term.*

**Genie space.** A Databricks text-to-SQL workspace asset that answers natural-language questions over Gold tables. Consumed here via REST API (not iframe-embedded) and rendered in a custom chat UI. *See also* supervisor agent, UC Function. *Source: Databricks term.*

**Knowledge Assistant.** A Databricks RAG product for question-answering over documents (ReliefWeb situation reports here). Deferred to a Day 4 stretch goal; not in the v1 critical path. *See also* ReliefWeb, supervisor agent. *Source: Databricks term.*

**MLflow Tracing.** Instrumentation that records every agent call — inputs, tool invocations, outputs — for observability and evaluation. Run on every supervisor-agent call. *See also* supervisor agent, RAI judge. *Source: Databricks / MLflow.*

**RAI judge (Responsible-AI judge).** One of seven custom evaluators run over a 30–50 query test set to grade agent outputs on responsible-AI criteria. `decision_support_framing` tests that the agent describes patterns rather than prescribing allocations. *See also* MLflow Tracing. *Source: project term (Databricks evaluation).*

**Supervisor agent.** The Mosaic AI agent (ChatAgent pattern) that routes a user query between Genie spaces (text-to-SQL) and UC Functions (scoring, ranking, spatial, validation tools). Explains rankings; never alters them. *See also* Genie space, UC Function. *Source: Databricks / Mosaic AI.*

**UC Function (Unity Catalog Function).** A SQL or Python function registered in Unity Catalog near its owning Gold table, exposed as an agent tool (e.g., `rank_crises`, `subnational_hotspots`). *See also* Bronze / Silver / Gold, supervisor agent. *Source: Databricks term.*

## 6. Methodology terms

**Bootstrap CI (confidence interval).** The 95% interval on a country's rank position, computed by recomputing the ranking under ~500 Dirichlet-sampled weight perturbations and taking the [2.5%, 97.5%] percentile range. Ranks are never reported without it. *See also* overlooked_score, stability_flag. *Source: project methodology.*

**Held-out validation.** Validation that withholds the most recent UFE rounds (2024–2025), recomputes the ranking using only prior-available data, and reports precision/recall at K=15. The headline defensibility number. *See also* UFE, ECHO FCA, NRC. *Source: project methodology.*

**Multi-country flow allocation cascade.** The Silver-layer procedure for splitting plan-level FTS flows to individual countries, in priority order: country-tagged → requirements-weighted → population-weighted fallback → `regional_unattributed`. Each split row carries its allocation method and lineage. *See also* FTS, COD-PS. *Source: project methodology.*

**Percentile rank within year.** Normalization that ranks each component metric against all in-scope countries in the same year, mapping it to 0–1 before weighting. Robust to the order-of-magnitude scale differences between countries. *See also* overlooked_score. *Source: project methodology (after DataNation).*
```
