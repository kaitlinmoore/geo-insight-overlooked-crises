# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze loader: `bronze_country_borders`
# MAGIC
# MAGIC Country-level land-border adjacency from **GeoNames** `countryInfo.txt` —
# MAGIC the portable replacement for the deferred Sedona polygon-adjacency path
# MAGIC (serverless Databricks compute can't install the Sedona JVM library; see
# MAGIC `DECISIONS.md` serverless entry). Single CSV: `country_borders.csv`, 252
# MAGIC rows, one per country, with a comma-separated alpha-3 `neighbor_iso3_list`.
# MAGIC
# MAGIC **Provenance & schema** — see `docs/notes/acquisition_geonames_borders.md`.
# MAGIC Source is GeoNames `countryInfo.txt`
# MAGIC (`download.geonames.org/export/dump/countryInfo.txt`), **CC-BY**
# MAGIC (attribution required), ~quarterly refresh, no auth. The 4-column schema is
# MAGIC fixed by `src/acquisition/acquire_geonames_borders.py`.
# MAGIC
# MAGIC **Quirks (acquisition note):**
# MAGIC - The CSV's first physical line is a `#`-comment provenance banner (source
# MAGIC   URL + acquisition date + license) → `comment="#"` on read so the real
# MAGIC   header is the next line.
# MAGIC - `neighbor_iso3_list` is **empty** for islands / dependent territories
# MAGIC   with no listed land border (`NZL`, `JPN`, `MDG`, `GRL`, `FRO`, …).
# MAGIC - A few non-standard codes ride along (`ANT` deprecated, `XKX` Kosovo) and
# MAGIC   simply don't match `gold_forgotten_crisis_index` on join — harmless.
# MAGIC   `CUB` carries one neighbour (`USA`, via the Guantánamo land boundary).

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

dbutils.widgets.text("source_path", f"{VOLUME_BASE}/country_borders.csv", "GeoNames borders CSV path")
dbutils.widgets.dropdown("dry_run", "false", ["false", "true"], "Dry run (read + count, no write)")

source_path = dbutils.widgets.get("source_path")
dry_run = get_dry_run()
TABLE = f"{CATALOG}.{BRONZE_SCHEMA}.bronze_country_borders"

ensure_target_schema()

# COMMAND ----------

# Explicit schema (the source is small + stable; no inferSchema). `comment="#"`
# skips the provenance banner line written by the acquisition script.
SCHEMA = "iso3 string, country_name string, neighbor_iso3_list string, n_neighbors int"

print(f"GeoNames borders file: {source_path.rsplit('/', 1)[-1]}")

df = (
    spark.read
    .option("header", "true")
    .option("encoding", "UTF-8")
    .option("comment", "#")
    .schema(SCHEMA)
    .csv(source_path)
)
df = add_audit_columns(df, source_file=source_path)
rows_read = df.count()

# COMMAND ----------

written = write_bronze_delta(df, TABLE, dry_run, merge_schema=False)
load_summary(df, rows_read, written, dry_run)
