# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: `silver_requirements`
# MAGIC
# MAGIC Country × year × plan requirements, with the **dual grain** decided on
# MAGIC 2026-05-22 (`DECISIONS.md`):
# MAGIC
# MAGIC - **(a) plan-level rows** — `bronze_fts_plan` (which is *already*
# MAGIC   country×plan×year grain, so per-country requirements are native and no
# MAGIC   allocation cascade is needed here) joined to `bronze_hrp` on plan
# MAGIC   `code` for the plan metadata (type, locations, dates).
# MAGIC - **(b) country-aggregate rows** — the `Not specified` rows in
# MAGIC   `bronze_fts_plan` (`code IS NULL`, `name='Not specified'`), attributed
# MAGIC   directly to `countryCode` with `plan_code = NULL`. These preserve the
# MAGIC   country-year presence for no-HRP countries (e.g. ETH 2026) so the
# MAGIC   ranking doesn't silently drop them. Their requirement is genuinely
# MAGIC   undefined (off-plan funding has no plan to require against), so
# MAGIC   `requirement_usd` is NULL — which is exactly the `gap_ratio`-undefined
# MAGIC   path methodology routes to `chronic_no_plan` / `well_funded`. The
# MAGIC   off-plan *funding* for these countries flows through `silver_fts_flows`
# MAGIC   (from the underlying flow records), not through this table.
# MAGIC
# MAGIC **`requirement_usd` source.** `schemas.md` names `revisedRequirements`;
# MAGIC because `bronze_fts_plan` carries the *per-country* requirement for each
# MAGIC plan row, that per-country value is preferred (correct denominator for a
# MAGIC country-grain `gap_ratio`), with HRP `revisedRequirements` →
# MAGIC `origRequirements` as fallback. Flagged for the user in the handoff.
# MAGIC
# MAGIC **Plan-type unification.** The 2024 HRP→HNRP rename means
# MAGIC `Humanitarian response plan` and `Humanitarian needs and response plan`
# MAGIC are folded into a single `country_response_plan` type; other appeal
# MAGIC types are carried through verbatim.

# COMMAND ----------

from _common import *  # noqa: F403,F401

# COMMAND ----------

import dlt

_CURRENT_YEAR = F.year(F.current_date())


def _unify_plan_type(type_name):
    return (
        F.when(
            type_name.isin("Humanitarian response plan",
                           "Humanitarian needs and response plan"),
            F.lit("country_response_plan"),
        ).otherwise(type_name)
    )


@dlt.table(
    name="silver_requirements",
    comment="Country×year×plan requirements. Dual grain: plan-level rows + "
            "'Not specified' country-aggregate rows (plan_code NULL). "
            "Future-dated (year > current) rows filtered out.",
)
@dlt.expect_or_drop("valid_iso3", VALID_ISO3)
@dlt.expect_or_drop("non_negative_requirement",
                    "requirement_usd IS NULL OR requirement_usd >= 0")
@dlt.expect_or_drop("valid_dates",
                    "start_date IS NULL OR end_date IS NULL OR end_date >= start_date")
@dlt.expect("requirement_present_for_plan_rows",
            "plan_code IS NULL OR requirement_usd IS NOT NULL")
def silver_requirements():
    fts = (
        spark.table(bronze("bronze_fts_plan"))
        .withColumn("iso3", norm_iso3(F.col("countryCode")))
        .where(F.col("year").cast("int") <= _CURRENT_YEAR)
    )

    # Drop the HXL hashtag row and select plan-metadata columns from HRP.
    hrp = (
        spark.table(bronze("bronze_hrp"))
        .where("code IS NOT NULL AND code <> '#response+code'")
        .select(
            F.col("code").alias("hrp_code"),
            F.col("planVersion").alias("hrp_plan_name"),
            F.col("locations").alias("hrp_locations"),
            F.col("revisedRequirements").cast("double").alias("hrp_revised_req"),
            F.col("origRequirements").cast("double").alias("hrp_orig_req"),
            F.to_date(F.col("startDate")).alias("hrp_start"),
            F.to_date(F.col("endDate")).alias("hrp_end"),
        )
        .dropDuplicates(["hrp_code"])
    )

    # (a) plan-level rows ----------------------------------------------------
    plan_level = (
        fts.where("code IS NOT NULL")
        .join(hrp, fts["code"] == hrp["hrp_code"], "left")
    )
    # locations: pipe-with-spaces delimited ISO3 list (HRP convention).
    country_list = F.transform(
        F.split(F.coalesce(F.col("hrp_locations"), F.col("iso3")), r"\s*\|\s*"),
        lambda c: F.upper(F.trim(c)),
    )
    plan_level = plan_level.select(
        F.col("iso3"),
        F.col("year").cast("int").alias("year"),
        F.col("code").alias("plan_code"),
        F.coalesce(F.col("hrp_plan_name"), F.col("name")).alias("plan_name"),
        _unify_plan_type(F.col("typeName")).alias("plan_type"),
        F.coalesce(F.col("requirements").cast("double"),
                   F.col("hrp_revised_req"),
                   F.col("hrp_orig_req")).alias("requirement_usd"),
        (F.size(country_list) > 1).alias("is_multi_country"),
        country_list.alias("country_list"),
        F.coalesce(F.col("hrp_start"), F.to_date(F.col("startDate"))).alias("start_date"),
        F.coalesce(F.col("hrp_end"), F.to_date(F.col("endDate"))).alias("end_date"),
    )

    # (b) country-aggregate "Not specified" rows ----------------------------
    agg = (
        fts.where("code IS NULL AND name = 'Not specified'")
        .select(
            F.col("iso3"),
            F.col("year").cast("int").alias("year"),
            F.lit(None).cast("string").alias("plan_code"),
            F.lit("Not specified").alias("plan_name"),
            F.lit("off_plan").alias("plan_type"),
            F.lit(None).cast("double").alias("requirement_usd"),
            F.lit(False).alias("is_multi_country"),
            F.array(F.col("iso3")).alias("country_list"),
            F.lit(None).cast("date").alias("start_date"),
            F.lit(None).cast("date").alias("end_date"),
        )
    )

    # Uniqueness on (iso3, year, plan_code) is enforced here (DLT expectations
    # are row-level and cannot assert a group-uniqueness contract).
    return plan_level.unionByName(agg).dropDuplicates(["iso3", "year", "plan_code"])
