# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze loader: `bronze_fts_flows`
# MAGIC
# MAGIC Flow-level funding records — the richest FTS table (37 columns).
# MAGIC **Three source files share one schema**, distinguished by the in-file
# MAGIC `boundary` column:
# MAGIC - `fts_incoming_funding_global.csv` (`boundary=incoming`)
# MAGIC - `fts_outgoing_funding_global.csv` (`boundary=outgoing`)
# MAGIC - `fts_internal_funding_global.csv` (`boundary=internal`)
# MAGIC
# MAGIC All three loaded together; `_source_file` (per-row) and the `boundary`
# MAGIC column both discriminate them.
# MAGIC
# MAGIC **Quirks (docs/schemas.md, data_profiling.md):**
# MAGIC - `destLocations` is a **comma-delimited** ISO3 list (multi-country
# MAGIC   flows; drives the Silver allocation cascade). Kept verbatim here.
# MAGIC - `onBoundary='shared'` flows risk double-counting across boundaries —
# MAGIC   Silver dedupes; Bronze keeps everything.
# MAGIC - `description` is free text and may contain embedded newlines →
# MAGIC   `multiLine=true` on read.

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

dbutils.widgets.text("source_path", f"{VOLUME_BASE}/fts", "FTS flows source directory")
dbutils.widgets.dropdown("dry_run", "false", ["false", "true"], "Dry run (read + count, no write)")

source_path = dbutils.widgets.get("source_path").rstrip("/")
dry_run = get_dry_run()
TABLE = f"{CATALOG}.{BRONZE_SCHEMA}.bronze_fts_flows"

ensure_target_schema()

# COMMAND ----------

flow_files = [
    f"{source_path}/fts_incoming_funding_global.csv",
    f"{source_path}/fts_outgoing_funding_global.csv",
    f"{source_path}/fts_internal_funding_global.csv",
]
print(f"FTS flow files: {[f.rsplit('/', 1)[-1] for f in flow_files]}")

# One read across all three: schemas are identical so a multi-path read keeps
# `input_file_name()` per row. mergeSchema not needed (same shape).
df = (
    spark.read
    .option("header", "true")
    .option("inferSchema", "true")
    .option("multiLine", "true")
    .csv(flow_files)
)
df = add_audit_columns(df, source_file=None)  # per-row input_file_name()
rows_read = df.count()

# COMMAND ----------

written = write_bronze_delta(df, TABLE, dry_run, merge_schema=False)
load_summary(df, rows_read, written, dry_run)
