# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: `gold_sector_coverage` — country × year × sector
# MAGIC
# MAGIC Per-sector funding gap, decomposable from the country-level ranking.
# MAGIC Substrate for `sector_gaps` and the `sector_imbalance` component of the
# MAGIC composite.
# MAGIC
# MAGIC **Sources (extended post-2026-05-22 CBPF integration):**
# MAGIC `bronze_fts_globalcluster` (FTS sector requirement + funding) +
# MAGIC `silver_cbpf_projects` (CBPF sector funding) + `silver_needs` (sector PIN)
# MAGIC + `silver_sector_crosswalk` (harmonization). All three funding/need sources
# MAGIC are mapped onto the harmonized IASC sector via the crosswalk, then summed
# MAGIC per `harmonized_sector_id`.
# MAGIC
# MAGIC **CBPF leg (the OCHA-vs-donors story):** `funding_usd = fts_funding_usd +
# MAGIC cbpf_funding_usd`, and `cbpf_funding_share = cbpf / (cbpf + fts)` gives the
# MAGIC Methodology slide a direct column for the pooled-fund-vs-bilateral
# MAGIC comparison per sector.
# MAGIC
# MAGIC `NOT_A_SECTOR_*` crosswalk rows (country-total, unattributed, multi-cluster
# MAGIC meta-rows) are excluded. CBPF `COVID-19` is reassigned to `Health` here
# MAGIC (the crosswalk's "reassign post-2023" rule lands at Gold, not in the
# MAGIC Silver CBPF aggregation).

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

from pyspark.sql import functions as F

# COMMAND ----------

# MAGIC %md
# MAGIC ## Crosswalk lookups

# COMMAND ----------

xwalk = (
    spark.table(silver("silver_sector_crosswalk"))
    .where("harmonized_sector NOT LIKE 'NOT_A_SECTOR%'")
)

xwalk_fts = (
    xwalk.where("fts_globalcluster_name IS NOT NULL")
    .select("fts_globalcluster_name", "harmonized_sector_id", "harmonized_sector")
    .dropDuplicates(["fts_globalcluster_name"])
)
xwalk_hno = (
    xwalk.where("hno_cluster_code IS NOT NULL")
    .select("hno_cluster_code", "harmonized_sector_id", "harmonized_sector")
    .dropDuplicates(["hno_cluster_code"])
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## FTS sector requirement + funding (harmonized)

# COMMAND ----------

fts = (
    spark.table(bronze("bronze_fts_globalcluster"))
    .withColumn("iso3", F.upper(F.trim(F.col("countryCode"))))
    .withColumn("year", F.col("year").cast("int"))
    .withColumn("cluster_name", F.trim(F.col("cluster")))
    .where("length(iso3) = 3 AND year IS NOT NULL")
)
fts_h = (
    fts.join(xwalk_fts, fts["cluster_name"] == xwalk_fts["fts_globalcluster_name"], "left")
    .groupBy("iso3", "year", "harmonized_sector_id", "harmonized_sector")
    .agg(
        F.sum(F.col("requirements").cast("double")).alias("requirement_usd"),
        F.sum(F.col("funding").cast("double")).alias("fts_funding_usd"),
    )
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## CBPF sector funding (already harmonized in Silver)

# COMMAND ----------

cbpf = (
    spark.table(silver("silver_cbpf_projects"))
    .where("harmonized_sector_id IS NOT NULL")
    # COVID-19 → Health reassignment (post-2023 rule, applied at Gold).
    .withColumn(
        "harmonized_sector_id",
        F.when(F.col("harmonized_sector_id") == "COV", F.lit("HEA")).otherwise(F.col("harmonized_sector_id")),
    )
    .withColumn(
        "harmonized_sector",
        F.when(F.col("harmonized_sector_id") == "HEA", F.lit("Health")).otherwise(F.col("harmonized_sector")),
    )
    .groupBy("iso3", "year", "harmonized_sector_id")
    .agg(F.sum("cbpf_funding_usd").alias("cbpf_funding_usd"))
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## HNO sector PIN (harmonized) + country total

# COMMAND ----------

needs = spark.table(silver("silver_needs"))
sector_pin = (
    needs.where("cluster <> 'ALL'")
    .join(xwalk_hno, needs["cluster"] == xwalk_hno["hno_cluster_code"], "left")
    .groupBy("iso3", "year", "harmonized_sector_id")
    .agg(F.sum("people_in_need").alias("sector_pin"))
)
country_pin = (
    needs.where("cluster = 'ALL'")
    .select("iso3", "year", F.col("pin_total_country"))
    .dropDuplicates(["iso3", "year"])
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Assemble

# COMMAND ----------

coverage = (
    fts_h
    .join(cbpf, ["iso3", "year", "harmonized_sector_id"], "outer")
    .join(sector_pin, ["iso3", "year", "harmonized_sector_id"], "left")
    .join(country_pin, ["iso3", "year"], "left")
    .fillna(0.0, subset=["requirement_usd", "fts_funding_usd", "cbpf_funding_usd"])
)

coverage = (
    coverage
    .withColumn("funding_usd", F.col("fts_funding_usd") + F.col("cbpf_funding_usd"))
    .withColumn(
        "sector_gap",
        F.when(F.col("requirement_usd") > 0,
               (F.col("requirement_usd") - F.col("funding_usd")) / F.col("requirement_usd")),
    )
    .withColumn(
        "cbpf_funding_share",
        F.when((F.col("cbpf_funding_usd") + F.col("fts_funding_usd")) > 0,
               F.col("cbpf_funding_usd") / (F.col("cbpf_funding_usd") + F.col("fts_funding_usd"))),
    )
    .withColumn(
        "pin_share",
        F.when((F.col("pin_total_country").isNotNull()) & (F.col("pin_total_country") > 0),
               F.col("sector_pin") / F.col("pin_total_country")),
    )
    .withColumn(
        "is_flagged_gap",
        (F.col("sector_gap") > 0.7) & (F.coalesce(F.col("pin_share"), F.lit(0.0)) >= 0.10),
    )
    .withColumnRenamed("harmonized_sector", "sector")
    .where("iso3 IS NOT NULL AND year IS NOT NULL AND harmonized_sector_id IS NOT NULL")
    .select(
        "iso3", "year", "sector", "harmonized_sector_id",
        "requirement_usd", "funding_usd", "fts_funding_usd", "cbpf_funding_usd",
        "cbpf_funding_share", "sector_gap", "sector_pin", "pin_share", "is_flagged_gap",
    )
)

assert_expectations(
    coverage,
    [
        ("warn:sector_gap_in_range", "sector_gap IS NULL OR sector_gap <= 1"),
        ("warn:cbpf_share_unit_interval", "cbpf_funding_share IS NULL OR cbpf_funding_share BETWEEN 0 AND 1"),
        ("fail:harmonized_resolved", "harmonized_sector_id IS NOT NULL"),
    ],
    "gold_sector_coverage",
)
(coverage.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .partitionBy("year")
    .saveAsTable(gold("gold_sector_coverage")))
