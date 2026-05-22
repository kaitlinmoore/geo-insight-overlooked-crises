# Data profiling: OCHA-canonical starter datasets

> **Source of these findings.** Captured from a profiling session on
> 2026-05-22, run against the data files committed to the project at repo
> root (the challenge-provided / OCHA-canonical starter datasets, not the
> acquired comparators and enrichments which live in `./staging/`).
> Findings are verified observations against the files using pandas /
> openpyxl, marked clearly where facts were verified vs. sampled vs. left
> open. Per the scope carve-out in `claude.md`, this is profiling /
> analysis work: `STATE.md` and `DECISIONS.md` were **not** edited.
> Promote relevant pieces into `docs/data-catalog.md` and `docs/schemas.md`
> when those land; the methodology-impacting items belong in
> `docs/open-questions.md` for review.
>
> **Tooling note.** Pandas 3.0.2 + openpyxl + pyarrow against
> `/mnt/project/` (read-only mount of the project knowledge sync). No
> data was written back.

## Headline findings — read these first

1. **Multi-country flows are 31.5% of incoming-flow dollars but 5.7% of
   rows, and 99.1% of them carry no destPlan.** The methodology cascade
   (requirements-weighted primary, population-weighted fallback,
   `regional_unattributed` for no-info) needs revisiting because the
   primary leg almost never applies — there's no plan to read
   requirements off of. Population-weighted is effectively the default for
   ~30% of all incoming dollars.

2. **HNO 2025 vs HNO 2026 are wildly different shapes.** HNO 2025 is a
   long-format 318k-row file with subnational rows (admin1/2/3) and
   demographic disaggregation, all numeric fields stored as **strings**.
   HNO 2026 is a 134-row country×cluster table with proper numeric types,
   no subnational. They need two different Bronze loaders. Ethiopia has
   zero HNO data in either file.

3. **Subnational admin1 coverage in HNO 2025 is worse than the
   methodology assumes.** Several priority countries (SDN, YEM, HTI, VEN,
   NGA) have only admin2 rows, no admin1; BFA and COD have only
   country-level; ETH has nothing. Admin1 must be derived by p-code
   prefix rollup, not read directly.

4. **INFORM Severity schema changed in Sep 2020** when the product
   renamed from GCSI to INFORM Severity (per the glossary). 20 files use
   the old `GCSI` sheet; 69 files use `INFORM Severity - country`. The
   column shape (21 cols) is otherwise stable. Country coverage grew
   from ~70 in 2019 to ~95 in late 2024, then drifted down to ~70-80 in
   early 2026.

5. **FTS plan-type label changed in 2024**, from `Humanitarian response
   plan` (HRP) to `Humanitarian needs and response plan` (HNRP). 2026 is
   fully on the new label; 2023 is fully on the old. Silver needs to
   unify them.

6. **2026 funding for priority countries is in crisis.** Yemen 13%
   funded, Burkina Faso 14%, Venezuela 15%, Sudan 21%, Haiti 22%.
   Compared to 2024 funding rates, every priority country has dropped —
   this is the story the deck's "overlooked" framing is built on, and
   the data backs it directly.

7. **CERF Allocations and Contributions in this repo are actually CBPF
   data, not CERF.** Nine files = nine years (2018-2026) of
   Country-Based Pooled Fund allocations and donor contributions. This
   is the substrate for the optional CBPF Allocation View screen, not
   for UFE validation. The actual CERF UFE data lives in
   `staging/` from the acquisition session (see
   `docs/notes/acquisition_cerf_ufe.md`).

8. **Three INFORM Severity files in this dataset are byte-identical
   duplicates with a `_1` suffix** (Sep 2025, Feb 2026, Mar 2026). Other
   apparent duplicates (e.g., `202604informseverityapril2026.xlsx` vs
   `..._20261.xlsx`) are **not** dupes — they're different snapshots of
   the same release month. Bronze loader needs sha256-or-content dedupe,
   not filename dedupe.

---

## Dataset profiles

### FTS plan-level requirements + funding
**File:** `fts_requirements_funding_global.csv`
**Shape:** 3,836 rows × 12 columns. 887 unique plan codes across 112
country codes. Year range 1999-2031 (includes future-dated rows that
should be filtered to ≤ current year in Silver).

**Schema:** `countryCode, id, name, code, typeId, typeName, startDate,
endDate, year, requirements, funding, percentFunded`.

**Gotchas:**
- **2,577 rows (67%) have NULL `code`, `id`, `typeName`, etc.** These
  are `Not specified` rows — funding to a country in a given year that
  is not tied to any specific plan. Sample: AFG 2024 has an `HAFG24`
  row with the real plan numbers AND a NULL-code row with $115M of
  off-plan funding. Cannot drop these without losing real flow value.
  Methodology decision needed: do `Not specified` flows count toward
  `funding_gap_ratio` denominator? They don't have requirements to
  compare against.
- **`percentFunded` is computed by FTS, not derived from `requirements`
  and `funding` rounded to integer percent.** Use it directly; don't
  recompute (it'll be slightly off and that's the FTS canonical value).
- **`typeName` taxonomy is messy and changing.** Major values: Regional
  response plan (457), Humanitarian response plan (220, decreasing),
  Consolidated appeals process (152), Flash appeal (133), Other (126),
  Humanitarian needs and response plan (54, increasing — this is the
  new HRP label). Silver should unify HRP and HNRP into a single
  `country_response_plan` category for ranking purposes.

### FTS plan × country-cluster requirements + funding
**File:** `fts_requirements_funding_cluster_global.csv`
**Shape:** 8,030 rows × 12 cols, year 2000-2026.

**Gotchas:**
- **962 distinct raw cluster names** including duplicates by case
  (`Health` vs `HEALTH`), language variants (`Santé`, `Sécurité
  alimentaire`), and historical taxonomy drift. This file is
  *un-normalized* sector data.
- **`cluster` value `Not specified` (815 rows) and `Multiple
  clusters/sectors (shared)` (815 rows)** are the sector-level analog of
  multi-country flows — funding that landed in a plan but couldn't be
  attributed to a specific cluster. Must be preserved with provenance
  for the sector-decomposition methodology.

### FTS global cluster rollup
**File:** `fts_requirements_funding_globalcluster_global.csv`
**Shape:** 10,635 rows × 12 cols, year 2000-2026. **Only 24 cluster
names**, properly normalized to the IASC taxonomy.

**Verdict:** This is the *normalized* version of the country-cluster
file. The 962-name version is the raw FTS export; this one is the IASC
mapping. Use **globalcluster** for sector decomposition in the
ranking; use country-cluster only as forensics / source-of-truth.

### HRP plans metadata
**File:** `humanitarianresponseplans.csv`
**Shape:** 911 rows × 10 cols, year 2000-2026.

**Gotchas:**
- **Row 0 is a HXL tag row** (`#date+year+list`, `#country+code+list`,
  `#response+code` — HXL is a humanitarian markup convention).
  `skiprows=[0]` or HXL-aware loader required. The `code` column appears
  as `#response+code` in HXL row, which leaked into the codes-not-in-FTS
  bucket below.
- **Multi-country plans in `locations`**: pipe-delimited (`YEM | KEN |
  DJI | SOM | ETH | TZA`) — different delimiter than FTS (which uses
  commas). Need to normalize when joining or splitting.
- **`categories` field is dual-format**: some rows are clean
  (`Consolidated appeals process`, `Flash appeal`), some are pipe-laden
  HXL fragments (`cluster | en | Humanitarian response plan`). Likely
  metadata leakage. Investigate before trusting `categories` as a
  classifier.

**Plan code join check:** HRP ↔ FTS plan code overlap is 882 / 887 FTS
codes / 900 HRP codes. 5 FTS-only codes are all 2025-2026 plans not yet
added to the HRP metadata (FTS updates ahead of the plans table).
**Join key reliability: 99% clean.**

### HNO 2025 (subnational)
**File:** `hpc_hno_2025.csv`
**Shape:** 318,260 rows × 16 cols. 23 countries.

**Critical schema issue:** Every numeric column (`Population`, `In
Need`, `Targeted`, `Affected`, `Reached`) is loaded as **string** by
default. The CSV evidently has formatting (commas in thousands or
similar) that breaks auto-typing. Bronze loader needs explicit
`dtype={'Population': 'string', ...}` plus a parse-with-error-handling
pass. **Compare to HNO 2026 below where types are clean.**

**Row composition (non-exclusive counts because of cluster/category
fan-out):**
- 294,499 rows have country-level In Need (no admin1 pcode)
- 15,792 rows are admin1 (Admin 2 PCode NULL)
- 228,156 rows are admin2 (Admin 3 PCode NULL)
- 71,818 rows are admin3

**Admin1 coverage for priority countries — *worse than expected*:**

| ISO3 | Total rows | Unique admin1 codes | Adm1 rows | Adm2 rows |
|------|-----------:|--------------------:|----------:|----------:|
| SDN  | 22,901 | 0   | 0      | 22,763 |
| YEM  | 22,138 | 0   | 0      | 22,040 |
| MMR  | 27,351 | 18  | 1,611  | 0      |
| BFA  | 23,464 | 0   | 0      | 0      |
| HTI  | 13,225 | 0   | 0      | 13,132 |
| COL  | 515    | 33  | 488    | 0      |
| VEN  | 3,203  | 0   | 0      | 3,182  |
| COD  | 23,018 | 0   | 0      | 0      |
| NGA  | 14,442 | 0   | 0      | 14,168 |
| ETH  | **0**  | 0   | 0      | 0      |

The methodology promise of "admin1 globally, admin2 for deep dives"
needs operational refinement:
- **Five priority countries (SDN, YEM, HTI, VEN, NGA) have admin2 but
  no admin1 rows.** Admin1 must be **derived** by rolling up admin2
  rows on the admin1 pcode prefix.
- **MMR and COL have admin1 but not admin2.** Subnational deep dive
  works at admin1.
- **BFA and COD have only country-level data in HNO 2025.** No
  subnational analysis available; `data_sparsity_flag` carries the
  burden.
- **ETH has zero HNO 2025 data.** Drops out of subnational
  entirely; country-level analysis depends on what survives in 2026 or
  earlier years.

**Demographic-category fan-out:** The `Category` column carries
sub-population labels (Children, Elderly, Female, Male, IDP, Host
Communities, etc., plus combinations like `Children - Female`). The
country-level total is `Category = total`. For methodology v1, filter
to `Category == 'total'` to avoid double-counting.

**Description-field language drift:** Mixes English and French
(`Sécurité alimentaire`, `Santé`). Cluster code field (`PRO`, `FSC`,
`WSH`) is more reliable for sector identification than description.

### HNO 2026 (early-year, country-only)
**File:** `hpc_hno_2026.csv`
**Shape:** 134 rows × 10 cols. 20 countries. **No admin columns at
all.**

**Schema delta vs 2025:** Missing all six admin columns (`Admin 1
PCode/Name`, `Admin 2 PCode/Name`, `Admin 3 PCode/Name`). Otherwise
same column names. Dtypes are properly numeric (Population: float64, In
Need: float64, Targeted: int64) — unlike 2025's all-string columns.

**Interpretation:** This is the GHO (Global Humanitarian Overview) /
"Plan caseload" preview format released early in the cycle, before
subnational HNO is finalized. Look for the `Description == 'GHO
Estimates'` / `'Plan caseload'` / `'Final'` rows for the country PIN;
cluster-specific rows give sector-level PIN.

**Country coverage:** AFG, BFA, CAF, CMR, COD, COL, HTI, MLI, MMR,
MOZ, NER, NGA, SDN, SOM, SSD, SYR, TCD, UKR, VEN, YEM. Notably
**ETH is missing from 2026 too.**

**Bronze handling:** Two separate Bronze tables (`bronze_hno_2025`,
`bronze_hno_2026`) with different schemas, OR a unified Bronze table
with NULL admin columns for 2026 rows. The latter simplifies the
multi-year query patterns; the former preserves the source-fidelity
audit trail. Recommend unified, with a `_source_version` column.

### INFORM Severity time series
**Files:** 89 unique xlsx files (after de-duplicating `_1` byte-identical
copies). Date range: Jan 2019 → April 2026 (~85 months).

**Sheet schema split:**
- **Jan 2019 – Aug 2020 (20 files)**: sheet named `GCSI`, 20-22 columns.
- **Sep 2020 – Apr 2026 (69 files)**: sheet named `INFORM Severity -
  country`, **stable at 21 columns**.

The product was renamed from GCSI to INFORM Severity in Sep 2020 (per
glossary.md); same content. Bronze loader must dispatch on sheet name
or filename pattern.

**Header convention:** Row 1 carries a formula / title; row 2 has
column headers; row 3 has a `Weights` row that should be dropped; data
starts row 4. Use `header=1` and drop the first data row if its first
column equals `Weights`.

**Country coverage trajectory:**

| Period | Countries (range) |
|---|---|
| 2019 (GCSI) | 65–78 |
| 2020 (transition) | 67–80 |
| 2021–2022 | 70–86 |
| 2023 | 83–93 |
| **2024 (peak)** | 91–95 |
| 2025 | 80–91 (declining) |
| 2026 (through April) | 68–82 |

Coverage isn't stable — some countries drop in/out across months as
ACAPS adds or retires crisis monitoring. For `chronic_index`
(N=3-consecutive-years per the bonus-task decision), a country with
intermittent INFORM coverage will have gaps that need explicit
handling (forward-fill? mark as `data_sparsity_flag`? skip the
chronic-classification for that country?).

**"Mid-month" releases:** Two files in late 2025
(`mid-november-2025`, `mid-december-2025`) plus end-of-month equivalents.
ACAPS occasionally publishes a mid-month update for fast-moving crises.
Use the latest by release date per calendar month, not by filename
order.

**Filename quirk:** `20190304gcsidatabasebetaversionfebruary2020.xlsx`
has a date prefix from 2019 but says February 2020 — almost certainly a
misnamed file (released 2020-03-04 covering Feb 2020 data). The
`About` sheet inside the xlsx is the canonical release date; trust it
over the filename.

### COD Population (admin0, admin1, admin4)
**Files:**
- `cod_population_admin0.csv` — 6,722 rows, 139 countries, ref years 2001-2025
- `cod_population_admin1.csv` — 91,471 rows, 123 countries (16 fewer
  than admin0), 1,882 admin1 `T_TL` rows, ref years 2001-2025
- `cod_population_admin4.csv` — **only one country**, 17,465 rows, all
  ref year 2018

**Use admin0 and admin1 only.** admin4 covers exactly one country and
is essentially noise at the global ranking layer.

**Important:** These three files are a **subset of the
`cod-ps-global` HDX resource pulled separately during acquisition** —
the supplemental_cod findings note (`docs/notes/acquisition_supplemental_cod.md`)
covers the admin2 and admin3 pulls that complete the set. For
methodology v1, the relevant denominators are:
- Country-level severity_rate: `admin0` `T_TL` rows
- Admin1 severity_rate: `admin1` `T_TL` rows
- Admin2 severity_rate: `cod_population_admin2.csv` from staging
  (acquired); recall YEM, MMR, NGA have **zero admin2 coverage** per
  the supplemental_cod note, so they degrade to admin1 with
  `data_sparsity_flag`.

### CERF/CBPF Allocations and Contributions
**Files:** Nine `Allocations__*.csv` + nine `Contributions__*.csv`
files, one per year 2018-2026, with redundant UTC timestamps in the
filenames.

**This is CBPF data, not CERF.** The `PooledFund` column carries 34
country-fund names (Sudan Humanitarian Fund, DRC Pooled Fund, Yemen
Humanitarian Fund, etc., plus newer regional pooled funds with
`(RhPF-WCA)` / `(RhPF-LAC)` / `(AP-RHPF)` / `(ESAHF)` suffixes
introduced 2022+). The actual CERF UFE allocations are in `staging/`
from the dedicated acquisition session.

**Allocations schema:** `Year, PooledFund, AllocationType, Budget`.
697 total rows. `AllocationType` is `reserve` (487) or `standard`
(210) — CBPF's two allocation windows. **23 exact duplicates after
concat**; dedupe before use.

**Contributions schema:** `Year, Donor, Donor type, Paid, Pledged,
Total`. 2,132 rows, 1,843 unique. **289 duplicates** — appears to be
multiple line items per donor-year (split contributions or pledge
revisions). The contributions file has **no PooledFund column**, so
these are global CBPF contributions, not per-fund. Top donors in 2026:
USA $150M (paid), Belgium $10M, Germany $8M (pledged), Finland,
Denmark, UAE, UK, Ireland.

**Methodology relevance:** This is the **CBPF Allocation View
(PFM-primary, optional)** substrate from `docs/architecture.md`. Not
in the v1 ranking pipeline. For the optional 6th screen, the Bronze
tables `bronze_cbpf_allocations` and `bronze_cbpf_contributions` are
the right targets.

### FTS flow-level data
**Files:** `fts_incoming_funding_global.csv` (9,255 rows, $14.24B
2020-2026), `fts_outgoing_funding_global.csv` (4,080 rows),
`fts_internal_funding_global.csv` (1,378 rows, 2024-2026 only).

**Gotcha — multi-country delimiter:** `destLocations` uses **commas**
between ISO3 codes, not pipes or semicolons. Sample:
`ABW,ARG,BOL,BRA,CHL,COL,CRI,CUB,CUW,DOM,ECU,GUY,MEX,PAN,PER,PRY,TTO,URY`
(18 countries on one flow). This is different from
`humanitarianresponseplans.csv` (pipes) — every loader needs to handle
its source's specific delimiter.

**Multi-country flow distribution (incoming, all years):**
- 8,727 single-country flows (94.3% of rows; **68.5% of dollars**)
- 528 multi-country flows (5.7% of rows; **31.5% of dollars =
  $4.48B**)

**99.1% of multi-country flows carry no `destPlan`.** Only 5 out of 528
have a plan attached. This is the core finding for the allocation
cascade:

The 2026-05-21 decision says "requirements-weighted primary,
population-weighted fallback, regional_unattributed for no-info."
**The data shows the primary leg almost never fires** — without a
destPlan there's no plan whose cluster requirements we can read. The
operating reality is:
- Single-country flows → direct attribution, no cascade needed (68.5% $)
- Multi-country flows w/ destPlan + plan requirements → requirements-weighted (<0.1% $)
- Multi-country flows w/o destPlan → population-weighted (the vast majority of multi-country $)
- Genuinely un-allocable → `regional_unattributed`

The 2026 multi-country flow total ($4.18B) is anomalously large
relative to all prior years combined ($299M, 2020-2025). Worth a
deeper look — likely a small number of mega-flows in early 2026
parked at regional level pending disaggregation. **Open question for
Silver design: should we delay attributing very recent multi-country
flows until they break down further?**

**Status field:** `commitment` (5,477) / `paid` (3,602) / `pledge`
(176). Methodology choice: `gap_ratio` numerator typically uses paid +
committed, excluding pledges (which are non-binding).

---

## Cross-cutting findings

### Naming and delimiter inconsistencies
| Source | Multi-country delimiter | Notes |
|---|---|---|
| `fts_incoming_funding_global.csv` (`destLocations`) | comma | 18-country flows seen |
| `humanitarianresponseplans.csv` (`locations`) | pipe with spaces (` \| `) | Regional plans |
| HXL convention | None — HXL tags use `+` | Row 0 of HRP file |
| FTS plan-type label | n/a | Renamed 2024: HRP → HNRP |
| HNO Cluster column | n/a | Coded (`PRO`, `FSC`) not natural-language |
| Population_group code | n/a | `T_TL` = total all-ages |

### Numeric type discipline
- HNO 2025: all numerics stored as strings (likely thousand-comma formatting)
- HNO 2026: numerics clean
- FTS files: numerics clean
- COD population: numerics clean
- INFORM Severity (xlsx): inspect after header normalization

This isn't catastrophic, just means HNO 2025 needs explicit casting
with error logging in Bronze.

### Future-dated and "Not specified" rows in FTS
- 2027-2031 rows exist in `fts_requirements_funding_global.csv`,
  largely from multi-year plan codes (RHO regional rolling plans).
  Filter to `year <= current_year` at Silver to avoid double-counting
  future intent.
- `Not specified` plan rows (NULL `code`) carry real funding dollars —
  decision needed on whether these contribute to the `funding_gap_ratio`
  denominator (no `requirements` to compare against) or only to the
  numerator (funding received not on a specific plan).

### Sector taxonomy: prefer `globalcluster` over `cluster`
962 raw cluster names vs 24 normalized IASC clusters. Use the
normalized rollup file for sector decomposition. Save the raw file for
the optional sector-imbalance audit on the Methodology screen.

### INFORM Severity dedupe pattern
Six pairs that *look* like duplicates by name (e.g.,
`202604informseverityapril2026.xlsx` vs `..._20261.xlsx`) — but only
three pairs are byte-identical. The others are genuine re-releases of
the same month (sometimes mid-month vs end-of-month, sometimes a
correction). Bronze should sha256 or row-count to dedupe, not match
filename patterns.

---

## Open questions surfaced or sharpened

For `docs/open-questions.md` integration:

**For Mary Keller / OCHA:**
- Confirm interpretation of `Not specified` plan rows in FTS
  requirements_funding — should off-plan funding count in the
  `funding_gap_ratio` numerator? Denominator?
- For multi-country flows with no destPlan, is OCHA's own attribution
  practice requirements-weighted (where requirements exist) or
  population-weighted by default? Want to align with institutional
  convention if there is one.
- The CERF `tableName` P / M question (already on the watch list) is
  unaffected by this profiling — the CBPF Allocations file in
  /mnt/project/ does not have a `tableName` field. The P / M values
  are in the staging-only CERF UFE data.

**For Dr. Kurland / GIS methodology:**
- Admin1 derivation by p-code prefix from admin2 rows — confirm the
  p-code convention is stable enough across countries (most are
  `<ISO3><admin1_num>` per OCHA) that simple `LEFT(pcode, n)` is
  reliable, vs. needing a lookup table.

**Methodology-side (for this chat / synthesis successor):**
- **Multi-country flow cascade refinement.** Requirements-weighted is
  effectively never available; the operating cascade is single-country
  direct → population-weighted multi-country → unattributed. Update
  `docs/methodology.md` to reflect the operating reality and rename the
  primary/fallback labels.
- **Mega-flow handling for 2026.** $4.18B in multi-country flows
  parked early in the year is anomalously large. Does the methodology
  want a `pending_attribution` flag for very-recent un-disaggregated
  flows, separate from `regional_unattributed`?
- **HNO admin1 derivation policy.** For SDN, YEM, HTI, VEN, NGA (admin2
  rows only), derive admin1 by pcode prefix rollup. Document this in
  methodology.md so the Silver behavior is auditable.
- **Ethiopia exclusion.** ETH has zero HNO 2025/2026 data despite being
  on the priority list. Either source ETH PIN from another file (older
  HNO year? UNHCR? IPC?) or drop from the demo until 2026 data lands.

**Data-quality flags to carry through Silver:**
- VEN population reference year 2011 (15 years stale) — surface as low-confidence
- ETH absent from HNO 2025 and 2026
- Countries with admin2-but-no-admin1 in HNO 2025 → flag `admin1_derived_from_admin2_rollup`
- BFA, COD with country-only HNO 2025 → flag `no_subnational_hno`

---

## Recommended next steps

1. **Schemas.md ingestion of these findings.** The Claude Code session
   currently writing `docs/schemas.md` should know about: HNO 2025
   string-typed numerics, HNO 2026 missing admin columns, FTS delimiter
   conventions, INFORM Severity sheet-split, the 962-vs-24 cluster
   taxonomy choice, and the CBPF Allocations year-per-file pattern.
   Surface this doc to that session.

2. **Methodology refinement on the multi-country cascade.** This
   probably wants a brief synthesis-style decision discussion before
   anyone writes Silver code that allocates flows. Recommend a short
   `DECISIONS.md` entry once we've talked it through.

3. **Bronze loader sketches.** Five distinct loader patterns are
   needed: (a) FTS CSV family, (b) HNO 2025 long-format with
   string-to-numeric casting, (c) HNO 2026 country×cluster wide, (d)
   HRP plans with HXL row skip, (e) INFORM Severity xlsx with
   GCSI/INFORM dispatch + Weights-row drop. CBPF Allocations and
   Contributions are simpler — straight CSV concat with dedupe.

4. **Sanity-check the priority-country gap-ratio story** before any
   demo screenshots. The 2026 funding-percent table (Yemen 13%,
   Burkina 14%, Venezuela 15%, Sudan 21%, Haiti 22%) is striking and
   real per FTS — these are the numbers that will land in slide 5 if
   we choose them. Worth confirming the YTD nature of these (a
   mid-year snapshot understates final-year funding) so we don't
   misrepresent.

5. **Don't promote profiling artifacts into Bronze loaders yet.**
   Profiling is research; the Bronze loaders happen after the
   permission grant lands. This doc is reference material for whoever
   writes them.

---

## What this profiling did NOT cover

- **CERF UFE data** (in `staging/` per the acquisition session, not in
  `/mnt/project/`). Profiled by the acquisition session; see
  `docs/notes/acquisition_cerf_ufe.md`.
- **fieldmaps boundaries GeoParquet** (in `staging/`). See
  `docs/notes/acquisition_fieldmaps.md`.
- **ACLED, NRC, ECHO FCA, HDX Signals** — all in `staging/`, covered in
  their respective acquisition notes.
- **Deep INFORM Severity column-by-column profile.** I verified sheet
  names, column counts, and country counts across the time series, but
  did not enumerate the 21 columns' content distributions. That's a
  follow-up before the chronic_index Gold computation.
- **HRP `categories` field cleaning.** Flagged the dual-format issue
  but did not enumerate the full taxonomy.
- **FTS internal vs outgoing flow semantics.** Schema-only check; no
  reconciliation between incoming/outgoing/internal totals.
- **Validation of the `revisedRequirements` vs `origRequirements`
  delta** in the HRP plans file. Likely useful for the chronic_index
  (revisions = sign of escalation) but not profiled here.
