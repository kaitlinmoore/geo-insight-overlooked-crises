# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: `silver_boundaries`
# MAGIC
# MAGIC Admin0/1/2 subnational boundaries from `bronze_fieldmaps_boundaries`
# MAGIC (admin2-grain polygons with admin0/1 ids denormalized).
# MAGIC
# MAGIC **Geometry handling.** The geometry uses Apache **Sedona** ST_* functions
# MAGIC (the documented approach in `schemas.md`; Sedona must be installed on the
# MAGIC pipeline cluster — it is a cluster library, not a Python pip dependency
# MAGIC added here). The WKB `geometry` column is carried through verbatim (Delta
# MAGIC stores it as binary); validity and centroids are derived scalar columns,
# MAGIC since the Sedona geometry UDT is not a Delta-storable type.
# MAGIC
# MAGIC - `contested_border_flag` — heuristic: a non-trivial `status_cd` **or** a
# MAGIC   non-empty `wld_notes` marks a disputed/worldview-sensitive polygon.
# MAGIC - `h3_cells_r5` precompute is left out of v1 (optional in `schemas.md`);
# MAGIC   the H3 polyfill over ~43k polygons is deferred to a Gold spatial step.
# MAGIC
# MAGIC **Open item.** `adm{1,2}_id` ≡ HNO `Admin N PCode` equality is unverified;
# MAGIC the `pcode_join_coverage` warn-expectation surfaces mismatch.

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

import dlt


@dlt.table(
    name="silver_boundaries",
    comment="fieldmaps admin0/1/2 boundaries. geometry kept as WKB binary; "
            "_geom_valid, centroid_lon/lat derived via Sedona. "
            "contested_border_flag from status_cd/wld_notes.",
)
@dlt.expect_or_drop("valid_geometry", "_geom_valid = true")
@dlt.expect_or_drop("valid_iso3", VALID_ISO3)
@dlt.expect("pcode_join_coverage", "_prefix_ok = true")
def silver_boundaries():
    b = spark.table(bronze("bronze_fieldmaps_boundaries"))
    cd = dlt.read("silver_country_dim").select("iso3", "pcode_prefix")

    geom = F.expr("ST_GeomFromWKB(geometry)")
    contested = (
        (F.col("status_cd").isNotNull() & (F.col("status_cd").cast("int") != 0))
        | (F.col("wld_notes").isNotNull() & (F.length(F.trim(F.col("wld_notes"))) > 0))
    )

    out = (
        b
        .withColumn("iso3", norm_iso3(F.col("iso_3")))
        .withColumn("_geom_valid", F.expr("ST_IsValid(ST_GeomFromWKB(geometry))"))
        .withColumn("centroid_lon", F.expr("ST_X(ST_Centroid(ST_GeomFromWKB(geometry)))"))
        .withColumn("centroid_lat", F.expr("ST_Y(ST_Centroid(ST_GeomFromWKB(geometry)))"))
        .withColumn("contested_border_flag", contested)
        .withColumn("adm1_id", F.upper(F.trim(F.col("adm1_id"))))
        .join(cd, "iso3", "left")
        .withColumn(
            "_prefix_ok",
            F.col("pcode_prefix").isNull() | F.col("adm1_id").startswith(F.col("pcode_prefix")),
        )
    )

    return out.select(
        "iso3",
        F.col("adm0_id"),
        "adm1_id",
        F.col("adm2_id"),
        F.col("adm0_name"),
        F.col("adm1_name"),
        F.col("adm2_name"),
        F.col("status_nm"),
        "contested_border_flag",
        "centroid_lon",
        "centroid_lat",
        "_geom_valid",
        "_prefix_ok",
        F.col("geometry"),  # WKB binary, carried for Gold spatial ops
    )
