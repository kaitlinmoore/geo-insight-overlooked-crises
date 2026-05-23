# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: `silver_media_attention`
# MAGIC
# MAGIC **Not in the `schemas.md` Silver enumeration** — added per the ReliefWeb
# MAGIC drift note (task "Reality vs schemas.md" #1): `bronze_reliefweb_attention`
# MAGIC is the load-bearing v1 input to `media_attention_norm` in
# MAGIC `gold_forgotten_crisis_index`, and that signal needs a Silver table.
# MAGIC Flagged for the user in the handoff.
# MAGIC
# MAGIC Transforms the dense per-country×month report-count grid into the
# MAGIC country×year signal the composite consumes:
# MAGIC - annualize: sum `report_count` within (iso3, year);
# MAGIC - normalize: **within-year percentile rank** in [0, 1]
# MAGIC   (`methodology.md`). The *negative* weight is applied later, in the Gold
# MAGIC   composite — this table carries the positive-direction norm.
# MAGIC
# MAGIC **Do not aggregate `report_count` across countries** to a global total
# MAGIC (21.3% of reports are multi-country tagged; a global sum double-counts).
# MAGIC The per-country annual sum here is safe.

# COMMAND ----------

from _common import *  # noqa: F403,F401

# COMMAND ----------

import dlt


@dlt.table(
    name="silver_media_attention",
    comment="Country×year ReliefWeb report counts + within-year percentile-rank "
            "norm (positive direction; negative weight applied in Gold composite).",
)
@dlt.expect_or_drop("valid_iso3", VALID_ISO3)
@dlt.expect_or_drop("non_negative_count", "report_count_annual >= 0")
@dlt.expect("norm_in_unit_interval", "media_attention_norm BETWEEN 0 AND 1")
def silver_media_attention():
    annual = (
        spark.table(bronze("bronze_reliefweb_attention"))
        .withColumn("iso3", norm_iso3(F.col("iso3")))
        .withColumn("year", F.split(F.col("year_month"), "-").getItem(0).cast("int"))
        .groupBy("iso3", "year")
        .agg(F.sum(F.col("report_count").cast("long")).alias("report_count_annual"))
    )
    return annual.withColumn(
        "media_attention_norm",
        percentile_rank_within_year(F.col("report_count_annual"), "year"),
    )
