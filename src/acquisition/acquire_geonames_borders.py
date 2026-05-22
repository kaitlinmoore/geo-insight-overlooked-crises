"""Acquire country-level land-border adjacency from GeoNames.

Portable replacement for the Sedona polygon-adjacency path that was deferred
from v1 (serverless Databricks compute can't install the Sedona JVM library).
This downloads the GeoNames `countryInfo.txt` reference table once, parses it,
and emits a clean ISO3-keyed CSV of each country's neighbour list. That CSV
loads as `bronze_country_borders` and feeds `gold_cross_border_patterns`.

SOURCE
------
GeoNames `countryInfo.txt` (`http://download.geonames.org/export/dump/`).
A tab-separated reference table: ~50 lines of `#`-comment metadata, then a
header row beginning `#ISO`, then one data row per country. License **CC-BY**
(GeoNames terms — attribution required; printed to stdout on every run).

The `neighbours` column is a comma-separated list of **alpha-2** codes. We
convert it to alpha-3 using the file's own ISO ↔ ISO3 mapping (every row maps
its alpha-2 to its alpha-3), so no external country-code dependency is needed.

GRAIN
-----
One row per country (ISO3). `neighbor_iso3_list` is comma-separated alpha-3;
empty for island/landlocked-with-no-listed-neighbours nations.

USAGE
-----
  python src/acquisition/acquire_geonames_borders.py            # full run
  python src/acquisition/acquire_geonames_borders.py --check    # reachability only

Outputs (./staging/, gitignored):
  country_borders.csv            iso3, country_name, neighbor_iso3_list, n_neighbors
  _country_borders_meta.json     audit trail: source URL + date + counts
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests

# --- Configuration ---------------------------------------------------------
SOURCE_URL = "http://download.geonames.org/export/dump/countryInfo.txt"
LICENSE = "CC-BY (GeoNames)"
ATTRIBUTION = "Country adjacency data © GeoNames (https://www.geonames.org/), CC-BY."

# Column indices in countryInfo.txt (header: #ISO ISO3 ISO-Numeric fips Country
# Capital Area Population Continent tld CurrencyCode CurrencyName Phone
# 'Postal Code Format' 'Postal Code Regex' Languages geonameid neighbours
# EquivalentFipsCode).
COL_ISO2 = 0
COL_ISO3 = 1
COL_COUNTRY = 4
COL_NEIGHBOURS = 17
MIN_COLS = 19

TIMEOUT_SEC = 120
BACKOFF_START_SEC = 5
BACKOFF_MAX_RETRIES = 4

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

REPO_ROOT = Path(__file__).resolve().parents[2]
STAGING = REPO_ROOT / "staging"
OUT_CSV = STAGING / "country_borders.csv"
META_JSON = STAGING / "_country_borders_meta.json"

OUT_FIELDS = ["iso3", "country_name", "neighbor_iso3_list", "n_neighbors"]


# --- HTTP layer ------------------------------------------------------------
def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


def fetch_text(session: requests.Session, url: str) -> str:
    backoff = BACKOFF_START_SEC
    for attempt in range(BACKOFF_MAX_RETRIES + 1):
        resp = session.get(url, timeout=TIMEOUT_SEC)
        if resp.status_code in (429, 500, 502, 503):
            if attempt == BACKOFF_MAX_RETRIES:
                resp.raise_for_status()
            print(f"    HTTP {resp.status_code} - backing off {backoff}s "
                  f"(attempt {attempt + 1}/{BACKOFF_MAX_RETRIES})")
            time.sleep(backoff)
            backoff *= 2
            continue
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return resp.text
    raise RuntimeError("unreachable")


# --- parsing ---------------------------------------------------------------
def parse_country_info(text: str) -> list[list[str]]:
    """Return the data rows (list of tab-split fields), skipping all
    `#`-comment lines (which includes the `#ISO...` header row)."""
    rows: list[list[str]] = []
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        rows.append(line.split("\t"))
    return rows


def build_alpha2_to_iso3(rows: list[list[str]]) -> dict[str, str]:
    """Map alpha-2 -> alpha-3 from the file's own rows."""
    m: dict[str, str] = {}
    for r in rows:
        if len(r) <= COL_ISO3:
            continue
        a2 = r[COL_ISO2].strip().upper()
        a3 = r[COL_ISO3].strip().upper()
        if len(a2) == 2 and len(a3) == 3:
            m[a2] = a3
    return m


def build_rows(rows: list[list[str]], a2_to_a3: dict[str, str]
               ) -> tuple[list[dict], list[dict]]:
    """Build the output rows plus a list of any neighbour alpha-2 codes that
    couldn't be resolved to an alpha-3 (audit flag)."""
    out: list[dict] = []
    unresolved: list[dict] = []
    for r in rows:
        if len(r) < MIN_COLS:
            continue
        iso3 = r[COL_ISO3].strip().upper()
        if len(iso3) != 3:
            continue
        country = r[COL_COUNTRY].strip()
        raw_neighbours = r[COL_NEIGHBOURS].strip()
        neighbours_a3: list[str] = []
        if raw_neighbours:
            for a2 in raw_neighbours.split(","):
                a2 = a2.strip().upper()
                if not a2:
                    continue
                a3 = a2_to_a3.get(a2)
                if a3:
                    neighbours_a3.append(a3)
                else:
                    unresolved.append({"iso3": iso3, "neighbour_alpha2": a2})
        out.append({
            "iso3": iso3,
            "country_name": country,
            "neighbor_iso3_list": ",".join(neighbours_a3),
            "n_neighbors": len(neighbours_a3),
        })
    out.sort(key=lambda d: d["iso3"])
    return out, unresolved


# --- output ----------------------------------------------------------------
def write_csv(rows: list[dict]) -> None:
    STAGING.mkdir(parents=True, exist_ok=True)
    acquired = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with OUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        # Header comment line (provenance). The Bronze loader skips it via the
        # Spark CSV `comment="#"` option, so the real header is the next line.
        fh.write(f"# country_borders.csv | source: {SOURCE_URL} | "
                 f"acquired: {acquired} | license: {LICENSE}\n")
        w = csv.DictWriter(fh, fieldnames=OUT_FIELDS)
        w.writeheader()
        w.writerows(rows)


def write_meta(rows: list[dict], unresolved: list[dict], n_data_rows: int) -> None:
    n = len(rows)
    zero = sorted(d["iso3"] for d in rows if d["n_neighbors"] == 0)
    mean_n = sum(d["n_neighbors"] for d in rows) / n if n else 0.0
    meta = {
        "acquired_at": datetime.now(timezone.utc).isoformat(),
        "source": {"url": SOURCE_URL, "license": LICENSE, "attribution": ATTRIBUTION},
        "counts": {
            "output_rows": n,
            "source_data_rows": n_data_rows,
            "mean_n_neighbors": round(mean_n, 3),
            "countries_zero_neighbors": len(zero),
            "unresolved_neighbour_codes": len(unresolved),
        },
        "countries_zero_neighbors": zero,
        "unresolved_neighbour_codes": unresolved,
    }
    META_JSON.write_text(json.dumps(meta, indent=2, ensure_ascii=False),
                         encoding="utf-8")


# --- summary ---------------------------------------------------------------
def print_summary(rows: list[dict], unresolved: list[dict]) -> None:
    n = len(rows)
    mean_n = sum(d["n_neighbors"] for d in rows) / n if n else 0.0
    zero = sorted(d["iso3"] for d in rows if d["n_neighbors"] == 0)
    print("\n" + "=" * 60)
    print(f"OUTPUT: {n} rows -> {OUT_CSV.name}")
    print(f"  mean n_neighbors        : {mean_n:.2f}")
    print(f"  countries w/ 0 neighbors: {len(zero)} (islands expected)")
    print(f"    {', '.join(zero)}")
    if unresolved:
        uniq = Counter(d["neighbour_alpha2"] for d in unresolved)
        print(f"  unresolved neighbour codes: {len(unresolved)} "
              f"({len(uniq)} distinct)")
        for a2, cnt in uniq.most_common():
            print(f"    {a2}: {cnt}")
    print(f"\n  {ATTRIBUTION}")


# --- check mode ------------------------------------------------------------
def run_check(session: requests.Session) -> int:
    print(f"Checking reachability: {SOURCE_URL} ...")
    try:
        text = fetch_text(session, SOURCE_URL)
    except Exception as e:  # noqa: BLE001
        print(f"  FAIL ({type(e).__name__}): {e}")
        return 1
    data_rows = parse_country_info(text)
    print(f"  OK - {len(text)} bytes, {len(data_rows)} data rows parsed.")
    return 0


# --- main ------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Acquire country land-border adjacency from GeoNames countryInfo.txt.")
    ap.add_argument("--check", action="store_true",
                    help="verify the source is reachable, then exit")
    args = ap.parse_args()

    print(ATTRIBUTION)
    session = make_session()
    if args.check:
        return run_check(session)

    print(f"GeoNames borders acquisition | {datetime.now().isoformat(timespec='seconds')}")
    print(f"  source: {SOURCE_URL}")

    text = fetch_text(session, SOURCE_URL)
    data_rows = parse_country_info(text)
    print(f"  parsed {len(data_rows)} data rows")

    a2_to_a3 = build_alpha2_to_iso3(data_rows)
    print(f"  alpha-2 -> alpha-3 map: {len(a2_to_a3)} entries")

    rows, unresolved = build_rows(data_rows, a2_to_a3)
    write_csv(rows)
    write_meta(rows, unresolved, len(data_rows))

    print_summary(rows, unresolved)
    print(f"\n  meta -> {META_JSON.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
