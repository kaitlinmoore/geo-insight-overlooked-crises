# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: `gold_funding_funnel` — country × year × stage
# MAGIC
# MAGIC The three-stage funding funnel (required → pledged → committed → paid) per
# MAGIC country-year. Substrate for `get_funding_funnel`.
# MAGIC
# MAGIC - **required** comes from `silver_requirements` (plan rows; per-country
# MAGIC   requirement, DECISIONS 2026-05-22).
# MAGIC - **pledged / committed / paid** come from `silver_fts_flows`, pivoted on
# MAGIC   `status`. `pending_attribution` flows are excluded (held out of the
# MAGIC   country-level funding picture, per open-questions.md), matching the
# MAGIC   numerator the index uses.
# MAGIC - `pct_of_requirement` aligns each stage to the requirement; NULL where no
# MAGIC   requirement exists (off-plan-only countries).

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

from pyspark.sql import functions as F

# COMMAND ----------

reqs = requirements_by_country(spark).select(
    "iso3", "year", "requirement_usd"
)
funding = funding_by_country(spark)  # excludes pending_attribution

joined = reqs.join(funding, ["iso3", "year"], "outer")

# long-format: one row per (iso3, year, stage)
stages = [
    ("required", F.col("requirement_usd")),
    ("pledged", F.col("funded_pledged_usd")),
    ("committed", F.col("funded_committed_usd")),
    ("paid", F.col("funded_paid_usd")),
]

stage_dfs = []
for stage_name, amount_col in stages:
    stage_dfs.append(
        joined.select(
            "iso3", "year",
            F.lit(stage_name).alias("stage"),
            F.coalesce(amount_col, F.lit(0.0)).cast("double").alias("amount_usd"),
            F.when(
                (F.col("requirement_usd").isNotNull()) & (F.col("requirement_usd") > 0),
                F.coalesce(amount_col, F.lit(0.0)) / F.col("requirement_usd"),
            ).alias("pct_of_requirement"),
        )
    )

funnel = stage_dfs[0]
for d in stage_dfs[1:]:
    funnel = funnel.unionByName(d)

funnel = funnel.where("iso3 IS NOT NULL AND year IS NOT NULL")

assert_expectations(
    funnel,
    [
        ("warn:non_negative_amount", "amount_usd >= 0"),
        ("fail:valid_stage", "stage IN ('required','pledged','committed','paid')"),
    ],
    "gold_funding_funnel",
)
(funnel.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .partitionBy("year")
    .saveAsTable(gold("gold_funding_funnel")))
