# DG ECHO Forgotten Crises Assessment — acquisition summary

## Result

`./staging/echo_fca_lists.csv` — **197 rows across 10 years**, schema as specified (`year, iso3, country_name, crisis_name, forgotten_category, source_url`). All ISO3 codes validated against pycountry (zero unrecognised).

| Year(s) | Source | Entries/yr |
|---|---|---|
| 2015 | `fca_2014_2015.pdf` (ISO3 in source) | 12 |
| 2016 + 2017 | GGOPHA 2017 Annex III "FCA 2016-2017" (ISO3 in source) | 12 |
| 2019 + 2020 | GGOPHA 2020 Annex III "FCA 2019-2020" (ISO3 in source) | 37 |
| 2021 | forgotten-crises web page | 20 |
| 2022 + 2023 | web page "For 2022-2023" | 14 |
| 2024 | web page (confirmed by GGOPHA 2024 SWD) | 15 |
| 2026 | live web page (bonus, outside requested range) | 24 |

## Key findings

- **No "fully forgotten" vs "partially forgotten" split exists** in any 2015-2026 ECHO source. ECHO publishes one undifferentiated list, so `forgotten_category` is `"forgotten"` everywhere. That binary in the brief likely conflates ECHO with **NRC Most Neglected** (which does tier) — worth keeping in mind for the NRC acquisition.
- **FCA is biennial-labelled.** Three assessments each name two operative years; emitted under both years with an identical `source_url` per pair, so `(iso3, year)` joins cleanly. 2016==2017, 2019==2020, 2022==2023 by construction.

## Gaps

- **2018** — no standalone GGOPHA doc archived; couldn't locate a list.
- **2025** — the web page skipped from the 2024 list straight to 2026 (snapshots through Aug 2025 still showed 2024). Likely no distinct 2025 list was published.

## Two things to verify by eye

1. **Suspected source typo:** the 2019/2020 annex lists `GIN Guinea` under the Caribbean "Venezuelan/Haitian refugees" group — almost certainly meant to be **Guyana (GUY)**. Kept verbatim as GIN and flagged. Source PDFs are retained in `./staging/` to check.
2. **2019/2020 is 37 rows** (vs ~15 elsewhere) because that annex enumerated every member of each regional crisis — a formatting artifact, not a severity signal. Consider down-weighting regional-member rows in overlap analysis.

## Provenance / artifacts

- Re-runnable script: `src/acquisition/acquire_echo_fca.py` (data embedded with per-year source URLs; validates ISO3; no network needed).
- Detailed findings: `docs/notes/acquisition_echo_fca.md`.
- Source PDFs retained in `./staging/`: `fca_2014_2015.pdf`, `ggopha_2017.pdf`, `ggopha_2020.pdf`, `ggopha_2024_swd.pdf`, `gvca_2014_en.pdf`.
- Per CLAUDE.md one-off-acquisition scope rule, `STATE.md` / `DECISIONS.md` were not touched.

## Open questions

- Accept the `GIN → GUY` (Guyana) correction for 2019/2020?
- Is 2018 / 2025 worth a deeper hunt (EUR-Lex SWD search, partners-helpdesk document repository), or is 10/11 years sufficient for the comparator?
