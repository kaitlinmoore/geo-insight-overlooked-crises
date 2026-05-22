# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: `silver_subnational_needs`
# MAGIC
# MAGIC Admin1 × cluster PIN from HNO, where subnational data exists (2024/2025
# MAGIC only — 2026 dropped all admin columns).
# MAGIC
# MAGIC ## Admin1 derivation via P-code rollup (task #5 / data_profiling.md)
# MAGIC
# MAGIC Several priority countries have only **admin2** rows in HNO (SDN, YEM,
# MAGIC HTI, VEN, NGA — no admin1 rows at all). Admin1 is therefore *derived*:
# MAGIC
# MAGIC - Rows that already carry an `Admin 1 PCode` (e.g. MMR, COL) use it.
# MAGIC - Rows with only an `Admin 2 PCode` get their admin1 from the
# MAGIC   authoritative `global_pcodes` parent lookup (admin2 P-code → its
# MAGIC   `Parent P-Code` = admin1), then PIN is summed over the admin2 children
# MAGIC   within each admin1.
# MAGIC
# MAGIC In practice a country has *either* admin1 rows *or* admin2 rows (never
# MAGIC both), so the admin2→admin1 sum doesn't double-count an existing admin1
# MAGIC total. `admin1_derived` flags the rolled-up rows for transparency.
# MAGIC
# MAGIC Countries with **no** admin rows (BFA, COD country-only; ETH zero HNO)
# MAGIC simply do not appear here; the consuming Gold table assigns
# MAGIC `data_sparsity_flag` to countries absent from this table.
# MAGIC
# MAGIC `admin2_pcode` is NULL in the output because the grain is admin1 (the
# MAGIC column is retained per `schemas.md`).

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

import dlt


def _to_bigint(col):
    return F.regexp_replace(F.trim(col), r"[,\s]", "").cast("bigint")


@dlt.table(
    name="silver_subnational_needs",
    comment="Admin1×year×cluster PIN from HNO 2024/2025. Admin1 derived via "
            "global_pcodes parent rollup where HNO only has admin2 rows "
            "(SDN/YEM/HTI/VEN/NGA). 2026 absent (no HNO subnational).",
)
@dlt.expect_or_drop("non_null_admin1_pcode", "admin1_pcode IS NOT NULL")
@dlt.expect_or_drop("non_negative_pin", "people_in_need >= 0")
@dlt.expect("pcode_prefix_matches_iso3", "_prefix_ok = true")
def silver_subnational_needs():
    # authoritative admin2 -> admin1 parent map + admin1 names
    pcodes = (
        spark.read.option("header", "true").csv(staging("global_pcodes_raw.csv"))
        .toDF("location", "admin_level", "pcode", "name", "parent_pcode",
              "valid_from", "version")
    )
    adm2_parent = (
        pcodes.where(F.col("admin_level").cast("int") == 2)
        .select(
            F.upper(F.trim(F.col("pcode"))).alias("adm2_pcode"),
            F.upper(F.trim(F.col("parent_pcode"))).alias("derived_admin1_pcode"),
        )
        .dropDuplicates(["adm2_pcode"])
    )
    adm1_names = (
        pcodes.where(F.col("admin_level").cast("int") == 1)
        .select(
            F.upper(F.trim(F.col("pcode"))).alias("adm1_pcode"),
            F.col("name").alias("ref_admin1_name"),
        )
        .dropDuplicates(["adm1_pcode"])
    )

    hno = (
        spark.table(bronze("bronze_hno"))
        .where("`Country ISO3` IS NOT NULL AND `Country ISO3` NOT LIKE '#%'")
        .withColumn("iso3", norm_iso3(F.col("`Country ISO3`")))
        .withColumn("year", F.col("_source_year").cast("int"))
        .withColumn("_cat", F.lower(F.trim(F.col("Category"))))
        # keep total-category admin rows only
        .where("_cat = 'total' AND (`Admin 1 PCode` IS NOT NULL OR `Admin 2 PCode` IS NOT NULL)")
        .select(
            "iso3", "year",
            F.upper(F.trim(F.col("`Admin 1 PCode`"))).alias("native_admin1_pcode"),
            F.col("`Admin 1 Name`").alias("native_admin1_name"),
            F.upper(F.trim(F.col("`Admin 2 PCode`"))).alias("adm2_pcode"),
            F.col("Cluster").alias("cluster"),
            _to_bigint(F.col("`In Need`")).alias("people_in_need"),
            _to_bigint(F.col("Targeted")).alias("targeted"),
        )
    )

    # derive admin1 where native is missing
    hno = hno.join(adm2_parent, "adm2_pcode", "left")
    hno = (
        hno
        .withColumn(
            "admin1_pcode",
            F.coalesce(F.col("native_admin1_pcode"), F.col("derived_admin1_pcode")),
        )
        .withColumn("admin1_derived", F.col("native_admin1_pcode").isNull())
    )

    rolled = (
        hno.groupBy("iso3", "year", "admin1_pcode", "cluster")
        .agg(
            F.sum("people_in_need").alias("people_in_need"),
            F.sum("targeted").alias("targeted"),
            F.max("native_admin1_name").alias("native_admin1_name"),
            F.max("admin1_derived").alias("admin1_derived"),
        )
    )

    # names + prefix check via country_dim
    cd = dlt.read("silver_country_dim").select("iso3", "pcode_prefix")
    out = (
        rolled
        .join(adm1_names, rolled["admin1_pcode"] == adm1_names["adm1_pcode"], "left")
        .join(cd, "iso3", "left")
        .withColumn("admin1_name",
                    F.coalesce(F.col("native_admin1_name"), F.col("ref_admin1_name")))
        .withColumn("admin2_pcode", F.lit(None).cast("string"))
        .withColumn("_prefix_ok",
                    F.col("pcode_prefix").isNull()
                    | F.col("admin1_pcode").startswith(F.col("pcode_prefix")))
    )

    return out.select(
        "iso3", "year", "admin1_pcode", "admin1_name", "admin2_pcode",
        "cluster", "people_in_need", "targeted", "admin1_derived", "_prefix_ok",
    )
