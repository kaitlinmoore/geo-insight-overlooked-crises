# Frontend scaffolding report

> Session: React frontend scaffolding (utility task; no `STATE.md`/`DECISIONS.md`
> edits per the scope carve-out in `claude.md`). Produced 2026-05-22.
> Build verified: `npm run build` (strict tsc + vite) passes; dev server boots
> and renders all six routes with no console errors (only React Router v7
> future-flag warnings, which are benign).

## 1. What was scaffolded

A Vite + React 18 + TypeScript (strict) app under `frontend/`, with Tailwind +
shadcn/ui, routing for the six screens, a shared app shell, mocked-data screen
shells, a FastAPI health-check backend, and a documented data contract.

### File tree

```
frontend/
├── index.html                 # dark-mode root (<html class="dark">)
├── package.json               # npm; React 18 pinned
├── package-lock.json
├── vite.config.ts             # @ alias; /api -> 127.0.0.1:8000 proxy
├── postcss.config.js
├── tailwind.config.ts         # shadcn tokens + semantic accents (chronic/acute/…)
├── components.json            # shadcn CLI config (new-york, CSS vars)
├── tsconfig.json / .app.json / .node.json   # strict, project references
├── .gitignore
├── src/
│   ├── main.tsx               # RouterProvider entry
│   ├── router.tsx             # 6 routes + /crisis/:iso3 + 404
│   ├── index.css              # shadcn CSS variables, dark-first palette
│   ├── vite-env.d.ts
│   ├── lib/
│   │   ├── mockData.ts        # ← DATA CONTRACT: types + fabricated fixtures
│   │   └── utils.ts           # cn()
│   ├── components/
│   │   ├── AppShell.tsx       # top nav + breadcrumb + <Outlet/>
│   │   ├── Placeholder.tsx    # labeled "[…viz…]" box
│   │   ├── NeglectBadge.tsx   # neglect_class chip
│   │   ├── ChangeIndicator.tsx# ↑5 / NEW / ↓3 / —
│   │   ├── RankCI.tsx         # honest "#2 [#1–3]" display
│   │   └── ui/                # vendored shadcn: button, card, badge,
│   │                          #   separator, tabs, select, tooltip
│   └── screens/
│       ├── TriageScreen.tsx           # real DOM ranked list + map placeholder
│       ├── CrisisExplorerScreen.tsx   # real DOM decomposition card + shells
│       ├── CompareScreen.tsx
│       ├── AskScreen.tsx              # full mocked Genie exchange
│       ├── MethodologyScreen.tsx
│       ├── CbpfScreen.tsx
│       └── NotFoundScreen.tsx
└── server/                    # FastAPI skeleton
    ├── main.py                # GET /api/health only
    ├── requirements.txt       # fastapi + uvicorn (no Databricks deps yet)
    └── README.md

# Repo-root addition:
.claude/launch.json            # preview/dev-server config (npm --prefix frontend run dev)
```

### Route table

| Route | Component | Persona | What it does |
|---|---|---|---|
| `/` | TriageScreen | HC | Global choropleth placeholder hero + ranked list (real DOM, mocked rows), region filter pills, current-mismatch ↔ structural-neglect toggle, change indicators, rank+CI, neglect badges. |
| `/crisis/:iso3` | CrisisExplorerScreen | HAO | Deterministic decomposition card (real DOM bars off mocked components), subnational severity list + choropleth placeholder, sector coverage bars, funding-trend placeholder, dormant KA narrative panel. |
| `/compare` | CompareScreen | HAO | 2–4 country fixed selection, metrics on shared 0–1 scale (real DOM), trend overlay placeholder. |
| `/ask` | AskScreen | HAO·HC | Custom chat UI: question → generated SQL block → result table → cited NL answer + thumbs feedback. One mocked exchange. |
| `/methodology` | MethodologyScreen | All | Composite formula, bootstrap-CI placeholder, validation placeholder, RAI scorecard (7 judges listed), sector-explorer placeholder. |
| `/cbpf` | CbpfScreen | PFM | Optional. Fund header, allocations table with rank+CI, allocations-vs-overlookedness scatter placeholder. |
| `*` | NotFoundScreen | — | Fallback. |

### Key component shells

- `AppShell` — sticky top nav (Triage/Compare/Ask/Methodology/CBPF; Crisis
  Explorer is reached by drill-in, not a nav item), breadcrumb row with a
  persistent "mocked data · not for citation" marker, content `<Outlet/>`.
- `RankCI` — enforces the honesty rule: rank never shown without its bootstrap
  CI; wide CIs colored as warning, `stable_top_n` colored as confidence.
- `Placeholder` — every un-built viz is a dashed box whose label names the chart
  type, the data shape, and the library (e.g. "[Global choropleth map] · admin0
  overlooked_score percentile · MapLibre + react-map-gl").

## 2. Stack-version choices

- **Vite** ^5.4 (5.4.21 resolved). Did not go to Vite 6 to stay on the
  well-trodden React 18 path.
- **React** ^18.3.1 — spec said React 18, so pinned 18 rather than letting a
  fresh scaffold pull React 19.
- **TypeScript** ~5.6, **strict: true**, plus `noUnusedLocals`/
  `noUnusedParameters`/`noFallthroughCasesInSwitch`. Build runs `tsc -b` first.
- **Tailwind** ^3.4 (not v4) — shadcn/ui's CSS-variable theming is documented
  against Tailwind 3; avoids v4 friction.
- **shadcn/ui** — `new-york` style, `cssVariables: true`, base color slate.
  Initialized **manually** (no interactive `npx shadcn init` available here);
  `components.json` present so `npx shadcn@latest add …` works going forward.
  Seven primitives vendored.
- **Package manager: npm.** pnpm was not installed on the machine; npm chosen
  and `package-lock.json` committed. Noted in the frontend README.
- recharts ^2.13, react-map-gl ^7.1, maplibre-gl ^4.7, react-router-dom ^6.27
  installed. recharts/react-map-gl/maplibre are installed but **not imported**
  anywhere yet (per "install, don't activate visually").

## 3. mockData.ts TypeScript types (verbatim)

```ts
export type NeglectClass =
  | "chronic_neglect"        // chronic_years_count >= 3 in last 5
  | "acute_deterioration"   // <3 chronic years but current gap_ratio >= 0.5
  | "improving"             // gap_ratio decreasing, current <= 0.3
  | "well_funded"           // chronic_years_count = 0 AND current gap_ratio <= 0.3
  | "chronic_no_plan";      // no HRP 3+ yrs but INFORM >= 3 / PIN >= 100k

export type ChangeDirection = "up" | "down" | "new" | "same";

export type ComponentKey =
  | "gap_ratio"
  | "severity_rate"
  | "dollars_per_pin_inv"   // norm(1 - dollars_per_pin)
  | "chronic_index"
  | "sector_imbalance"
  | "media_attention"       // NEGATIVE weight
  | "geographic_isolation"; // need-multiplier, interacts with severity_rate

export interface ScoreComponent {
  key: ComponentKey;
  label: string;
  percentile: number;   // within-year percentile rank, 0..1
  weight: number;       // nominal w1..w7; negative for media_attention
  contribution: number; // weight * percentile (signed)
}

export interface CrisisRanking {
  iso3: string;
  country_name: string;
  region: string;
  year: number;
  overlooked_score: number;   // 0..1
  rank_position: number;      // 1-indexed
  rank_ci_low: number;        // bootstrap 95% CI
  rank_ci_high: number;
  stable_top_n: boolean;      // top-10 in >=90% of bootstrap samples
  neglect_class: NeglectClass;
  change_direction: ChangeDirection;
  change_magnitude: number;
  components: ScoreComponent[];
  people_in_need: number;
  gap_ratio: number;          // 0..1
  inform_severity: number;    // 0..5
  data_sparsity_flag: boolean;
  hno_last_updated: string | null;
}

export interface SectorCoverage {
  sector: string;
  requirement_usd: number;
  funding_usd: number;
  sector_gap: number;   // 0..1
  pin_share: number;    // 0..1
  flagged: boolean;     // gap > 0.7 AND pin_share >= 0.10
}

export interface FundingFunnelStage {
  stage: "requirement" | "pledged" | "committed" | "paid";
  amount_usd: number;
}

export interface FundingTrendPoint {
  year: number;
  requirement_usd: number;
  funding_paid_usd: number;
  gap_ratio: number;
}

export interface SubnationalArea {
  pcode: string;              // UN p-code
  admin1_name: string;
  overlooked_score: number;   // 0..1
  inform_severity: number;    // 0..5
  people_in_need: number;
  inferred_funding_usd: number;
  is_hotspot: boolean;        // ACLED-driven
}

export interface CrisisDetail {
  ranking: CrisisRanking;
  sectors: SectorCoverage[];
  funnel: FundingFunnelStage[];
  trend: FundingTrendPoint[];
  subnational: SubnationalArea[];
  donor_top3_share: number;   // 0..1
  narrative: string | null;   // null until KA stretch lands
}

export interface AskExchange {
  id: string;
  question: string;
  generated_sql: string;
  result_rows: Array<Record<string, string | number>>;
  answer: string;             // NL synthesis with (iso3, year, table) citations
}

export interface CompareMetric {
  metric_key: string;
  label: string;
  values: Record<string, number>; // per-iso3 on shared 0..1 scale
}

export interface CbpfAllocation {
  iso3: string;
  country_name: string;
  allocated_usd: number;
  overlooked_score: number;
  rank_position: number;
}

export interface CbpfFund {
  fund_id: string;
  fund_name: string;
  countries: string[];
  allocations: CbpfAllocation[];
}
```

Exports beyond the types: `NEGLECT_CLASS_META`, `COMPONENT_LABELS` (label +
theme-token maps), `MOCK_RANKINGS` (10 countries), `getCrisisDetail(iso3)`,
`MOCK_REGIONS`, `MOCK_ASK_EXCHANGE`, `MOCK_COMPARE_METRICS`, `MOCK_CBPF_FUND`.

## 4. Ambiguities found translating the docs to shells

- **Crisis Explorer is not a top-level nav item.** `docs/architecture.md` lists
  "six screens" but Crisis Explorer is reached by drilling into a country
  (`/crisis/:iso3`), so the persona/IA reads as five nav destinations + one
  drill-in. I built it that way (nav shows 5; Triage rows link into Crisis
  Explorer). Worth confirming this matches the intended IA.
- **Ask screen embedding.** `personas.md` still says "Embedded native Genie UI
  handles this" / "embedded AI/BI Dashboard," but `STATE.md`/`DECISIONS.md`
  (2026-05-21) supersede that with the API-based custom-UI pattern. I built the
  custom chat UI per the newer decision. `personas.md` has stale embedding
  language that may want a cleanup pass.
- **`overlooked_score` display tension.** Methodology forbids false precision
  ("0.8347" is dishonest) yet the score is naturally a 0..1 number. I kept it in
  the data model but lead the UI with rank+CI and percentages rounded to whole
  numbers; the raw score is shown sparingly. Flagging in case you want it hidden
  entirely from the default view.
- **Funding funnel grain.** Methodology describes paid/committed/pledged as the
  three-stage funnel, and `gap_ratio` uses `paid`. I modeled funnel as four
  stages (requirement + the three flow statuses). Confirm whether "requirement"
  should be a funnel stage or a separate denominator.
- **Subnational under data sparsity.** I made `data_sparsity_flag === true`
  yield an empty subnational array (country-level only). That matches the
  "graceful degradation" language but is an interpretation — confirm the UI
  should show the flag + empty state rather than inferred admin1 rows.
- **No `sample_command_center.png` in the repo.** The reference image named in
  the prompt isn't present. I worked from the written "control center" register
  (dark, dense, restrained cyan-teal primary, data color carries signal).

None of these blocked the scaffold; they're contract questions for the
integration session, not methodology improvisations.

## 5. What the next integration session needs to do, in order

1. **FastAPI data layer** — implement `/api/rankings/top`, `/api/crisis/{iso3}`,
   etc. against the Databricks SQL Connector; credentials via env vars.
2. **Fetch layer in the frontend** — keep `mockData.ts` types, add an API client
   returning those same types; screens stay unchanged.
3. **Maps** — global admin0 choropleth (Triage) and admin1 choropleth +
   ACLED hotspot overlay (Crisis Explorer) via react-map-gl + MapLibre over
   fieldmaps.io boundaries.
4. **Recharts** — funding trend, sector breakdown, bootstrap-CI bands,
   validation (precision/recall + Jaccard), CBPF scatter.
5. **Ask screen → Genie REST** via `/api/ask` with streaming; persist thumbs
   feedback to a Delta table.
6. **Methodology screen** reads real Gold tables; RAI scorecard from MLflow.
7. **Databricks App packaging** (`databricks.yml`) declaring Model Serving
   endpoint, SQL warehouse, and Gold-table dependencies.

Detail also lives in `frontend/README.md`.
