# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze shared helpers (`_common`)
# MAGIC
# MAGIC Cross-cutting utilities every Bronze loader depends on. Imported via
# MAGIC `%run ./_common` so the functions and constants run in the caller's
# MAGIC notebook context (same `spark` / `dbutils`).
# MAGIC
# MAGIC **Contract (see `docs/schemas.md` "Lineage / audit columns"):**
# MAGIC - Every Bronze table carries `_ingested_at` (timestamp) and
# MAGIC   `_source_file` (string, originating file path).
# MAGIC - Bronze is **append-only** and **verbatim**: one row = one source-file
# MAGIC   row. No filtering, no HXL-row removal, no type-casting here — that is
# MAGIC   Silver's job.
# MAGIC - These loaders **never** `CREATE SCHEMA`/`CREATE VOLUME`. Provisioning
# MAGIC   is separate infra (permissions pending as of 2026-05-22).

# COMMAND ----------

from pyspark.sql import functions as F
import re

# Databricks namespace (docs/schemas.md "Conventions")
CATALOG = "geo_insight"
BRONZE_SCHEMA = "bronze"
VOLUME_BASE = "/Volumes/geo_insight/raw/staging"


# COMMAND ----------

def add_audit_columns(df, source_file=None):
    """Append the two required Bronze audit columns.

    `_ingested_at` is always set to `current_timestamp()`.

    `_source_file` is resolved in priority order:
      1. an explicit literal `source_file` string (single-file loads), else
      2. left as-is if the caller already populated `_source_file`
         (e.g. the INFORM loader, which reads xlsx via pandas and sets it
         per-file before converting to Spark), else
      3. `input_file_name()` — the per-row origin for Spark-native multi-file
         globs (CBPF, FTS flows, COD, fieldmaps, ReliefWeb docs).

    The documented signature is `add_audit_columns(df, source_file: str)`;
    the `None` default extends it to cover the multi-file cases above.
    """
    df = df.withColumn("_ingested_at", F.current_timestamp())
    if source_file is not None:
        df = df.withColumn("_source_file", F.lit(source_file))
    elif "_source_file" not in df.columns:
        df = df.withColumn("_source_file", F.input_file_name())
    return df


# COMMAND ----------

def ensure_target_schema(catalog=CATALOG, schema=BRONZE_SCHEMA):
    """Verify the target schema exists. Does NOT create it.

    `CREATE SCHEMA`/`CREATE VOLUME` permissions are pending; provisioning is
    infra setup, separate from loader code (see task scope "Out of scope").
    Returns True if the schema exists, False otherwise. Prints a clear warning
    when missing so a dry-run still works but a real write will fail loudly
    rather than silently.
    """
    full = f"{catalog}.{schema}"
    try:
        exists = spark.catalog.databaseExists(full)  # noqa: F821 (spark is ambient)
    except Exception as e:  # pragma: no cover - defensive
        print(f"[WARN] could not check existence of {full}: {e}")
        exists = False
    if not exists:
        print(
            f"[WARN] target schema `{full}` does not exist yet "
            f"(CREATE SCHEMA/VOLUME permissions pending). Dry-run is fine; "
            f"a real write will fail until the schema is provisioned."
        )
    return exists


# COMMAND ----------

def parse_year_from_filename(path, patterns):
    """Extract a 4-digit year from a filename using the first matching regex.

    `patterns` is a list of regexes, each expected to capture the year in
    group 1. Tried in order; first match wins. Returns `int` or `None`.

    Used by the HNO loader (`hpc_hno_2026.csv` -> 2026). NOTE: the CBPF files
    are timestamped (`Allocations__20260518_145724_UTC.csv`) and do NOT encode
    the crisis year in the name — those loaders read the year from the in-file
    `Year` column instead, not from this helper.
    """
    base = path.rsplit("/", 1)[-1]
    for pat in patterns:
        m = re.search(pat, base, flags=re.IGNORECASE)
        if m:
            try:
                return int(m.group(1))
            except (ValueError, IndexError):
                continue
    return None


# COMMAND ----------

def write_bronze_delta(df, table, dry_run, merge_schema=False):
    """Single append-mode write entry point for every Bronze loader.

    - Append mode (Bronze is append-only).
    - `merge_schema=True` only where the source genuinely evolves
      (HNO across years; INFORM GCSI vs INFORM-Severity column sets).
    - `dry_run=True` short-circuits: counts and reports, writes nothing.

    Returns the row count (rows that were / would be appended).
    """
    n = df.count()
    if dry_run:
        print(
            f"[DRY RUN] would append {n:,} rows to `{table}` "
            f"(merge_schema={merge_schema}); not writing."
        )
        return n
    writer = df.write.format("delta").mode("append")
    if merge_schema:
        writer = writer.option("mergeSchema", "true")
    writer.saveAsTable(table)
    print(f"[WRITE] appended {n:,} rows to `{table}` (merge_schema={merge_schema}).")
    return n


# COMMAND ----------

def load_summary(df, rows_read, rows_written, dry_run):
    """Print the end-of-load summary required by the task scope:
    rows read, rows written, distinct `_source_file` count, schema fingerprint.
    """
    n_src = df.select("_source_file").distinct().count()
    fp = ", ".join(f"{f.name}:{f.dataType.simpleString()}" for f in df.schema.fields)
    print("=" * 72)
    print(f"LOAD SUMMARY (dry_run={dry_run})")
    print(f"  rows read             : {rows_read:,}")
    print(f"  rows written          : {rows_written:,}")
    print(f"  distinct _source_file : {n_src}")
    print(f"  columns ({len(df.schema.fields)}) : {fp}")
    print("=" * 72)


# COMMAND ----------

def get_dry_run():
    """Read the standard `dry_run` widget. Default 'false' (production-safe)."""
    return dbutils.widgets.get("dry_run").strip().lower() == "true"  # noqa: F821


def list_files(path, suffixes=None):
    """List files under a volume directory via dbutils.fs.ls.

    Returns a list of dbfs-style paths. Optionally filter by suffix tuple
    (e.g. ('.csv',) or ('.xlsx',)). Non-recursive.
    """
    out = []
    for fi in dbutils.fs.ls(path):  # noqa: F821
        if fi.name.endswith("/"):
            continue
        if suffixes and not fi.name.lower().endswith(tuple(s.lower() for s in suffixes)):
            continue
        out.append(fi.path)
    return out
