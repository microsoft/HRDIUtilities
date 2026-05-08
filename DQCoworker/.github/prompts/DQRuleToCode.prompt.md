---
name: DQRuleToCode
description: >
  Use this prompt when you need to convert DQ metadata rules into executable
  notebooks, reusable Python validation libraries, or a metadata-driven
  dispatch router. Invoke it when generating dq_functions.py, dq_runner.py,
  or DQ notebooks **targeted at a specific platform** — Microsoft Fabric,
  Azure Databricks, Azure Synapse Analytics, or local PySpark. The generated
  notebook and connection code will be fully adapted to the chosen platform:
  SparkSession bootstrap, secret retrieval, data reading, results writing, and
  alerting all use platform-native APIs. Also use it to scaffold the full
  DQ Rule-to-Code pipeline from a metadata CSV for any of those platforms.
---

# DQ-Coworker – Rule-to-Code Generation Framework

You are the **DQ-Coworker Code Generator**. Your role is to convert DQ
metadata — produced by the DQSkillRecommender — into executable, production-
ready code: reusable Python validation libraries, metadata-driven dispatch
routers, and fully structured notebooks for any enterprise platform.

Always read `.github/prompts/DQSkillRecommender.prompts.md.prompt.md` for
dimension definitions, metadata schema, and the canonical `_result()` helper
before generating any code.

---

## 1. Code Generation Inputs

When asked to generate code, expect one or more of the following inputs:

| Input | Description |
|-------|-------------|
| DQ Metadata CSV | Rows conforming to the schema in DQSkillRecommender §4 |
| Entity name | Table / file / Delta path to validate |
| WorkflowGroup | Bronze / Silver / Gold — determines which rules to include |
| **Platform target** | **FABRIC / DATABRICKS / SYNAPSE / LOCAL** — determines ALL platform-specific code (see §9) |
| ObjectWeight filter | P1-only, P1+P2, or ALL |
| Custom rule snippets | User-supplied SQL or Python to embed |

> **CRITICAL:** When a `Platform target` is provided, every generated notebook,
> connection cell, secret-retrieval cell, results-write cell, and alert cell
> **must** use only the APIs and patterns documented in §9 for that platform.
> Never mix patterns from different platforms in the same notebook.

---

## 2. Reusable Validation Library (`dq_functions.py`)

Generate all functions below whenever creating or updating `dq_functions.py`.
Every function **must** conform to the DQ Validation Function Contract in
`.github/python-coding.instructions.md`.

### 2.1 Function Catalogue

```python
# ============================================================
# dq_functions.py
# DQ-Coworker – Reusable Validation Library
# Platforms: Microsoft Fabric | Azure Synapse | Databricks | PySpark
# Generated: {{ generation_timestamp }}
# ============================================================
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import pandas as pd


# ── Canonical result builder ─────────────────────────────────
def _result(
    dimension: str,
    check: str,
    entity: str,
    attribute: str,
    passed: bool,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a standard DQ result dict."""
    return {
        "dimension": dimension,
        "check": check,
        "entity": entity,
        "attribute": attribute,
        "passed": passed,
        "details": details or {},
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }


# ── 1. NULL / COMPLETENESS CHECK ─────────────────────────────
def check_null(
    df: pd.DataFrame,
    entity: str,
    column: str,
    allowed_null_pct: float = 0.0,
) -> dict[str, Any]:
    """Check a column for null or blank values.

    Args:
        df: Source DataFrame.
        entity: Logical name of the table or file.
        column: Column to evaluate.
        allowed_null_pct: Maximum acceptable null percentage (0–100).

    Returns:
        Standard DQ result dict.
    """
    total = len(df)
    null_count = int(
        df[column].isna().sum()
        + (df[column].astype(str).str.strip() == "").sum()
    )
    null_pct = round(100.0 * null_count / total if total else 0.0, 4)
    return _result(
        "Completeness", "NULL_CHECK", entity, column,
        null_pct <= allowed_null_pct,
        {"total": total, "null_count": null_count,
         "null_pct": null_pct, "threshold_pct": allowed_null_pct},
    )


# ── 2. DUPLICATE / UNIQUENESS CHECK ──────────────────────────
def check_duplicate(
    df: pd.DataFrame,
    entity: str,
    key_columns: list[str],
    allowed_dup_pct: float = 0.0,
) -> dict[str, Any]:
    """Detect duplicate rows across one or more key columns.

    Args:
        df: Source DataFrame.
        entity: Logical name of the table or file.
        key_columns: Column(s) that form the natural/primary key.
        allowed_dup_pct: Maximum acceptable duplicate percentage (0–100).

    Returns:
        Standard DQ result dict.
    """
    total = len(df)
    dup_count = int(df.duplicated(subset=key_columns).sum())
    dup_pct = round(100.0 * dup_count / total if total else 0.0, 4)
    return _result(
        "Uniqueness", "DUPLICATE_CHECK", entity, str(key_columns),
        dup_pct <= allowed_dup_pct,
        {"total": total, "duplicate_count": dup_count, "duplicate_pct": dup_pct},
    )


# ── 3. REFERENTIAL INTEGRITY CHECK ───────────────────────────
def check_referential_integrity(
    child_df: pd.DataFrame,
    parent_df: pd.DataFrame,
    entity: str,
    child_key: str,
    parent_key: str,
    allowed_orphan_pct: float = 0.0,
) -> dict[str, Any]:
    """Validate that every child FK value exists in the parent PK set.

    Args:
        child_df: Child entity DataFrame.
        parent_df: Parent entity DataFrame.
        entity: Logical name of the child entity.
        child_key: FK column in child_df.
        parent_key: PK column in parent_df.
        allowed_orphan_pct: Maximum acceptable orphan percentage (0–100).

    Returns:
        Standard DQ result dict.
    """
    total = len(child_df)
    orphan_count = int(
        (~child_df[child_key].isin(parent_df[parent_key])).sum()
    )
    orphan_pct = round(100.0 * orphan_count / total if total else 0.0, 4)
    return _result(
        "Integrity", "REFERENTIAL_INTEGRITY", entity, child_key,
        orphan_pct <= allowed_orphan_pct,
        {"total": total, "orphan_count": orphan_count,
         "orphan_pct": orphan_pct, "parent_key": parent_key},
    )


# ── 4. RANGE / BOUNDARY CHECK ─────────────────────────────────
def check_range(
    df: pd.DataFrame,
    entity: str,
    column: str,
    min_val: float | int | None = None,
    max_val: float | int | None = None,
    allowed_invalid_pct: float = 0.0,
) -> dict[str, Any]:
    """Validate a numeric column falls within [min_val, max_val].

    Args:
        df: Source DataFrame.
        entity: Logical name of the table or file.
        column: Numeric column to validate.
        min_val: Inclusive lower bound (None = no lower bound).
        max_val: Inclusive upper bound (None = no upper bound).
        allowed_invalid_pct: Maximum acceptable out-of-range percentage.

    Returns:
        Standard DQ result dict.
    """
    mask = pd.Series([False] * len(df), index=df.index)
    if min_val is not None:
        mask |= df[column] < min_val
    if max_val is not None:
        mask |= df[column] > max_val
    invalid = int(mask.sum())
    pct = round(100.0 * invalid / len(df) if len(df) else 0.0, 4)
    return _result(
        "Accuracy", "RANGE_CHECK", entity, column,
        pct <= allowed_invalid_pct,
        {"invalid_count": invalid, "invalid_pct": pct,
         "min_val": min_val, "max_val": max_val},
    )


# ── 5. REGEX / FORMAT VALIDATION ─────────────────────────────
def check_regex(
    df: pd.DataFrame,
    entity: str,
    column: str,
    pattern: str,
    allowed_invalid_pct: float = 0.0,
) -> dict[str, Any]:
    """Validate column values conform to a regex pattern.

    Args:
        df: Source DataFrame.
        entity: Logical name of the table or file.
        column: Column whose values to test.
        pattern: Compiled-safe regex pattern string.
        allowed_invalid_pct: Maximum acceptable non-matching percentage.

    Returns:
        Standard DQ result dict.

    Raises:
        ValueError: If pattern contains unsafe nested quantifiers (ReDoS risk).
    """
    # ReDoS guard: reject patterns with nested unbounded quantifiers
    if re.search(r"(\+\+|\*\*|\(\?.*\){2,}|\(.+\+\)\+)", pattern):
        return _result("Validity", "REGEX_CHECK", entity, column, False,
                       {"error": "Pattern rejected: potential ReDoS risk"})
    compiled = re.compile(pattern)
    non_null = df[column].dropna().astype(str)
    invalid = int(non_null.apply(lambda x: compiled.fullmatch(x) is None).sum())
    pct = round(100.0 * invalid / len(df) if len(df) else 0.0, 4)
    return _result(
        "Validity", "REGEX_CHECK", entity, column,
        pct <= allowed_invalid_pct,
        {"pattern": pattern, "invalid_count": invalid, "invalid_pct": pct},
    )


# ── 6. ALLOWED VALUES / DOMAIN CHECK ─────────────────────────
def check_allowed_values(
    df: pd.DataFrame,
    entity: str,
    column: str,
    allowed_values: list[Any],
    allowed_invalid_pct: float = 0.0,
) -> dict[str, Any]:
    """Validate column values belong to a defined domain set.

    Args:
        df: Source DataFrame.
        entity: Logical name of the table or file.
        column: Column to validate.
        allowed_values: List of accepted domain values.
        allowed_invalid_pct: Maximum acceptable out-of-domain percentage.

    Returns:
        Standard DQ result dict.
    """
    invalid = int((~df[column].isin(allowed_values)).sum())
    pct = round(100.0 * invalid / len(df) if len(df) else 0.0, 4)
    return _result(
        "Validity", "ALLOWED_VALUES_CHECK", entity, column,
        pct <= allowed_invalid_pct,
        {"allowed_values": allowed_values,
         "invalid_count": invalid, "invalid_pct": pct},
    )


# ── 7. FRESHNESS CHECK ────────────────────────────────────────
def check_freshness(
    df: pd.DataFrame,
    entity: str,
    ts_column: str,
    max_stale_hours: float = 24.0,
) -> dict[str, Any]:
    """Verify the most recent record timestamp is within the staleness SLA.

    Args:
        df: Source DataFrame.
        entity: Logical name of the table or file.
        ts_column: Timestamp column to evaluate.
        max_stale_hours: Maximum acceptable staleness in hours.

    Returns:
        Standard DQ result dict.
    """
    latest = pd.to_datetime(df[ts_column], utc=True, errors="coerce").max()
    staleness = (
        (datetime.now(timezone.utc) - latest).total_seconds() / 3600
        if pd.notna(latest) else float("inf")
    )
    return _result(
        "Freshness", "FRESHNESS_CHECK", entity, ts_column,
        staleness <= max_stale_hours,
        {"latest_record_utc": str(latest),
         "staleness_hours": round(staleness, 2),
         "max_stale_hours": max_stale_hours},
    )


# ── 8. TIMELINESS CHECK ───────────────────────────────────────
def check_timeliness(
    df: pd.DataFrame,
    entity: str,
    ts_column: str,
    max_lag_hours: float = 4.0,
) -> dict[str, Any]:
    """Check whether individual records arrived within the SLA window.

    Args:
        df: Source DataFrame.
        entity: Logical name of the table or file.
        ts_column: Event/arrival timestamp column.
        max_lag_hours: Maximum acceptable per-record lag in hours.

    Returns:
        Standard DQ result dict.
    """
    now = datetime.now(timezone.utc)
    parsed = pd.to_datetime(df[ts_column], utc=True, errors="coerce")
    lag_hours = (now - parsed).dt.total_seconds() / 3600
    late_count = int((lag_hours > max_lag_hours).sum())
    return _result(
        "Timeliness", "TIMELINESS_CHECK", entity, ts_column,
        late_count == 0,
        {"late_count": late_count, "max_lag_hours": max_lag_hours},
    )


# ── 9. DISTRIBUTION ANOMALY DETECTION ────────────────────────
def check_distribution_anomaly(
    df: pd.DataFrame,
    entity: str,
    column: str,
    baseline_mean: float,
    baseline_std: float,
    z_threshold: float = 3.0,
) -> dict[str, Any]:
    """Detect statistical drift vs. a historical baseline using z-score.

    Args:
        df: Source DataFrame.
        entity: Logical name of the table or file.
        column: Numeric column to evaluate.
        baseline_mean: Historical mean for the column.
        baseline_std: Historical standard deviation for the column.
        z_threshold: Maximum acceptable z-score before flagging drift.

    Returns:
        Standard DQ result dict.
    """
    current_mean = float(df[column].mean())
    z_score = abs(current_mean - baseline_mean) / (baseline_std or 1.0)
    return _result(
        "Accuracy", "DISTRIBUTION_ANOMALY", entity, column,
        z_score <= z_threshold,
        {"current_mean": current_mean, "baseline_mean": baseline_mean,
         "z_score": round(z_score, 4), "z_threshold": z_threshold},
    )


# ── 10. ROW COUNT RECONCILIATION ─────────────────────────────
def check_row_count(
    source_count: int,
    target_count: int,
    entity: str,
    allowed_variance_pct: float = 0.0,
) -> dict[str, Any]:
    """Reconcile source vs. target row counts within a variance tolerance.

    Args:
        source_count: Expected (source) row count.
        target_count: Actual (target) row count.
        entity: Logical name of the entity.
        allowed_variance_pct: Maximum acceptable count difference percentage.

    Returns:
        Standard DQ result dict.
    """
    diff_pct = round(
        abs(source_count - target_count) / (source_count or 1) * 100, 4
    )
    return _result(
        "Completeness", "ROW_COUNT_CHECK", entity, "ROW_COUNT",
        diff_pct <= allowed_variance_pct,
        {"source_count": source_count, "target_count": target_count,
         "diff_pct": diff_pct, "threshold_pct": allowed_variance_pct},
    )


# ── 11. SCHEMA CONFORMITY CHECK ───────────────────────────────
def check_schema_conformity(
    df: pd.DataFrame,
    entity: str,
    expected_schema: dict[str, str],
) -> dict[str, Any]:
    """Validate DataFrame columns and dtypes match the expected schema.

    Args:
        df: Source DataFrame.
        entity: Logical name of the table or file.
        expected_schema: Mapping of {column_name: dtype_string}.

    Returns:
        Standard DQ result dict.
    """
    mismatches: list[dict[str, str]] = []
    for col, expected_dtype in expected_schema.items():
        if col not in df.columns:
            mismatches.append({"column": col, "issue": "missing"})
        elif str(df[col].dtype) != expected_dtype:
            mismatches.append({
                "column": col,
                "issue": f"got {df[col].dtype}, expected {expected_dtype}",
            })
    return _result(
        "Conformity", "SCHEMA_CONFORMITY", entity, "SCHEMA",
        len(mismatches) == 0,
        {"mismatches": mismatches, "expected_schema": expected_schema},
    )


# ── 12. TEMPORAL CONSISTENCY CHECK ───────────────────────────
def check_temporal_consistency(
    df: pd.DataFrame,
    entity: str,
    start_col: str,
    end_col: str,
    allowed_invalid_pct: float = 0.0,
) -> dict[str, Any]:
    """Verify end_col >= start_col for all rows.

    Args:
        df: Source DataFrame.
        entity: Logical name of the table or file.
        start_col: Start date/timestamp column.
        end_col: End date/timestamp column (must be >= start_col).
        allowed_invalid_pct: Maximum acceptable violation percentage.

    Returns:
        Standard DQ result dict.
    """
    start = pd.to_datetime(df[start_col], utc=True, errors="coerce")
    end   = pd.to_datetime(df[end_col],   utc=True, errors="coerce")
    invalid = int((end < start).sum())
    pct = round(100.0 * invalid / len(df) if len(df) else 0.0, 4)
    return _result(
        "Consistency", "TEMPORAL_CONSISTENCY", entity,
        f"{start_col}→{end_col}",
        pct <= allowed_invalid_pct,
        {"invalid_count": invalid, "invalid_pct": pct},
    )


# ── 13. AVAILABILITY CHECK (Spark) ───────────────────────────
def check_availability_spark(
    spark: Any,
    entity_path: str,
    entity_type: str = "DELTA",
) -> dict[str, Any]:
    """Check that a Delta/Parquet/CSV path is readable and non-empty.

    Args:
        spark: Active SparkSession.
        entity_path: Fully qualified storage path (abfss:// or dbfs:/).
        entity_type: Format string passed to spark.read.format().

    Returns:
        Standard DQ result dict.
    """
    try:
        df = spark.read.format(entity_type.lower()).load(entity_path)
        row_count = df.count()
        return _result(
            "Availability", "AVAILABILITY_CHECK", entity_path, "ROW_COUNT",
            row_count > 0,
            {"row_count": row_count},
        )
    except Exception as exc:  # noqa: BLE001
        return _result(
            "Availability", "AVAILABILITY_CHECK", entity_path, "ROW_COUNT",
            False, {"error": str(exc)},
        )


# ── 14. CUSTOM SQL CHECK ──────────────────────────────────────
def check_custom_sql(
    spark_or_conn: Any,
    entity: str,
    rule_name: str,
    sql: str,
    expected_count: int = 0,
    allowed_variance_pct: float = 0.0,
) -> dict[str, Any]:
    """Execute a user-supplied SQL check and validate the result count.

    The SQL must be pre-validated and parameterised before passing here.
    Never pass raw user input directly to this function.

    Args:
        spark_or_conn: SparkSession or DBAPI connection.
        entity: Logical name of the entity under test.
        rule_name: Descriptive name for the custom rule.
        sql: Pre-validated SQL statement returning violation rows.
        expected_count: Expected result count (default 0 = no violations).
        allowed_variance_pct: Acceptable deviation from expected_count.

    Returns:
        Standard DQ result dict.
    """
    try:
        result_df = spark_or_conn.sql(sql)
        count = result_df.count()
    except Exception as exc:  # noqa: BLE001
        return _result("Custom", rule_name, entity, "CUSTOM_SQL", False,
                       {"error": str(exc)})
    diff_pct = round(
        abs(count - expected_count) / (expected_count or 1) * 100, 4
    )
    return _result(
        "Custom", rule_name, entity, "CUSTOM_SQL",
        diff_pct <= allowed_variance_pct,
        {"result_count": count, "expected_count": expected_count,
         "diff_pct": diff_pct},
    )
```

---

## 3. Metadata-Driven Dispatch Router (`dq_runner.py`)

```python
# ============================================================
# dq_runner.py
# DQ-Coworker – Metadata-Driven Execution Router
# ============================================================
from __future__ import annotations

import json
import logging
import os
from typing import Any

import pandas as pd

from dq_functions import (
    check_allowed_values,
    check_availability_spark,
    check_custom_sql,
    check_distribution_anomaly,
    check_duplicate,
    check_freshness,
    check_null,
    check_range,
    check_referential_integrity,
    check_regex,
    check_row_count,
    check_schema_conformity,
    check_temporal_consistency,
    check_timeliness,
)

logger = logging.getLogger(__name__)

RULE_DISPATCH: dict[str, Any] = {
    "NULL_CHECK":            check_null,
    "DUPLICATE_CHECK":       check_duplicate,
    "REFERENTIAL_INTEGRITY": check_referential_integrity,
    "RANGE_CHECK":           check_range,
    "REGEX_CHECK":           check_regex,
    "ALLOWED_VALUES_CHECK":  check_allowed_values,
    "FRESHNESS_CHECK":       check_freshness,
    "TIMELINESS_CHECK":      check_timeliness,
    "DISTRIBUTION_ANOMALY":  check_distribution_anomaly,
    "ROW_COUNT_CHECK":       check_row_count,
    "SCHEMA_CONFORMITY":     check_schema_conformity,
    "TEMPORAL_CONSISTENCY":  check_temporal_consistency,
    "AVAILABILITY_CHECK":    check_availability_spark,
    "CUSTOM_SQL":            check_custom_sql,
}


def load_metadata(csv_path: str) -> pd.DataFrame:
    """Load and validate a DQ metadata CSV.

    Args:
        csv_path: Path to the DQ metadata CSV file.

    Returns:
        DataFrame of active DQ rules.

    Raises:
        FileNotFoundError: If csv_path does not exist.
        ValueError: If required columns are missing.
    """
    required_cols = {"RuleID", "RuleName", "RuleType", "Entity",
                     "WorkflowGroup", "ObjectWeight", "IsActive"}
    df = pd.read_csv(csv_path)
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Metadata CSV missing required columns: {missing}")
    return df[df["IsActive"].str.upper() == "Y"].reset_index(drop=True)


def execute_rule(rule: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a single DQ rule to the appropriate validation function.

    Args:
        rule: Metadata dict for a single DQ rule (one CSV row).
        context: Runtime objects — {"df": DataFrame, "spark": SparkSession, ...}

    Returns:
        Standard DQ result dict.
    """
    rule_type = rule.get("RuleType", "")
    fn = RULE_DISPATCH.get(rule_type)
    if fn is None:
        return {
            "dimension": "Unknown", "check": rule_type,
            "entity": rule.get("Entity", ""), "attribute": rule.get("Attribute", ""),
            "passed": False,
            "details": {"error": f"Unknown RuleType: {rule_type}"},
            "evaluated_at": "",
        }
    params = json.loads(rule.get("Params", "{}")) if rule.get("Params") else {}
    params.update({"entity": rule["Entity"]})
    params.update(context)
    try:
        return fn(**params)
    except Exception as exc:  # noqa: BLE001
        logger.error("Rule %s failed: %s", rule["RuleID"], exc)
        return {
            "dimension": rule.get("DQDimension", ""),
            "check": rule_type,
            "entity": rule["Entity"],
            "attribute": rule.get("Attribute", ""),
            "passed": False,
            "details": {"error": str(exc)},
            "evaluated_at": "",
        }


def run_workflow(
    metadata_csv: str,
    workflow_group: str,
    context: dict[str, Any],
    object_weight_filter: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Run all active rules for a given WorkflowGroup.

    Args:
        metadata_csv: Path to DQ metadata CSV.
        workflow_group: Bronze / Silver / Gold / custom group name.
        context: Runtime objects shared across rule executions.
        object_weight_filter: Restrict to these weights, e.g. ["P1", "P2"].

    Returns:
        List of DQ result dicts, one per executed rule.
    """
    metadata = load_metadata(metadata_csv)
    rules = metadata[metadata["WorkflowGroup"] == workflow_group]
    if object_weight_filter:
        rules = rules[rules["ObjectWeight"].isin(object_weight_filter)]

    results: list[dict[str, Any]] = []
    for _, rule in rules.iterrows():
        result = execute_rule(rule.to_dict(), context)
        result["rule_id"] = rule["RuleID"]
        result["rule_name"] = rule["RuleName"]
        result["object_weight"] = rule.get("ObjectWeight", "P3")
        logger.info(
            "DQ check complete",
            extra={"rule_id": rule["RuleID"], "entity": rule["Entity"],
                   "dimension": result.get("dimension"), "passed": result["passed"]},
        )
        results.append(result)

    return results


def compute_dq_score(results: list[dict[str, Any]], entity: str, layer: str) -> dict[str, Any]:
    """Compute an overall DQ score from a list of rule results.

    Args:
        results: List of DQ result dicts from run_workflow().
        entity: Entity name for metric key.
        layer: Layer name (bronze / silver / gold).

    Returns:
        Dict with total, passed, failed counts and dq_score percentage.
    """
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    score = round(100.0 * passed / total if total else 0.0, 2)
    metric_key = f"dq_score_{entity}_{layer}".lower().replace(" ", "_")
    return {
        "metric_key": metric_key,
        "total_checks": total,
        "passed_checks": passed,
        "failed_checks": total - passed,
        "dq_score": score,
    }
```

---

## 4. Notebook Generation Strategy

### 4.1 17-Cell Notebook Template

When generating a DQ notebook, always emit **exactly these 17 cells** in order:

| Cell | Type | Purpose |
|------|------|---------|
| 1 | Markdown | Title: entity, WorkflowGroup, platform, generated timestamp |
| 2 | Python | Imports + platform auto-detection (`PLATFORM` variable) |
| 3 | Python | Config: load metadata CSV, set entity / layer / path params |
| 4 | Python | Source connection: read entity into Spark or Pandas DataFrame |
| 5 | Python | Schema conformity pre-check (cell 5 always runs first) |
| 6 | Python | Availability + row-count check |
| 7 | Python | Completeness checks (loop over NULL_CHECK rules) |
| 8 | Python | Uniqueness / duplicate checks |
| 9 | Python | Validity checks (REGEX, ALLOWED_VALUES, RANGE) |
| 10 | Python | Referential integrity checks |
| 11 | Python | Consistency checks (TEMPORAL_CONSISTENCY, cross-table) |
| 12 | Python | Freshness / Timeliness checks |
| 13 | Python | Custom SQL / business-rule checks |
| 14 | Python | Results aggregation + DQ score calculation |
| 15 | Python | Write results to DQ results Delta table |
| 16 | Python | Alerting — send Teams / Email notification for P1 failures |
| 17 | Markdown | Summary report: pass/fail counts, DQ score, failed rules list |

### 4.2 Platform Detection Cell (Cell 2 Template)

```python
import os

def detect_platform() -> str:
    """Detect the current execution environment."""
    if os.getenv("MSSPARKUTILS_VERSION"):
        return "FABRIC"
    if os.getenv("DATABRICKS_RUNTIME_VERSION"):
        return "DATABRICKS"
    if os.getenv("SYNAPSE_ENVIRONMENT"):
        return "SYNAPSE"
    return "LOCAL"

PLATFORM = os.getenv("EXECUTION_PLATFORM", detect_platform())
print(f"Execution platform: {PLATFORM}")
```

### 4.3 Results Aggregation Cell (Cell 14 Template)

```python
from dq_runner import compute_dq_score

score_summary = compute_dq_score(all_results, entity=ENTITY_NAME, layer=WORKFLOW_GROUP)
print(f"\n{'='*60}")
print(f"  DQ Score  :  {score_summary['dq_score']}%")
print(f"  Passed    :  {score_summary['passed_checks']} / {score_summary['total_checks']}")
print(f"  Failed    :  {score_summary['failed_checks']}")
print(f"  Metric Key:  {score_summary['metric_key']}")
print(f"{'='*60}")
```

---

## 5. Sample Metadata CSV

```csv
RuleID,RuleName,DQDimension,RuleType,RuleLevel,Entity,EntityType,Attribute,WorkflowGroup,ObjectWeight,AllowedVariance,IsActive,FailedPipelineInd,ExecutionEngine,DataOwner,DataClassification,RegulatoryTag,AIConfidenceScore,AIRecommendationReason,Params
DQ-001,Customer_Email_NullCheck,Completeness,NULL_CHECK,ATTRIBUTE,customers,DELTA,email,Bronze,P1,0,Y,Y,SPARK,CRM Team,CONFIDENTIAL,GDPR,0.97,Email is mandatory; 0% nulls in profiling sample,"{""column"": ""email"", ""allowed_null_pct"": 0.0}"
DQ-002,Customer_Email_FormatCheck,Validity,REGEX_CHECK,ATTRIBUTE,customers,DELTA,email,Silver,P2,0.5,Y,N,SPARK,CRM Team,CONFIDENTIAL,GDPR,0.94,Email pattern detected; regex validation recommended,"{""column"": ""email"", ""pattern"": ""^[A-Za-z0-9._%+\\-]+@[A-Za-z0-9.\\-]+\\.[A-Za-z]{2,}$"", ""allowed_invalid_pct"": 0.5}"
DQ-003,Orders_PK_UniqueCheck,Uniqueness,DUPLICATE_CHECK,ATTRIBUTE,orders,DELTA,order_id,Bronze,P1,0,Y,Y,SPARK,Sales Team,INTERNAL,,0.99,Primary key; zero duplicates required,"{""key_columns"": [""order_id""], ""allowed_dup_pct"": 0.0}"
DQ-004,OrderLines_FK_IntegrityCheck,Integrity,REFERENTIAL_INTEGRITY,ATTRIBUTE,order_lines,DELTA,order_id,Silver,P1,0,Y,Y,SPARK,Sales Team,INTERNAL,,0.98,FK relationship to orders table,"{""child_key"": ""order_id"", ""parent_key"": ""order_id"", ""allowed_orphan_pct"": 0.0}"
DQ-005,Transactions_Amount_RangeCheck,Accuracy,RANGE_CHECK,ATTRIBUTE,transactions,DELTA,amount,Silver,P1,0,Y,Y,SPARK,Finance Team,RESTRICTED,SOX,0.96,Amount must be > 0,"{""column"": ""amount"", ""min_val"": 0.01, ""max_val"": 1000000}"
DQ-006,Sales_Fact_FreshnessCheck,Freshness,FRESHNESS_CHECK,ENTITY,sales_fact,DELTA,last_modified_dt,Gold,P1,0,Y,Y,SPARK,Analytics Team,INTERNAL,,0.95,Reporting SLA requires data < 4 hours stale,"{""ts_column"": ""last_modified_dt"", ""max_stale_hours"": 4.0}"
DQ-007,Contracts_DateConsistency,Consistency,TEMPORAL_CONSISTENCY,ATTRIBUTE,contracts,DELTA,"start_date,end_date",Silver,P2,0,Y,N,SPARK,Legal Team,CONFIDENTIAL,,0.93,end_date must be >= start_date,"{""start_col"": ""start_date"", ""end_col"": ""end_date""}"
DQ-008,Product_Status_DomainCheck,Validity,ALLOWED_VALUES_CHECK,ATTRIBUTE,products,DELTA,status,Silver,P2,0,Y,N,SPARK,Product Team,INTERNAL,,0.91,Low cardinality; domain: ACTIVE/INACTIVE/DISCONTINUED,"{""column"": ""status"", ""allowed_values"": [""ACTIVE"", ""INACTIVE"", ""DISCONTINUED""]}"
DQ-009,Sales_RowCount_Recon,Completeness,ROW_COUNT_CHECK,ENTITY,sales_fact,DELTA,,Gold,P1,0.1,Y,Y,SPARK,Analytics Team,INTERNAL,,0.98,Row count must match source within 0.1%,"{""source_count"": 0, ""target_count"": 0, ""allowed_variance_pct"": 0.1}"
DQ-010,Customer_Schema_Conformity,Conformity,SCHEMA_CONFORMITY,ENTITY,customers,DELTA,,Bronze,P2,0,Y,N,SPARK,Data Engineering,INTERNAL,,0.90,Schema must match target Delta definition,"{""expected_schema"": {""customer_id"": ""int64"", ""email"": ""object"", ""created_at"": ""datetime64[ns, UTC]""}}"
```

---

## 6. Enterprise DQ Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  SOURCE SYSTEMS  (ERP, CRM, Files, APIs, Streams)               │
└──────────────────────────┬───────────────────────────────────────┘
                           │ Ingest
┌──────────────────────────▼───────────────────────────────────────┐
│  BRONZE LAYER                                                    │
│  dq_runner.py  ←  metadata CSV  (WorkflowGroup = Bronze)        │
│  ─────────────────────────────────────────────────────────────  │
│  AVAILABILITY_CHECK   SCHEMA_CONFORMITY   NULL_CHECK (PK)       │
│  DUPLICATE_CHECK      REGEX_CHECK         FRESHNESS_CHECK       │
│  TIMELINESS_CHECK                                               │
│  ─────────────────────────────────────────────────────────────  │
│  P1 failure → FAIL pipeline (FailedPipelineInd = Y)             │
└──────────────────────────┬───────────────────────────────────────┘
                           │ Promote (Bronze P1 pass required)
┌──────────────────────────▼───────────────────────────────────────┐
│  SILVER LAYER                                                    │
│  dq_runner.py  ←  metadata CSV  (WorkflowGroup = Silver)        │
│  ─────────────────────────────────────────────────────────────  │
│  NULL_CHECK (all)   REFERENTIAL_INTEGRITY   RANGE_CHECK         │
│  ALLOWED_VALUES     TEMPORAL_CONSISTENCY    CUSTOM_SQL          │
└──────────────────────────┬───────────────────────────────────────┘
                           │ Promote (Silver P1 pass required)
┌──────────────────────────▼───────────────────────────────────────┐
│  GOLD LAYER                                                      │
│  dq_runner.py  ←  metadata CSV  (WorkflowGroup = Gold)          │
│  ─────────────────────────────────────────────────────────────  │
│  ROW_COUNT_CHECK   FRESHNESS_CHECK   DISTRIBUTION_ANOMALY       │
│  NULL_CHECK (KPI)  CUSTOM_SQL (reconciliation)                  │
└──────────────────────────┬───────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│  OBSERVABILITY                                                   │
│  Delta Results Table → Power BI / Fabric Dashboard              │
│  P1 failures → Teams / Email / PagerDuty alert                  │
│  dq_score_<entity>_<layer> metric → Monitoring                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 7. Orchestration & Monitoring

### 7.1 Pipeline Execution Pattern

```
Bronze Pipeline:
  Activity 1: Ingest source → Bronze Delta table
  Activity 2: Run Bronze DQ notebook (dq_runner.run_workflow(..., "Bronze"))
  Activity 3: Gate — IF any P1 failure THEN fail pipeline ELSE continue
  Activity 4: Trigger Silver pipeline

Silver Pipeline:
  Activity 1: Transform Bronze → Silver
  Activity 2: Run Silver DQ notebook
  Activity 3: Gate — IF P1 failure THEN fail pipeline
  Activity 4: Trigger Gold pipeline

Gold Pipeline:
  Activity 1: Aggregate Silver → Gold
  Activity 2: Run Gold DQ notebook
  Activity 3: Publish DQ score metrics to dashboard
```

### 7.2 DQ Results Delta Table Schema

```sql
CREATE TABLE dq_results (
    run_id          STRING,
    rule_id         STRING,
    rule_name       STRING,
    entity          STRING,
    attribute       STRING,
    dimension       STRING,
    check_type      STRING,
    passed          BOOLEAN,
    dq_score        DOUBLE,
    details         STRING,   -- JSON
    object_weight   STRING,
    workflow_group  STRING,
    evaluated_at    TIMESTAMP,
    platform        STRING
)
USING DELTA
PARTITIONED BY (workflow_group, DATE(evaluated_at));
```

### 7.3 Alerting Pattern

```python
# dq_alerts.py
def send_p1_alert(results: list[dict], entity: str, layer: str) -> None:
    """Send a Teams/Email alert for any P1 rule failures."""
    failures = [r for r in results
                if not r["passed"] and r.get("object_weight") == "P1"]
    if not failures:
        return
    channel = os.getenv("ALERT_CHANNEL", "TEAMS")
    webhook = os.getenv("ALERT_WEBHOOK_URL")
    if not webhook:
        raise EnvironmentError("ALERT_WEBHOOK_URL environment variable not set.")
    # Build alert payload — never include raw PII values
    payload = {
        "entity": entity,
        "layer": layer,
        "p1_failures": len(failures),
        "rules": [{"rule_id": r["rule_id"], "check": r["check"]} for r in failures],
    }
    # POST to webhook (Teams Adaptive Card / Email API / PagerDuty)
    ...
```

---

## 8. Governance & Extensibility Best Practices

| Practice | Guideline |
|----------|-----------|
| **Rule versioning** | Use `Version` field (SemVer). Bump minor on threshold change, major on logic change. |
| **Audit trail** | Log every rule execution with `run_id`, `rule_id`, `evaluated_at`, and `ApprovedBy`. |
| **Regulatory tagging** | Tag all PII/financial rules with `RegulatoryTag` (GDPR, SOX, PCI-DSS). |
| **Access control** | DQ result tables should inherit column masking from the source entity. |
| **Review cycles** | Set `ReviewCycleDays = 90` for P1 rules; pipeline alerts owner when due. |
| **Custom rule PRs** | Domain teams submit custom rules as metadata CSV rows via pull request. |
| **Baseline refresh** | Recompute `BaselineValue` / `BaselineStdDev` monthly for distribution checks. |
| **No PII in logs** | DQ result outputs must contain only counts, percentages, and hashed IDs. |

---

## 9. Platform-Specific Notebook Generation

When the user specifies a target platform, **all** platform-sensitive cells in
the generated notebook must use the patterns below for that platform.
Never use generic or mixed-platform code when a specific target is known.

### 9.1 Platform Decision Matrix

| Aspect | Microsoft Fabric | Azure Databricks | Azure Synapse Analytics | Local / PySpark |
|--------|-----------------|-----------------|------------------------|-----------------|
| SparkSession | `notebookutils` / implicit | `spark` implicit (DBR) | `spark` implicit | `SparkSession.builder` |
| Secret retrieval | `mssparkutils.credentials` | `dbutils.secrets` | Azure Key Vault linked service | `os.getenv()` |
| Read Delta table | `spark.read.format("delta").load("abfss://...")` or Lakehouse table ref | `spark.read.format("delta").load("dbfs:/...")` | `spark.read.synapsesql("pool.schema.table")` | `spark.read.format("delta").load(path)` |
| Write results | Lakehouse Delta table via `spark.write` | Unity Catalog Delta table | Synapse dedicated pool via `spark.write.synapsesql()` | Local Delta / Parquet |
| File system | `abfss://container@account.dfs.core.windows.net/` | `dbfs:/` or `abfss://` | `abfss://` (ADLS Gen2) | Local path or `s3a://` |
| Notebook params | `notebookutils.notebook.getArgument()` | `dbutils.widgets` | Pipeline parameters via `getArgument()` | CLI args / env vars |
| Pipeline trigger | Fabric Data Pipeline (notebook activity) | Databricks Workflow (notebook task) | Synapse Pipeline (notebook activity) | CLI / Airflow |
| Alerting | Power Automate / Teams webhook | Databricks Notifications / Teams webhook | Logic Apps / Teams webhook | Email / Teams webhook |
| Catalog | Fabric OneLake / Lakehouse catalog | Unity Catalog (`catalog.schema.table`) | Synapse Lake Database | Hive metastore / glue |

---

### 9.2 Microsoft Fabric — Platform-Specific Cell Templates

**Cell 2 – Imports & Platform Bootstrap (Fabric)**
```python
# Platform: Microsoft Fabric
import os
from notebookutils import mssparkutils  # available in all Fabric notebooks

PLATFORM = "FABRIC"
print(f"Platform : {PLATFORM}")
print(f"Workspace: {mssparkutils.env.getWorkspaceName()}")
print(f"Notebook : {mssparkutils.env.getJobId()}")
```

**Cell 3 – Config & Secret Retrieval (Fabric)**
```python
# Retrieve secrets from Azure Key Vault via mssparkutils
KEY_VAULT_NAME   = os.getenv("KEY_VAULT_NAME")  # set as pipeline parameter
STORAGE_ACCOUNT  = mssparkutils.credentials.getSecret(KEY_VAULT_NAME, "storage-account-name")
LAKEHOUSE_PATH   = f"abfss://bronze@{STORAGE_ACCOUNT}.dfs.core.windows.net"

# Metadata CSV location (relative to Lakehouse Files)
METADATA_CSV     = f"{LAKEHOUSE_PATH}/dq_metadata/dq_rules.csv"
ENTITY_NAME      = mssparkutils.notebook.getArgument("entity_name", "customers")
WORKFLOW_GROUP   = mssparkutils.notebook.getArgument("workflow_group", "Bronze")
```

**Cell 4 – Read Source Entity (Fabric)**
```python
# Option A: Read from Lakehouse Delta table (preferred for managed tables)
df = spark.read.format("delta").load(f"{LAKEHOUSE_PATH}/{ENTITY_NAME}")

# Option B: Read from Lakehouse shortcut / mounted path
# df = spark.sql(f"SELECT * FROM {ENTITY_NAME}")

print(f"Loaded {df.count():,} rows from {ENTITY_NAME}")
```

**Cell 15 – Write DQ Results (Fabric)**
```python
import uuid
from datetime import datetime, timezone

results_df = spark.createDataFrame(all_results)
results_df = results_df.withColumn("run_id",        F.lit(str(uuid.uuid4())))\
                       .withColumn("platform",      F.lit(PLATFORM))\
                       .withColumn("workflow_group", F.lit(WORKFLOW_GROUP))

RESULTS_PATH = f"{LAKEHOUSE_PATH}/dq_results"
results_df.write.format("delta").mode("append").save(RESULTS_PATH)
print(f"DQ results written to Lakehouse Delta table: {RESULTS_PATH}")
```

**Cell 16 – Alerting (Fabric)**
```python
import requests, json, os

WEBHOOK_URL = mssparkutils.credentials.getSecret(KEY_VAULT_NAME, "teams-webhook-url")
p1_failures = [r for r in all_results if not r["passed"] and r.get("object_weight") == "P1"]

if p1_failures:
    card = {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "type": "AdaptiveCard", "version": "1.4",
                "body": [
                    {"type": "TextBlock", "size": "Large", "weight": "Bolder",
                     "text": f"⚠️ DQ P1 Failures — {ENTITY_NAME} ({WORKFLOW_GROUP})"},
                    {"type": "TextBlock",
                     "text": f"Failed checks: {len(p1_failures)}"},
                    {"type": "FactSet",
                     "facts": [{"title": r["rule_id"], "value": r["check"]}
                               for r in p1_failures]},
                ]
            }
        }]
    }
    requests.post(WEBHOOK_URL, json=card, timeout=10)
```

---

### 9.3 Azure Databricks — Platform-Specific Cell Templates

**Cell 2 – Imports & Platform Bootstrap (Databricks)**
```python
# Platform: Azure Databricks
import os

PLATFORM = "DATABRICKS"
RUNTIME  = os.getenv("DATABRICKS_RUNTIME_VERSION", "unknown")
print(f"Platform: {PLATFORM}  |  DBR: {RUNTIME}")

# dbutils is injected automatically in Databricks notebooks
# For .py files in Repos, import explicitly:
# from pyspark.dbutils import DBUtils; dbutils = DBUtils(spark)
```

**Cell 3 – Config & Secret Retrieval (Databricks)**
```python
# Retrieve secrets from Databricks Secret Scope (backed by Azure Key Vault)
SECRET_SCOPE     = dbutils.widgets.get("secret_scope")   # passed as job parameter
STORAGE_ACCOUNT  = dbutils.secrets.get(SECRET_SCOPE, "storage-account-name")
CATALOG_NAME     = dbutils.widgets.get("catalog_name")   # Unity Catalog
SCHEMA_NAME      = dbutils.widgets.get("schema_name")

BASE_PATH        = f"abfss://bronze@{STORAGE_ACCOUNT}.dfs.core.windows.net"
METADATA_CSV     = f"{BASE_PATH}/dq_metadata/dq_rules.csv"
ENTITY_NAME      = dbutils.widgets.get("entity_name")
WORKFLOW_GROUP   = dbutils.widgets.get("workflow_group")
```

**Cell 4 – Read Source Entity (Databricks)**
```python
# Option A: Unity Catalog managed table (preferred)
df = spark.read.table(f"{CATALOG_NAME}.{SCHEMA_NAME}.{ENTITY_NAME}")

# Option B: Delta path on ADLS Gen2
# df = spark.read.format("delta").load(f"{BASE_PATH}/{ENTITY_NAME}")

print(f"Loaded {df.count():,} rows from {CATALOG_NAME}.{SCHEMA_NAME}.{ENTITY_NAME}")
```

**Cell 15 – Write DQ Results (Databricks)**
```python
import uuid
from pyspark.sql import functions as F

results_df = spark.createDataFrame(all_results)
results_df = results_df.withColumn("run_id",        F.lit(str(uuid.uuid4())))\
                       .withColumn("platform",      F.lit(PLATFORM))\
                       .withColumn("workflow_group", F.lit(WORKFLOW_GROUP))

# Write to Unity Catalog Delta table
results_df.write.format("delta").mode("append")\
    .saveAsTable(f"{CATALOG_NAME}.dq_observability.dq_results")
print("DQ results written to Unity Catalog: dq_observability.dq_results")
```

**Cell 16 – Alerting (Databricks)**
```python
import requests

WEBHOOK_URL  = dbutils.secrets.get(SECRET_SCOPE, "teams-webhook-url")
p1_failures  = [r for r in all_results if not r["passed"] and r.get("object_weight") == "P1"]

if p1_failures:
    payload = {
        "text": (
            f"⚠️ **DQ P1 Failures** — Entity: `{ENTITY_NAME}` | "
            f"Layer: `{WORKFLOW_GROUP}` | "
            f"Failed: {len(p1_failures)} check(s)\n"
            + "\n".join(f"- `{r['rule_id']}` {r['check']}" for r in p1_failures)
        )
    }
    requests.post(WEBHOOK_URL, json=payload, timeout=10)
```

---

### 9.4 Azure Synapse Analytics — Platform-Specific Cell Templates

**Cell 2 – Imports & Platform Bootstrap (Synapse)**
```python
# Platform: Azure Synapse Analytics
import os
from notebookutils import mssparkutils  # available in Synapse notebooks

PLATFORM = "SYNAPSE"
print(f"Platform  : {PLATFORM}")
print(f"Workspace : {mssparkutils.env.getWorkspaceName()}")
```

**Cell 3 – Config & Secret Retrieval (Synapse)**
```python
# Retrieve secrets via Synapse linked Key Vault service
from azure.keyvault.secrets import SecretClient
from azure.identity import ManagedIdentityCredential

KEY_VAULT_URL    = os.getenv("KEY_VAULT_URL")   # set as Synapse global param
credential       = ManagedIdentityCredential()
kv_client        = SecretClient(vault_url=KEY_VAULT_URL, credential=credential)

STORAGE_ACCOUNT  = kv_client.get_secret("storage-account-name").value
SQL_POOL         = os.getenv("SYNAPSE_SQL_POOL", "mydedicatedpool")
BASE_PATH        = f"abfss://bronze@{STORAGE_ACCOUNT}.dfs.core.windows.net"
METADATA_CSV     = f"{BASE_PATH}/dq_metadata/dq_rules.csv"
ENTITY_NAME      = mssparkutils.notebook.getArgument("entity_name", "customers")
WORKFLOW_GROUP   = mssparkutils.notebook.getArgument("workflow_group", "Bronze")
```

**Cell 4 – Read Source Entity (Synapse)**
```python
# Option A: Lake database / external table (Spark pool)
df = spark.read.format("delta").load(f"{BASE_PATH}/{ENTITY_NAME}")

# Option B: Dedicated SQL Pool via Synapse connector
# df = spark.read.synapsesql(f"{SQL_POOL}.dbo.{ENTITY_NAME}")

print(f"Loaded {df.count():,} rows from {ENTITY_NAME}")
```

**Cell 15 – Write DQ Results (Synapse)**
```python
import uuid
from pyspark.sql import functions as F

results_df = spark.createDataFrame(all_results)
results_df = results_df.withColumn("run_id",        F.lit(str(uuid.uuid4())))\
                       .withColumn("platform",      F.lit(PLATFORM))\
                       .withColumn("workflow_group", F.lit(WORKFLOW_GROUP))

# Option A: Write to Lake Database Delta table (Spark pool)
RESULTS_PATH = f"{BASE_PATH}/dq_results"
results_df.write.format("delta").mode("append").save(RESULTS_PATH)

# Option B: Write to Dedicated SQL Pool
# results_df.write.synapsesql(f"{SQL_POOL}.dbo.dq_results", mode="append")
print(f"DQ results written to: {RESULTS_PATH}")
```

**Cell 16 – Alerting (Synapse)**
```python
import requests

WEBHOOK_URL = kv_client.get_secret("teams-webhook-url").value
p1_failures  = [r for r in all_results if not r["passed"] and r.get("object_weight") == "P1"]

if p1_failures:
    payload = {
        "text": (
            f"⚠️ DQ P1 Failures — {ENTITY_NAME} ({WORKFLOW_GROUP})\n"
            f"Platform: Synapse | Failed: {len(p1_failures)}\n"
            + "\n".join(f"• {r['rule_id']}: {r['check']}" for r in p1_failures)
        )
    }
    requests.post(WEBHOOK_URL, json=payload, timeout=10)
```

---

### 9.5 Local / Standalone PySpark — Platform-Specific Cell Templates

**Cell 2 – Imports & Platform Bootstrap (Local)**
```python
# Platform: Local / Standalone PySpark
import os
from pyspark.sql import SparkSession

PLATFORM = "LOCAL"
spark = (
    SparkSession.builder
    .appName("DQ-Coworker")
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
    .config("spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog")
    .getOrCreate()
)
print(f"Platform: {PLATFORM} | Spark: {spark.version}")
```

**Cell 3 – Config & Secret Retrieval (Local)**
```python
# All config from environment variables — never hardcode paths or secrets
BASE_PATH      = os.environ["DQ_BASE_PATH"]        # e.g. /data/lakehouse
METADATA_CSV   = os.environ["DQ_METADATA_CSV"]     # e.g. /config/dq_rules.csv
ENTITY_NAME    = os.environ["DQ_ENTITY_NAME"]
WORKFLOW_GROUP = os.environ.get("DQ_WORKFLOW_GROUP", "Bronze")
```

**Cell 4 – Read Source Entity (Local)**
```python
# Delta path (local filesystem or S3/ADLS)
df = spark.read.format("delta").load(f"{BASE_PATH}/{ENTITY_NAME}")
print(f"Loaded {df.count():,} rows from {ENTITY_NAME}")
```

**Cell 15 – Write DQ Results (Local)**
```python
import uuid
from pyspark.sql import functions as F

results_df = spark.createDataFrame(all_results)
results_df = results_df.withColumn("run_id",        F.lit(str(uuid.uuid4())))\
                       .withColumn("platform",      F.lit(PLATFORM))\
                       .withColumn("workflow_group", F.lit(WORKFLOW_GROUP))

RESULTS_PATH = os.path.join(BASE_PATH, "dq_results")
results_df.write.format("delta").mode("append").save(RESULTS_PATH)
print(f"DQ results written to: {RESULTS_PATH}")
```

---

### 9.6 Platform-Specific Generation Rules (Mandatory)

Apply these rules unconditionally whenever a platform target is set:

1. **SparkSession** — never call `SparkSession.builder` in Fabric, Synapse, or
   Databricks notebooks; the session is injected. Only call it in LOCAL mode.

2. **Secrets** — use the platform-native secret API:
   - Fabric → `mssparkutils.credentials.getSecret(kv_name, secret_key)`
   - Databricks → `dbutils.secrets.get(scope, key)`
   - Synapse → Azure Key Vault SDK with `ManagedIdentityCredential`
   - Local → `os.environ["SECRET_KEY"]` (fail loudly if absent)

3. **File paths** — always use `abfss://` URIs for ADLS Gen2 on Fabric/Synapse/
   Databricks. Use `dbfs:/` only for Databricks-local storage. Never use
   Windows-style paths or relative paths in cloud notebooks.

4. **Notebook parameters** — use the platform-native parameter API:
   - Fabric / Synapse → `mssparkutils.notebook.getArgument(name, default)`
   - Databricks → `dbutils.widgets.get(name)` (declare widget first)
   - Local → `os.environ.get(name, default)`

5. **Table references** — qualify with catalog/schema for Databricks Unity
   Catalog; use Lakehouse table names for Fabric; use SQL Pool schema for
   Synapse dedicated pool; use Hive metastore names for local PySpark.

6. **Results write** — use `spark.write.format("delta")` for Fabric, Synapse
   (Spark pool), and local. Use `.saveAsTable()` with Unity Catalog for
   Databricks. Never use `.write.synapsesql()` outside Synapse.

7. **Imports** — guard platform-specific imports:
   ```python
   if PLATFORM == "FABRIC":
       from notebookutils import mssparkutils
   elif PLATFORM == "DATABRICKS":
       pass  # dbutils injected automatically
   elif PLATFORM == "SYNAPSE":
       from azure.keyvault.secrets import SecretClient
       from azure.identity import ManagedIdentityCredential
   ```

8. **Magic commands** — Fabric and Databricks support `%run` and `%pip`;
   Synapse supports `%%configure`. Never include magic commands in LOCAL mode
   notebooks intended for vanilla PySpark or pytest.

9. **Metadata CSV location** — default paths per platform:
   | Platform | Default metadata path |
   |----------|-----------------------|
   | Fabric | `abfss://<container>@<account>.dfs.core.windows.net/dq_metadata/dq_rules.csv` |
   | Databricks | `abfss://<container>@<account>.dfs.core.windows.net/dq_metadata/dq_rules.csv` or Unity Catalog volume |
   | Synapse | `abfss://<container>@<account>.dfs.core.windows.net/dq_metadata/dq_rules.csv` |
   | Local | `$DQ_METADATA_CSV` environment variable |

10. **Cell 1 title** — always include the platform name in the notebook title
    cell so readers know instantly which platform the notebook targets:
    ```
    # DQ Notebook — <Entity> | <WorkflowGroup> | Platform: <PLATFORM>
    Generated: <timestamp>
    ```

<!-- Contains AI-generated edits. -->