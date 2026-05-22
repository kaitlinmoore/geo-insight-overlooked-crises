# Databricks notebook source
# MAGIC %md
# MAGIC # Gold shared helpers (`_common`)
# MAGIC
# MAGIC Cross-cutting constants and reusable transforms for the Gold notebooks.
# MAGIC Imported with `%run ./_common` so the names resolve in the caller's
# MAGIC notebook context (same `spark`).
# MAGIC
# MAGIC **Gold is not DLT** (DLT is Silver-only in this architecture, see
# MAGIC `docs/architecture.md`). Each Gold notebook reads cleaned Silver tables
# MAGIC with `spark.table(silver("..."))`, computes, and materializes with
# MAGIC `df.write.format("delta").mode("overwrite").saveAsTable(gold("..."))`.
# MAGIC Data-quality assertions are post-write checks (`assert_expectations`).
# MAGIC
# MAGIC **What lives here** (anything reused by >2 Gold tables, per the task brief):
# MAGIC - namespace helpers (`gold` / `silver` / `bronze`);
# MAGIC - the composite weight vector + every methodology threshold as a named
# MAGIC   constant (so the Methodology screen reads them from one place);
# MAGIC - `percentile_rank_within_year` — the within-year normalization
# MAGIC   (`methodology.md` §Normalization), used by the index, explanation
# MAGIC   features, sector and subnational tables;
# MAGIC - `gap_ratio_base` / `chronic_features` / `neglect_class_expr` — the
# MAGIC   funding-gap + temporal-classification substrate shared by the index and
# MAGIC   `gold_funding_trend`;
# MAGIC - `build_components` — the country×year component matrix the composite is
# MAGIC   built from, shared by the index and `gold_explanation_features`;
# MAGIC - `dirichlet_bootstrap_rank_ci` — the rank-CI sampler.

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql import Window
from pyspark.sql import types as T

# ---------------------------------------------------------------------------
# Namespace (docs/schemas.md "Conventions")
# ---------------------------------------------------------------------------
CATALOG = "geo_insight"


def gold(name):
    return f"{CATALOG}.gold.{name}"


def silver(name):
    return f"{CATALOG}.silver.{name}"


def bronze(name):
    return f"{CATALOG}.bronze.{name}"


# COMMAND ----------

# MAGIC %md
# MAGIC ## Methodology constants
# MAGIC
# MAGIC Every tunable from `docs/methodology.md` in one place. The seven composite
# MAGIC weights are stored as **absolute** magnitudes; `COMPONENT_SIGNS` carries
# MAGIC the direction (media attention is the lone negative term). The absolute
# MAGIC weights sum to exactly 1.0 — which is what lets the bootstrap perturb them
# MAGIC with a single Dirichlet draw (see `dirichlet_bootstrap_rank_ci`).
# MAGIC
# MAGIC `GAP_NUMERATOR` defaults to `paid`, matching `methodology.md`/`schemas.md`.
# MAGIC This is the one place to flip it to `paid_committed`; either way the
# MAGIC `gap_ratio_paid_committed` sibling column is emitted for sensitivity work.

# COMMAND ----------

# Ordered component keys — the canonical order used everywhere (weights, signs,
# norm columns, bootstrap value matrix). The geographic-isolation term is the
# interaction norm(geographic_isolation) × norm(severity_rate).
COMPONENT_KEYS = [
    "gap_ratio",
    "severity_rate",
    "dollars_per_pin_inv",
    "chronic_index",
    "sector_imbalance",
    "media_attention",
    "geographic_isolation",
]

# Absolute weight magnitudes (methodology.md §Composite). Sum = 1.00 exactly.
COMPONENT_WEIGHTS = {
    "gap_ratio": 0.30,
    "severity_rate": 0.20,
    "dollars_per_pin_inv": 0.10,
    "chronic_index": 0.15,
    "sector_imbalance": 0.10,
    "media_attention": 0.10,
    "geographic_isolation": 0.05,
}

# Sign each component contributes with. Media attention is negative: more
# attention → less overlooked.
COMPONENT_SIGNS = {
    "gap_ratio": 1.0,
    "severity_rate": 1.0,
    "dollars_per_pin_inv": 1.0,
    "chronic_index": 1.0,
    "sector_imbalance": 1.0,
    "media_attention": -1.0,
    "geographic_isolation": 1.0,
}

# gap_ratio numerator policy. "paid" (the default) matches methodology.md
# §gap_ratio and schemas.md — the headline overlooked_score derives from
# gap_ratio = (requirement − paid) / requirement. "paid_committed" =
# (paid + commitment) is the alternative. Regardless of this setting,
# gap_ratio_base always emits a `gap_ratio_paid_committed` sibling column for
# sensitivity analysis on the Methodology slide.
GAP_NUMERATOR = "paid"

# Severity gate (methodology.md §Severity gate) — keys on the INFORM 1–5
# category, not the 1–10 index (DECISIONS 2026-05-22).
SEVERITY_GATE_CATEGORY = 4       # INFORM Severity category ≥ 4 enters ranking
CHRONIC_NOPLAN_CATEGORY = 3      # second-pass: ≥ 3 + no plan → chronic_no_plan
PIN_GATE_MIN = 100_000           # PIN threshold to enter on need alone

# Temporal classification (methodology.md §Chronic index / §Temporal class).
CHRONIC_GAP_THRESHOLD = 0.5      # a year counts as "chronic" when gap > 0.5
CHRONIC_WINDOW_YEARS = 5         # look-back window for chronic_years_count
CHRONIC_YEARS_FOR_CLASS = 3      # ≥ this many → chronic_neglect
NOPLAN_YEARS_FOR_CLASS = 3       # ≥ this many consecutive no-plan years
IMPROVING_GAP_CEIL = 0.3         # "improving"/"well_funded" current-year ceiling

# Bootstrap (methodology.md §Bootstrap uncertainty + open-questions.md).
BOOTSTRAP_N = 500
BOOTSTRAP_ALPHA_SCALE = 100.0    # Dirichlet α_i = scale × |w_i| (~10% rel. perturbation)
BOOTSTRAP_CI_LOW_PCT = 2.5
BOOTSTRAP_CI_HIGH_PCT = 97.5
STABLE_TOP_N = 10
STABLE_FRACTION = 0.90           # in top-N in ≥ 90% of samples → stable_top_n

# Data-freshness (open-questions.md — Venezuela 2011 population).
STALE_POP_MAX_AGE_YEARS = 5      # Reference_year < year − 5 → stale_population_flag

# Geographic-isolation sub-weights (methodology.md §Geographic isolation).
# PLACEHOLDERS — distance-to-urban-center is deferred in v1 (no urban-centroid
# reference table yet), so the available three are renormalized to sum to 1.
# Flagged in the handoff as a calibration item.
ISOLATION_SUBWEIGHTS = {
    "data_sparsity": 0.40,
    "inverse_acled_density": 0.30,
    "contested_border": 0.30,
}


# COMMAND ----------

# MAGIC %md
# MAGIC ## `percentile_rank_within_year`
# MAGIC
# MAGIC The within-year normalization from `methodology.md`. `percent_rank()` is 0
# MAGIC for the minimum and 1 for the maximum within each year partition. NULLs
# MAGIC sort first (ascending) → rank 0, i.e. a missing component contributes the
# MAGIC lowest overlooked signal; callers that prefer to treat missingness as
# MAGIC signal handle that separately via `data_sparsity_flag`.

# COMMAND ----------

def percentile_rank_within_year(value_col, year_col="year"):
    w = Window.partitionBy(year_col).orderBy(value_col)
    return F.percent_rank().over(w)


def assert_expectations(df, checks, table_name):
    """Post-write DQ. `checks` = list of (name, boolean SQL predicate that
    should hold for EVERY row). Logs a count of violations per check; raises on
    any `expect_or_fail`-severity check (name prefixed 'fail:'). Warn-only
    checks ('warn:') print but never raise — the Gold analogue of a DLT
    `@dlt.expect`. Cheap enough to run inline after each materialization."""
    total = df.count()
    print(f"[DQ] {table_name}: {total} rows")
    for name, predicate in checks:
        violations = df.where(f"NOT ({predicate})").count()
        status = "OK" if violations == 0 else f"{violations} VIOLATIONS"
        print(f"[DQ]   {name}: {status}  ({predicate})")
        if violations and name.startswith("fail:"):
            raise ValueError(f"{table_name}.{name}: {violations} rows fail `{predicate}`")


# COMMAND ----------

# MAGIC %md
# MAGIC ## Funding aggregation + `gap_ratio_base`
# MAGIC
# MAGIC `funding_by_country` rolls `silver_fts_flows` up to country×year by status,
# MAGIC **excluding `pending_attribution`** flows (open-questions.md: the 2026
# MAGIC regional mega-flows held out of `gap_ratio` until FTS disaggregates them).
# MAGIC The excluded dollar total is returned alongside so the explanation-features
# MAGIC table can document it.
# MAGIC
# MAGIC `gap_ratio_base` is the per-(iso3, year) funding-gap substrate the chronic
# MAGIC index and the temporal classification both build on. Denominator is
# MAGIC per-country requirements summed over **plan rows only** (`plan_code` not
# MAGIC null) — the country-aggregate `Not specified` rows carry NULL requirement
# MAGIC (DECISIONS 2026-05-22: per-country requirements, not plan totals).

# COMMAND ----------

def funding_by_country(spark, include_pending=False):
    """country×year funding by stage from silver_fts_flows. Returns a DataFrame
    with funded_paid_usd, funded_committed_usd, funded_pledged_usd, and
    funded_paid_committed_usd (the headline numerator). pending_attribution
    flows are excluded unless include_pending=True."""
    flows = spark.table(silver("silver_fts_flows")).where("iso3 IS NOT NULL")
    if not include_pending:
        flows = flows.where("allocation_method <> 'pending_attribution'")
    flows = flows.withColumn("year", F.year("flow_date"))
    return (
        flows.groupBy("iso3", "year")
        .agg(
            F.sum(F.when(F.col("status") == "paid", F.col("amount_usd")).otherwise(0.0)).alias("funded_paid_usd"),
            F.sum(F.when(F.col("status") == "commitment", F.col("amount_usd")).otherwise(0.0)).alias("funded_committed_usd"),
            F.sum(F.when(F.col("status") == "pledge", F.col("amount_usd")).otherwise(0.0)).alias("funded_pledged_usd"),
        )
        .withColumn(
            "funded_paid_committed_usd",
            F.col("funded_paid_usd") + F.col("funded_committed_usd"),
        )
    )


def requirements_by_country(spark):
    """country×year requirement_usd summed over plan rows only (plan_code not
    null). Country-aggregate 'Not specified' rows (plan_code null) carry a NULL
    requirement and are excluded from the denominator, but their presence is
    surfaced via `has_offplan_only` so no-HRP countries aren't silently lost."""
    reqs = spark.table(silver("silver_requirements"))
    plan = (
        reqs.where("plan_code IS NOT NULL AND requirement_usd IS NOT NULL")
        .groupBy("iso3", "year")
        .agg(F.sum("requirement_usd").alias("requirement_usd"),
             F.count(F.lit(1)).alias("n_plans"))
    )
    presence = (
        reqs.groupBy("iso3", "year")
        .agg(F.max(F.when(F.col("plan_code").isNotNull(), True).otherwise(False)).alias("has_plan"))
    )
    return (
        presence.join(plan, ["iso3", "year"], "left")
        .withColumn("has_offplan_only", ~F.col("has_plan"))
    )


def gap_ratio_base(spark):
    """Per-(iso3, year) funding gap. gap_ratio uses the GAP_NUMERATOR policy
    (paid by default → headline); gap_ratio_paid_committed always uses
    paid+committed as a sensitivity sibling. gap is NULL where requirement is
    missing/zero (→ chronic_no_plan / well_funded path downstream, never
    silently 0)."""
    funding = funding_by_country(spark)
    reqs = requirements_by_country(spark)
    base = reqs.join(funding, ["iso3", "year"], "left").fillna(
        0.0,
        subset=["funded_paid_usd", "funded_committed_usd", "funded_pledged_usd",
                "funded_paid_committed_usd"],
    )
    numerator = (
        F.col("funded_paid_committed_usd")
        if GAP_NUMERATOR == "paid_committed"
        else F.col("funded_paid_usd")
    )
    req_ok = F.col("requirement_usd").isNotNull() & (F.col("requirement_usd") > 0)
    return base.select(
        "iso3", "year", "requirement_usd", "n_plans", "has_plan", "has_offplan_only",
        "funded_paid_usd", "funded_committed_usd", "funded_pledged_usd",
        "funded_paid_committed_usd",
        F.when(req_ok, (F.col("requirement_usd") - numerator) / F.col("requirement_usd"))
            .alias("gap_ratio"),
        F.when(req_ok,
               (F.col("requirement_usd") - F.col("funded_paid_committed_usd")) / F.col("requirement_usd"))
            .alias("gap_ratio_paid_committed"),
    )


# COMMAND ----------

# MAGIC %md
# MAGIC ## `chronic_features` + `neglect_class_expr`
# MAGIC
# MAGIC Chronic index (`methodology.md` §Chronic index):
# MAGIC `chronic_index = chronic_years_count × mean_chronic_gap`, over a trailing
# MAGIC `CHRONIC_WINDOW_YEARS`-year window where `gap_ratio > CHRONIC_GAP_THRESHOLD`.
# MAGIC The window uses `rangeBetween(-4, 0)` on the integer `year` so a missing
# MAGIC year doesn't shift the window (`rowsBetween` would).
# MAGIC
# MAGIC The `neglect_class` precedence (`methodology.md` §Temporal classification),
# MAGIC highest-priority first: `chronic_no_plan` → `chronic_neglect` →
# MAGIC `improving` → `acute_deterioration` → `well_funded`.

# COMMAND ----------

def chronic_features(gap_base):
    """Adds chronic_years_count, mean_chronic_gap, chronic_index,
    gap_ratio_yoy_delta, and lag columns to a gap_ratio_base DataFrame."""
    by_year = Window.partitionBy("iso3").orderBy("year")
    win5 = by_year.rangeBetween(-(CHRONIC_WINDOW_YEARS - 1), 0)

    is_chronic_year = (F.col("gap_ratio") > CHRONIC_GAP_THRESHOLD)
    chronic_gap_sum = F.sum(F.when(is_chronic_year, F.col("gap_ratio")).otherwise(0.0)).over(win5)
    chronic_years_count = F.sum(F.when(is_chronic_year, 1).otherwise(0)).over(win5)
    no_plan_recent = F.sum(F.when(~F.col("has_plan"), 1).otherwise(0)).over(
        by_year.rangeBetween(-(NOPLAN_YEARS_FOR_CLASS - 1), 0)
    )

    out = (
        gap_base
        .withColumn("chronic_years_count", chronic_years_count)
        .withColumn(
            "mean_chronic_gap",
            F.when(chronic_years_count > 0, chronic_gap_sum / chronic_years_count).otherwise(0.0),
        )
        .withColumn("chronic_index", F.col("chronic_years_count") * F.col("mean_chronic_gap"))
        .withColumn("_gap_lag1", F.lag("gap_ratio", 1).over(by_year))
        .withColumn("_gap_lag2", F.lag("gap_ratio", 2).over(by_year))
        .withColumn("gap_ratio_yoy_delta", F.col("gap_ratio") - F.col("_gap_lag1"))
        .withColumn("_no_plan_recent", no_plan_recent)
    )
    return out


def neglect_class_expr():
    """Column expression for neglect_class. Expects the columns produced by
    `chronic_features` plus `severity_category_max` and `pin_total_country`
    (joined in by the caller for the chronic_no_plan need test)."""
    has_need = (F.col("severity_category_max") >= CHRONIC_NOPLAN_CATEGORY) | \
               (F.col("pin_total_country") >= PIN_GATE_MIN)
    chronic_no_plan = (F.col("_no_plan_recent") >= NOPLAN_YEARS_FOR_CLASS) & has_need
    chronic_neglect = F.col("chronic_years_count") >= CHRONIC_YEARS_FOR_CLASS
    improving = (
        F.col("gap_ratio").isNotNull()
        & F.col("_gap_lag1").isNotNull()
        & F.col("_gap_lag2").isNotNull()
        & (F.col("gap_ratio") <= IMPROVING_GAP_CEIL)
        & (F.col("gap_ratio") < F.col("_gap_lag1"))
        & (F.col("_gap_lag1") < F.col("_gap_lag2"))
    )
    acute = (F.col("chronic_years_count") < CHRONIC_YEARS_FOR_CLASS) & \
            (F.col("gap_ratio") >= CHRONIC_GAP_THRESHOLD)
    well_funded = (F.col("chronic_years_count") == 0) & \
                  (F.col("gap_ratio").isNotNull()) & (F.col("gap_ratio") <= IMPROVING_GAP_CEIL)
    return (
        F.when(chronic_no_plan, F.lit("chronic_no_plan"))
        .when(chronic_neglect, F.lit("chronic_neglect"))
        .when(improving, F.lit("improving"))
        .when(acute, F.lit("acute_deterioration"))
        .when(well_funded, F.lit("well_funded"))
        # default: a country with a gap but no chronic/acute/improving signal.
        .otherwise(F.lit("acute_deterioration"))
    )


# COMMAND ----------

# MAGIC %md
# MAGIC ## `build_geographic_isolation`
# MAGIC
# MAGIC The bounded 0–1 isolation signal (`methodology.md` §Geographic isolation).
# MAGIC v1 combines the **three** sub-signals we have data for, renormalized to
# MAGIC sum to 1; the distance-to-urban-centroid term is deferred (no urban-center
# MAGIC reference table acquired yet) and flagged for the user.
# MAGIC
# MAGIC - **data_sparsity**: 1 when the country-year has no machine-readable
# MAGIC   admin1 needs (HNO 2026 dropped subnational entirely), else 0. Lack of
# MAGIC   subnational visibility is itself an isolation signal.
# MAGIC - **inverse_acled_density**: 1 − percentile-rank of political-violence
# MAGIC   event counts (only `political_violence`, to avoid the documented
# MAGIC   `civilian_targeting` overlap). Lower conflict monitoring → more isolated.
# MAGIC - **contested_border**: 1 when any boundary in the country is OCHA-flagged
# MAGIC   contested, else 0.

# COMMAND ----------

def build_geographic_isolation(spark):
    """Returns iso3×year geographic_isolation in [0, 1] plus the sub-signal
    columns for transparency. Best-effort: any missing source degrades that
    sub-signal to 0 rather than failing."""
    # data sparsity from silver_needs.has_subnational
    needs = (
        spark.table(silver("silver_needs"))
        .groupBy("iso3", "year")
        .agg(F.max("has_subnational").alias("_has_sub"))
        .withColumn("data_sparsity", F.when(F.col("_has_sub"), 0.0).otherwise(1.0))
        .select("iso3", "year", "data_sparsity")
    )

    # ACLED political-violence density (silver_acled_severity is admin2×month).
    sev = (
        spark.table(silver("silver_acled_severity"))
        .where("event_category = 'political_violence'")
        .withColumn("year", F.col("year").cast("int"))
        .groupBy("iso3", "year")
        .agg(F.sum("events").alias("_events"))
    )
    sev = sev.withColumn("_dens_norm", percentile_rank_within_year(F.col("_events"), "year"))
    sev = sev.withColumn("inverse_acled_density", F.lit(1.0) - F.col("_dens_norm")).select(
        "iso3", "year", "inverse_acled_density"
    )

    # contested borders from silver_boundaries (year-invariant).
    bnd = (
        spark.table(silver("silver_boundaries"))
        .groupBy("iso3")
        .agg(F.max(F.when(F.col("contested_border_flag"), 1.0).otherwise(0.0)).alias("contested_border"))
    )

    base = needs.join(sev, ["iso3", "year"], "outer").join(bnd, "iso3", "left").fillna(
        0.0, subset=["data_sparsity", "inverse_acled_density", "contested_border"]
    )

    sw = ISOLATION_SUBWEIGHTS
    denom = sum(sw.values())
    isolation = (
        sw["data_sparsity"] * F.col("data_sparsity")
        + sw["inverse_acled_density"] * F.col("inverse_acled_density")
        + sw["contested_border"] * F.col("contested_border")
    ) / F.lit(denom)
    return base.withColumn("geographic_isolation", isolation)


# COMMAND ----------

# MAGIC %md
# MAGIC ## `build_components`
# MAGIC
# MAGIC The country×year component matrix the composite is built from — shared by
# MAGIC `gold_forgotten_crisis_index` and `gold_explanation_features` so the two
# MAGIC never drift. Emits the **raw** component values, the chronic/temporal
# MAGIC fields, the severity-gate inputs, the freshness inputs, and the
# MAGIC `sector_imbalance` from `gold_sector_coverage`. Normalization and the
# MAGIC weighted sum are applied by the callers via `normalize_components` /
# MAGIC `composite_score_expr` so the bootstrap can re-perturb the weights.

# COMMAND ----------

def build_components(spark):
    gap = chronic_features(gap_ratio_base(spark))

    # need / population / severity --------------------------------------------
    needs_total = (
        spark.table(silver("silver_needs"))
        .where("cluster = 'ALL'")
        .select("iso3", "year",
                F.col("pin_total_country").alias("pin_total_country"))
        .dropDuplicates(["iso3", "year"])
    )
    pop = (
        spark.table(silver("silver_population"))
        .where("admin1_pcode IS NULL")
        .select("iso3",
                F.col("population_total").cast("double").alias("population_total"),
                F.col("reference_year").alias("pop_reference_year"))
        .dropDuplicates(["iso3"])
    )
    sev = (
        spark.table(silver("silver_severity"))
        .select("iso3", "year", "severity_category_max", "severity_index_max",
                "latest_snapshot_date")
    )

    # sector imbalance from gold_sector_coverage (std-dev of sector gaps) -------
    sector_imb = (
        spark.table(gold("gold_sector_coverage"))
        .where("sector NOT LIKE 'NOT_A_SECTOR%'")
        .groupBy("iso3", "year")
        .agg(F.stddev_samp("sector_gap").alias("sector_imbalance"))
    )

    media = (
        spark.table(silver("silver_media_attention"))
        .select("iso3", "year", "media_attention_norm", "report_count_annual")
    )
    iso = build_geographic_isolation(spark).select("iso3", "year", "geographic_isolation")

    df = (
        gap
        .join(needs_total, ["iso3", "year"], "left")
        .join(pop, "iso3", "left")
        .join(sev, ["iso3", "year"], "left")
        .join(sector_imb, ["iso3", "year"], "left")
        .join(media, ["iso3", "year"], "left")
        .join(iso, ["iso3", "year"], "left")
    )

    df = (
        df
        .withColumn(
            "severity_rate",
            F.when(
                (F.col("population_total").isNotNull()) & (F.col("population_total") > 0)
                & F.col("pin_total_country").isNotNull(),
                F.col("pin_total_country") / F.col("population_total"),
            ),
        )
        .withColumn(
            "dollars_per_pin",
            F.when(
                (F.col("pin_total_country").isNotNull()) & (F.col("pin_total_country") > 0),
                F.col("funded_paid_usd") / F.col("pin_total_country"),
            ),
        )
        # data-freshness flags
        .withColumn(
            "stale_population_flag",
            F.when(F.col("pop_reference_year").isNotNull(),
                   F.col("pop_reference_year") < (F.col("year") - STALE_POP_MAX_AGE_YEARS))
            .otherwise(False),
        )
        .withColumn(
            "data_sparsity_flag",
            F.col("pin_total_country").isNull() | F.col("severity_category_max").isNull(),
        )
    )
    return df


# COMMAND ----------

# MAGIC %md
# MAGIC ## Normalization + composite assembly
# MAGIC
# MAGIC `normalize_components` adds the seven `*_norm` columns. Note
# MAGIC `dollars_per_pin_inv_norm = 1 − percentile_rank(dollars_per_pin)` — low
# MAGIC dollars-per-PIN means *more* overlooked (`methodology.md`: `norm(1 −
# MAGIC dollars_per_pin)`). `media_attention_norm` arrives already normalized from
# MAGIC `silver_media_attention`, so it passes through.
# MAGIC
# MAGIC `composite_score_expr` is the weighted sum with the geographic-isolation
# MAGIC interaction term (`norm(geographic_isolation) × norm(severity_rate)`).

# COMMAND ----------

def normalize_components(df):
    """Adds *_norm columns for every composite component (within-year).

    **Neutral 0.5 imputation (approach b).** `percent_rank()` over a column with
    NULLs treats those rows nulls-first → percentile ≈ 0, which would penalize a
    data-sparse country on a dimension it simply lacks data for. So wherever the
    raw input is NULL we override the resulting norm to **0.5** (the
    weight-symmetric neutral midpoint), regardless of what `percent_rank`
    returned. This stops the composite from punishing missingness; the
    `data_sparsity_flag` still travels through to `inputs_freshness`
    independently, so the missingness remains visible — it's just no longer
    scored as "least overlooked"."""

    def norm_or_neutral(raw_col, norm_expr):
        return F.when(F.col(raw_col).isNull(), F.lit(0.5)).otherwise(norm_expr)

    out = (
        df
        .withColumn("gap_ratio_norm",
                    norm_or_neutral("gap_ratio", percentile_rank_within_year(F.col("gap_ratio"))))
        .withColumn("severity_rate_norm",
                    norm_or_neutral("severity_rate", percentile_rank_within_year(F.col("severity_rate"))))
        .withColumn(
            "dollars_per_pin_inv_norm",
            norm_or_neutral("dollars_per_pin",
                            F.lit(1.0) - percentile_rank_within_year(F.col("dollars_per_pin"))),
        )
        .withColumn("chronic_index_norm",
                    norm_or_neutral("chronic_index", percentile_rank_within_year(F.col("chronic_index"))))
        .withColumn("sector_imbalance_norm",
                    norm_or_neutral("sector_imbalance", percentile_rank_within_year(F.col("sector_imbalance"))))
        # media_attention_norm passes through from silver; neutral 0.5 when absent.
        .withColumn("media_attention_n", F.coalesce(F.col("media_attention_norm"), F.lit(0.5)))
        .withColumn("geographic_isolation_norm",
                    norm_or_neutral("geographic_isolation", percentile_rank_within_year(F.col("geographic_isolation"))))
    )
    return out


def composite_score_expr(weights=None):
    """Weighted-sum column expression over the *_norm columns. `weights` is an
    optional dict of absolute magnitudes (defaults to COMPONENT_WEIGHTS); signs
    come from COMPONENT_SIGNS. The geographic-isolation term is the interaction
    norm(geographic_isolation) × norm(severity_rate)."""
    w = weights or COMPONENT_WEIGHTS
    s = COMPONENT_SIGNS

    def term(key, col):
        return F.lit(s[key] * w[key]) * col

    # 0.5 = neutral midpoint (see normalize_components). The *_norm columns are
    # already 0.5-imputed where their raw input was null; the coalesce here is a
    # belt-and-suspenders default for any unexpected null.
    return (
        term("gap_ratio", F.coalesce(F.col("gap_ratio_norm"), F.lit(0.5)))
        + term("severity_rate", F.coalesce(F.col("severity_rate_norm"), F.lit(0.5)))
        + term("dollars_per_pin_inv", F.coalesce(F.col("dollars_per_pin_inv_norm"), F.lit(0.5)))
        + term("chronic_index", F.coalesce(F.col("chronic_index_norm"), F.lit(0.5)))
        + term("sector_imbalance", F.coalesce(F.col("sector_imbalance_norm"), F.lit(0.5)))
        + term("media_attention", F.col("media_attention_n"))
        + term(
            "geographic_isolation",
            F.coalesce(F.col("geographic_isolation_norm"), F.lit(0.5))
            * F.coalesce(F.col("severity_rate_norm"), F.lit(0.5)),
        )
    )


# COMMAND ----------

# MAGIC %md
# MAGIC ## `dirichlet_bootstrap_rank_ci`
# MAGIC
# MAGIC The rank-CI sampler (`methodology.md` §Bootstrap uncertainty). The
# MAGIC normalized component matrix per year is small (≈25–130 countries × 7
# MAGIC components), so the bootstrap runs on the **driver** with numpy — far
# MAGIC simpler than `pyspark.ml` for a weight-perturbation loop over a tiny
# MAGIC matrix, and exact.
# MAGIC
# MAGIC Per the brief: 500 Dirichlet samples with concentration α_i =
# MAGIC `BOOTSTRAP_ALPHA_SCALE × |w_i|` (= 100 × weight → ~10% relative
# MAGIC perturbation; gap_ratio 0.30 ± ~0.03). Because the absolute weights sum to
# MAGIC 1.0, a single `Dirichlet(100·w)` draw has mean = the nominal weights and
# MAGIC the right per-component spread. Signs (media negative) are re-applied
# MAGIC after sampling. Per sample we recompute the composite and dense-rank;
# MAGIC `rank_ci_low`/`rank_ci_high` are the 2.5/97.5 percentiles of rank, and
# MAGIC `stable_top_n` is True when the country lands in the top-`STABLE_TOP_N` in
# MAGIC ≥ `STABLE_FRACTION` of samples.

# COMMAND ----------

def dirichlet_bootstrap_rank_ci(norm_pdf, seed=20260522):
    """`norm_pdf`: pandas DataFrame for ONE year with columns ['iso3'] +
    the seven `<key>_norm`-style columns referenced below + 'severity_rate_norm'
    for the interaction. Returns a pandas DataFrame
    [iso3, rank_ci_low, rank_ci_high, stable_top_n]."""
    import numpy as np
    import pandas as pd

    keys = COMPONENT_KEYS
    # Column the norm for each component lives in (matches normalize_components).
    norm_col = {
        "gap_ratio": "gap_ratio_norm",
        "severity_rate": "severity_rate_norm",
        "dollars_per_pin_inv": "dollars_per_pin_inv_norm",
        "chronic_index": "chronic_index_norm",
        "sector_imbalance": "sector_imbalance_norm",
        "media_attention": "media_attention_n",
        "geographic_isolation": "geographic_isolation_norm",
    }
    n = len(norm_pdf)
    if n == 0:
        return pd.DataFrame(columns=["iso3", "rank_ci_low", "rank_ci_high", "stable_top_n"])

    # value matrix V[n, 7]; the geo column is the interaction (geo × severity).
    # fillna(0.5) = neutral midpoint, consistent with normalize_components (the
    # incoming *_norm columns are already 0.5-imputed; this is a safety net).
    V = np.zeros((n, len(keys)))
    for j, k in enumerate(keys):
        col = pd.to_numeric(norm_pdf[norm_col[k]], errors="coerce").fillna(0.5).to_numpy()
        if k == "geographic_isolation":
            sevr = pd.to_numeric(norm_pdf["severity_rate_norm"], errors="coerce").fillna(0.5).to_numpy()
            col = col * sevr
        V[:, j] = col

    signs = np.array([COMPONENT_SIGNS[k] for k in keys])
    abs_w = np.array([COMPONENT_WEIGHTS[k] for k in keys])
    alpha = BOOTSTRAP_ALPHA_SCALE * abs_w

    rng = np.random.default_rng(seed)
    ranks = np.zeros((BOOTSTRAP_N, n), dtype=np.int32)
    for b in range(BOOTSTRAP_N):
        w_sample = rng.dirichlet(alpha) * signs       # signed perturbed weights
        scores = V @ w_sample
        # dense rank: highest score → rank 1
        order = np.argsort(-scores, kind="stable")
        r = np.empty(n, dtype=np.int32)
        r[order] = np.arange(1, n + 1)
        ranks[b, :] = r

    lo = np.percentile(ranks, BOOTSTRAP_CI_LOW_PCT, axis=0).round().astype(int)
    hi = np.percentile(ranks, BOOTSTRAP_CI_HIGH_PCT, axis=0).round().astype(int)
    stable = (ranks <= STABLE_TOP_N).mean(axis=0) >= STABLE_FRACTION

    return pd.DataFrame({
        "iso3": norm_pdf["iso3"].to_numpy(),
        "rank_ci_low": lo,
        "rank_ci_high": hi,
        "stable_top_n": stable,
    })
