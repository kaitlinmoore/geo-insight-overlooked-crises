# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze loader: `bronze_reliefweb_situation_reports` (+ metadata + attention)
# MAGIC
# MAGIC ReliefWeb documents for the media-attention proxy + optional Day-4
# MAGIC Knowledge Assistant. Acquired via the ReliefWeb v2 API
# MAGIC (`acquire_reliefweb.py`); three staged outputs (see
# MAGIC `acquisition_reliefweb.md`).
# MAGIC
# MAGIC **Divergence note (see report):** `docs/schemas.md` names a single
# MAGIC planned `bronze_reliefweb_situation_reports` (doc-level). The actual
# MAGIC acquisition produced **three** distinct outputs, and the acquisition note
# MAGIC recommends three tables. This one notebook loads all three (so the
# MAGIC load-bearing v1 `media_attention` signal is not stranded), writing:
# MAGIC
# MAGIC | staged file | -> table |
# MAGIC |---|---|
# MAGIC | `reliefweb_docs/{iso3}/*.json` (500 docs) | `bronze_reliefweb_situation_reports` |
# MAGIC | `reliefweb_metadata.csv` (47,339 rows) | `bronze_reliefweb_metadata` |
# MAGIC | `reliefweb_media_attention.csv` (900 cells) | `bronze_reliefweb_attention` |
# MAGIC
# MAGIC **Quirks (acquisition_reliefweb.md):**
# MAGIC - `media_attention` is a dense 25x36 (country x month) grid — per-country
# MAGIC   by design; **do not sum `report_count` to a global total** (21.3% of
# MAGIC   reports are multi-country tagged). Kept verbatim in Bronze.
# MAGIC - 45 docs are <100 words (attachment-only stubs), 1 fully empty — kept in
# MAGIC   Bronze; Silver drops `body_word_count<100` before KA embedding.
# MAGIC - JSON docs carry an `all_countries` array; Spark infers it as array.

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

dbutils.widgets.text("source_path", f"{VOLUME_BASE}/reliefweb", "ReliefWeb staging directory")
dbutils.widgets.dropdown("dry_run", "false", ["false", "true"], "Dry run (read + count, no write)")

source_path = dbutils.widgets.get("source_path").rstrip("/")
dry_run = get_dry_run()

DOCS_TABLE = f"{CATALOG}.{BRONZE_SCHEMA}.bronze_reliefweb_situation_reports"
META_TABLE = f"{CATALOG}.{BRONZE_SCHEMA}.bronze_reliefweb_metadata"
ATTN_TABLE = f"{CATALOG}.{BRONZE_SCHEMA}.bronze_reliefweb_attention"

ensure_target_schema()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Situation-report documents (JSON corpus)

# COMMAND ----------

docs_path = f"{source_path}/reliefweb_docs"
docs_df = (
    spark.read
    .option("multiLine", "true")
    .option("recursiveFileLookup", "true")
    .json(docs_path)
)
docs_df = add_audit_columns(docs_df, source_file=None)  # per-row input_file_name()
docs_read = docs_df.count()
docs_written = write_bronze_delta(docs_df, DOCS_TABLE, dry_run, merge_schema=True)
load_summary(docs_df, docs_read, docs_written, dry_run)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Metadata index (per-report rows)

# COMMAND ----------

meta_path = f"{source_path}/reliefweb_metadata.csv"
meta_df = (
    spark.read
    .option("header", "true")
    .option("inferSchema", "true")
    .option("multiLine", "true")
    .csv(meta_path)
)
meta_df = add_audit_columns(meta_df, source_file=meta_path)
meta_read = meta_df.count()
meta_written = write_bronze_delta(meta_df, META_TABLE, dry_run, merge_schema=False)
load_summary(meta_df, meta_read, meta_written, dry_run)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Media-attention signal (country x month grid)

# COMMAND ----------

attn_path = f"{source_path}/reliefweb_media_attention.csv"
attn_df = (
    spark.read
    .option("header", "true")
    .option("inferSchema", "true")
    .csv(attn_path)
)
attn_df = add_audit_columns(attn_df, source_file=attn_path)
attn_read = attn_df.count()
attn_written = write_bronze_delta(attn_df, ATTN_TABLE, dry_run, merge_schema=False)
load_summary(attn_df, attn_read, attn_written, dry_run)
