/**
 * types.ts — the TypeScript half of the Geo-Insight data CONTRACT.
 *
 * These mirror the Pydantic models in `frontend/server/models.py` field-for-field
 * (snake_case both sides). The fixtures now live server-side in
 * `frontend/server/mock_data.py`; this file is types-only. `mockData.ts`
 * re-exports everything here for backward-compatible imports.
 *
 * Honesty rules baked in (docs/methodology.md "Honesty commitments"):
 *  - ranks ALWAYS travel with a bootstrap CI (rank_ci_low / rank_ci_high)
 *  - composite components are within-year percentile ranks in [0,1], not raw values
 *  - missing data is a signal (neglect_class can be `chronic_no_plan`;
 *    `data_sparsity_flag` is explicit, never silently imputed)
 */

// --- enumerations ----------------------------------------------------------

/** Temporal classification — methodology.md "Temporal classification". */
export type NeglectClass =
  | "chronic_neglect"
  | "acute_deterioration"
  | "improving"
  | "well_funded"
  | "chronic_no_plan";

/** Direction of rank movement since the prior period. */
export type ChangeDirection = "up" | "down" | "new" | "same";

/** The seven composite components (methodology.md "Composite overlooked score"). */
export type ComponentKey =
  | "gap_ratio"
  | "severity_rate"
  | "dollars_per_pin_inv" // norm(1 - dollars_per_pin); higher = more overlooked
  | "chronic_index"
  | "sector_imbalance"
  | "media_attention" // NEGATIVE weight
  | "geographic_isolation"; // need-multiplier, interacts with severity_rate

/** Funnel stages (methodology three-stage funnel + requirement denominator). */
export type FunnelStage = "required" | "pledged" | "committed" | "paid";

// --- core ranking (grain: country x year — gold_forgotten_crisis_index) ----

export interface ScoreComponent {
  key: ComponentKey;
  label: string;
  /** within-year percentile rank, 0..1 */
  percentile: number;
  /** nominal weight w1..w7; negative for media_attention */
  weight: number;
  /** weight * percentile — signed contribution */
  contribution: number;
}

export interface ScoreHistoryPoint {
  year: number;
  /** 0..1 */
  overlooked_score: number;
}

export interface CrisisRanking {
  iso3: string;
  country_name: string;
  region: string;
  year: number;

  /** composite overlooked_score, 0..1; shown sparingly (rank+CI is the honest unit) */
  overlooked_score: number;
  rank_position: number;
  rank_ci_low: number;
  rank_ci_high: number;
  /** in top-10 across >=90% of bootstrap samples */
  stable_top_n: boolean;

  neglect_class: NeglectClass;

  change_direction: ChangeDirection;
  change_magnitude: number;

  /** deterministic decomposition, sorted by |contribution| desc */
  components: ScoreComponent[];
  /** 5-point sparkline series (oldest -> current) */
  score_history: ScoreHistoryPoint[];

  people_in_need: number;
  /** funding gap fraction 0..1 (UI rounds to whole percent) */
  gap_ratio: number;
  /** INFORM Severity Index 0..5 */
  inform_severity: number;

  data_sparsity_flag: boolean;
  /** ISO date of last HNO update; null = unknown/stale */
  hno_last_updated: string | null;
}

// --- sector coverage (grain: country x year x sector) ----------------------

export interface SectorCoverage {
  sector: string;
  requirement_usd: number;
  funding_usd: number;
  /** (requirement - funding) / requirement, 0..1 */
  sector_gap: number;
  /** sector's share of country PIN, 0..1 */
  pin_share: number;
  /** flagged when sector_gap > 0.7 AND pin_share >= 0.10 */
  is_flagged_gap: boolean;
}

// --- funding funnel (grain: country x year x stage) ------------------------

export interface FundingFunnelStage {
  stage: FunnelStage;
  amount_usd: number;
  /** amount / required amount */
  pct_of_requirement: number;
}

// --- multi-year funding trend (grain: country x year) ----------------------

export interface FundingTrendPoint {
  year: number;
  requirement_usd: number;
  funding_paid_usd: number;
  gap_ratio: number;
}

// --- subnational admin1 (grain: admin1 x year — gold_subnational_index) -----

export interface SubnationalArea {
  pcode: string;
  admin1_name: string;
  overlooked_score: number;
  inform_severity: number;
  people_in_need: number;
  inferred_funding_usd: number;
  is_hotspot: boolean;
}

// --- ACLED hotspots (grain: admin1 — silver_acled_severity @ admin1 monthly) -

export interface AcledHotspot {
  admin1_pcode: string;
  latitude: number;
  longitude: number;
  /** cumulative events over the queried window */
  event_count: number;
  /** recent slice of event_count (drives circle color/recency) */
  recent_event_count: number;
  /** ISO date of the most recent event */
  last_event_date: string;
}

export interface HotspotsResponse {
  iso3: string;
  since: string;
  hotspots: AcledHotspot[];
}

// --- crisis detail ---------------------------------------------------------

export interface CrisisDetail {
  ranking: CrisisRanking;
  sectors: SectorCoverage[];
  funnel: FundingFunnelStage[];
  trend: FundingTrendPoint[];
  subnational: SubnationalArea[];
  donor_top3_share: number;
  narrative: string | null;
}

// --- responses -------------------------------------------------------------

export interface RankingsResponse {
  year: number;
  scope: string;
  rankings: CrisisRanking[];
}

export interface CompareMetric {
  metric_key: string;
  label: string;
  /** per-iso3 value on a shared 0..1 scale */
  values: Record<string, number>;
}

export interface CompareResponse {
  countries: string[];
  /** full ranking rows for the selected countries (powers the quadrant scatter) */
  rankings: CrisisRanking[];
  metrics: CompareMetric[];
}

export interface AskExchange {
  id: string;
  question: string;
  generated_sql: string;
  result_rows: Array<Record<string, string | number>>;
  answer: string;
}

export interface CascadeMethod {
  method: string;
  label: string;
  /** share of total flow dollars, 0..100 */
  share_pct: number;
  note: string;
}

export interface CascadeResponse {
  methods: CascadeMethod[];
  note: string;
}

export interface CompositeWeight {
  key: ComponentKey;
  label: string;
  weight: number;
  rationale: string;
}

export interface CompositeWeightsResponse {
  weights: CompositeWeight[];
  note: string;
}

export interface CbpfAllocation {
  iso3: string;
  country_name: string;
  allocated_usd: number;
  reserve_usd: number;
  standard_usd: number;
  overlooked_score: number;
  rank_position: number;
}

export interface CbpfFund {
  fund_id: string;
  fund_name: string;
  countries: string[];
  allocations: CbpfAllocation[];
  /** empty by design in v1 — CBPF has no sector tag at allocation level */
  sector_breakdown: unknown[];
}

export interface CbpfResponse {
  year: number;
  funds: CbpfFund[];
}

export interface ChangeIndicatorRow {
  iso3: string;
  country_name: string;
  change_direction: ChangeDirection;
  change_magnitude: number;
  rank_position: number;
  prev_rank: number | null;
}

export interface ChangesResponse {
  since: string;
  changes: ChangeIndicatorRow[];
}

// --- display helpers (label + theme token) ---------------------------------

export const NEGLECT_CLASS_META: Record<
  NeglectClass,
  { label: string; tokenClass: string; description: string }
> = {
  chronic_neglect: {
    label: "Chronic neglect",
    tokenClass: "text-chronic",
    description: "Underfunded ≥3 of the last 5 years.",
  },
  acute_deterioration: {
    label: "Acute deterioration",
    tokenClass: "text-acute",
    description: "Recent sharp gap; not yet chronic.",
  },
  improving: {
    label: "Improving",
    tokenClass: "text-improving",
    description: "Gap decreasing, current ≤30%.",
  },
  well_funded: {
    label: "Well funded",
    tokenClass: "text-improving",
    description: "No chronic years; current gap ≤30%.",
  },
  chronic_no_plan: {
    label: "Chronic, no plan",
    tokenClass: "text-noplan",
    description: "Need persists with no HRP for 3+ years.",
  },
};

export const COMPONENT_LABELS: Record<ComponentKey, string> = {
  gap_ratio: "Funding gap",
  severity_rate: "Severity rate",
  dollars_per_pin_inv: "Low $/PIN",
  chronic_index: "Chronic index",
  sector_imbalance: "Sector imbalance",
  media_attention: "Media attention",
  geographic_isolation: "Geographic isolation",
};
