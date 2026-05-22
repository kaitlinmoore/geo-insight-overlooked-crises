# Databricks notebook source

# DEFERRED FROM V1 — see DECISIONS.md "Serverless deployment" entry.
#
# This notebook would have cleaned bronze_fieldmaps_boundaries into
# silver_boundaries: decoding the WKB geometry column to a geometry
# type, validating polygons (ST_IsValid), deriving centroids
# (ST_Centroid), deriving the contested_border_flag from
# status_cd / wld_notes, and precomputing admin1 adjacency for
# gold_cross_border_patterns. Every one of those steps depends on
# Apache Sedona ST_* functions.
#
# Sedona requires JVM library installation, which is unavailable on
# Databricks serverless compute. The v1 deployment uses serverless
# exclusively (trial workspace constraint). Its upstream Bronze loader
# (bronze_fieldmaps_boundaries) is deferred for the same reason.
#
# WHAT REPLACES IT:
# 1. Frontend choropleth maps: offline GeoJSON extraction via
#    src/acquisition/extract_geojson.py (operates directly on the
#    local GeoParquet; outputs simplified GeoJSON to
#    frontend/public/maps/).
# 2. Country adjacency for gold_cross_border_patterns: GeoNames
#    countryInfo.txt → bronze_country_borders (replaces the Sedona
#    admin1 polygon adjacency self-join).
# 3. Contested-border sub-signal of geographic_isolation: the
#    CONTESTED_BORDER_COUNTRIES reference list in
#    notebooks/gold/_common.py (replaces contested_border_flag).
#
# When classic compute is available, this DLT table can be reactivated
# without methodology change.

print("silver_boundaries: deferred (serverless v1 deployment); see notebook header.")
