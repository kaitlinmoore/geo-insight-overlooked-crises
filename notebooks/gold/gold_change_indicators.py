# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: `gold_change_indicators` — country × period
# MAGIC
# MAGIC Period-over-period movement in the ranking — powers the Triage change
# MAGIC indicators (`↑5 positions`, `NEW to top 10`) and the alert roadmap.
# MAGIC Substrate for `get_ranking_delta`.
# MAGIC
# MAGIC **v1 period grain = year.** The index is year-versioned, so deltas are
# MAGIC year-over-year (`period` = the year as a string). Finer quarterly periods
# MAGIC (`2026-Q1`) are a refinement once intra-year index snapshots exist —
# MAGIC flagged for the user. ACLED uses `silver_acled_severity` (current to last
# MAGIC month) rather than the embargoed event path.
# MAGIC
# MAGIC - `rank_delta` = `rank[y-1] − rank[y]` → **positive means improved
# MAGIC   visibility** (moved toward rank 1 / more overlooked).
# MAGIC - `direction` keys on `rank_delta`.

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql import Window

# COMMAND ----------

index = spark.table(gold("gold_forgotten_crisis_index")).select(
    "iso3", "year", "rank_position", "gap_ratio", "severity_rate"
)

acled = (
    spark.table(silver("silver_acled_severity"))
    .where("event_category = 'political_violence'")
    .withColumn("year", F.col("year").cast("int"))
    .groupBy("iso3", "year")
    .agg(F.sum("events").alias("acled_events"))
)

base = index.join(acled, ["iso3", "year"], "left")

by_year = Window.partitionBy("iso3").orderBy("year")
deltas = (
    base
    .withColumn("rank_delta", F.lag("rank_position", 1).over(by_year) - F.col("rank_position"))
    .withColumn("gap_ratio_delta", F.col("gap_ratio") - F.lag("gap_ratio", 1).over(by_year))
    .withColumn("severity_delta", F.col("severity_rate") - F.lag("severity_rate", 1).over(by_year))
    .withColumn("acled_events_delta", F.col("acled_events") - F.lag("acled_events", 1).over(by_year))
    .withColumn("period", F.col("year").cast("string"))
    .withColumn(
        "direction",
        F.when(F.col("rank_delta").isNull(), F.lit("stable"))
        .when(F.col("rank_delta") > 0, F.lit("worsening"))   # moved toward rank 1
        .when(F.col("rank_delta") < 0, F.lit("improving"))
        .otherwise(F.lit("stable")),
    )
    .select(
        "iso3", "period",
        "rank_delta", "gap_ratio_delta", "severity_delta", "acled_events_delta",
        "direction",
    )
    .where("period IS NOT NULL")
)

assert_expectations(
    deltas,
    [
        ("fail:period_parseable", "period RLIKE '^[0-9]{4}'"),
        ("fail:direction_in_set", "direction IN ('worsening','improving','stable')"),
    ],
    "gold_change_indicators",
)
(deltas.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(gold("gold_change_indicators")))
