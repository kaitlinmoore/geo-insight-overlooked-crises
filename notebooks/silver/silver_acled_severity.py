# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: `silver_acled_severity`
# MAGIC
# MAGIC Admin2 × month conflict aggregates — the *current-coverage* counterpart
# MAGIC to `silver_acled_events` (events are embargoed ~12 months; this is current
# MAGIC to last month and carries P-codes).
# MAGIC
# MAGIC - `iso3` coalesced from `priority_iso3` (fills the GTM/HND/PHL source
# MAGIC   NULLs).
# MAGIC - Explicit zero-event rows (~64% of the grid) are **kept** in this base
# MAGIC   table; analytic views filter them.
# MAGIC - `event_category` ∈ {political_violence, civilian_targeting,
# MAGIC   demonstration}; **`civilian_targeting` overlaps political_violence** —
# MAGIC   downstream must not sum all three (documented, not enforced here since
# MAGIC   Silver keeps the grain intact).

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

import dlt


@dlt.table(
    name="silver_acled_severity",
    comment="ACLED admin2×month×category counts, current. iso3 coalesced from "
            "priority_iso3 (fills GTM/HND/PHL). Zero-event grid rows retained.",
)
@dlt.expect_or_drop("non_negative_events", "events >= 0")
@dlt.expect("valid_category",
            "event_category IN ('political_violence','civilian_targeting','demonstration')")
@dlt.expect("iso3_present_after_coalesce", "iso3 IS NOT NULL")
def silver_acled_severity():
    return (
        spark.table(bronze("bronze_acled_severity"))
        .withColumn("iso3", norm_iso3(F.coalesce(F.col("priority_iso3"), F.col("iso3"))))
        .select(
            "iso3",
            F.col("country"),
            F.col("admin1"),
            F.col("admin2"),
            F.upper(F.trim(F.col("admin1_pcode"))).alias("admin1_pcode"),
            F.upper(F.trim(F.col("admin2_pcode"))).alias("admin2_pcode"),
            F.col("event_category"),
            F.col("year").cast("int").alias("year"),
            F.col("month_num").cast("int").alias("month_num"),
            F.to_date(F.col("month_start")).alias("month_start"),
            F.col("events").cast("int").alias("events"),
            F.col("fatalities").cast("int").alias("fatalities"),
        )
    )
