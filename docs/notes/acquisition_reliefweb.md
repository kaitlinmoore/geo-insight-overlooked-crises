# Acquisition findings: ReliefWeb situation reports — BLOCKED (awaiting appname)

> **Source of these findings.** Captured from a Claude Code acquisition session on 2026-05-22. An attempted two-stage scrape (metadata index + per-report body text) for 25 priority countries. **No report data was acquired** — both access paths are gated. An HDX fallback was investigated (negative) and an API-based acquisition script was built and queued, ready to run the moment the appname is approved. This note documents the blocker, the evidence, the HDX result, and the queued script so the next session resumes without re-discovering the wall.

## What was attempted

- **Goal**: media-attention signal (report counts per country × month, the negative-weighted attention proxy in the composite score) + an optional Knowledge Assistant body-text corpus.
- **Planned path**: unauthenticated HTML scraping of `https://reliefweb.int/country/{iso3}` listing pages, then per-report body extraction. API deliberately avoided because v2 requires an approved `appname` (applied for; timing uncertain).
- **Priority countries (25)**: SDN, YEM, MMR, BFA, MLI, NER, TCD, COD, SSD, COL, VEN, HTI, AFG, ETH, SOM, NGA, SYR, UKR, PSE, PHL, HND, GTM, CMR, CAF, MOZ.
- **Outcome**: blocked at the front door. No metadata CSV, no doc JSONs were produced.

## The blocker (verified, not inferred)

**Path A — HTML scraping is behind an AWS WAF JavaScript challenge.**

Every page request (homepage, `/country/sdn`, etc.) returns:

```
HTTP 202 Accepted
Server: awselb/2.0
x-amzn-waf-action: challenge
Content-Length: 2245
```

The 2245-byte body is **not** content — it's an AWS WAF challenge page:

```html
<script src="https://...token.awswaf.com/.../challenge.js"></script>
...
AwsWafIntegration.getToken().then(() => { window.location.reload(true); });
<noscript>... we need to verify that you're not a robot. This requires JavaScript. ...</noscript>
```

- The challenge requires executing `challenge.js` in a real JS engine to solve a cryptographic token (`window.gokuProps`) and obtain an `aws-waf-token` cookie before any real HTML is served.
- `robots.txt` itself returns the same 202 challenge (empty body to a plain client), so `urllib.robotparser` reads an empty ruleset and (misleadingly) reports "allowed" for every path. The real gate is the WAF, not robots.txt.
- Header experiments: a bare `User-Agent` (polite or browser) yields a **zero-length** 202; adding a full browser header set (`Accept`, `Accept-Language`, `Accept-Encoding`, `Upgrade-Insecure-Requests`) yields the 2245-byte challenge page — but still never real content. A `requests.Session` priming the homepage first did not help. **Plain `requests`/`BeautifulSoup` cannot pass this.**
- The WAF cookie domain list in the challenge spans the whole OCHA family: `interagencystandingcommittee.org`, `unocha.org`, `reliefweb.int`, `hpc.tools`, `un.org`, `humdata.org`.

**Path B — the v2 API requires an approved appname.**

`GET https://api.reliefweb.int/v2/reports?appname=geo-insight-unocha-hackathon` returns:

```json
{"status":403,"time":26,"error":{"type":"AccessDeniedHttpException",
 "message":"You are not using an approved appname. Kindly request an appname
 from ReliefWeb here: https://apidoc.reliefweb.int/parameters#appname"}}
```

- This is a clean **403** — the literal hard-stop trigger in the acquisition brief. It confirms the user's premise: v2 now enforces appname approval (historically `appname` was a self-declared free string; that era is over).
- The API endpoint itself is **not** WAF-challenged (it returned structured JSON, not a challenge page), so once the appname is approved the API is immediately usable without browser automation.

## Why we stopped instead of bypassing

The brief's failure-mode rules said: stop and report on (a) JavaScript-only page behavior and (b) any hard 403. We hit **both**. Beyond the letter of the rules, the spirit matters here: circumventing an AWS WAF bot-challenge on a **UN OCHA service** — the same organization sponsoring this hackathon — to scrape content the org also offers through a sanctioned, approval-gated API is the wrong trade. The polite-scraping ethos and the "content-access boundary we don't want to cross" instruction both point the same way. **Decision deferred to the human** (see Open questions).

## HDX investigation (time-boxed, 2026-05-22) — negative result

Question asked: does HDX carry any ReliefWeb content usable as the media-attention signal (report counts per country × month)? **Answer: no.** HDX has a `reliefweb` organization, but its holdings are *catalog / curated-figures* products, not the report-volume stream we need. All accessed via the plain CKAN API (`data.humdata.org/api/3/action/...`, no auth).

The `reliefweb` org has **4 datasets**:

| Dataset | What it is | Verdict |
|---|---|---|
| `reliefweb-disasters-list` | **Active** (weekly, freq 7), 3,707 rows, 1981→2026-05. One row per *declared disaster event* (floods, quakes, etc.) with `glide`, `primary_type-name`, `date-created/-event/-changed`, `primary_country-iso3` (lowercase). | A **hazard-occurrence catalog**, not a reporting-volume signal. Conceptually misaligned (counts declared disasters, not coverage) and biased toward sudden-onset natural hazards — chronic conflict crises (Sudan, Yemen) are under-represented as discrete "disasters." **Not usable** as the attention proxy. |
| `reliefweb-crisis-figures` | **ARCHIVED** (stops 2024-12). Curated key figures (PiN, IDPs…) for ~27 crises; `figure_url` links to ReliefWeb reports. | Stale + only 27 crises + it's *figures*, not volume. **Not usable.** |
| `unocha-glides` | A single JSON resource whose URL is literally `https://api.reliefweb.int/v1/disasters?appname=vocabulary`. | The **v1 API is decommissioned (HTTP 410)** — this HDX resource is broken. Confirms there is no open API path (even the appname HDX itself uses now 410s). |
| `asia-pacific-monitoring-on-diseases-disasters` | Regional Google Sheet, APAC disasters/diseases. | Out of scope. |

**Conclusion:** the per-country × month situation-report count (the negative-weighted attention proxy) is **only** available through the ReliefWeb v2 `reports` endpoint with date bucketing. HDX does not substitute for it. No interim fallback found.

## API-based acquisition script — BUILT, queued, untested-against-live

`src/acquisition/acquire_reliefweb.py` is written and ready to run the instant the appname is approved. It supersedes scraping entirely (no HTML fragility).

- **Stage 1 (required for v1)** — paginates `v2/reports` per country across the 36-month window (`profile=list`, page size 1000), writes:
  - `./staging/reliefweb_metadata.csv` — `iso3, country_name, title, publication_date, format, source_organization, report_url` (one row per matching report).
  - `./staging/reliefweb_media_attention.csv` — `iso3, year_month, report_count` (the attention signal, derived directly from the index rows so it does not depend on facet response shape).
- **Stage 2 (optional, KA corpus)** — `profile=full`, 20 most-recent docs/country, global cap 500, one JSON per doc at `./staging/reliefweb_docs/{iso3}/{YYYY-MM-DD}_{report_id}.json` matching the brief's schema (`body_text`, `body_word_count`, `scraped_at`, `scraper_version`).
- **Filters**: `format.name ∈ {Situation Report, Analysis, Assessment}`, `language.name=English`, `status=published`, `date.original` within 36 months. Country association via `country.iso3` (inclusive, matches public country-page semantics; a one-line constant switches it to `primary_country.iso3`).
- **Polite practice**: fixed `User-Agent` (`Geo-Insight-UNOCHA-Hackathon/1.0 (contact: 6ingeraffe@gmail.com)`), ≥1 request/second self-throttle, exponential backoff on 429/503 starting at 60 s (4 retries), and **immediate abort on HTTP 403** (appname rejected).
- **Modes**: `--check` (one request to validate the appname), `--stage1`, `--stage2`, or no flag for the full run. Reads `RELIEFWEB_APPNAME` from OS env or repo-root `.env`.
- **Verified now**: compiles clean; `--check` exercises the full HTTP + 403-abort path end-to-end against the live API and correctly reports "appname not approved" (exit 2). **Not verified**: the data-fetch paths (Stage 1/2 response parsing) — these need a real approved appname. On the first successful run, confirm the exact `format` taxonomy strings and that `body` populates under `profile=full`.
- **Config added**: `.env.example` created at repo root (was missing) documenting `RELIEFWEB_APPNAME` + the ACLED keys. The live `.env` has an **empty** `RELIEFWEB_APPNAME` (approval not yet received as of 2026-05-22).

**To run once approved:** put the approved value in `.env` → `python src/acquisition/acquire_reliefweb.py --check` → if OK, `python src/acquisition/acquire_reliefweb.py`.

## Path NOT taken: WAF-bypass automation

Browser automation (Playwright/Selenium driving `challenge.js` to mint the `aws-waf-token` cookie, then reusing it for `requests`) is technically feasible but **consciously declined**: it deliberately defeats the operator's bot control, contradicts the brief's stop-rules, and is needless when the sanctioned API is one approval away. Documented so a future contributor knows it was considered, not overlooked.

## Output files

**None produced yet** (gated on appname). The script writes, on a successful run:

- `./staging/reliefweb_metadata.csv` — `iso3, country_name, title, publication_date, format, source_organization, report_url`
- `./staging/reliefweb_media_attention.csv` — `iso3, year_month, report_count` (the v1 attention signal)
- `./staging/reliefweb_docs/{iso3}/{YYYY-MM-DD}_{report_id}.json` — per the brief's schema (`body_text`, `body_word_count`, `scraped_at`, `scraper_version`, …)

## Implications for downstream

- **Silver `media_attention`**: the negative-weighted attention proxy depends on this signal. It is **not yet available**. The HDX fallback was checked and does **not** substitute (see HDX section). Only path is the v2 API once the appname clears — then `reliefweb_media_attention.csv` is the direct input. Until then, the attention term in the composite score has no input — **flag in methodology as a known gap**.
- **Bronze / KA corpus**: no JSON docs to ingest yet. KA is a Day-4 stretch goal, so the corpus is not on the v1 critical path — but the v1 media-attention signal **is** required, and it shares the same blocker.
- **No HTML-structure / CSS-selector dependency to document** (the original scraping ask): the API path makes it moot. If anyone ever reverts to scraping, the AWS WAF challenge must be solved first; the listing/report selectors were never reachable to verify.

## Open questions

- **Appname approval status & ETA?** The single gating item. When it lands, drop it in `.env` and run — the script is ready.
- **Format taxonomy exact strings**: confirm `Situation Report` / `Analysis` / `Assessment` spelling against the API's `format` reference on the first successful run (the filter is exact-match).
- **Country association choice**: script defaults to `country.iso3` (any tagged country, matches the public country-page). If the attention signal should attribute each report to a single country, switch to `primary_country.iso3` (one-line constant) — decide before the signal feeds the score.
- **Is browser-automation WAF bypass acceptable?** Default assumption **no** (see "Path NOT taken"). Only revisit if the appname is indefinitely stalled and the signal is blocking v1.
