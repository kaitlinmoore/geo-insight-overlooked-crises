# Submission

What gets delivered, by when, in what format. Pre-submission checklist included at the bottom.

## Deadline

- **Original deadline**: Thursday, 2026-05-21, 23:59 EST
- **Extended deadline**: TBD per Tanvir's communication. Update this line when confirmed.

All deliverables submitted via the hackathon submission portal (or per Tanvir's instructions if different).

## Required deliverables

Per the hackathon brief, the submission consists of three artifacts:

- **Slide deck** — 5-8 slides, PDF format
- **Demo video** — ~15 minutes, mp4 or YouTube link
- **Technical appendix** — public GitHub repository link, with MLflow traces and Databricks workspace artifacts referenced from the README

The deck is the front door (judges read this first). The demo is the experience (judges watch second). The repo is the proof (judges scan for technical depth if the deck and demo land).

## Slide deck — 8 slides

Target the upper end of the 5-8 range. The pitch line and differentiators warrant the space; trimming below 8 would cut substance, not fat.

| # | Title | Purpose | Owner |
|---|---|---|---|
| 1 | Title + tagline | *"A command center for identifying the world's most overlooked crises."* Project name, team, sponsor logos (UN OCHA, Databricks, Heinz). | Human design, Claude language. |
| 2 | The user, the question, the friction | Humanitarian coordinators face hundreds of competing crises and limited time. The weekly question — which are most overlooked? — takes hours of cross-referencing OCHA's own data systems. Our system answers that question on demand, grounded in OCHA data the coordinator already trusts. | Collaborative writing. |
| 3 | Five accessible differentiators | Overlooked-vs-underfunded; chronic-vs-acute; sector-aware; geography matters; explainable. Each in one bullet, operational language, no jargon. | Collaborative writing. |
| 4 | The system at a glance | One screenshot of Triage (with global map + ranked list + change indicators) + 3 capabilities listed. Demonstrates the product is real. | Screenshots from completed frontend; Claude drafts capability bullets. |
| 5 | How we know it's trustworthy | Methodology (composite + percentile rank + bootstrap CIs); validation (UFE precision/recall on held-out window, ECHO FCA + NRC overlap); Responsible-AI scorecard (7 judges); deterministic decomposition example. | Claude drafts; human reviews validation numbers when they land. |
| 6 | Workflow fit + persona walk-through | A humanitarian coordinator opens the app on a Monday morning. 30-second walkthrough of what they see, what they click, what they walk away with for the 9 AM briefing. | Collaborative writing; informed by personas.md. |
| 7 | Failure modes and limitations | What we don't claim. Where data is sparse. Where uncertainty is high. What's deferred to roadmap (Knowledge Assistant, alert subscriptions). The honesty slide. | Claude drafts; human reviews. |
| 8 | Technical appendix | GitHub link, MLflow run links, Databricks workspace artifacts (catalog, Genie spaces, agent serving endpoint). One-sentence architecture summary. | Auto-fillable once artifacts are live. |

Slide deck working file lives in Google Drive (PowerPoint). PDF export committed to repo at `/deliverables/geo_insight_deck.pdf` before submission.

## Demo video — ~15 minutes

Recorded screen capture with voiceover. Structure with timing targets:

| Time | Section | Content |
|---|---|---|
| 0:00 - 1:00 | Framing | The user, the question, the friction. *"A humanitarian coordinator opens our app on a Monday morning..."* Same energy as slide 2. |
| 1:00 - 9:00 | Live demo | Walk through the product: Triage (top-10 with change indicators) → Crisis Explorer (subnational map, sector breakdown, ACLED hotspots, explain-ranking) → Compare (2 crises side by side) → Ask (Genie via custom chat UI; show generated SQL). Demonstrate 2-3 specific user journeys end-to-end. |
| 9:00 - 12:00 | Methodology and validation | Walk through Methodology screen. Show composite formula. Show validation slide: UFE precision number, ECHO/NRC overlap. Show bootstrap CI visualization. *"Here's how we know the ranking is defensible."* |
| 12:00 - 14:00 | Responsible AI | RAI scorecard with 7 judges. Show a refused adversarial query ("Should we cut funding to Yemen?" → analytical reframe). Show MLflow traces. |
| 14:00 - 15:00 | Close | One-sentence summary, what's next, thank-you to mentors. Show GitHub URL. |

Buffer of ~30 seconds at the end is fine. Going *over* 15 minutes is not.

Demo recording on the user's machine via OBS, Loom, or similar. Multiple takes expected. Final mp4 uploaded to YouTube (unlisted) and linked from the deck, or attached directly per submission portal requirements.

## Technical appendix — GitHub repository

The repo is the long-form artifact judges can dig into. Make it scannable.

### Repository hygiene (must)

- Repo is **public** (or invite-only with judges' GitHub handles added before deadline)
- **No API keys, tokens, or credentials** in any commit. `.env` is gitignored; `.env.example` lists required variables without values.
- **No raw humanitarian data** in commits. Schemas and references only; raw data lives on the Databricks volume.
- All commits have meaningful messages (no "wip" or "stuff" at submission time).
- LICENSE present (MIT, already in place).

### README hero (top of README.md)

The README's first 50 lines do the same work as the deck's slide 1-2: tagline, the problem, the differentiators, screenshots. Judges who land on the repo from the deck need to recognize the project immediately.

- Pitch line at the top
- One-paragraph problem framing
- Three screenshots (Triage, Crisis Explorer, Methodology)
- Five differentiators as a short list
- Links into the rest of the repo

### Required repo contents

- `README.md` — public-facing, polished
- `STATE.md`, `DECISIONS.md`, `claude.md` — internal docs but useful to show process
- `docs/methodology.md` — referenced from the deck
- `docs/personas.md`, `docs/prior-art.md`, `docs/glossary.md`, `docs/open-questions.md` — supporting context
- `docs/schemas.md` — Bronze / Silver / Gold table schemas
- `docs/architecture.md` — system diagram, agent design
- `docs/data-catalog.md` — data inventory from Bronze profiling
- `notebooks/` — all Bronze, Silver, Gold, agent, validation, evaluation notebooks
- `src/` — acquisition scripts, portable Python, tests
- `frontend/` — React app source
- `deliverables/` — final PDF of deck, link to demo video, RAI scorecard export

### MLflow integration

- MLflow Tracing active on supervisor agent across the demo session
- Eval suite (30-50 queries, 7 judges) has at least one full run logged
- Specific MLflow experiment(s) referenced in the deck and README with shareable URLs (Databricks-hosted)
- A small `mlflow_runs.md` file at `/deliverables/mlflow_runs.md` lists relevant experiment URLs and what to look at

### Databricks workspace artifacts

The repo can't ship the Databricks workspace itself, but it should reference what lives there:

- Catalog: `geo_insight` (or final name)
- Genie spaces (3-4, by topic)
- Supervisor agent endpoint (Model Serving)
- Vector Search endpoint (provisioned even if KA didn't land)
- AI/BI Dashboard URL(s) if any were built

These are listed in `/deliverables/databricks_artifacts.md` with descriptions.

## Pre-submission checklist

Walk through this in order, ~2 hours before the deadline. Do not skip; missing checks at this stage cost evaluation points unrecoverable later.

### Deck

- [ ] PDF exported and committed to `/deliverables/`
- [ ] All slides have consistent fonts, colors, sponsor logos
- [ ] No placeholder text (no "Lorem ipsum", no "TKTK", no "fill in")
- [ ] Validation numbers on slide 5 are real (not "[X]%")
- [ ] All citations to source data on every numeric claim
- [ ] GitHub URL on slide 8 is correct and the repo is accessible

### Demo video

- [ ] Final cut uploaded (YouTube unlisted, or per submission portal)
- [ ] URL works in an incognito window (verifies sharing settings)
- [ ] Voiceover is clear; no background noise; no recording errors
- [ ] Screen recordings are crisp; cursor visible; text legible
- [ ] No PII, no real personal data, no logged-in personal accounts in any captured screen
- [ ] Duration is ≤ 15:00 (preferably 14:30-15:00)

### Repository

- [ ] Repo is public (or judges' GitHub handles added)
- [ ] README hero matches slide 1-2 framing
- [ ] No `.env` file in commits; `.env.example` is present
- [ ] No API keys in any committed file (search the repo: `grep -r "dapi\|sk-\|Bearer " .` should find nothing real)
- [ ] All notebooks have descriptive names and execute without secret-key errors
- [ ] LICENSE present (MIT)
- [ ] `/deliverables/` folder contains deck PDF, demo video link, MLflow run links, Databricks artifacts list

### Workspace artifacts

- [ ] Genie spaces are working (test by asking a real question)
- [ ] Supervisor agent endpoint responds (test via Model Serving UI)
- [ ] Gold tables are populated (test by querying `gold_forgotten_crisis_index`)
- [ ] At least one MLflow run is logged and shareable
- [ ] Vector Search endpoint state is "Online"

### Submission portal

- [ ] All three artifacts uploaded or linked per the portal's requirements
- [ ] Submission confirmed (check for confirmation email)

## Stretch additions — promote to submission if they land

These are Day 4 stretch goals. If they land by Day 4 afternoon, they get added to the demo and the appendix; if not, they're roadmap.

- **Knowledge Assistant** integration in the Ask screen — narrative panel in Crisis Explorer fed by ReliefWeb situation reports
- **IPC food security** as a second independent severity signal
- **Cross-border patterns view** as a sixth UI screen (currently optional)
- **Maximum-tier bonus task viz** — simultaneous comparison of structural vs. acute neglect quadrant chart
- **AI/BI Dashboard** with public URL, linked from the Methodology screen as an additional exploration surface

## Roadmap — explicitly NOT in v1, claimed in deck

These are documented in the deck and methodology as planned extensions:

- **Alert subscriptions** (email / Slack notifications when ranks change). Architecture supports it; delivery layer not built.
- **Post-deadline UFE round-grain validation** via an announcement-date lookup table.
- **CIRV ingestion as baseline comparator** in the validation slide.
- **Expanded vector-indexed corpus** including ACAPS humanitarian briefs and HRP narrative sections.
- **Public dashboards** beyond Databricks Apps (Vercel or similar) for portfolio purposes.

## What gets dropped if time runs short

The order in which to cut, if Day 4 schedule pressure forces it:

1. **Simultaneous-comparison viz** for the bonus task (already a stretch)
2. **Cross-border / regional view** as a sixth screen (the data still exists; the dedicated screen is what gets cut)
3. **CBPF Allocation View** as a built screen — methodology mentions PFM as a persona either way
4. **Knowledge Assistant** if Day 4 afternoon has no slack (stays as roadmap)
5. **IPC integration** if ACLED alone is what shipped (Day 4 stretch by default anyway)
6. **Compare screen** — the most "if we have to" cut among the original five screens; HAO can do most comparison work via Ask
7. **Methodology screen polish** — falls back to "link to docs/methodology.md from README" if visualization work doesn't complete

Cuts in this order preserve the headline (Triage + Crisis Explorer + Ask + Methodology + validation evidence + RAI scorecard) which is what the deck centers on.
