# Geo-Insight Frontend

The React command center for identifying the world's most overlooked
humanitarian crises. Six screens over Databricks Gold tables and a Mosaic AI
supervisor agent. **This is a scaffold** — real visualizations and Databricks
integration land in the next session. Everything renders against mocked data.

## Stack

| Concern | Choice | Version (pinned in `package.json`) |
|---|---|---|
| Build tool | Vite | ^5.4 |
| UI runtime | React | ^18.3 (React 18, per spec) |
| Language | TypeScript (strict) | ~5.6 |
| Styling | Tailwind CSS | ^3.4 |
| Primitives | shadcn/ui (new-york style, CSS variables) | Radix-based, vendored in `src/components/ui` |
| Routing | react-router-dom | ^6.27 |
| Charts (installed, not yet used) | recharts | ^2.13 |
| Maps (installed, not yet used) | react-map-gl + maplibre-gl | ^7.1 / ^4.7 |
| Icons | lucide-react | ^0.451 |
| Backend | FastAPI (`server/`) | see `server/requirements.txt` |

**Package manager: npm.** pnpm was not installed on the build machine; npm is
the committed choice (`package-lock.json`). Switching to pnpm later is a
`pnpm import` away if desired.

**shadcn setup approach:** initialized manually rather than via `npx shadcn init`
(no interactive prompt in this environment). `components.json` is present so the
shadcn CLI can add further primitives later (`npx shadcn@latest add <name>`).
The base primitives used by the shells (button, card, badge, separator, tabs,
select, tooltip) are vendored in `src/components/ui/`.

## Install & run

```powershell
cd frontend
npm install
npm run dev          # Vite dev server at http://localhost:5173
```

Other scripts:

```powershell
npm run build        # tsc -b (strict typecheck) + vite production build
npm run typecheck    # tsc --noEmit only
npm run preview      # serve the production build
```

The backend (optional during scaffolding — only `/api/health` exists) runs
separately; see [`server/README.md`](server/README.md). The Vite dev server
proxies `/api/*` to `http://127.0.0.1:8000`.

## Routes

| Route | Screen | Primary persona | Purpose |
|---|---|---|---|
| `/` | Triage | HC | Global map hero + ranked overlooked-crisis list with change indicators, region filters, and a current-mismatch ↔ structural-neglect toggle. |
| `/crisis/:iso3` | Crisis Explorer | HAO | Country deep-dive: deterministic decomposition card, subnational severity, sector coverage, multi-year funding trend, optional KA narrative panel. |
| `/compare` | Compare | HAO | 2–4 countries side-by-side, metrics aligned on a shared scale. |
| `/ask` | Ask | HAO · HC | Custom Genie chat UI: question → generated SQL → result table → cited NL answer, with thumbs feedback. |
| `/methodology` | Methodology | All | Composite formula, bootstrap CI viz, UFE/ECHO/NRC validation, RAI scorecard, sector explorer. |
| `/cbpf` | CBPF Allocation View | PFM | *Optional.* Fund-scoped ranking + allocations-vs-overlookedness, factual framing only. |

## What's mocked vs. real

**Real (works now):**
- Routing, the app shell (nav, breadcrumb, content slot), theming.
- Triage ranked list — real DOM rendering mocked rows, region filter, rank
  mode toggle, change indicators, rank+CI display, neglect-class badges.
- Crisis Explorer decomposition card, sector bars, subnational list — real DOM
  off the mocked `CrisisDetail` shape.
- Ask screen renders a full mocked exchange (question/SQL/result/answer).

**Mocked (placeholder boxes labeled with the eventual viz):**
- All maps (global choropleth, subnational choropleth, ACLED hotspots).
- All Recharts visualizations (funding trend, validation, bootstrap CIs,
  sector heatmap, CBPF scatter).
- ACLED point data is **not** mocked (too much shape) — placeholder only.

**Not present (out of scope this session):**
- Any Databricks connectivity (SQL Connector, Genie REST, agent endpoint).
- Credential/env wiring.
- Streaming responses, MLflow trace links, feedback persistence.

The mocked numbers in `src/lib/mockData.ts` are **fabricated and must not be
cited.** They exist only to exercise realistic data shapes.

## The data contract

`src/lib/mockData.ts` is the single source of truth for the shapes the screens
expect. Its TypeScript types mirror the Gold tables in `docs/architecture.md`
and the methodology vocabulary in `docs/methodology.md` (overlooked_score,
rank_position + rank_ci_low/high, percentile-ranked components, neglect_class,
change indicators, sector gaps, subnational rows). Every field is commented.
The next session swaps the fixtures for live data **without changing the types**.

## Project layout

```
frontend/
├── index.html               # dark-mode root
├── package.json             # npm, React 18 pinned
├── vite.config.ts           # @ alias, /api proxy to FastAPI
├── tailwind.config.ts       # shadcn theme tokens + semantic accents
├── components.json          # shadcn CLI config
├── tsconfig*.json           # strict mode, project references
├── src/
│   ├── main.tsx             # RouterProvider entry
│   ├── router.tsx           # 6 routes + crisis detail + 404
│   ├── index.css            # shadcn CSS variables (dark-first palette)
│   ├── lib/
│   │   ├── mockData.ts      # ← THE DATA CONTRACT (types + fixtures)
│   │   └── utils.ts         # cn() helper
│   ├── components/
│   │   ├── AppShell.tsx      # nav + breadcrumb + content slot
│   │   ├── Placeholder.tsx   # labeled viz placeholder
│   │   ├── NeglectBadge.tsx  # neglect_class chip
│   │   ├── ChangeIndicator.tsx
│   │   ├── RankCI.tsx        # honest "#2 [#1–3]" rank display
│   │   └── ui/               # vendored shadcn primitives
│   └── screens/
│       ├── TriageScreen.tsx
│       ├── CrisisExplorerScreen.tsx
│       ├── CompareScreen.tsx
│       ├── AskScreen.tsx
│       ├── MethodologyScreen.tsx
│       ├── CbpfScreen.tsx
│       └── NotFoundScreen.tsx
└── server/                  # FastAPI skeleton (health-check only)
```

## Next integration session, in order

1. **Stand up the FastAPI data layer.** Implement `/api/rankings/top`,
   `/api/crisis/{iso3}`, etc. against the Databricks SQL Connector. Add
   credentials via env vars (host, token, warehouse ID).
2. **Replace mock fixtures with a fetch layer.** Keep the `mockData.ts` types;
   add a thin API client that returns the same types. Screens shouldn't change.
3. **Wire the maps.** Global choropleth (admin0 percentile) on Triage and
   admin1 choropleth on Crisis Explorer, using react-map-gl + MapLibre against
   fieldmaps.io boundaries. Add the ACLED hotspot overlay.
4. **Wire Recharts.** Funding trend, sector breakdown, bootstrap-CI viz,
   validation charts, CBPF scatter.
5. **Wire the Ask screen** to the Genie REST API via `/api/ask`, with streaming
   and the generated-SQL/result/answer rendering already stubbed here. Persist
   thumbs feedback to a Delta table.
6. **Methodology screen** reads real Gold tables via the SQL Connector and
   surfaces MLflow eval results for the RAI scorecard.
7. **Package as a Databricks App** (`databricks.yml`) declaring the Model
   Serving endpoint, SQL warehouse, and Gold-table dependencies.
