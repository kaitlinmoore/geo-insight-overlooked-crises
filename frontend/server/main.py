"""
Geo-Insight FastAPI backend — SKELETON ONLY.

This server will eventually:
  - read Gold tables via the Databricks SQL Connector (Triage, Crisis Explorer,
    Methodology, Compare, CBPF)
  - proxy the Ask screen to the Mosaic AI supervisor agent's Model Serving
    endpoint (and stream Genie REST responses back)

None of that is wired yet. This scaffolding session ships a single health-check
route so the Vite dev-server proxy (/api -> 127.0.0.1:8000) has something to hit.

Run locally:
    cd frontend/server
    python -m venv .venv && .venv\\Scripts\\activate   # Windows
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Geo-Insight API", version="0.1.0")

# Vite dev server origin. In the deployed Databricks App the frontend is served
# same-origin, so CORS is only needed for local development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness check. The only route wired in the scaffolding session."""
    return {"status": "ok", "service": "geo-insight-api", "version": "0.1.0"}


# --- NOT YET IMPLEMENTED (next integration session) -------------------------
# @app.get("/api/rankings/top")        -> SELECT FROM gold_forgotten_crisis_index
# @app.get("/api/crisis/{iso3}")       -> parallel Gold reads for Crisis Explorer
# @app.post("/api/ask")                -> forward to supervisor agent / Genie REST
# See frontend/README.md "Next integration session" for the contract.
