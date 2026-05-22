# Personas

Who this system is built for, in priority order, with the user stories and design implications that fall out of each.

> **How to use this document.** Personas are tiebreakers, not constraints. When a design decision has multiple defensible answers, the primary persona's needs win. Secondary personas are served by the same surfaces, sometimes with progressive disclosure. The tertiary persona is "should not be hostile to," not "optimized for." When in doubt about a UI or content decision, ask: would the primary persona understand this at a glance? Would the secondary personas be able to drill into it for more depth?

## Persona cascade

- **Primary**: Humanitarian Coordinator (HC)
- **Secondary**: Humanitarian Affairs Officer (HAO)
- **Secondary**: Pooled Funds Manager (PFM)
- **Tertiary** (should not be hostile to, but not the design target): Donor Advisor

Two secondary personas rather than one because the HAO and PFM use the system for genuinely different purposes — HAO for analytical depth, PFM for allocation context — and the IA serves them through different screens rather than blending their needs.

## Humanitarian Coordinator — Primary

**One-line summary.** A senior decision-maker who needs to know, this morning, which crises in their portfolio are most overlooked, with enough evidence to defend the answer in a briefing.

### Role and context

The HC sits at country, regional, or HQ level within UN OCHA. They are responsible for setting priorities, allocating attention and resources across multiple crises, and advocating on behalf of overlooked populations to donors, member states, and the wider humanitarian community. They are accountable for decisions but rarely have time for deep analytical work themselves.

The HC's organizational reality: they are pulled in many directions, sit on many briefings, and need synthesis they can trust quickly. They are not data analysts. They are decision-makers who work *with* data analysts.

### Session characteristics

- **Length**: 5–15 minutes, sometimes 2–3 minutes between meetings
- **Frequency**: Several times per week, often daily during a budget cycle or crisis surge
- **Context**: Phone or laptop, sometimes in the middle of other work. Not a dedicated analytical environment.

### Primary screens

- **Triage** — the headline ranked list and global map. Designed for at-a-glance comprehension.
- **Crisis Explorer** — drilldown for one or two crises that warrant a closer look in the same session.

### Key user stories

- *"As an HC, I want to see the top 10 most overlooked crises this week so that I can decide where to focus advocacy effort, with one click into each for the reasoning."*
- *"As an HC, I want to know how the rankings have changed since last quarter so that I can spot deteriorating situations before they hit the news."*
- *"As an HC, I want a one-paragraph summary I can paste into a briefing memo, with citations to the underlying data, so that I can defend the framing in a stakeholder meeting."*
- *"As an HC, I want the system to be honest about what it doesn't know so that I don't get caught out using a number that isn't defensible."*

### Design implications

- The Triage hero must communicate the top-line ranking and at least one piece of supporting evidence (region, severity, current gap) without requiring a click.
- Change indicators (`↑5 positions`, `NEW to top 10`, `↓3`) are first-class — the HC's question is often "what's changed" more than "what's the absolute state."
- Crisis Explorer's default view shows the 3–5 most important facts about a country before any interaction, in language an HC can paste into a briefing.
- Uncertainty is visible but not alarming. CIs are shown as small ranges next to the rank ("#2, range #1–3"), not as overwhelming error bars.
- "Briefing-ready" outputs from the Ask screen produce paragraphs, not raw data tables, with citations.

### What we don't optimize for

- Methodology depth in the default view. The HC trusts the methodology because it's available in `docs/methodology.md` and the Methodology screen, not because they read it.
- Comparative analysis across many countries at once. The HC sees one screen at a time. The Compare screen exists for the HAO.
- Data export to spreadsheets. If the HC wants raw data, they ask the HAO.

## Humanitarian Affairs Officer (HAO) — Secondary

**One-line summary.** The analyst who supports the HC and other senior staff. Does the deep-dive work that produces the briefings the HC presents.

### Role and context

HAOs are mid-level officers within OCHA who do the analytical work that informs decisions. They prepare briefing materials, respond to ad-hoc questions from leadership, build advocacy products, and sometimes write the HRP / HNO narratives themselves. They work with humanitarian data routinely and can defend specific numbers in front of skeptical audiences.

The HAO knows that aggregate funding figures hide sector-specific gaps. They know that PIN figures depend on methodology choices that vary by country. They want a tool that respects this expertise rather than oversimplifying.

### Session characteristics

- **Length**: 30–90 minutes, sometimes multiple hours when preparing a major brief or HRP / HNO chapter
- **Frequency**: Multiple times per week
- **Context**: Dedicated work session, full desktop, willing to read methodology details

### Primary screens

- **Crisis Explorer** — deep drilldown on one country, including subnational view, sector breakdown, funding history, ACLED hotspots
- **Compare** — side-by-side analysis across 2–4 countries on specific dimensions
- **Ask** — natural language queries for ad-hoc questions ("which countries have had >50% health funding gaps in 3 of the last 5 years?")
- **Methodology** — the embedded AI/BI Dashboard for raw exploration of Gold tables

### Key user stories

- *"As an HAO, I want to drill into the subnational pattern of an overlooked country so that I can identify which admin1 areas are driving the national-level result."*
- *"As an HAO, I want to compare two countries on funding-to-need ratio over time so that I can show in a brief that one situation is structurally different from another."*
- *"As an HAO, I want to ask 'what changed in Sudan's funding picture in 2024?' and get an evidence-grounded answer with source citations so that I can use the response in a memo."*
- *"As an HAO, I want to see the deterministic decomposition of an overlooked-ness score — which components drove the ranking — so that I can defend a specific country's position to a senior who pushes back."*
- *"As an HAO, I want to know when ACLED is showing emerging conflict events that the HNO hasn't yet captured so that I can flag situations earlier."*

### Design implications

- Crisis Explorer must support full subnational drill (admin1 choropleth, sector breakdown, multi-year trend, ACLED overlay) without overwhelming the default view. Progressive disclosure.
- The deterministic decomposition of overlooked_score is a first-class element of Crisis Explorer — *"Sudan scores 0.84: gap_ratio contributes 0.31, severity_rate 0.24, chronic_index 0.19, sector_imbalance 0.10."*
- Compare screen accepts 2–4 country selections and aligns metrics on a shared scale.
- Ask screen surfaces the SQL Genie generates so the HAO can verify what was queried and reproduce the result. Embedded native Genie UI handles this.
- Methodology screen exposes raw Gold tables via the embedded AI/BI Dashboard so the HAO can run their own analyses.

### What we don't optimize for

- Two-minute summarized views. The HAO wants depth. Brevity is the HC's job.
- Strong opinions or recommendations. The HAO wants the data, not the system's view.
- Mobile-first layouts. The HAO is at a desk.

## Pooled Funds Manager (PFM) — Secondary

**One-line summary.** Responsible for allocation decisions across a Country-Based Pooled Fund or similar. Needs the ranking in their fund's specific operational context.

### Role and context

PFMs manage the allocation of pooled humanitarian funds (CBPFs at country level, CERF at global level) on behalf of OCHA. Their decisions are scrutinized: allocations must be defensible against multiple stakeholders (donors, partners, affected populations, member states). They operate under explicit allocation cycles with documented criteria.

The PFM cares deeply about transparency in *how* a ranking is computed because they will be asked to justify allocations that flow from it. They also care about the difference between fund-specific data and global data — a CBPF in Sudan operates at a country level even though Sudan's overall funding picture spans many sources.

### Session characteristics

- **Length**: 15–30 minutes per allocation review, sometimes longer during a major allocation round
- **Frequency**: Weekly during active cycles, less often otherwise
- **Context**: Often in the middle of fund-management work; the system is a reference, not the workflow

### Primary screens

- **CBPF Allocation View** (optional screen) — fund-specific view showing allocation history, fund balance, and gap analysis at fund scope
- **Crisis Explorer** — same as HAO, for any country the fund operates in
- **Methodology** — for transparency when justifying allocation decisions

### Key user stories

- *"As a PFM, I want to see how my fund's recent allocations compare to overlooked-ness signals so that I can identify whether my allocations are aligned with documented need."*
- *"As a PFM, I want to filter the ranking by countries where my fund operates so that I can use this tool in my actual allocation context."*
- *"As a PFM, I want documentation of the methodology that produced any ranking I cite so that I can defend an allocation to donors or partners."*
- *"As a PFM, I want the tool to never recommend specific allocations so that I'm not in the position of either following or refusing a machine's instruction."*

### Design implications

- The CBPF Allocation View, if built, exposes per-fund context: which CBPF is selected, what countries it operates in, what's been allocated recently, and how those allocations compare to overlooked-ness signals.
- Allocation history is visible alongside the ranking, not blended into it.
- Methodology slide and methodology screen are easily linkable from any view (a PFM may need to share the methodology link with stakeholders).
- The agent's refusal of prescriptive framing is *especially* important for this persona. The PFM cannot use a tool that recommends specific allocations.

### What we don't optimize for

- Speed of consumption. The PFM is working in a deliberate, accountable mode.
- Cross-country breadth in the headline. The PFM cares about their fund's scope first.

## Donor Advisor — Tertiary

**One-line summary.** External to OCHA. Advises donor government agencies on where to allocate humanitarian funding. Different incentives, different information context.

### Role and context

Donor advisors sit inside government foreign-affairs or development agencies (USAID, FCDO, the European Commission, etc.) and advise on humanitarian budgets. They are not OCHA staff. Their decisions are shaped by political priorities, bilateral relationships, and donor-government strategic considerations as much as by humanitarian need.

A donor advisor uses this tool the way an informed outsider would — they want to know what OCHA's analytical lens says about overlooked crises, partly to compare against their own agency's view and partly to identify potential investment areas.

### Session characteristics

- **Length**: Variable. Sometimes a 5-minute look during a budget review; sometimes longer when preparing a position paper
- **Frequency**: Periodic, not routine
- **Context**: Their workflow is their agency's tools and processes. This is a reference resource, not a daily driver.

### Primary screens

- Triage, Crisis Explorer, Ask — same surfaces as HC and HAO, used differently
- **Methodology** — important for trust calibration; donor advisors need to know what they're looking at

### Key user stories

- *"As a Donor Advisor, I want to compare OCHA's overlooked-crises ranking to other respected lists (ECHO FCA, NRC Most Neglected) so that I can calibrate where these analyses agree and disagree."*
- *"As a Donor Advisor, I want to see the methodology in detail so that I can credibly cite or critique results in my agency's internal deliberations."*
- *"As a Donor Advisor, I want to query the system about specific countries my agency funds so that I can see what an independent analytical lens says about their funding picture."*

### Design implications

- The Methodology screen and validation evidence (UFE precision, ECHO/NRC overlap) are particularly important for this persona.
- Tone in agent outputs stays analytical and non-advocacy: the donor advisor will translate findings into their own agency's language and priorities.
- The system never characterizes donor decisions or specific donor agencies in evaluative terms. (Donor concentration metrics are presented as factual: "70% of Yemen's 2024 funding came from 3 donors." Not: "Yemen is overly dependent on a small number of donors.")

### What we don't optimize for

- This persona is explicitly tertiary. UI choices that would harm the HC, HAO, or PFM are not made for the Donor Advisor's benefit.
- Advocacy framing. The HC may use the tool's outputs for advocacy; the Donor Advisor uses outputs as evidence in agency deliberations.

## Cross-cutting design implications

A few patterns surface across personas that should be honored consistently:

**Progressive disclosure.** The HC sees less by default; the HAO and PFM access more depth via the same surfaces. The default view is the HC's; the secondary depth is accessed via clicks, toggles, and side panels — not separate screens for each persona.

**Citations to source data.** Every numeric claim in every persona's view traces to a Gold table row and ultimately to source data. The HC may not click the citation; the HAO and PFM will.

**Uncertainty visible.** Bootstrap CIs, data freshness flags, and coverage flags are not hidden behind "advanced" toggles. They are part of the default view at appropriate levels of prominence.

**Analytical voice, not advocacy voice.** The system describes patterns, not prescriptions. This serves the PFM and Donor Advisor most directly but is also what the HC needs for briefings (the HC adds advocacy framing themselves; the system supplies the evidence).

**No persona-specific dashboards.** Resist the temptation to build "HC view," "HAO view," "PFM view." Instead, build well-designed screens that progressively disclose depth. The CBPF Allocation View is the one exception — it has fund-specific context that doesn't belong in the cross-cutting screens.

## Anti-personas

It's worth being explicit about who this system is **not** built for:

- **Affected populations.** The system shows humanitarian need at country and admin1 level. It does not interact with people affected by crises. It must not be used in contexts that put those populations at risk (e.g., named individuals, location-level data that could enable targeting).
- **Press and media.** The system is for decision-makers within and adjacent to OCHA. Outputs may be used in briefings that journalists attend; the system itself is not a press tool.
- **General public.** A future product might serve a public audience. This is not that product. The framing, vocabulary, and required context assume humanitarian-domain expertise.
- **Quantitative researchers.** Academics studying humanitarian financing patterns are welcome to use the tool, but the system's outputs are tuned for decision support, not for hypothesis testing or causal inference.

If a design decision benefits an anti-persona at the cost of the primary or secondary personas, it's the wrong decision.
