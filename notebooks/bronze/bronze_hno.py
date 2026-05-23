# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze loader: `bronze_hno`
# MAGIC
# MAGIC People-in-Need / needs figures from the HPC HNO exports — a **three-year
# MAGIC load** (2024, 2025, 2026) into one append-only table.
# MAGIC
# MAGIC **Schema drift (docs/schemas.md `bronze_hno`):**
# MAGIC - 2024 & 2025: 16 columns, a leading **HXL hashtag row**, admin1/2/3
# MAGIC   P-code+name columns (subnational present), all values read as strings.
# MAGIC - 2026: 10 columns, **no HXL row, no admin columns**, numeric values.
# MAGIC
# MAGIC **Loader-time decisions (documented per scope):**
# MAGIC - Read **all three with `inferSchema=false` (every column as string)**.
# MAGIC   The HXL row already forces 2024/2025 to string; reading 2026 as string
# MAGIC   too gives a uniform type across years so `mergeSchema=true` can union
# MAGIC   the 16-col and 10-col shapes without a string-vs-numeric merge conflict.
# MAGIC   This honours the Bronze rule (no type-casting; Silver casts).
# MAGIC - Keep **all rows verbatim**, including the HXL hashtag row (Silver drops
# MAGIC   it). Append `_source_year` derived from the filename.
# MAGIC - `mergeSchema=true` so 2026's missing admin columns land as NULL.

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

dbutils.widgets.text("source_path", f"{VOLUME_BASE}/hno", "HNO source directory (contains hpc_hno_YYYY.csv)")
dbutils.widgets.dropdown("dry_run", "false", ["false", "true"], "Dry run (read + count, no write)")

source_path = dbutils.widgets.get("source_path").rstrip("/")
dry_run = get_dry_run()
TABLE = f"{CATALOG}.{BRONZE_SCHEMA}.bronze_hno"

ensure_target_schema()

# COMMAND ----------

# Read each year explicitly so we can attach `_source_year` and `_source_file`
# per file, then union (mergeSchema absorbs the 2026 column difference).
files = list_files(source_path, suffixes=(".csv",))
print(f"HNO source files: {[f.rsplit('/', 1)[-1] for f in files]}")

parts = []
for path in files:
    raw = (
        spark.read
        .option("header", "true")
        .option("encoding", "UTF-8")
        .option("inferSchema", "false")   # all columns as string — see header notes
        .option("multiLine", "true")
        .csv(path)
    )
    year = parse_year_from_filename(path, [r"hpc_hno_(\d{4})", r"(\d{4})"])
    raw = raw.withColumn("_source_year", F.lit(year).cast("int"))
    raw = add_audit_columns(raw, source_file=path)
    parts.append(raw)

# unionByName with allowMissingColumns: 2026 lacks the six admin columns.
df = parts[0]
for p in parts[1:]:
    df = df.unionByName(p, allowMissingColumns=True)

rows_read = df.count()

# COMMAND ----------

written = write_bronze_delta(df, TABLE, dry_run, merge_schema=True, column_mapping=True)
load_summary(df, rows_read, written, dry_run)

# COMMAND ----------

# MAGIC %sql
# MAGIC DESCRIBE TABLE geo_insight.bronze.bronze_hno;

# COMMAND ----------


