# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: `gold_explanation_features` — country × year
# MAGIC
# MAGIC The deterministic decomposition substrate: every component's raw value, its
# MAGIC within-year normalized form, the weight it carries, and its contribution
# MAGIC (`sign × weight × norm`) to the composite — so `explain_ranking` can break
# MAGIC down a country's score without recomputation. The contributions sum to
# MAGIC `overlooked_score`.
# MAGIC
# MAGIC To stay byte-consistent with `gold_forgotten_crisis_index`, this notebook
# MAGIC re-derives the components with the same `_common` helpers, **restricted to
# MAGIC the same in-scope cohort** (read back from the index) and normalized within
# MAGIC that cohort — then asserts `Σ contribution_* ≈ overlooked_score`.
# MAGIC
# MAGIC Also carries `excluded_pending_attribution_usd`: the FTS dollars held out of
# MAGIC `gap_ratio` (the 2026 regional mega-flows), documented per the task brief.

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

from pyspark.sql import functions as F

# COMMAND ----------

index = spark.table(gold("gold_forgotten_crisis_index")).select(
    "iso3", "year", "overlooked_score", "rank_position"
)

# rebuild components, restrict to the ranked cohort, normalize within it
components = build_components(spark)
cohort = components.join(index, ["iso3", "year"], "inner")
norm = normalize_components(cohort)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Per-component contributions
# MAGIC
# MAGIC `contribution_i = sign_i × weight_i × norm_i` (the geographic-isolation
# MAGIC term uses the interaction `norm(geo) × norm(severity_rate)`).

# COMMAND ----------

W = COMPONENT_WEIGHTS
S = COMPONENT_SIGNS

# 0.5 = neutral midpoint, consistent with _common.normalize_components /
# composite_score_expr. The *_norm columns are already 0.5-imputed where their
# raw input was null, so these coalesce defaults are a belt-and-suspenders
# safety net — kept at 0.5 so the contribution math matches the composite math.
norm_value = {
    "gap_ratio": F.coalesce(F.col("gap_ratio_norm"), F.lit(0.5)),
    "severity_rate": F.coalesce(F.col("severity_rate_norm"), F.lit(0.5)),
    "dollars_per_pin_inv": F.coalesce(F.col("dollars_per_pin_inv_norm"), F.lit(0.5)),
    "chronic_index": F.coalesce(F.col("chronic_index_norm"), F.lit(0.5)),
    "sector_imbalance": F.coalesce(F.col("sector_imbalance_norm"), F.lit(0.5)),
    "media_attention": F.col("media_attention_n"),
    "geographic_isolation": (
        F.coalesce(F.col("geographic_isolation_norm"), F.lit(0.5))
        * F.coalesce(F.col("severity_rate_norm"), F.lit(0.5))
    ),
}

feat = norm
for key in COMPONENT_KEYS:
    feat = feat.withColumn(f"weight_{key}", F.lit(S[key] * W[key]))
    feat = feat.withColumn(f"contribution_{key}", F.lit(S[key] * W[key]) * norm_value[key])

feat = feat.withColumn(
    "contribution_sum",
    sum(F.col(f"contribution_{k}") for k in COMPONENT_KEYS),
)

# pending_attribution dollars held out of gap_ratio (documented transparency).
pending = (
    spark.table(silver("silver_fts_flows"))
    .where("allocation_method = 'pending_attribution'")
    .withColumn("year", F.year("flow_date"))
    .groupBy("iso3", "year")
    .agg(F.sum("amount_usd").alias("excluded_pending_attribution_usd"))
)
feat = feat.join(pending, ["iso3", "year"], "left").fillna(
    0.0, subset=["excluded_pending_attribution_usd"]
)

# COMMAND ----------

select_cols = (
    ["iso3", "year", "overlooked_score", "rank_position"]
    # raw
    + ["gap_ratio", "severity_rate", "dollars_per_pin", "chronic_index",
       "sector_imbalance", "media_attention_norm", "geographic_isolation"]
    # norms
    + ["gap_ratio_norm", "severity_rate_norm", "dollars_per_pin_inv_norm",
       "chronic_index_norm", "sector_imbalance_norm", "media_attention_n",
       "geographic_isolation_norm"]
    # weights + contributions
    + [f"weight_{k}" for k in COMPONENT_KEYS]
    + [f"contribution_{k}" for k in COMPONENT_KEYS]
    + ["contribution_sum", "excluded_pending_attribution_usd"]
)
explanation = feat.select(*select_cols)

assert_expectations(
    explanation,
    [
        ("fail:contributions_sum_to_score",
         "abs(contribution_sum - overlooked_score) < 0.0001"),
        ("warn:norms_in_unit_interval",
         "gap_ratio_norm BETWEEN 0 AND 1 AND severity_rate_norm BETWEEN 0 AND 1"),
    ],
    "gold_explanation_features",
)
(explanation.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .partitionBy("year")
    .saveAsTable(gold("gold_explanation_features")))
