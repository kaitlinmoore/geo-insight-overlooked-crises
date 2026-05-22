# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: `gold_cross_border_patterns`
# MAGIC
# MAGIC Regional / cross-border structure that country-level ranks hide — the
# MAGIC "regional structural neglect" beat on the methodology slide. For every
# MAGIC country×year in `gold_forgotten_crisis_index`, this summarizes how
# MAGIC overlooked its **land neighbours** are and tags membership in a small set
# MAGIC of known regional crisis clusters.
# MAGIC
# MAGIC **Serverless adaptation.** The previous draft stubbed adjacency on a Sedona
# MAGIC `ST_Touches` polygon self-join (deferred — serverless compute can't install
# MAGIC the Sedona JVM library; see `DECISIONS.md` serverless entry). Adjacency now
# MAGIC comes from `bronze_country_borders` (GeoNames `countryInfo.txt`, CC-BY) at
# MAGIC **country grain** — coarser than admin1 polygons, but portable and
# MAGIC sufficient for the regional-pattern view.
# MAGIC
# MAGIC **Sources**: `geo_insight.bronze.bronze_country_borders` +
# MAGIC `geo_insight.gold.gold_forgotten_crisis_index`.
# MAGIC **Grain / PK**: (`iso3`, `year`).
# MAGIC
# MAGIC **Neighbour aggregates** are computed by exploding `neighbor_iso3_list` and
# MAGIC joining back to the index for the **same year** (only neighbours that
# MAGIC themselves appear in the index that year count). Countries with no ranked
# MAGIC neighbours get `n_neighbors_ranked = 0` and null neighbour-score aggregates.
# MAGIC
# MAGIC **Cluster labels are illustrative starting groupings**, hardcoded for the v1
# MAGIC demo and the methodology slide — not computed. A future v2 could derive
# MAGIC clusters dynamically (e.g. spectral clustering on the GeoNames adjacency
# MAGIC matrix), but the hardcoded labels handle the demo case deterministically.
# MAGIC `NER` and `TCD` sit in two listed corridors each (Sahel **and** Lake Chad);
# MAGIC the precedence below is **first-listed-wins**, so each country resolves to
# MAGIC exactly one `cluster_label` (NER, TCD → `sahel_g5`).

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql import Window

# Known regional crisis clusters (illustrative; hardcoded for the v1 demo).
# Order matters: a country in two corridors resolves to the FIRST one listed
# (NER, TCD ∈ sahel_g5 AND lake_chad → assigned sahel_g5).
CLUSTER_DEFS = [
    ("sahel_g5",            ["BFA", "MLI", "NER", "TCD", "MRT"]),
    ("horn_of_africa",      ["ETH", "ERI", "SOM", "SSD", "SDN"]),
    ("lake_chad",           ["NGA", "NER", "CMR", "TCD"]),
    ("andean_displacement", ["VEN", "COL", "ECU", "PER", "BRA"]),
    ("levant_displaced",    ["SYR", "LBN", "JOR", "TUR", "IRQ"]),
]

# Flatten to a single iso3 → cluster_label lookup with first-listed-wins.
COUNTRY_TO_CLUSTER: dict[str, str] = {}
for _label, _members in CLUSTER_DEFS:
    for _c in _members:
        COUNTRY_TO_CLUSTER.setdefault(_c, _label)

# COMMAND ----------

idx = (
    spark.table(gold("gold_forgotten_crisis_index"))
    .select("iso3", "year", "country_name", "overlooked_score", "rank_position")
)
borders = (
    spark.table(bronze("bronze_country_borders"))
    .select("iso3", "neighbor_iso3_list")
)

# Index left-joined to borders on iso3 (borders is year-invariant). Index rows
# whose iso3 isn't in the borders table keep a null neighbor_iso3_list.
base = idx.join(borders, "iso3", "left")

# COMMAND ----------

# Explode the comma-separated neighbour list → one row per (iso3, year, neighbor).
# Countries with an empty/null list explode to zero rows (they drop out here and
# pick up null aggregates on the left join back below).
exploded = (
    base
    .withColumn(
        "neighbor_iso3",
        F.explode(
            F.when(
                F.col("neighbor_iso3_list").isNotNull()
                & (F.length(F.trim(F.col("neighbor_iso3_list"))) > 0),
                F.split(F.col("neighbor_iso3_list"), ","),
            ).otherwise(F.array().cast("array<string>"))
        ),
    )
    .withColumn("neighbor_iso3", F.upper(F.trim(F.col("neighbor_iso3"))))
    .select("iso3", "year", "neighbor_iso3")
)

# Join each neighbour back to the index for the SAME year — only neighbours that
# are themselves ranked that year contribute to the aggregates.
idx_neighbor = idx.select(
    F.col("iso3").alias("neighbor_iso3"),
    F.col("year"),
    F.col("overlooked_score").alias("_n_score"),
    F.col("rank_position").alias("_n_rank"),
)
neighbor_agg = (
    exploded.join(idx_neighbor, ["neighbor_iso3", "year"], "inner")
    .groupBy("iso3", "year")
    .agg(
        F.count(F.lit(1)).alias("n_neighbors_ranked"),
        F.avg("_n_score").alias("neighbor_mean_overlooked_score"),
        F.max("_n_score").alias("neighbor_max_overlooked_score"),
        F.min("_n_rank").alias("neighbor_top_rank"),  # best = lowest rank number
    )
)

# COMMAND ----------

cluster_expr = F.create_map(
    *sum(([F.lit(k), F.lit(v)] for k, v in COUNTRY_TO_CLUSTER.items()), [])
)

enriched = (
    base
    .join(neighbor_agg, ["iso3", "year"], "left")
    .withColumn("n_neighbors_ranked", F.coalesce(F.col("n_neighbors_ranked"), F.lit(0)))
    .withColumn("cluster_label", cluster_expr[F.col("iso3")])
)

# is_regional_cluster_peak: highest overlooked_score among ranked members of the
# same cluster_label within the year. Computed only where cluster_label is set.
peak_win = Window.partitionBy("cluster_label", "year")
enriched = (
    enriched
    .withColumn(
        "_cluster_max_score",
        F.when(F.col("cluster_label").isNotNull(),
               F.max("overlooked_score").over(peak_win)),
    )
    .withColumn(
        "is_regional_cluster_peak",
        F.when(
            F.col("cluster_label").isNotNull()
            & F.col("overlooked_score").isNotNull(),
            F.col("overlooked_score") == F.col("_cluster_max_score"),
        ).otherwise(F.lit(False)),
    )
)

out = enriched.select(
    "iso3",
    "year",
    "country_name",
    "neighbor_iso3_list",
    "n_neighbors_ranked",
    "neighbor_mean_overlooked_score",
    "neighbor_max_overlooked_score",
    "neighbor_top_rank",
    "cluster_label",
    "is_regional_cluster_peak",
)

# COMMAND ----------

assert_expectations(
    out,
    [("fail:n_neighbors_ranked_nonneg", "n_neighbors_ranked >= 0"),
     ("warn:peak_requires_cluster", "is_regional_cluster_peak = false OR cluster_label IS NOT NULL")],
    "gold_cross_border_patterns",
)
(out.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(gold("gold_cross_border_patterns")))
