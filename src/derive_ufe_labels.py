"""Derive UFE (Underfunded Emergencies) country-year-round labels from CERF allocations.

Source: HDX dataset "CERF Allocations" (slug: cerf-allocations).
  https://data.humdata.org/dataset/cerf-allocations
  Publisher: OCHA Central Emergency Response Fund (CERF).
  License: CC BY-IGO.

Schema of the raw CSV (verified 2026-05-21):
  agencyName, continentName, countryCode, countryName, dateUSGSignature,
  emergencyTypeName, projectCode, projectID, projectTitle, regionName,
  tableName, totalAmountApproved, windowFullName, year,
  projectsectors, projectclusters, projectgroupings, projectcapcodes

The CERF "window" — i.e. the funding stream that distinguishes UFE from
Rapid Response — is encoded in column **`windowFullName`**. Verified
distinct values across the full 2006-2026 history (8511 rows):
  - 'Rapid Response'           (5508 rows)  — sudden-onset / RR
  - 'Underfunded Emergencies'  (3003 rows)  — UFE  ← what we want

No NULLs, no other values, no synonyms. `tableName` ('P'/'M') is an
internal CERF categorical that does NOT distinguish UFE from RR.

There is no explicit "round" column in the raw data. CERF UFE
allocations are made in two rounds per calendar year. We derive
the round from `dateUSGSignature` (USG = Under-Secretary-General):
  - month 1-6   → 'H1' (first-half round)
  - month 7-12  → 'H2' (second-half round)

A profile of UFE signature dates shows clean clustering with a gap
in July for most years; the H1/H2 split is a defensible default
and matches the user-facing convention ("2024 H1", "2025 H1", ...).

Output: ./staging/ufe_labels.csv with schema
  iso3, country_name, year, round, ufe_selected (bool), allocation_usd (float)
One row per (iso3, year, round) that received any UFE allocation.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

RAW = Path("staging/cerf_allocations_raw.csv")
OUT = Path("staging/ufe_labels.csv")

UFE = "Underfunded Emergencies"


def derive_round(date_iso: str) -> str:
    """Map an ISO date 'YYYY-MM-DD' to 'H1' (Jan-Jun) or 'H2' (Jul-Dec)."""
    month = int(date_iso[5:7])
    return "H1" if month <= 6 else "H2"


def main() -> None:
    if not RAW.exists():
        raise SystemExit(f"missing {RAW}; download first")

    # key: (iso3, country_name, year, round) -> sum of allocation_usd
    agg: dict[tuple[str, str, int, str], float] = defaultdict(float)
    rr_rows = 0
    ufe_rows = 0
    bad_iso = []
    bad_date = []

    with RAW.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            window = row["windowFullName"]
            if window == "Rapid Response":
                rr_rows += 1
                continue
            if window != UFE:
                # unknown window value — flag and skip
                bad_iso.append(("unknown_window", window))
                continue
            ufe_rows += 1
            iso3 = (row["countryCode"] or "").strip()
            cname = (row["countryName"] or "").strip()
            year_raw = row["year"]
            dsig = row["dateUSGSignature"]
            amt_raw = row["totalAmountApproved"]
            if len(iso3) != 3:
                bad_iso.append((iso3, cname))
                continue
            if not dsig or len(dsig) < 7:
                bad_date.append((iso3, year_raw))
                continue
            year = int(year_raw)
            rnd = derive_round(dsig)
            try:
                amt = float(amt_raw or 0)
            except ValueError:
                amt = 0.0
            agg[(iso3, cname, year, rnd)] += amt

    # write labels
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["iso3", "country_name", "year", "round",
                    "ufe_selected", "allocation_usd"])
        for (iso3, cname, year, rnd), amt in sorted(agg.items()):
            w.writerow([iso3, cname, year, rnd, "true", f"{amt:.2f}"])

    # summary
    print(f"input rows                : {rr_rows + ufe_rows}")
    print(f"  Rapid Response (skipped): {rr_rows}")
    print(f"  Underfunded Emergencies : {ufe_rows}")
    print(f"distinct (iso3,year,round): {len(agg)}")
    if bad_iso:
        print(f"FLAG bad iso3 / unknown window ({len(bad_iso)}):")
        for x in bad_iso[:5]:
            print("  ", x)
    if bad_date:
        print(f"FLAG missing dates ({len(bad_date)}):")
        for x in bad_date[:5]:
            print("  ", x)
    if not bad_iso and not bad_date:
        print("no schema anomalies detected")

    # countries selected in 2024 H1, 2024 H2, 2025 H1 (for spot-check)
    print("\n--- countries selected per recent round (derived) ---")
    for y, r in [(2024, "H1"), (2024, "H2"), (2025, "H1"), (2025, "H2"),
                 (2026, "H1")]:
        countries = sorted({k[1] for k in agg if k[2] == y and k[3] == r})
        if countries:
            print(f"{y} {r} ({len(countries)} countries): "
                  + ", ".join(countries))
        else:
            print(f"{y} {r}: (none in data)")


if __name__ == "__main__":
    main()
