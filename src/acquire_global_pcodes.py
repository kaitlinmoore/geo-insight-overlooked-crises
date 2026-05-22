"""Acquire the OCHA Global P-code List from HDX.

Source: HDX dataset slug `global-pcodes` (CC BY-IGO, ~30-day refresh).
Canonical reference of every COD p-code (iso3, admin level, p-code, name,
parent p-code, date). Used to validate HNO p-codes against an official COD
reference and to provide an admin2->admin1->admin0 rollup hierarchy.

Outputs to ./staging/ (gitignored). Resource download URLs are resolved live
from the CKAN API so the script survives resource-id rotation. HDX blocks
plain WebFetch (Cloudflare); a browser User-Agent header is required.

Run:  python src/acquire_global_pcodes.py
"""
from __future__ import annotations

import json
import pathlib
import urllib.request

DATASET = "global-pcodes"
# Resources we want, by HDX resource `name` -> local staging filename.
WANTED = {
    "global_pcodes.csv": "global_pcodes_raw.csv",
    "global_pcode_lengths.csv": "global_pcode_lengths.csv",
}

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
STAGING = pathlib.Path(__file__).resolve().parents[1] / "staging"
CKAN = "https://data.humdata.org/api/3/action/package_show?id="


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def main() -> None:
    STAGING.mkdir(exist_ok=True)
    meta = json.loads(_get(CKAN + DATASET))["result"]
    by_name = {r.get("name"): r for r in meta.get("resources", [])}

    # Persist dataset metadata for the audit trail.
    (STAGING / "_global_pcodes_meta.json").write_text(
        json.dumps(
            {
                "title": meta.get("title"),
                "last_modified": meta.get("last_modified"),
                "data_update_frequency": meta.get("data_update_frequency"),
                "cod_level": meta.get("cod_level"),
                "license": meta.get("license_id"),
                "methodology_other": meta.get("methodology_other"),
                "resources": [
                    {"name": r.get("name"), "url": r.get("download_url")}
                    for r in meta.get("resources", [])
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    for res_name, out_name in WANTED.items():
        res = by_name.get(res_name)
        if not res:
            print(f"WARN: resource {res_name!r} not found in dataset")
            continue
        data = _get(res["download_url"])
        out = STAGING / out_name
        out.write_bytes(data)
        print(f"wrote {out} ({len(data):,} bytes)")


if __name__ == "__main__":
    main()
