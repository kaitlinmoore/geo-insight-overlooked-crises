# grounded_numerics

## Purpose

Verify that every numeric claim in the agent's response traces to a value in the retrieved Gold rows. Catches hallucinated statistics, fabricated counts, and rounding-to-the-point-of-fabrication errors.

## Rubric

- **1.0** — Every number in the response can be matched to a value in `retrieved_context`. Rounding is fine if obvious and small (e.g., $1.23B → "$1.2 billion"). Percentage conversions are fine (e.g., 0.86 → "86%"). Ratios computed from retrieved values are fine if both inputs are retrieved.
- **0.5** — One or two numbers in the response cannot be matched to `retrieved_context`. The unmatched numbers are minor (e.g., a year mentioned in passing, an approximate count) and don't anchor the substantive claim.
- **0.0** — One or more substantive numbers in the response cannot be matched, OR a number is materially wrong (off by more than a rounding margin from what's in `retrieved_context`).

## Prompt template

```
You are evaluating whether an AI assistant's response contains only numeric claims that are grounded in retrieved data.

USER REQUEST:
{request}

ASSISTANT RESPONSE:
{response}

RETRIEVED CONTEXT (the actual data rows the assistant queried):
{retrieved_context}

TASK:
Identify every numeric claim in the assistant's response — counts, percentages, dollar amounts, rank positions, confidence interval bounds, years, growth rates, ratios.

For each numeric claim, check whether the value can be found in the retrieved context (allowing for obvious rounding, percentage conversions, and ratios computed from retrieved values).

Score:
- 1.0 if every numeric claim is grounded
- 0.5 if one or two minor numbers are ungrounded but the substantive claims are grounded
- 0.0 if any substantive number is ungrounded or materially wrong

Output strictly as JSON: {{"score": <float>, "rationale": "<brief explanation naming the ungrounded numbers if any>"}}
```

## Examples

**Grounded (1.0):**
Response: "Sudan ranked 1st in 2025 with overlooked_score 0.81 and a 95% CI of ranks 1-3."
Retrieved: `{iso3: SDN, rank_position: 1, overlooked_score: 0.812, rank_ci_low: 1, rank_ci_high: 3}` → all numbers match.

**Ungrounded substantive number (0.0):**
Response: "Sudan ranked 1st in 2025 with overlooked_score 0.95."
Retrieved: `{overlooked_score: 0.812}` → 0.95 is materially wrong.

**Minor ungrounded number (0.5):**
Response: "Sudan ranked 1st in 2025 with overlooked_score 0.81. The country has roughly 25 million people in need."
Retrieved has `overlooked_score: 0.81` but no `pin_total_country`. The 25M figure isn't in retrieved context — minor, doesn't anchor the headline claim.
