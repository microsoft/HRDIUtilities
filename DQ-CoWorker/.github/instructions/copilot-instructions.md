---
applyTo: "**"
---

# DQ-Coworker – GitHub Copilot Workspace Instructions

## File Annotation

Add a comment at the end of every file you create or modify: `Contains AI-generated edits.`
- Python files: `# Contains AI-generated edits.`
- SQL files: `-- Contains AI-generated edits.`
- Markdown / YAML / CSV: `<!-- Contains AI-generated edits. -->`
- Notebooks (.ipynb): add a markdown cell at the end with `> Contains AI-generated edits.`

---

## Project Purpose

This workspace implements the **DQ-Coworker** — an intelligent Data Quality
framework for enterprise data platforms. All code, notebooks, and metadata
produced here must align with the DQ-Coworker architecture documented in
`.github/prompts/DQSkillRecommender.prompts.md.prompt.md`.

When a user asks you to recommend, design, generate, review, or execute any
Data Quality checks, **always consult the DQSkillRecommender prompt** for
dimension definitions, threshold guidance, metadata schema, and code patterns.

---

## Architecture Context

This project operates across three data layers. Always respect layer boundaries:

| Layer | Role | DQ Focus |
|-------|------|----------|
| **Bronze** | Raw ingestion | Availability, Completeness (keys), Validity (format), Uniqueness, Freshness, Timeliness |
| **Silver** | Cleansed / transformed | Accuracy, Consistency, Referential Integrity, Conformity, full Completeness |
| **Gold** | Analytical / reporting | Accuracy (reconciliation), Freshness (SLA), Distribution drift, Cross-system Consistency |

Never place Silver or Gold DQ logic in the Bronze layer, and never skip Bronze
checks before promoting data to Silver.

---

## DQ Metadata Schema Rules

When generating or modifying DQ metadata (CSV, Delta table, or dict):

1. Every rule **must** have: `RuleID`, `RuleName`, `DQDimension`, `RuleType`,
   `Entity`, `EntityType`, `WorkflowGroup`, `ObjectWeight`, `IsActive`.
2. Auto-derive where possible: `RuleLevel`, `DataType`, `IsNullable`,
   `IsPrimaryKey`, `IsForeignKey`, `LayerTarget`, `GeneratedBy`,
   `GeneratedTimestamp`.
3. Set `FailedPipelineInd = Y` only for P1 rules on primary keys, financial
   fields, or regulatory-tagged columns.
4. Always populate `AIConfidenceScore` and `AIRecommendationReason` for any
   AI-generated rule.
5. Use `AllowedVariance = 0` as the default; only increase after explicit
   human approval.
6. Valid `ObjectWeight` values: `P1` (critical), `P2` (required), `P3` (optional).
7. Valid `WorkflowGroup` values: `Bronze`, `Silver`, `Gold`, or a custom domain name.

---

## Code Generation Standards

### Python

- Follow `.github/python-coding.instructions.md` (snake_case, PEP 8, type hints, docstrings).
- All DQ validation functions **must** be modular, parameterised, and return a
  standard result dict with keys:
  `dimension`, `check`, `entity`, `attribute`, `passed`, `details`, `evaluated_at`.
- Use the function signatures from `dq_functions.py` as the canonical pattern.
- Functions must be **platform-agnostic**: support both Pandas DataFrames and
  PySpark DataFrames where feasible. Use `isinstance(df, pd.DataFrame)` guards.
- Target compatibility: **Microsoft Fabric**, **Azure Synapse**, **Databricks**,
  and standalone **PySpark**.
- Never hardcode connection strings, credentials, storage paths, or workspace IDs.
  Use parameters or environment variables.
- All custom SQL injected by users must be validated for syntax before execution.
  Never execute untrusted raw SQL strings directly — parameterise or validate first.

### SQL

- Follow `.github/general-coding.instructions.md`.
- Use `NULLIF` to guard against division-by-zero in percentage calculations.
- Prefer `COUNT(*) FILTER (WHERE ...)` syntax for Spark SQL / Fabric SQL.
- Always alias computed columns clearly (e.g., `AS null_pct`, `AS dup_count`).

### Notebooks

- Structure every generated DQ notebook using the 17-cell sequence defined in
  Section 7 of the DQSkillRecommender prompt.
- Cell 1 must be a Markdown title cell with: entity name, WorkflowGroup,
  platform target, and generation timestamp.
- Cell 2 must auto-detect the execution platform
  (Fabric / Databricks / Synapse / local) and set `PLATFORM` variable.
- Always include a results aggregation cell that computes an overall **DQ Score**
  as `passed_checks / total_checks * 100`.
- Always include a final Markdown summary cell with pass/fail statistics.

---

## Human-in-the-Loop Rules

When presenting DQ check recommendations to a user:

1. Present checks **one entity at a time**, grouped by DQ dimension.
2. Use the structured recommendation format:
   ```
   Entity    : <name>
   Attribute : <col>     Dimension : <dimension>
   Rule      : <RuleName>
   Reason    : <why recommended>
   Threshold : <value>   Severity  : P1 / P2 / P3
   [APPROVE] [REJECT] [MODIFY THRESHOLD] [ADD CUSTOM LOGIC]
   ```
3. **Never** generate the final metadata CSV or notebook without at least one
   explicit human approval.
4. If a check is rejected, ask for the rejection reason and record it in
   `AIRejectionReason`.
5. If a user modifies a threshold, confirm the change and update the metadata
   row before moving to the next check.
6. If a user provides custom SQL or Python logic, validate syntax and confirm
   acceptance before incorporating.
7. Summarise `approved / rejected / modified` counts before emitting output.

---

## DQ Dimension Mapping Shortcuts

When analysing a column, apply these automatic rules before asking the user:

| Column Trait | Recommended Dimensions |
|---|---|
| Primary key | Uniqueness, Completeness, Validity |
| Foreign key | Integrity, Referential Integrity |
| NOT NULL constraint | Completeness |
| Timestamp / date column | Timeliness, Freshness |
| Numeric (amount, quantity) | Accuracy (range), Validity |
| Low-cardinality categorical | Validity (allowed values) |
| Email / phone / postal pattern | Validity (regex) |
| PII / financial / regulatory | Completeness, Validity, Accuracy (P1) |
| Date-range pair (start / end) | Consistency (temporal) |
| High-cardinality identifier | Uniqueness |

---

## Security & Governance

- **Never** log, display, or store raw PII values in DQ result outputs.
  Log counts and percentages only.
- Tag all rules touching PII or regulated data with appropriate
  `DataClassification` and `RegulatoryTag` fields.
- Validate all user-supplied regex patterns are safe (no ReDoS risk) before
  compiling.
- Do not generate code that bypasses row-level security, column masking, or
  workspace access controls.
- When generating connection code, always use managed identity / service
  principal patterns — never username/password in code.

---

## Observability & Alerting

- Every P1 rule failure must trigger an alert. Default `AlertChannel = Teams`.
- Write DQ results to a persistent Delta table after each run for trending.
- Enable `TrendingEnabled = Y` by default for all P1 and P2 rules.
- Always emit a DQ score metric keyed as `dq_score_<entity>_<layer>`.

---

## Output Formats

| Requested Output | Format |
|---|---|
| DQ metadata | CSV with headers matching the metadata schema in DQSkillRecommender prompt |
| Validation library | Python module `dq_functions.py` with functions per Section 5.1 |
| DQ runner | Python module `dq_runner.py` with dispatch router per Section 5.2 |
| Notebook | `.ipynb` following the 17-cell structure in Section 7 |
| Architecture diagram | ASCII art aligned with Section 8.1 |
| DQ results | JSON array of result dicts, one per rule executed |

<!-- Contains AI-generated edits. -->
