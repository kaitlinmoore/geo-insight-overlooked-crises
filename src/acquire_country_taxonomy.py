"""Acquire the OCHA Countries & Territories Taxonomy reference table.

Source: the OCHA C&T taxonomy feed used by the official `hdx-python-country`
library as its live source (a published Google Sheets CSV). Provides per
country: ISO3, ISO2, official names (multi-language), and the UN M49 regional
hierarchy (Region / Sub-region / Intermediate Region, names + codes). This is
the intended substrate for `silver_country_dim` and the `rank_crises(scope=...)`
regional filter.

Outputs to ./staging/ (gitignored). No HDX involved here; the Google Sheets
publish endpoint serves the CSV directly.

Run:  python src/acquire_country_taxonomy.py
"""
from __future__ import annotations

import pathlib
import urllib.request

# `_ochaurl_default` from hdx-python-country (OCHA C&T Taxonomy MVP feed).
FEED = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vSIIswgPn6oc_Ui3hCl2RTAdVZEw2sx4GjgqWFywrr8dt9R9B-p6Cs3jKeJigDguIbOjMxYtnloLlmI"
    "/pub?gid=1528390745&single=true&output=csv"
)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
STAGING = pathlib.Path(__file__).resolve().parents[1] / "staging"


def main() -> None:
    STAGING.mkdir(exist_ok=True)
    req = urllib.request.Request(FEED, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    out = STAGING / "country_taxonomy_raw.csv"
    out.write_bytes(data)
    print(f"wrote {out} ({len(data):,} bytes)")


if __name__ == "__main__":
    main()
