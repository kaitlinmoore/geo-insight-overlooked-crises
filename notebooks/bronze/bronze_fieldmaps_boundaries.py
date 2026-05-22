# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze loader: `bronze_fieldmaps_boundaries`
# MAGIC
# MAGIC Edge-matched global subnational boundaries (fieldmaps.io).
# MAGIC Source: `fieldmaps_admin_boundaries.geoparquet` (GeoParquet 1.1.0,
# MAGIC 43,064 rows, ~2 GB; CRS OGC:CRS84 == EPSG:4326).
# MAGIC See `acquisition_fieldmaps.md`.
# MAGIC
# MAGIC **Strategy (docs/schemas.md, acquisition_fieldmaps.md):**
# MAGIC - GeoParquet is just Parquet with a geo metadata block, so we read it
# MAGIC   with the **plain Spark Parquet reader** (`spark.read.parquet`). No
# MAGIC   Sedona / geospatial library is needed at Bronze — the `geometry`
# MAGIC   column comes through as **WKB-encoded binary** and is stored verbatim.
# MAGIC   Silver (`silver_boundaries`) decodes WKB -> geometry via Sedona and
# MAGIC   does validity checks + H3 indexing.
# MAGIC - `geometry_bbox` (struct<xmin,ymin,xmax,ymax>) and all 45 columns are
# MAGIC   retained as-is. Join keys: `iso_3` (country) and `adm{0,1,2}_id`
# MAGIC   (P-code-equivalent).
# MAGIC
# MAGIC **Note**: avoid `inferSchema`/casting — Parquet is already typed.

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

dbutils.widgets.text("source_path", f"{VOLUME_BASE}/fieldmaps/fieldmaps_admin_boundaries.geoparquet", "Fieldmaps GeoParquet path")
dbutils.widgets.dropdown("dry_run", "false", ["false", "true"], "Dry run (read + count, no write)")

source_path = dbutils.widgets.get("source_path")
dry_run = get_dry_run()
TABLE = f"{CATALOG}.{BRONZE_SCHEMA}.bronze_fieldmaps_boundaries"

ensure_target_schema()

# COMMAND ----------

# GeoParquet -> read as Parquet; geometry stays as binary (WKB). The geo
# metadata block in the file footer is ignored by the plain reader, which is
# exactly what we want for an audit-grade verbatim Bronze copy.
df = spark.read.parquet(source_path)
df = add_audit_columns(df, source_file=source_path)
rows_read = df.count()

# COMMAND ----------

written = write_bronze_delta(df, TABLE, dry_run, merge_schema=False)
load_summary(df, rows_read, written, dry_run)
