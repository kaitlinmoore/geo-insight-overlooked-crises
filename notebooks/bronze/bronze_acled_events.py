# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze loader: `bronze_acled_events`
# MAGIC
# MAGIC Point-level conflict events (ACLED OAuth API). Source:
# MAGIC `acled_events_2020_present.parquet` (736,648 rows, 25 priority countries,
# MAGIC 2020-01-01 -> 2025-05-22). See `acquisition_acled.md`.
# MAGIC
# MAGIC **Quirks baked into the data:**
# MAGIC - **12-month recency embargo** — no events newer than ~12 months
# MAGIC   (account tier). Hotspot logic must treat `max(event_date)` as "now".
# MAGIC - `iso` is **ISO numeric** (729=SDN); `priority_iso3` (alpha-3) was added
# MAGIC   at acquisition for joining — use it.
# MAGIC - `assoc_actor_*` are semicolon-delimited multi-value; `geo_precision>=2`
# MAGIC   are centroids (down-weight in Silver hotspots). lat/lon already float64,
# MAGIC   zero nulls.
# MAGIC
# MAGIC Parquet is already typed — read as-is, append audit columns, append.

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

dbutils.widgets.text("source_path", f"{VOLUME_BASE}/acled/acled_events_2020_present.parquet", "ACLED events parquet path")
dbutils.widgets.dropdown("dry_run", "false", ["false", "true"], "Dry run (read + count, no write)")

source_path = dbutils.widgets.get("source_path")
dry_run = get_dry_run()
TABLE = f"{CATALOG}.{BRONZE_SCHEMA}.bronze_acled_events"

ensure_target_schema()

# COMMAND ----------

df = spark.read.parquet(source_path)
df = add_audit_columns(df, source_file=source_path)
rows_read = df.count()

# COMMAND ----------

written = write_bronze_delta(df, TABLE, dry_run, merge_schema=False)
load_summary(df, rows_read, written, dry_run)
