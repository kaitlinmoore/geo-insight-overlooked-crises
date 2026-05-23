# Serverless / Lakeflow constraints

Running notes on quirks of Databricks serverless compute and Lakeflow
Declarative Pipelines (the 2025+ DLT rebrand) discovered while building this
project. Each entry: what the constraint is, where it bit, what we do
instead.

## Lakeflow DP strips notebook magics (except `%pip`)

**Constraint.** Lakeflow Declarative Pipelines (Lakeflow DP, formerly DLT)
does not honor notebook magics at pipeline runtime — `%run`, `%md`, `%sql`
cells are inert. The only magic it still respects is `%pip` (notebook-scoped
library install). This is a difference from interactive notebooks on
classic / serverless compute, where `%run ./_common` works fine.

**Where it bit.** `notebooks/silver/silver_cerf_allocations` failed at
pipeline runtime with `NameError: VALID_ISO3 is not defined`. The
`# MAGIC %run ./_common` cell at the top of every Silver notebook was being
skipped, so none of the shared helpers (`VALID_ISO3`, `bronze()`,
`norm_iso3`, etc. from `notebooks/silver/_common.py`) ever loaded into the
caller's namespace. The first reference to any of them raised.

**What we do instead.** Replace `%run ./_common` with a proper Python
import:

```python
from _common import *  # noqa: F403,F401
```

Lakeflow DP treats Workspace Files co-located with the pipeline's source
notebooks as importable modules — `_common.py` sits next to the silver
notebooks, so the import resolves with no `sys.path` manipulation. The
`noqa` silences the lint warnings star-imports usually trigger; here the
star-import is the intended interface (every Silver notebook expects the
full helper surface).

The Bronze loaders still use `%run ./_common` because they're invoked as
standalone notebook runs (job tasks), not as a Lakeflow pipeline — magics
work there. If we ever migrate Bronze to Lakeflow we have to do the same
swap.

## See also

- `DECISIONS.md` — 2026-05-22 clustered entry "Databricks serverless
  constraints encountered during Bronze→Silver build" enumerates this
  finding alongside the three others discovered in the same session.
