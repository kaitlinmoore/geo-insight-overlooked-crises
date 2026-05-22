# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: `gold_cross_border_patterns` — 📋 Day-4 stretch (LOWER FIDELITY)
# MAGIC
# MAGIC Adjacent overlooked admin1 areas across national borders — the Sahel /
# MAGIC Horn / Lake Chad / N. Central America regional dynamics country-level ranks
# MAGIC hide. Substrate for `cross_border_pattern`. **Day-4 stretch, not v1
# MAGIC critical** — drafted at lower fidelity per the task brief.
# MAGIC
# MAGIC **What is implemented:** the candidate admin1 pair set restricted to the
# MAGIC top-30%-overlooked admin1 areas (from `gold_subnational_index`), the
# MAGIC distinct-country constraint, a region label heuristic, and the combined
# MAGIC score.
# MAGIC
# MAGIC **What is STUBBED (the load-bearing piece — needs work before deploy):**
# MAGIC - **`shares_boundary`**: true adjacency needs a Sedona `ST_Touches` /
# MAGIC   `ST_Intersects` self-join of `silver_boundaries` admin1 geometries (or a
# MAGIC   precomputed adjacency table). Here it is set to NULL and **every pair is
# MAGIC   emitted as a candidate**; without the adjacency filter this is a
# MAGIC   cross-product of top-overlooked admin1 areas across different countries,
# MAGIC   intended only as scaffolding. TODO marked inline.

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql import Window

# region heuristic: ISO3 → regional label for the four named corridors.
REGION_MAP = {
    "BFA": "Sahel", "MLI": "Sahel", "NER": "Sahel", "TCD": "Lake Chad", "MRT": "Sahel",
    "NGA": "Lake Chad", "CMR": "Lake Chad",
    "SDN": "Horn", "SSD": "Horn", "ETH": "Horn", "SOM": "Horn", "ERI": "Horn", "KEN": "Horn",
    "GTM": "N. Central America", "HND": "N. Central America", "SLV": "N. Central America",
}

# COMMAND ----------

sub = spark.table(gold("gold_subnational_index")).where("admin1_overlooked_score IS NOT NULL")

# top-30% overlooked admin1 areas within year
w_year = Window.partitionBy("year")
top = (
    sub
    .withColumn("_pct", F.percent_rank().over(w_year.orderBy(F.col("admin1_overlooked_score"))))
    .where("_pct >= 0.70")
    .select(
        "year",
        F.col("iso3").alias("iso3_a"),
        F.col("admin1_pcode").alias("admin1_pcode_a"),
        F.col("admin1_overlooked_score").alias("score_a"),
    )
)
top_b = top.select(
    "year",
    F.col("iso3_a").alias("iso3_b"),
    F.col("admin1_pcode_a").alias("admin1_pcode_b"),
    F.col("score_a").alias("score_b"),
)

region_expr = F.create_map(*sum(([F.lit(k), F.lit(v)] for k, v in REGION_MAP.items()), []))

pairs = (
    top.join(top_b, "year")
    # distinct countries; canonical ordering to avoid (A,B)+(B,A) dupes
    .where("iso3_a < iso3_b")
    .withColumn("shares_boundary", F.lit(None).cast("boolean"))  # TODO(Day-4): Sedona ST_Touches
    .withColumn("both_top_30pct", F.lit(True))
    .withColumn("combined_overlooked_score", F.col("score_a") + F.col("score_b"))
    .withColumn(
        "region_label",
        F.when(region_expr[F.col("iso3_a")] == region_expr[F.col("iso3_b")],
               region_expr[F.col("iso3_a")]),
    )
    .select(
        "admin1_pcode_a", "admin1_pcode_b", "iso3_a", "iso3_b",
        "shares_boundary", "both_top_30pct", "region_label",
        "combined_overlooked_score", "year",
    )
)

assert_expectations(
    pairs,
    [("fail:distinct_countries", "iso3_a <> iso3_b"),
     ("warn:adjacency_stubbed", "shares_boundary IS NULL")],  # expected until Sedona join lands
    "gold_cross_border_patterns",
)
(pairs.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(gold("gold_cross_border_patterns")))
