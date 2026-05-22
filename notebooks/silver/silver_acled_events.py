# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: `silver_acled_events`
# MAGIC
# MAGIC Point-level ACLED events, geocoded and **H3 res-5 indexed** for hotspot
# MAGIC detection.
# MAGIC
# MAGIC - `iso3` = `priority_iso3` (the reliable alpha-3 added at acquisition),
# MAGIC   falling back to the numeric `iso` → alpha-3 bridge through
# MAGIC   `silver_country_dim.iso_numeric`.
# MAGIC - `h3_r5` via the Databricks built-in `h3_longlatash3string` (stock on
# MAGIC   Photon-enabled DBR — no extra dependency).
# MAGIC - `geo_precision` / `time_precision` retained for hotspot down-weighting.
# MAGIC
# MAGIC **Recency.** The account embargo bounds events to ~12 months stale; the
# MAGIC hotspot logic downstream must treat `max(event_date)` as "now", not the
# MAGIC calendar date.

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

import dlt


@dlt.table(
    name="silver_acled_events",
    comment="ACLED point events with iso3, H3 res-5 index, event_month. "
            "geo_precision>=2 retained but flagged for hotspot weighting. "
            "Embargoed to ~12 months stale.",
)
@dlt.expect_or_drop("valid_coords",
                    "latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180")
@dlt.expect_or_drop("non_null_h3", "h3_r5 IS NOT NULL")
@dlt.expect("geo_precision_flagged", "geo_precision = 1 OR geo_precision_low = true")
@dlt.expect("non_negative_fatalities", "fatalities >= 0")
def silver_acled_events():
    ev = spark.table(bronze("bronze_acled_events"))
    dim = dlt.read("silver_country_dim").select(
        F.col("iso_numeric"), F.col("iso3").alias("dim_iso3")
    )

    ev = (
        ev
        .withColumn("latitude", F.col("latitude").cast("double"))
        .withColumn("longitude", F.col("longitude").cast("double"))
        .join(dim, ev["iso"].cast("int") == dim["iso_numeric"], "left")
        .withColumn("iso3", norm_iso3(F.coalesce(F.col("priority_iso3"), F.col("dim_iso3"))))
        .withColumn("event_date", F.to_date(F.col("event_date")))
        .withColumn("event_month", F.trunc(F.col("event_date"), "month"))
        .withColumn("geo_precision", F.col("geo_precision").cast("int"))
        .withColumn("geo_precision_low", F.col("geo_precision").cast("int") >= 2)
        .withColumn("fatalities", F.col("fatalities").cast("int"))
        .withColumn(
            "h3_r5",
            F.expr("h3_longlatash3string(longitude, latitude, 5)"),
        )
    )

    return ev.select(
        F.col("event_id_cnty"),
        "iso3",
        "event_date",
        "event_month",
        F.col("year").cast("int").alias("year"),
        F.col("event_type"),
        F.col("sub_event_type"),
        F.col("disorder_type"),
        F.col("actor1"),
        F.col("actor2"),
        F.col("admin1"),
        F.col("admin2"),
        "latitude",
        "longitude",
        "geo_precision",
        "geo_precision_low",
        F.col("time_precision").cast("int").alias("time_precision"),
        "fatalities",
        "h3_r5",
    )
