# Geo-Insight backend (FastAPI)

Skeleton backend for the Geo-Insight command center. **Health-check only** in
the scaffolding phase — no Databricks connectivity yet.

## Run locally

```powershell
cd frontend/server
python -m venv .venv
.venv\Scripts\activate          # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Verify: `curl http://127.0.0.1:8000/api/health` → `{"status":"ok",...}`.

## How the dev proxy works

`frontend/vite.config.ts` proxies any request to `/api/*` to
`http://127.0.0.1:8000`. So during local development you run **two** processes:

1. `npm run dev` in `frontend/` (Vite, port 5173)
2. `uvicorn main:app --port 8000` in `frontend/server/`

The React app calls `fetch("/api/health")` and Vite forwards it to FastAPI.
In the deployed Databricks App the two are served same-origin, so no proxy is
needed in production.

## What the next session adds here

- Databricks SQL Connector reads of Gold tables, exposed as `/api/rankings/top`,
  `/api/crisis/{iso3}`, etc. (the "direct SQL" data-access pattern).
- `/api/ask` forwarding to the Mosaic AI supervisor agent / Genie REST API
  (the "agent calls" pattern), streaming responses back to the Ask screen.
- Credential handling via environment variables (Databricks host, token,
  warehouse ID) — never hardcoded.
