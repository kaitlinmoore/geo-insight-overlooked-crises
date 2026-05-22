# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze loader: `bronze_cod_population_admin2`
# MAGIC
# MAGIC UN COD population at **admin2** — the subnational deep-dive denominator.
# MAGIC Source: `cod_population_admin2.csv` (the `cod-ps-global` pull,
# MAGIC ~1M rows, 19 columns; see `acquisition_supplemental_cod.md`).
# MAGIC
# MAGIC **Divergence note (see report):** kept as its own table per the task's
# MAGIC explicit deliverable list, rather than folded into `bronze_cod_population`
# MAGIC as `docs/schemas.md` describes. It is also a distinct, more-complete
# MAGIC source than the small CMU-drop admin2 file.
# MAGIC
# MAGIC **Quirks (acquisition_supplemental_cod.md):**
# MAGIC - Long-format, age/sex disaggregated; total = `Population_group='T_TL'`.
# MAGIC - Coverage is partial: **YEM, MMR, NGA have zero admin2 population** and
# MAGIC   degrade to admin1 + `data_sparsity_flag` in Silver.
# MAGIC - `Reference_year` varies and some are stale (VEN=2011); carried through
# MAGIC   for the data-freshness indicators.

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

dbutils.widgets.text("source_path", f"{VOLUME_BASE}/cod/cod_population_admin2.csv", "COD admin2 population CSV path")
dbutils.widgets.dropdown("dry_run", "false", ["false", "true"], "Dry run (read + count, no write)")

source_path = dbutils.widgets.get("source_path")
dry_run = get_dry_run()
TABLE = f"{CATALOG}.{BRONZE_SCHEMA}.bronze_cod_population_admin2"

ensure_target_schema()

# COMMAND ----------

df = (
    spark.read
    .option("header", "true")
    .option("encoding", "UTF-8")
    .option("inferSchema", "true")
    .csv(source_path)
)
df = df.withColumn("_admin_level", F.lit(2))
df = add_audit_columns(df, source_file=source_path)
rows_read = df.count()

# COMMAND ----------

written = write_bronze_delta(df, TABLE, dry_run, merge_schema=False)
load_summary(df, rows_read, written, dry_run)
