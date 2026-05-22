# Acquisition findings: OCHA HDX Signals

> **Source of these findings.** Captured from a Claude Code acquisition session on 2026-05-22. Verified observations on the live HDX Signals product and dataset, not inferences. Promote into `docs/methodology.md` (integration point) and `docs/data-catalog.md` if Signals is cited in v1.

## Bottom line

HDX Signals exists, is actively maintained (code v0.5.0.0, 3 March 2026), and offers **full structured bulk access** — a weekly-updated, CC BY-IGO CSV on HDX. Pulled and saved. **But** it is built almost entirely on datasets we already ingest directly (ACLED, IPC, IDMC, ACAPS INFORM Severity). So its value to us is as a **methodology citation / "recent deterioration alerts" integration point**, not as a new input to the overlooked-crises ranking.

## What it is

HDX Signals (OCHA Centre for Humanitarian Data) monitors key humanitarian datasets and **generates automated alerts when significant negative changes are detected**, delivered as email campaigns plus a published dataset. It is a *change-detection / acute-deterioration* product — directly relevant to our "chronic neglect vs. acute deterioration" differentiator and the Triage change-indicators panel.

- Website / signup: `https://data.humdata.org/signals` (note: `centre.humdata.org/signals/` 404s; the live home is on data.humdata.org)
- Code + technical docs: `https://github.com/OCHA-DAP/hdx-signals` (GPLv3)
- Methodology: `https://un-ocha-centre-for-humanitarian.gitbook.io/hdx-signals`

## Structured access — AVAILABLE (pulled)

HDX dataset `hdx-signals` (`data.humdata.org/dataset/hdx-signals`), 3 CSV resources, all downloaded to `./staging/`:

| Saved file | Source resource | Rows |
|---|---|---|
| `hdx_signals_current.csv` | `hdx_signals.csv` (the alerts table) | 1,374 |
| `hdx_signals_location_metadata.csv` | location coverage + per-indicator boundary sources | 251 |
| `hdx_signals_data_dictionary.csv` | field definitions | 22 fields |

- **License:** CC BY-IGO. **Update frequency:** 7 (weekly). **Source:** "Multiple Partners". **Last modified:** 2026-05-15. **Date span:** 1998-05-15 → 2026-05-06 (historical backfill + current).
- Programmatic pull is a plain CKAN call — no auth/app-identifier needed:
  `https://data.humdata.org/api/3/action/package_show?id=hdx-signals` → resource download URLs.
- **Not in HDX HAPI.** HAPI exposes food-security/conflict/IDP/etc. subcategories but has **no Signals endpoint**. Signals is its own HDX dataset, not a HAPI resource.

## Topics / indicators (actual)

The brief said "~5 topics"; the live data has **7 active indicators** (an 8th, `who_cholera`, exists in the location-metadata schema but produced no current alerts). Counts in the current pull:

| `indicator_id` | Theme | Alerts |
|---|---|---|
| `acled_conflict` | Conflict | 397 |
| `jrc_agricultural_hotspots` | Food security / agriculture | 295 |
| `idmc_displacement_conflict` | Displacement (conflict) | 160 |
| `idmc_displacement_disaster` | Displacement (disaster) | 148 |
| `ipc_food_insecurity` | Food security | 143 |
| `acaps_inform_severity` | Crisis severity | 136 |
| `wfp_market_monitor` | Markets / food prices | 95 |
| `who_cholera` | Health | 0 (schema only) |

These collapse to roughly five themes: **conflict, food insecurity, displacement, severity, markets/health**.

## Coverage & alert structure

- **Locations:** 251 in the metadata file (≈ the "~200 locations" claim); **107 distinct ISO3** have at least one alert in the current table. Keyed on **ISO3** (mostly official; a few custom codes — documented in the metadata file). Tagged by UNOCHA region and an `hrp_location` boolean.
- **Alert levels:** `High concern` (500) and `Medium concern` (874). An alert fires only if no alert at that level-or-higher occurred in the prior ~6 months (de-duplication built in); a `extreme_case` flag bypasses the 180-day filter for severe cases (e.g. IPC Phase 5).
- **Rich per-alert payload:** AI-generated `summary_short` / `summary_long`, source URLs, plot/map image URLs, HDX dataset link, and `campaign_date`/`campaign_url`. Example: `SOM / ipc_food_insecurity / 2026-04-01 / High concern — "Poor rains, food prices worsen hunger; 6 million need aid."`

## Overlap with our pipeline (the key caveat)

Signals' inputs are **our inputs**: ACLED (our primary independent severity signal), IPC (our Day-4 food-security stretch), IDMC, ACAPS INFORM Severity, plus JRC hotspots and WFP markets. It does **not** add an independent data layer for the composite score. What it adds is OCHA's **packaged change-detection + thresholds + AI summaries** over those sources.

## Recommendation (given time budget)

**Cite it; optionally surface it; do not depend on it for v1.**

- **Cite as an integration point (low effort, high credibility):** name HDX Signals in `docs/methodology.md` as the canonical OCHA change-detection product our "acute deterioration" axis aligns with, and as a future feed for the Triage change-indicators / alert panel. This is a strong UN-audience signal that our framing matches OCHA's own tooling.
- **Optional v1 nicety:** the `summary_short` + `source_url` + `campaign_date` fields are well-suited to a "recent alerts for this country" strip in Crisis Explorer's narrative panel. Cheap because the CSV is already pulled and joins on ISO3.
- **Avoid:** wiring Signals into the `overlooked_score` itself — it would double-count ACLED/IPC/IDMC and muddy validation cleanliness (same reason CIRV was deferred). Keep it presentational/contextual.
- **Refresh cost if used:** trivial — re-run the CKAN download (weekly cadence). No credentials.

## Artifacts

- `./staging/hdx_signals_current.csv`, `./staging/hdx_signals_location_metadata.csv`, `./staging/hdx_signals_data_dictionary.csv` (gitignored staging).
- Per CLAUDE.md one-off-acquisition scope rule, `STATE.md` / `DECISIONS.md` were not touched.

## Open questions

- Confirm `who_cholera` is genuinely dormant vs. seasonal before relying on a health axis.
- If we surface AI `summary_*` text in the UI, confirm attribution/disclaimer requirements (campaigns carry an OCHA disclaimer; CC BY-IGO requires attribution).
