"""Silver shared helpers (`_common`).

Cross-cutting constants and tiny utilities every Silver DLT notebook
depends on. Imported via `from _common import *` (Lakeflow Declarative
Pipelines does not honor `%run`, and refuses to import files carrying
the Databricks notebook header marker — this file is therefore a plain
Python module, not a notebook; see `docs/notes/serverless_constraints.md`).

**Read patterns (one convention, applied everywhere):**
- **Bronze inputs** are *external* to this DLT pipeline (written by the
  separate Bronze loaders into `geo_insight.bronze.*`). Read them with
  `spark.table(bronze("bronze_X"))` — `dlt.read` would not resolve a
  table that isn't defined in this pipeline.
- **Silver→Silver** dependencies (e.g. `silver_fts_flows` reading
  `silver_population`) use `dlt.read("silver_X")` so DLT records the
  lineage edge and orders the graph.
- **Staging CSVs** that never got a Bronze table (`country_taxonomy_raw`,
  `global_pcodes_raw`, the hand-built crosswalk) are read straight off the
  volume with `spark.read.csv(staging(...))`.

**DLT severity legend** (matches `docs/architecture.md` Layer-1 mapping):
- `@dlt.expect_or_drop` — invalid rows dropped from the table.
- `@dlt.expect` — warn-and-keep ("quarantine"): rows retained, the
  violation is tracked in the DLT event log / data-quality metrics.
- `@dlt.expect_or_fail` — contract violation that halts the pipeline.
"""

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
