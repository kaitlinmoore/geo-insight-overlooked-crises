# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze loader: `bronze_echo_fca`
# MAGIC
# MAGIC DG ECHO Forgotten Crises Assessment annual lists — Layer-2 validation
# MAGIC comparator (top-N overlap analysis alongside NRC Most Neglected).
# MAGIC Source: `echo_fca_lists.csv` (197 rows, 10 years 2015–2026; see
# MAGIC `docs/notes/acquisition_echo_fca.md`).
# MAGIC
# MAGIC **Quirks (docs/schemas.md `bronze_echo_fca`, acquisition note):**
# MAGIC - `forgotten_category` is always `forgotten` — ECHO publishes one
# MAGIC   undifferentiated list, no fully/partially split.
# MAGIC - `iso3` is ~0.5% null (multi-country regional entries with no member
# MAGIC   breakdown). Kept verbatim; not dropped here.
# MAGIC - Biennial-labelled assessments are emitted under both operative years
# MAGIC   (2016==2017, 2019==2020, 2022==2023); 2018 and 2025 are absent.
# MAGIC - `inferSchema=true`; clean single-schema file, no HXL row.

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

dbutils.widgets.text("source_path", f"{VOLUME_BASE}/echo/echo_fca_lists.csv", "ECHO FCA lists CSV path")
dbutils.widgets.dropdown("dry_run", "false", ["false", "true"], "Dry run (read + count, no write)")

source_path = dbutils.widgets.get("source_path")
dry_run = get_dry_run()
TABLE = f"{CATALOG}.{BRONZE_SCHEMA}.bronze_echo_fca"

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
