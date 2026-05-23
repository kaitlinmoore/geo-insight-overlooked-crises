# driver_disclosure

## Purpose

Verify that ranking responses surface the top contributing components — the explainability backbone of the methodology. When a user asks "why does X rank where it does", the response must name the drivers, not just report the rank.

## Rubric

- **1.0** — Response names the top 3 contributors by absolute contribution. Each contributor is named in plain language (not just `weight_chronic_index = 0.42` but "chronic neglect, which contributes 0.42 to the score"). Optionally includes the sign (some components are negative-weighted; media_attention is the obvious case).
- **0.5** — Mentions some drivers but not the top 3, or lists components without explaining the contribution magnitudes.
- **0.0** — Reports the rank without explaining why, OR cites the wrong drivers, OR drops the explanation entirely.

This judge only applies to cases where the user asked "why" or "explain" — not to simple "what's the rank" queries. For purely descriptive queries, this judge isn't relevant — score 1.0 by default.

## Prompt template

```
You are evaluating whether an AI assistant explains the drivers of a ranking when asked to.

USER REQUEST:
{request}

ASSISTANT RESPONSE:
{response}

RETRIEVED CONTEXT (should include the seven-component decomposition):
{retrieved_context}

TASK:
First, check whether the user asked for an explanation ("why", "explain", "drivers", "what's causing"). If not, score 1.0 — this judge doesn't apply.

If the user did ask for explanation, check whether the response:
- Names the top 3 contributors by absolute contribution (1.0)
- Mentions some drivers but not the full top-3, or skips the contribution magnitudes (0.5)
- Reports the rank without explaining drivers (0.0)

Drivers should be named in plain language ("chronic neglect", "wide funding gap", "high severity rate"), with their contribution magnitudes mentioned.

Output strictly as JSON: {{"score": <float>, "rationale": "<brief explanation>"}}
```

## Examples

**Full disclosure (1.0):**
"Sudan ranks 1st in 2025 primarily because of three drivers: chronic neglect (0.42 contribution), wide funding gap (0.31 contribution), and high severity rate (0.18 contribution). Media attention is below the global median, slightly raising the score (negative-weighted, +0.04 contribution)."

**Partial disclosure (0.5):**
"Sudan ranks 1st because of its chronic neglect and funding gap." (Mentions two drivers, no magnitudes, doesn't address the rest.)

**No disclosure (0.0):**
"Sudan ranks 1st in 2025." (No explanation at all.)
