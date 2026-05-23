# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: `silver_population`
# MAGIC
# MAGIC National (admin0) + admin1 total-population denominators, from
# MAGIC `bronze_cod_population`. The single total-population row per admin unit is
# MAGIC `Population_group='T_TL'` AND `Gender='all'` AND `Age_range='all'`.
# MAGIC
# MAGIC - National rows carry `admin1_pcode = NULL` (the cascade reads these for
# MAGIC   population-weighted multi-country allocation; `severity_rate` uses them).
# MAGIC - Admin1 rows carry their `ADM1_PCODE` (subnational weights / severity).
# MAGIC
# MAGIC **`stale_population_flag`** (task #7, distinct from `data_sparsity_flag`):
# MAGIC `Reference_year < current_year - 5`. Surfaced in Gold via
# MAGIC `inputs_freshness`. VEN (ref year 2011) is the canonical stale case.

# COMMAND ----------

from _common import *  # noqa: F403,F401

# COMMAND ----------

import dlt

_STALE_BEFORE = F.year(F.current_date()) - F.lit(5)


@dlt.table(
    name="silver_population",
    comment="COD-PS total population by country and admin1. "
            "admin1_pcode NULL = national row. stale_population_flag set when "
            "Reference_year < current_year - 5.",
)
@dlt.expect_or_drop("positive_population", "population_total > 0")
@dlt.expect_or_drop("valid_iso3", VALID_ISO3)
def silver_population():
    base = (
        spark.table(bronze("bronze_cod_population"))
        .where(
            "Population_group = 'T_TL' AND Gender = 'all' AND Age_range = 'all'"
        )
        .select(
            norm_iso3(F.col("ISO3")).alias("iso3"),
            F.when(F.col("_admin_level") == 1, F.col("ADM1_PCODE"))
            .otherwise(F.lit(None)).alias("admin1_pcode"),
            F.col("Population").cast("bigint").alias("population_total"),
            F.col("Reference_year").cast("int").alias("reference_year"),
            F.col("Source").alias("source"),
        )
        .withColumn("stale_population_flag", F.col("reference_year") < _STALE_BEFORE)
    )
    # One total row per unit (national = iso3; subnational = admin1_pcode).
    # Enforced here because DLT expectations are row-level, not group-unique.
    return base.dropDuplicates(["iso3", "admin1_pcode"])
