# Geo-Insight Frontend

The React command center for identifying the world's most overlooked
humanitarian crises. Six screens over (eventually) Databricks Gold tables and a
Mosaic AI supervisor agent. **Current state: real API contract + real Recharts
visualizations against mocked data.** No Databricks connectivity yet — a FastAPI
backend serves fixtures whose shapes match the future Gold tables, so swapping in
the Databricks SQL Connector later is mechanical.

## Stack

| Concern | Choice | Version (pinned in `package.json`) |
|---|---|---|
| Build tool | Vite | ^5.4 |
| UI runtime | React | ^18.3 |
| Language | TypeScript (strict) | ~5.6 |
| Styling | Tailwind CSS | ^3.4 |
| Primitives | shadcn/ui (new-york, CSS variables) | vendored in `src/components/ui` |
| Data fetching | @tanstack/react-query | ^5.59 |
| Charts | recharts | ^2.13 |
| Routing | react-router-dom | ^6.27 |
| Maps | react-map-gl (maplibre) + maplibre-gl | ^7.1 / ^4.7 |
| Icons | lucide-react | ^0.451 |
| Backend | FastAPI + Pydantic v2 (`server/`) | see `server/requirements.txt` |

**Package manager: npm** (`package-lock.json` committed).

## Install & run (two processes)

The app calls `/api/*`; the Vite dev server proxies those to FastAPI on `:8000`.
Run both:

```powershell
# 1) backend
cd frontend/server
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 2) frontend (separate terminal)
cd frontend
npm install
npm run dev          # http://localhost:5173
```

The proxy is configured in `vite.config.ts` (`/api` → `http://127.0.0.1:8000`).
In the deployed Databricks App the two are served same-origin, so no proxy is
needed in production.

Other scripts: `npm run build` (strict `tsc -b` + vite build), `npm run
typecheck`, `npm run preview`.

## Routes

| Route | Screen | Persona | Data source |
|---|---|---|---|
| `/` | Triage | HC | `GET /api/v1/rankings` (+ sparklines from `score_history`) |
| `/crisis/:iso3` | Crisis Explorer | HAO | `GET /api/v1/crisis/{iso3}` |
| `/compare` | Compare | HAO | `GET /api/v1/compare?countries=A,B,C` |
| `/ask` | Ask | HAO · HC | `POST /api/v1/ask` |
| `/methodology` | Methodology | All | `GET /api/v1/methodology/{composite-weights,cascade-distribution}` |
| `/cbpf` | CBPF Allocation View | PFM | `GET /api/v1/cbpf/funds` |

## API endpoints (all under `/api/v1/`)

| Method · Path | Response model |
|---|---|
| `GET /rankings?year&scope&region` | `RankingsResponse` |
| `GET /crisis/{iso3}?year` | `CrisisDetail` |
| `GET /crisis/{iso3}/hotspots?since` | `HotspotsResponse` |
| `GET /compare?countries=A,B,C` (or repeated `?iso3=`) | `CompareResponse` |
| `POST /ask` `{question}` | `AskExchange` |
| `GET /methodology/cascade-distribution` | `CascadeResponse` |
| `GET /methodology/composite-weights` | `CompositeWeightsResponse` |
| `GET /cbpf/funds?year` | `CbpfResponse` |
| `GET /changes?since` | `ChangesResponse` |
| `GET /api/health` | liveness |

Pydantic models live in `server/models.py`; fixtures in `server/mock_data.py`.

## What's real vs. mocked

**Real (works now):**
- TanStack Query fetch layer (`src/lib/api.ts`) against the FastAPI endpoints,
  with loading (shadcn `Skeleton`), error, and success states on every screen.
- **Recharts visualizations**: Crisis Explorer sector-gap bar, funding funnel,
  multi-year trend (with 50% chronic reference line); Triage per-row score
  sparklines; Compare chronic-vs-acute quadrant scatter; CBPF reserve/standard
  allocation bars; Methodology composite-weights bars + cascade table.
- Deterministic decomposition card, rank+CI display, neglect badges, change
  indicators, region/mode filters.
- **Maps (MapLibre)**: Triage global admin0 choropleth (fill by neglect_class,
  hover tooltip, click → Crisis Explorer); Crisis Explorer admin1 choropleth
  (fill by overlooked_score) with ACLED hotspot circles. See **Maps** below.

**Mocked (placeholder boxes, labeled with the eventual viz):**
- Subnational fill values + ACLED hotspot counts are FABRICATED but keyed to
  REAL fieldmaps admin1 P-codes / interior points, so the join + geography are
  real; only the numbers are placeholders.
- Methodology bootstrap-CI and UFE/ECHO/NRC validation charts (need endpoints).
- KA narrative panel (Day-4 stretch).

**Not present (out of scope this session):**
- Databricks connectivity (SQL Connector, Genie REST, agent endpoint), credentials.
- Streaming Ask responses, MLflow trace links, feedback persistence.

All fixture numbers (`server/mock_data.py`) are **fabricated — do not cite.**

## Maps

Two MapLibre choropleths via `react-map-gl` (the `react-map-gl/maplibre`
entrypoint — no Mapbox token):

- `components/maps/TriageMap.tsx` — global **admin0** choropleth on the Triage
  hero. Loads `/maps/admin0.geojson`, joins rankings by `iso3`, fills each
  country by its `neglect_class` color (unranked → neutral). Hover tooltip;
  click navigates to `/crisis/{iso3}`.
- `components/maps/SubnationalMap.tsx` — **admin1** choropleth + ACLED hotspot
  overlay on Crisis Explorer. Loads `/maps/admin1/{iso3}.geojson`, joins
  `CrisisDetail.subnational[]` by `admin1_pcode` (fill by `overlooked_score`),
  overlays `GET /crisis/{iso3}/hotspots` as circles sized by event count and
  colored by recency.
- `components/maps/mapStyle.ts` — shared base style + color helpers.

**Base map style.** The default is an **offline, token-free background-only
style** (`EMPTY_DARK_STYLE`): a deep-slate canvas with no external tiles. The
choropleth polygons *are* the map. This was a deliberate choice — the app is
dark-first and targets a Databricks App that may have no network egress, so we
do not depend on MapLibre demotiles or OpenFreeMap at runtime. To add a basemap
later (needs egress), pass a style URL to the `<Map>` `mapStyle` prop instead,
e.g. `"https://tiles.openfreemap.org/styles/dark"`.

**GeoJSON source.** `src/acquisition/extract_geojson.py` reads the local
fieldmaps GeoParquet (`staging/fieldmaps_admin_boundaries.geoparquet`),
dissolves admin2 → admin0 / admin1, simplifies (topology-preserving), and writes
`public/maps/admin0.geojson`, `public/maps/admin1/{iso3}.geojson` (25 priority
countries), and `public/maps/admin1_centroids.json` (consumed by the FastAPI
mock to place hotspots and key subnational fixtures to real P-codes). The
outputs are committed; re-run the script only when boundaries change.

## The data contract

- `src/lib/types.ts` — the TypeScript contract (types only). Mirrors
  `server/models.py` field-for-field (snake_case both sides).
- `src/lib/mockData.ts` — now just `export * from "./types"` for backward-compat.
- `src/lib/api.ts` — typed `fetch()` client, one function per endpoint.
- `server/models.py` / `server/mock_data.py` — Pydantic contract + canonical fixtures.

Swapping mocks for Databricks: replace the builders in `mock_data.py` with SQL
Connector queries that return the same Pydantic models. The TypeScript side and
the screens do not change.

## Project layout

```
frontend/
├── vite.config.ts           # @ alias, /api → :8000 proxy
├── src/
│   ├── main.tsx             # RouterProvider + QueryClientProvider
│   ├── router.tsx           # 6 routes + crisis detail + 404
│   ├── lib/
│   │   ├── types.ts         # ← TS half of the data contract
│   │   ├── mockData.ts      # re-export of types.ts (compat shim)
│   │   ├── api.ts           # typed fetch client
│   │   ├── chartTheme.ts    # Recharts colors / formatters
│   │   └── utils.ts
│   ├── components/
│   │   ├── AppShell.tsx · Placeholder · NeglectBadge · ChangeIndicator · RankCI
│   │   ├── QueryState.tsx   # loading/error/success wrapper
│   │   ├── charts/          # ScoreSparkline, SectorGapChart, FundingFunnelChart,
│   │   │                    #   FundingTrendChart, CompareQuadrantChart
│   │   ├── maps/            # TriageMap, SubnationalMap, mapStyle (MapLibre)
│   │   └── ui/              # vendored shadcn primitives (+ skeleton)
│   └── screens/             # Triage, CrisisExplorer, Compare, Ask, Methodology, Cbpf, NotFound
└── server/
    ├── main.py              # FastAPI routes (/api/v1/*)
    ├── models.py            # Pydantic response/request models
    ├── mock_data.py         # canonical fixtures
    └── requirements.txt
```

## Next integration session, in order

1. **Ask → Genie REST** — replace the keyword-routed mock in `mock_data.ask_response`
   with a real Genie REST call; add streaming + MLflow trace links; persist
   thumbs feedback to a Delta table.
2. **Databricks SQL Connector data layer** — replace every builder in
   `server/mock_data.py` with Gold-table queries returning the same Pydantic
   models; add credentials via env vars (host, token, warehouse ID). Also add
   the missing methodology endpoints (bootstrap CIs, UFE/ECHO/NRC validation).
