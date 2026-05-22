"""Acquire ReliefWeb situation reports / analyses / assessments into local staging.

Source: ReliefWeb API (OCHA's humanitarian information portal).
  Endpoint: https://api.reliefweb.int/v2/reports   (v1 was decommissioned 2025; v2
  is fully compatible with v1 — same POST query structure and field names.)
  Docs: https://apidoc.reliefweb.int

These documents feed an OPTIONAL Day-4 Knowledge Assistant indexing step. They go
to Bronze regardless of whether they are ever indexed. This is a one-off local
acquisition into ./staging/ (gitignored); it does not touch Databricks.

APPNAME REQUIREMENT (blocker if unset)
--------------------------------------
From 1 November 2025 the ReliefWeb API requires a *pre-approved* appname. An
arbitrary string returns HTTP 403. Request one (reviewed + emailed back by
ReliefWeb) via the form linked at:
  https://apidoc.reliefweb.int/parameters#appname
ReliefWeb recommends the form "<org>-<purpose>-<random>", e.g.
  geo-insight-hackathon-knowledge-assistant-7f3a
Then put it in a local .env at the repo root (see .env.example):
  RELIEFWEB_APPNAME=...
This script reads .env without requiring python-dotenv (simple line parser);
an OS environment variable of the same name takes precedence.

What it does
------------
For each of FOCUS_COUNTRIES (25 ISO3 codes — overlooked focus + reference crises
for demo contrast), query the API for:
  - format.name in {"Situation Report", "Analysis", "Assessment"}
  - date.original within the last LOOKBACK_MONTHS months
  - language English, status published
Pulls up to PER_COUNTRY_LIMIT (20) most-recent docs per country, with a global
cap of GLOBAL_CAP (500). Each doc is written as one JSON file:
  ./staging/reliefweb_docs/{iso3}/{date}_{id}.json
containing: id, title, country (primary), iso3, date, source organisation(s),
format, language, url, body (markdown text), body_html, plus the query context.

Countries returning 0 docs / HTTP errors are logged and skipped; the run
continues. A final summary prints per-country counts, date-range coverage, and
an aggregate body-length distribution so we can sanity-check that docs are
substantive rather than 200-word stubs. For the first country (SDN) it also
prints 2 sample titles and the first 200 chars of body as a quality check.
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# --- Configuration ---------------------------------------------------------
API_URL = "https://api.reliefweb.int/v2/reports"

# Top-25 focus list: overlooked focus + reference crises for demo contrast.
FOCUS_COUNTRIES = [
    "SDN", "YEM", "MMR", "BFA", "MLI", "NER", "TCD", "COD", "SSD", "COL",
    "VEN", "HTI", "AFG", "ETH", "SOM", "NGA", "SYR", "UKR", "PSE", "PHL",
    "HND", "GTM", "CMR", "CAF", "MOZ",
]

FORMATS = ["Situation Report", "Analysis", "Assessment"]
LOOKBACK_MONTHS = 36
PER_COUNTRY_LIMIT = 20
GLOBAL_CAP = 500
REQUEST_PAUSE_SEC = 0.5  # polite spacing between API calls
TIMEOUT_SEC = 60

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "staging" / "reliefweb_docs"

# Fields requested from the API (v2 == v1 field names).
INCLUDE_FIELDS = [
    "id", "title", "status", "url", "url_alias",
    "date.original", "date.created",
    "source.name", "source.shortname",
    "format.name", "language.name",
    "primary_country.iso3", "primary_country.name",
    "country.iso3", "country.name",
    "body", "body-html",
]


def load_appname() -> str:
    """Resolve RELIEFWEB_APPNAME from the OS env or a repo-root .env file.

    OS environment wins. Avoids a python-dotenv dependency with a minimal
    KEY=VALUE line parser (ignores blanks and #comments, strips quotes).
    """
    import os

    val = os.environ.get("RELIEFWEB_APPNAME")
    if val:
        return val.strip()

    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, raw = line.partition("=")
            if key.strip() == "RELIEFWEB_APPNAME":
                return raw.strip().strip('"').strip("'")
    return ""


def build_query(iso3: str, date_from: str, date_to: str) -> dict:
    """POST body for one country: filtered, most-recent-first, profile=full."""
    return {
        "limit": PER_COUNTRY_LIMIT,
        "profile": "full",
        "sort": ["date.original:desc"],
        "filter": {
            "operator": "AND",
            "conditions": [
                {"field": "primary_country.iso3", "value": iso3},
                {"field": "format.name", "value": FORMATS},
                {"field": "language.name", "value": "English"},
                {"field": "status", "value": "published"},
                {"field": "date.original",
                 "value": {"from": date_from, "to": date_to}},
            ],
        },
        "fields": {"include": INCLUDE_FIELDS},
    }


def doc_date(fields: dict) -> str:
    """YYYY-MM-DD for the filename: prefer date.original, fall back to created."""
    date = fields.get("date", {}) or {}
    raw = date.get("original") or date.get("created") or ""
    return raw[:10] if raw else "undated"


def names(value) -> list[str]:
    """Extract .name values from a list-of-dicts API field (source/format/etc.)."""
    if isinstance(value, list):
        return [v.get("name", "") for v in value if isinstance(v, dict)]
    if isinstance(value, dict):
        return [value.get("name", "")]
    return []


def record_from(fields: dict, iso3: str, ctx: dict) -> dict:
    """Shape the saved JSON: the task-required fields plus query context."""
    primary = fields.get("primary_country", {}) or {}
    if isinstance(primary, list):  # API may return a single-element list
        primary = primary[0] if primary else {}
    return {
        "id": fields.get("id"),
        "title": fields.get("title"),
        "country": primary.get("name"),
        "iso3": primary.get("iso3", iso3),
        "all_countries": names(fields.get("country")),
        "date": doc_date(fields),
        "date_original": (fields.get("date", {}) or {}).get("original"),
        "date_created": (fields.get("date", {}) or {}).get("created"),
        "source_organization": names(fields.get("source")),
        "format": names(fields.get("format")),
        "language": names(fields.get("language")),
        "status": fields.get("status"),
        "url": fields.get("url") or fields.get("url_alias"),
        "body": fields.get("body", "") or "",
        "body_html": fields.get("body-html", "") or "",
        "_query_country": iso3,
        "_acquired_at": ctx["acquired_at"],
        "_api_url": API_URL,
        "_appname": ctx["appname"],
    }


def fetch_country(appname: str, iso3: str, date_from: str, date_to: str) -> dict:
    """Return the API JSON for one country. Raises on HTTP/transport error."""
    resp = requests.post(
        API_URL,
        params={"appname": appname},
        json=build_query(iso3, date_from, date_to),
        timeout=TIMEOUT_SEC,
    )
    resp.raise_for_status()
    return resp.json()


def main() -> int:
    appname = load_appname()
    if not appname:
        print("ERROR: RELIEFWEB_APPNAME is not set.", file=sys.stderr)
        print("The ReliefWeb v2 API requires a PRE-APPROVED appname (since "
              "2025-11-01).", file=sys.stderr)
        print("  1. Request one: https://apidoc.reliefweb.int/parameters#appname",
              file=sys.stderr)
        print("     (form suggests '<org>-<purpose>-<random>'; ReliefWeb emails "
              "back an approval)", file=sys.stderr)
        print("  2. Add to a repo-root .env:  RELIEFWEB_APPNAME=...", file=sys.stderr)
        print("  3. Re-run this script.", file=sys.stderr)
        return 2

    now = datetime.now(timezone.utc)
    date_to = now.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    date_from = (now - timedelta(days=LOOKBACK_MONTHS * 30)).strftime(
        "%Y-%m-%dT%H:%M:%S+00:00")
    ctx = {"acquired_at": now.isoformat(), "appname": appname}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"ReliefWeb acquisition -> {OUT_DIR}")
    print(f"Window: {date_from[:10]} .. {date_to[:10]}  "
          f"({LOOKBACK_MONTHS} months) | up to {PER_COUNTRY_LIMIT}/country, "
          f"cap {GLOBAL_CAP}\n")

    saved_per_country: dict[str, int] = {}
    skipped: list[tuple[str, str]] = []  # (iso3, reason)
    body_lengths: list[int] = []
    all_dates: list[str] = []
    total_saved = 0
    sdn_samples: list[tuple[str, str]] = []  # (title, body) for quality check

    for iso3 in FOCUS_COUNTRIES:
        if total_saved >= GLOBAL_CAP:
            skipped.append((iso3, "global cap reached"))
            continue

        try:
            data = fetch_country(appname, iso3, date_from, date_to)
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else "?"
            skipped.append((iso3, f"HTTP {code}"))
            print(f"  {iso3}: HTTP {code} — logged and skipped")
            if code == 403:  # appname rejected: no point hammering 24 more times
                print("  (HTTP 403 = appname not approved; aborting run)")
                break
            time.sleep(REQUEST_PAUSE_SEC)
            continue
        except requests.RequestException as e:
            skipped.append((iso3, f"transport error: {type(e).__name__}"))
            print(f"  {iso3}: {type(e).__name__} — logged and skipped")
            time.sleep(REQUEST_PAUSE_SEC)
            continue

        items = data.get("data", []) or []
        if not items:
            skipped.append((iso3, "no docs returned"))
            print(f"  {iso3}: 0 docs (totalCount={data.get('totalCount')})")
            time.sleep(REQUEST_PAUSE_SEC)
            continue

        country_dir = OUT_DIR / iso3
        country_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for item in items:
            if total_saved >= GLOBAL_CAP:
                break
            fields = item.get("fields", {}) or {}
            fields.setdefault("id", item.get("id"))
            rec = record_from(fields, iso3, ctx)

            fname = f"{rec['date']}_{rec['id']}.json"
            (country_dir / fname).write_text(
                json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

            body_lengths.append(len(rec["body"]))
            all_dates.append(rec["date"])
            if iso3 == "SDN" and len(sdn_samples) < 2:
                sdn_samples.append((rec["title"] or "(no title)", rec["body"]))
            count += 1
            total_saved += 1

        saved_per_country[iso3] = count
        print(f"  {iso3}: saved {count} "
              f"(totalCount={data.get('totalCount')})")
        time.sleep(REQUEST_PAUSE_SEC)

    # --- Summary -----------------------------------------------------------
    print("\n" + "=" * 60)
    print("ACQUISITION SUMMARY")
    print("=" * 60)
    print(f"Total docs saved: {total_saved}  "
          f"(across {len(saved_per_country)} countries)")

    print("\nDocs per country:")
    for iso3 in FOCUS_COUNTRIES:
        if iso3 in saved_per_country:
            print(f"  {iso3}: {saved_per_country[iso3]}")
    if skipped:
        print(f"\nSkipped / empty ({len(skipped)}):")
        for iso3, reason in skipped:
            print(f"  {iso3}: {reason}")

    dated = sorted(d for d in all_dates if d != "undated")
    if dated:
        n_undated = sum(1 for d in all_dates if d == "undated")
        print(f"\nDate-range coverage: {dated[0]} .. {dated[-1]}"
              + (f"  ({n_undated} undated)" if n_undated else ""))
        year_hist = Counter(d[:4] for d in dated)
        print("  by year: " + ", ".join(
            f"{y}:{year_hist[y]}" for y in sorted(year_hist)))

    if body_lengths:
        body_lengths.sort()
        n = len(body_lengths)
        def pct(p: float) -> int:
            return body_lengths[min(n - 1, int(p * n))]
        stubs = sum(1 for b in body_lengths if b < 500)
        print(f"\nBody-length distribution (chars, n={n}):")
        print(f"  min={body_lengths[0]}  p25={pct(0.25)}  median={pct(0.50)}  "
              f"p75={pct(0.75)}  p90={pct(0.90)}  max={body_lengths[-1]}")
        print(f"  mean={sum(body_lengths)//n}  "
              f"empty(0 chars)={sum(1 for b in body_lengths if b == 0)}  "
              f"stubs(<500 chars)={stubs}")
        if stubs > n * 0.5:
            print("  FLAG: >50% of docs are <500 chars — bodies may be "
                  "truncated/boilerplate; revisit the query (profile/fields).")

    # --- Quality check: SDN ------------------------------------------------
    print("\n" + "-" * 60)
    print("QUALITY CHECK — first country (SDN), 2 sample docs:")
    print("-" * 60)
    if not sdn_samples:
        print("  No SDN docs were saved — cannot run the body sanity check.")
        print("  FLAG: investigate SDN query (it should be a high-volume "
              "country).")
    else:
        for i, (title, body) in enumerate(sdn_samples, 1):
            head = " ".join((body or "").split())[:200]
            print(f"  [{i}] title: {title}")
            print(f"      body[:200]: {head!r}")
            print(f"      body length: {len(body)} chars")
        if all(len(b) < 200 for _, b in sdn_samples):
            print("\n  FLAG: SDN sample bodies are < 200 chars / empty. The API "
                  "query may need adjustment (check profile='full' and that "
                  "'body' is in fields.include).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
