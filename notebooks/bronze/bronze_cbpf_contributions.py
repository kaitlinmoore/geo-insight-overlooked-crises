# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze loader: `bronze_cbpf_contributions`
# MAGIC
# MAGIC CBPF inflows (donor contributions into the pooled-fund system).
# MAGIC **Nine files = nine years (2018-2026)**, loaded together.
# MAGIC Source: `Contributions__*.csv`.
# MAGIC
# MAGIC **Quirks (docs/schemas.md, data_profiling.md):**
# MAGIC - **No fund/country column** — these are *global* CBPF contributions by
# MAGIC   donor per year, not attributable to a specific fund or crisis. NOT used
# MAGIC   for country-level `donor_concentration` (that comes from FTS flows).
# MAGIC - Year lives in the in-file `Year` column, not the (UTC-timestamp)
# MAGIC   filename.
# MAGIC - ~289 within-file duplicate donor-year rows (split contributions /
# MAGIC   pledge revisions) — kept verbatim; Silver dedupes.

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

dbutils.widgets.text("source_path", f"{VOLUME_BASE}/cbpf", "CBPF source directory")
dbutils.widgets.dropdown("dry_run", "false", ["false", "true"], "Dry run (read + count, no write)")

source_path = dbutils.widgets.get("source_path").rstrip("/")
dry_run = get_dry_run()
TABLE = f"{CATALOG}.{BRONZE_SCHEMA}.bronze_cbpf_contributions"

ensure_target_schema()

# COMMAND ----------

files = list_files(source_path, suffixes=(".csv",))
files = [f for f in files if f.rsplit("/", 1)[-1].lower().startswith("contributions")]
print(f"CBPF contribution files ({len(files)}): {[f.rsplit('/', 1)[-1] for f in files]}")

df = (
    spark.read
    .option("header", "true")
    .option("encoding", "UTF-8")
    .option("inferSchema", "true")
    .csv(files)
)
df = add_audit_columns(df, source_file=None)  # per-row input_file_name()
rows_read = df.count()

# COMMAND ----------

written = write_bronze_delta(df, TABLE, dry_run, merge_schema=False)
load_summary(df, rows_read, written, dry_run)
