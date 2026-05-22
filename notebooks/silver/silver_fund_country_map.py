# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: `silver_fund_country_map`
# MAGIC
# MAGIC Bridges the two CBPF Bronze tables. Maps each
# MAGIC `bronze_cbpf_allocations.PooledFund` value to (a) its ISO3 + regional
# MAGIC flag, and (b) the corresponding `bronze_cbpf_projects` fund — both the
# MAGIC stable `fund_id` and that source's `fund_name` spelling. Hand-built from
# MAGIC the 34 distinct `PooledFund` values verified in the actual CMU
# MAGIC `Allocations__*.csv` drop, joined to the verified
# MAGIC `(fund_id, fund_name, iso3)` triples in `staging/cbpf_projects.csv`
# MAGIC (see `docs/notes/acquisition_cbpf_projects.md`).
# MAGIC
# MAGIC ## Columns
# MAGIC | column | notes |
# MAGIC |---|---|
# MAGIC | `fund_name` | The `bronze_cbpf_allocations.PooledFund` value. **PK** and the join key `silver_cbpf_allocations` already joins on — kept under this name so that consumer is untouched. |
# MAGIC | `fund_name_canonical` | The `bronze_cbpf_projects.fund_name` spelling for the same fund (e.g. `Burkina Faso (RhPF-WCA)` → `Burkina Faso`); equals `fund_name` when the two sources agree or no project exists yet. |
# MAGIC | `fund_id` | Stable join key from `bronze_cbpf_projects.fund_id`. **Nullable** — null for funds with no projects in GMS yet (currently only `Honduras (RhPF-LAC)`, a 2026-only allocation). |
# MAGIC | `fund_iso3` | Recipient-country ISO3. Non-null for all 34 real funds (there is no country-less fund in the real data). |
# MAGIC | `is_regional_fund` | True for funds run under a regional pooled-fund mechanism (`RhPF-WCA`, `RhPF-LAC`, `AP-RHPF`, `ESAHF`). They keep their anchor-country ISO3 **and** this flag, so the CBPF Allocation View can roll them into the country or treat them as regional. |
# MAGIC
# MAGIC ## Why a static map and not a fuzzy join
# MAGIC The fund vocabulary is small (34), closed, and the two Bronze sources spell
# MAGIC the same fund differently (regional-window suffixes; `DRC`↔`DRC`,
# MAGIC `oPt`↔`oPt`, but `Burkina Faso (RhPF-WCA)`↔`Burkina Faso`). ISO3 alone
# MAGIC cannot disambiguate every case — e.g. **Pakistan has two distinct funds with
# MAGIC the same ISO3**: `Pakistan` (`fund_id` 60) and `Pakistan (AP-RHPF)`
# MAGIC (`fund_id` 97). A literal, audited map is the only safe bridge. New fund
# MAGIC names in future drops fail the coverage `@dlt.expect` in
# MAGIC `silver_cbpf_allocations` and get added here.
# MAGIC
# MAGIC ## Two source data quirks baked in (see acquisition note)
# MAGIC - `Mozambique (RhPF)` is mis-coded `LI` (Liechtenstein) at source → `MOZ`.
# MAGIC - `Syria Cross border` carries placeholder `XX` → `SYR` (operated
# MAGIC   cross-border from Türkiye; recipient population is Syrian). It is **not**
# MAGIC   flagged regional — it is a country-anchored cross-border window, distinct
# MAGIC   from the in-country `Syria` fund (`fund_id` 62) but sharing ISO3 `SYR`.

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

import dlt

# (fund_name, fund_name_canonical, fund_id, fund_iso3, is_regional_fund).
# fund_name      = bronze_cbpf_allocations.PooledFund (PK; the silver_cbpf_allocations join key)
# fund_name_canonical = bronze_cbpf_projects.fund_name spelling for the same fund
# fund_id        = bronze_cbpf_projects.fund_id (None where no projects exist yet)
# Verified against staging/cbpf_projects.csv: every non-null fund_id resolves and
# its projects-side iso3 matches fund_iso3 (0 mismatches).
_FUND_MAP = [
    ("Afghanistan", "Afghanistan", 23, "AFG", False),
    ("Bangladesh (AP-RHPF)", "Bangladesh", 99, "BGD", True),
    ("Burkina Faso (RhPF-WCA)", "Burkina Faso", 85, "BFA", True),
    ("CAR", "CAR", 17, "CAF", False),
    ("Chad (RhPF-WCA)", "Chad (RhPF)", 90, "TCD", True),
    ("Colombia (RhPF-LAC)", "Colombia (RhPF)", 87, "COL", True),
    ("DRC", "DRC", 24, "COD", False),
    ("El Salvador (RhPF-LAC)", "El Salvador", 509, "SLV", True),
    ("Ethiopia", "Ethiopia", 53, "ETH", False),
    ("Fiji (AP-Rhpf)", "Fiji", 94, "FJI", True),
    ("Guatemala (RhPF-LAC)", "Guatemala", 508, "GTM", True),
    ("Haiti (RhPF-LAC)", "Haiti (RhPF)", 88, "HTI", True),
    # 2026-only allocation; no projects entered in GMS yet -> fund_id null.
    ("Honduras (RhPF-LAC)", "Honduras (RhPF-LAC)", None, "HND", True),
    ("Iraq", "Iraq", 72, "IRQ", False),
    ("Jordan", "Jordan", 73, "JOR", False),
    ("Kenya (ESAHF)", "Kenya", 511, "KEN", True),
    ("Lebanon", "Lebanon", 71, "LBN", False),
    ("Mali (RhPF-WCA)", "Mali", 86, "MLI", True),
    ("Mozambique (RhPF)", "Mozambique (RhPF)", 89, "MOZ", True),
    ("Myanmar", "Myanmar", 59, "MMR", False),
    ("Niger (RhPF-WCA)", "Niger", 84, "NER", True),
    ("Nigeria", "Nigeria", 75, "NGA", False),
    ("Pakistan", "Pakistan", 60, "PAK", False),
    ("Pakistan (AP-RHPF)", "Pakistan", 97, "PAK", True),
    ("Somalia", "Somalia", 21, "SOM", False),
    ("South Sudan", "South Sudan", 19, "SSD", False),
    ("Sudan", "Sudan", 15, "SDN", False),
    ("Syria", "Syria", 62, "SYR", False),
    ("Syria Cross border", "Syria Cross border", 70, "SYR", False),
    ("Uganda (ESAHF)", "Uganda", 512, "UGA", True),
    ("Ukraine", "Ukraine", 81, "UKR", False),
    ("Venezuela", "Venezuela", 83, "VEN", False),
    ("Yemen", "Yemen", 64, "YEM", False),
    ("oPt", "oPt", 67, "PSE", False),
]


@dlt.table(
    name="silver_fund_country_map",
    comment="CBPF PooledFund → ISO3 + fund_id bridge between bronze_cbpf_allocations "
            "and bronze_cbpf_projects. is_regional_fund flags regional pooled-fund "
            "mechanisms (RhPF/AP-RHPF/ESAHF). fund_id is null where no projects exist yet.",
)
@dlt.expect("iso3_present_unless_regional", "fund_iso3 IS NOT NULL OR is_regional_fund = true")
@dlt.expect("fund_id_resolved", "fund_id IS NOT NULL")
def silver_fund_country_map():
    return spark.createDataFrame(
        _FUND_MAP,
        schema="fund_name string, fund_name_canonical string, fund_id int, "
               "fund_iso3 string, is_regional_fund boolean",
    )
