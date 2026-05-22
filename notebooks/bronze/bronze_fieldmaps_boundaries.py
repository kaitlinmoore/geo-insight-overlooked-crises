# Databricks notebook source

# DEFERRED FROM V1 — see DECISIONS.md "Serverless deployment" entry.
#
# This notebook would have loaded the FieldMaps GeoParquet
# (~2 GB, 43,064 admin2 polygons with denormalized admin0/admin1
# identifiers) into bronze_fieldmaps_boundaries with geometry stored as
# WKB binary. The dependency was Apache Sedona for ST_IsValid /
# ST_GeomFromWKB / ST_Centroid operations.
#
# Sedona requires JVM library installation, which is unavailable on
# Databricks serverless compute. The v1 deployment uses serverless
# exclusively (trial workspace constraint).
#
# WHAT REPLACES IT:
# 1. Frontend choropleth maps: offline GeoJSON extraction via
#    src/acquisition/extract_geojson.py (operates directly on the
#    local GeoParquet; outputs simplified GeoJSON to
#    frontend/public/maps/).
# 2. Country adjacency for gold_cross_border_patterns: GeoNames
#    countryInfo.txt → bronze_country_borders.
# 3. Contested-border flag for geographic_isolation: hardcoded
#    reference list in notebooks/gold/_common.py.
#
# When classic compute is available, this loader can be reactivated
# without methodology change.

print("bronze_fieldmaps_boundaries: deferred (serverless v1 deployment); see notebook header.")
