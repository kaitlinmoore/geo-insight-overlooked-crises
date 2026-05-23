# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: `silver_ufe_label`
# MAGIC
# MAGIC The Layer-1 labeled ground truth: country × year × round binary UFE
# MAGIC selection. **Derived from `silver_cerf_allocations`** (the principled
# MAGIC Bronze→Silver path) rather than the pre-baked `staging/ufe_labels.csv`,
# MAGIC so the lineage is auditable end-to-end. The staging CSV remains an
# MAGIC equivalent shortcut if a direct load is ever preferred.
# MAGIC
# MAGIC Only UFE-selected country-rounds appear here (`ufe_selected = true`);
# MAGIC the negatives are the ranking universe, supplied by the validation join
# MAGIC in `gold_ufe_validation`.
# MAGIC
# MAGIC **Round derivation caveat.** `round` (H1/H2) is inferred from the USG
# MAGIC signature month, which lags the ERC round announcement 2–6 months — so
# MAGIC the **year grain is exact, the round grain approximate** (documented in
# MAGIC `methodology.md`).

# COMMAND ----------

from _common import *  # noqa: F403,F401

# COMMAND ----------

import dlt


@dlt.table(
    name="silver_ufe_label",
    comment="UFE-selected country×year×round labels (ufe_selected=true), "
            "derived from CERF Underfunded Emergencies allocations. Round "
            "inferred from signature month (approximate; year exact).",
)
@dlt.expect_or_drop("valid_iso3", VALID_ISO3)
@dlt.expect("round_in_set", "round IN ('H1','H2')")
@dlt.expect("boolean_label", "ufe_selected IS NOT NULL")
def silver_ufe_label():
    ufe = (
        dlt.read("silver_cerf_allocations")
        .where("window = 'Underfunded Emergencies'")
        .withColumn(
            "round",
            F.when(F.month("signature_date") <= 6, F.lit("H1")).otherwise(F.lit("H2")),
        )
        .groupBy("iso3", "year", "round")
        .agg(F.sum("amount_usd").alias("allocation_usd"))
        .withColumn("ufe_selected", F.lit(True))
    )
    names = dlt.read("silver_country_dim").select("iso3", "country_name")
    return (
        ufe.join(names, "iso3", "left")
        .select("iso3", "country_name", "year", "round", "ufe_selected", "allocation_usd")
    )
