# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: `gold_donor_concentration` — country × year
# MAGIC
# MAGIC Donor-dependency metrics per country-year. Substrate for `donor_dependency`.
# MAGIC
# MAGIC Uses **FTS** donor identity (`silver_fts_flows.donor_org`), **not** CBPF
# MAGIC contributions — `bronze_cbpf_contributions` is global donor totals with no
# MAGIC country attribution (DECISIONS 2026-05-22). Computed over **paid** flows
# MAGIC (the realized funding), excluding `pending_attribution`.
# MAGIC
# MAGIC - `hhi` = Herfindahl–Hirschman index of donor shares (Σ shareᵢ²), 0–1.
# MAGIC - `top1_share` / `top3_share` = concentration in the largest donor(s).

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql import Window

# COMMAND ----------

flows = (
    spark.table(silver("silver_fts_flows"))
    .where("iso3 IS NOT NULL AND status = 'paid' AND allocation_method <> 'pending_attribution'")
    .withColumn("year", F.year("flow_date"))
    .withColumn("donor_org", F.coalesce(F.col("donor_org"), F.lit("Unknown")))
)

by_donor = (
    flows.groupBy("iso3", "year", "donor_org")
    .agg(F.sum("amount_usd").alias("donor_usd"))
    .where("donor_usd > 0")
)

w_cy = Window.partitionBy("iso3", "year")
by_donor = (
    by_donor
    .withColumn("country_total", F.sum("donor_usd").over(w_cy))
    .withColumn("share", F.col("donor_usd") / F.col("country_total"))
    .withColumn("donor_rank", F.row_number().over(w_cy.orderBy(F.col("donor_usd").desc())))
)

agg = (
    by_donor.groupBy("iso3", "year")
    .agg(
        F.countDistinct("donor_org").alias("n_donors"),
        F.sum(F.col("share") * F.col("share")).alias("hhi"),
        F.max(F.when(F.col("donor_rank") == 1, F.col("donor_org"))).alias("top1_donor"),
        F.max(F.when(F.col("donor_rank") == 1, F.col("share"))).alias("top1_share"),
        F.sum(F.when(F.col("donor_rank") <= 3, F.col("share")).otherwise(0.0)).alias("top3_share"),
    )
)

assert_expectations(
    agg,
    [
        ("warn:hhi_unit_interval", "hhi BETWEEN 0 AND 1.0001"),
        ("warn:top1_le_top3", "top1_share <= top3_share + 0.0001"),
    ],
    "gold_donor_concentration",
)
(agg.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .partitionBy("year")
    .saveAsTable(gold("gold_donor_concentration")))
