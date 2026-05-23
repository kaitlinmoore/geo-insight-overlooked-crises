# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: `silver_cbpf_projects`
# MAGIC
# MAGIC Country × year × harmonized-sector CBPF funding, the aggregation
# MAGIC `gold_sector_coverage` consumes for the CBPF sectoral leg (and the
# MAGIC optional CBPF Allocation View).
# MAGIC
# MAGIC **Transforms**
# MAGIC - Join `bronze_cbpf_projects.cluster` → `silver_sector_crosswalk.cbpf_category`
# MAGIC   (**case-sensitive** — the CBPF taxonomy uses specific casing like
# MAGIC   `Multi-purpose CASH` / `Multi-Sector`, added as crosswalk variants
# MAGIC   2026-05-22).
# MAGIC - Unresolved clusters are not silently dropped: they fall into a NULL
# MAGIC   `harmonized_sector_id` bucket surfaced by the `crosswalk_resolved` warn
# MAGIC   expectation (quarantine semantics), so a new CBPF cluster name shows up
# MAGIC   as a violation rather than vanishing.
# MAGIC - Aggregate to (iso3, year, harmonized_sector): sum `amount_usd`, distinct
# MAGIC   project / fund counts.
# MAGIC
# MAGIC **v2 notes**
# MAGIC - `sub_cluster` (6.2% populated in the source) is dropped in v1; the
# MAGIC   `sub_cluster_dropped_v1` warn expectation surfaces the count of
# MAGIC   sector-groups that contained dropped sub-cluster detail. v2: profile
# MAGIC   `sub_cluster` against the crosswalk's Protection sub-cluster rows
# MAGIC   (`PRO-CPN`, `PRO-GBV`, `PRO-MIN`, `PRO-HLP`, `PRO-HTS`).
# MAGIC - CBPF `COVID-19` (48 rows) maps to harmonized `COVID-19` here; the
# MAGIC   crosswalk's "reassign to Health post-2023" rule is a Gold/methodology
# MAGIC   concern, not applied in this Silver aggregation.

# COMMAND ----------

from _common import *  # noqa: F403,F401

# COMMAND ----------

import dlt


@dlt.table(
    name="silver_cbpf_projects",
    comment="Country×year×harmonized_sector CBPF funding from bronze_cbpf_projects, "
            "crosswalked on cluster→cbpf_category (case-sensitive). Unresolved "
            "clusters quarantined via crosswalk_resolved warn.",
)
@dlt.expect_or_drop("valid_iso3", VALID_ISO3)
@dlt.expect_or_drop("non_negative_funding", "cbpf_funding_usd >= 0")
@dlt.expect("crosswalk_resolved", "harmonized_sector_id IS NOT NULL")
@dlt.expect("sub_cluster_dropped_v1", "_had_sub_cluster = false")
def silver_cbpf_projects():
    proj = (
        spark.table(bronze("bronze_cbpf_projects"))
        .withColumn("iso3", norm_iso3(F.col("iso3")))
        .withColumn("year", F.col("year").cast("int"))
        .withColumn("amount_usd", F.col("amount_usd").cast("double"))
        .withColumn(
            "_has_sub",
            F.col("sub_cluster").isNotNull() & (F.length(F.trim(F.col("sub_cluster"))) > 0),
        )
    )

    xwalk = (
        dlt.read("silver_sector_crosswalk")
        .where("cbpf_category IS NOT NULL")
        .select("cbpf_category", "harmonized_sector", "harmonized_sector_id")
        .dropDuplicates(["cbpf_category"])
    )

    # case-sensitive join (CBPF casing is exact in the crosswalk variants)
    joined = proj.join(xwalk, proj["cluster"] == xwalk["cbpf_category"], "left")

    return (
        joined.groupBy("iso3", "year", "harmonized_sector_id", "harmonized_sector")
        .agg(
            F.sum("amount_usd").alias("cbpf_funding_usd"),
            F.countDistinct("project_code").alias("project_count"),
            F.countDistinct("fund_id").alias("fund_count"),
            F.max("_has_sub").alias("_had_sub_cluster"),
        )
    )
