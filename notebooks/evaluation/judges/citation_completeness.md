# citation_completeness

## Purpose

Verify that every factual claim carries enough provenance for a human to verify — minimally a `(iso3, year, table)` tuple. Catches hand-wavy claims without sources.

## Rubric

- **1.0** — Every substantive factual claim in the response is attributable to a specific source (iso3, year, table) either via inline citation or via clearly-named context ("from gold_forgotten_crisis_index for 2025…").
- **0.5** — Most claims are cited, but one or two are presented without provenance even though they could be (the data is there, the citation isn't).
- **0.0** — Substantive claims are presented without any citation, OR citations are vague enough that a human couldn't verify ("according to our data" without naming the table).

## Prompt template

```
You are evaluating whether an AI assistant cites sources for its factual claims.

USER REQUEST:
{request}

ASSISTANT RESPONSE:
{response}

RETRIEVED CONTEXT:
{retrieved_context}

TASK:
For each substantive factual claim in the response, check whether it carries provenance — minimally the country (iso3), year, and source table.

Citation can be:
- Inline ("Sudan, 2025, gold_forgotten_crisis_index")
- By clear context ("From the 2025 forgotten crisis index, Sudan ranks first…")
- By naming the source table once and referring to it across a coherent passage.

Citation cannot be:
- Vague ("our data shows…", "according to the analysis…")
- Missing for a claim that requires a specific source.

Score:
- 1.0 if every substantive claim is attributable
- 0.5 if most are cited but a few are missed
- 0.0 if claims are uncited or citations are too vague to verify

Output strictly as JSON: {{"score": <float>, "rationale": "<brief explanation>"}}
```

## Examples

**Complete (1.0):**
"Sudan ranks 1st in the 2025 forgotten crisis index (gold_forgotten_crisis_index), with a funding gap of 79% (gold_funding_funnel, SDN 2025)."

**Vague (0.0):**
"Sudan is the most overlooked crisis right now. The funding gap is huge."

**Partial (0.5):**
"Sudan ranks 1st in the 2025 forgotten crisis index. The country's gap ratio is 0.79." (Cited for ranking, not for gap_ratio source.)
