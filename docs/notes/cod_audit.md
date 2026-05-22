# COD audit: gaps vs. existing Geo-Insight data

> **Source of these findings.** Research-only session, 2026-05-21. No datasets were
> acquired beyond reading HDX CKAN metadata (JSON) to assess fit. Findings are based on
> the OCHA COD program documentation (IM Toolbox), the HDX CKAN API metadata for the
> relevant datasets, and the existing project context (`STATE.md`, `docs/methodology.md`,
> `docs/notes/acquisition_*.md`). Per the scope carve-out in `claude.md`, this is research
> findings work: `STATE.md` and `DECISIONS.md` were **not** edited. The human integrates
> recommendations into project docs.
>
> **Tooling note.** HDX blocks WebFetch (Cloudflare 403). All metadata here was read via
> `curl -A "<browser UA>" https://data.humdata.org/api/3/action/package_show?id=<slug>`.
> Reuse that pattern for any follow-up assessment.

## TL;DR — the headline corrections and recommendations

1. **COD-EM is not "Event Monitoring." It is "Edge-Matched" administrative boundaries.**
   There is no event-monitoring COD in the program. The audit category was based on a
   wrong expansion of the acronym. Edge-matched boundaries are exactly what our
   fieldmaps.io GeoParquet already is — so this category is **redundant, not a gap.**
   Independent event data is ACLED's job (already our primary signal).

2. **The single highest-value missing dataset is the Global P-code List**
   (`global-pcodes`) — a lightweight global CSV of every COD p-code with parent and
   reference date. It directly enables the HNO p-code validation the audit asked about.
   **Acquire.**

3. **We already own the COD-PS global bundle; we're just missing two files from it.**
   `cod_population_admin0/1/4.csv` are resources of the `cod-ps-global` dataset, which
   also ships `admin2.csv` and `admin3.csv`. Grabbing those two is a trivial top-up that
   unlocks the admin2 deep-dive denominator. **Acquire (same dataset).**

4. **The OCHA Countries & Territories Taxonomy feed** is a clean iso3 → official-name →
   region/sub-region/intermediate-region CSV — the natural substrate for
   `silver_country_dim`. **Acquire.**

5. **Per-country COD-AB geometry is redundant** with the fieldmaps global edge-matched
   product (fieldmaps *is* the OCHA edge-matched pipeline; see below). **Skip.**

| # | Category | Verdict | One-line reason |
|---|----------|---------|-----------------|
| 1 | COD-AB (Admin Boundaries) | **Skip** (geometry) | fieldmaps is the global edge-matched superset; per-country COD-AB adds little geometry we lack |
| 2 | COD-PS (Population) | **Acquire** (top-up) | admin2 + admin3 CSVs already exist in the bundle we partially pulled |
| 3 | COD-EM ("Event Monitoring") | **Skip** | acronym was wrong: COD-EM = Edge-Matched = what fieldmaps already gives us; events = ACLED |
| 4 | Global p-code authority list | **Acquire** | canonical p-code reference for validating HNO p-codes; tiny, monthly-refreshed |
| 5 | Reference data (country/region) | **Acquire** | OCHA C&T taxonomy is a ready-made `silver_country_dim` source |
| 6 | Other CODs | **Defer to v2** | populated-places COD could feed `geographic_isolation`; HDX Signals overlaps prompt 7 |

---

## 1. COD-AB — Administrative Boundaries

**(a) What's available.** OCHA publishes per-country COD-AB datasets (`cod-ab-<iso3>`),
each a bundle of the same geometry in four forms: a File Geodatabase, a shapefile zip, a
GeoJSON zip, and an **XLSX gazetteer** (p-code ↔ admin-name lookup, no geometry). All ten
priority countries (SDN, YEM, MMR, BFA, HTI, COL, VEN, COD, NGA, ETH) are present and
`cod-enhanced`, refreshed annually-to-biennially (last modified Jan–Apr 2026). Admin depth
varies by country (e.g. DRC, Ethiopia, Sudan reach admin3; Nigeria, Somalia admin2).

There is also a **global aggregation**, `cod-ab-global` ("Global – Subnational
Administrative Boundaries"): admin1–4 boundaries for **109 countries/territories**,
`cod-enhanced`, refreshed every 30 days, shipped in three geometry variants —
**Edge-Matched** (gaps/overlaps eliminated), **Original**, and **Extended** — plus a
metadata CSV.

**(b) Do we already have an equivalent/superset?** Yes. Our fieldmaps.io GeoParquet
("Global Edge-matched Subnational Boundaries (Humanitarian)", HDX slug
`edge-matched-boundaries-humanitarian-adm-0-4`, 43,064 polygons, all admin levels) is the
**edge-matched product itself**. fieldmaps.io is the pipeline that produces OCHA's
edge-matched boundaries; `cod-ab-global`'s Edge-Matched variant and our fieldmaps file are
the same lineage. Our single GeoParquet is a global superset of the per-country COD-AB
geometry, already in our preferred storage (GeoParquet, CRS84, `iso_3` join key).

**(c) Would acquisition improve ranking/validation/geo?** Marginally and only in narrow
cases:
- **admin3/admin4 for deep-dive countries.** The fieldmaps "all levels" parquet *should*
  already carry admin3 where it exists, but per the fieldmaps acquisition notes this was
  **not verified** (column schema and per-level row counts were never enumerated). The
  cheaper move is to *verify fieldmaps' admin3 coverage* (run `src/verify_boundaries.py`)
  before acquiring anything. If fieldmaps turns out to stop at admin2 for a country whose
  HNO has admin3 data, pull that one country's COD-AB — not the whole program.
- **Official XLSX gazetteers.** Useful as a clean p-code↔name lookup, but the Global
  P-code List (category 4) delivers that globally in one file, so the per-country
  gazetteers are redundant.
- **Disputed-territory edge cases.** COD-AB follows the same OCHA operational conventions
  fieldmaps tracks; no different handling expected. The open disputed-territory questions
  in the fieldmaps notes (Western Sahara, Kosovo, Crimea encoding) are best answered by
  *inspecting the fieldmaps file*, not by acquiring COD-AB.

**(d) Effort.** N/A for the skip. If a specific admin3 gap is confirmed, a single-country
COD-AB pull is ~15 min (download GeoJSON zip, extract the admin3 layer).

**Recommendation: SKIP** (verify fieldmaps admin3 coverage first; acquire a single country
only if a confirmed admin3 gap blocks a planned deep-dive).

---

## 2. COD-PS — Population Statistics

**(a) What's available.** Two tiers:
- **Per-country** (`cod-ps-<iso3>`): full age- and sex-disaggregated population, multiple
  admin levels, one tab per admin level, with p-codes, feature names, and reference year.
  Fields like `M_00_04`, `F_50_54`, `T_TL`. Depth varies (Ethiopia admin0–3, Burkina
  admin0–2, etc.).
- **Global rollup** (`cod-ps-global`, "Global – Subnational Population Statistics",
  `cod-standard`, annual refresh): five CSVs —
  `cod_population_admin0.csv` through `cod_population_admin4.csv` — each with subnational
  p-codes, admin names, source org, and reference dates.

**(b) Do we already have it?** Partially. The project's
`cod_population_admin0/1/4.csv` are **resources of `cod-ps-global`**. We pulled three of
the five CSVs and skipped `admin2.csv` and `admin3.csv` — the same dataset, same refresh,
same schema family.

**(c) Would acquisition improve the analysis?** Yes, specifically:
- **`severity_rate` at admin2.** Methodology defines `severity_rate = PIN / COD_PS_population`
  and the geographic plan ranks at "admin2 for deep dives." Without `cod_population_admin2.csv`
  there is no admin2 denominator, so deep-dive severity rates can't be computed. **This is a
  real, methodology-aligned gap.**
- **admin3** is lower priority — only a handful of countries have admin3 HNO data; pulling
  the file is free insurance for those.
- **Age/sex disaggregation** (only in the per-country COD-PS, not the global totals rollup):
  our v1 methodology uses population only as a denominator and an allocation weight, neither
  of which needs age/sex. So age/sex is **not** needed for v1. It would matter only if a
  demographic-vulnerability feature (e.g. child/elderly share as a need amplifier) is added —
  a v2 idea, not a v1 commitment.

**(d) Effort.** ~5 min — two additional CSV downloads from a dataset we already use. No new
schema work (identical structure to the admin0/1/4 files already staged).

**Recommendation: ACQUIRE** `cod_population_admin2.csv` and `cod_population_admin3.csv`
from `cod-ps-global`. **Defer** per-country age/sex COD-PS to v2.

---

## 3. COD-EM — (audited as "Event Monitoring"; actually "Edge-Matched")

**Correction first.** COD-EM stands for **Edge-Matched** administrative boundaries, not
Event Monitoring. Per OCHA's IM Toolbox: ITOS merges the lowest COD admin level with the UN
1:1m international boundary, clips/extends lines logically, and rebuilds clean-topology
polygons. "COD-EM datasets do not replace the authoritative COD-AB; however COD-EM datasets
may be preferred for cartographic purposes." Each COD-EM carries the COD-AB gazetteer
(names + p-codes), a shapefile zip, a geodatabase, and a live ITOS geoservice.

**(a)/(b) Availability & overlap.** This is the *same thing* as our fieldmaps global
edge-matched GeoParquet (see category 1). Per-country COD-EM is therefore redundant with
what we already hold.

**There is no "Event Monitoring" COD.** The COD program is boundaries (COD-AB), edge-matched
boundaries (COD-EM), and population (COD-PS), plus reference/thematic layers. Spatial-temporal
*event* data is out of program scope.

**(c) Event/spatial-temporal needs.** Already covered by **ACLED** (our primary independent
severity signal and the substrate for H3 hotspot detection — `subnational_hotspots`). The
only adjacent OCHA-adjacent product is **HDX Signals** (acute-deterioration alerts), which is
already on the acquisition backlog as optional prompt 7. Nothing in the COD program adds
event capability.

**(d) Effort.** N/A.

**Recommendation: SKIP.** No event-monitoring COD exists; edge-matched boundaries are
already in hand via fieldmaps; event coverage is ACLED's role.

---

## 4. Global p-code authority list

**(a) What's available.** `global-pcodes` ("Global P-code List") — a single CSV,
`global_pcodes.csv`, with columns: **3-digit ISO code, admin level, p-code, administrative
name, parent p-code, date**. `cod-enhanced`, refreshed every 30 days (last modified
2026-05-19), sourced from "the latest administrative boundary layers available on the OCHA
ArcGIS server." CC BY-IGO. Coverage: world (every country with COD boundaries; Indonesia
admin4 noted as excluded). Built from the same COD gazetteers as the boundaries.

**(b) Do we already have an equivalent?** No. We have boundary *geometry* (fieldmaps) whose
p-code columns and naming convention were **explicitly left unverified** in the fieldmaps
acquisition notes (open question: "do they match HNO's p-codes one-to-one?"). We have no
standalone canonical p-code reference table.

**(c) Would acquisition improve the analysis?** Yes — directly enables what the audit asked
for: **validate HNO p-codes against an official COD reference.** Concretely it supports:
- A Silver-layer validation check: every admin1/admin2 p-code appearing in HNO data should
  exist in `global_pcodes.csv` for that iso3+level; misses are flagged (typos, stale codes,
  non-standard codes).
- Resolving the fieldmaps↔HNO p-code join question without parsing 2 GB of geometry — join
  HNO to `global_pcodes` on (iso3, p-code) as a lightweight conformance gate, then trust the
  geometry join.
- A `parent p-code` column gives a free admin2→admin1→admin0 rollup hierarchy, useful for
  aggregating subnational results to country level.

**(d) Effort.** ~10–15 min. One small CSV (no auth, public download URL). Trivial to profile
(row counts per iso3/level, p-code format conformance). Lands as `bronze_global_pcodes` →
feeds a `silver_pcode_reference` lookup.

**Recommendation: ACQUIRE.** Highest value-to-effort ratio in this audit.

---

## 5. Reference data — country / region lookups for `silver_country_dim`

**(a) What's available.** OCHA maintains the **Countries & Territories Taxonomy** feed — a
published Google-Sheets CSV used by the official `hdx-python-country` library as its live
source. Per the library source, it provides per-country: ISO3, ISO2, official names
(multi-language: EN/FR/ES/RU/ZH/AR), **Region Name + Region Code, Sub-region Name + Code,
Intermediate Region Name + Code** (the UN M49 regional hierarchy).

Direct CSV (the library's `_ochaurl_default`):
`https://docs.google.com/spreadsheets/d/e/2PACX-1vSIIswgPn6oc_Ui3hCl2RTAdVZEw2sx4GjgqWFywrr8dt9R9B-p6Cs3jKeJigDguIbOjMxYtnloLlmI/pub?gid=1528390745&single=true&output=csv`

The `hdx-python-country` library also offers programmatic iso3↔region mapping, fuzzy
country-name matching ("Dem.", "Rep." handling), and admin-name matching across sources —
useful for reconciling the long-form country names noted in the CERF UFE findings
(`Republic of the Sudan`, `Syrian Arab Republic`, etc.).

**(b) Do we already have it?** No. `silver_country_dim` is referenced throughout the
methodology (join target for CERF, FTS allocation, region scoping in `rank_crises`) but no
canonical source is staged. The CERF UFE notes flag exactly the problem this solves:
"Always join on iso3, never on name" because of long-form name variants.

**(c) Would acquisition improve the analysis?** Yes:
- **Region scoping.** `rank_crises(scope=...)` filters by region; the taxonomy supplies the
  iso3→region mapping that makes regional rankings possible (Sahel, Horn of Africa framing
  in the cross-border view).
- **Name normalization.** A single authoritative iso3→official-name table resolves the
  CERF/FTS/HNO name-variant joins cleanly.
- **Cross-border / regional view** depends on a consistent region grouping; the M49
  sub-region / intermediate-region levels are a ready-made grouping.

**(d) Effort.** ~10 min for the CSV (one download), or add `hdx-python-country` as a
dependency (justified: it also gives FX rates and fuzzy admin-name matching we'll likely
want — but per `claude.md`'s "don't add dependencies casually," prefer the static CSV for
v1 unless the fuzzy matching is needed). Lands as `bronze_country_taxonomy` →
`silver_country_dim`.

**Recommendation: ACQUIRE** the C&T taxonomy CSV. Treat `hdx-python-country` as an optional
convenience, not a v1 requirement.

---

## 6. Other CODs / catalog items worth noting

- **Populated-places / settlements reference COD** — *defer to v2, but flag.* The
  `geographic_isolation` metric needs "distance from population centroids to the country's
  largest urban center." A settlements/populated-places layer with population (where OCHA or
  HDX publishes one per country) would supply the urban-center anchors. v1 can approximate
  with admin-unit centroids from fieldmaps; a proper settlements layer is a v2 refinement of
  the isolation component. **Defer to v2.**
- **`cod-ab-global` metadata CSV** — boundary version/reference dates per country. Minor;
  useful for data-freshness flags on subnational rankings. **Defer** (nice-to-have for the
  "data freshness indicators" honesty commitment, not blocking).
- **HDX Signals** — acute-deterioration alerts. Overlaps the acute side of our temporal
  classification and is already optional acquisition prompt 7. **Defer** (out of COD scope;
  tracked elsewhere).
- **UNHCR Global Admin1 / Admin2 divisions** — alternative global boundary/p-code lists.
  Redundant with fieldmaps + global-pcodes. **Skip.**
- **INFORM Severity** — already a methodology source (ACAPS, not a COD). No action here.

---

## Acquisition prompts (ready to drop into a Claude Code session)

> Each prompt is self-contained for a fresh session. All follow `claude.md` conventions:
> outputs to gitignored `./staging/`, one `verb_source` script, no raw data committed,
> findings reported in chat for the human to integrate.

### Prompt A — Global P-code List (category 4) — **priority**

```
Acquire the OCHA Global P-code List from HDX for the Geo-Insight project.

Source: HDX dataset slug `global-pcodes`. Direct CSV resource:
https://data.humdata.org/dataset/cb963915-d7d1-4ffa-90dc-31277e24406f/resource/71a63c2f-ba2f-4fef-8bf9-e4259dc41610/download/global_pcodes.csv
(If that resource URL has rotated, resolve it via the CKAN API:
`curl -A "Mozilla/5.0" "https://data.humdata.org/api/3/action/package_show?id=global-pcodes"`
and read the CSV resource's download_url. HDX blocks WebFetch; use curl with a browser UA.)

Expected schema: iso3 (3-digit ISO), admin level, p-code, administrative name,
parent p-code, date. License CC BY-IGO.

Write a `src/acquire_global_pcodes.py` script that downloads to
`./staging/global_pcodes_raw.csv`. Then profile and report in chat (do NOT edit
STATE.md/DECISIONS.md — this is a one-off acquisition per claude.md scope rules):
  1. Row count and distinct iso3 count.
  2. Row counts per admin level (0/1/2/3/4).
  3. Coverage for our 10 priority countries: SDN, YEM, MMR, BFA, HTI, COL, VEN,
     COD, NGA, ETH — confirm admin1 and admin2 p-codes exist for each.
  4. P-code format conformance: do admin1 p-codes follow `<ISO3><digits>`? Note
     any country whose convention deviates.
  5. Parent-p-code integrity: does every admin2 parent p-code exist as an admin1
     p-code row? Report orphan count.

Capture findings in docs/notes/ (e.g. acquisition_global_pcodes.md) for promotion
into docs/data-catalog.md and docs/schemas.md. This table becomes
`bronze_global_pcodes` → `silver_pcode_reference`, used to validate HNO p-codes.
```

### Prompt B — COD-PS admin2 + admin3 top-up (category 2)

```
Top up the COD-PS global population data for the Geo-Insight project. We already
have cod_population_admin0/1/4.csv in staging; we are missing admin2 and admin3
from the SAME dataset.

Source: HDX dataset slug `cod-ps-global` ("Global - Subnational Population
Statistics"). Resolve the resource download URLs for `cod_population_admin2.csv`
and `cod_population_admin3.csv` via the CKAN API (HDX blocks WebFetch; use curl
with a browser UA):
`curl -A "Mozilla/5.0" "https://data.humdata.org/api/3/action/package_show?id=cod-ps-global"`

Download both to `./staging/cod_population_admin2.csv` and
`./staging/cod_population_admin3.csv` (extend or mirror whatever script pulled the
admin0/1/4 files). Then report in chat (do NOT edit STATE.md/DECISIONS.md):
  1. Schema of admin2.csv — confirm it carries p-code, admin name, and a total
     population column (the `severity_rate` denominator).
  2. admin2 coverage for the 10 priority countries (SDN, YEM, MMR, BFA, HTI, COL,
     VEN, COD, NGA, ETH): which have admin2 population rows, which don't.
  3. Reference-year spread: how stale is the population data per country?
  4. Whether the admin2 p-codes match the Global P-code List admin2 p-codes
     (if Prompt A has been run) — join on (iso3, pcode), report mismatch rate.

Rationale: admin2 population is the denominator for subnational severity_rate in
the geographic deep-dive (docs/methodology.md, "Subnational ranking"). Without it,
admin2 severity rates can't be computed.
```

### Prompt C — OCHA Countries & Territories taxonomy (category 5)

```
Acquire the OCHA Countries & Territories Taxonomy reference table for the
Geo-Insight project, to become the substrate for silver_country_dim.

Source: the OCHA C&T taxonomy feed used by the official hdx-python-country library:
https://docs.google.com/spreadsheets/d/e/2PACX-1vSIIswgPn6oc_Ui3hCl2RTAdVZEw2sx4GjgqWFywrr8dt9R9B-p6Cs3jKeJigDguIbOjMxYtnloLlmI/pub?gid=1528390745&single=true&output=csv

Write `src/acquire_country_taxonomy.py` to download to
`./staging/country_taxonomy_raw.csv`. Then report in chat (do NOT edit
STATE.md/DECISIONS.md):
  1. Full column inventory. Confirm presence of: ISO3, ISO2, an English official
     name, Region Name + Region Code, Sub-region Name + Code, Intermediate Region
     Name + Code.
  2. Row count and whether it covers all UN member states + territories.
  3. The region/sub-region values for our 10 priority countries — confirm they
     give a usable grouping for the `rank_crises(scope=...)` regional filter and
     the cross-border view (Sahel, Horn of Africa, etc.).
  4. Whether the official names reconcile the long-form CERF names (e.g. does
     SDN map to a name that the CERF "Republic of the Sudan" / FTS variants can be
     normalized against via iso3).

This lands as `bronze_country_taxonomy` → `silver_country_dim`. Do NOT add
hdx-python-country as a dependency for v1 unless fuzzy name-matching proves
necessary (per claude.md "don't add dependencies casually") — the static CSV is
sufficient.
```

---

## What this audit did NOT do (time-box / scope honesty)

- **Did not download or profile any dataset.** All findings are from HDX CKAN metadata +
  OCHA program docs. Row-level claims (e.g. exact admin2 coverage per country) are deferred
  to the acquisition prompts above.
- **Did not verify fieldmaps' actual admin3 coverage.** The category-1 "skip" assumes
  fieldmaps' all-levels parquet includes admin3 where it exists; the fieldmaps acquisition
  notes flag this as unverified. Running `src/verify_boundaries.py` to enumerate per-level
  row counts would confirm the skip is safe and is the prerequisite check before concluding
  no admin3 COD-AB pull is needed.
- **Did not enumerate the full COD thematic-reference catalog** (hydrology, transport,
  health facilities, etc.). None appeared relevant to overlooked-crisis ranking on a first
  pass; the one borderline case (populated places for `geographic_isolation`) is flagged in
  category 6 as a v2 candidate.
