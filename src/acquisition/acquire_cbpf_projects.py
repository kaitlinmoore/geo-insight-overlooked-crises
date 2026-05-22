"""Acquire CBPF project-level allocations with cluster (sector) attribution.

This fills the gap left by `bronze_cbpf_allocations` (CMU `Allocations__*.csv`),
which has only Year / PooledFund / AllocationType / Budget and NO sector field.
The output here carries a per-project, per-cluster budget split so that
`gold_sector_coverage` and the optional CBPF Allocation View screen can show
what sectors each fund allocated to.

SOURCE
------
OCHA CBPF Business Intelligence OData API (`cbpfapi.unocha.org/vo1/odata/`),
discovered via the HDX dataset `cbpf-allocations-and-contributions`
(`data.humdata.org/dataset/cbpf-allocations-and-contributions`), whose resource
list publishes the same OData service. License CC BY (IGO). No auth required.

The HDX *CSV* resource `global_cbpf_project_summary.csv` has project-grain rows
but NO cluster column. The cluster split lives only in the OData `Cluster`
entity (`ExcelClusterBase`), which is the primary source used here. Two sibling
OData entities are joined in:
  * `Poolfund`       -> fund -> recipient CountryCode (alpha-2) -> iso3
  * `ProjectSummary` -> project title / organization / dates (1:1 on project code)

GRAIN
-----
One row per (project x cluster). A project split across N clusters yields N rows;
`amount_usd` is that cluster's slice of the project budget (OData `ClusterBudget`),
and `cluster_percentage` is its share of the project.

iso3 DERIVATION
---------------
CBPF funds are (almost always) single-country. iso3 is mapped from the fund via
`Poolfund.CountryCode` (alpha-2 -> alpha-3 with pycountry). Two source values are
overridden (see FUND_ISO3_OVERRIDES):
  * Mozambique (RhPF) is mis-coded 'LI' (Liechtenstein) at source -> MOZ
  * Syria Cross border carries placeholder 'XX'                   -> SYR
    (operated cross-border from Turkey; recipient population is Syrian)

USAGE
-----
  python src/acquisition/acquire_cbpf_projects.py            # full run + enrich
  python src/acquisition/acquire_cbpf_projects.py --no-enrich # skip ProjectSummary join
  python src/acquisition/acquire_cbpf_projects.py --check     # one call, verify reachable

Outputs (./staging/, gitignored):
  cbpf_projects.csv             the project x cluster table
  _cbpf_projects_meta.json      audit trail: CKAN package_show + OData lineage + counts
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

try:
    import pycountry
except ImportError:  # pragma: no cover
    print("ERROR: pycountry is required (pip install pycountry).", file=sys.stderr)
    sys.exit(2)

# --- Configuration ---------------------------------------------------------
ODATA_BASE = "https://cbpfapi.unocha.org/vo1/odata/"
HDX_DATASET = "cbpf-allocations-and-contributions"
HDX_PACKAGE_SHOW = "https://data.humdata.org/api/3/action/package_show"

# HDX sits behind Cloudflare and 403s bare clients; send a browser UA.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

PAGE_SIZE = 5000          # OData $top per page; entity is ~24k rows
TIMEOUT_SEC = 180
BACKOFF_START_SEC = 5
BACKOFF_MAX_RETRIES = 4

# Fund CountryCode values that are wrong/placeholder at source -> corrected iso3.
FUND_ISO3_OVERRIDES = {
    "LI": "MOZ",   # Mozambique (RhPF) mis-coded as Liechtenstein
    "XX": "SYR",   # Syria Cross border placeholder
}

REPO_ROOT = Path(__file__).resolve().parents[2]
STAGING = REPO_ROOT / "staging"
OUT_CSV = STAGING / "cbpf_projects.csv"
META_JSON = STAGING / "_cbpf_projects_meta.json"

OUT_FIELDS = [
    "year", "fund_id", "fund_name", "iso3", "country_name",
    "cluster", "sub_cluster", "cluster_percentage", "amount_usd",
    "allocation_window", "project_code", "chf_id",
    "project_title", "recipient_organization", "recipient_organization_type",
    "project_status", "actual_start_date", "actual_end_date",
]

NULL_DATE = "0001-01-01T00:00:00"   # OData null-date sentinel


# --- HTTP layer ------------------------------------------------------------
def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


def get_json(session: requests.Session, url: str, params: dict) -> dict:
    backoff = BACKOFF_START_SEC
    for attempt in range(BACKOFF_MAX_RETRIES + 1):
        resp = session.get(url, params=params, timeout=TIMEOUT_SEC)
        if resp.status_code == 403:
            raise RuntimeError(
                f"HTTP 403 from {url} - source now requires auth or blocks the "
                f"client. Stopping (do not fish for keys)."
            )
        if resp.status_code in (429, 500, 502, 503):
            if attempt == BACKOFF_MAX_RETRIES:
                resp.raise_for_status()
            print(f"    HTTP {resp.status_code} - backing off {backoff}s "
                  f"(attempt {attempt + 1}/{BACKOFF_MAX_RETRIES})")
            time.sleep(backoff)
            backoff *= 2
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError("unreachable")


def odata_pull(session: requests.Session, entity: str,
               select: list[str] | None = None) -> list[dict]:
    """Pull an entire OData entity set via $skip pagination."""
    rows: list[dict] = []
    skip = 0
    params_base = {"$format": "json", "$top": str(PAGE_SIZE)}
    if select:
        params_base["$select"] = ",".join(select)
    while True:
        params = dict(params_base, **{"$skip": str(skip)})
        data = get_json(session, ODATA_BASE + entity, params)
        page = data.get("value", [])
        if not page:
            break
        rows.extend(page)
        skip += len(page)
        if len(page) < PAGE_SIZE:
            break
    return rows


# --- fund -> iso3 map ------------------------------------------------------
def build_fund_map(session: requests.Session) -> tuple[dict[int, dict], list[dict]]:
    """Return {PooledFundId: {iso3, country_name, fund_name, alpha2}} and a list
    of override/anomaly flags."""
    funds = odata_pull(session, "Poolfund")
    fund_map: dict[int, dict] = {}
    flags: list[dict] = []
    for f in funds:
        fid = f.get("Id")
        name = f.get("PoolfundName") or ""
        a2 = (f.get("CountryCode") or "").strip().upper()
        if a2 in FUND_ISO3_OVERRIDES:
            iso3 = FUND_ISO3_OVERRIDES[a2]
            flags.append({"fund_id": fid, "fund_name": name,
                          "source_alpha2": a2, "applied_iso3": iso3,
                          "reason": "source CountryCode overridden"})
        else:
            rec = pycountry.countries.get(alpha_2=a2)
            iso3 = rec.alpha_3 if rec else None
            if iso3 is None:
                flags.append({"fund_id": fid, "fund_name": name,
                              "source_alpha2": a2, "applied_iso3": None,
                              "reason": "alpha-2 not resolvable by pycountry"})
        country = pycountry.countries.get(alpha_3=iso3) if iso3 else None
        fund_map[fid] = {
            "iso3": iso3,
            "country_name": country.name if country else name,
            "fund_name": name,
            "alpha2": a2,
        }
    return fund_map, flags


# --- project metadata ------------------------------------------------------
def build_project_meta(session: requests.Session) -> dict[str, dict]:
    """Return {ChfProjectCode: {title, org, org_type, status, start, end}}.
    ProjectSummary is 1:1 on ChfProjectCode (verified during acquisition)."""
    rows = odata_pull(session, "ProjectSummary", select=[
        "ChfProjectCode", "ProjectTitle", "OrganizationName",
        "OrganizationType", "ProjectStatus", "ActualStartDate", "ActualEndDate",
    ])
    meta: dict[str, dict] = {}
    for r in rows:
        code = r.get("ChfProjectCode")
        if not code:
            continue
        meta[code] = r
    return meta


def clean_date(raw: str | None) -> str:
    if not raw or raw.startswith(NULL_DATE[:10]):
        return ""
    return raw[:10]


# --- main build ------------------------------------------------------------
def build_rows(cluster_rows: list[dict], fund_map: dict[int, dict],
               proj_meta: dict[str, dict]) -> list[dict]:
    out: list[dict] = []
    for c in cluster_rows:
        fid = c.get("PooledFundId")
        fm = fund_map.get(fid, {})
        code = c.get("ChfProjectCode")
        pm = proj_meta.get(code, {})
        window = (c.get("AllocationSourceName") or "").strip().lower()  # standard/reserve
        out.append({
            "year": c.get("AllocationYear"),
            "fund_id": fid,
            "fund_name": c.get("PooledFundName"),
            "iso3": fm.get("iso3"),
            "country_name": fm.get("country_name"),
            "cluster": c.get("Cluster"),
            "sub_cluster": c.get("SubCluster") or "",
            "cluster_percentage": c.get("Percentage"),
            "amount_usd": c.get("ClusterBudget"),
            "allocation_window": window,
            "project_code": code,
            "chf_id": c.get("ChfId"),
            "project_title": pm.get("ProjectTitle", ""),
            "recipient_organization": pm.get("OrganizationName", ""),
            "recipient_organization_type": pm.get("OrganizationType", ""),
            "project_status": pm.get("ProjectStatus", ""),
            "actual_start_date": clean_date(pm.get("ActualStartDate")),
            "actual_end_date": clean_date(pm.get("ActualEndDate")),
        })
    return out


def write_csv(rows: list[dict]) -> None:
    STAGING.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=OUT_FIELDS)
        w.writeheader()
        w.writerows(rows)


def fetch_ckan_snapshot(session: requests.Session) -> dict:
    try:
        return get_json(session, HDX_PACKAGE_SHOW, {"id": HDX_DATASET}).get("result", {})
    except Exception as e:  # noqa: BLE001 - audit-trail nicety, never fatal
        return {"_error": f"{type(e).__name__}: {e}"}


def write_meta(rows: list[dict], fund_flags: list[dict], enriched: bool,
               ckan: dict, n_cluster: int, n_projmeta: int) -> None:
    years = sorted({r["year"] for r in rows})
    funds = sorted({r["fund_name"] for r in rows})
    meta = {
        "acquired_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "odata_base": ODATA_BASE,
            "primary_entity": "Cluster (ExcelClusterBase)",
            "joined_entities": ["Poolfund", "ProjectSummary"] if enriched else ["Poolfund"],
            "discovered_via_hdx_dataset": HDX_DATASET,
            "license": ckan.get("license_id"),
            "data_update_frequency_days": ckan.get("data_update_frequency"),
        },
        "counts": {
            "output_rows": len(rows),
            "cluster_entity_rows": n_cluster,
            "project_summary_rows": n_projmeta,
            "distinct_funds": len(funds),
            "year_min": years[0] if years else None,
            "year_max": years[-1] if years else None,
        },
        "fund_iso3_flags": fund_flags,
        "ckan_package_show": ckan,
    }
    META_JSON.write_text(json.dumps(meta, indent=2, ensure_ascii=False),
                         encoding="utf-8")


# --- summary ---------------------------------------------------------------
def print_summary(rows: list[dict], fund_flags: list[dict]) -> None:
    n = len(rows)
    print("\n" + "=" * 60)
    print(f"OUTPUT: {n} rows (project x cluster) -> {OUT_CSV.name}")
    cl_null = sum(1 for r in rows if not r["cluster"])
    iso_ok = sum(1 for r in rows if r["iso3"] and len(r["iso3"]) == 3)
    amt_null = sum(1 for r in rows if r["amount_usd"] is None)
    print(f"  cluster non-null : {n - cl_null}/{n} ({100*(n-cl_null)/n:.2f}%)")
    print(f"  iso3 valid a3    : {iso_ok}/{n} ({100*iso_ok/n:.2f}%)")
    print(f"  amount non-null  : {n - amt_null}/{n}")
    years = sorted({r["year"] for r in rows})
    print(f"  year range       : {years[0]} - {years[-1]}")
    print(f"  distinct funds   : {len({r['fund_name'] for r in rows})}")
    print("\n  clusters present:")
    for cl, cnt in Counter(r["cluster"] for r in rows).most_common():
        print(f"    {cnt:6d}  {cl}")
    if fund_flags:
        print("\n  fund->iso3 flags (review):")
        for f in fund_flags:
            print(f"    [{f['fund_id']}] {f['fund_name']}: "
                  f"{f['source_alpha2']!r} -> {f['applied_iso3']} ({f['reason']})")


# --- check mode ------------------------------------------------------------
def run_check(session: requests.Session) -> int:
    print(f"Checking OData reachability: {ODATA_BASE}Cluster ...")
    try:
        data = get_json(session, ODATA_BASE + "Cluster",
                        {"$format": "json", "$top": "1", "$inlinecount": "allpages"})
    except Exception as e:  # noqa: BLE001
        print(f"  FAIL ({type(e).__name__}): {e}")
        return 1
    print(f"  OK - Cluster entity reachable. odata.count={data.get('odata.count')}.")
    return 0


# --- main ------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Acquire CBPF project x cluster allocations (OCHA CBPF OData API).")
    ap.add_argument("--no-enrich", action="store_true",
                    help="skip the ProjectSummary join (title/org/dates omitted)")
    ap.add_argument("--check", action="store_true",
                    help="verify the endpoint is reachable, then exit")
    args = ap.parse_args()

    session = make_session()
    if args.check:
        return run_check(session)

    print(f"CBPF project x cluster acquisition | {datetime.now().isoformat(timespec='seconds')}")
    print(f"OData base: {ODATA_BASE}")

    print("  [1/4] fund -> iso3 map (Poolfund) ...")
    fund_map, fund_flags = build_fund_map(session)
    print(f"        {len(fund_map)} funds; {len(fund_flags)} iso3 override/flag(s)")

    print("  [2/4] cluster splits (Cluster entity) ...")
    cluster_rows = odata_pull(session, "Cluster")
    print(f"        {len(cluster_rows)} cluster rows")

    proj_meta: dict[str, dict] = {}
    if not args.no_enrich:
        print("  [3/4] project metadata (ProjectSummary) ...")
        proj_meta = build_project_meta(session)
        print(f"        {len(proj_meta)} projects")
    else:
        print("  [3/4] skipped (--no-enrich)")

    print("  [4/4] assembling + writing ...")
    rows = build_rows(cluster_rows, fund_map, proj_meta)
    write_csv(rows)

    ckan = fetch_ckan_snapshot(session)
    write_meta(rows, fund_flags, not args.no_enrich, ckan,
               len(cluster_rows), len(proj_meta))

    print_summary(rows, fund_flags)
    print(f"\n  meta -> {META_JSON.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
