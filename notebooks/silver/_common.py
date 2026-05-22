# Databricks notebook source
# MAGIC %md
# MAGIC # Silver shared helpers (`_common`)
# MAGIC
# MAGIC Cross-cutting constants and tiny utilities every Silver DLT notebook
# MAGIC depends on. Imported via `%run ./_common` so the names resolve in the
# MAGIC caller's notebook context (same `spark` / `dlt`).
# MAGIC
# MAGIC **Read patterns (one convention, applied everywhere):**
# MAGIC - **Bronze inputs** are *external* to this DLT pipeline (written by the
# MAGIC   separate Bronze loaders into `geo_insight.bronze.*`). Read them with
# MAGIC   `spark.table(bronze("bronze_X"))` — `dlt.read` would not resolve a
# MAGIC   table that isn't defined in this pipeline.
# MAGIC - **Silver→Silver** dependencies (e.g. `silver_fts_flows` reading
# MAGIC   `silver_population`) use `dlt.read("silver_X")` so DLT records the
# MAGIC   lineage edge and orders the graph.
# MAGIC - **Staging CSVs** that never got a Bronze table (`country_taxonomy_raw`,
# MAGIC   `global_pcodes_raw`, the hand-built crosswalk) are read straight off the
# MAGIC   volume with `spark.read.csv(staging(...))`.
# MAGIC
# MAGIC **DLT severity legend** (matches `docs/architecture.md` Layer-1 mapping):
# MAGIC - `@dlt.expect_or_drop` — invalid rows dropped from the table.
# MAGIC - `@dlt.expect` — warn-and-keep ("quarantine"): rows retained, the
# MAGIC   violation is tracked in the DLT event log / data-quality metrics.
# MAGIC - `@dlt.expect_or_fail` — contract violation that halts the pipeline.

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql import Window

# Namespace (docs/schemas.md "Conventions")
CATALOG = "geo_insight"
BRONZE_SCHEMA = "bronze"
SILVER_SCHEMA = "silver"
VOLUME_BASE = "/Volumes/geo_insight/raw/staging"


def bronze(name):
    """Fully-qualified Bronze table name for `spark.table(...)`."""
    return f"{CATALOG}.{BRONZE_SCHEMA}.{name}"


def staging(*parts):
    """Volume path under the raw staging area (FUSE path for spark.read)."""
    tail = "/".join(p.strip("/") for p in parts)
    return f"{VOLUME_BASE}/{tail}"


# COMMAND ----------

# Reusable expectation predicates (SQL strings passed to @dlt.expect*).
# Keeping them here means the same column contract reads identically across
# every table that asserts it.
VALID_ISO3 = "iso3 IS NOT NULL AND length(iso3) = 3"
NON_NEGATIVE_AMOUNT = "amount_usd >= 0"


def norm_iso3(col):
    """Uppercase + trim an ISO3 column expression. Returns a Column."""
    return F.upper(F.trim(col))


def percentile_rank_within_year(value_col, year_col="year"):
    """Within-year percentile rank in [0, 1] for `value_col`.

    `percent_rank()` is 0 for the minimum and 1 for the maximum within each
    year partition — the within-year normalization `methodology.md` specifies
    for the composite components (here used by `silver_media_attention`).
    """
    w = Window.partitionBy(year_col).orderBy(value_col)
    return F.percent_rank().over(w)
