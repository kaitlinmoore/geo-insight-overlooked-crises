# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: `silver_needs`
# MAGIC
# MAGIC Country × year × cluster People-in-Need from `bronze_hno` (2024/2025/2026).
# MAGIC
# MAGIC **Transforms**
# MAGIC - Drop the HXL hashtag row (`Country ISO3` starts with `#`).
# MAGIC - Keep **country-level** rows only (Admin 1 & 2 P-codes NULL — true for
# MAGIC   all 2026 rows since that file has no admin columns); the subnational
# MAGIC   grain lives in `silver_subnational_needs`.
# MAGIC - Collapse the demographic `Category` fan-out by keeping the `total`
# MAGIC   rows (the aggregate per country/cluster).
# MAGIC - Cast the string-typed numerics (HNO 2024/2025 are all-string because of
# MAGIC   the HXL row; thousands separators stripped before cast). Parse failures
# MAGIC   become NULL and are dropped by `non_negative_pin`.
# MAGIC - Isolate the `Cluster='ALL'` caseload as the per-country
# MAGIC   `pin_total_country`.
# MAGIC - `has_subnational` = whether the country-year has any admin1/2 rows
# MAGIC   (always false for 2026).

# COMMAND ----------

from _common import *  # noqa: F403,F401

# COMMAND ----------

import dlt


def _to_bigint(col):
    """Strip thousands separators / stray spaces, then cast to bigint."""
    return F.regexp_replace(F.trim(col), r"[,\s]", "").cast("bigint")


@dlt.table(
    name="silver_needs",
    comment="Country×year×cluster PIN from HNO. pin_total_country = the "
            "Cluster='ALL' country caseload. has_subnational false for 2026.",
)
@dlt.expect_or_drop("valid_iso3", VALID_ISO3)
@dlt.expect_or_drop("non_negative_pin", "people_in_need >= 0")
@dlt.expect("pin_not_exceeding_population",
            "population IS NULL OR people_in_need <= population")
def silver_needs():
    hno = (
        spark.table(bronze("bronze_hno"))
        .where("`Country ISO3` IS NOT NULL AND `Country ISO3` NOT LIKE '#%'")
        .withColumn("iso3", norm_iso3(F.col("`Country ISO3`")))
        .withColumn("year", F.col("_source_year").cast("int"))
        .withColumn("_cat", F.lower(F.trim(F.col("Category"))))
        .withColumn("_pin", _to_bigint(F.col("`In Need`")))
        .withColumn("_targeted", _to_bigint(F.col("Targeted")))
        .withColumn("_population", _to_bigint(F.col("Population")))
    )

    # admin presence per country-year (for has_subnational); guarded for 2026
    # where the admin columns don't exist after the Bronze union (NULL).
    has_admin = F.col("`Admin 1 PCode`").isNotNull() | F.col("`Admin 2 PCode`").isNotNull()
    subnational = (
        hno.groupBy("iso3", "year")
        .agg(F.max(F.when(has_admin, F.lit(True)).otherwise(F.lit(False))).alias("has_subnational"))
    )

    # country-level total rows only
    country_total = hno.where(
        "`Admin 1 PCode` IS NULL AND `Admin 2 PCode` IS NULL AND _cat = 'total'"
    )

    # per (iso3, year, cluster) — max collapses any residual duplicate rows
    by_cluster = (
        country_total.groupBy("iso3", "year", F.col("Cluster").alias("cluster"))
        .agg(
            F.max("_pin").alias("people_in_need"),
            F.max("_targeted").alias("targeted"),
            F.max("_population").alias("population"),
            F.max("Description").alias("cluster_name"),
        )
    )

    # country caseload from the ALL row
    pin_total = (
        by_cluster.where("cluster = 'ALL'")
        .select("iso3", "year", F.col("people_in_need").alias("pin_total_country"))
    )

    return (
        by_cluster
        .join(pin_total, ["iso3", "year"], "left")
        .join(subnational, ["iso3", "year"], "left")
    )
