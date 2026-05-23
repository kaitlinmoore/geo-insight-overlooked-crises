# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: `silver_cbpf_allocations`
# MAGIC
# MAGIC CBPF allocations mapped to ISO3 via `silver_fund_country_map`. Substrate
# MAGIC for the optional CBPF Allocation View (not the main ranking).
# MAGIC
# MAGIC - `PooledFund` → `fund_iso3` (NULL only for the one pure-regional fund).
# MAGIC - `is_regional_fund` carried from the map.
# MAGIC - The 23 exact duplicate rows from the nine-file concat are removed.

# COMMAND ----------

from _common import *  # noqa: F403,F401

# COMMAND ----------

import dlt


@dlt.table(
    name="silver_cbpf_allocations",
    comment="CBPF allocations by year×fund×allocation_type, fund→ISO3 mapped. "
            "Exact duplicates from the 9-file concat removed.",
)
@dlt.expect_or_drop("non_negative_budget", "budget_usd >= 0")
@dlt.expect("allocation_type_valid", "allocation_type IN ('standard','reserve')")
@dlt.expect("fund_resolved", "fund_iso3 IS NOT NULL OR is_regional_fund = true")
def silver_cbpf_allocations():
    alloc = (
        spark.table(bronze("bronze_cbpf_allocations"))
        .select(
            F.col("Year").cast("int").alias("year"),
            F.col("PooledFund").alias("fund_name"),
            F.lower(F.trim(F.col("AllocationType"))).alias("allocation_type"),
            F.col("Budget").cast("bigint").alias("budget_usd"),
        )
        .dropDuplicates(["year", "fund_name", "allocation_type", "budget_usd"])
    )
    fmap = dlt.read("silver_fund_country_map")
    return (
        alloc.join(fmap, "fund_name", "left")
        .select("year", "fund_name", "fund_iso3", "is_regional_fund",
                "allocation_type", "budget_usd")
    )
