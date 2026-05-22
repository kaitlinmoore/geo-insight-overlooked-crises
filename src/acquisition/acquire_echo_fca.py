"""Compile the DG ECHO Forgotten Crises Assessment (FCA) lists, 2015-2026.

ECHO FCA is a Layer 2 validation comparator (top-N overlap analysis) for the
Geo-Insight overlooked-crises ranking. This script does NOT silently scrape: the
crisis lists below were extracted by hand from the authoritative ECHO sources
(PDF annexes and the official forgotten-crises web page / Wayback snapshots),
each tagged with its exact source URL. The script's job is to (1) hold that
extracted data with full provenance, (2) validate every ISO3 with pycountry and
flag anything unmappable, and (3) write ./staging/echo_fca_lists.csv.

Run:  python src/acquisition/acquire_echo_fca.py

Notes on the source material (see docs/notes/acquisition_echo_fca.md):
  * ECHO publishes ONE undifferentiated list each cycle. There is no
    "fully forgotten" vs "partially forgotten" split in any 2015-2026 source,
    so `forgotten_category` is "forgotten" for every row.
  * The FCA is a biennial-labelled exercise. fca_2014_2015 ("FCA 2014"),
    ggopha_2017 ("FCA 2016-2017") and ggopha_2020 ("FCA 2019-2020") each name
    two operative years; their lists are emitted under BOTH named years so the
    comparator can be joined per (iso3, year). Identical source_url across the
    two years makes the shared-assessment relationship transparent.
  * Regional/multi-country entries that name their members are expanded to one
    row per member. Entries that do NOT name members (e.g. "Multiple crises in
    Central America", 2024) are emitted with a blank iso3 and flagged.
  * Gaps: 2018 and 2025 lists could not be located (no standalone GGOPHA doc
    archived; the web page skipped from the 2024 list straight to 2026).
"""

import csv
import os

import pycountry

STAGING = os.path.join(os.path.dirname(__file__), "..", "..", "staging")
OUT = os.path.normpath(os.path.join(STAGING, "echo_fca_lists.csv"))

# --- Source URLs (Wayback "id_" raw captures where the live URL has moved) ---
SRC_2015 = "https://web.archive.org/web/20141223015209/http://ec.europa.eu/echo/files/policies/strategy/fca_2014_2015.pdf"
SRC_1617 = "https://web.archive.org/web/20200821142555/https://ec.europa.eu/echo/sites/echo-site/files/ggopha_2017.pdf"
SRC_1920 = "https://web.archive.org/web/20200821142425/https://ec.europa.eu/echo/sites/echo-site/files/1_en_ggopha_2020.pdf"
SRC_2021 = "https://web.archive.org/web/20220216122402/https://ec.europa.eu/echo/what/humanitarian-aid/needs-assessment/forgotten-crises_en"
SRC_2223 = "https://web.archive.org/web/20230422074556/https://civil-protection-humanitarian-aid.ec.europa.eu/what/humanitarian-aid/needs-assessment/forgotten-crises_en"
SRC_2024 = "https://web.archive.org/web/20240819003618/https://civil-protection-humanitarian-aid.ec.europa.eu/what/humanitarian-aid/needs-assessment/forgotten-crises_en"
SRC_2026 = "https://civil-protection-humanitarian-aid.ec.europa.eu/what/humanitarian-aid/needs-assessment/forgotten-crises_en"

# Each record: (iso3 or "", country_name, crisis_name)
# ISO3 in the PDF-table years (2015/2017/2020) is taken verbatim from the source.

# FCA 2014 -> operative 2015. Source: fca_2014_2015.pdf (ISO3 in source).
LIST_2015 = [
    ("DZA", "Algeria", "Sahrawi Refugee Crisis"),
    ("BGD", "Bangladesh", "Rohingya refugee crisis and Chittagong Hill Tracts"),
    ("CMR", "Cameroon", ""),
    ("TCD", "Chad", ""),
    ("IND", "India", "Conflicts in Jammu and Kashmir, central India (Naxalite Insurgency) and the North East"),
    ("MMR", "Myanmar", "Kachin conflict and Rakhine crisis"),
    ("PAK", "Pakistan", ""),
    ("SDN", "Sudan", ""),
    ("YEM", "Yemen", ""),
    ("COL", "Colombia", "Colombia crisis - internal armed conflict; Colombian refugees in Ecuador and Venezuela"),
    ("ECU", "Ecuador", "Colombian refugees (Colombia crisis)"),
    ("VEN", "Venezuela", "Colombian refugees (Colombia crisis)"),
]

# FCA 2016-2017 -> operative 2016 AND 2017. Source: ggopha_2017 Annex III (ISO3 in source).
LIST_1617 = [
    ("PHL", "Philippines", "Mindanao Conflict"),
    ("CMR", "Cameroon", "CAR Crisis"),
    ("MLI", "Mali", "Northern Mali Conflict (Kidal, Gao & Tombouctou)"),
    ("BGD", "Bangladesh", "Rohingya Refugee Crisis (Cox Bazar), Chittagong Hill Tracts"),
    ("IND", "India", "Jammu & Kashmir, Naxal Insurgency, North East States insurgency"),
    ("MMR", "Myanmar", "Central/Northern Rakhine State, Kachin and (northern) Shan States"),
    ("DZA", "Algeria", "Sahrawi crisis"),
    ("SDN", "Sudan", "Darfur and the Two Areas (SKS/BNS), food insecurity, large-scale refugee crisis"),
    ("PAK", "Pakistan", "Conflict-affected population, food insecurity & undernutrition / natural disasters"),
    ("COL", "Colombia", "Armed Conflict"),
    ("TCD", "Chad", "Refugee crisis (Eastern and Southern Chad)"),
    ("YEM", "Yemen", "Conflict and displacement, pre-existing crises, refugees and migrants"),
]

# FCA 2019-2020 -> operative 2019 AND 2020. Source: ggopha_2020 Annex III (ISO3 in source).
# Regional groups carry the group crisis description. DPRK (PRK) was identified
# but explicitly NOT included in the list (footnote) -> excluded here.
LIST_1920 = [
    ("AFG", "Afghanistan", "Countrywide complex crisis; Afghan refugees/returnees (Iran); recurrent natural disasters incl. drought"),
    ("PAK", "Pakistan", "Drought/food insecurity & malnutrition; Afghan refugee crisis; internal conflict IDPs/returnees"),
    ("MMR", "Myanmar", "Central Rakhine; Kachin and Northern Shan States; Northern Rakhine"),
    ("PHL", "Philippines", "Mindanao Conflict"),
    ("DZA", "Algeria", "Sahrawi Refugee Crisis"),
    ("SDN", "Sudan", "Food and nutrition crises, internal conflict"),
    ("COL", "Colombia", "Internal armed conflict"),
    ("HTI", "Haiti", "Food and nutrition crisis"),
    ("UKR", "Ukraine", "Conflict"),
    # Rohingya Regional Crisis
    ("IND", "India", "Rohingya Regional Crisis"),
    ("IDN", "Indonesia", "Rohingya Regional Crisis"),
    ("BGD", "Bangladesh", "Rohingya Regional Crisis"),
    ("MYS", "Malaysia", "Rohingya Regional Crisis"),
    ("THA", "Thailand", "Rohingya Regional Crisis"),
    # Burundi regional - refugees crisis
    ("BDI", "Burundi", "Burundi regional - refugees crisis"),
    ("RWA", "Rwanda", "Burundi regional - refugees crisis"),
    ("TZA", "Tanzania", "Burundi regional - refugees crisis"),
    # Central African Republic Regional Crisis
    ("CMR", "Cameroon", "Central African Republic Regional Crisis"),
    ("CAF", "Central African Republic", "Central African Republic Regional Crisis"),
    ("TCD", "Chad", "Central African Republic Regional Crisis"),
    # Sahel - conflicts and violence
    ("BFA", "Burkina Faso", "Sahel - conflicts and violence"),
    ("MLI", "Mali", "Sahel - conflicts and violence"),
    ("MRT", "Mauritania", "Sahel - conflicts and violence"),
    ("NER", "Niger", "Sahel - conflicts and violence"),
    # Central America - food insecurity and violence
    ("SLV", "El Salvador", "Central America - food insecurity and violence"),
    ("GTM", "Guatemala", "Central America - food insecurity and violence"),
    ("HND", "Honduras", "Central America - food insecurity and violence"),
    ("MEX", "Mexico", "Central America - food insecurity and violence"),
    # Caribbean - Venezuelan and Haitian refugees crisis
    ("CUB", "Cuba", "Caribbean - Venezuelan and Haitian refugees crisis"),
    ("DMA", "Dominica", "Caribbean - Venezuelan and Haitian refugees crisis"),
    ("DOM", "Dominican Republic", "Caribbean - Venezuelan and Haitian refugees crisis"),
    ("GRD", "Grenada", "Caribbean - Venezuelan and Haitian refugees crisis"),
    # Source literally prints "GIN Guinea" here; near-certainly a typo for GUY
    # (Guyana) given the Caribbean Venezuelan-refugee context. Kept verbatim, flagged in notes.
    ("GIN", "Guinea", "Caribbean - Venezuelan and Haitian refugees crisis [source likely meant Guyana/GUY]"),
    ("JAM", "Jamaica", "Caribbean - Venezuelan and Haitian refugees crisis"),
    ("LCA", "Saint Lucia", "Caribbean - Venezuelan and Haitian refugees crisis"),
    ("VCT", "Saint Vincent and the Grenadines", "Caribbean - Venezuelan and Haitian refugees crisis"),
    ("TTO", "Trinidad and Tobago", "Caribbean - Venezuelan and Haitian refugees crisis"),
]

# Web page "In 2021". Source: SRC_2021.
LIST_2021 = [
    ("DZA", "Algeria", "Sahrawi crisis"),
    ("BDI", "Burundi", "Regional refugee crisis"),
    ("CMR", "Cameroon", "Conflict and violence in the North-West/South-West regions"),
    ("COD", "Democratic Republic of the Congo", "Complex crisis"),
    ("MDG", "Madagascar", "Drought"),
    ("SOM", "Somalia", "Complex crisis"),
    ("SSD", "South Sudan", "Complex crisis"),
    ("CAF", "Central African Republic", "Regional crisis (CAR, Cameroon, Chad)"),
    ("TCD", "Chad", "Regional crisis (CAR, Cameroon, Chad)"),
    ("BGD", "Bangladesh", "Rohingya regional crisis (Bangladesh/Myanmar)"),
    ("MMR", "Myanmar", "Conflict and displacement in Kachin and Northern Shan States; Rohingya regional crisis"),
    ("PAK", "Pakistan", "Food crisis"),
    ("PHL", "Philippines", "Armed conflict in Mindanao"),
    ("COL", "Colombia", "Internal armed conflict"),
    ("HTI", "Haiti", "Complex crisis"),
    ("SLV", "El Salvador", "Regional crisis - food insecurity and violence"),
    ("GTM", "Guatemala", "Regional crisis - food insecurity and violence"),
    ("HND", "Honduras", "Regional crisis - food insecurity and violence"),
    ("MEX", "Mexico", "Regional crisis - food insecurity and violence"),
    ("UKR", "Ukraine", "Conflict"),
]

# Web page "For 2022-2023" -> operative 2022 AND 2023. Source: SRC_2223.
LIST_2223 = [
    ("COD", "Democratic Republic of the Congo", "Complex crisis"),
    ("CMR", "Cameroon", "Complex crisis"),
    ("BDI", "Burundi", "Complex crisis"),
    ("SSD", "South Sudan", "Complex crisis"),
    ("SDN", "Sudan", "Violence in West Darfur; refugee crisis in Sudan"),
    ("CAF", "Central African Republic", "Complex crisis"),
    ("TCD", "Chad", "CAR refugees in Chad"),
    ("NGA", "Nigeria", "Banditry in Northwest Nigeria"),
    ("DZA", "Algeria", "Sahrawi crisis"),
    ("BGD", "Bangladesh", "Rohingya refugee crisis"),
    ("LBN", "Lebanon", "Socio-economic crisis"),
    ("ECU", "Ecuador", "Displacement of Venezuelans"),
    ("PER", "Peru", "Displacement of Venezuelans"),
    ("COL", "Colombia", "Complex crisis"),
]

# Web page "For 2024" (also confirmed by GGOPHA 2024 SWD_2023_354). Source: SRC_2024.
LIST_2024 = [
    ("COD", "Democratic Republic of the Congo", "Complex crisis"),
    ("UGA", "Uganda", "Displacement crisis"),
    ("BFA", "Burkina Faso", "Conflict"),
    ("CMR", "Cameroon", "Crisis in Northwest and Southwest provinces"),
    ("NGA", "Nigeria", "Banditry and intercommunity violence in Northwest Nigeria"),
    ("SSD", "South Sudan", "Complex crisis"),
    ("MLI", "Mali", "Complex crisis"),
    ("DZA", "Algeria", "Sahrawi crisis"),
    ("BGD", "Bangladesh", "Rohingya refugee crisis"),
    ("MMR", "Myanmar", "Complex crisis (including displacement crisis in the region)"),
    ("PHL", "Philippines", "Conflict - Mindanao"),
    ("IRQ", "Iraq", "Multiple crises"),
    ("LBN", "Lebanon", "Socio-economic crisis"),
    ("HTI", "Haiti", "Complex crisis"),
    ("", "Central America", "Multiple crises in Central America (members not named in source)"),
]

# Web page "For 2026" (beyond requested 2015-2025 range; included as current list). Source: SRC_2026.
LIST_2026 = [
    ("AFG", "Afghanistan", "Complex crisis in Afghanistan"),
    ("DZA", "Algeria", "Sahrawi refugees in Algeria"),
    ("BGD", "Bangladesh", "Rohingya refugee crisis"),
    ("BDI", "Burundi", "Complex crisis in Burundi"),
    ("CMR", "Cameroon", "Multiple crises in Cameroon"),
    ("CAF", "Central African Republic", "Complex crisis in CAR"),
    ("GTM", "Guatemala", "Complex crisis in CAM (Guatemala, El Salvador, Honduras)"),
    ("SLV", "El Salvador", "Complex crisis in CAM (Guatemala, El Salvador, Honduras)"),
    ("HND", "Honduras", "Complex crisis in CAM (Guatemala, El Salvador, Honduras)"),
    ("BFA", "Burkina Faso", "Complex crisis in Central Sahel (Mali, Niger, Burkina Faso)"),
    ("MLI", "Mali", "Complex crisis in Central Sahel (Mali, Niger, Burkina Faso)"),
    ("NER", "Niger", "Complex crisis in Central Sahel (Mali, Niger, Burkina Faso)"),
    ("COL", "Colombia", "Complex crisis in Colombia and Venezuela displacement"),
    ("HTI", "Haiti", "Complex crisis in Haiti"),
    ("IRQ", "Iraq", "Multiple crises (conflict and Syrian and Palestinian refugees)"),
    ("JOR", "Jordan", "Syrian refugees in Jordan"),
    ("LBY", "Libya", "Mixed migration flows in Libya"),
    ("MOZ", "Mozambique", "Cabo Delgado Islamist insurgency"),
    ("PHL", "Philippines", "Mindanao conflict"),
    ("SOM", "Somalia", "Complex crisis in Somalia"),
    ("SSD", "South Sudan", "Complex crisis in South Sudan"),
    ("UGA", "Uganda", "Refugee crisis - international displacement"),
    ("VEN", "Venezuela", "Venezuela complex crisis"),
    ("YEM", "Yemen", "Conflict in Yemen"),
]

# (years, records, source_url). Biennial assessments map to two years.
SOURCES = [
    ([2015], LIST_2015, SRC_2015),
    ([2016, 2017], LIST_1617, SRC_1617),
    ([2019, 2020], LIST_1920, SRC_1920),
    ([2021], LIST_2021, SRC_2021),
    ([2022, 2023], LIST_2223, SRC_2223),
    ([2024], LIST_2024, SRC_2024),
    ([2026], LIST_2026, SRC_2026),
]


def validate_iso3(iso3):
    """Return (ok, canonical_name). ok=False flags an unmappable code."""
    if not iso3:
        return False, None
    rec = pycountry.countries.get(alpha_3=iso3)
    return (rec is not None), (rec.name if rec else None)


def main():
    rows = []
    flags = []
    for years, records, url in SOURCES:
        for year in years:
            seen = set()  # dedupe by iso3 within a year (regional members can repeat)
            for iso3, country, crisis in records:
                key = iso3 or country  # blank-iso3 regional rows keyed on name
                if key in seen:
                    continue
                seen.add(key)
                ok, canonical = validate_iso3(iso3)
                if iso3 and not ok:
                    flags.append((year, iso3, country, "ISO3 not recognised by pycountry"))
                if not iso3:
                    flags.append((year, "", country, "Multi-country/regional - no single ISO3"))
                rows.append({
                    "year": year,
                    "iso3": iso3,
                    "country_name": country,
                    "crisis_name": crisis,
                    "forgotten_category": "forgotten",
                    "source_url": url,
                })

    rows.sort(key=lambda r: (r["year"], r["iso3"] or "zzz", r["country_name"]))
    os.makedirs(STAGING, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "year", "iso3", "country_name", "crisis_name", "forgotten_category", "source_url",
        ])
        w.writeheader()
        w.writerows(rows)

    years = sorted({r["year"] for r in rows})
    print(f"Wrote {len(rows)} rows to {OUT}")
    print(f"Years covered: {years}")
    print(f"Rows per year: " + ", ".join(f"{y}:{sum(1 for r in rows if r['year']==y)}" for y in years))
    print(f"Requested-range gaps (2015-2025): 2018, 2025 (no list located)")
    if flags:
        print("\nFlags (review by eye):")
        for y, iso3, country, msg in flags:
            print(f"  {y} [{iso3 or '-'}] {country}: {msg}")


if __name__ == "__main__":
    main()
