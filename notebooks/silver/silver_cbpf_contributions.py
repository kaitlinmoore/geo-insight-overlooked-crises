# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: `silver_cbpf_contributions`
# MAGIC
# MAGIC **Not in the `schemas.md` Silver enumeration** — added per task scope #8
# MAGIC (the within-file-dedupe open item, `open-questions.md` 2026-05-22).
# MAGIC Flagged for the user in the handoff.
# MAGIC
# MAGIC `bronze_cbpf_contributions` has 289 within-file duplicate `(Year, Donor)`
# MAGIC pairs (pledge revisions / multi-installment payments). The Silver rule is
# MAGIC to **sum** `Paid`/`Pledged`/`Total` over `(Year, Donor)` and keep an
# MAGIC `n_records` count for transparency.
# MAGIC
# MAGIC This table is global donor totals with **no country/fund attribution**;
# MAGIC it does **not** feed `gold_donor_concentration` (that uses
# MAGIC `silver_fts_flows.donor_org` — DECISIONS 2026-05-22). It exists for the
# MAGIC optional CBPF Allocation View's pooled-fund context.

# COMMAND ----------

from _common import *  # noqa: F403,F401

# COMMAND ----------

import dlt


@dlt.table(
    name="silver_cbpf_contributions",
    comment="Global CBPF donor contributions by year×donor, summed over the "
            "within-file duplicate line items (n_records retained). No country "
            "attribution — not used for donor_concentration.",
)
@dlt.expect_or_drop("non_negative_total", "total_usd >= 0")
@dlt.expect("valid_year", "year BETWEEN 2018 AND 2027")
def silver_cbpf_contributions():
    return (
        spark.table(bronze("bronze_cbpf_contributions"))
        .select(
            F.col("Year").cast("int").alias("year"),
            F.col("Donor").alias("donor"),
            F.col("`Donor type`").alias("donor_type"),
            F.col("Paid").cast("double").alias("paid_usd"),
            F.col("Pledged").cast("double").alias("pledged_usd"),
            F.col("Total").cast("double").alias("total_usd"),
        )
        .groupBy("year", "donor")
        .agg(
            F.first("donor_type", ignorenulls=True).alias("donor_type"),
            F.sum("paid_usd").alias("paid_usd"),
            F.sum("pledged_usd").alias("pledged_usd"),
            F.sum("total_usd").alias("total_usd"),
            F.count("*").alias("n_records"),
        )
    )
