"""
Pydantic response/request models for the Geo-Insight API.

These mirror the TypeScript types in `frontend/src/lib/types.ts` field-for-field
(snake_case both sides) so the swap to a typed React fetcher is mechanical, and
so the later swap of mock_data.py for real Databricks SQL Connector queries only
changes *where the data comes from*, not its shape.

Field-naming + scale conventions follow docs/methodology.md:
  - ranks ALWAYS carry a bootstrap CI (rank_ci_low / rank_ci_high)
  - composite components are within-year PERCENTILE ranks in [0, 1], not raw values
  - gap_ratio / sector_gap / overlooked_score are fractions in [0, 1]
  - inform_severity is the 0..5 INFORM Severity Index
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# --- enumerations ----------------------------------------------------------

NeglectClass = Literal[
    "chronic_neglect",
    "acute_deterioration",
    "improving",
    "well_funded",
    "chronic_no_plan",
]

ChangeDirection = Literal["up", "down", "new", "same"]

ComponentKey = Literal[
    "gap_ratio",
    "severity_rate",
    "dollars_per_pin_inv",
    "chronic_index",
    "sector_imbalance",
    "media_attention",
    "geographic_isolation",
]

FunnelStage = Literal["required", "pledged", "committed", "paid"]


# --- core ranking (grain: country x year — gold_forgotten_crisis_index) -----

class ScoreComponent(BaseModel):
    key: ComponentKey
    label: str
    percentile: float = Field(ge=0, le=1, description="within-year percentile rank")
    weight: float = Field(description="nominal w1..w7; negative for media_attention")
    contribution: float = Field(description="weight * percentile (signed)")


class ScoreHistoryPoint(BaseModel):
    year: int
    overlooked_score: float = Field(ge=0, le=1)


class CrisisRanking(BaseModel):
    iso3: str
    country_name: str
    region: str
    year: int

    overlooked_score: float = Field(ge=0, le=1)
    rank_position: int = Field(ge=1)
    rank_ci_low: int
    rank_ci_high: int
    stable_top_n: bool

    neglect_class: NeglectClass

    change_direction: ChangeDirection
    change_magnitude: int

    components: list[ScoreComponent]
    # 5-point sparkline series (oldest -> current). Faked in mock data;
    # eventually a time-windowed read of gold_forgotten_crisis_index.
    score_history: list[ScoreHistoryPoint]

    people_in_need: int
    gap_ratio: float = Field(ge=0, le=1)
    inform_severity: float = Field(ge=0, le=5)

    data_sparsity_flag: bool
    hno_last_updated: str | None


# --- sector coverage (grain: country x year x sector) ----------------------

class SectorCoverage(BaseModel):
    sector: str
    requirement_usd: float
    funding_usd: float
    sector_gap: float = Field(ge=0, le=1)
    pin_share: float = Field(ge=0, le=1)
    # flagged when sector_gap > 0.7 AND pin_share >= 0.10 (methodology.md)
    is_flagged_gap: bool


# --- funding funnel (grain: country x year x stage) ------------------------

class FundingFunnelStage(BaseModel):
    stage: FunnelStage
    amount_usd: float
    pct_of_requirement: float = Field(ge=0, description="amount / required amount")


# --- multi-year funding trend (grain: country x year) ----------------------

class FundingTrendPoint(BaseModel):
    year: int
    requirement_usd: float
    funding_paid_usd: float
    gap_ratio: float = Field(ge=0, le=1)


# --- subnational admin1 (grain: admin1 x year — gold_subnational_index) -----

class SubnationalArea(BaseModel):
    pcode: str
    admin1_name: str
    overlooked_score: float = Field(ge=0, le=1)
    inform_severity: float = Field(ge=0, le=5)
    people_in_need: int
    inferred_funding_usd: float
    is_hotspot: bool


# --- crisis detail (everything one Crisis Explorer view needs) -------------

class CrisisDetail(BaseModel):
    ranking: CrisisRanking
    sectors: list[SectorCoverage]
    funnel: list[FundingFunnelStage]
    trend: list[FundingTrendPoint]
    subnational: list[SubnationalArea]
    donor_top3_share: float = Field(ge=0, le=1)
    narrative: str | None


# --- rankings response (Triage) --------------------------------------------

class RankingsResponse(BaseModel):
    year: int
    scope: str
    rankings: list[CrisisRanking]


# --- compare ----------------------------------------------------------------

class CompareMetric(BaseModel):
    metric_key: str
    label: str
    # per-iso3 value on a shared 0..1 scale, for aligned bar rendering
    values: dict[str, float]


class CompareResponse(BaseModel):
    countries: list[str]
    # full ranking rows for the selected countries (powers the quadrant scatter)
    rankings: list[CrisisRanking]
    metrics: list[CompareMetric]


# --- ask (Genie REST custom chat UI) ---------------------------------------

class AskRequest(BaseModel):
    question: str


class AskExchange(BaseModel):
    id: str
    question: str
    generated_sql: str
    # tabular preview; columns vary by query
    result_rows: list[dict[str, Any]]
    answer: str


# --- methodology transparency ----------------------------------------------

class CascadeMethod(BaseModel):
    method: str
    label: str
    share_pct: float = Field(description="share of total flow dollars, 0..100")
    note: str


class CascadeResponse(BaseModel):
    methods: list[CascadeMethod]
    note: str


class CompositeWeight(BaseModel):
    key: ComponentKey
    label: str
    weight: float
    rationale: str


class CompositeWeightsResponse(BaseModel):
    weights: list[CompositeWeight]
    note: str


# --- CBPF allocation view ---------------------------------------------------

class CbpfAllocation(BaseModel):
    iso3: str
    country_name: str
    allocated_usd: float
    # CBPF's two allocation windows (data_catalog.md: AllocationType).
    reserve_usd: float
    standard_usd: float
    overlooked_score: float = Field(ge=0, le=1)
    rank_position: int


class CbpfFund(BaseModel):
    fund_id: str
    fund_name: str
    countries: list[str]
    allocations: list[CbpfAllocation]
    # EMPTY BY DESIGN in v1: CBPF carries no sector tag at allocation level
    # (data_catalog.md). Present in the contract so the UI can show the caveat.
    sector_breakdown: list[Any] = Field(default_factory=list)


class CbpfResponse(BaseModel):
    year: int
    funds: list[CbpfFund]


# --- change indicators (Triage deltas) -------------------------------------

class ChangeIndicatorRow(BaseModel):
    iso3: str
    country_name: str
    change_direction: ChangeDirection
    change_magnitude: int
    rank_position: int
    prev_rank: int | None


class ChangesResponse(BaseModel):
    since: str
    changes: list[ChangeIndicatorRow]
