# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: `gold_subnational_index` — admin1 × year
# MAGIC
# MAGIC Admin1-level need + inferred funding, where HNO subnational data exists.
# MAGIC Substrate for `subnational_hotspots`.
# MAGIC
# MAGIC - **admin1_pin** from `silver_subnational_needs` (prefer the `ALL`-cluster
# MAGIC   caseload per admin1; fall back to the max across clusters).
# MAGIC - **admin1_inferred_funding** = country paid funding × (admin1 PIN ÷ country
# MAGIC   total PIN) — the PIN-proportional inference (`methodology.md`
# MAGIC   §Subnational funding inference), **always flagged** as an estimate.
# MAGIC - **admin1_overlooked_score** (v1, simplified): within-year percentile rank
# MAGIC   of admin1 PIN, scaled by the country `gap_ratio` so a high-need admin1 in
# MAGIC   a poorly funded country scores higher. The full admin1 composite (the
# MAGIC   country score as an aggregation of subnational results) is a refinement;
# MAGIC   flagged for the user.
# MAGIC
# MAGIC **⚠️ 2026 coverage.** HNO 2026 dropped subnational columns entirely
# MAGIC (`silver_subnational_needs` has no 2026 rows), so 2026 admin1 rows are
# MAGIC absent and the country carries `data_sparsity_flag` downstream.

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql import Window

# COMMAND ----------

sub = spark.table(silver("silver_subnational_needs"))

admin1_pin = (
    sub.groupBy("iso3", "year", "admin1_pcode", "admin1_name")
    .agg(
        F.max(F.when(F.col("cluster") == "ALL", F.col("people_in_need"))).alias("_all_pin"),
        F.max("people_in_need").alias("_max_pin"),
    )
    .withColumn("admin1_pin", F.coalesce(F.col("_all_pin"), F.col("_max_pin")))
    .select("iso3", "year", "admin1_pcode", "admin1_name", "admin1_pin")
)

# country funding (paid) + country total PIN + country gap_ratio
country_funding = funding_by_country(spark).select("iso3", "year", "funded_paid_usd")
country_pin = (
    spark.table(silver("silver_needs"))
    .where("cluster = 'ALL'")
    .select("iso3", "year", "pin_total_country")
    .dropDuplicates(["iso3", "year"])
)
country_gap = gap_ratio_base(spark).select("iso3", "year", "gap_ratio")

# COMMAND ----------

df = (
    admin1_pin
    .join(country_funding, ["iso3", "year"], "left")
    .join(country_pin, ["iso3", "year"], "left")
    .join(country_gap, ["iso3", "year"], "left")
)

# pin share within country-year (denominator from the country caseload; if the
# caseload is missing, fall back to the sum of admin1 PINs we observed).
w_country = Window.partitionBy("iso3", "year")
df = df.withColumn(
    "_pin_denom",
    F.coalesce(F.col("pin_total_country"), F.sum("admin1_pin").over(w_country)),
)
df = df.withColumn(
    "pin_share",
    F.when(F.col("_pin_denom") > 0, F.col("admin1_pin") / F.col("_pin_denom")),
)

df = df.withColumn(
    "admin1_inferred_funding",
    F.col("funded_paid_usd") * F.coalesce(F.col("pin_share"), F.lit(0.0)),
)

# simplified admin1 overlooked score: need percentile × country gap
df = df.withColumn(
    "_pin_norm", percentile_rank_within_year(F.col("admin1_pin"), "year")
)
df = df.withColumn(
    "admin1_overlooked_score",
    F.col("_pin_norm") * F.coalesce(F.col("gap_ratio"), F.lit(0.5)),
)
df = df.withColumn(
    "admin1_rank_in_country",
    F.row_number().over(w_country.orderBy(F.col("admin1_overlooked_score").desc())),
)
df = df.withColumn("is_inference_flagged", F.lit(True))
df = df.withColumn(
    "data_sparsity_flag",
    F.col("admin1_pin").isNull() | F.col("pin_total_country").isNull(),
)

out = df.select(
    "iso3", "admin1_pcode", "admin1_name", "year",
    "admin1_pin", "admin1_inferred_funding", "admin1_overlooked_score",
    "admin1_rank_in_country", "pin_share",
    "is_inference_flagged", "data_sparsity_flag",
).where("admin1_pcode IS NOT NULL")

assert_expectations(
    out,
    [
        ("warn:inference_flagged", "is_inference_flagged = true"),
        ("warn:pin_share_unit_interval", "pin_share IS NULL OR pin_share BETWEEN 0 AND 1.0001"),
    ],
    "gold_subnational_index",
)
(out.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .partitionBy("year")
    .saveAsTable(gold("gold_subnational_index")))
