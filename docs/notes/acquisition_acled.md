# Acquisition findings: ACLED conflict data

> **Source of these findings.** Captured from a Claude Code acquisition session on 2026-05-22. Findings are the session's verified observations on the downloaded datasets, not inferences from documentation. Marked clearly where facts were verified vs. sampled vs. open. Promote into `docs/data-catalog.md` and `docs/schemas.md` when those are written.

## Headline

ACLED was acquired via **two distinct sources feeding two distinct Silver paths**, because the HDX mirror and the ACLED API turned out to carry materially different data — the original premise that "HDX is the same data, just simpler" is false.

| Path | Source | Output | Grain | Coverage window | Feeds |
|---|---|---|---|---|---|
| **Severity** | HDX (aggregated XLSX) | `staging/acled_severity_admin2_month_2020_present.parquet` | Admin2 × Month × category | **2020-01 → 2026-05** (current) | `silver_acled_severity` |
| **Events** | ACLED OAuth API | `staging/acled_events_2020_present.parquet` | Point event | **2020-01 → 2025-05** (12-mo embargo) | `silver_acled_events` (H3 res-5) |

The two paths have **complementary gaps**: HDX is current but has no coordinates; the API has coordinates but the account is embargoed from the most recent 12 months. Neither alone satisfies both "independent severity signal" and "recent spatial-temporal hotspots." See **Open questions**.

Scripts (re-runnable, resolve URLs at runtime):
- `src/acquisition/acquire_acled.py` — HDX severity path. No credentials.
- `src/acquisition/acquire_acled_api.py` — API event path. Needs `ACLED_USERNAME`/`ACLED_PASSWORD` in `.env`.

---

## Path 1 — HDX severity (Admin2 × Month)

### Identity
- **Source**: HDX organization `acled` (`data.humdata.org/organization/acled`), 243 per-country datasets named `{country}-acled-conflict-data`.
- **License**: `hdx-other` (ACLED Terms of Use & Attribution Policy — embedded as a `TOU` sheet in every file; attribution required).
- **Refresh**: `data_update_frequency: 7` (weekly); all 25 files last modified 2026-05-20.
- **Output**: `acled_severity_admin2_month_2020_present.parquet` — 942,126 rows, **25/25 priority countries**, 1.2 MB.

### What HDX actually serves (the big surprise)
ACLED's HDX country datasets are **not event-level**. Each dataset has **three aggregated XLSX** resources — `..._political_violence_events_and_fatalities_by_month-year`, `..._civilian_targeting_...`, `..._demonstration_...` — each a `Data` sheet of **counts by Admin2 × Month × Year**. There are **no coordinates, no event_date, no sub_event_type, no actors, no notes, no source**. The event "type" is encoded by *which of the three files* a row comes from, captured here as the `event_category` column.

### Schema (14 columns)
```
iso3            ISO3 alpha from the source (NULL for GTM/HND/PHL — see quirks)
priority_iso3   ISO3 we requested; reliable join key (added by us)
country         long-form country name
admin1, admin2  admin unit names
admin1_pcode    e.g. SD12   (P-codes — unique value-add of this path)
admin2_pcode    e.g. SD12075
event_category  political_violence | civilian_targeting | demonstration
year            int
month_name      'January'..'December'
month_num       1..12 (added)
month_start     first-of-month datetime (added; convenience key)
events          count of events in that admin2 × month × category
fatalities      count of fatalities likewise
```

### Verified facts
- **`priority_iso3` covers all 25; source `iso3` is NULL for GTM, HND, PHL.** ACLED left the ISO3 column blank in those three files. **Join on `priority_iso3`, never on `iso3`.**
- **P-codes are this path's reason to exist.** The event API does *not* return P-codes; these admin1/admin2 P-codes are how the Silver layer should join ACLED to boundary geometries.
- **Includes zero rows.** 600,150 of 942,126 rows have `events == 0` (every admin2 × month gets a row even with no activity). A missing cell ≠ zero here; zero is explicit. Useful for time-series, but filter `events > 0` before most analysis.
- **Coverage is current** — through 2026-05 for all countries (month-grain).
- Spot-check (events_sum / fatalities_sum, 2020-01→2026-05): Sudan 29,503 / 85,481 · Yemen 63,943 / 58,599 · **Myanmar 96,076 / 117,215** · Burkina Faso 12,520 / 40,214 · Haiti 13,074 / 20,852. Myanmar's very high counts match expectation.

---

## Path 2 — ACLED API events (point-level)

### Identity
- **Source**: ACLED OAuth API. Token: `POST https://acleddata.com/oauth/token` (grant_type=password, client_id=acled, scope=authenticated) → bearer token (24 h). Data: `GET https://acleddata.com/api/acled/read`.
- **Auth note**: the account was created via **Google SSO**; the OAuth *password* grant still works once a password is set on the account (password-reset flow). There is no separate API key in the new system.
- **Output**: `acled_events_2020_present.parquet` — 736,648 rows, **25/25 priority countries**, 73 MB.

### Schema (26 columns)
Full event-level record: `event_id_cnty, event_date, year, time_precision, disorder_type, event_type, sub_event_type, actor1, assoc_actor_1, actor2, assoc_actor_2, iso, country, admin1, admin2, admin3, location, latitude, longitude, geo_precision, source, source_scale, notes, fatalities, tags` + `priority_iso3` (added).

### Verified facts
- **The "iso" gotcha is real and present.** `iso` is the **ISO numeric** code (int64; 729 = Sudan, 4 = Afghanistan). We added `priority_iso3` (alpha-3) for joining. **Map numeric→alpha in Silver, or just use `priority_iso3`.**
- **lat/lon arrive as strings from the API; we cast to float64.** Native precision is 4 decimal places, preserved losslessly by float64 (verified ranges: lat −26.84→52.34, lon −92.19→126.54; **zero null coordinates**). H3 res-5 indexing happens downstream as planned.
- **`event_date` 2020-01-01 → 2025-05-22.** See the embargo quirk below.
- Spot-check (event count / fatalities_sum): Sudan 22,620 / 49,777 · Yemen 54,318 / 52,254 · **Myanmar 82,978 / 84,742** · Burkina Faso 10,407 / 28,043 · Haiti 9,475 / 11,910. Densest overall: **Ukraine 204,888**, Myanmar 82,978, Syria 69,408 (the high-attention contrast cases).

---

## Quirks worth knowing about

**⚠️ API account has a 12-month recency embargo.** The response field `data_query_restrictions.date_recency` = `{quantity: 12, unit: Months}`. The account returns **only events ≥12 months old** — today that ceiling is **2025-05-22**; a probe for events after it returns 0 rows. So the event/H3 path has **no data for the most recent ~12 months**. The HDX severity path is *not* embargoed (current to last month). This directly affects any "recent deterioration / current hotspot" use of the event-level path. Lifting it requires an elevated ACLED access tier (e.g. academic/special). **Resolve before relying on event-level recency.**

**ACLED's HDX XLSX are served with broken zip structure.** Verified byte-stable across downloads (not our network, not the sandbox proxy):
- *Most* files have a non-standard zip central directory that `openpyxl`/stdlib `zipfile` reject ("Bad magic number for central directory"). The Rust `calamine` engine reads them — so the script uses `engine="calamine"` (added dependency: **python-calamine**).
- *Chad, Colombia, CAR* additionally have broken central-directory **offsets** that defeat calamine too. Recovered by walking the intact *local* file headers top-down (`recover_by_local_walk`, the Python equivalent of `zip -FF`).
- **Colombia's `demonstration` file is genuinely damaged** (worksheet XML, not just offsets) and is unrecoverable. **COL therefore has only `political_violence` + `civilian_targeting`, not `demonstration`.** This is the single gap across both datasets.

**Multi-value / delimited fields (event path).** `assoc_actor_1`/`assoc_actor_2` are **semicolon-delimited** multi-value (~4% contain `;`). `disorder_type` can be combined (`"Political violence; Demonstrations"`, 1,414 rows). `tags` are key=value pairs (e.g. `crowd size=hundreds`), ~9% empty, rarely multi-valued in this subset. Split on `;` if these are needed.

**Precision flags (event path).** `time_precision`: 1 = exact day (94%), 2 = within a week/month, 3 = within the month/year (cast to int). `geo_precision`: 1 = precise location (55%), 2 = admin/territory centroid (42%), 3 = larger region (2%). **Down-weight or flag `geo_precision >= 2` before H3 hotspot inference** — those points are centroids, not real locations, and will pile onto admin centroids.

**Category semantics differ between paths.** HDX `civilian_targeting` is a *subset overlapping* political violence (a flag), not a disjoint type; summing the three HDX categories double-counts civilian-targeting events. In the event path the equivalent is the boolean `civilian_targeting` column (not requested here; derivable from `sub_event_type`). Don't treat the two paths' "events" totals as identical — they differ by the embargo window, category overlap, and zero-row inclusion (severity sums run ~10–15% above event-row counts, mostly the extra 12 months).

**No missing/stale countries.** All 25 priority datasets exist on HDX, all all-categories present and fresh (2026-05-20), all coverage starting ≤2018 so the 2020+ filter is clean for every country.

## Implications for downstream layers

- **`silver_acled_severity`** ← `acled_severity_admin2_month_2020_present.parquet`. Join to boundaries on `admin2_pcode`/`admin1_pcode`; key country on `priority_iso3`. Filter `events > 0` for most uses; keep zeros only for explicit time-series. Note COL has no demonstration rows.
- **`silver_acled_events`** ← `acled_events_2020_present.parquet`. H3 res-5 index on (`latitude`,`longitude`); key on `priority_iso3` (or map `iso` numeric→alpha). Carry `geo_precision`/`time_precision` into hotspot logic. **Treat the 12-month embargo as a hard temporal boundary** until access is upgraded.
- Both keyed cleanly on `(priority_iso3, …)`; the numeric-vs-alpha ISO mismatch is fully absorbed by `priority_iso3`.

## Open questions

- **API 12-month embargo** — is elevated ACLED access (academic/special tier) available to lift it? Without it, the event/H3 path can't power *recent* hotspots; only the admin2 severity path is current. This is a methodology-shaping constraint — flag to the team.
- **Colombia demonstrations** — accept the gap (HDX file corrupt), or backfill COL demonstrations from the event path (loses P-codes, and is embargoed past 2025-05)?
- **Bridging the two paths' recency** — option: derive admin2×month aggregates from the event path for cross-validation against HDX on the overlapping window (2020-01→2025-05); requires a documented event_type→category mapping (a methodology decision — not improvised here).
- **`civilian_targeting` double-count** — confirm the Silver layer treats HDX `civilian_targeting` as an overlapping flag, not an additive third category.
