"""Top up COD-PS global subnational population data (admin2 + admin3).

Source: HDX dataset slug `cod-ps-global` ("Global - Subnational Population
Statistics", CC BY-IGO, annual refresh). The project already holds the
admin0/1/4 CSVs from this same dataset; this script pulls the two missing
levels. admin2 population is the denominator for subnational `severity_rate`
in the geographic deep-dive (docs/methodology.md, "Subnational ranking").

Outputs to ./staging/ (gitignored). HDX blocks plain WebFetch; a browser
User-Agent is required.

Run:  python src/acquire_cod_population.py
"""
from __future__ import annotations

import json
import pathlib
import urllib.request

DATASET = "cod-ps-global"
WANTED = {
    "cod_population_admin2.csv": "cod_population_admin2.csv",
    "cod_population_admin3.csv": "cod_population_admin3.csv",
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

    (STAGING / "_cod_ps_global_meta.json").write_text(
        json.dumps(
            {
                "title": meta.get("title"),
                "last_modified": meta.get("last_modified"),
                "data_update_frequency": meta.get("data_update_frequency"),
                "cod_level": meta.get("cod_level"),
                "license": meta.get("license_id"),
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
