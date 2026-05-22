# Synthesis → Execution Handoff

> **Purpose of this doc.** Capture what the bootstrap docs don't — the conversational history behind decisions, working-style preferences, the conversation-orchestration model, and the open threads being watched. Read once when starting the execution-phase central chat, then refer back as needed.

## Where this project came from

The Geo-Insight project went through a multi-day synthesis phase across several Claude conversations before reaching execution. The most recent and authoritative synthesis happened on 2026-05-21 in a long conversation that:

- Reviewed three prior synthesis documents (`strategy_synthesis.md`, `geo_insight_project_handoff.md`, `Synthesis_of_Day_1_Presentation_Notes_and_Ideas`)
- Resolved ten architectural and methodological decisions (logged in `DECISIONS.md`)
- Produced the current generation of bootstrap docs (`STATE.md`, `DECISIONS.md`, `claude.md`, `docs/methodology.md`, `docs/personas.md`, `SUBMISSION.md`)
- Discovered and documented the iframe-embedding constraint and pivoted the frontend architecture to API-based consumption

That synthesis conversation also produced findings notes in `docs/notes/` from parallel Claude Code acquisition sessions (CERF UFE, fieldmaps boundaries).

The synthesis chat is the authoritative source for the *reasoning* behind decisions. The bootstrap docs are the authoritative source for the *current state* of those decisions. When they conflict (which can happen at the edges), the bootstrap docs win because they're maintained.

## Bootstrap docs are canonical

The docs to read in priority order:

- `STATE.md` — current state, immediate next actions, open threads
- `DECISIONS.md` — append-only log of all architectural and methodological decisions
- `docs/methodology.md` — composite formula, validation strategy, geographic methodology
- `claude.md` — working conventions for Claude Code sessions
- `docs/personas.md` — HC primary, HAO + PFM secondary, Donor Advisor tertiary
- `SUBMISSION.md` — deliverable checklist, deck structure, demo video timing, pre-submission checks

Plus the findings notes in `docs/notes/` for what was learned during data acquisition.

If a question can be answered from these docs, it should be — they were written with full context and care. If a question genuinely isn't answered, that's a signal to ask the user rather than improvise.

## Working style preferences (Will)

A few things Will values that shape how Claude should engage:

**Honesty over flattery.** Will catches drift and will surface it directly. Don't soften recommendations to manage feelings; don't pad agreement. If you disagree with a choice, say so with reasoning. The synthesis chat had several moments where pushback from Claude was helpful.

**Direct questions deserve direct answers.** Will asks pointed questions ("why population-weighted vs equal split?", "where did the word overlooked come from?"). The right response is the answer with reasoning, not a discursive lead-up.

**Strategic over execution-focused responses for decisions; execution-focused responses for tasks.** When deciding architectural questions, Will wants the trade space, the recommendation, and the rationale. When executing, he wants the concrete step or the artifact.

**Pressure-test recommendations.** Will will challenge claims — "are these actually justifiable per Mary's framing?", "I'm not confident this is methodologically sound." When pushed, double-check the reasoning rather than capitulating. He'll back off if the reasoning holds.

**MVP scope plus clear stretch goals.** Will is realistic about timeframe. Don't propose ambitious scope without flagging trade-offs. Don't propose minimal scope without flagging what's being left on the table. He'll choose; just give honest options.

**Substantive responses, not bullet padding.** Long responses are welcome when the content warrants. Short responses are welcome when the question is small. What's not welcome: prose padded with bullets, headers added for visual density, generic acknowledgment before the actual answer. Be direct; be substantive.

**Solo developer, no team coordination.** Will makes the decisions. No need to coordinate with imaginary teammates or external approvers. Mentors (Dr. Kurland, Elise, Mary Keller) are touch-points for specific questions, not decision blockers.

## The conversation-orchestration model

Multiple Claude conversations work in parallel during execution:

- **The execution chat (you, if you're reading this as that chat)** is the central conversation. Houses high-level coordination, methodology questions, deck content collaboration, strategic decisions during the build, ad-hoc questions that don't fit a spin-off chat.
- **Spin-off chats** handle bounded topics:
  - **Databricks setup / troubleshooting** — workspace configuration, permissions, CLI issues, vector endpoint, Genie spaces, MLflow setup
  - **Frontend development** — React app build, Cursor + Claude integration, component design, embedding pattern
  - **Deck writing** — slide content production, when we have validation numbers and screenshots
  - **Demo recording** — script, rehearsal, narration
  - **Specific Claude Code sessions** — each acquisition prompt, each Bronze loader, each Gold notebook is potentially its own session

The execution chat doesn't need to know everything happening in the spin-off chats. The spin-off chats report results back via the user, who integrates findings into the canonical docs. When ambiguity arises about which chat owns a decision, the execution chat is the tiebreaker.

When the execution chat itself starts running long, it spawns successor chats and hands off via an update to `STATE.md` and (if substantial) a new handoff doc.

## Open threads being watched

These are active workstreams that may need attention during the build. Each has a primary owner.

- **Databricks schema and volume creation permissions** — requested, pending grant. Blocking the Bronze layer until resolved. *Owner: user via OCHA/CMU support.*
- **Acquisition completion** — prompts 1 (CERF UFE) and 3 (fieldmaps) done; 2 (ACLED), 4 (ECHO FCA), 5 (NRC), 6 (ReliefWeb), 7 (HDX Signals, optional) pending. *Owner: user supervising Claude Code.*
- **Git baseline** — bootstrap docs being committed in the same window this handoff is produced. After commit, parallel sessions are safer.
- **Composite weight calibration** — placeholder weights in `methodology.md` need empirical calibration once Gold is computed.
- **`tableName` field in CERF data** — meaning unknown, ask Mary via Slack.
- **Embed verification** — supplanted by API-based pattern, but the API itself needs a quick smoke test (Genie REST API end-to-end) before Ask screen is wired.
- **Demo crisis selection** — needs decision by Day 4 morning. Likely one well-known crisis + one our model surfaces + one structural-neglect example.

## Anti-patterns to avoid

A few specific things Claude shouldn't do, learned from this synthesis:

- **Don't auto-update `STATE.md` or `DECISIONS.md` from a Claude Code session that's doing a one-off task** (e.g., a data acquisition script). See the scope carve-out in `claude.md` working protocol.
- **Don't invent composite weights, thresholds, or methodology values.** They live in `docs/methodology.md`. If a value isn't there, ask.
- **Don't propose iframe embedding of Databricks workspace assets** — confirmed unavailable, replaced by API consumption (see `DECISIONS.md` 2026-05-21 entry).
- **Don't present rankings with false precision.** Bootstrap CIs accompany every rank in any output.
- **Don't recommend specific allocations.** The system is decision support; the agent describes patterns, never prescribes.
- **Don't add formal "Decision / Alternatives / Rationale / Revisit if" entries to `DECISIONS.md` for findings or research outputs** — only for actual architectural or methodological decisions. Findings go in `docs/notes/` or chat reports.

## Quick reference

- **Pitch line**: *"A command center for identifying the world's most overlooked crises."*
- **Five differentiators**: overlooked-vs-underfunded; chronic-vs-acute; sector-aware; geography matters; explainable
- **Primary persona**: Humanitarian Coordinator
- **Architecture**: Mosaic AI supervisor → Genie spaces + UC Functions (KA stretch); React + Tailwind + shadcn/ui frontend on Databricks Apps; Genie via REST API (no iframe)
- **Validation**: UFE + ECHO/NRC + bootstrap CIs
- **Submission**: 8-slide deck (PDF), 15-min demo video, GitHub repo with appendix
- **Submission deadline**: extended per Tanvir; update `STATE.md` when confirmed
