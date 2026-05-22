# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze loader: `bronze_inform_severity`
# MAGIC
# MAGIC Monthly INFORM Severity snapshots (ACAPS) — the hardest Bronze source.
# MAGIC ~90 `*inform-severity*.xlsx` / `*gcsi*.xlsx` files, ~monthly 2019->2026.
# MAGIC Each file is a 21-sheet analytical workbook full of cross-sheet formulas;
# MAGIC we read only the crisis-list sheets into long form.
# MAGIC
# MAGIC **Strategy (docs/schemas.md `bronze_inform_severity`, data_profiling.md):**
# MAGIC - **Sheet-name dispatch**: read `INFORM Severity - country` if present,
# MAGIC   else fall back to `GCSI` (the legacy Jan 2019 - Aug 2020 branding).
# MAGIC   Also read `INFORM Severity - all crises` where present.
# MAGIC - **Header gymnastics**: real headers are on the **2nd row**
# MAGIC   (`header=1`); a `Weights` marker row and the `(1-10)`/`(1-5)` range
# MAGIC   annotations sit just below. The Bronze rule is **keep them verbatim**
# MAGIC   (Silver drops the `Weights` row), so we do NOT filter rows here.
# MAGIC - **Long form**: both sheets are stacked with a `sheet_name`
# MAGIC   discriminator; `snapshot_date` is derived from the filename
# MAGIC   (month-name preferred, then a leading `YYYYMM` prefix).
# MAGIC - **Types**: xlsx is read via pandas (Spark has no native xlsx reader).
# MAGIC   Columns are coerced to **string** before the Spark conversion. This
# MAGIC   keeps Bronze verbatim and side-steps mixed-dtype failures — the kept
# MAGIC   `Weights`/annotation rows force every value column to be mixed text +
# MAGIC   number anyway, exactly the HXL-forces-string situation in HNO.
# MAGIC - `mergeSchema=true`: GCSI-era and INFORM-era column sets differ.
# MAGIC
# MAGIC **Dependencies**: pandas + openpyxl only (both stock on Databricks
# MAGIC Runtime). These INFORM files are NOT the broken-zip ACLED files, so
# MAGIC openpyxl reads them fine (no python-calamine needed).
# MAGIC
# MAGIC **Note on duplicates**: three `_1`-suffixed files are byte-identical
# MAGIC dupes and other same-month files are genuine re-releases
# MAGIC (data_profiling.md). Bronze keeps everything verbatim; content-hash
# MAGIC dedupe is a Silver concern (open-questions.md).

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

import re
import pandas as pd

dbutils.widgets.text("source_path", f"{VOLUME_BASE}/inform_severity", "INFORM Severity xlsx directory")
dbutils.widgets.dropdown("dry_run", "false", ["false", "true"], "Dry run (read + count, no write)")

source_path = dbutils.widgets.get("source_path").rstrip("/")
dry_run = get_dry_run()
TABLE = f"{CATALOG}.{BRONZE_SCHEMA}.bronze_inform_severity"

ensure_target_schema()

COUNTRY_SHEET = "INFORM Severity - country"
GCSI_SHEET = "GCSI"
ALL_CRISES_SHEET = "INFORM Severity - all crises"

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}

# COMMAND ----------

def parse_snapshot_date(filename):
    """Derive a first-of-month `YYYY-MM-01` string from an INFORM filename.

    Prefer the spelled-out `<month> <year>` (authoritative per the
    `About` sheet convention and robust to the one misnamed file whose
    numeric prefix disagrees with its month name). Fall back to a leading
    `YYYYMM` prefix, then `YYYY`. Returns a string or None.
    """
    base = filename.lower()
    m = re.search(r"(january|february|march|april|may|june|july|august|"
                  r"september|october|november|december)[-_ ]+(\d{4})", base)
    if m:
        return f"{int(m.group(2)):04d}-{_MONTHS[m.group(1)]:02d}-01"
    m = re.search(r"(?:^|[^\d])(\d{4})(\d{2})(?:\d{2})?[-_]", base)
    if m and 1 <= int(m.group(2)) <= 12:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-01"
    m = re.search(r"(\d{4})", base)
    return f"{int(m.group(1)):04d}-01-01" if m else None


def read_sheet(local_path, sheet, filename):
    """Read one INFORM sheet to a stringified pandas frame, verbatim
    (Weights/annotation rows kept), with audit/discriminator columns added."""
    pdf = pd.read_excel(local_path, sheet_name=sheet, header=1, engine="openpyxl",
                        dtype=str)
    pdf.columns = [str(c).strip() for c in pdf.columns]
    pdf = pdf.astype(str).where(pdf.notna(), None)
    pdf["sheet_name"] = sheet
    pdf["snapshot_date"] = parse_snapshot_date(filename)
    pdf["_source_file"] = local_path
    return pdf

# COMMAND ----------

# Volume FUSE path for pandas: dbutils.fs.ls returns dbfs:/Volumes/...; pandas
# reads the plain /Volumes/... path.
dbfs_files = list_files(source_path, suffixes=(".xlsx",))
local_files = [p.replace("dbfs:", "", 1) for p in dbfs_files]
print(f"INFORM/GCSI workbooks found: {len(local_files)}")

frames = []
skipped = []
for lp in local_files:
    fname = lp.rsplit("/", 1)[-1]
    try:
        sheets = pd.ExcelFile(lp, engine="openpyxl").sheet_names
    except Exception as e:
        skipped.append((fname, f"open failed: {e}"))
        continue

    primary = COUNTRY_SHEET if COUNTRY_SHEET in sheets else (GCSI_SHEET if GCSI_SHEET in sheets else None)
    if primary is None:
        skipped.append((fname, f"no country/GCSI sheet; sheets={sheets[:5]}"))
        continue
    frames.append(read_sheet(lp, primary, fname))

    if ALL_CRISES_SHEET in sheets:
        frames.append(read_sheet(lp, ALL_CRISES_SHEET, fname))

if skipped:
    print(f"[WARN] skipped {len(skipped)} file(s):")
    for fn, why in skipped:
        print(f"   - {fn}: {why}")

# COMMAND ----------

# Union the heterogeneous frames (pandas aligns on column names; missing cols
# become NaN -> None). Then one Spark conversion; mergeSchema absorbs the
# GCSI-vs-INFORM column-set differences on write.
pdf_all = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
pdf_all = pdf_all.where(pdf_all.notna(), None)
print(f"combined pandas rows: {len(pdf_all):,}; columns: {len(pdf_all.columns)}")

df = spark.createDataFrame(pdf_all)
df = add_audit_columns(df, source_file=None)  # keeps the pandas-set _source_file
rows_read = df.count()

# COMMAND ----------

written = write_bronze_delta(df, TABLE, dry_run, merge_schema=True)
load_summary(df, rows_read, written, dry_run)
