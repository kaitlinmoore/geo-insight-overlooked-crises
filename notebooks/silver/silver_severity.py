# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: `silver_severity`
# MAGIC
# MAGIC Country × year INFORM severity, collapsing the monthly snapshots and the
# MAGIC multiple-crises-per-country rows from `bronze_inform_severity`.
# MAGIC
# MAGIC **Header resolution.** Bronze keeps the original spreadsheet headers
# MAGIC verbatim (no rename), and those vary slightly across the GCSI era and the
# MAGIC INFORM era. Columns are therefore resolved by **case-insensitive regex**
# MAGIC against `df.columns` rather than hard-coded names — this is the part most
# MAGIC worth a smoke test against a real Bronze sample before deploy.
# MAGIC
# MAGIC **`snapshot_date` source of truth.** The Bronze loader derives
# MAGIC `snapshot_date` from the filename, *preferring the spelled-out month name*
# MAGIC — which already corrects the one known misnamed file
# MAGIC (`...betaversionfebruary2020.xlsx`, numeric prefix from 2019). So a full
# MAGIC `About`-sheet read is **not** needed for v1; we trust the Bronze date and
# MAGIC quarantine (warn) any implausible value. Reading the `About` sheet per
# MAGIC workbook to override remains the documented upgrade path
# MAGIC (`open-questions.md`).
# MAGIC
# MAGIC The `Weights` marker row and the `(1-10)`/`(1-5)` annotation rows kept in
# MAGIC Bronze fall out naturally: they carry no valid ISO3 and no numeric
# MAGIC severity, so `valid_iso3` / range expectations drop them.

# COMMAND ----------

from _common import *  # noqa: F403,F401

# COMMAND ----------

import dlt
import re


def _resolve(columns, *patterns):
    """First column whose name matches any (case-insensitive) regex, else None."""
    for pat in patterns:
        rx = re.compile(pat, re.IGNORECASE)
        for c in columns:
            if rx.search(c):
                return c
    return None


@dlt.table(
    name="silver_severity",
    comment="Country×year INFORM severity. Monthly snapshots collapsed "
            "(mean/max index, max 1-5 category, modal trend/reliability). "
            "Severity gate downstream uses severity_category_max (the 1-5 scale).",
)
@dlt.expect_or_drop("valid_iso3", VALID_ISO3)
@dlt.expect_or_drop("severity_index_in_range", "severity_index_max BETWEEN 0 AND 10")
@dlt.expect_or_drop("category_in_range", "severity_category_max BETWEEN 1 AND 5")
@dlt.expect("snapshot_date_plausible",
            "year(latest_snapshot_date) BETWEEN 2018 AND 2027")
def silver_severity():
    src = spark.table(bronze("bronze_inform_severity"))
    cols = src.columns

    iso_c = _resolve(cols, r"^iso.?3$", r"iso.?3")
    # INFORM-era column names preferred. GCSI-era columns (SEVERITY CATEGORY /
    # CRISIS SEVERITY) exist in the unioned bronze table because of the GCSI->
    # INFORM rebrand in Sep 2020 but are NULL for INFORM-era rows. Anchoring
    # the patterns and trying INFORM names first picks the column that
    # actually has data.
    
    idx_c = _resolve(
        cols,
        r"^inform\s+severity\s+index(?:__dup\d+)?$",  # INFORM era
        r"^crisis\s+severity(?:__dup\d+)?$",          # GCSI fallback
        r"^severity\s*index$",                         # generic last resort
    )
    cat_c = _resolve(
        cols,
        r"^inform\s+severity\s+category(?:__dup\d+)?$",  # INFORM era
        r"^severity\s+category(?:__dup\d+)?$",           # GCSI fallback
        r"^categor",                                      # generic last resort
    )
    trend_c = _resolve(cols, r"trend")
    rel_c = _resolve(cols, r"reliab")

    clean = (
        src
        .where("snapshot_date IS NOT NULL")
        .select(
            norm_iso3(F.col(f"`{iso_c}`")).alias("iso3"),
            F.to_date(F.col("snapshot_date")).alias("snapshot_date"),
            F.col(f"`{idx_c}`").cast("double").alias("sev_index"),
            F.col(f"`{cat_c}`").cast("double").cast("int").alias("sev_category"),
            (F.col(f"`{trend_c}`") if trend_c else F.lit(None)).alias("trend"),
            (F.col(f"`{rel_c}`") if rel_c else F.lit(None)).alias("reliability"),
        )
        .where("length(iso3) = 3 AND sev_index IS NOT NULL")
        .withColumn("year", F.year("snapshot_date"))
    )

    # collapse multiple crises per (country, snapshot) → the max severity
    monthly = (
        clean.groupBy("iso3", "year", "snapshot_date")
        .agg(F.max("sev_index").alias("idx_m"), F.max("sev_category").alias("cat_m"))
    )

    annual = (
        monthly.groupBy("iso3", "year")
        .agg(
            F.avg("idx_m").alias("severity_index_mean"),
            F.max("idx_m").alias("severity_index_max"),
            F.max("cat_m").alias("severity_category_max"),
            F.countDistinct("snapshot_date").alias("n_snapshots"),
            F.max("snapshot_date").alias("latest_snapshot_date"),
        )
    )

    # modal trend / reliability within (iso3, year)
    def _modal(value_col, out_name):
        w = Window.partitionBy("iso3", "year").orderBy(F.col("cnt").desc(), F.col(value_col))
        return (
            clean.where(F.col(value_col).isNotNull())
            .groupBy("iso3", "year", value_col).agg(F.count("*").alias("cnt"))
            .withColumn("_rk", F.row_number().over(w))
            .where("_rk = 1")
            .select("iso3", "year", F.col(value_col).alias(out_name))
        )

    trend_modal = _modal("trend", "trend_modal")
    rel_modal = _modal("reliability", "reliability_modal")

    return (
        annual
        .join(trend_modal, ["iso3", "year"], "left")
        .join(rel_modal, ["iso3", "year"], "left")
    )
