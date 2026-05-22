# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze loader: `bronze_nrc_neglected`
# MAGIC
# MAGIC NRC "World's Most Neglected Displacement Crises" — Layer-2 validation
# MAGIC comparator (this one **is** ranked: `rank` 1 = most neglected).
# MAGIC Source: `nrc_most_neglected_lists.csv` (90 rows, 9 years, top-10 each;
# MAGIC see `docs/notes/acquisition_NRC.md`).
# MAGIC
# MAGIC **Quirks (docs/schemas.md `bronze_nrc_neglected`, acquisition note):**
# MAGIC - `rank` is the signal — NRC publishes a single ordered top-10, no
# MAGIC   severity tier/category.
# MAGIC - `year` is the **data year** (published the following June); 2015 and
# MAGIC   2025 are absent (series boundaries, not extraction failures).
# MAGIC - `inferSchema=true`; clean single-schema file, no HXL row.

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

dbutils.widgets.text("source_path", f"{VOLUME_BASE}/nrc/nrc_most_neglected_lists.csv", "NRC Most Neglected lists CSV path")
dbutils.widgets.dropdown("dry_run", "false", ["false", "true"], "Dry run (read + count, no write)")

source_path = dbutils.widgets.get("source_path")
dry_run = get_dry_run()
TABLE = f"{CATALOG}.{BRONZE_SCHEMA}.bronze_nrc_neglected"

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
