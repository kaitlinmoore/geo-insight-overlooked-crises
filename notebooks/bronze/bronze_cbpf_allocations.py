# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze loader: `bronze_cbpf_allocations`
# MAGIC
# MAGIC CBPF outflows (allocations to projects), pre-aggregated by fund.
# MAGIC **Nine files = nine years (2018-2026)**, one per year, loaded together.
# MAGIC Source: `Allocations__*.csv`.
# MAGIC
# MAGIC **Quirks (docs/schemas.md, data_profiling.md):**
# MAGIC - The filenames are **UTC timestamps** (`Allocations__20260518_145724_UTC.csv`)
# MAGIC   and do **not** encode the crisis year — the year lives in the in-file
# MAGIC   `Year` column. So `_source_file` is retained for audit but is NOT the
# MAGIC   year key here (contrast the task brief, which assumed the filename
# MAGIC   carries the year — corrected per the actual files).
# MAGIC - `PooledFund` is mostly a country but some are regional
# MAGIC   (`Fiji (AP-Rhpf)`); fund->ISO3 mapping is a Silver concern.
# MAGIC - ~23 exact duplicate rows exist after concat (data_profiling.md);
# MAGIC   Bronze keeps them verbatim — Silver dedupes.

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

dbutils.widgets.text("source_path", f"{VOLUME_BASE}/cbpf", "CBPF source directory")
dbutils.widgets.dropdown("dry_run", "false", ["false", "true"], "Dry run (read + count, no write)")

source_path = dbutils.widgets.get("source_path").rstrip("/")
dry_run = get_dry_run()
TABLE = f"{CATALOG}.{BRONZE_SCHEMA}.bronze_cbpf_allocations"

ensure_target_schema()

# COMMAND ----------

files = list_files(source_path, suffixes=(".csv",))
files = [f for f in files if f.rsplit("/", 1)[-1].lower().startswith("allocations")]
print(f"CBPF allocation files ({len(files)}): {[f.rsplit('/', 1)[-1] for f in files]}")

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
