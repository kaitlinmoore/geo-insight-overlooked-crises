"""Acquire ACLED conflict data for the Geo-Insight priority country list.

Two distinct downstream paths (see docs/notes/acquisition_acled.md):

  HDX aggregates  -> ./staging/acled_severity_admin2_month_2020_present.parquet
                     feeds silver_acled_severity (admin2 x month grain).
                     No credentials required. THIS is what `main()` pulls.

  ACLED API       -> ./staging/acled_events_2020_present.parquet
                     feeds silver_acled_events (point-level, H3-indexed).
                     Requires credentials; see acquire_acled_api.py.

The HDX ACLED country datasets are *aggregated* (event/fatality counts by
Admin2 x Month x Year), split into three thematic files. They do NOT contain
point lat/lon, event_date, sub_event_type, actors, or notes. Resource URLs
embed an "as-of" date that changes weekly, so we resolve them at runtime via
the HDX CKAN API rather than hardcoding.
"""
from __future__ import annotations

import io
import struct
import sys
import time
import zipfile
import zlib
from pathlib import Path

import pandas as pd
import requests

HDR = {"User-Agent": "geo-insight-acquisition/1.0"}
CKAN = "https://data.humdata.org/api/3/action/package_show?id={slug}-acled-conflict-data"
STAGING = Path(__file__).resolve().parents[2] / "staging"

# ISO3 -> HDX dataset slug. Verified against the ACLED HDX org listing.
PRIORITY = {
    "SDN": "sudan", "YEM": "yemen", "MMR": "myanmar", "BFA": "burkina-faso",
    "MLI": "mali", "NER": "niger", "TCD": "chad",
    "COD": "democratic-republic-of-congo", "SSD": "south-sudan",
    "COL": "colombia", "VEN": "venezuela", "HTI": "haiti", "AFG": "afghanistan",
    "ETH": "ethiopia", "SOM": "somalia", "NGA": "nigeria", "SYR": "syria",
    "UKR": "ukraine", "PSE": "palestine", "PHL": "philippines", "HND": "honduras",
    "GTM": "guatemala", "CMR": "cameroon", "CAF": "central-african-republic",
    "MOZ": "mozambique",
}

CATEGORIES = ("political_violence", "civilian_targeting", "demonstration")
MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}
START_YEAR = 2020


def categorise(resource_name: str) -> str | None:
    n = resource_name.lower()
    if "political_violence" in n:
        return "political_violence"
    if "civilian_targeting" in n:
        return "civilian_targeting"
    if "demonstration" in n:
        return "demonstration"
    return None


def resolve_resources(iso: str, slug: str) -> dict[str, str]:
    r = requests.get(CKAN.format(slug=slug), headers=HDR, timeout=90)
    r.raise_for_status()
    out: dict[str, str] = {}
    for res in r.json()["result"]["resources"]:
        cat = categorise(res.get("name", ""))
        if cat:
            out[cat] = res["url"]
    return out


def recover_by_local_walk(raw: bytes) -> bytes:
    """Rebuild a zip by scanning local file headers top-down, ignoring the
    (corrupt) central directory -- the Python equivalent of `zip -FF`.

    Some ACLED HDX XLSX (e.g. Chad, Colombia, CAR) ship with a broken zip
    central directory whose offsets point at garbage, defeating openpyxl,
    calamine, and stdlib zipfile. The *local* file headers and the deflate
    streams themselves are intact, so we can recover the real data by walking
    them sequentially and writing a fresh, valid zip.
    """
    out = io.BytesIO()
    dst = zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED)
    pos, n = 0, len(raw)
    while pos < n - 4 and raw[pos:pos + 4] == b"PK\x03\x04":
        (_ver, _fl, method, _mt, _md, _crc, csize, _usize,
         nlen, elen) = struct.unpack("<HHHHHIIIHH", raw[pos + 4:pos + 30])
        name = raw[pos + 30:pos + 30 + nlen].decode("utf-8", "replace")
        data_start = pos + 30 + nlen + elen
        comp = raw[data_start:data_start + csize]
        try:
            data = zlib.decompress(comp, -15) if method == 8 else comp
            dst.writestr(name, data)
        except Exception:  # noqa: BLE001
            pass
        pos = data_start + csize if csize > 0 else (
            raw.find(b"PK\x03\x04", data_start) or n)
    dst.close()
    return out.getvalue()


def read_data_sheet(url: str, attempts: int = 4) -> pd.DataFrame:
    """Download an ACLED HDX XLSX and read its 'Data' sheet, with retries.

    Two server-side quirks in ACLED's HDX XLSX (verified: byte-stable across
    downloads, so not our network):
      1. Non-standard zip central directory that openpyxl/stdlib reject. The
         Rust-based `calamine` engine reads these fine, so it's the default.
      2. A few files (Chad, Colombia, CAR) additionally have broken cd offsets
         that defeat calamine too -- recovered via recover_by_local_walk().
    Retries also cover genuine network truncation.
    """
    last = None
    for i in range(attempts):
        try:
            raw = requests.get(url, headers=HDR, timeout=300).content
        except Exception as exc:  # noqa: BLE001
            last = str(exc)
            time.sleep(1.5 * (i + 1))
            continue
        # 'TOU' sheet = terms of use; 'Data' sheet = the aggregates.
        try:
            return pd.read_excel(io.BytesIO(raw), sheet_name="Data",
                                 engine="calamine")
        except Exception as exc:  # noqa: BLE001
            last = f"calamine: {exc}"
        try:
            fixed = recover_by_local_walk(raw)
            return pd.read_excel(io.BytesIO(fixed), sheet_name="Data",
                                 engine="calamine")
        except Exception as exc:  # noqa: BLE001
            last = f"recovery: {exc}"
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"read failed after {attempts} attempts: {last}")


def read_aggregate(url: str, iso: str, category: str) -> pd.DataFrame:
    df = read_data_sheet(url)
    df.columns = [c.strip() for c in df.columns]
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce").astype("Int64")
    df = df[df["Year"] >= START_YEAR].copy()
    df["event_category"] = category
    df["priority_iso3"] = iso
    df["month_num"] = df["Month"].map(MONTHS)
    df["month_start"] = pd.to_datetime(
        dict(year=df["Year"], month=df["month_num"], day=1), errors="coerce")
    return df


def main() -> int:
    STAGING.mkdir(exist_ok=True)
    frames, missing = [], []
    for iso, slug in PRIORITY.items():
        try:
            res = resolve_resources(iso, slug)
        except Exception as exc:  # noqa: BLE001
            missing.append((iso, f"resolve failed: {exc}"))
            continue
        got = 0
        for cat in CATEGORIES:
            url = res.get(cat)
            if not url:
                missing.append((iso, f"missing {cat}"))
                continue
            try:
                frames.append(read_aggregate(url, iso, cat))
                got += 1
            except Exception as exc:  # noqa: BLE001
                missing.append((iso, f"{cat}: {exc}"))
        print(f"  {iso} {slug}: {got}/3 files", flush=True)

    if not frames:
        print("No data acquired.", file=sys.stderr)
        return 1

    full = pd.concat(frames, ignore_index=True)
    # Normalise column names to snake_case for the parquet.
    full = full.rename(columns={
        "Country": "country", "Admin1": "admin1", "Admin2": "admin2",
        "ISO3": "iso3", "Admin2 Pcode": "admin2_pcode",
        "Admin1 Pcode": "admin1_pcode", "Month": "month_name",
        "Year": "year", "Events": "events", "Fatalities": "fatalities"})
    cols = ["iso3", "priority_iso3", "country", "admin1", "admin2",
            "admin1_pcode", "admin2_pcode", "event_category", "year",
            "month_name", "month_num", "month_start", "events", "fatalities"]
    full = full[[c for c in cols if c in full.columns]]
    out = STAGING / "acled_severity_admin2_month_2020_present.parquet"
    full.to_parquet(out, index=False)

    print(f"\nWrote {out}  rows={len(full):,}  countries={full['iso3'].nunique()}")
    if missing:
        print("\nIssues:")
        for iso, why in missing:
            print(f"  {iso}: {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
