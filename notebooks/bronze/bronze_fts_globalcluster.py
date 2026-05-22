# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze loader: `bronze_fts_globalcluster`
# MAGIC
# MAGIC Sector/cluster-level requirements vs funding — the **harmonized global
# MAGIC cluster** (IASC) taxonomy. Source:
# MAGIC `fts_requirements_funding_globalcluster_global.csv`.
# MAGIC
# MAGIC **Divergence note (see report):** `docs/schemas.md` folds this file into
# MAGIC `bronze_fts_cluster` (one table, two source files tagged by
# MAGIC `_source_file`). We keep it as its own table because it carries the
# MAGIC normalized 24-name IASC taxonomy (vs the 962-name raw country-cluster
# MAGIC file) and is the preferred input for cross-country sector decomposition
# MAGIC (`gold_sector_coverage`). Same schema/columns as `bronze_fts_cluster`.

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

dbutils.widgets.text("source_path", f"{VOLUME_BASE}/fts/fts_requirements_funding_globalcluster_global.csv", "FTS global-cluster CSV path")
dbutils.widgets.dropdown("dry_run", "false", ["false", "true"], "Dry run (read + count, no write)")

source_path = dbutils.widgets.get("source_path")
dry_run = get_dry_run()
TABLE = f"{CATALOG}.{BRONZE_SCHEMA}.bronze_fts_globalcluster"

ensure_target_schema()

# COMMAND ----------

df = (
    spark.read
    .option("header", "true")
    .option("encoding", "UTF-8")
    .option("inferSchema", "true")
    .option("multiLine", "true")
    .csv(source_path)
)
df = add_audit_columns(df, source_file=source_path)
rows_read = df.count()

# COMMAND ----------

written = write_bronze_delta(df, TABLE, dry_run, merge_schema=False)
load_summary(df, rows_read, written, dry_run)
