# NRC World's Most Neglected Displacement Crises — acquisition summary

## Result

`./staging/nrc_most_neglected_lists.csv` — **90 rows across 9 years** (top-10 each), schema as specified (`year, rank, iso3, country_name, source_url`). All ISO3 codes resolved via pycountry; zero unresolved, zero fuzzy matches.

| Data year | #1 country | Source page |
|---|---|---|
| 2016 | Central African Republic | nrc.no/perspectives/2016/… |
| 2017 | DR Congo | nrc.no/news/2018/june/… |
| 2018 | Cameroon | nrc.no/shorthand/…/the-worlds-most-neglected-displacement-crises/ |
| 2019 | Cameroon | nrc.no/shorthand/…/-in-2019/ |
| 2020 | DR Congo | nrc.no/resources/reports/…-in-2020/ |
| 2021 | DR Congo | nrc.no/resources/reports/…-in-2021 |
| 2022 | Burkina Faso | nrc.no/feature/2023/…-in-2022 |
| 2023 | Burkina Faso | nrc.no/resources/reports/…-in-2023 |
| 2024 | Cameroon | nrc.no/feature/2025/…-in-2024 |

Full per-row source URLs are in the CSV.

## Key findings

- **NRC publishes a single ranked top-10 — no severity tier.** Unlike the binary implied for ECHO FCA, NRC does *not* split "fully" vs "partially" neglected. The signal is the **rank** (1 = most neglected). The cross-reference in `DGECHO.md` (that NRC "does tier") is not borne out — NRC's tiering is ordinal rank, not a category label.
- **Year label = data year, published the following June.** The "2024" list was published June 2025 (Cameroon #1). Press and some NRC URLs inconsistently use the *publication* year, which blends adjacent editions in search results. Every year here is anchored on NRC's canonical archive (`nrc.no/neglected`) and confirmed against a per-year NRC page. **The CSV uses data year — confirm this matches the year key in the overlooked index before computing top-N overlap.**
- **Three-criteria methodology** (consistent across editions): lack of funding, lack of media attention, lack of political/diplomatic engagement. Aligns with the project's "overlooked ≠ underfunded" framing — NRC explicitly weights media + political neglect, not just funding.

## Gaps

- **2015** — no edition exists. The NRC series began with the 2016 data year (first list published June 2017).
- **2025** — not published yet; next edition due ~June 2026.

So 9/11 requested years; the two missing are structural (series boundaries), not extraction failures.

## ISO3 mapping — 18 alias-mapped rows (all flagged, high confidence)

All are official-vs-common name variants, not uncertain matches:

- **Democratic Republic of the Congo → `COD`** (every year) — pycountry official: "Congo, The Democratic Republic of the".
- **Venezuela → `VEN`**, **Iran → `IRN`** — pycountry officials carry "Bolivarian Republic of" / "Islamic Republic of".
- **Palestine → `PSE`** (2016–2018) — pycountry official "Palestine, State of"; **politically contested entity**. Watch this one: it may not exist as a row in the FTS/HNO-derived universe and could legitimately drop from overlap.

## Confidence notes

- **2020–2024**: high — multiple corroborating sources per year.
- **2016–2019**: grounded on NRC canonical per-year pages and confirmed via the contemporaneous NRC press release naming the #1 country.
- **2017** (DR Congo #1) was the shakiest initially (search summaries blended it with adjacent editions); confirmed against NRC's June 2018 "DR Congo tops neglected crises list" release.

## Provenance / artifacts

- Re-runnable script: `src/acquisition/acquire_nrc_neglected.py` (lists embedded with per-year source URLs; maps ISO3 via pycountry; no network needed).
- Data gathered via NRC web pages/reports (not a downloadable API), so no source files retained in `./staging/`.
- Per CLAUDE.md one-off-acquisition scope rule, `STATE.md` / `DECISIONS.md` were not touched.

## Open questions

- Keep **Palestine (PSE)** in the comparator, or exclude (no standard HRP/FTS counterpart)?
- Match overlap on **data year** (as compiled) — confirm the overlooked index is keyed the same way and not by publication year.
- Is the **rank** worth using as a weighted signal in overlap (e.g. rank-correlation vs simple top-N set intersection), given NRC provides ordinal position?
