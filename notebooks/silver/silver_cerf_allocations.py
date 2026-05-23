# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: `silver_cerf_allocations`
# MAGIC
# MAGIC CERF allocations (RR + UFE windows), cleaned to snake_case. The UFE
# MAGIC subset is the labeled ground truth for Layer-1 validation
# MAGIC (`silver_ufe_label` derives from this table).
# MAGIC
# MAGIC `tableName` (`P`/`M`, meaning unresolved — open question for Mary Keller)
# MAGIC is carried through unused.

# COMMAND ----------

from _common import *  # noqa: F403,F401

# COMMAND ----------

import dlt


@dlt.table(
    name="silver_cerf_allocations",
    comment="CERF allocations (one row per project). window ∈ "
            "{Rapid Response, Underfunded Emergencies}. tableName carried unused.",
)
@dlt.expect_or_drop("valid_window",
                    "window IN ('Rapid Response','Underfunded Emergencies')")
@dlt.expect_or_drop("non_negative_amount", "amount_usd >= 0")
@dlt.expect_or_drop("valid_iso3", VALID_ISO3)
def silver_cerf_allocations():
    return (
        spark.table(bronze("bronze_cerf_allocations"))
        .select(
            F.col("projectID").cast("string").alias("project_id"),
            F.col("projectCode").cast("string").alias("project_code"),
            norm_iso3(F.col("countryCode")).alias("iso3"),
            F.col("windowFullName").alias("window"),
            F.col("totalAmountApproved").cast("double").alias("amount_usd"),
            F.to_date(F.col("dateUSGSignature")).alias("signature_date"),
            F.col("year").cast("int").alias("year"),
            F.col("agencyName").alias("agency"),
            F.col("emergencyTypeName").alias("emergency_type"),
            F.col("projectsectors").alias("sectors"),
            F.col("tableName").alias("table_name"),
        )
    )
