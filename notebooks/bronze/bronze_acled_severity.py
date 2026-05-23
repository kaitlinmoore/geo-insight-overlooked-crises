# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze loader: `bronze_acled_severity`
# MAGIC
# MAGIC Admin2 x month conflict aggregates (ACLED via HDX) — the
# MAGIC current-coverage counterpart to `bronze_acled_events`. Source:
# MAGIC `acled_severity_admin2_month_2020_present.parquet` (942,126 rows,
# MAGIC 25 countries, 2020-01 -> 2026-05, current). See `acquisition_acled.md`.
# MAGIC
# MAGIC **Quirks:**
# MAGIC - Source `iso3` is **NULL for GTM/HND/PHL**; `priority_iso3` is the
# MAGIC   reliable join key (Silver coalesces).
# MAGIC - Carries `admin1_pcode`/`admin2_pcode` — the value-add over the event
# MAGIC   path (join to boundaries).
# MAGIC - `event_category` ∈ {political_violence, civilian_targeting,
# MAGIC   demonstration}; **civilian_targeting overlaps political_violence — do
# MAGIC   not sum all three**. **COL has no demonstration rows** (source file
# MAGIC   corrupt at acquisition).
# MAGIC - Includes explicit **zero-event rows** (~64%); kept verbatim, filtered
# MAGIC   `events>0` in most Silver views.
# MAGIC
# MAGIC Parquet is already typed — read as-is, append audit columns, append.

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

dbutils.widgets.text("source_path", f"{VOLUME_BASE}/acled/acled_severity_admin2_month_2020_present.parquet", "ACLED severity parquet path")
dbutils.widgets.dropdown("dry_run", "false", ["false", "true"], "Dry run (read + count, no write)")

source_path = dbutils.widgets.get("source_path")
dry_run = get_dry_run()
TABLE = f"{CATALOG}.{BRONZE_SCHEMA}.bronze_acled_severity"

ensure_target_schema()

# COMMAND ----------

import pandas as pd

# Serverless's Spark parquet reader rejects INT64 TIMESTAMP(NANOS).
# Read via pandas (which handles nanos), truncate to micros, hand to Spark.
pdf = pd.read_parquet(source_path)

for col in pdf.columns:
    if pd.api.types.is_datetime64_ns_dtype(pdf[col]):
        pdf[col] = pdf[col].astype('datetime64[us]')

df = spark.createDataFrame(pdf)
df = add_audit_columns(df, source_file=source_path)
rows_read = df.count()

# COMMAND ----------

written = write_bronze_delta(df, TABLE, dry_run, merge_schema=False)
load_summary(df, rows_read, written, dry_run)
