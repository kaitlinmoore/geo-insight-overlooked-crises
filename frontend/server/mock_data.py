"""
Canonical mock fixtures for the Geo-Insight API.

This file is now the SINGLE source of truth for the demo fixtures (the
TypeScript side is types-only after this session). Numbers are FABRICATED and
plausible — they must not be cited. The later integration session replaces the
builders here with Databricks SQL Connector queries; response shapes do not change.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

from models import (
    AcledHotspot,
    AskExchange,
    CascadeMethod,
    CascadeResponse,
    CbpfAllocation,
    CbpfFund,
    CbpfResponse,
    ChangeIndicatorRow,
    ChangesResponse,
    CompareMetric,
    CompareResponse,
    CompositeWeight,
    CompositeWeightsResponse,
    CrisisDetail,
    CrisisRanking,
    FundingFunnelStage,
    FundingTrendPoint,
    HotspotsResponse,
    RankingsResponse,
    ScoreComponent,
    ScoreHistoryPoint,
    SectorCoverage,
    SubnationalArea,
)

ANALYSIS_YEAR = 2026

# Real admin1 P-codes / interior points, emitted by src/acquisition/extract_geojson.py.
# Lets the subnational fixtures key to ACTUAL fieldmaps admin1 units (so the
# choropleth join on admin1_pcode works) and places ACLED hotspots at real
# coordinates. Absent until the extraction runs — fixtures degrade gracefully.
_CENTROIDS_PATH = Path(__file__).resolve().parents[1] / "public" / "maps" / "admin1_centroids.json"
try:
    CENTROIDS: dict[str, list[dict]] = json.loads(_CENTROIDS_PATH.read_text(encoding="utf-8"))
except FileNotFoundError:
    CENTROIDS = {}


def _seed(s: str) -> int:
    """Stable cross-run integer from a string (Python's hash() is salted)."""
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)

# Nominal composite weights (docs/methodology.md). media_attention is negative.
WEIGHTS: dict[str, float] = {
    "gap_ratio": 0.30,
    "severity_rate": 0.20,
    "dollars_per_pin_inv": 0.10,
    "chronic_index": 0.15,
    "sector_imbalance": 0.10,
    "media_attention": -0.10,
    "geographic_isolation": 0.05,
}

COMPONENT_LABELS: dict[str, str] = {
    "gap_ratio": "Funding gap",
    "severity_rate": "Severity rate",
    "dollars_per_pin_inv": "Low $/PIN",
    "chronic_index": "Chronic index",
    "sector_imbalance": "Sector imbalance",
    "media_attention": "Media attention",
    "geographic_isolation": "Geographic isolation",
}

WEIGHT_RATIONALES: dict[str, str] = {
    "gap_ratio": "Primary mismatch signal: share of the appeal that went unfunded.",
    "severity_rate": "Need normalized by population — intensity relative to country scale.",
    "dollars_per_pin_inv": "Low per-capita investment raises overlooked-ness (uses 1 − $/PIN).",
    "chronic_index": "Multi-year structural neglect; the bonus-task contribution.",
    "sector_imbalance": "Within-country sector dispersion — aggregate funding can hide gaps.",
    "media_attention": "Negative weight: visibility/advocacy reduces overlooked-ness.",
    "geographic_isolation": "Need-multiplier interacting with severity where fewer are watching.",
}


# --- per-country fixture inputs --------------------------------------------
# Each tuple carries the raw inputs; ScoreComponents are derived from the
# 7 percentiles via WEIGHTS so the decomposition stays internally consistent.

# (iso3, name, region, score, rank, ci_low, ci_high, stable, neglect, change_dir,
#  change_mag, pin, gap_ratio, inform, sparsity, hno_updated, percentiles{})
_COUNTRIES: list[dict] = [
    dict(iso3="SDN", name="Sudan", region="East & Horn of Africa", score=0.84,
         rank=1, lo=1, hi=3, stable=True, neglect="chronic_neglect", cdir="up", cmag=2,
         pin=24_800_000, gap=0.71, inform=4.6, sparse=False, hno="2025-12-01",
         pcts=dict(gap_ratio=0.93, severity_rate=0.88, dollars_per_pin_inv=0.71,
                   chronic_index=0.90, sector_imbalance=0.55, media_attention=0.42,
                   geographic_isolation=0.60)),
    dict(iso3="COD", name="Dem. Rep. of the Congo", region="East & Horn of Africa", score=0.79,
         rank=2, lo=1, hi=4, stable=True, neglect="chronic_neglect", cdir="same", cmag=0,
         pin=21_200_000, gap=0.66, inform=4.4, sparse=False, hno="2025-11-15",
         pcts=dict(gap_ratio=0.85, severity_rate=0.80, dollars_per_pin_inv=0.66,
                   chronic_index=0.82, sector_imbalance=0.60, media_attention=0.38,
                   geographic_isolation=0.70)),
    dict(iso3="BFA", name="Burkina Faso", region="West & Central Africa", score=0.74,
         rank=3, lo=2, hi=8, stable=True, neglect="acute_deterioration", cdir="up", cmag=5,
         pin=6_300_000, gap=0.69, inform=4.1, sparse=True, hno="2025-09-30",
         pcts=dict(gap_ratio=0.80, severity_rate=0.72, dollars_per_pin_inv=0.70,
                   chronic_index=0.45, sector_imbalance=0.66, media_attention=0.22,
                   geographic_isolation=0.85)),
    dict(iso3="MMR", name="Myanmar", region="Asia & the Pacific", score=0.71,
         rank=4, lo=2, hi=7, stable=True, neglect="chronic_neglect", cdir="down", cmag=1,
         pin=19_900_000, gap=0.63, inform=4.0, sparse=False, hno="2025-10-20",
         pcts=dict(gap_ratio=0.78, severity_rate=0.69, dollars_per_pin_inv=0.64,
                   chronic_index=0.74, sector_imbalance=0.50, media_attention=0.30,
                   geographic_isolation=0.55)),
    dict(iso3="HTI", name="Haiti", region="Latin America & Caribbean", score=0.68,
         rank=5, lo=3, hi=9, stable=True, neglect="acute_deterioration", cdir="new", cmag=0,
         pin=5_500_000, gap=0.60, inform=3.9, sparse=False, hno="2025-08-12",
         pcts=dict(gap_ratio=0.74, severity_rate=0.70, dollars_per_pin_inv=0.60,
                   chronic_index=0.40, sector_imbalance=0.58, media_attention=0.25,
                   geographic_isolation=0.50)),
    dict(iso3="TCD", name="Chad", region="West & Central Africa", score=0.66,
         rank=6, lo=3, hi=12, stable=False, neglect="chronic_no_plan", cdir="up", cmag=3,
         pin=7_000_000, gap=0.64, inform=3.7, sparse=True, hno=None,
         pcts=dict(gap_ratio=0.70, severity_rate=0.65, dollars_per_pin_inv=0.72,
                   chronic_index=0.60, sector_imbalance=0.40, media_attention=0.15,
                   geographic_isolation=0.90)),
    dict(iso3="YEM", name="Yemen", region="Middle East & North Africa", score=0.63,
         rank=7, lo=4, hi=11, stable=False, neglect="chronic_neglect", cdir="down", cmag=4,
         pin=18_200_000, gap=0.55, inform=4.3, sparse=False, hno="2025-11-01",
         pcts=dict(gap_ratio=0.68, severity_rate=0.75, dollars_per_pin_inv=0.50,
                   chronic_index=0.78, sector_imbalance=0.62, media_attention=0.70,
                   geographic_isolation=0.30)),
    dict(iso3="AFG", name="Afghanistan", region="Asia & the Pacific", score=0.61,
         rank=8, lo=5, hi=13, stable=False, neglect="chronic_neglect", cdir="same", cmag=0,
         pin=23_700_000, gap=0.52, inform=4.2, sparse=False, hno="2025-10-05",
         pcts=dict(gap_ratio=0.66, severity_rate=0.70, dollars_per_pin_inv=0.55,
                   chronic_index=0.72, sector_imbalance=0.48, media_attention=0.50,
                   geographic_isolation=0.45)),
    dict(iso3="SOM", name="Somalia", region="East & Horn of Africa", score=0.58,
         rank=9, lo=5, hi=15, stable=False, neglect="acute_deterioration", cdir="down", cmag=2,
         pin=6_900_000, gap=0.50, inform=4.0, sparse=False, hno="2025-09-18",
         pcts=dict(gap_ratio=0.62, severity_rate=0.68, dollars_per_pin_inv=0.58,
                   chronic_index=0.50, sector_imbalance=0.44, media_attention=0.40,
                   geographic_isolation=0.60)),
    dict(iso3="MLI", name="Mali", region="West & Central Africa", score=0.55,
         rank=10, lo=6, hi=18, stable=False, neglect="chronic_neglect", cdir="up", cmag=1,
         pin=4_100_000, gap=0.57, inform=3.8, sparse=True, hno="2025-07-22",
         pcts=dict(gap_ratio=0.60, severity_rate=0.58, dollars_per_pin_inv=0.62,
                   chronic_index=0.64, sector_imbalance=0.50, media_attention=0.20,
                   geographic_isolation=0.78)),
]


def _components(pcts: dict[str, float]) -> list[ScoreComponent]:
    comps = [
        ScoreComponent(
            key=key,  # type: ignore[arg-type]
            label=COMPONENT_LABELS[key],
            percentile=pcts[key],
            weight=WEIGHTS[key],
            contribution=round(WEIGHTS[key] * pcts[key], 3),
        )
        for key in WEIGHTS
    ]
    comps.sort(key=lambda c: abs(c.contribution), reverse=True)
    return comps


def _score_history(score: float) -> list[ScoreHistoryPoint]:
    # Deterministic 5-point series ending at the current score (oldest -> now).
    deltas = [-0.09, -0.04, -0.06, -0.02, 0.0]
    years = [ANALYSIS_YEAR - 4 + i for i in range(5)]
    return [
        ScoreHistoryPoint(year=y, overlooked_score=round(max(0.0, min(1.0, score + d)), 3))
        for y, d in zip(years, deltas)
    ]


def _ranking(c: dict) -> CrisisRanking:
    return CrisisRanking(
        iso3=c["iso3"],
        country_name=c["name"],
        region=c["region"],
        year=ANALYSIS_YEAR,
        overlooked_score=c["score"],
        rank_position=c["rank"],
        rank_ci_low=c["lo"],
        rank_ci_high=c["hi"],
        stable_top_n=c["stable"],
        neglect_class=c["neglect"],
        change_direction=c["cdir"],
        change_magnitude=c["cmag"],
        components=_components(c["pcts"]),
        score_history=_score_history(c["score"]),
        people_in_need=c["pin"],
        gap_ratio=c["gap"],
        inform_severity=c["inform"],
        data_sparsity_flag=c["sparse"],
        hno_last_updated=c["hno"],
    )


RANKINGS: list[CrisisRanking] = [_ranking(c) for c in _COUNTRIES]
_RANKING_BY_ISO: dict[str, CrisisRanking] = {r.iso3: r for r in RANKINGS}


def _sectors() -> list[SectorCoverage]:
    return [
        SectorCoverage(sector="Food Security", requirement_usd=9.2e8, funding_usd=5.1e8, sector_gap=0.45, pin_share=0.34, is_flagged_gap=False),
        SectorCoverage(sector="Health", requirement_usd=4.4e8, funding_usd=6.6e7, sector_gap=0.85, pin_share=0.18, is_flagged_gap=True),
        SectorCoverage(sector="WASH", requirement_usd=3.1e8, funding_usd=1.2e8, sector_gap=0.61, pin_share=0.15, is_flagged_gap=False),
        SectorCoverage(sector="Protection", requirement_usd=2.6e8, funding_usd=4.2e7, sector_gap=0.84, pin_share=0.12, is_flagged_gap=True),
        SectorCoverage(sector="Education", requirement_usd=1.8e8, funding_usd=9.0e7, sector_gap=0.50, pin_share=0.09, is_flagged_gap=False),
        SectorCoverage(sector="Shelter & NFI", requirement_usd=1.5e8, funding_usd=5.5e7, sector_gap=0.63, pin_share=0.08, is_flagged_gap=False),
    ]


def _subnational_from_centroids(r: CrisisRanking, paid: float) -> list[SubnationalArea]:
    """Build a SubnationalArea per real admin1 unit, keyed to fieldmaps P-codes.
    Scores are FABRICATED but deterministic per P-code so the map and list agree."""
    areas: list[SubnationalArea] = []
    for a in CENTROIDS.get(r.iso3, []):
        seed = _seed(a["admin1_pcode"])
        areas.append(SubnationalArea(
            pcode=a["admin1_pcode"],
            admin1_name=a["admin1_name"],
            overlooked_score=round(0.30 + (seed % 60) / 100, 3),  # 0.30..0.89
            inform_severity=round(2.5 + (seed % 25) / 10, 1),     # 2.5..4.9
            people_in_need=int(r.people_in_need * ((seed % 18) + 3) / 200),
            inferred_funding_usd=paid * (((seed % 15) + 2) / 100),
            is_hotspot=(seed % 4 == 0),
        ))
    areas.sort(key=lambda x: x.overlooked_score, reverse=True)
    return areas


def hotspots_response(iso3: str, since: str) -> HotspotsResponse:
    """ACLED conflict hotspots for a country's admin1 units. FABRICATED counts at
    real interior points; the real source is silver_acled_severity aggregated to
    admin1 monthly (current to last month — not embargoed; see acquisition_acled.md)."""
    iso3 = iso3.upper()
    base = date(ANALYSIS_YEAR, 5, 1)  # severity path is current to last month
    spots: list[AcledHotspot] = []
    for a in CENTROIDS.get(iso3, []):
        seed = _seed(a["admin1_pcode"] + "acled")
        events = 15 + seed % 420
        spots.append(AcledHotspot(
            admin1_pcode=a["admin1_pcode"],
            latitude=a["lat"],
            longitude=a["lon"],
            event_count=events,
            recent_event_count=int(events * (0.08 + (seed % 40) / 200)),  # ~8..28%
            last_event_date=(base - timedelta(days=seed % 120)).isoformat(),
        ))
    spots.sort(key=lambda s: s.event_count, reverse=True)
    return HotspotsResponse(iso3=iso3, since=since, hotspots=spots[: max(4, len(spots) // 2)])


def crisis_detail(iso3: str) -> CrisisDetail | None:
    r = _RANKING_BY_ISO.get(iso3.upper())
    if r is None:
        return None

    sectors = _sectors()
    total_req = sum(s.requirement_usd for s in sectors)
    paid = total_req * (1 - r.gap_ratio)

    funnel = [
        FundingFunnelStage(stage="required", amount_usd=total_req, pct_of_requirement=1.0),
        FundingFunnelStage(stage="pledged", amount_usd=paid * 1.35, pct_of_requirement=round(paid * 1.35 / total_req, 3)),
        FundingFunnelStage(stage="committed", amount_usd=paid * 1.12, pct_of_requirement=round(paid * 1.12 / total_req, 3)),
        FundingFunnelStage(stage="paid", amount_usd=paid, pct_of_requirement=round(paid / total_req, 3)),
    ]

    trend: list[FundingTrendPoint] = []
    for i, year in enumerate([2022, 2023, 2024, 2025, 2026]):
        req = total_req * (0.8 + i * 0.06)
        gap = min(0.95, r.gap_ratio - 0.12 + i * 0.04)
        trend.append(FundingTrendPoint(
            year=year, requirement_usd=req, funding_paid_usd=req * (1 - gap), gap_ratio=round(gap, 2),
        ))

    if r.data_sparsity_flag:
        # Honest gap: no machine-readable admin1 data -> ranked at country level.
        subnational: list[SubnationalArea] = []
    elif r.iso3 in CENTROIDS:
        # Real fieldmaps admin1 units -> the choropleth join on admin1_pcode works.
        subnational = _subnational_from_centroids(r, paid)
    else:
        subnational = [
            SubnationalArea(pcode=f"{r.iso3}01", admin1_name="Region A", overlooked_score=0.81, inform_severity=4.5, people_in_need=int(r.people_in_need * 0.30), inferred_funding_usd=paid * 0.28, is_hotspot=True),
            SubnationalArea(pcode=f"{r.iso3}02", admin1_name="Region B", overlooked_score=0.62, inform_severity=3.9, people_in_need=int(r.people_in_need * 0.22), inferred_funding_usd=paid * 0.24, is_hotspot=False),
            SubnationalArea(pcode=f"{r.iso3}03", admin1_name="Region C", overlooked_score=0.49, inform_severity=3.4, people_in_need=int(r.people_in_need * 0.18), inferred_funding_usd=paid * 0.20, is_hotspot=False),
            SubnationalArea(pcode=f"{r.iso3}04", admin1_name="Region D", overlooked_score=0.70, inform_severity=4.1, people_in_need=int(r.people_in_need * 0.16), inferred_funding_usd=paid * 0.16, is_hotspot=True),
        ]

    return CrisisDetail(
        ranking=r, sectors=sectors, funnel=funnel, trend=trend,
        subnational=subnational, donor_top3_share=0.70, narrative=None,
    )


def rankings_response(year: int, scope: str, region: str | None) -> RankingsResponse:
    rows = list(RANKINGS)
    if region:
        rows = [r for r in rows if r.region == region]
    rows.sort(key=lambda r: r.rank_position)
    return RankingsResponse(year=year, scope=scope, rankings=rows)


def compare_response(isos: list[str]) -> CompareResponse:
    isos = [i.upper() for i in isos]
    rows = [_RANKING_BY_ISO[i] for i in isos if i in _RANKING_BY_ISO]

    def pct(r: CrisisRanking, key: str) -> float:
        for comp in r.components:
            if comp.key == key:
                return comp.percentile
        return 0.0

    metrics = [
        CompareMetric(metric_key="overlooked_score", label="Overlooked score", values={r.iso3: r.overlooked_score for r in rows}),
        CompareMetric(metric_key="gap_ratio", label="Funding gap", values={r.iso3: r.gap_ratio for r in rows}),
        CompareMetric(metric_key="severity_rate", label="Severity rate (pct)", values={r.iso3: pct(r, "severity_rate") for r in rows}),
        CompareMetric(metric_key="chronic_index", label="Chronic index (pct)", values={r.iso3: pct(r, "chronic_index") for r in rows}),
        CompareMetric(metric_key="media_attention", label="Media attention (pct)", values={r.iso3: pct(r, "media_attention") for r in rows}),
    ]
    return CompareResponse(countries=[r.iso3 for r in rows], rankings=rows, metrics=metrics)


def ask_response(question: str) -> AskExchange:
    q = question.lower()
    # Simple keyword routing over a few canned, plausible exchanges.
    if any(k in q for k in ("health", "sector")):
        return AskExchange(
            id="ex-health",
            question=question,
            generated_sql=(
                "SELECT iso3, country_name, sector, sector_gap\n"
                "FROM geo_insight.gold.gold_sector_coverage\n"
                "WHERE year = 2026 AND sector = 'Health' AND sector_gap > 0.7\n"
                "ORDER BY sector_gap DESC;"
            ),
            result_rows=[
                {"iso3": "SDN", "country_name": "Sudan", "sector_gap": 0.85},
                {"iso3": "HTI", "country_name": "Haiti", "sector_gap": 0.84},
                {"iso3": "BFA", "country_name": "Burkina Faso", "sector_gap": 0.78},
            ],
            answer=(
                "Three countries show a health-sector funding gap above 70% in 2026: "
                "Sudan (85%), Haiti (84%), and Burkina Faso (78%). The data indicates these "
                "gaps coincide with INFORM Severity ≥ 4 in each case. "
                "(SDN, 2026, gold_sector_coverage; HTI, 2026, gold_sector_coverage; "
                "BFA, 2026, gold_sector_coverage)"
            ),
        )
    if any(k in q for k in ("chronic", "structural", "neglect")):
        return AskExchange(
            id="ex-chronic",
            question=question,
            generated_sql=(
                "SELECT iso3, country_name, chronic_index, neglect_class\n"
                "FROM geo_insight.gold.gold_funding_trend\n"
                "WHERE year = 2026 AND neglect_class IN ('chronic_neglect','chronic_no_plan')\n"
                "ORDER BY chronic_index DESC;"
            ),
            result_rows=[
                {"iso3": "SDN", "country_name": "Sudan", "neglect_class": "chronic_neglect"},
                {"iso3": "COD", "country_name": "Dem. Rep. of the Congo", "neglect_class": "chronic_neglect"},
                {"iso3": "TCD", "country_name": "Chad", "neglect_class": "chronic_no_plan"},
            ],
            answer=(
                "Sudan and DR Congo carry the highest chronic-index values among 2026 crises, "
                "both classified chronic_neglect; Chad is flagged chronic_no_plan — persistent "
                "need with no active HRP. (SDN/COD/TCD, 2026, gold_funding_trend)"
            ),
        )
    # default: top overlooked
    return AskExchange(
        id="ex-top",
        question=question,
        generated_sql=(
            "SELECT iso3, country_name, rank_position, overlooked_score\n"
            "FROM geo_insight.gold.gold_forgotten_crisis_index\n"
            "WHERE year = 2026 ORDER BY rank_position ASC LIMIT 5;"
        ),
        result_rows=[
            {"iso3": r.iso3, "country_name": r.country_name, "rank_position": r.rank_position}
            for r in RANKINGS[:5]
        ],
        answer=(
            "The five most overlooked crises in 2026 are Sudan (#1, 95% CI [#1–3]), DR Congo (#2), "
            "Burkina Faso (#3), Myanmar (#4), and Haiti (#5, new to the top 10). Ranks carry "
            "bootstrap confidence intervals. (2026, gold_forgotten_crisis_index)"
        ),
    )


def cascade_response() -> CascadeResponse:
    # Shares from docs/notes/data_profiling.md (multi-country flow cascade).
    return CascadeResponse(
        methods=[
            CascadeMethod(method="country_tagged", label="Single-country (direct)", share_pct=68.5,
                          note="8,727 single-country flows; attributed directly, no cascade."),
            CascadeMethod(method="requirements_weighted", label="Requirements-weighted", share_pct=0.05,
                          note="Effectively never available — 99.1% of multi-country flows carry no destPlan."),
            CascadeMethod(method="population_weighted_fallback", label="Population-weighted fallback", share_pct=31.0,
                          note="De facto handler for multi-country flows (31.5% of dollars, 5.7% of rows)."),
            CascadeMethod(method="regional_unattributed", label="Regional, unattributed", share_pct=0.45,
                          note="No country tag and no country list; reported in aggregate only."),
        ],
        note=(
            "Requirements-weighted is the methodology's primary method but is effectively "
            "unavailable in practice; population-weighted is the operating handler. See "
            "docs/notes/data_profiling.md and DECISIONS 2026-05-22."
        ),
    )


def composite_weights_response() -> CompositeWeightsResponse:
    return CompositeWeightsResponse(
        weights=[
            CompositeWeight(key=key, label=COMPONENT_LABELS[key], weight=WEIGHTS[key], rationale=WEIGHT_RATIONALES[key])  # type: ignore[arg-type]
            for key in WEIGHTS
        ],
        note="Illustrative placeholder weights, calibrated against UFE; reported as configurable (docs/methodology.md).",
    )


def cbpf_response(year: int) -> CbpfResponse:
    sdn = _RANKING_BY_ISO["SDN"]
    return CbpfResponse(
        year=year,
        funds=[
            CbpfFund(
                fund_id="SDN-CBPF",
                fund_name="Sudan Humanitarian Fund",
                countries=["SDN"],
                allocations=[
                    CbpfAllocation(iso3="SDN", country_name="Sudan", allocated_usd=1.4e8,
                                   reserve_usd=9.1e7, standard_usd=4.9e7,
                                   overlooked_score=sdn.overlooked_score, rank_position=sdn.rank_position),
                ],
                sector_breakdown=[],  # empty by design — no sector tag at allocation level
            ),
            CbpfFund(
                fund_id="COD-CBPF",
                fund_name="DR Congo Humanitarian Fund",
                countries=["COD"],
                allocations=[
                    CbpfAllocation(iso3="COD", country_name="Dem. Rep. of the Congo", allocated_usd=9.6e7,
                                   reserve_usd=5.2e7, standard_usd=4.4e7,
                                   overlooked_score=_RANKING_BY_ISO["COD"].overlooked_score,
                                   rank_position=_RANKING_BY_ISO["COD"].rank_position),
                ],
                sector_breakdown=[],
            ),
        ],
    )


def changes_response(since: str) -> ChangesResponse:
    rows = [
        ChangeIndicatorRow(
            iso3=r.iso3,
            country_name=r.country_name,
            change_direction=r.change_direction,
            change_magnitude=r.change_magnitude,
            rank_position=r.rank_position,
            prev_rank=(
                None if r.change_direction == "new"
                else r.rank_position - r.change_magnitude if r.change_direction == "up"
                else r.rank_position + r.change_magnitude if r.change_direction == "down"
                else r.rank_position
            ),
        )
        for r in RANKINGS
        if r.change_direction != "same"
    ]
    return ChangesResponse(since=since, changes=rows)
