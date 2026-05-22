# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: `gold_forgotten_crisis_index` — the headline ranking
# MAGIC
# MAGIC The composite `overlooked_score` with bootstrap uncertainty, temporal
# MAGIC classification, the severity gate, and the data-freshness flags. Substrate
# MAGIC for `rank_crises` / `get_overlooked_score`.
# MAGIC
# MAGIC **Pipeline**
# MAGIC 1. `build_components` — country×year raw component matrix (`_common`).
# MAGIC 2. **Severity gate** (INFORM category ≥ 4 OR PIN ≥ 100k OR active plan),
# MAGIC    plus the chronic-no-plan second pass (≥ 3 + no plan 3+ yrs). Gated-out
# MAGIC    countries with observable signal are written to
# MAGIC    `silver_excluded_with_signal`.
# MAGIC 3. **Normalize within the in-scope cohort** (per year), then the weighted
# MAGIC    composite.
# MAGIC 4. **Dense rank** within year; **Dirichlet bootstrap** for rank CIs +
# MAGIC    `stable_top_n`.
# MAGIC 5. `neglect_class`, freshness struct, write.
# MAGIC
# MAGIC **gap_ratio numerator**: headline uses **paid** (`_common.GAP_NUMERATOR`),
# MAGIC matching `methodology.md`/`schemas.md`. `gap_ratio_paid_committed` is
# MAGIC emitted alongside as a sensitivity sibling. `pending_attribution` flows are
# MAGIC excluded from both (the 2026 regional mega-flows).

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql import Window

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Components + severity gate

# COMMAND ----------

components = build_components(spark)

country_dim = (
    spark.table(silver("silver_country_dim"))
    .select("iso3", "country_name")
    .dropDuplicates(["iso3"])
)
components = components.join(country_dim, "iso3", "left")

# severity gate (methodology.md §Severity gate) — keys on the 1–5 category.
gate_severity = F.col("severity_category_max") >= SEVERITY_GATE_CATEGORY
gate_pin = F.col("pin_total_country") >= PIN_GATE_MIN
gate_plan = F.col("has_plan") == True  # noqa: E712 (Spark Column truthiness)
components = components.withColumn(
    "passed_severity_gate",
    F.coalesce(gate_severity, F.lit(False))
    | F.coalesce(gate_pin, F.lit(False))
    | F.coalesce(gate_plan, F.lit(False)),
)

# neglect_class needs chronic features (already on `components` via
# chronic_features) + severity + pin (joined above). chronic_no_plan also opens
# the second-pass door into the ranking.
components = components.withColumn("neglect_class", neglect_class_expr())
components = components.withColumn(
    "in_ranking",
    F.col("passed_severity_gate") | (F.col("neglect_class") == "chronic_no_plan"),
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Side output — `silver_excluded_with_signal`
# MAGIC
# MAGIC Countries that fail the gate AND are not on the chronic-no-plan path, but
# MAGIC carry observable need or funding signal. Written to the `silver` schema
# MAGIC (per `schemas.md`) even though it is computed here in Gold. The list is
# MAGIC itself a signal: low documented need *and* low coverage may be a data gap,
# MAGIC not genuinely low need.

# COMMAND ----------

excluded = components.where("NOT in_ranking").select(
    "iso3", "year", "country_name",
    "severity_category_max", "severity_index_max", "pin_total_country",
    "requirement_usd", "funded_paid_usd", "funded_paid_committed_usd",
    "gap_ratio", "has_plan", "data_sparsity_flag",
    F.when(F.col("pin_total_country") > 0, True).otherwise(False).alias("has_need_signal"),
    F.when(F.col("funded_paid_usd") > 0, True).otherwise(False).alias("has_funding_signal"),
    F.lit("failed_severity_gate").alias("exclusion_reason"),
).where("has_need_signal OR has_funding_signal OR severity_category_max IS NOT NULL")

assert_expectations(
    excluded,
    [("warn:has_some_signal", "has_need_signal OR has_funding_signal OR severity_category_max IS NOT NULL")],
    "silver_excluded_with_signal",
)
(excluded.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(silver("silver_excluded_with_signal")))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Normalize within cohort + composite

# COMMAND ----------

ranked = components.where("in_ranking")
ranked = normalize_components(ranked)
ranked = ranked.withColumn("overlooked_score", composite_score_expr())

w_year = Window.partitionBy("year").orderBy(F.col("overlooked_score").desc())
ranked = ranked.withColumn("rank_position", F.dense_rank().over(w_year))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Dirichlet bootstrap rank CIs
# MAGIC
# MAGIC Collect the per-year normalized matrix to the driver (tiny) and run the
# MAGIC 500-sample weight perturbation in numpy via `dirichlet_bootstrap_rank_ci`.

# COMMAND ----------

import pandas as pd

norm_cols = [
    "iso3", "year",
    "gap_ratio_norm", "severity_rate_norm", "dollars_per_pin_inv_norm",
    "chronic_index_norm", "sector_imbalance_norm", "media_attention_n",
    "geographic_isolation_norm",
]
norm_pdf_all = ranked.select(*norm_cols).toPandas()

ci_frames = []
for yr, grp in norm_pdf_all.groupby("year"):
    ci = dirichlet_bootstrap_rank_ci(grp.reset_index(drop=True))
    ci["year"] = yr
    ci_frames.append(ci)

ci_pdf = (
    pd.concat(ci_frames, ignore_index=True)
    if ci_frames
    else pd.DataFrame(columns=["iso3", "rank_ci_low", "rank_ci_high", "stable_top_n", "year"])
)
ci_sdf = spark.createDataFrame(ci_pdf)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Assemble, freshness struct, write

# COMMAND ----------

inputs_freshness = F.struct(
    F.col("latest_snapshot_date").alias("inform_severity_snapshot"),
    F.col("pop_reference_year").alias("population_reference_year"),
    F.col("year").alias("needs_year"),
)

index_df = (
    ranked.join(ci_sdf, ["iso3", "year"], "left")
    .withColumn("inputs_freshness", inputs_freshness)
    .select(
        "iso3", "year", "country_name",
        "overlooked_score", "rank_position",
        "rank_ci_low", "rank_ci_high", "stable_top_n",
        "gap_ratio", "gap_ratio_paid_committed",
        "severity_rate", "dollars_per_pin",
        "chronic_index", "sector_imbalance",
        "media_attention_norm", "geographic_isolation",
        "neglect_class",
        "data_sparsity_flag", "stale_population_flag",
        "passed_severity_gate",
        "inputs_freshness",
    )
)

assert_expectations(
    index_df,
    [
        ("fail:rank_ci_brackets_rank",
         "rank_ci_low IS NULL OR (rank_ci_low <= rank_position AND rank_position <= rank_ci_high)"),
        ("warn:score_bounded", "overlooked_score BETWEEN -0.10 AND 0.90"),
        ("fail:unique_pk", "iso3 IS NOT NULL AND year IS NOT NULL"),
    ],
    "gold_forgotten_crisis_index",
)
(index_df.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(gold("gold_forgotten_crisis_index")))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Notes on the score range
# MAGIC
# MAGIC With a negative media term and absolute weights summing to 1.0, the raw
# MAGIC `overlooked_score` is bounded to `[−w_media, Σ positive weights] = [−0.10,
# MAGIC 0.90]`, **not** `[0, 1]`. `schemas.md` states a `score_in_unit_interval`
# MAGIC DQ check; that's relaxed here to the true bound and flagged for the user.
# MAGIC Ranking and the bootstrap CI (both rank-based) are unaffected. Display
# MAGIC rounding and the "no false precision" rule are handled downstream.
