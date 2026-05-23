# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: `silver_fts_flows`  — multi-country allocation cascade
# MAGIC
# MAGIC Cleaned, country-attributed funding flows. One source flow may fan out to
# MAGIC several country rows; each carries `allocation_method`,
# MAGIC `allocation_weight`, and `source_flow_id` for full lineage back to
# MAGIC `bronze_fts_flows`.
# MAGIC
# MAGIC ## Cascade order (methodology.md + DECISIONS 2026-05-22 + open-questions)
# MAGIC
# MAGIC For each (deduped) flow, exploded over its `destLocations` comma-list:
# MAGIC
# MAGIC 1. **`country_tagged`** — exactly one destination country → weight 1.0.
# MAGIC    (94% of rows / 68.5% of $.)
# MAGIC 2. **`pending_attribution`** — multi-country, *recent* (flow_date within
# MAGIC    6 months of the dataset's max flow_date) **and** more than 5
# MAGIC    destination countries. These are the 2026 regional mega-flows parked
# MAGIC    pending FTS disaggregation; population-weighting them would
# MAGIC    over-attribute to large countries. Held out of `gap_ratio` downstream
# MAGIC    (Gold filters `allocation_method <> 'pending_attribution'`). Checked
# MAGIC    **before** requirements/population so a recent mega-flow can't slip
# MAGIC    into the population leg. Weight = population share (so the lineage
# MAGIC    survives if the flow is later promoted), summing to 1.
# MAGIC 3. **`requirements_weighted`** — multi-country with a plan whose
# MAGIC    per-country requirements are all known in `silver_requirements`:
# MAGIC    weight_i = req_i / Σ req. (Rare: 99% of multi-country flows have no
# MAGIC    destPlan.)
# MAGIC 4. **`population_weighted_fallback`** — multi-country, requirements
# MAGIC    unavailable, but the country list maps to known COD-PS populations:
# MAGIC    weight_i = pop_i / Σ pop. (De-facto handler for ~30% of incoming $.)
# MAGIC 5. **`regional_unattributed`** — no destination country at all
# MAGIC    (empty/NULL `destLocations`) **or** a multi-country flow whose
# MAGIC    countries have no known population to weight by. iso3 is NULL; these
# MAGIC    rows are dropped by the `valid_iso3` expectation (excluded from
# MAGIC    country-level analysis, per methodology). The aggregate regional total
# MAGIC    remains recoverable from Bronze for the Methodology transparency panel.
# MAGIC
# MAGIC ## Shared-boundary dedupe
# MAGIC
# MAGIC `onBoundary='shared'` flows appear in both the incoming and outgoing
# MAGIC files. We keep one row per `id` for shared flows (preferring `incoming`,
# MAGIC the destination-country perspective we attribute on); `single` flows are
# MAGIC untouched.

# COMMAND ----------

from _common import *  # noqa: F403,F401

# COMMAND ----------

import dlt

# Recency window for the pending_attribution heuristic (open-questions.md).
_PENDING_RECENCY_MONTHS = 6
_PENDING_MIN_COUNTRIES = 5  # "more than 5" → strictly > 5


@dlt.table(
    name="silver_fts_flows",
    comment="Country-attributed funding flow shares. allocation_method ∈ "
            "{country_tagged, requirements_weighted, population_weighted_fallback, "
            "pending_attribution, regional_unattributed}. pending_attribution "
            "rows are held out of gap_ratio downstream.",
)
@dlt.expect_or_drop("valid_status", "status IN ('paid','commitment','pledge')")
@dlt.expect_or_drop("non_negative_amount", NON_NEGATIVE_AMOUNT)
@dlt.expect_or_drop("valid_iso3", VALID_ISO3)
@dlt.expect("weights_sum_to_one", "weight_sum_check BETWEEN 0.999 AND 1.001")
@dlt.expect("no_shared_double_count", "on_boundary <> 'shared' OR _kept_shared = true")
def silver_fts_flows():
    raw = spark.table(bronze("bronze_fts_flows"))

    # --- shared-boundary dedupe -------------------------------------------
    boundary_rank = (
        F.when(F.col("boundary") == "incoming", 1)
        .when(F.col("boundary") == "internal", 2)
        .otherwise(3)
    )
    w_id = Window.partitionBy("id").orderBy(boundary_rank)
    deduped = (
        raw.withColumn("_rk", F.row_number().over(w_id))
        # keep all 'single' rows; for 'shared' keep only the top-ranked id row
        .withColumn(
            "_kept_shared",
            (F.col("onBoundary") != "shared") | (F.col("_rk") == 1),
        )
        .where("_kept_shared = true")
    )

    # --- normalize the columns we keep ------------------------------------
    flows = deduped.select(
        F.col("id").alias("source_flow_id"),
        F.to_date(F.col("date")).alias("flow_date"),
        F.col("amountUSD").cast("double").alias("amount_usd_total"),
        F.col("status"),
        # destGlobalClusters can be a comma list; take the first, normalized.
        F.trim(F.split(F.col("destGlobalClusters"), ",").getItem(0)).alias("cluster"),
        F.col("srcOrganization").alias("donor_org"),
        F.col("srcOrganizationTypes").alias("donor_type"),
        F.col("destPlanCode").alias("plan_code"),
        F.col("destLocations"),
        F.col("boundary"),
        F.col("onBoundary").alias("on_boundary"),
        F.col("_kept_shared"),
    )

    # dataset "now" = max flow_date (ACLED-style: data may lag the calendar).
    max_date = flows.agg(F.max("flow_date")).first()[0]
    recent_floor = F.add_months(F.lit(max_date), -_PENDING_RECENCY_MONTHS)

    # --- explode destinations (explode_outer keeps empty/NULL as one row) --
    dest_arr = F.expr(
        "filter(transform(split(destLocations, ','), x -> upper(trim(x))), x -> length(x) = 3)"
    )
    flows = flows.withColumn("_dest", dest_arr)
    # F.size() returns -1 for a NULL array, so coalesce explicitly to 0.
    flows = flows.withColumn(
        "n_dest",
        F.when(F.col("_dest").isNull(), F.lit(0)).otherwise(F.size("_dest")),
    )
    exploded = flows.withColumn("iso3", F.explode_outer("_dest"))

    # --- per-country weight inputs ----------------------------------------
    pops = (
        dlt.read("silver_population")
        .where("admin1_pcode IS NULL")  # national totals only
        .select("iso3", F.col("population_total").cast("double").alias("pop"))
    )
    reqs = (
        dlt.read("silver_requirements")
        .where("plan_code IS NOT NULL AND requirement_usd IS NOT NULL AND requirement_usd > 0")
        .select(F.col("plan_code"), F.col("iso3"), F.col("requirement_usd").alias("req"))
        .dropDuplicates(["plan_code", "iso3"])
    )

    exploded = (
        exploded
        .join(pops, on="iso3", how="left")
        .join(reqs, on=["plan_code", "iso3"], how="left")
    )

    # --- per-flow aggregates for the cascade decision ---------------------
    w_flow = Window.partitionBy("source_flow_id")
    exploded = (
        exploded
        .withColumn("pop_sum", F.sum(F.coalesce("pop", F.lit(0.0))).over(w_flow))
        .withColumn("req_sum", F.sum(F.coalesce("req", F.lit(0.0))).over(w_flow))
        .withColumn("n_req_present", F.sum(F.when(F.col("req").isNotNull(), 1).otherwise(0)).over(w_flow))
        .withColumn("is_recent", F.col("flow_date") >= recent_floor)
    )
    # requirements_weighted only when EVERY destination country has a positive
    # requirement under the plan (so the weights are fully defined).
    has_full_reqs = (F.col("n_req_present") == F.col("n_dest")) & (F.col("req_sum") > 0)

    method = (
        F.when(F.col("n_dest") == 1, F.lit("country_tagged"))
        .when(F.col("n_dest") == 0, F.lit("regional_unattributed"))
        .when(F.col("is_recent") & (F.col("n_dest") > _PENDING_MIN_COUNTRIES),
              F.lit("pending_attribution"))
        .when(has_full_reqs, F.lit("requirements_weighted"))
        .when(F.col("pop_sum") > 0, F.lit("population_weighted_fallback"))
        .otherwise(F.lit("regional_unattributed"))
    )
    exploded = exploded.withColumn("allocation_method", method)

    # --- weights per method -----------------------------------------------
    # pop_share / req_share are well-defined only where their denominator > 0;
    # the method gating guarantees that for the population/requirements legs.
    # pending_attribution may have pop_sum = 0 (obscure ISO3s with no COD pop),
    # so it falls back to an equal split — it is held out of gap_ratio anyway.
    pop_share = F.coalesce(F.col("pop"), F.lit(0.0)) / F.col("pop_sum")
    equal_share = F.lit(1.0) / F.col("n_dest")
    weight = (
        F.when(F.col("allocation_method") == "country_tagged", F.lit(1.0))
        .when(F.col("allocation_method") == "requirements_weighted",
              F.coalesce(F.col("req"), F.lit(0.0)) / F.col("req_sum"))
        .when(F.col("allocation_method") == "population_weighted_fallback", pop_share)
        .when(F.col("allocation_method") == "pending_attribution",
              F.when(F.col("pop_sum") > 0, pop_share).otherwise(equal_share))
        # regional_unattributed: collapsed below to one null-iso3 row, weight 1.0
        .otherwise(F.lit(1.0))
    )
    exploded = exploded.withColumn("allocation_weight", weight)

    # regional_unattributed: a multi-country flow with no usable weights would
    # otherwise produce N rows each carrying the full amount. Null the iso3
    # (excluded from country analysis per methodology) and collapse to ONE row
    # per flow so the weight sums to 1 and the dollars aren't multiplied.
    is_regional = F.col("allocation_method") == "regional_unattributed"
    exploded = exploded.withColumn(
        "iso3", F.when(is_regional, F.lit(None).cast("string")).otherwise(F.col("iso3"))
    )
    attributed = exploded.where("allocation_method <> 'regional_unattributed'")
    regional = (
        exploded.where("allocation_method = 'regional_unattributed'")
        .withColumn("allocation_weight", F.lit(1.0))
        .dropDuplicates(["source_flow_id"])
    )
    combined = attributed.unionByName(regional)

    # weights-sum-to-one check (per source flow), computed after the collapse.
    combined = combined.withColumn(
        "weight_sum_check", F.sum("allocation_weight").over(w_flow)
    )

    return combined.select(
        "source_flow_id",
        "iso3",
        "plan_code",
        (F.col("amount_usd_total") * F.col("allocation_weight")).alias("amount_usd"),
        "status",
        "cluster",
        "donor_org",
        "donor_type",
        "flow_date",
        "boundary",
        "on_boundary",
        "allocation_method",
        "allocation_weight",
        "weight_sum_check",
        "_kept_shared",
    )
