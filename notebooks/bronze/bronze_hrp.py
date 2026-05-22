# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze loader: `bronze_hrp`
# MAGIC
# MAGIC Plan-level dimension + requirements totals (one row per response plan).
# MAGIC Source: `humanitarian-response-plans.csv`.
# MAGIC
# MAGIC **Quirks (docs/schemas.md `bronze_hrp`, data_profiling.md):**
# MAGIC - Row 0 is an **HXL hashtag row** (`#response+code`, etc.) — kept
# MAGIC   verbatim in Bronze, dropped in Silver.
# MAGIC - `locations` is a **pipe-delimited** ISO3 list (multi-country plans);
# MAGIC   different delimiter from FTS (commas). Split happens in Silver.
# MAGIC - Read with `inferSchema=false`: the HXL row forces every column to
# MAGIC   string anyway, so we keep all columns as string (verbatim; Silver
# MAGIC   casts `revisedRequirements` etc.).

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

dbutils.widgets.text("source_path", f"{VOLUME_BASE}/hrp/humanitarian-response-plans.csv", "HRP plans CSV path")
dbutils.widgets.dropdown("dry_run", "false", ["false", "true"], "Dry run (read + count, no write)")

source_path = dbutils.widgets.get("source_path")
dry_run = get_dry_run()
TABLE = f"{CATALOG}.{BRONZE_SCHEMA}.bronze_hrp"

ensure_target_schema()

# COMMAND ----------

df = (
    spark.read
    .option("header", "true")
    .option("encoding", "UTF-8")
    .option("inferSchema", "false")
    .option("multiLine", "true")
    .csv(source_path)
)
df = add_audit_columns(df, source_file=source_path)
rows_read = df.count()

# COMMAND ----------

written = write_bronze_delta(df, TABLE, dry_run, merge_schema=False)
load_summary(df, rows_read, written, dry_run)
