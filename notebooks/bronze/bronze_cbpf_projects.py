# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze loader: `bronze_cbpf_projects`
# MAGIC
# MAGIC CBPF allocations at **project × cluster** grain — the sector-tagged CBPF
# MAGIC source that `bronze_cbpf_allocations` (fund/year/window aggregate, no
# MAGIC sector) lacks. Single CSV: `cbpf_projects.csv`, 24,219 rows, 2010–2026,
# MAGIC all 34 funds, 100% cluster-tagged.
# MAGIC
# MAGIC **Provenance & schema** — see `docs/notes/acquisition_cbpf_projects.md`.
# MAGIC Source is the OCHA CBPF Business Intelligence **OData API**
# MAGIC (`cbpfapi.unocha.org/vo1/odata/`, entity `Cluster` joined to `Poolfund`
# MAGIC and `ProjectSummary`), discovered via the HDX dataset
# MAGIC `cbpf-allocations-and-contributions`. CC BY (IGO), monthly refresh, no
# MAGIC auth. The 18-column schema is fixed by `src/acquisition/acquire_cbpf_projects.py`.
# MAGIC
# MAGIC **Quirks (acquisition note):**
# MAGIC - Grain is project × cluster — a project split across N clusters yields N
# MAGIC   rows; `amount_usd` is that cluster's slice. Bronze keeps all rows verbatim.
# MAGIC - `iso3` carries two source overrides applied at acquisition
# MAGIC   (`LI`→`MOZ`, `XX`→`SYR`); Bronze keeps the acquired value as-is.
# MAGIC - `project_title` may contain newlines from the OData output →
# MAGIC   `multiLine=true` on read.

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

dbutils.widgets.text("source_path", f"{VOLUME_BASE}/cbpf", "CBPF source directory")
dbutils.widgets.dropdown("dry_run", "false", ["false", "true"], "Dry run (read + count, no write)")

source_path = dbutils.widgets.get("source_path").rstrip("/")
dry_run = get_dry_run()
TABLE = f"{CATALOG}.{BRONZE_SCHEMA}.bronze_cbpf_projects"

ensure_target_schema()

# COMMAND ----------

source_file = f"{source_path}/cbpf_projects.csv"
print(f"CBPF projects file: {source_file.rsplit('/', 1)[-1]}")

df = (
    spark.read
    .option("header", "true")
    .option("encoding", "UTF-8")
    .option("inferSchema", "true")
    .option("multiLine", "true")
    .csv(source_file)
)
df = add_audit_columns(df, source_file=source_file)
rows_read = df.count()

# COMMAND ----------

written = write_bronze_delta(df, TABLE, dry_run, merge_schema=False)
load_summary(df, rows_read, written, dry_run)
