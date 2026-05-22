# Acquisition findings: ReliefWeb situation reports — ACQUIRED (v2 API)

> **Source of these findings.** Claude Code acquisition sessions on 2026-05-22.
> The appname was approved; `src/acquisition/acquire_reliefweb.py` ran end-to-end
> against the v2 API (no scraping). Both stages completed: the metadata index +
> per-country × month attention signal (Stage 1) and the Knowledge-Assistant
> body-text corpus (Stage 2). This note records the actual results; the earlier
> appname/WAF blocker is **resolved** (condensed history at the bottom).

## What was acquired

- **Goal**: the negative-weighted media-attention signal (situation-report counts
  per country × month) for the composite score, plus a body-text corpus for the
  Day-4 Knowledge Assistant stretch goal.
- **Path**: ReliefWeb v2 API, `appname` approved. Filters: `format.name ∈
  {Situation Report, Analysis, Assessment}`, `language=English`,
  `status=published`, `date.original` within a 36-month window.
- **Window**: `2023-06-08 → 2026-05-22` (36 months).
- **Priority countries (25)**: SDN, YEM, MMR, BFA, MLI, NER, TCD, COD, SSD, COL,
  VEN, HTI, AFG, ETH, SOM, NGA, SYR, UKR, PSE, PHL, HND, GTM, CMR, CAF, MOZ.

## Output files (in `./staging/`, gitignored)

| File | Rows / size | Schema |
|---|---|---|
| `reliefweb_metadata.csv` | **47,339 rows** | `iso3, country_name, title, publication_date, format, source_organization, report_url` |
| `reliefweb_media_attention.csv` | **900 cells** (25 countries × 36 months) | `iso3, year_month, report_count` |
| `reliefweb_docs/{iso3}/{YYYY-MM-DD}_{report_id}.json` | **500 docs**, ~3.4 MB on disk; **median 281 body words** | `iso3, country_name, title, publication_date, format, source_organization, report_url, body_text, body_html, body_word_count, all_countries, report_id, scraped_at, scraper_version` |

- **Metadata**: 47,339 report rows across all 25 countries. Format mix:
  Situation Report 28,138 · Analysis 15,057 · Assessment 4,144. (The exact
  taxonomy strings `Situation Report` / `Analysis` / `Assessment` are confirmed
  against the live API — the prior open question on spelling is resolved.)
- **Media attention**: a complete 25 × 36 dense grid — every country has a row
  for every month in the window (zeros where a country had no reports that
  month), so the signal needs no gap-filling downstream.
- **KA corpus (Stage 2)**: 20 most-recent docs per country (uniform 20/country,
  500 total), **182,890 body words** total. Word-count distribution:
  `min=0 · p25=150 · median=281 · p75=482 · p90=742 · max=1,945`. Each JSON
  carries both `body_text` and `body_html` plus the brief's audit fields.
  **45 docs fall below the script's 100-word "short" threshold** (`< 100` words,
  including the 1 fully empty body).

## Per-country report distribution (metadata rows)

```
SDN 4288   SYR 3376   PSE 3034   PHL 3012   AFG 2835
UKR 2751   SOM 2584   SSD 2464   ETH 2423   NGA 2046
MMR 2042   COD 1935   YEM 1684   TCD 1580   MOZ 1335
HTI 1314   MLI 1288   CAF 1207   CMR 1086   NER 1062
BFA 1011   COL  993   VEN  806   GTM  605   HND  578
```

Sudan leads (4,288), tracking its status as the headline crisis; the Latin
American cases (VEN, GTM, HND) sit lowest — consistent with the "overlooked"
thesis that report volume (attention) and need diverge.

## Quirks encountered

- **Inclusive country association inflates raw counts.** The script used
  `country.iso3` (any tagged country), matching ReliefWeb's public country-page
  semantics. The 47,339 rows resolve to **26,381 distinct reports** — **5,618
  reports (21.3%)** are tagged to more than one priority country and therefore
  appear once per country. This is correct and intended for a *per-country*
  attention signal (a Syria-3RP regional sitrep legitimately counts as attention
  for SYR and JOR and LBN), but **downstream must not sum `report_count` across
  countries as a global total** — it would double-count. If a single-attribution
  variant is ever needed, re-run with `primary_country.iso3` (one-line constant).
- **Empty / short bodies (attachment-only posts).** 1 doc has a fully empty
  body (`NGA/2026-05-16_4212413.json`, "Nigeria Weekly Sitrep May 8–14 2026") and
  45 fall below 100 words — these are ReliefWeb posts whose substance lives in
  an attached PDF with little or no inline HTML body. Short docs cluster in the
  weekly-sitrep-heavy countries (PHL 5, and ETH / NGA / SDN / SSD 4 each); 9 of
  the 25 countries have **zero** short docs (CAF, CMR, HND, HTI, SOM, …).
  **Recommended Silver-layer filter for KA: drop `body_word_count < 100`** before
  chunking/embedding (≈9% of the corpus) so attachment-only stubs don't pollute
  the vector index. The metadata + `media_attention` signals are unaffected —
  those count the *report*, regardless of inline body length.
- **Quality check — passed.** Manual inspection of median-length samples
  confirms substantive prose, not boilerplate. E.g. `HTI/2026-05-07_4210985.json`
  (287 words, Analysis) opens "The humanitarian situation in Haiti has continued
  to rapidly deteriorate since April 2025… armed gangs… expansion into Centre and
  Artibonite departments"; `COD/2026-05-19_4212781.json` (359 words, Situation
  Report) carries structured DREF flood-response detail for Uvira, South Kivu.
  The above-threshold corpus is fit for KA ingestion.
- **`body_html` retained alongside `body_text`.** The corpus keeps both; KA
  ingestion should prefer `body_text` (already stripped) and treat `body_html`
  as provenance only.

## Implications for downstream

- **Silver `media_attention`** — the negative-weighted attention proxy now has
  its input: `reliefweb_media_attention.csv` is the direct source (per-country ×
  month counts, dense grid). The earlier "known gap, flag in methodology" caveat
  is **lifted**. Remember the inclusive-association note above: the signal is
  per-country by design; don't aggregate to a global denominator.
- **KA stretch goal is viable** — the 500-doc / 25-country corpus exists (≈454
  usable after the `< 100`-word filter) and can be indexed against the
  (already-provisioned, Online) Vector Search endpoint when Day-4 slack allows.
  Not on the v1 critical path, but no longer blocked.
- **Bronze loader** — straightforward: `reliefweb_metadata.csv` and
  `reliefweb_media_attention.csv` map to `bronze_reliefweb_metadata` and
  `bronze_reliefweb_attention`; the JSON corpus to a `bronze_reliefweb_docs`
  table (or a volume path for KA chunking). Drop the one empty-body doc in Silver.

## Resolved history (condensed)

The first acquisition attempt (also 2026-05-22, earlier) was **blocked** and is
worth keeping for context:

- **HTML scraping was walled off** by an AWS WAF JavaScript challenge (HTTP 202,
  `x-amzn-waf-action: challenge`) across the whole OCHA domain family. Plain
  `requests`/`BeautifulSoup` could not pass it; browser-automation bypass was
  consciously declined (defeating a UN OCHA bot control to scrape content the
  org also offers via a sanctioned API was the wrong trade).
- **The v2 API initially returned a clean 403** ("not using an approved
  appname"). We stopped and requested the appname rather than improvise.
- **An HDX fallback was investigated and rejected** — the `reliefweb` HDX org
  carries a hazard-occurrence catalog and archived curated figures, not the
  report-volume stream; the v1 API resource it references is decommissioned
  (HTTP 410). No substitute for the v2 `reports` endpoint.

Once the appname was approved, the pre-built API script ran cleanly and produced
everything above — vindicating the decision to wait for the sanctioned path
rather than bypass the WAF.
