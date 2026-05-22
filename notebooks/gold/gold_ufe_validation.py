# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: `gold_ufe_validation` — country × year × round
# MAGIC
# MAGIC Validation Layer 1: our ranking vs CERF Underfunded-Emergencies selections
# MAGIC as labeled ground truth (`methodology.md` §Validation). Substrate for
# MAGIC `compare_to_ufe`. Reports precision/recall at K=15 on the held-out window.
# MAGIC
# MAGIC - **prediction** = `gold_forgotten_crisis_index.rank_position` (top-K with
# MAGIC   K=15).
# MAGIC - **truth** = `silver_ufe_label.ufe_selected`.
# MAGIC - `evaluation_window` = `holdout` for 2024–2025 rounds, else `train`.
# MAGIC
# MAGIC **⚠️ Point-in-time caveat.** A leakage-free evaluation recomputes the rank
# MAGIC using only data available *before* each round. v1 ships a **year-grain**
# MAGIC comparison against the current index (the index is itself year-versioned),
# MAGIC which is an approximation — the round-grain, strictly point-in-time path is
# MAGIC roadmap (`open-questions.md`). Flagged for the user.

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

from pyspark.sql import functions as F

K = 15

# COMMAND ----------

pred = (
    spark.table(gold("gold_forgotten_crisis_index"))
    .select("iso3", "year", "rank_position")
    .withColumn("predicted_top_k", F.col("rank_position") <= K)
)

label = (
    spark.table(silver("silver_ufe_label"))
    .select("iso3", "year", "round",
            F.coalesce(F.col("ufe_selected"), F.lit(False)).alias("ufe_selected"))
)

# Full outer join over (iso3, year): keeps top-K predictions that were not
# UFE-selected (FP) and UFE-selected countries we didn't rank top-K (FN).
joined = (
    pred.join(label, ["iso3", "year"], "outer")
    .withColumn("predicted_top_k", F.coalesce(F.col("predicted_top_k"), F.lit(False)))
    .withColumn("ufe_selected", F.coalesce(F.col("ufe_selected"), F.lit(False)))
)

validation = (
    joined
    .withColumn("is_true_positive", F.col("predicted_top_k") & F.col("ufe_selected"))
    .withColumn("is_false_positive", F.col("predicted_top_k") & ~F.col("ufe_selected"))
    .withColumn("is_false_negative", ~F.col("predicted_top_k") & F.col("ufe_selected"))
    .withColumn(
        "evaluation_window",
        F.when(F.col("year").isin(2024, 2025), F.lit("holdout")).otherwise(F.lit("train")),
    )
    .select(
        "iso3", "year", "round",
        F.col("rank_position").alias("predicted_rank"),
        "predicted_top_k", "ufe_selected",
        "is_true_positive", "is_false_positive", "is_false_negative",
        "evaluation_window",
    )
)

assert_expectations(
    validation,
    [
        ("warn:label_present_or_prediction",
         "ufe_selected IS NOT NULL OR predicted_rank IS NOT NULL"),
        ("fail:window_in_set", "evaluation_window IN ('train','holdout')"),
    ],
    "gold_ufe_validation",
)
(validation.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(gold("gold_ufe_validation")))
