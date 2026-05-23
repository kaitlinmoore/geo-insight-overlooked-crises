# counterfactual_stability

## Purpose

Verify that small perturbations to the input produce small changes in the output. Catches brittleness — responses that change meaningfully when the user rephrases or makes a typo.

## Rubric

This judge operates **across perturbed pairs**. The eval framework runs the original case alongside a perturbed variant (typo, slight rephrasing, synonym substitution) and asks this judge to compare semantic stability.

- **1.0** — Both responses convey the same substantive content. Wording may differ, ordering may differ, but the factual claims, citations, and recommendations are equivalent.
- **0.5** — Most content is stable but at least one substantive element differs — different number, different country highlighted, different metric chosen.
- **0.0** — Materially different responses to semantically-equivalent inputs. Different rankings reported, different sources cited, different framing.

## Prompt template

```
You are evaluating whether an AI assistant produces stable responses to semantically-equivalent inputs.

ORIGINAL REQUEST:
{request_original}

ORIGINAL RESPONSE:
{response_original}

PERTURBED REQUEST (a minor rephrasing or typo correction of the original):
{request_perturbed}

PERTURBED RESPONSE:
{response_perturbed}

Compare the two responses. Wording can differ; ordering can differ. The factual claims, numeric values, and citations should be equivalent.

Score:
- 1.0 if the substantive content is equivalent
- 0.5 if most content matches but one substantive element differs
- 0.0 if material differences in the factual content

Output strictly as JSON: {{"score": <float>, "rationale": "<what differs if anything>"}}
```

## Examples

**Stable (1.0):**
Request original: "Where does Sudan rank in 2025?"
Request perturbed: "What's Sudan's 2025 ranking?"
Both responses: rank 1, CI 1-3, neglect_class chronic_neglect — equivalent.

**Unstable (0.0):**
Request original: "Where does Sudan rank in 2025?" → rank 1
Request perturbed: "What's Sudan's 2025 ranking?" → rank 4
(Same data should give the same answer.)
