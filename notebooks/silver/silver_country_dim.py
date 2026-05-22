# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: `silver_country_dim`
# MAGIC
# MAGIC Country reference dimension — the spine every country-grain table joins
# MAGIC to. Built from the staging taxonomy CSV (no Bronze table exists for it)
# MAGIC plus the global P-code reference for the per-country P-code prefix.
# MAGIC
# MAGIC **Source columns used** (from `staging/country_taxonomy_raw.csv`):
# MAGIC `m49 numerical code` → `iso_numeric` (bridges ACLED `iso`),
# MAGIC `ISO 3166-1 Alpha 2-Codes` → `iso2`, `ISO 3166-1 Alpha 3-Codes` → `iso3`,
# MAGIC `English Short` → `country_name`, `Region Name` → `region`,
# MAGIC `Sub-region Name` → `subregion`, `Has HRP` / `In GHO` → `is_in_scope`.
# MAGIC `pcode_prefix` is derived from the leading alpha characters of each
# MAGIC country's admin-1 P-codes in `staging/global_pcodes_raw.csv`.
# MAGIC
# MAGIC **No `pycountry` dependency** — the taxonomy CSV already carries the
# MAGIC numeric/alpha codes, so the numeric↔alpha bridge needs no extra package
# MAGIC (stays within stock Databricks Runtime).

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

import dlt


@dlt.table(
    name="silver_country_dim",
    comment="Country reference dimension (iso3 spine); numeric/alpha codes, "
            "OCHA region, P-code prefix, in-scope flag.",
)
@dlt.expect_or_drop("valid_iso3", VALID_ISO3)
@dlt.expect("non_null_country_name", "country_name IS NOT NULL")
def silver_country_dim():
    tax = (
        spark.read.option("header", "true").option("multiLine", "true")
        .csv(staging("country_taxonomy_raw.csv"))
    )

    base = (
        tax.select(
            norm_iso3(F.col("`ISO 3166-1 Alpha 3-Codes`")).alias("iso3"),
            F.col("`m49 numerical code`").cast("int").alias("iso_numeric"),
            F.upper(F.trim(F.col("`ISO 3166-1 Alpha 2-Codes`"))).alias("iso2"),
            F.coalesce(F.col("`English Short`"), F.col("`Preferred Term`")).alias("country_name"),
            F.col("`Region Name`").alias("region"),
            F.col("`Sub-region Name`").alias("subregion"),
            ((F.upper(F.trim(F.col("`Has HRP`"))) == "Y")
             | (F.upper(F.trim(F.col("`In GHO`"))) == "Y")).alias("is_in_scope"),
        )
        .where("iso3 IS NOT NULL AND length(iso3) = 3")
        # One row per ISO3 (taxonomy can carry deprecated/duplicate entries).
        .dropDuplicates(["iso3"])
    )

    # Per-country P-code prefix = leading alpha chars of admin-1 P-codes
    # (e.g. AFG admin1 'AF01' → 'AF'). Aggregated to the modal prefix per
    # country to absorb the rare mixed-prefix country.
    pcodes = (
        spark.read.option("header", "true")
        .csv(staging("global_pcodes_raw.csv"))
    )
    prefixes = (
        pcodes
        .where(F.col("`Admin Level`").cast("int") == 1)
        .select(
            norm_iso3(F.col("Location")).alias("iso3"),
            F.regexp_extract(F.col("`P-Code`"), r"^([A-Za-z]+)", 1).alias("pcode_prefix"),
        )
        .where("pcode_prefix <> ''")
        .groupBy("iso3", "pcode_prefix").count()
    )
    w = Window.partitionBy("iso3").orderBy(F.col("count").desc())
    prefixes = (
        prefixes.withColumn("_rk", F.row_number().over(w))
        .where("_rk = 1")
        .select("iso3", "pcode_prefix")
    )

    return base.join(prefixes, on="iso3", how="left")
