# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: `gold_hotspots` — 📋 Day-4 stretch (LOWER FIDELITY)
# MAGIC
# MAGIC Spatial-temporal conflict clusters from H3-indexed ACLED events. Substrate
# MAGIC for `spatial_cluster_events`. **Day-4 stretch, not v1 critical** — drafted
# MAGIC at lower fidelity per the task brief.
# MAGIC
# MAGIC **What is implemented:** H3-cell × 90-day-period event/fatality counts, a
# MAGIC within-country density z-score, the >2σ spatial-hotspot flag, and the >50%
# MAGIC period-over-period jump (`is_emerging`).
# MAGIC
# MAGIC **What is STUBBED (needs work before deploy):**
# MAGIC - **admin1 point-in-polygon** (`admin1_pcode`): requires a Sedona spatial
# MAGIC   join of H3-cell centroids against `silver_boundaries` geometries. Emitted
# MAGIC   as NULL with a TODO. The H3 cell itself is correct.
# MAGIC - **Recency**: `silver_acled_events` is embargoed to ≥12 months old, so
# MAGIC   "now" is the max `event_date`, not the calendar date.

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql import Window

# COMMAND ----------

events = (
    spark.table(silver("silver_acled_events"))
    .where("h3_r5 IS NOT NULL AND iso3 IS NOT NULL")
    .withColumn("event_date", F.to_date("event_date"))
)

# dataset "now" = max event_date (embargo-aware), bucket into 90-day periods.
max_date = events.agg(F.max("event_date")).first()[0]
events = events.withColumn(
    "_days_back", F.datediff(F.lit(max_date), F.col("event_date"))
)
events = events.withColumn("_period_idx", (F.col("_days_back") / F.lit(90)).cast("int"))
events = events.withColumn(
    "period",
    F.concat(F.lit("P-"), F.col("_period_idx").cast("string")),  # P-0 = most recent 90d
)

# COMMAND ----------

agg = (
    events.groupBy("iso3", "h3_r5", "period", "_period_idx")
    .agg(
        F.count(F.lit(1)).alias("event_count"),
        F.sum(F.coalesce(F.col("fatalities"), F.lit(0))).alias("fatalities"),
    )
)

# within-country density z-score (per period)
w_country_period = Window.partitionBy("iso3", "period")
agg = (
    agg
    .withColumn("_mean", F.avg("event_count").over(w_country_period))
    .withColumn("_std", F.stddev_samp("event_count").over(w_country_period))
    .withColumn(
        "density_zscore",
        F.when(F.col("_std") > 0, (F.col("event_count") - F.col("_mean")) / F.col("_std")).otherwise(0.0),
    )
    .withColumn("is_spatial_hotspot", F.col("density_zscore") > 2.0)
)

# emerging: >50% jump vs the immediately prior 90-day period for the same cell.
w_cell = Window.partitionBy("iso3", "h3_r5").orderBy(F.col("_period_idx").desc())
agg = (
    agg
    .withColumn("_prev_count", F.lag("event_count", 1).over(w_cell))
    .withColumn(
        "density_jump_pct",
        F.when((F.col("_prev_count").isNotNull()) & (F.col("_prev_count") > 0),
               (F.col("event_count") - F.col("_prev_count")) / F.col("_prev_count")),
    )
    .withColumn("is_emerging", F.coalesce(F.col("density_jump_pct") > 0.5, F.lit(False)))
    # TODO(Day-4): point-in-polygon against silver_boundaries (Sedona) for admin1.
    .withColumn("admin1_pcode", F.lit(None).cast("string"))
)

out = agg.select(
    "h3_r5", "iso3", "admin1_pcode", "period",
    "event_count", "fatalities", "density_zscore", "is_spatial_hotspot",
    "density_jump_pct", "is_emerging",
)

assert_expectations(
    out,
    [("fail:valid_h3", "h3_r5 IS NOT NULL"),
     ("warn:period_present", "period IS NOT NULL")],
    "gold_hotspots",
)
(out.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(gold("gold_hotspots")))
