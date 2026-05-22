# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: `silver_fund_country_map`
# MAGIC
# MAGIC Maps CBPF `PooledFund` names → ISO3, flagging the genuinely-regional
# MAGIC funds (which have no single owning country). Hand-built from the 34
# MAGIC distinct `PooledFund` values inventoried in `docs/data_catalog.md`
# MAGIC (`bronze_cbpf_allocations`).
# MAGIC
# MAGIC Why a static map and not a fuzzy join: the fund vocabulary is small (34),
# MAGIC closed, and includes regional pooled funds (`(RhPF-WCA)`, `(RhPF-LAC)`,
# MAGIC `(AP-RHPF)`, `(ESAHF)`) plus one pure-regional fund with no country at
# MAGIC all. A literal map is auditable and avoids mis-mapping a regional fund to
# MAGIC the wrong country. New fund names appearing in future drops fail the
# MAGIC coverage `@dlt.expect` in `silver_cbpf_allocations` and get added here.
# MAGIC
# MAGIC The country-suffixed regional funds (e.g. `Sudan (ESAHF)`) keep their
# MAGIC anchor country's ISO3 **and** carry `is_regional_fund=true`, so the
# MAGIC optional CBPF Allocation View can either roll them into the country or
# MAGIC treat them as regional.

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

import dlt

# (fund_name, fund_iso3, is_regional_fund). fund_iso3 = None for the one
# pure-regional fund with no anchor country.
_FUND_MAP = [
    ("Afghanistan", "AFG", False),
    ("Burkina Faso", "BFA", False),
    ("Burkina Faso (RhPF-WCA)", "BFA", True),
    ("Cameroon", "CMR", False),
    ("Cameroon (RhPF-WCA)", "CMR", True),
    ("Central African Republic", "CAF", False),
    ("Chad", "TCD", False),
    ("Colombia (AP-RHPF)", "COL", True),
    ("Democratic Republic of the Congo", "COD", False),
    ("Ethiopia", "ETH", False),
    ("Fiji (AP-RHPF)", "FJI", True),
    ("Haiti", "HTI", False),
    ("Haiti (RhPF-LAC)", "HTI", True),
    ("Iraq", "IRQ", False),
    ("Jordan", "JOR", False),
    ("Lebanon", "LBN", False),
    ("Mali", "MLI", False),
    ("Mali (RhPF-WCA)", "MLI", True),
    ("Myanmar", "MMR", False),
    ("Niger", "NER", False),
    ("Niger (RhPF-WCA)", "NER", True),
    ("Nigeria", "NGA", False),
    ("Occupied Palestinian Territory", "PSE", False),
    ("Pakistan (AP-RHPF)", "PAK", True),
    ("Papua New Guinea (AP-RHPF)", "PNG", True),
    ("Philippines (AP-RHPF)", "PHL", True),
    ("Regional Humanitarian Pooled Fund - South & Central America", None, True),
    ("Somalia", "SOM", False),
    ("South Sudan", "SSD", False),
    ("Sudan", "SDN", False),
    ("Sudan (ESAHF)", "SDN", True),
    ("Syrian Arab Republic", "SYR", False),
    ("Türkiye", "TUR", False),
    ("Ukraine", "UKR", False),
    ("Vanuatu (AP-RHPF)", "VUT", True),
    ("Yemen", "YEM", False),
]


@dlt.table(
    name="silver_fund_country_map",
    comment="CBPF PooledFund → ISO3 map; is_regional_fund flags the four "
            "regional pooled funds and the one country-less regional fund.",
)
@dlt.expect("iso3_present_unless_regional", "fund_iso3 IS NOT NULL OR is_regional_fund = true")
def silver_fund_country_map():
    return spark.createDataFrame(
        _FUND_MAP, schema="fund_name string, fund_iso3 string, is_regional_fund boolean"
    )
