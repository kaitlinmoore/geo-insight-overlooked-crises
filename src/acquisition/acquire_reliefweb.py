"""Acquire ReliefWeb situation reports / analyses / assessments into local staging.

Source: ReliefWeb API v2 (OCHA's humanitarian information portal).
  Endpoint: https://api.reliefweb.int/v2/reports
  Docs: https://apidoc.reliefweb.int

Two deliverables, mapped to the two project purposes:

  STAGE 1 - metadata index + media-attention signal  [REQUIRED for v1]
    Paginates the full list of matching reports per country across the lookback
    window and writes:
      ./staging/reliefweb_metadata.csv          (one row per report)
      ./staging/reliefweb_media_attention.csv   (iso3 x year_month -> report_count)
    The per-country x month count is the negative-weighted "attention" proxy in
    the composite overlooked-crises score.

  STAGE 2 - body-text corpus  [OPTIONAL, Day-4 Knowledge Assistant]
    Pulls up to PER_COUNTRY_LIMIT (20) most-recent docs per country (global cap
    GLOBAL_CAP=500), full body text, one JSON per doc:
      ./staging/reliefweb_docs/{iso3}/{date}_{id}.json

This is a one-off LOCAL acquisition into ./staging/ (gitignored); it does not
touch Databricks.

WHY THE API, NOT SCRAPING
-------------------------
The public HTML site (reliefweb.int) sits behind an AWS WAF JavaScript challenge
(every page returns HTTP 202 + `x-amzn-waf-action: challenge`; a plain HTTP
client never receives content). The v1 API is decommissioned (HTTP 410). The v2
API is the only viable, sanctioned path. See docs/notes/acquisition_reliefweb.md.

APPNAME REQUIREMENT (blocker if unset)
--------------------------------------
From 2025-11-01 the ReliefWeb API requires a *pre-approved* appname. An arbitrary
string returns HTTP 403. Request one via the form at
  https://apidoc.reliefweb.int/parameters#appname
(form suggests "<org>-<purpose>-<random>", e.g.
 geo-insight-hackathon-knowledge-assistant-7f3a). Then add to a repo-root .env:
  RELIEFWEB_APPNAME=...
An OS environment variable of the same name takes precedence.

USAGE
-----
  python acquire_reliefweb.py --check   # one request: verify the appname works
  python acquire_reliefweb.py           # full run: stage 1 then stage 2
  python acquire_reliefweb.py --stage1  # metadata + attention signal only
  python acquire_reliefweb.py --stage2  # body-text corpus only

STATUS: written and self-consistent, but NOT yet verified against the live API
(blocked on appname approval as of 2026-05-22). The response-shape handling
(facets aside; counts are derived from list rows) is defensive, but field names
and the format taxonomy strings should be confirmed on the first successful run.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# --- Configuration ---------------------------------------------------------
API_URL = "https://api.reliefweb.int/v2/reports"

CONTACT_EMAIL = "6ingeraffe@gmail.com"
USER_AGENT = f"Geo-Insight-UNOCHA-Hackathon/1.0 (contact: {CONTACT_EMAIL})"

# Top-25 focus list: overlooked focus + reference crises for demo contrast.
FOCUS_COUNTRIES = [
    "SDN", "YEM", "MMR", "BFA", "MLI", "NER", "TCD", "COD", "SSD", "COL",
    "VEN", "HTI", "AFG", "ETH", "SOM", "NGA", "SYR", "UKR", "PSE", "PHL",
    "HND", "GTM", "CMR", "CAF", "MOZ",
]

# Long-form country names for the metadata CSV (API also returns these; this is
# a local fallback so the CSV is populated even if a row lacks the field).
COUNTRY_NAMES = {
    "SDN": "Sudan", "YEM": "Yemen", "MMR": "Myanmar", "BFA": "Burkina Faso",
    "MLI": "Mali", "NER": "Niger", "TCD": "Chad",
    "COD": "Democratic Republic of the Congo", "SSD": "South Sudan",
    "COL": "Colombia", "VEN": "Venezuela", "HTI": "Haiti", "AFG": "Afghanistan",
    "ETH": "Ethiopia", "SOM": "Somalia", "NGA": "Nigeria",
    "SYR": "Syrian Arab Republic", "UKR": "Ukraine",
    "PSE": "occupied Palestinian territory", "PHL": "Philippines",
    "HND": "Honduras", "GTM": "Guatemala", "CMR": "Cameroon",
    "CAF": "Central African Republic", "MOZ": "Mozambique",
}

FORMATS = ["Situation Report", "Analysis", "Assessment"]
LOOKBACK_MONTHS = 36
PER_COUNTRY_LIMIT = 20            # stage 2 body-text cap per country
GLOBAL_CAP = 500                  # stage 2 global doc cap
PAGE_SIZE = 1000                  # v2 max page size for the stage-1 index
SCRAPER_VERSION = "1.0"

# Polite HTTP practice (the API has no published rate limit; we self-throttle).
MIN_INTERVAL_SEC = 1.0            # >= 1 request / second across the whole run
BACKOFF_START_SEC = 60           # exponential backoff base for 429 / 503
BACKOFF_MAX_RETRIES = 4
TIMEOUT_SEC = 60

# Date field used for filtering / bucketing. date.original = original publication
# date of the document; falls back to date.created in filename/bucket logic.
DATE_FIELD = "date.original"
# Country association used for attribution. country.iso3 = any tagged country
# (matches the public country-page semantics, more inclusive); switch to
# "primary_country.iso3" to count each report against a single country only.
COUNTRY_FIELD = "country.iso3"

REPO_ROOT = Path(__file__).resolve().parents[2]
STAGING = REPO_ROOT / "staging"
DOCS_DIR = STAGING / "reliefweb_docs"
METADATA_CSV = STAGING / "reliefweb_metadata.csv"
ATTENTION_CSV = STAGING / "reliefweb_media_attention.csv"

INCLUDE_FIELDS_LIST = [
    "id", "title", "url", "url_alias",
    "date.original", "date.created",
    "source.name", "source.shortname",
    "format.name", "language.name",
    "primary_country.iso3", "primary_country.name",
    "country.iso3", "country.name",
]
INCLUDE_FIELDS_FULL = INCLUDE_FIELDS_LIST + ["body", "body-html"]


# --- appname resolution ----------------------------------------------------
def load_appname() -> str:
    """Resolve RELIEFWEB_APPNAME from the OS env or a repo-root .env file."""
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


# --- polite HTTP layer -----------------------------------------------------
class Forbidden(Exception):
    """HTTP 403 - appname not approved; abort the whole run immediately."""


class PoliteClient:
    """A requests.Session wrapper: fixed User-Agent, >=1 req/sec spacing, and
    exponential backoff on 429/503. A 403 raises Forbidden (caller aborts)."""

    def __init__(self, appname: str):
        self.appname = appname
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._last_request_ts = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_ts
        if elapsed < MIN_INTERVAL_SEC:
            time.sleep(MIN_INTERVAL_SEC - elapsed)

    def post(self, body: dict) -> dict:
        backoff = BACKOFF_START_SEC
        for attempt in range(BACKOFF_MAX_RETRIES + 1):
            self._throttle()
            resp = self.session.post(
                API_URL, params={"appname": self.appname},
                json=body, timeout=TIMEOUT_SEC,
            )
            self._last_request_ts = time.monotonic()

            if resp.status_code == 403:
                raise Forbidden(resp.text[:300])
            if resp.status_code in (429, 503):
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


# --- shared helpers --------------------------------------------------------
def window() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    to = now.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    frm = (now - timedelta(days=LOOKBACK_MONTHS * 30)).strftime(
        "%Y-%m-%dT%H:%M:%S+00:00")
    return frm, to


def base_filter(iso3: str, date_from: str, date_to: str) -> dict:
    return {
        "operator": "AND",
        "conditions": [
            {"field": COUNTRY_FIELD, "value": iso3},
            {"field": "format.name", "value": FORMATS},
            {"field": "language.name", "value": "English"},
            {"field": "status", "value": "published"},
            {"field": DATE_FIELD, "value": {"from": date_from, "to": date_to}},
        ],
    }


def names(value) -> list[str]:
    if isinstance(value, list):
        return [v.get("name", "") for v in value if isinstance(v, dict)]
    if isinstance(value, dict):
        return [value.get("name", "")]
    return []


def fields_of(item: dict) -> dict:
    f = item.get("fields", {}) or {}
    f.setdefault("id", item.get("id"))
    return f


def pub_date(fields: dict) -> str:
    date = fields.get("date", {}) or {}
    raw = date.get("original") or date.get("created") or ""
    return raw[:10] if raw else "undated"


# --- STAGE 1: metadata index + media-attention counts ----------------------
def fetch_index_page(client: PoliteClient, iso3: str, frm: str, to: str,
                     offset: int) -> dict:
    return client.post({
        "limit": PAGE_SIZE,
        "offset": offset,
        "profile": "list",
        "sort": [f"{DATE_FIELD}:desc"],
        "filter": base_filter(iso3, frm, to),
        "fields": {"include": INCLUDE_FIELDS_LIST},
    })


def run_stage1(client: PoliteClient, frm: str, to: str) -> None:
    print("=" * 60)
    print("STAGE 1 - metadata index + media-attention signal")
    print("=" * 60)
    rows: list[dict] = []
    counts: dict[tuple[str, str], int] = defaultdict(int)  # (iso3, ym) -> n
    per_country_total: dict[str, int] = {}

    for iso3 in FOCUS_COUNTRIES:
        offset, total = 0, None
        before = len(rows)
        while True:
            try:
                data = fetch_index_page(client, iso3, frm, to, offset)
            except Forbidden:
                raise
            except requests.RequestException as e:
                print(f"  {iso3}: {type(e).__name__} at offset {offset} "
                      f"- partial, moving on")
                break
            total = data.get("totalCount", 0)
            items = data.get("data", []) or []
            if not items:
                break
            for it in items:
                f = fields_of(it)
                date = pub_date(f)
                rows.append({
                    "iso3": iso3,
                    "country_name": COUNTRY_NAMES.get(iso3, iso3),
                    "title": f.get("title", ""),
                    "publication_date": date,
                    "format": "; ".join(names(f.get("format"))),
                    "source_organization": "; ".join(names(f.get("source"))),
                    "report_url": f.get("url") or f.get("url_alias") or "",
                })
                if date != "undated":
                    counts[(iso3, date[:7])] += 1
            offset += len(items)
            if offset >= (total or 0):
                break
        n = len(rows) - before
        per_country_total[iso3] = n
        print(f"  {iso3}: {n} reports (totalCount={total})")

    METADATA_CSV.parent.mkdir(parents=True, exist_ok=True)
    with METADATA_CSV.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "iso3", "country_name", "title", "publication_date",
            "format", "source_organization", "report_url"])
        w.writeheader()
        w.writerows(rows)

    with ATTENTION_CSV.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["iso3", "year_month", "report_count"])
        for (iso3, ym) in sorted(counts):
            w.writerow([iso3, ym, counts[(iso3, ym)]])

    print(f"\n  wrote {len(rows)} rows -> {METADATA_CSV.name}")
    print(f"  wrote {len(counts)} (country x month) cells -> {ATTENTION_CSV.name}")
    zero = [c for c in FOCUS_COUNTRIES if per_country_total.get(c, 0) == 0]
    if zero:
        print(f"  SUSPICIOUS: zero reports for {zero} - investigate "
              f"(high-volume crises should not be empty)")


# --- STAGE 2: body-text corpus ---------------------------------------------
def fetch_bodies(client: PoliteClient, iso3: str, frm: str, to: str) -> dict:
    return client.post({
        "limit": PER_COUNTRY_LIMIT,
        "profile": "full",
        "sort": [f"{DATE_FIELD}:desc"],
        "filter": base_filter(iso3, frm, to),
        "fields": {"include": INCLUDE_FIELDS_FULL},
    })


def doc_record(fields: dict, iso3: str, acquired_at: str) -> dict:
    primary = fields.get("primary_country", {}) or {}
    if isinstance(primary, list):
        primary = primary[0] if primary else {}
    body = fields.get("body", "") or ""
    return {
        "iso3": primary.get("iso3", iso3) or iso3,
        "country_name": primary.get("name") or COUNTRY_NAMES.get(iso3, iso3),
        "title": fields.get("title"),
        "publication_date": pub_date(fields),
        "format": (names(fields.get("format")) or [""])[0],
        "source_organization": names(fields.get("source")),
        "report_url": fields.get("url") or fields.get("url_alias"),
        "body_text": body,
        "body_word_count": len(body.split()),
        "scraped_at": acquired_at,
        "scraper_version": SCRAPER_VERSION,
        # extra context (not in the brief's schema, but cheap to keep):
        "report_id": fields.get("id"),
        "body_html": fields.get("body-html", "") or "",
        "all_countries": names(fields.get("country")),
    }


def run_stage2(client: PoliteClient, frm: str, to: str) -> None:
    print("\n" + "=" * 60)
    print("STAGE 2 - body-text corpus")
    print("=" * 60)
    acquired_at = datetime.now(timezone.utc).isoformat()
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    per_country: dict[str, int] = {}
    skipped: list[tuple[str, str]] = []
    word_counts: list[int] = []
    samples: dict[str, tuple[str, str]] = {}  # iso3 -> (title, body) for SDN/YEM
    total = 0

    for iso3 in FOCUS_COUNTRIES:
        if total >= GLOBAL_CAP:
            skipped.append((iso3, "global cap reached"))
            continue
        try:
            data = fetch_bodies(client, iso3, frm, to)
        except Forbidden:
            raise
        except requests.RequestException as e:
            skipped.append((iso3, type(e).__name__))
            print(f"  {iso3}: {type(e).__name__} - skipped")
            continue

        items = data.get("data", []) or []
        if not items:
            skipped.append((iso3, "no docs"))
            print(f"  {iso3}: 0 docs (totalCount={data.get('totalCount')})")
            continue

        cdir = DOCS_DIR / iso3
        cdir.mkdir(parents=True, exist_ok=True)
        n = 0
        for it in items:
            if total >= GLOBAL_CAP:
                break
            rec = doc_record(fields_of(it), iso3, acquired_at)
            (cdir / f"{rec['publication_date']}_{rec['report_id']}.json").write_text(
                json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
            word_counts.append(rec["body_word_count"])
            if iso3 in ("SDN", "YEM") and iso3 not in samples:
                samples[iso3] = (rec["title"] or "(no title)", rec["body_text"])
            n += 1
            total += 1
        per_country[iso3] = n
        print(f"  {iso3}: saved {n} (totalCount={data.get('totalCount')})")

    stage2_summary(per_country, skipped, word_counts, samples, total)


def stage2_summary(per_country, skipped, word_counts, samples, total) -> None:
    print("\n" + "-" * 60)
    print(f"Stage 2 total docs: {total} across {len(per_country)} countries")
    if skipped:
        print("Skipped / empty:")
        for iso3, reason in skipped:
            print(f"  {iso3}: {reason}")
    if word_counts:
        word_counts.sort()
        n = len(word_counts)
        def pct(p): return word_counts[min(n - 1, int(p * n))]
        short = sum(1 for w in word_counts if w < 100)
        print(f"\nBody word-count distribution (n={n}):")
        print(f"  min={word_counts[0]}  p25={pct(.25)}  median={pct(.50)}  "
              f"p75={pct(.75)}  p90={pct(.90)}  max={word_counts[-1]}")
        print(f"  empty={sum(1 for w in word_counts if w == 0)}  "
              f"short(<100 words)={short}")
    print("\nQuality check - most recent SDN & YEM doc (first 200 chars):")
    for iso3 in ("SDN", "YEM"):
        if iso3 in samples:
            title, body = samples[iso3]
            head = " ".join((body or "").split())[:200]
            print(f"  [{iso3}] {title}")
            print(f"        {head!r}")
        else:
            print(f"  [{iso3}] no doc saved - investigate (high-volume country)")


# --- check mode ------------------------------------------------------------
def run_check(client: PoliteClient) -> int:
    print(f"Checking appname against {API_URL} ...")
    try:
        data = client.post({"limit": 1, "profile": "list",
                            "fields": {"include": ["id", "title"]}})
    except Forbidden as e:
        print("  FAIL (HTTP 403): appname not approved.")
        print(f"  {e}")
        print("  Request approval: https://apidoc.reliefweb.int/parameters#appname")
        return 2
    except requests.RequestException as e:
        print(f"  FAIL ({type(e).__name__}): {e}")
        return 1
    print(f"  OK - appname accepted. API totalCount={data.get('totalCount')}.")
    return 0


# --- main ------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Acquire ReliefWeb reports (v2 API).")
    ap.add_argument("--check", action="store_true",
                    help="verify the appname with one request, then exit")
    ap.add_argument("--stage1", action="store_true",
                    help="metadata index + media-attention signal only")
    ap.add_argument("--stage2", action="store_true",
                    help="body-text corpus only")
    args = ap.parse_args()

    appname = load_appname()
    if not appname:
        print("ERROR: RELIEFWEB_APPNAME is not set.", file=sys.stderr)
        print("The ReliefWeb v2 API requires a PRE-APPROVED appname "
              "(since 2025-11-01).", file=sys.stderr)
        print("  1. Request one: https://apidoc.reliefweb.int/parameters#appname",
              file=sys.stderr)
        print("  2. Add to a repo-root .env:  RELIEFWEB_APPNAME=...", file=sys.stderr)
        print("  3. Re-run.", file=sys.stderr)
        return 2

    client = PoliteClient(appname)
    if args.check:
        return run_check(client)

    frm, to = window()
    print(f"ReliefWeb v2 acquisition | window {frm[:10]} .. {to[:10]} "
          f"({LOOKBACK_MONTHS} months)")
    print(f"User-Agent: {USER_AGENT}\n")

    do_stage1 = args.stage1 or not args.stage2
    do_stage2 = args.stage2 or not args.stage1
    try:
        if do_stage1:
            run_stage1(client, frm, to)
        if do_stage2:
            run_stage2(client, frm, to)
    except Forbidden as e:
        print(f"\nABORTED: HTTP 403 - appname not approved.\n  {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
