"""Spot-check derived UFE labels against CERF's authoritative round announcements.

Reference lists are hand-curated from CERF press releases / OCHA news
(retrieved 2026-05-21). Each entry lists the countries that the
Emergency Relief Coordinator (ERC) officially selected for that
Underfunded Emergencies (UFE) round.

Sources:
  - 2024 UFE Round 1 ($100M, Feb 2024, 7 countries):
      https://cerf.un.org/news/story/directing-funding-where-it-needed-most-largest-allocation-cerf-underfunded-emergencies
      (confirmed via UN News / ReliefWeb summaries)
  - 2024 UFE Round 2 ($100M, Aug 2024, 10 countries):
      https://news.un.org/en/story/2024/08/1153766
  - 2025 UFE Round 1 ($110M, Mar 2025, 10 countries — 4 Tier-1 + 6 Tier-2):
      https://cerf.un.org/sites/default/files/resources/OCHA%20CERF%20UFE%202025-I%20Country%20Selection%20and%20Fund%20Allocations.pdf
      https://www.unocha.org/publications/report/sudan/un-releases-us110-million-shore-life-saving-assistance-neglected-humanitarian-crises

Discrepancy classes we expect to surface:
  - "missing_in_derived": country is in authoritative round R but absent
    from our derived H1/H2 bucket — almost always because its USG
    signature dates straddled the half-year boundary.
  - "extra_in_derived": country appears in our H2 bucket but the
    authoritative R2 announcement does NOT list it — usually because
    it was an R1 country whose late-signed projects landed in H2.

These are known limitations of the date-based round derivation
(dateUSGSignature is a project-level event, lagging the ERC's
round announcement by 2-6 months). They are documented in
derive_ufe_labels.py and surfaced here.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

LABELS = Path("staging/ufe_labels.csv")

# Authoritative round lists, by *country_name as it appears in the
# raw CERF CSV* (so the comparison is exact). Mapping notes:
#   "Sudan" in press releases       -> "Republic of the Sudan" in CSV
#   "Syria" in press releases       -> "Syrian Arab Republic" in CSV
#   "DRC" / "DR Congo"              -> "Democratic Republic of the Congo"
#   "CAR"                           -> "Central African Republic"
AUTHORITATIVE = {
    (2024, "H1"): {
        "Chad",
        "Democratic Republic of the Congo",
        "Honduras",
        "Lebanon",
        "Niger",
        "Republic of the Sudan",
        "Syrian Arab Republic",
    },
    (2024, "H2"): {
        "Burkina Faso",
        "Burundi",
        "Cameroon",
        "Ethiopia",
        "Haiti",
        "Malawi",
        "Mali",
        "Mozambique",
        "Myanmar",
        "Yemen",
    },
    (2025, "H1"): {
        "Afghanistan",
        "Central African Republic",
        "Chad",
        "Honduras",
        "Mauritania",
        "Niger",
        "Somalia",
        "Republic of the Sudan",
        "Venezuela",
        "Zambia",
    },
}


def main() -> None:
    if not LABELS.exists():
        raise SystemExit(f"missing {LABELS}; run derive_ufe_labels.py first")

    derived: dict[tuple[int, str], set[str]] = defaultdict(set)
    with LABELS.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            derived[(int(row["year"]), row["round"])].add(row["country_name"])

    total_missing = 0
    total_extra = 0
    print("=" * 70)
    print("UFE LABEL SPOT-CHECK vs CERF authoritative round announcements")
    print("=" * 70)
    for (y, r), auth in AUTHORITATIVE.items():
        got = derived.get((y, r), set())
        missing = sorted(auth - got)
        extra = sorted(got - auth)
        match = sorted(auth & got)
        total_missing += len(missing)
        total_extra += len(extra)
        print(f"\n{y} {r}  authoritative={len(auth)}  derived={len(got)}  "
              f"match={len(match)}")
        if missing:
            print(f"  MISSING IN DERIVED ({len(missing)}): "
                  + ", ".join(missing))
        if extra:
            print(f"  EXTRA IN DERIVED   ({len(extra)}): "
                  + ", ".join(extra))
        if not missing and not extra:
            print("  exact match")

    print("\n" + "=" * 70)
    print(f"summary: {total_missing} missing, {total_extra} extra across "
          f"{len(AUTHORITATIVE)} reference rounds")
    print("=" * 70)
    print("""
Interpretation:
  - "missing" entries are UFE-selected countries whose USG signature
    dates all fell outside the half-year of their announcement.
    Example: Syria 2024 R1 (announced Feb 2024) — all 5 project
    signatures occurred in August 2024, so they bucket into H2 by date.
  - "extra" H2 entries are R1 countries whose late-signed projects
    landed in H2. These would be filtered out by joining on an
    authoritative round-announcement table (TODO: build one from
    CERF press-release dates) rather than relying on signature date.
  - Recommended downstream usage: treat ufe_selected at year-grain
    (any round in year Y) as a high-precision label, and treat
    H1/H2 splits as approximate.
""")


if __name__ == "__main__":
    main()
