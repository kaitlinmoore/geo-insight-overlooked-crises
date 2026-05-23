# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: `silver_sector_crosswalk`
# MAGIC
# MAGIC The hand-built sector harmonization table (25 rows) materialized as a
# MAGIC Silver reference table. Loaded verbatim from `data/silver_sector_crosswalk.csv`.
# MAGIC
# MAGIC **Join semantics** (used downstream, primarily by `gold_sector_coverage`):
# MAGIC - HNO sources join on `hno_cluster_code` (e.g. `EDU`, `FSC`, `PRO-GBV`).
# MAGIC - FTS sources join on `fts_globalcluster_name` (the 24-name IASC taxonomy
# MAGIC   from `bronze_fts_globalcluster`).
# MAGIC - Rows whose `harmonized_sector` begins `NOT_A_SECTOR_` are meta-rows
# MAGIC   (`ALL` country total, `Not specified`, `Multiple clusters/sectors`) —
# MAGIC   carried here so consumers can *filter them out* of sector coverage
# MAGIC   explicitly rather than guessing. `is_real_sector` flags them.
# MAGIC
# MAGIC The CBPF column is intentionally empty (project-level CBPF sector data is
# MAGIC out of v1 scope — see `docs/data_catalog.md`).
# MAGIC
# MAGIC **Source path note**: the CSV ships in the repo at `data/`; for the
# MAGIC pipeline it is uploaded to the volume alongside the other reference CSVs.

# COMMAND ----------

from _common import *  # noqa: F403,F401

# COMMAND ----------

import dlt


@dlt.table(
    name="silver_sector_crosswalk",
    comment="Hand-built HNO-cluster ↔ FTS-globalcluster harmonization (25 rows). "
            "is_real_sector=false marks the FTS/HNO meta-rows to exclude from sector coverage.",
)
@dlt.expect_or_fail("non_empty", "harmonized_sector_id IS NOT NULL OR harmonized_sector IS NOT NULL")
@dlt.expect("has_join_key", "hno_cluster_code IS NOT NULL OR fts_globalcluster_name IS NOT NULL")
def silver_sector_crosswalk():
    df = (
        spark.read.option("header", "true").option("multiLine", "true")
        .csv(staging("silver_sector_crosswalk.csv"))
    )
    return df.select(
        F.col("harmonized_sector"),
        F.col("harmonized_sector_id"),
        F.col("hno_cluster_code"),
        F.col("hno_cluster_name"),
        F.col("fts_globalcluster_name"),
        F.col("fts_cluster_variants"),
        F.col("cbpf_category"),
        F.col("notes"),
        (~F.col("harmonized_sector").startswith("NOT_A_SECTOR_")).alias("is_real_sector"),
    )
