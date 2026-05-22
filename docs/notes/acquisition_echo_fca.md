# Acquisition findings: ECHO Forgotten Crises Assessment (FCA)

> **Source of these findings.** Captured from a Claude Code acquisition session on 2026-05-22. Findings are the session's verified observations on the located ECHO sources, not inferences from documentation. Marked clearly where facts were verified vs. flagged as uncertain. Promote into `docs/prior-art.md` / validation notes when those are revised.

## What was acquired

- **Comparator**: DG ECHO Forgotten Crises Assessment annual lists. Layer 2 validation comparator (top-N overlap analysis alongside NRC Most Neglected). Not used as training labels.
- **Output**: `./staging/echo_fca_lists.csv` — 197 rows, 10 years.
- **Script**: `src/acquisition/acquire_echo_fca.py`. Holds the hand-extracted lists with per-year source URLs, validates every ISO3 with `pycountry`, writes the CSV. Re-runnable offline (no network needed; data is embedded with provenance).
- **Schema**: `year, iso3, country_name, crisis_name, forgotten_category, source_url`.
- **Source PDFs retained in `./staging/`** for eye-verification: `fca_2014_2015.pdf`, `ggopha_2017.pdf`, `ggopha_2020.pdf`, `ggopha_2024_swd.pdf`, `gvca_2014_en.pdf`.

## Years covered (10) and where each came from

| Year(s) | Source | ISO3 in source? | Entries |
|---|---|---|---|
| 2015 | `fca_2014_2015.pdf` ("FCA 2014") | Yes (table) | 12 |
| 2016 + 2017 | `ggopha_2017.pdf` Annex III ("FCA 2016-2017", Sep 2016) | Yes (table) | 12 each |
| 2019 + 2020 | `ggopha_2020.pdf` Annex III ("FCA 2019-2020") | Yes (table) | 37 each |
| 2021 | forgotten-crises web page (Wayback 2022-02) "In 2021" | No (mapped) | 20 |
| 2022 + 2023 | web page (Wayback 2023-04) "For 2022-2023" | No (mapped) | 14 each |
| 2024 | web page (Wayback 2024-08) "For 2024"; confirmed by GGOPHA 2024 SWD(2023)354 | No (mapped) | 15 |
| 2026 | live web page "For 2026" | No (mapped) | 24 |

2026 is beyond the requested 2015-2025 range; included because it is the current published list.

## Gaps (could not locate a reliable list)

- **2018** — no standalone GGOPHA 2018 document found in Wayback or on the live EC servers; the web page was not archived this far back.
- **2025** — the official web page skipped directly from the 2024 list to the 2026 list (snapshots through Aug 2025 still showed the 2024 list; by Feb 2026 it showed 2026). No 2025 GGOPHA SWD located. Likely no distinct 2025 list was published; the FCA cadence is effectively biennial.

## Verified facts (directly checked)

- **No "fully forgotten" vs "partially forgotten" split exists in any 2015-2026 ECHO source.** ECHO publishes a single undifferentiated list. `forgotten_category` is therefore `"forgotten"` for every row. The fully/partially binary in the task brief does not match ECHO's modern methodology (it may be a conflation with NRC Most Neglected, which does tier its list — relevant for the NRC acquisition).
- **FCA is a biennial-labelled exercise.** `fca_2014_2015`, `FCA 2016-2017`, `FCA 2019-2020` each name two operative years. Their lists are emitted under **both** named years (identical `source_url` per pair), so the comparator joins cleanly on `(iso3, year)`. The web era similarly published a combined "2022-2023" list.
- **The 2024 web list is corroborated** by the GGOPHA 2024 Staff Working Document (SWD(2023) 354), which states the list derives from the "2022-2023 assessment" but is published "For 2024".
- **All ISO3 codes validate against `pycountry`** (0 unrecognised). PDF-table years carry ISO3 verbatim from ECHO; web years were mapped by hand and validated.

## Quirks worth knowing about

- **The 2019-2020 list is much larger (37 vs ~15).** That annex enumerated *every* member country of each regional crisis (Rohingya regional, Burundi regional, CAR regional, Sahel, Central America, Caribbean Venezuelan/Haitian refugees). Other years name fewer countries. Do not read the count as a severity signal — it is a formatting difference. Consider whether regional-member rows should be down-weighted in overlap analysis.
- **Suspected source typo, 2019/2020: `GIN Guinea` under the Caribbean "Venezuelan and Haitian refugees crisis" group.** Guinea (West Africa) does not fit; this is almost certainly meant to be **Guyana (GUY)**, which borders Venezuela and hosts Venezuelan refugees. Kept **verbatim as GIN** in the CSV (with a note in `crisis_name`); fix to GUY if you accept the interpretation.
- **DPRK (PRK) excluded from 2019/2020.** The annex footnote states the DPRK food crisis "has been identified as a forgotten crisis. However, the situation is currently not conducive for principled humanitarian operations which is why it has not been included in the list." Excluded accordingly.
- **One blank-ISO3 row (2024 "Central America").** That year's web list said "Multiple crises in Central America" without naming members, so `iso3` is blank and the row is flagged. In 2026 the same crisis names Guatemala/El Salvador/Honduras and is expanded to three rows.
- **Regional entries that name members are expanded** to one row per member (e.g. 2026 Central Sahel -> BFA/MLI/NER). Per-year dedupe on ISO3 keeps the first occurrence when a country appears both standalone and in a group.
- **FCA Index scores available but not captured.** The PDF-table years (2015/2017/2020) include the 0-12 FCA Index and its four sub-dimensions (INFORM/vulnerability, media coverage, public aid per capita, qualitative). Not in the CSV schema; extractable from the retained PDFs if a numeric comparator is wanted.

## Implications for downstream use

- Join the comparator on `(iso3, year)`. Biennial duplication means 2016==2017 and 2019==2020 and 2022==2023 by construction.
- For top-N overlap, decide how to treat the oversized 2019/2020 regional-member rows and the blank-ISO3 2024 row.
- 2018 and 2025 will be missing from any per-year overlap; document as comparator gaps.

## Open questions

- Accept `GIN -> GUY` (Guyana) correction for 2019/2020?
- Should biennial assessments be emitted under both years (current behaviour) or collapsed to the single funding year?
- Is a 2018 / 2025 list worth a deeper hunt (EUR-Lex SWD search, partners-helpdesk document repository), or are 10/11 years sufficient for the comparator?
