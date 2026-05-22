"""Acquire ACLED *event-level* data via the ACLED OAuth API.

Feeds the point-level / H3 path: silver_acled_events.
Output: ./staging/acled_events_2020_present.parquet

Why this exists separately from acquire_acled.py: the HDX ACLED mirror is
aggregated (Admin2 x Month, no coordinates). Point lat/lon, event_date,
sub_event_type, actors, and notes are only available from the API, which is
required for H3 resolution-5 spatial-temporal hotspot detection.

Credentials (never commit): set in .env at repo root
    ACLED_USERNAME=<your acleddata.com account email>
    ACLED_PASSWORD=<your acleddata.com password>

Register a free account at https://acleddata.com/register/ . The OAuth flow:
    POST https://acleddata.com/oauth/token
        username, password, grant_type=password, client_id=acled,
        scope=authenticated
    -> access_token (valid 24h). Use as `Authorization: Bearer <token>` on
    GET https://acleddata.com/api/acled/read
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pandas as pd
import pycountry
import requests

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except Exception:  # noqa: BLE001
    pass

TOKEN_URL = "https://acleddata.com/oauth/token"
READ_URL = "https://acleddata.com/api/acled/read"
STAGING = Path(__file__).resolve().parents[2] / "staging"
START_DATE = "2020-01-01"
PAGE_LIMIT = 5000

# Same 25 priority ISO3 as acquire_acled.py.
PRIORITY_ISO3 = [
    "SDN", "YEM", "MMR", "BFA", "MLI", "NER", "TCD", "COD", "SSD", "COL",
    "VEN", "HTI", "AFG", "ETH", "SOM", "NGA", "SYR", "UKR", "PSE", "PHL",
    "HND", "GTM", "CMR", "CAF", "MOZ",
]

# Fields to request. event_type/sub_event_type/notes/source + precision flags
# + actors so the Silver layer has everything it needs.
FIELDS = "|".join([
    "event_id_cnty", "event_date", "year", "time_precision", "disorder_type",
    "event_type", "sub_event_type", "actor1", "assoc_actor_1", "actor2",
    "assoc_actor_2", "country", "iso", "admin1", "admin2", "admin3",
    "location", "latitude", "longitude", "geo_precision", "source",
    "source_scale", "notes", "fatalities", "tags",
])


def iso_numeric(iso3: str) -> str:
    c = pycountry.countries.get(alpha_3=iso3)
    if not c:
        raise ValueError(f"unknown ISO3 {iso3}")
    return str(int(c.numeric))


def get_token() -> str:
    user = os.environ.get("ACLED_USERNAME")
    pwd = os.environ.get("ACLED_PASSWORD")
    if not user or not pwd:
        print("ERROR: set ACLED_USERNAME and ACLED_PASSWORD in .env "
              "(see header of this file).", file=sys.stderr)
        sys.exit(2)
    r = requests.post(TOKEN_URL, data={
        "username": user, "password": pwd, "grant_type": "password",
        "client_id": "acled", "scope": "authenticated"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=60)
    if r.status_code != 200:
        print(f"OAuth failed {r.status_code}: {r.text[:300]}", file=sys.stderr)
        sys.exit(2)
    return r.json()["access_token"]


def fetch_country(token: str, iso3: str) -> pd.DataFrame:
    headers = {"Authorization": f"Bearer {token}"}
    iso_num = iso_numeric(iso3)
    rows, page = [], 1
    while True:
        params = {
            "iso": iso_num,
            "event_date": START_DATE,
            "event_date_where": ">=",
            "fields": FIELDS,
            "limit": PAGE_LIMIT,
            "page": page,
        }
        r = requests.get(READ_URL, headers=headers, params=params, timeout=180)
        r.raise_for_status()
        payload = r.json()
        data = payload.get("data", [])
        if not data:
            break
        rows.extend(data)
        if len(data) < PAGE_LIMIT:
            break
        page += 1
        time.sleep(0.3)  # be polite
    df = pd.DataFrame(rows)
    if not df.empty:
        df["priority_iso3"] = iso3  # alpha-3; ACLED 'iso' is numeric
    return df


def normalize_types(df: pd.DataFrame) -> pd.DataFrame:
    """The ACLED API returns all values as JSON strings. Cast the numeric
    columns so the parquet is directly usable downstream. lat/lon -> float64
    losslessly preserves ACLED's native 4-decimal precision (H3 indexing
    happens downstream). Keeps event_date as datetime."""
    floats = ["latitude", "longitude"]
    ints = ["year", "iso", "fatalities", "geo_precision", "time_precision"]
    for c in floats:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ints:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    if "event_date" in df:
        df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    return df


def main() -> int:
    STAGING.mkdir(exist_ok=True)
    token = get_token()
    frames, summary = [], []
    for iso3 in PRIORITY_ISO3:
        try:
            df = fetch_country(token, iso3)
            frames.append(df)
            summary.append((iso3, len(df)))
            print(f"  {iso3}: {len(df):,} events", flush=True)
        except Exception as exc:  # noqa: BLE001
            summary.append((iso3, f"ERROR {exc}"))
            print(f"  {iso3}: ERROR {exc}", flush=True)

    frames = [f for f in frames if not f.empty]
    if not frames:
        print("No events acquired.", file=sys.stderr)
        return 1
    full = pd.concat(frames, ignore_index=True)
    full = normalize_types(full)
    out = STAGING / "acled_events_2020_present.parquet"
    full.to_parquet(out, index=False)
    print(f"\nWrote {out}  rows={len(full):,}  countries={full['priority_iso3'].nunique()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
