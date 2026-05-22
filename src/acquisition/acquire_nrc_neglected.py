"""Compile NRC "World's Most Neglected Displacement Crises" annual top-10 lists.

Layer-2 validation comparator for the Geo-Insight project (top-N overlap analysis,
not training labels). Completeness over precision.

The ranked lists below were extracted manually from NRC's canonical per-year
pages/reports (see SOURCE_URLS). NRC labels each edition by its DATA YEAR and
publishes it the following June (e.g. the "2024" list was published June 2025).
The series began with the 2016 data year; no 2015 edition exists, and the 2025
edition is not published yet (due ~June 2026).

Country names are mapped to ISO3 with pycountry. Names that do not resolve via a
direct pycountry lookup are routed through ALIASES and flagged in the run report.

Output: ./staging/nrc_most_neglected_lists.csv
Schema: year, rank, iso3, country_name, source_url
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pycountry

# --- Canonical NRC source per data year ------------------------------------
SOURCE_URLS = {
    2016: "https://www.nrc.no/perspectives/2016/the-worlds-most-neglected-displacement-crises-2016",
    2017: "https://www.nrc.no/news/2018/june/democratic-republic-of-the-congo-tops-neglected-crises-list/",
    2018: "https://www.nrc.no/shorthand/fr/the-worlds-most-neglected-displacement-crises/index.html",
    2019: "https://www.nrc.no/shorthand/fr/the-worlds-most-neglected-displacement-crises-in-2019/index.html",
    2020: "https://www.nrc.no/resources/reports/the-worlds-most-neglected-displacement-crises-in-2020/",
    2021: "https://www.nrc.no/resources/reports/the-worlds-most-neglected-displacement-crises-in-2021",
    2022: "https://www.nrc.no/feature/2023/the-worlds-most-neglected-displacement-crises-in-2022",
    2023: "https://www.nrc.no/resources/reports/the-worlds-most-neglected-displacement-crises-in-2023",
    2024: "https://www.nrc.no/feature/2025/the-worlds-most-neglected-displacement-crises-in-2024",
}

# --- Ranked top-10 lists (index 0 == rank 1) -------------------------------
LISTS: dict[int, list[str]] = {
    2016: ["Central African Republic", "Democratic Republic of the Congo", "Sudan",
           "South Sudan", "Nigeria", "Yemen", "Palestine", "Ukraine", "Myanmar", "Somalia"],
    2017: ["Democratic Republic of the Congo", "South Sudan", "Central African Republic",
           "Burundi", "Ethiopia", "Palestine", "Myanmar", "Yemen", "Venezuela", "Nigeria"],
    2018: ["Cameroon", "Democratic Republic of the Congo", "Central African Republic",
           "Burundi", "Ukraine", "Venezuela", "Mali", "Libya", "Ethiopia", "Palestine"],
    2019: ["Cameroon", "Democratic Republic of the Congo", "Burkina Faso", "Burundi",
           "Venezuela", "Mali", "South Sudan", "Nigeria", "Central African Republic", "Niger"],
    2020: ["Democratic Republic of the Congo", "Cameroon", "Burundi", "Venezuela",
           "Honduras", "Nigeria", "Burkina Faso", "Ethiopia", "Central African Republic", "Mali"],
    2021: ["Democratic Republic of the Congo", "Burkina Faso", "Cameroon", "South Sudan",
           "Chad", "Mali", "Sudan", "Nigeria", "Burundi", "Ethiopia"],
    2022: ["Burkina Faso", "Democratic Republic of the Congo", "Colombia", "Sudan",
           "Venezuela", "Burundi", "Cameroon", "Mali", "El Salvador", "Ethiopia"],
    2023: ["Burkina Faso", "Cameroon", "Democratic Republic of the Congo", "Mali",
           "Niger", "Honduras", "South Sudan", "Central African Republic", "Chad", "Sudan"],
    2024: ["Cameroon", "Ethiopia", "Mozambique", "Burkina Faso", "Mali",
           "Uganda", "Iran", "Democratic Republic of the Congo", "Honduras", "Somalia"],
}

# --- Name -> ISO3 aliases for entries that do not resolve via direct lookup --
# Each carries a note so the run report can flag why manual help was needed.
ALIASES: dict[str, tuple[str, str]] = {
    "Democratic Republic of the Congo": ("COD", "common name; pycountry official is 'Congo, The Democratic Republic of the'"),
    "Palestine": ("PSE", "pycountry official is 'Palestine, State of'; politically contested entity"),
    "Iran": ("IRN", "pycountry official is 'Iran, Islamic Republic of'"),
    "Venezuela": ("VEN", "pycountry official is 'Venezuela, Bolivarian Republic of'"),
    "Bolivia": ("BOL", "pycountry official is 'Bolivia, Plurinational State of'"),
}


def resolve_iso3(name: str) -> tuple[str | None, str]:
    """Return (iso3, flag_note). flag_note == '' means a clean direct match."""
    if name in ALIASES:
        iso3, note = ALIASES[name]
        return iso3, f"alias-mapped ({note})"
    try:
        match = pycountry.countries.lookup(name)
        return match.alpha_3, ""
    except LookupError:
        pass
    try:
        results = pycountry.countries.search_fuzzy(name)
        if results:
            return results[0].alpha_3, f"fuzzy-matched to '{results[0].name}' — VERIFY"
    except LookupError:
        pass
    return None, "UNRESOLVED — no pycountry match"


def main() -> int:
    out_path = Path(__file__).resolve().parents[2] / "staging" / "nrc_most_neglected_lists.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    flags = []
    for year in sorted(LISTS):
        for rank, country in enumerate(LISTS[year], start=1):
            iso3, note = resolve_iso3(country)
            rows.append((year, rank, iso3 or "", country, SOURCE_URLS[year]))
            if note:
                flags.append((year, rank, country, iso3, note))

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["year", "rank", "iso3", "country_name", "source_url"])
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows ({len(LISTS)} years x 10) -> {out_path}")
    print(f"Years covered: {min(LISTS)}-{max(LISTS)}")
    print("Missing years: 2015 (series not yet started), 2025 (not published until ~June 2026)")
    print()
    if flags:
        print(f"MAPPING FLAGS ({len(flags)}):")
        for year, rank, country, iso3, note in flags:
            print(f"  {year} #{rank} {country!r} -> {iso3}: {note}")
    else:
        print("No mapping flags: all names resolved by direct pycountry lookup.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
