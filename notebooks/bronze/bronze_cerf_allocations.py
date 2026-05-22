# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze loader: `bronze_cerf_allocations`
# MAGIC
# MAGIC CERF allocations (Rapid Response + Underfunded Emergencies windows).
# MAGIC Source: `cerf_allocations_raw.csv` (HDX `cerf-allocations`, full
# MAGIC 2006-2026, 8,511 rows; see `acquisition_cerf_ufe.md`).
# MAGIC
# MAGIC **Naming note (see report):** the task originally named this loader
# MAGIC `bronze_cerf_ufe`; the file is now `bronze_cerf_allocations` to match the
# MAGIC Delta table it writes (`docs/schemas.md`, authoritative). We load the
# MAGIC **full RR+UFE file verbatim** — the Bronze layer keeps both windows; the
# MAGIC UFE filter (`windowFullName='Underfunded Emergencies'`) happens in Silver
# MAGIC (`silver_ufe_label`).
# MAGIC
# MAGIC **Quirks (acquisition_cerf_ufe.md):**
# MAGIC - `windowFullName` is the UFE/RR discriminator. `countryCode` is ISO3;
# MAGIC   country names are long-form (join on `countryCode`, never name).
# MAGIC - No `round` column (derived in Silver from `dateUSGSignature`, with a
# MAGIC   documented 2-6 month announcement lag — year-grain reliable).
# MAGIC - `tableName` (P/M) meaning unresolved — carried, unused.
# MAGIC - 2026 has rows but zero UFE allocations yet (timing, not a bug).

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

dbutils.widgets.text("source_path", f"{VOLUME_BASE}/cerf/cerf_allocations_raw.csv", "CERF allocations CSV path")
dbutils.widgets.dropdown("dry_run", "false", ["false", "true"], "Dry run (read + count, no write)")

source_path = dbutils.widgets.get("source_path")
dry_run = get_dry_run()
TABLE = f"{CATALOG}.{BRONZE_SCHEMA}.bronze_cerf_allocations"

ensure_target_schema()

# COMMAND ----------

df = (
    spark.read
    .option("header", "true")
    .option("inferSchema", "true")
    .option("multiLine", "true")
    .csv(source_path)
)
df = add_audit_columns(df, source_file=source_path)
rows_read = df.count()

# COMMAND ----------

written = write_bronze_delta(df, TABLE, dry_run, merge_schema=False)
load_summary(df, rows_read, written, dry_run)
