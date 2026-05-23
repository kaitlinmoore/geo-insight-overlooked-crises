# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze loader: `bronze_cod_population`
# MAGIC
# MAGIC UN Common Operational Dataset population, long format by demographic —
# MAGIC the **national (admin0) + admin1** levels (the denominators actually used
# MAGIC at the global / subnational ranking layers).
# MAGIC Sources: `cod_population_admin0.csv`, `cod_population_admin1.csv`.
# MAGIC
# MAGIC **Divergence note (see report):** `docs/schemas.md` describes a single
# MAGIC `bronze_cod_population` loading all five files (admin0-4). We split off
# MAGIC admin2 into `bronze_cod_population_admin2` (its own notebook, ~1M rows
# MAGIC from the more-complete `cod-ps-global` pull) per the task's explicit
# MAGIC two-table deliverable, and we exclude admin3 (ETH-only) and admin4
# MAGIC (one-country noise) from the named scope — they can be added later with
# MAGIC the same pattern. admin0+admin1 belong together (national + admin1
# MAGIC severity-rate denominators).
# MAGIC
# MAGIC **Quirks:** total-population row = `Population_group='T_TL'` AND
# MAGIC `Gender='all'` AND `Age_range='all'` (Silver filters to it). admin1 file
# MAGIC has extra `ADM1_*` columns -> `mergeSchema=true` unions the two levels;
# MAGIC `_admin_level` is derived for clarity.

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

dbutils.widgets.text("source_path", f"{VOLUME_BASE}/cod", "COD population source directory")
dbutils.widgets.dropdown("dry_run", "false", ["false", "true"], "Dry run (read + count, no write)")

source_path = dbutils.widgets.get("source_path").rstrip("/")
dry_run = get_dry_run()
TABLE = f"{CATALOG}.{BRONZE_SCHEMA}.bronze_cod_population"

ensure_target_schema()

# COMMAND ----------

level_files = {
    0: f"{source_path}/cod_population_admin0.csv",
    1: f"{source_path}/cod_population_admin1.csv",
}

parts = []
for level, path in level_files.items():
    raw = (
        spark.read
        .option("header", "true")
        .option("encoding", "UTF-8")
        .option("inferSchema", "true")
        .csv(path)
    )
    raw = raw.withColumn("_admin_level", F.lit(level))
    raw = add_audit_columns(raw, source_file=path)
    parts.append(raw)

df = parts[0]
for p in parts[1:]:
    df = df.unionByName(p, allowMissingColumns=True)

rows_read = df.count()

# COMMAND ----------

written = write_bronze_delta(df, TABLE, dry_run, merge_schema=True)
load_summary(df, rows_read, written, dry_run)

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT COUNT(*), MIN(_ingested_at), MAX(_ingested_at)
# MAGIC    FROM geo_insight.bronze.bronze_cod_population;
