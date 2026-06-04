---
applyTo: "**"
---

# DQ-Coworker – General Coding Standards

These standards apply to **all files** in this workspace. Language-specific
rules in `.github/python-coding.instructions.md` extend (not replace) these.

---

## Naming Conventions

| Construct | Convention | Example |
|-----------|-----------|---------|
| Constants | `ALL_CAPS` | `MAX_NULL_PCT = 5.0` |
| Variables / functions | `snake_case` | `check_null_rate` |
| Classes | `PascalCase` | `DQRuleRunner` |
| SQL aliases | `lower_snake_case` | `AS null_pct` |
| DQ Rule IDs | `DQ-NNN` | `DQ-001` |
| Metric keys | `dq_score_<entity>_<layer>` | `dq_score_customers_bronze` |

- Prefer descriptive, intent-revealing names over abbreviations.
- Avoid single-letter names except in short loop indices (`i`, `j`) or
  comprehensions where the meaning is unambiguous.

---

## Error Handling

- Use `try/except` (Python) or `try/catch` (TypeScript/JS) for all I/O,
  network, and external-system operations.
- Always catch specific exception types; never use bare `except:` or
  `catch (Exception)` without re-raising or logging.
- Return structured error dicts rather than raising in DQ validation functions
  so callers can aggregate results without aborting:
  ```python
  {"passed": False, "error": "Connection timeout", "dimension": "Availability"}
  ```
- Log errors with context (entity name, rule ID, timestamp). Never swallow
  exceptions silently.
- For pipeline-critical (P1) failures, always raise after logging so the
  orchestrator can halt the pipeline.

---

## Security

- **No hardcoded credentials, secrets, connection strings, or workspace IDs.**
  Use environment variables or a secrets manager (Azure Key Vault, Databricks
  Secrets, Fabric Key Vault reference).
- **Validate all user-supplied input** (SQL fragments, regex patterns, file
  paths) before use. Never pass raw user input to `eval()`, `exec()`, or
  directly into a SQL string.
- Guard regex patterns against ReDoS: reject patterns with unbounded nested
  quantifiers before compiling.
- Use parameterised queries or the DataFrame API for all data access; never
  use f-strings or `.format()` to build SQL with untrusted values.
- Do not log raw PII values. Log only counts, percentages, and hashed/masked
  identifiers.

---

## Code Quality & Style

- Keep functions small and single-purpose. If a function exceeds ~40 lines,
  consider splitting it.
- Avoid deep nesting (> 3 levels). Use early returns / guard clauses.
- Every public function must have a docstring / JSDoc comment describing:
  purpose, parameters, return value, and any raised exceptions.
- Delete dead code; do not comment it out and leave it.
- Do not add unrelated refactoring, style fixes, or feature additions in the
  same change — keep commits focused.

---

## SQL Standards

- Use `NULLIF(<expr>, 0)` to guard every division operation.
- Prefer `COUNT(*) FILTER (WHERE <condition>)` over nested `CASE WHEN` for
  Spark SQL / Fabric SQL aggregations.
- Always alias every computed column:
  ```sql
  ROUND(100.0 * null_count / NULLIF(total_rows, 0), 2) AS null_pct
  ```
- Qualify all column references with the table alias in multi-table queries.
- Use uppercase SQL keywords (`SELECT`, `FROM`, `WHERE`, `GROUP BY`).
- Format CTEs with one CTE per logical block; name them descriptively
  (`source_counts`, `null_rates`, not `cte1`, `cte2`).
- Never use `SELECT *` in production DQ checks — list columns explicitly.

---

## File & Module Organisation

- One logical concern per file. Do not mix DQ validation logic, configuration
  loading, and alerting in the same module.
- Canonical module names for this project:
  | Module | Purpose |
  |--------|---------|
  | `dq_functions.py` | Reusable, parameterised DQ validation functions |
  | `dq_runner.py` | Metadata-driven dispatch router |
  | `dq_profiler.py` | Schema and sample-data profiling utilities |
  | `dq_metadata.py` | Metadata CSV / Delta read-write helpers |
  | `dq_alerts.py` | Alerting integrations (Teams, Email, PagerDuty) |
  | `dq_config.py` | Environment-aware configuration loader |
- Place shared constants in `dq_config.py`; never scatter magic numbers across
  modules.

---

## Configuration & Environment

- All environment-specific values (paths, workspace IDs, catalog names,
  alert endpoints) must be externalised to environment variables or a config
  file loaded at runtime.
- Support at minimum these execution environments without code changes:
  **Microsoft Fabric**, **Azure Synapse**, **Databricks**, **local PySpark**.
- Use an `EXECUTION_PLATFORM` environment variable (or auto-detect) to switch
  platform-specific behaviour (e.g., Delta path vs. Lakehouse table reference).

---

## Testing & Validation

- Every DQ validation function must have at least one unit test covering:
  the passing case, the failing case, and the edge case (empty DataFrame,
  all-null column).
- Use `pytest` with `pytest-mock` for Python unit tests.
- Test data must be synthetic; never use real customer or production data in
  tests.
- Assert on the full result dict structure, not just the `passed` flag.

---

## Observability & Logging

- Use structured logging (JSON lines format) so log aggregators can parse
  fields without regex.
- Every DQ run must emit a log entry containing: `rule_id`, `entity`,
  `dimension`, `passed`, `evaluated_at`, and `dq_score`.
- P1 rule failures must emit an alert in addition to a log entry.
- Use the metric key pattern `dq_score_<entity>_<layer>` for all DQ score
  metrics published to monitoring dashboards.

---

## Version Control

- Write commit messages in imperative mood: `Add null check for customer_email`,
  not `Added` or `Adding`.
- Never commit secrets, generated Delta/Parquet data files, or notebook
  checkpoint folders (`.ipynb_checkpoints/`).
- Tag DQ metadata CSV releases with the version from the `Version` field
  (SemVer: `v1.0.0`).

<!-- Contains AI-generated edits. -->
