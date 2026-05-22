# Databricks notebook source
# MAGIC %md
# MAGIC # Agent: register Unity Catalog Functions
# MAGIC
# MAGIC Registers the 11 UC Functions in `geo_insight.agent` that back the Mosaic
# MAGIC AI supervisor agent's tool calls. Re-runnable (`CREATE OR REPLACE`).
# MAGIC
# MAGIC **Tool inventory (see `notebooks/agent/README.md` for the full table):**
# MAGIC
# MAGIC 1. `get_country_ranking(iso3, year)` — headline ranking + CI + class
# MAGIC 2. `list_top_overlooked(year, limit_n, region)` — top-N triage
# MAGIC 3. `get_funding_funnel(iso3, year)` — required → pledged → committed → paid
# MAGIC 4. `get_sector_coverage(iso3, year, only_flagged)` — per-sector gap
# MAGIC 5. `get_funding_trend(iso3, start_year, end_year)` — multi-year gap + class
# MAGIC 6. `get_score_decomposition(iso3, year)` — 7-component composite breakdown
# MAGIC 7. `get_donor_concentration(iso3, year)` — per-donor share + HHI + top-3
# MAGIC 8. `compare_countries(iso3_csv, year)` — aligned metrics for 2–4 countries
# MAGIC 9. `get_ranking_delta(iso3, from_year, to_year)` — year-over-year rank move
# MAGIC 10. `get_regional_cluster(iso3, year)` — neighbour aggregates + cluster label
# MAGIC 11. `get_subnational_breakdown(iso3, year)` — admin1 rows where available
# MAGIC
# MAGIC **Required upstream tables** (must exist + be populated before running):
# MAGIC `geo_insight.gold.gold_forgotten_crisis_index`,
# MAGIC `gold_funding_funnel`, `gold_sector_coverage`, `gold_funding_trend`,
# MAGIC `gold_donor_concentration`, `gold_explanation_features`,
# MAGIC `gold_change_indicators`, `gold_cross_border_patterns`,
# MAGIC `gold_subnational_index`,
# MAGIC plus `geo_insight.silver.silver_country_dim`, `silver_needs`,
# MAGIC `silver_fts_flows`.
# MAGIC
# MAGIC **Docstring discipline.** The `COMMENT` strings drive supervisor tool
# MAGIC selection. Each one names the user-facing question type the tool answers,
# MAGIC gives one or two example phrasings, and calls out the bounds + caveats so
# MAGIC the agent doesn't misuse the result. Edit COMMENTs deliberately — they are
# MAGIC the spec the LLM reads.

# COMMAND ----------

spark.sql("CREATE SCHEMA IF NOT EXISTS geo_insight.agent")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. `get_country_ranking(iso3, year)`
# MAGIC
# MAGIC Headline ranking + bootstrap CI + neglect class for one country-year.
# MAGIC Joins `silver_needs` for `pin_total_country` (not stored on the index).

# COMMAND ----------

spark.sql("""
CREATE OR REPLACE FUNCTION geo_insight.agent.get_country_ranking(
  iso3 STRING COMMENT 'ISO 3166-1 alpha-3 country code (e.g. SDN, YEM, COD)',
  year INT COMMENT 'Year of analysis (e.g. 2026)'
)
RETURNS TABLE (
  iso3 STRING,
  country_name STRING,
  year INT,
  rank_position INT,
  rank_ci_low INT,
  rank_ci_high INT,
  stable_top_n BOOLEAN,
  overlooked_score DOUBLE,
  neglect_class STRING,
  gap_ratio DOUBLE,
  severity_rate DOUBLE,
  pin_total_country BIGINT,
  data_sparsity_flag BOOLEAN
)
COMMENT 'Returns the overlooked-crisis rank position, 95% bootstrap confidence interval, and neglect classification for a single country in a given year. Use this when a user asks about a specific country — for example, "where does Sudan rank?" or "is Yemen still overlooked?". The rank is the headline; the CI shows how stable it is across weight perturbations. Always pair the rank with the CI when answering; never report rank as a single integer.'
RETURN
  SELECT
    fci.iso3,
    fci.country_name,
    fci.year,
    fci.rank_position,
    fci.rank_ci_low,
    fci.rank_ci_high,
    fci.stable_top_n,
    fci.overlooked_score,
    fci.neglect_class,
    fci.gap_ratio,
    fci.severity_rate,
    n.pin_total_country,
    fci.data_sparsity_flag
  FROM geo_insight.gold.gold_forgotten_crisis_index AS fci
  LEFT JOIN (
    SELECT iso3, year, MAX(pin_total_country) AS pin_total_country
    FROM geo_insight.silver.silver_needs
    WHERE cluster = 'ALL'
    GROUP BY iso3, year
  ) AS n
    ON fci.iso3 = n.iso3 AND fci.year = n.year
  WHERE fci.iso3 = get_country_ranking.iso3
    AND fci.year = get_country_ranking.year
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. `list_top_overlooked(year, limit_n, region)`
# MAGIC
# MAGIC The Triage workhorse. Joins `silver_country_dim` for the `region` column
# MAGIC (gold_forgotten_crisis_index doesn't carry it). `region` parameter is NULL
# MAGIC by default → return all regions.

# COMMAND ----------

spark.sql("""
CREATE OR REPLACE FUNCTION geo_insight.agent.list_top_overlooked(
  year INT COMMENT 'Year of analysis (e.g. 2026)',
  limit_n INT DEFAULT 15 COMMENT 'Number of rows to return (default 15, matching the K=15 validation framework)',
  region STRING DEFAULT NULL COMMENT 'Optional OCHA region filter, e.g. sub_saharan_africa, middle_east_north_africa, latin_america_caribbean. NULL = global.'
)
RETURNS TABLE (
  iso3 STRING,
  country_name STRING,
  region STRING,
  year INT,
  rank_position INT,
  rank_ci_low INT,
  rank_ci_high INT,
  stable_top_n BOOLEAN,
  overlooked_score DOUBLE,
  neglect_class STRING,
  gap_ratio DOUBLE
)
COMMENT 'Returns the top-N most overlooked crises for a given year, optionally filtered to a region (e.g. sub_saharan_africa, middle_east_north_africa). Use this for the headline triage question — "what are the most overlooked crises right now?" — and for region-scoped variants like "which African crises are most underfunded?". Default limit is 15 (matches the K=15 validation framework). Always present results with their bootstrap CIs; flag rows where stable_top_n is false as "less stable across weight choices".'
RETURN
  SELECT
    fci.iso3,
    fci.country_name,
    cd.region,
    fci.year,
    fci.rank_position,
    fci.rank_ci_low,
    fci.rank_ci_high,
    fci.stable_top_n,
    fci.overlooked_score,
    fci.neglect_class,
    fci.gap_ratio
  FROM geo_insight.gold.gold_forgotten_crisis_index AS fci
  LEFT JOIN geo_insight.silver.silver_country_dim AS cd
    ON fci.iso3 = cd.iso3
  WHERE fci.year = list_top_overlooked.year
    AND (list_top_overlooked.region IS NULL OR cd.region = list_top_overlooked.region)
  ORDER BY fci.rank_position ASC
  LIMIT list_top_overlooked.limit_n
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. `get_funding_funnel(iso3, year)`
# MAGIC
# MAGIC Four-row long form (`required` / `pledged` / `committed` / `paid`).

# COMMAND ----------

spark.sql("""
CREATE OR REPLACE FUNCTION geo_insight.agent.get_funding_funnel(
  iso3 STRING COMMENT 'ISO 3166-1 alpha-3 country code',
  year INT COMMENT 'Year of analysis'
)
RETURNS TABLE (
  iso3 STRING,
  year INT,
  stage STRING,
  amount_usd DOUBLE,
  pct_of_requirement DOUBLE
)
COMMENT 'Returns the four-stage funding funnel (required → pledged → committed → paid) for a country and year, with the percentage of the requirement reached at each stage. Use this when a user asks about funding gaps in detail — "how much of Yemens requirement was actually paid?" — or wants to understand commitment vs. payment lag. Returns four rows (one per stage); the headline gap_ratio in get_country_ranking is computed from required vs. paid.'
RETURN
  SELECT
    iso3,
    year,
    stage,
    amount_usd,
    pct_of_requirement
  FROM geo_insight.gold.gold_funding_funnel
  WHERE iso3 = get_funding_funnel.iso3
    AND year = get_funding_funnel.year
  ORDER BY
    CASE stage
      WHEN 'required'  THEN 1
      WHEN 'pledged'   THEN 2
      WHEN 'committed' THEN 3
      WHEN 'paid'      THEN 4
      ELSE 5
    END
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. `get_sector_coverage(iso3, year, only_flagged)`
# MAGIC
# MAGIC Gold table column is `sector` (renamed from `harmonized_sector` in the Gold
# MAGIC notebook); aliased back to `harmonized_sector` here for the agent surface.

# COMMAND ----------

spark.sql("""
CREATE OR REPLACE FUNCTION geo_insight.agent.get_sector_coverage(
  iso3 STRING COMMENT 'ISO 3166-1 alpha-3 country code',
  year INT COMMENT 'Year of analysis',
  only_flagged BOOLEAN DEFAULT FALSE COMMENT 'If TRUE, return only critically underfunded sectors (gap > 70% AND PIN share >= 10%)'
)
RETURNS TABLE (
  iso3 STRING,
  year INT,
  harmonized_sector STRING,
  requirement_usd DOUBLE,
  fts_funding_usd DOUBLE,
  cbpf_funding_usd DOUBLE,
  sector_gap DOUBLE,
  pin_share DOUBLE,
  cbpf_funding_share DOUBLE,
  is_flagged_gap BOOLEAN
)
COMMENT 'Returns per-sector funding coverage for a country and year. Each row shows the harmonized IASC sector (Health, Food Security, Protection, WASH, etc.), the FTS bilateral donor funding, the CBPF pooled-fund funding, the sector gap as a fraction of requirement, the sector PIN share, and a flag for critically underfunded sectors (gap > 70% AND PIN share >= 10%). Use this when a user asks about sector-specific gaps — "is health funded in DRC?" or "where is protection getting cut?". Set only_flagged=TRUE to return only the critically underfunded sectors.'
RETURN
  SELECT
    iso3,
    year,
    sector AS harmonized_sector,
    requirement_usd,
    fts_funding_usd,
    cbpf_funding_usd,
    sector_gap,
    pin_share,
    cbpf_funding_share,
    is_flagged_gap
  FROM geo_insight.gold.gold_sector_coverage
  WHERE iso3 = get_sector_coverage.iso3
    AND year = get_sector_coverage.year
    AND (get_sector_coverage.only_flagged = FALSE OR is_flagged_gap = TRUE)
  ORDER BY sector_gap DESC NULLS LAST
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. `get_funding_trend(iso3, start_year, end_year)`
# MAGIC
# MAGIC `gold_funding_trend` carries `gap_ratio`, `chronic_index`, `neglect_class`
# MAGIC but NOT `funded_paid_usd` / `requirement_usd` — those are pivoted onto
# MAGIC `gold_funding_funnel` (`paid` and `required` stages). Joined here so the
# MAGIC agent can quote dollar totals alongside the trend classification.

# COMMAND ----------

spark.sql("""
CREATE OR REPLACE FUNCTION geo_insight.agent.get_funding_trend(
  iso3 STRING COMMENT 'ISO 3166-1 alpha-3 country code',
  start_year INT COMMENT 'First year in the requested window (inclusive)',
  end_year INT COMMENT 'Last year in the requested window (inclusive)'
)
RETURNS TABLE (
  iso3 STRING,
  year INT,
  funded_paid_usd DOUBLE,
  requirement_usd DOUBLE,
  gap_ratio DOUBLE,
  chronic_index DOUBLE,
  neglect_class STRING
)
COMMENT 'Returns the multi-year funding trend for a country, one row per year in the requested range, with the gap ratio, chronic index, and year-by-year neglect classification. Use this for chronic-vs-acute questions — "has Yemen always been this underfunded?" or "when did Sudans gap start widening?". The trend lets users see whether a crisis is structurally neglected (chronic) or recently deteriorating (acute). A useful default range is the last 5 years (start_year = current_year - 4, end_year = current_year).'
RETURN
  SELECT
    t.iso3,
    t.year,
    paid.amount_usd AS funded_paid_usd,
    req.amount_usd AS requirement_usd,
    t.gap_ratio,
    t.chronic_index,
    t.neglect_class
  FROM geo_insight.gold.gold_funding_trend AS t
  LEFT JOIN geo_insight.gold.gold_funding_funnel AS paid
    ON t.iso3 = paid.iso3 AND t.year = paid.year AND paid.stage = 'paid'
  LEFT JOIN geo_insight.gold.gold_funding_funnel AS req
    ON t.iso3 = req.iso3 AND t.year = req.year AND req.stage = 'required'
  WHERE t.iso3 = get_funding_trend.iso3
    AND t.year BETWEEN get_funding_trend.start_year AND get_funding_trend.end_year
  ORDER BY t.year ASC
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. `get_score_decomposition(iso3, year)`
# MAGIC
# MAGIC `gold_explanation_features` stores the components wide (one row per
# MAGIC country×year, seven `*_norm` / `weight_*` / `contribution_*` triples).
# MAGIC Pivoted to long here so the agent can iterate components without
# MAGIC reasoning about column lists.
# MAGIC
# MAGIC The stored `weight_*` columns carry the sign (so `weight_media_attention`
# MAGIC is negative). We split: `weight` returned as the **absolute magnitude**,
# MAGIC `sign` returned as +1 / -1 — easier for the agent to format ("weight 0.10
# MAGIC applied negatively").

# COMMAND ----------

spark.sql("""
CREATE OR REPLACE FUNCTION geo_insight.agent.get_score_decomposition(
  iso3 STRING COMMENT 'ISO 3166-1 alpha-3 country code',
  year INT COMMENT 'Year of analysis'
)
RETURNS TABLE (
  iso3 STRING,
  year INT,
  component STRING,
  raw_value DOUBLE,
  percentile_norm DOUBLE,
  weight DOUBLE,
  contribution DOUBLE,
  sign INT
)
COMMENT 'Returns the seven-component decomposition of a countrys overlooked score: gap_ratio, severity_rate, dollars_per_pin_inv, chronic_index, sector_imbalance, media_attention (applied with a negative sign), and geographic_isolation (applied as an interaction with severity_rate). Each row shows the raw value, the within-year percentile rank, the absolute weight magnitude, the contribution to the composite (signed), and the sign (+1 or -1). Use this when a user asks "why does this country rank where it does?" — the decomposition is the explainability backbone. The contributions sum to the overlooked_score by construction (self-check enforced at Gold build time).'
RETURN
  SELECT iso3, year, 'gap_ratio'            AS component, gap_ratio                AS raw_value, gap_ratio_norm                 AS percentile_norm, ABS(weight_gap_ratio)            AS weight, contribution_gap_ratio            AS contribution, CAST(SIGN(weight_gap_ratio)            AS INT) AS sign
  FROM geo_insight.gold.gold_explanation_features
  WHERE iso3 = get_score_decomposition.iso3 AND year = get_score_decomposition.year
  UNION ALL
  SELECT iso3, year, 'severity_rate'        AS component, severity_rate            AS raw_value, severity_rate_norm             AS percentile_norm, ABS(weight_severity_rate)        AS weight, contribution_severity_rate        AS contribution, CAST(SIGN(weight_severity_rate)        AS INT) AS sign
  FROM geo_insight.gold.gold_explanation_features
  WHERE iso3 = get_score_decomposition.iso3 AND year = get_score_decomposition.year
  UNION ALL
  SELECT iso3, year, 'dollars_per_pin_inv'  AS component, dollars_per_pin          AS raw_value, dollars_per_pin_inv_norm       AS percentile_norm, ABS(weight_dollars_per_pin_inv)  AS weight, contribution_dollars_per_pin_inv  AS contribution, CAST(SIGN(weight_dollars_per_pin_inv)  AS INT) AS sign
  FROM geo_insight.gold.gold_explanation_features
  WHERE iso3 = get_score_decomposition.iso3 AND year = get_score_decomposition.year
  UNION ALL
  SELECT iso3, year, 'chronic_index'        AS component, chronic_index            AS raw_value, chronic_index_norm             AS percentile_norm, ABS(weight_chronic_index)        AS weight, contribution_chronic_index        AS contribution, CAST(SIGN(weight_chronic_index)        AS INT) AS sign
  FROM geo_insight.gold.gold_explanation_features
  WHERE iso3 = get_score_decomposition.iso3 AND year = get_score_decomposition.year
  UNION ALL
  SELECT iso3, year, 'sector_imbalance'     AS component, sector_imbalance         AS raw_value, sector_imbalance_norm          AS percentile_norm, ABS(weight_sector_imbalance)     AS weight, contribution_sector_imbalance     AS contribution, CAST(SIGN(weight_sector_imbalance)     AS INT) AS sign
  FROM geo_insight.gold.gold_explanation_features
  WHERE iso3 = get_score_decomposition.iso3 AND year = get_score_decomposition.year
  UNION ALL
  SELECT iso3, year, 'media_attention'      AS component, media_attention_norm     AS raw_value, media_attention_n              AS percentile_norm, ABS(weight_media_attention)      AS weight, contribution_media_attention      AS contribution, CAST(SIGN(weight_media_attention)      AS INT) AS sign
  FROM geo_insight.gold.gold_explanation_features
  WHERE iso3 = get_score_decomposition.iso3 AND year = get_score_decomposition.year
  UNION ALL
  SELECT iso3, year, 'geographic_isolation' AS component, geographic_isolation     AS raw_value, geographic_isolation_norm      AS percentile_norm, ABS(weight_geographic_isolation) AS weight, contribution_geographic_isolation AS contribution, CAST(SIGN(weight_geographic_isolation) AS INT) AS sign
  FROM geo_insight.gold.gold_explanation_features
  WHERE iso3 = get_score_decomposition.iso3 AND year = get_score_decomposition.year
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. `get_donor_concentration(iso3, year)`
# MAGIC
# MAGIC `gold_donor_concentration` is country-aggregate (one row per `iso3, year`
# MAGIC carrying `hhi`, `top1_share`, `top3_share`). The per-donor breakdown lives
# MAGIC in `silver_fts_flows` — recomputed here with window functions and joined
# MAGIC back to the aggregate so every row carries the country-level `top3_share`
# MAGIC and `donor_hhi` for context.

# COMMAND ----------

spark.sql("""
CREATE OR REPLACE FUNCTION geo_insight.agent.get_donor_concentration(
  iso3 STRING COMMENT 'ISO 3166-1 alpha-3 country code',
  year INT COMMENT 'Year of analysis'
)
RETURNS TABLE (
  iso3 STRING,
  year INT,
  donor_org STRING,
  paid_usd DOUBLE,
  donor_share DOUBLE,
  donor_rank INT,
  top3_share DOUBLE,
  donor_hhi DOUBLE
)
COMMENT 'Returns the donor concentration breakdown for a countrys funding in a given year. Shows the top donors, each ones share of total paid funding, their rank, the country-level top-3 concentration, and the Herfindahl-Hirschman Index. Use this when a user asks about funding diversification — "who is funding Yemen?" or "is this crisis dependent on a single donor?". High top-3 share or high HHI signals donor fragility, which is itself an overlooked-ness risk factor (a crisis dependent on one donor is at risk if that donor pulls back). Uses FTS donor identity (CBPF contributions are unattributable at country level).'
RETURN
  WITH per_donor AS (
    SELECT
      iso3,
      YEAR(flow_date) AS year,
      COALESCE(donor_org, 'Unknown') AS donor_org,
      SUM(amount_usd) AS paid_usd
    FROM geo_insight.silver.silver_fts_flows
    WHERE status = 'paid'
      AND allocation_method <> 'pending_attribution'
      AND iso3 IS NOT NULL
    GROUP BY iso3, YEAR(flow_date), COALESCE(donor_org, 'Unknown')
  ),
  ranked AS (
    SELECT
      iso3,
      year,
      donor_org,
      paid_usd,
      paid_usd / SUM(paid_usd) OVER (PARTITION BY iso3, year) AS donor_share,
      CAST(
        ROW_NUMBER() OVER (PARTITION BY iso3, year ORDER BY paid_usd DESC)
        AS INT
      ) AS donor_rank
    FROM per_donor
    WHERE paid_usd > 0
  )
  SELECT
    r.iso3,
    r.year,
    r.donor_org,
    r.paid_usd,
    r.donor_share,
    r.donor_rank,
    c.top3_share,
    c.hhi AS donor_hhi
  FROM ranked AS r
  LEFT JOIN geo_insight.gold.gold_donor_concentration AS c
    ON r.iso3 = c.iso3 AND r.year = c.year
  WHERE r.iso3 = get_donor_concentration.iso3
    AND r.year = get_donor_concentration.year
  ORDER BY r.donor_rank ASC
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. `compare_countries(iso3_csv, year)`
# MAGIC
# MAGIC Comma-separated ISO3 list (e.g. `"SDN,BFA,YEM"`) → one row per country.
# MAGIC `has_subnational` is derived via EXISTS against `gold_subnational_index`
# MAGIC (not stored on the index itself).
# MAGIC
# MAGIC See the report on this notebook for the trade-off vs. `ARRAY<STRING>`.

# COMMAND ----------

spark.sql("""
CREATE OR REPLACE FUNCTION geo_insight.agent.compare_countries(
  iso3_csv STRING COMMENT 'Comma-separated ISO 3166-1 alpha-3 codes, e.g. "SDN,BFA,YEM". Whitespace tolerated; case-insensitive.',
  year INT COMMENT 'Year of analysis'
)
RETURNS TABLE (
  iso3 STRING,
  country_name STRING,
  year INT,
  rank_position INT,
  rank_ci_low INT,
  rank_ci_high INT,
  neglect_class STRING,
  overlooked_score DOUBLE,
  gap_ratio DOUBLE,
  severity_rate DOUBLE,
  chronic_index DOUBLE,
  pin_total_country BIGINT,
  has_subnational BOOLEAN
)
COMMENT 'Returns aligned ranking and component metrics for multiple countries in a single year, useful for side-by-side comparison. Pass a comma-separated list of ISO3 codes — for example, "SDN,BFA,YEM" to compare Sudan, Burkina Faso, and Yemen. Returns one row per country with the same metric set as get_country_ranking, plus a chronic_index column and a has_subnational flag. Use this for explicit comparison questions — "how does Sudan compare to Yemen?" — and as the data source for the Compare screen.'
RETURN
  WITH wanted AS (
    SELECT UPPER(TRIM(c)) AS iso3
    FROM (
      SELECT EXPLODE(SPLIT(compare_countries.iso3_csv, ',')) AS c
    )
    WHERE TRIM(c) <> ''
  ),
  needs AS (
    SELECT iso3, year, MAX(pin_total_country) AS pin_total_country
    FROM geo_insight.silver.silver_needs
    WHERE cluster = 'ALL'
    GROUP BY iso3, year
  ),
  sub AS (
    SELECT DISTINCT iso3, year FROM geo_insight.gold.gold_subnational_index
  )
  SELECT
    fci.iso3,
    fci.country_name,
    fci.year,
    fci.rank_position,
    fci.rank_ci_low,
    fci.rank_ci_high,
    fci.neglect_class,
    fci.overlooked_score,
    fci.gap_ratio,
    fci.severity_rate,
    fci.chronic_index,
    n.pin_total_country,
    sub.iso3 IS NOT NULL AS has_subnational
  FROM geo_insight.gold.gold_forgotten_crisis_index AS fci
  INNER JOIN wanted AS w ON fci.iso3 = w.iso3
  LEFT JOIN needs AS n ON fci.iso3 = n.iso3 AND fci.year = n.year
  LEFT JOIN sub ON fci.iso3 = sub.iso3 AND fci.year = sub.year
  WHERE fci.year = compare_countries.year
  ORDER BY fci.rank_position ASC NULLS LAST
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. `get_ranking_delta(iso3, from_year, to_year)`
# MAGIC
# MAGIC `gold_change_indicators` stores only `rank_delta` + `direction` (period
# MAGIC grain = year as string). For the agent surface we want `rank_from`,
# MAGIC `rank_to`, `score_from`, `score_to`, signed score change and magnitude —
# MAGIC so we compute directly from a self-join of `gold_forgotten_crisis_index`.

# COMMAND ----------

spark.sql("""
CREATE OR REPLACE FUNCTION geo_insight.agent.get_ranking_delta(
  iso3 STRING COMMENT 'ISO 3166-1 alpha-3 country code',
  from_year INT COMMENT 'Earlier year (the baseline)',
  to_year INT COMMENT 'Later year (the comparison)'
)
RETURNS TABLE (
  iso3 STRING,
  from_year INT,
  to_year INT,
  rank_from INT,
  rank_to INT,
  rank_change INT,
  overlooked_score_from DOUBLE,
  overlooked_score_to DOUBLE,
  score_change DOUBLE,
  change_direction STRING,
  change_magnitude INT
)
COMMENT 'Returns the year-over-year ranking change for a country — how many positions it moved and in which direction. Use this for change-watching questions — "is Burkina Faso getting more or less overlooked?" or "did Sudan move up the rankings since 2024?". POSITIVE rank_change means moving UP the rankings (i.e. toward rank 1, MORE overlooked); negative means moving down (less overlooked). change_direction is one of worsening / improving / new / dropped / stable. Pre-architected for future alert subscriptions — see DECISIONS.md.'
RETURN
  WITH a AS (
    SELECT iso3, year, rank_position, overlooked_score
    FROM geo_insight.gold.gold_forgotten_crisis_index
    WHERE iso3 = get_ranking_delta.iso3 AND year = get_ranking_delta.from_year
  ),
  b AS (
    SELECT iso3, year, rank_position, overlooked_score
    FROM geo_insight.gold.gold_forgotten_crisis_index
    WHERE iso3 = get_ranking_delta.iso3 AND year = get_ranking_delta.to_year
  )
  SELECT
    COALESCE(b.iso3, a.iso3) AS iso3,
    get_ranking_delta.from_year AS from_year,
    get_ranking_delta.to_year AS to_year,
    a.rank_position AS rank_from,
    b.rank_position AS rank_to,
    (a.rank_position - b.rank_position) AS rank_change,
    a.overlooked_score AS overlooked_score_from,
    b.overlooked_score AS overlooked_score_to,
    (b.overlooked_score - a.overlooked_score) AS score_change,
    CASE
      WHEN a.rank_position IS NULL AND b.rank_position IS NOT NULL THEN 'new'
      WHEN b.rank_position IS NULL AND a.rank_position IS NOT NULL THEN 'dropped'
      WHEN a.rank_position - b.rank_position > 0 THEN 'worsening'
      WHEN a.rank_position - b.rank_position < 0 THEN 'improving'
      ELSE 'stable'
    END AS change_direction,
    CAST(ABS(COALESCE(a.rank_position - b.rank_position, 0)) AS INT) AS change_magnitude
  FROM a FULL OUTER JOIN b ON a.iso3 = b.iso3
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 10. `get_regional_cluster(iso3, year)` — STRETCH
# MAGIC
# MAGIC Country-grain regional structure from `gold_cross_border_patterns` (rebuilt
# MAGIC at country grain when the Sedona admin1-polygon adjacency path was deferred
# MAGIC for serverless — see DECISIONS.md).

# COMMAND ----------

spark.sql("""
CREATE OR REPLACE FUNCTION geo_insight.agent.get_regional_cluster(
  iso3 STRING COMMENT 'ISO 3166-1 alpha-3 country code',
  year INT COMMENT 'Year of analysis'
)
RETURNS TABLE (
  iso3 STRING,
  year INT,
  country_name STRING,
  cluster_label STRING,
  neighbor_iso3_list STRING,
  n_neighbors_ranked INT,
  neighbor_mean_overlooked_score DOUBLE,
  neighbor_top_rank INT,
  is_regional_cluster_peak BOOLEAN
)
COMMENT 'Returns regional crisis cluster information for a country — which known regional pattern it belongs to (sahel_g5, horn_of_africa, lake_chad, andean_displacement, levant_displaced), how its ranked land neighbours score on average, the best (lowest-numbered) rank among those neighbours, and whether this country is the most-overlooked member of its cluster. Use this for regional questions — "is the Sahel crisis worse this year?" or "are Burkina Fasos neighbours also overlooked?". The regional view surfaces structural patterns that country-by-country ranking misses. cluster_label is null for countries outside the five hardcoded clusters; n_neighbors_ranked counts only neighbours that are themselves in gold_forgotten_crisis_index for the same year.'
RETURN
  SELECT
    iso3,
    year,
    country_name,
    cluster_label,
    neighbor_iso3_list,
    n_neighbors_ranked,
    neighbor_mean_overlooked_score,
    neighbor_top_rank,
    is_regional_cluster_peak
  FROM geo_insight.gold.gold_cross_border_patterns
  WHERE iso3 = get_regional_cluster.iso3
    AND year = get_regional_cluster.year
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 11. `get_subnational_breakdown(iso3, year)` — STRETCH
# MAGIC
# MAGIC One row per admin1 with PIN, inferred funding, and the simplified admin1
# MAGIC score. `gold_subnational_index` stores `pin_share` and
# MAGIC `admin1_inferred_funding`; renamed to `admin1_pin_share` /
# MAGIC `admin1_funding_inferred` on the agent surface for readability.

# COMMAND ----------

spark.sql("""
CREATE OR REPLACE FUNCTION geo_insight.agent.get_subnational_breakdown(
  iso3 STRING COMMENT 'ISO 3166-1 alpha-3 country code',
  year INT COMMENT 'Year of analysis'
)
RETURNS TABLE (
  iso3 STRING,
  year INT,
  admin1_pcode STRING,
  admin1_name STRING,
  admin1_pin BIGINT,
  admin1_pin_share DOUBLE,
  admin1_funding_inferred DOUBLE,
  admin1_overlooked_score DOUBLE,
  admin1_rank_in_country INT,
  is_inference_flagged BOOLEAN,
  data_sparsity_flag BOOLEAN
)
COMMENT 'Returns the admin1-level breakdown for a countrys overlooked-crisis assessment, when subnational data is available. Each row is one admin1 region with population in need, share of country PIN, inferred funding (PIN-proportional from country paid funding), and a simplified admin1 overlooked score. is_inference_flagged is always true (a reminder that admin1 funding is inferred, not observed). Use this when a user asks about subnational variation — "where in Sudan is the crisis worst?" or "are some regions of Yemen more underfunded than others?". IMPORTANT: returns empty for HNO 2026 (which dropped subnational columns) and for countries that lack machine-readable subnational data; in those cases the parent country carries data_sparsity_flag = true in gold_forgotten_crisis_index.'
RETURN
  SELECT
    iso3,
    year,
    admin1_pcode,
    admin1_name,
    admin1_pin,
    pin_share AS admin1_pin_share,
    admin1_inferred_funding AS admin1_funding_inferred,
    admin1_overlooked_score,
    admin1_rank_in_country,
    is_inference_flagged,
    data_sparsity_flag
  FROM geo_insight.gold.gold_subnational_index
  WHERE iso3 = get_subnational_breakdown.iso3
    AND year = get_subnational_breakdown.year
  ORDER BY admin1_rank_in_country ASC NULLS LAST
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verification: list all registered functions

# COMMAND ----------

display(spark.sql("SHOW FUNCTIONS IN geo_insight.agent"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Inspect each function's docstring
# MAGIC
# MAGIC Sanity-check pass before deploying the supervisor — the COMMENT strings
# MAGIC are what the LLM reads when it picks a tool. Print signature + COMMENT
# MAGIC for visual review.

# COMMAND ----------

for func_name in [
    "get_country_ranking",
    "list_top_overlooked",
    "get_funding_funnel",
    "get_sector_coverage",
    "get_funding_trend",
    "get_score_decomposition",
    "get_donor_concentration",
    "compare_countries",
    "get_ranking_delta",
    "get_regional_cluster",
    "get_subnational_breakdown",
]:
    print(f"\n=== {func_name} ===")
    display(spark.sql(f"DESCRIBE FUNCTION EXTENDED geo_insight.agent.{func_name}"))
