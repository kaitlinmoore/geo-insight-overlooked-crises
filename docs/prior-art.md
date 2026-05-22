# Prior Art

The question "which crises are most overlooked?" is not new. Several mature efforts — institutional, academic, and NGO — already rank or flag neglected crises, and this project borrows from all of them. This document describes each precedent honestly: what it does, where it lands well, and where it leaves a gap this project addresses. The point is intellectual honesty, not competitive positioning. A reader should come away trusting that we understand the landscape we are building in.

A note on framing: most of these efforts answer a question adjacent to ours but not identical to it. Some rank *underfunded* crises (CERF UFE, DataNation); some rank *forgotten* or *neglected* crises with attention as an explicit dimension (NRC, ECHO); some measure *severity or risk* rather than overlooked-ness (INFORM, CIRV). Our composite treats "overlooked" as multi-dimensional — need, coverage, attention, persistence, and geographic context — which is closest to NRC's framing but extends it on several axes.

## 1. NRC World's Most Neglected Displacement Crises

The closest precedent for our composite framing. The Norwegian Refugee Council has published an annual top-10 list of the world's most neglected displacement crises since 2019. The ranking combines three dimensions: **lack of funding** (the humanitarian funding gap relative to assessed need), **lack of media attention** (volume of media coverage), and **lack of political will** (international diplomatic and political engagement). NRC publishes a methodology document each year describing the indicators and data sources behind the list.

NRC lands well on the conceptual move that anchors this whole project: neglect is more than a funding gap, and media attention belongs in the model as a first-class signal rather than a footnote. Their published methodology makes the list defensible and reproducible in spirit, which is rare in this space.

**What we use it for.** A Layer 2 validation comparator (top-N overlap analysis against our ranking) and the conceptual touchstone for treating attention as a negative-weighted component of overlooked-ness.

**What we differ on.** NRC's list is annual, country-level, and displacement-focused, with attention measured at national granularity. We extend on four axes: (1) multi-year temporal tracking with an explicit chronic-vs-acute classification rather than a single annual snapshot; (2) sector decomposition, so a country's ranking is traceable to cluster-level gaps; (3) geographic depth — subnational ranking and spatial hotspot detection where data supports it; and (4) held-out quantitative validation against UFE selections rather than expert curation alone. We are also not displacement-restricted: our severity gate admits any crisis meeting the documented-need thresholds.

**Citation.** Norwegian Refugee Council, "The World's Most Neglected Displacement Crises," published annually since 2019. https://www.nrc.no/shorthand/neglected/

## 2. DG ECHO Forgotten Crises Assessment (FCA)

The European Commission's Directorate-General for Humanitarian Aid and Civil Protection (DG ECHO) produces an annual Forgotten Crises Assessment as part of its Integrated Analysis Framework for humanitarian funding allocation. The FCA identifies crises that receive low media coverage and low per-capita aid relative to need. The resulting list is published, but the full methodology — the precise indicators, weights, and the qualitative ECHO field-assessment input — is not detailed publicly in a reproducible form.

The FCA lands well as an institutional, donor-side determination with real budget consequences: ECHO uses it to direct funding, so it carries operational weight that a purely academic index does not. Its longevity makes it a stable year-over-year benchmark.

**What we use it for.** A Layer 2 ground-truth comparator. We compare our annual top-15 against the published ECHO FCA list and report set overlap, discussing both blind spots (in ECHO but not ours) and potential novel insights (in ours but not ECHO).

**What we differ on.** Because the FCA methodology is not fully public, we use the *published list* as a comparator rather than attempting to reproduce or incorporate its scoring. Critically, we treat ECHO FCA as a validation target, **not** as a training signal or model feature — keeping it independent of our ranking preserves the comparison's value.

**Citation.** European Commission DG ECHO, "Forgotten Crisis Assessment," annual, part of the Integrated Analysis Framework. https://civil-protection-humanitarian-aid.ec.europa.eu/

## 3. CIRV — Compound Index of Risk and Vulnerability

CIRV (Rost, Ham, Kaffes, 2026) is OCHA's own composite index of risk and vulnerability, used to inform CERF Underfunded Emergencies (UFE) window selections. It was published in February 2026 in the *Journal of International Humanitarian Action*. CIRV combines risk, vulnerability, and severity signals into a single index that feeds OCHA's institutional process for identifying underfunded emergencies.

CIRV lands well as a rigorous, peer-reviewed, institutionally-adopted index — it is arguably the most authoritative single composite in this space, precisely because it is OCHA's own and is wired into a real funding decision.

**What we use it for.** Nothing, deliberately, in the ranking model. CIRV is **explicitly excluded** from our feature set.

**What we differ on.** This is a methodological-hygiene decision rather than a disagreement. We validate our ranking against UFE selections (Layer 1, labeled ground truth). Because CIRV informs those same UFE selections, using CIRV as a feature in our model and then validating against UFE would inflate measured agreement through circularity — we would partly be testing whether we reproduced CIRV, not whether we independently identified overlooked crises. Excluding CIRV keeps the UFE validation clean. See `DECISIONS.md` entry 2026-05-21 ("CIRV deferred for v1") and the CIRV circularity caveat in `docs/methodology.md`.

**Citation.** Rost, L., Ham, M., Kaffes, I. (2026). "A Compound Index of Risk and Vulnerability for humanitarian prioritization." *Journal of International Humanitarian Action*, February 2026.

## 4. DataNation Forgotten Crisis Index

The DataNation Forgotten Crisis Index won the 2026 Carnegie Mellon University datathon. Its core methodological move was to compute a percentile rank *within year* on a single funding-gap signal, producing an annual ranking robust to the order-of-magnitude scale differences between countries. The within-year percentile-rank normalization is a genuinely good idea, and we adopt it directly.

DataNation lands well on normalization robustness and on demonstrating that a defensible ranking can be built quickly from public data. It is the most direct methodological predecessor in the datathon lineage this project shares.

**What we use it for.** The within-year percentile-rank normalization (see `docs/methodology.md`, "Normalization: within-year percentile rank") and the bootstrap/stability-flag robustness check are both inherited from or inspired by DataNation's approach.

**What we differ on.** DataNation ranked on a single funding-gap signal at country-year granularity with internal robustness only. We extend to: (1) a multi-dimensional composite (funding gap, severity rate, per-capita investment, chronic index, sector imbalance, media attention, geographic isolation); (2) multi-year temporal classification distinguishing chronic neglect from acute deterioration; (3) geographic depth (subnational ranking, ACLED hotspots, cross-border patterns); and (4) external validation against UFE, ECHO, and NRC rather than internal robustness alone. DataNation also did not address multi-country flow attribution, which our Silver-layer allocation cascade handles explicitly.

**Citation.** DataNation, "Forgotten Crisis Index," winning entry, Carnegie Mellon University datathon, 2026.

## 5. ACAPS INFORM Severity

INFORM Severity (formerly GCIS) is a multi-indicator composite severity index maintained by ACAPS, scoring crises on a 0–5 scale across roughly 35 indicators, updated monthly. It is a mature, widely-trusted measure of how severe a crisis is, independent of how it is funded.

INFORM Severity lands well as a rigorous, regularly-updated, multi-indicator severity measure with broad humanitarian-sector adoption. It is one of the standard reference points for crisis severity.

**What we use it for.** A primary **input**, not a comparator. INFORM Severity provides the severity dimension in our composite and the severity gate (Severity 4–5 admits a crisis to the ranking). Its multi-year trend feeds our `chronic_index`, and persistent INFORM Severity ≥ 3 across years drives the `chronic_no_plan` classification for countries without an active HRP.

**What we differ on.** We do not differ — INFORM measures severity, which is one component of overlooked-ness, not overlooked-ness itself. A crisis can be severe and well-attended (not overlooked) or moderately severe and invisible (overlooked). We consume INFORM as a building block and combine it with coverage, attention, and persistence to answer a different question than INFORM asks.

**Citation.** ACAPS, "INFORM Severity Index," methodology documented at https://www.acaps.org/en/thematics/all-topics/inform-severity-index

## 6. CERF Underfunded Emergencies (UFE) selections

The Central Emergency Response Fund's Underfunded Emergencies window is OCHA's twice-yearly institutional answer to "which crises are most underfunded." Each round, OCHA selects a set of countries to receive UFE allocations based on its internal prioritization process (which CIRV now informs — see §3). These selections are published.

UFE lands well as the single most authoritative signal available for our specific question: it is OCHA's own determination, made with internal data and institutional judgment, with real money attached. No external index can claim that authority.

**What we use it for.** Layer 1 validation — **labeled ground truth**. We build a country × year × round dataset with a binary `ufe_selected` label, hold out recent rounds (2024–2025), compute our ranking using only data available before each round, and report precision and recall at K=15. UFE is the strongest validation target we have precisely because it is OCHA's own answer rather than a third-party proxy.

**What we differ on.** UFE answers "underfunded," we answer "overlooked" — a deliberately broader question that adds attention and geographic context. We expect substantial but imperfect overlap with UFE; the interesting cases are the divergences (a crisis we rank highly that UFE did not select may reflect our attention or isolation signals, and is worth examining rather than assuming it is an error). UFE is a benchmark to align with, not a definition to reproduce.

**Citation.** UN OCHA, Central Emergency Response Fund — Underfunded Emergencies window selections (published per round). https://cerf.un.org/

## 7. HDX Signals

HDX Signals is an automated alerting product from OCHA's Centre for Humanitarian Data. It monitors roughly five topics (such as conflict events, food insecurity, displacement, and market prices) across approximately 200 locations and emits alerts when monitored indicators cross thresholds, surfacing emerging changes for humanitarian responders.

HDX Signals lands well as a live, operational, OCHA-native alerting layer — it is the closest existing product to the change-detection and alert-subscription extensions on our roadmap, and it operates at scale across many locations and topics.

**What we use it for.** Currently a citation and conceptual integration point in our methodology, not a live data dependency. Our temporal substrate (time-versioned Gold tables, the `get_ranking_delta` UC Function, and the change indicators on the Triage screen) is designed so that consuming or complementing HDX Signals is a contained future extension rather than a rewrite. See `DECISIONS.md` entry 2026-05-21 ("Alert subscriptions deferred to roadmap").

**What we differ on.** HDX Signals alerts on *changes in monitored indicators*; we rank crises by a composite *overlooked* score and classify them as chronic or acute. The two are complementary: Signals is well-suited to acute-onset detection, while our chronic-neglect classification surfaces the slow-burning crises that threshold-based alerting tends to miss. Live integration is roadmap, not v1.

**Citation.** OCHA Centre for Humanitarian Data, "HDX Signals." https://data.humdata.org/

## Summary: where we sit in the landscape

| Precedent | What it ranks | Our relationship |
|---|---|---|
| NRC Most Neglected | Neglected displacement crises (funding, media, political will) | Closest precedent; Layer 2 comparator; we extend on time, sector, geography, validation |
| ECHO FCA | Forgotten crises (donor-side, allocation-linked) | Layer 2 comparator; ground truth, not a feature |
| CIRV | Risk & vulnerability (OCHA, informs UFE) | Deliberately excluded to keep UFE validation clean |
| DataNation FCI | Funding gap, percentile-ranked within year | Methodological ancestor; we adopt normalization, extend everything else |
| INFORM Severity | Crisis severity (multi-indicator) | Input, not comparator |
| CERF UFE | Underfunded emergencies (OCHA institutional) | Layer 1 labeled ground truth |
| HDX Signals | Indicator-change alerts (~200 locations) | Roadmap integration point; complementary, not overlapping |

Our contribution is not a new signal nobody has thought of; it is the combination — a multi-dimensional, multi-year, sector-aware, geographically-deep composite, every score of which is explainable and externally validated. Each precedent above does part of this well. None does all of it together, and that combination is the project's claim.
