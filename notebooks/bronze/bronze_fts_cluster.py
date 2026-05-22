# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze loader: `bronze_fts_cluster`
# MAGIC
# MAGIC Sector/cluster-level requirements vs funding — the **country-specific
# MAGIC cluster** taxonomy. Source: `fts_requirements_funding_cluster_global.csv`.
# MAGIC
# MAGIC **Divergence note (see report):** `docs/schemas.md` describes a single
# MAGIC `bronze_fts_cluster` holding *both* the country-cluster and the
# MAGIC harmonized global-cluster files, tagged by `_source_file`. This loader
# MAGIC keeps them **separate** (`bronze_fts_cluster` here, `bronze_fts_globalcluster`
# MAGIC in its own notebook) because the two files use different taxonomies
# MAGIC (962 raw cluster names vs 24 IASC clusters); separate tables avoid
# MAGIC mixing taxonomies and make the downstream `globalcluster`-preferred
# MAGIC selection trivial. Both are valid; this matches the task's explicit
# MAGIC two-notebook deliverable list.
# MAGIC
# MAGIC **Quirks:** `cluster` values `Not specified` / `Multiple clusters/sectors
# MAGIC (shared)` are the sector-level analog of multi-country flows — kept
# MAGIC verbatim with provenance for the sector-decomposition methodology.

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

dbutils.widgets.text("source_path", f"{VOLUME_BASE}/fts/fts_requirements_funding_cluster_global.csv", "FTS country-cluster CSV path")
dbutils.widgets.dropdown("dry_run", "false", ["false", "true"], "Dry run (read + count, no write)")

source_path = dbutils.widgets.get("source_path")
dry_run = get_dry_run()
TABLE = f"{CATALOG}.{BRONZE_SCHEMA}.bronze_fts_cluster"

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
