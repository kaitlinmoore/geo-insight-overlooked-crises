"""
Geo-Insight FastAPI backend.

Serves the React frontend's data contract under /api/v1/. In THIS session every
endpoint returns fixtures from `mock_data.py` — no Databricks connectivity. The
later integration session swaps the mock_data builders for Databricks SQL
Connector queries (and /api/v1/ask for the Genie REST API); response shapes,
defined by the Pydantic models in `models.py`, do not change.

Run locally:
    cd frontend/server
    python -m venv .venv && .venv\\Scripts\\activate   # Windows
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000

The Vite dev server proxies /api/* to http://127.0.0.1:8000 (see vite.config.ts).
"""

from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

import mock_data as mock
from models import (
    AskExchange,
    AskRequest,
    CascadeResponse,
    CbpfResponse,
    ChangesResponse,
    CompareResponse,
    CompositeWeightsResponse,
    CrisisDetail,
    RankingsResponse,
)

app = FastAPI(title="Geo-Insight API", version="0.2.0")

# CORS only matters for local dev (Vite on :5173). In the deployed Databricks
# App the frontend is served same-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness check."""
    return {"status": "ok", "service": "geo-insight-api", "version": "0.2.0"}


# --- Triage ----------------------------------------------------------------

@app.get("/api/v1/rankings", response_model=RankingsResponse)
def get_rankings(
    year: int = 2026,
    scope: str = Query("global", pattern="^(global|region|country)$"),
    region: str | None = None,
) -> RankingsResponse:
    """Ranked overlooked-crisis list for the Triage screen."""
    return mock.rankings_response(year=year, scope=scope, region=region)


@app.get("/api/v1/changes", response_model=ChangesResponse)
def get_changes(since: str = "2025-Q4") -> ChangesResponse:
    """Rank-delta / NEW-to-top-10 change indicators since a prior period."""
    return mock.changes_response(since=since)


# --- Crisis Explorer -------------------------------------------------------

@app.get("/api/v1/crisis/{iso3}", response_model=CrisisDetail)
def get_crisis(iso3: str, year: int = 2026) -> CrisisDetail:
    """Full Crisis Explorer detail (ranking + sectors + funnel + trend + subnational)."""
    detail = mock.crisis_detail(iso3)
    if detail is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"No crisis data for '{iso3}'")
    return detail


# --- Compare ----------------------------------------------------------------

@app.get("/api/v1/compare", response_model=CompareResponse)
def get_compare(
    iso3: list[str] | None = Query(default=None),
    countries: str | None = None,
) -> CompareResponse:
    """Comparison data for 2–4 countries. Accepts repeated ?iso3= or ?countries=A,B,C."""
    isos: list[str] = []
    if iso3:
        isos = iso3
    elif countries:
        isos = [c.strip() for c in countries.split(",") if c.strip()]
    if not isos:
        isos = ["SDN", "COD", "BFA"]
    return mock.compare_response(isos)


# --- Ask (Genie custom chat UI) --------------------------------------------

@app.post("/api/v1/ask", response_model=AskExchange)
def post_ask(body: AskRequest) -> AskExchange:
    """Mocked Genie exchange: keyword-routed canned SQL + result + NL answer."""
    return mock.ask_response(body.question)


# --- Methodology -----------------------------------------------------------

@app.get("/api/v1/methodology/cascade-distribution", response_model=CascadeResponse)
def get_cascade() -> CascadeResponse:
    """Multi-country flow allocation cascade shares (transparency table)."""
    return mock.cascade_response()


@app.get("/api/v1/methodology/composite-weights", response_model=CompositeWeightsResponse)
def get_weights() -> CompositeWeightsResponse:
    """The seven composite weights with brief rationales."""
    return mock.composite_weights_response()


# --- CBPF Allocation View --------------------------------------------------

@app.get("/api/v1/cbpf/funds", response_model=CbpfResponse)
def get_cbpf(year: int = 2026) -> CbpfResponse:
    """Fund-level CBPF allocations (reserve/standard windows; no sector breakdown by design)."""
    return mock.cbpf_response(year=year)
