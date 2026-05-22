# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: `gold_funding_trend` — country × year (temporal classification)
# MAGIC
# MAGIC The multi-year funding-gap trend and the `neglect_class` label that powers
# MAGIC the bonus task (`structural_neglect`). Reuses the exact same chronic /
# MAGIC classification logic as `gold_forgotten_crisis_index` via `_common`, so the
# MAGIC two never disagree.
# MAGIC
# MAGIC - `chronic_years_count`, `mean_chronic_gap`, `chronic_index` over the
# MAGIC   trailing `CHRONIC_WINDOW_YEARS`-year window (`methodology.md`).
# MAGIC - `gap_ratio_yoy_delta` = current minus prior year.
# MAGIC - `neglect_class` ∈ {chronic_neglect, acute_deterioration, improving,
# MAGIC   well_funded, chronic_no_plan}.

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

from pyspark.sql import functions as F

# COMMAND ----------

trend = chronic_features(gap_ratio_base(spark))

# neglect_class needs severity + country PIN for the chronic_no_plan need test.
sev = (
    spark.table(silver("silver_severity"))
    .select("iso3", "year", "severity_category_max")
)
pin = (
    spark.table(silver("silver_needs"))
    .where("cluster = 'ALL'")
    .select("iso3", "year", "pin_total_country")
    .dropDuplicates(["iso3", "year"])
)

trend = (
    trend
    .join(sev, ["iso3", "year"], "left")
    .join(pin, ["iso3", "year"], "left")
    .withColumn("neglect_class", neglect_class_expr())
    .select(
        "iso3", "year",
        "gap_ratio", "gap_ratio_paid_committed",
        "chronic_years_count", "mean_chronic_gap", "chronic_index",
        "neglect_class", "gap_ratio_yoy_delta",
    )
)

assert_expectations(
    trend,
    [
        ("warn:chronic_years_range", "chronic_years_count BETWEEN 0 AND 5"),
        ("fail:neglect_class_in_set",
         "neglect_class IN ('chronic_neglect','acute_deterioration','improving','well_funded','chronic_no_plan')"),
    ],
    "gold_funding_trend",
)
(trend.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .partitionBy("year")
    .saveAsTable(gold("gold_funding_trend")))
