# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze loader: `bronze_fts_plan`
# MAGIC
# MAGIC Plan/appeal-level requirements vs funding by country.
# MAGIC Source: `fts_requirements_funding_global.csv`.
# MAGIC
# MAGIC **Quirks (docs/schemas.md `bronze_fts_plan`, data_profiling.md):**
# MAGIC - Two row grains share the file: *plan-level* rows (have `code`) and
# MAGIC   *country-aggregate* rows (`code`/`id` NULL, `name='Not specified'`,
# MAGIC   ~67% of rows). **Both kept verbatim** — Silver carries both grains
# MAGIC   (the `Not specified` rows preserve off-plan funding signal for
# MAGIC   no-HRP countries like ETH 2026).
# MAGIC - Future-dated rows (year 2027-2031) exist; Silver filters to
# MAGIC   `year <= current_year`. Bronze keeps them.
# MAGIC - `inferSchema=true` gives reasonable Delta types for this clean,
# MAGIC   single-schema file (no HXL row).

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

dbutils.widgets.text("source_path", f"{VOLUME_BASE}/fts/fts_requirements_funding_global.csv", "FTS plan-level CSV path")
dbutils.widgets.dropdown("dry_run", "false", ["false", "true"], "Dry run (read + count, no write)")

source_path = dbutils.widgets.get("source_path")
dry_run = get_dry_run()
TABLE = f"{CATALOG}.{BRONZE_SCHEMA}.bronze_fts_plan"

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
