---
applyTo: "**/*.py"
---

# DQ-Coworker – Python Coding Standards

Apply the [general coding guidelines](./general-coding.instructions.md) to all Python code.
The rules below are Python-specific and take precedence where they overlap.

---

## Style & Formatting

- Follow **PEP 8** in all files. Max line length: **100 characters**.
- Use `snake_case` for variables, functions, and module names.
- Use `PascalCase` for class names.
- Use `ALL_CAPS` for module-level constants.
- Use a single blank line between methods inside a class; two blank lines
  between top-level definitions.
- Use double quotes `"` for strings by default; single quotes only inside
  f-strings when needed to avoid escaping.
- Never use wildcard imports (`from module import *`).

---

## Type Hints

- Add type hints to **all** function parameters and return values.
- Use `from __future__ import annotations` at the top of every file so
  forward references resolve at runtime.
- Use built-in generic types (`list[str]`, `dict[str, int]`) — not
  `typing.List`, `typing.Dict` (deprecated since Python 3.9).
- Use `Optional[X]` only when a parameter genuinely can be `None`; prefer
  `X | None` syntax (Python 3.10+) where the platform supports it.
- Use `TypedDict` or `dataclass` for structured result and config objects
  rather than untyped `dict`.

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass
class DQResult:
    dimension: str
    check: str
    entity: str
    attribute: str
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = ""
```

---

## Docstrings

- Write **Google-style** docstrings for all public modules, classes, functions,
  and methods.
- Docstrings are **not optional** — every exported symbol must have one.

```python
def check_null(
    df: pd.DataFrame,
    entity: str,
    column: str,
    allowed_null_pct: float = 0.0,
) -> dict[str, Any]:
    """Check a column for null/blank values against an allowed threshold.

    Args:
        df: Source DataFrame (Pandas or PySpark converted to Pandas).
        entity: Logical name of the table or file being checked.
        column: Column name to evaluate.
        allowed_null_pct: Maximum acceptable null percentage (0–100).

    Returns:
        DQ result dict with keys: dimension, check, entity, attribute,
        passed, details, evaluated_at.

    Raises:
        KeyError: If ``column`` does not exist in ``df``.
    """
```

---

## DQ Validation Function Contract

Every DQ validation function in this project **must** conform to this contract:

1. **Signature** — accept `df`, `entity: str`, the relevant column/key
   parameters, and an `allowed_*` threshold parameter.
2. **Return** — always return a `dict` (or `DQResult` dataclass) with at
   minimum: `dimension`, `check`, `entity`, `attribute`, `passed`, `details`,
   `evaluated_at`.
3. **No side effects** — validation functions must not write to disk, send
   alerts, or modify the input DataFrame.
4. **Platform guard** — use `isinstance(df, pd.DataFrame)` to branch between
   Pandas and PySpark logic; never assume one platform.
5. **Never raise** inside a validation function — catch exceptions and return
   `passed=False` with `details["error"]` populated.

```python
# Canonical result helper — use in every validation function
from datetime import datetime, timezone

def _result(
    dimension: str, check: str, entity: str, attribute: str,
    passed: bool, details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "dimension": dimension,
        "check": check,
        "entity": entity,
        "attribute": attribute,
        "passed": passed,
        "details": details or {},
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }
```

---

## Platform Compatibility

Target: **Microsoft Fabric**, **Azure Synapse**, **Databricks**, **local PySpark**.

- Detect the platform at startup via the `EXECUTION_PLATFORM` environment
  variable; do not hardcode paths, catalog names, or workspace IDs.
- When a function must behave differently per platform, use a clearly named
  helper rather than inline `if/elif` chains:

```python
def _get_spark_session():
    """Return the active SparkSession for the current execution platform."""
    platform = os.getenv("EXECUTION_PLATFORM", "local").upper()
    if platform == "FABRIC":
        from notebookutils import mssparkutils  # type: ignore[import]
        return mssparkutils.spark
    from pyspark.sql import SparkSession
    return SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
```

- Use `abfss://` URIs for ADLS Gen2; never construct storage paths with
  string concatenation — use `pathlib.PurePosixPath` or a helper.
- Never import Databricks-specific or Fabric-specific modules at the top level;
  guard them inside `if platform == "..."` blocks or `try/except ImportError`.

---

## Imports

Order all imports as follows (enforced by `isort`):
1. `from __future__ import annotations`
2. Standard library
3. Third-party libraries (`pandas`, `pyspark`, `pytest`, …)
4. Internal project modules (`dq_functions`, `dq_config`, …)

Separate each group with a blank line. Never mix groups.

```python
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from pyspark.sql import DataFrame as SparkDataFrame

from dq_config import load_config
from dq_functions import _result
```

---

## DataFrame Patterns

- Never call `.toPandas()` on a large SparkDataFrame without first applying
  a filter or sample; document the expected row count in a comment.
- Prefer PySpark native aggregations (`df.agg(...)`) over `.toPandas()` for
  statistical checks on large datasets.
- Do not mutate the input DataFrame; always work on a copy or derive new
  columns without assignment to the original.
- Use `errors="coerce"` when casting columns with `pd.to_datetime` or
  `pd.to_numeric` to avoid hard failures on malformed data.

---

## Configuration & Secrets

- Load all configuration from environment variables using a central helper:

```python
# dq_config.py
import os

def require_env(key: str) -> str:
    """Return an environment variable value or raise if missing."""
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(f"Required environment variable '{key}' is not set.")
    return value
```

- Never use `os.getenv("KEY", "hardcoded_default")` for secrets or paths
  that differ between environments — make missing config a loud failure.

---

## Testing

- Use `pytest`; organise tests under a `tests/` directory mirroring the
  source layout.
- Name test functions `test_<function_name>_<scenario>`:
  `test_check_null_all_nulls`, `test_check_null_passes_threshold`.
- Every DQ validation function needs tests for:
  - **Pass case**: valid data within threshold
  - **Fail case**: data exceeding threshold
  - **Empty DataFrame**: `len(df) == 0`
  - **All-null column**
  - **Type mismatch** (string in numeric column)
- Use `pytest.mark.parametrize` for threshold boundary tests.
- Use `unittest.mock.patch` (or `pytest-mock`) to mock SparkSession and
  external service calls.
- Never use real or production data in test fixtures — generate synthetic data
  with `pd.DataFrame(...)` or `faker`.

```python
import pytest
import pandas as pd
from dq_functions import check_null

@pytest.mark.parametrize("null_pct,threshold,expected", [
    (0.0,  0.0, True),
    (5.0,  5.0, True),
    (5.1,  5.0, False),
    (100.0, 0.0, False),
])
def test_check_null_threshold_boundary(null_pct, threshold, expected):
    size = 100
    null_count = int(size * null_pct / 100)
    data = [None] * null_count + ["value"] * (size - null_count)
    df = pd.DataFrame({"col": data})
    result = check_null(df, entity="test_entity", column="col",
                        allowed_null_pct=threshold)
    assert result["passed"] is expected
```

---

## Logging

- Use the standard `logging` module; never use `print()` in library code.
- Obtain a logger per module: `logger = logging.getLogger(__name__)`.
- Use structured log messages that include `rule_id`, `entity`, `dimension`,
  and `passed` so log aggregators can parse them without regex.
- Log at `DEBUG` for per-row diagnostics, `INFO` for rule results, `WARNING`
  for threshold breaches, `ERROR` for exceptions.

```python
import logging
logger = logging.getLogger(__name__)

# Good
logger.info("DQ check complete", extra={
    "rule_id": rule_id, "entity": entity,
    "dimension": dimension, "passed": passed,
})

# Bad — avoid
print(f"Check done: {rule_id}")
```

<!-- Contains AI-generated edits. -->