# DQ Rule Recommender — Wiki

> **Skill:** `dq-rule-recommender`  
> **Role:** Intelligent Data Quality framework agent that recommends, designs, generates, and reviews DQ checks for enterprise data platforms across Bronze / Silver / Gold layers.

---

## Table of Contents

1. [Overview](#overview)
2. [Standard DQ Dimensions](#standard-dq-dimensions)
3. [Recommendation Engine](#recommendation-engine)
4. [Human-in-the-Loop Workflow](#human-in-the-loop-workflow)
5. [DQ Metadata Schema](#dq-metadata-schema)
6. [Layer-Based Check Placement](#layer-based-check-placement)
7. [Rule-to-Code Generation (Summary)](#rule-to-code-generation-summary)
8. [Enterprise Architecture & Best Practices](#enterprise-architecture--best-practices)
9. [Invocation Examples](#invocation-examples)

---

## Overview

The **DQ Rule Recommender** is an AI-powered agent that analyses a dataset's schema and sample data, maps columns to applicable Data Quality dimensions, scores checks by business criticality, and produces:

- Structured DQ recommendations for human review
- A DQ Metadata CSV (`dq_rules.csv`) ready for pipeline execution
- Executable Jupyter/Fabric/Databricks/Synapse notebooks

It follows industry-standard DQ dimensions and supports all major enterprise platforms: **Microsoft Fabric**, **Azure Synapse Analytics**, **Azure Databricks**, and **local PySpark**.

---

## Standard DQ Dimensions

For every dataset or attribute the agent evaluates all applicable dimensions below.

### 1. Completeness

Degree to which required data values are present and non-null.

| Check Type | Description |
|------------|-------------|
| Null / blank count | Per-column null and empty-string detection |
| Mandatory field coverage | Rate of populated required fields |
| Row count vs. expected | Source vs. target row reconciliation |
| Partial record detection | Key fields populated, others empty |

**Thresholds**

| Priority | Null % Allowed |
|----------|---------------|
| P1 — Critical keys | 0 % |
| P2 — Required fields | ≤ 1 % |
| P3 — Optional fields | ≤ 5 % |

**Severity:** P1 fields → FAIL pipeline. P2 → WARNING. P3 → INFO log.

**Best Practices**
- Mark primary/foreign keys and mandatory business fields as P1.
- Run completeness checks at Bronze ingestion before any transformation.
- Trend null rates over time to detect upstream feed degradation.

---

### 2. Accuracy

Degree to which data correctly represents the real-world entity or event.

| Check Type | Description |
|------------|-------------|
| Range / boundary | `age 0–120`, `amount ≥ 0` |
| Cross-system reconciliation | Source count = target count |
| Statistical distribution | Mean, stddev drift detection |
| Golden-record comparison | Validate against authoritative source |
| Lookup / reference validation | Value exists in reference table |

**Thresholds:** 0 % out-of-range for financial/regulatory data; ≤ 0.1 % for operational data.

**Best Practices**
- Define valid ranges from the business glossary or source system constraints.
- Automate statistical drift alerts using z-score or IQR methods.

---

### 3. Consistency

Data values are coherent across systems, tables, or time periods with no contradictions.

| Check Type | Description |
|------------|-------------|
| Cross-table consistency | `order_total = SUM(order_lines.amount)` |
| Cross-system consistency | CRM customer count = ERP customer count |
| Temporal consistency | `end_date ≥ start_date` |
| Derived column consistency | Calculated field matches its formula |
| Encoding consistency | Gender stored uniformly as `M/F` |

**Thresholds:** 0 % tolerance for date/financial relationships.

---

### 4. Validity

Data conforms to defined formats, data types, business rules, and allowed value sets.

| Check Type | Description |
|------------|-------------|
| Regex pattern matching | Email, phone, postal code, ISO date |
| Allowed-value / domain | `status IN ('ACTIVE','INACTIVE')` |
| Data-type conformance | Numeric stored as text → parse failure |
| Business-rule validation | Invoice date ≤ payment due date |
| Checksum / Luhn | Credit card number validation |

**Thresholds:** 0 % for identifier/key fields; ≤ 0.5 % for free-text fields.

---

### 5. Uniqueness

Each data record or value exists only once where duplicates are not permitted.

| Check Type | Description |
|------------|-------------|
| Primary-key duplicates | Single-column PK duplicate detection |
| Composite-key uniqueness | Multi-column natural key check |
| Fuzzy duplicate detection | Name / address near-match (Levenshtein) |

**Thresholds:** 0 duplicates on primary/natural keys always.

---

### 6. Timeliness

Data is available within the required time window relative to the business event.

| Check Type | Description |
|------------|-------------|
| SLA arrival check | File/batch landed within N hours |
| Record age vs. SLA | Per-record event-to-ingest lag |
| Pipeline latency monitoring | End-to-end execution time |

---

### 7. Integrity

Data maintains structural and relational correctness, including foreign-key and hierarchical constraints.

| Check Type | Description |
|------------|-------------|
| Foreign-key existence | Every FK resolves to a valid PK |
| Parent-child relationships | Order lines have a matching order header |
| Orphan record detection | Child records with no parent |

**Thresholds:** 0 orphan records for transactional entities.

---

### 8. Conformity

Data adheres to a defined schema, naming convention, encoding standard, or industry specification (ISO, HL7, FHIR, EDI).

| Check Type | Description |
|------------|-------------|
| Schema column count / names | Expected columns present and named correctly |
| Data-type conformity | Column dtypes match target schema |
| Industry standard formats | ISO 8601 dates, ISO 4217 currency codes |
| File-format structure | CSV header row, delimiter consistency |

---

### 9. Referential Integrity

Every foreign-key value in a child entity resolves to a valid primary key in the parent entity, across tables or systems.

Additional checks include cross-database FK validation, surrogate key mapping completeness, and dimension-to-fact join coverage at the Gold layer.

---

### 10. Freshness

Data reflects the most recent state of the source within the agreed refresh cadence.

| Check Type | Description |
|------------|-------------|
| `MAX(last_modified)` | Compared to expected refresh timestamp |
| Partition / watermark currency | Most recent partition is current |
| Zero-record detection | Empty load may indicate stale feed |

---

### 11. Availability

Data is accessible to authorised consumers when needed.

| Check Type | Description |
|------------|-------------|
| Table / file existence | Entity reachable before pipeline starts |
| Row-count floor | Non-empty guard (count > 0) |
| Partition existence | Required partition present |
| Connection / endpoint health | Probe before heavy read |

---

## Recommendation Engine

### Agent Inputs

| Input Signal | How Used |
|---|---|
| Source system metadata | Derive entity type, keys, nullable flags |
| Schema analysis | Map columns to DQ dimensions |
| Sample data profiling | Detect nulls, distributions, formats |
| Business use case / context | Weight dimensions by criticality |
| Downstream consumption | Elevate Gold-layer accuracy/freshness SLAs |
| Data sensitivity | Enforce P1 checks on PII/financial fields |
| Historical DQ issues | Re-weight previously failing checks |
| Data layer (Bronze/Silver/Gold) | Route checks to correct execution layer |

### Recommendation Workflow

```
1. CONNECT    → Authenticate & read source schema + sample rows
2. PROFILE    → Run statistical profiling (null %, cardinality,
                 min/max, top-N values, format detection)
3. CLASSIFY   → Map each column to applicable DQ dimensions
4. SCORE      → Rank dimensions by business criticality &
                 historical issues
5. GENERATE   → Produce DQ metadata rows
6. PRESENT    → Show recommendations to human reviewer
7. ITERATE    → Apply approvals / overrides / custom rules
8. EMIT       → Write final DQ metadata CSV + generate notebooks
```

### Automatic Dimension Mapping Rules

| Column Signal | Dimensions Applied |
|---|---|
| `is_primary_key` | Uniqueness, Completeness, Validity |
| `is_foreign_key` | Integrity, Referential Integrity |
| `is_nullable_false` | Completeness |
| `is_timestamp` | Timeliness, Freshness |
| `is_numeric` | Accuracy, Validity (range checks) |
| `is_categorical` | Validity (allowed-values check) |
| `is_email_pattern` | Validity (regex check) |
| `is_pii` | Completeness, Validity, Accuracy |
| `high_cardinality` | Uniqueness |
| `low_cardinality` | Validity (domain check) |
| `has_historical_nulls` | Completeness |
| `is_date_range_pair` | Consistency |

---

## Human-in-the-Loop Workflow

### Interaction Modes

| Mode | Description |
|------|-------------|
| **Review** | Agent presents recommended checks; human approves / rejects each |
| **Reconfigure** | Human overrides threshold, allowed variance, severity |
| **Custom SQL** | Human injects bespoke SQL or Python validation logic |
| **Business Rule** | Human adds domain-specific rules outside standard dimensions |
| **Group / Workflow** | Human assigns checks to WorkflowGroups (Bronze/Silver/Gold) |
| **Bulk Approve** | Approve all P2/P3 checks with a single confirmation |

### Recommendation Presentation Format

Each recommendation is displayed in a structured card:

```
DQ-Coworker Recommendation
───────────────────────────────────────────────────────────
Entity    : <table_name>
Attribute : <column_name>        Dimension : <DQ Dimension>
Rule      : <RuleName>
Reason    : <Why this check was recommended>
Threshold : <default value>      Severity  : P1 / P2 / P3
───────────────────────────────────────────────────────────
[APPROVE] [REJECT] [MODIFY THRESHOLD] [ADD CUSTOM LOGIC]
```

### Conversation Guidelines

- Present checks one entity at a time, grouped by DQ dimension.
- Never proceed to metadata generation without at least one human approval.
- If a user rejects a check, ask for the reason and record it in `AIRejectionReason`.
- If a user adds custom SQL/Python, validate the syntax before accepting.
- Always summarise approved / rejected / modified counts before emitting the final metadata CSV.

---

## DQ Metadata Schema

### Core Fields

| Field | Description | Required? | Default |
|-------|-------------|-----------|---------|
| `RuleID` | Unique rule identifier (e.g., `DQ-001`) | Yes | Auto-generated |
| `RuleName` | Descriptive rule name | Yes | — |
| `RuleLevel` | `ENTITY` or `ATTRIBUTE` | No | Derived |
| `Entity` | Table / file / object name | Yes | — |
| `EntityType` | `TABLE`, `PARQUET`, `CSV`, `DELTA`, `ICEBERG`, `JSON` | Yes | — |
| `Attribute` | Column name (blank for entity-level rules) | Depends | — |
| `WorkflowGroup` | `Bronze` / `Silver` / `Gold` / Custom | Optional | All |
| `ObjectWeight` | Priority: `P1` / `P2` / `P3` | Optional | P3 |
| `AllowedVariance` | Acceptable failure threshold (%) | Optional | 0 |
| `IsActive` | Rule active flag (`Y`/`N`) | Optional | Y |
| `FailedPipelineInd` | Fail pipeline on violation (`Y`/`N`) | Optional | N |

### Auto-Derivable Fields

| Field | Description | Derivation |
|-------|-------------|------------|
| `DQDimension` | Completeness, Accuracy, etc. | From rule type |
| `RuleType` | `NULL_CHECK`, `REGEX`, `RANGE`, `FK`, `DUPLICATE`… | From check pattern |
| `DataType` | Source column data type | Schema metadata |
| `IsNullable` | Column nullable flag | Schema metadata |
| `IsPrimaryKey` | PK flag | Schema metadata |
| `IsForeignKey` | FK flag | Schema metadata / ERD |
| `GeneratedBy` | `HUMAN` / `AI` / `HYBRID` | Set at generation time |
| `GeneratedTimestamp` | UTC timestamp of rule creation | Auto |

### Execution Fields

| Field | Description | Default |
|-------|-------------|---------|
| `ExecutionEngine` | `SPARK`, `SQL`, `PYTHON`, `FABRIC` | SPARK |
| `ExecutionMode` | `BATCH` / `STREAMING` | BATCH |
| `SampleRate` | % of rows to sample for profiling checks | 100 |
| `FilterCondition` | WHERE clause to scope the check | — |
| `TimeoutSeconds` | Max execution time before alert | 300 |

### Monitoring & Observability Fields

| Field | Description |
|-------|-------------|
| `AlertChannel` | Teams / Email / PagerDuty / Slack |
| `AlertThresholdPct` | Failure % that triggers alert |
| `MetricName` | Metric key for observability dashboard |
| `TrendingEnabled` | Enable historical trending (`Y`/`N`) |
| `BaselineValue` | Statistical baseline for drift detection |
| `BaselineStdDev` | Baseline standard deviation |

### Audit & Governance Fields

| Field | Description |
|-------|-------------|
| `DataOwner` | Business owner of the entity |
| `DataSteward` | Data steward responsible for DQ |
| `Domain` | Business domain (Finance, HR, Sales…) |
| `DataClassification` | `PUBLIC` / `INTERNAL` / `CONFIDENTIAL` / `RESTRICTED` |
| `RegulatoryTag` | `GDPR` / `HIPAA` / `SOX` / `PCI-DSS` |
| `ApprovedBy` | Human approver of the rule |
| `ReviewCycleDays` | Days between mandatory rule reviews |
| `Version` | Rule version (SemVer: `1.0.0`) |

### AI Explainability Fields

| Field | Description |
|-------|-------------|
| `AIConfidenceScore` | 0–1 confidence of AI recommendation |
| `AIRecommendationReason` | Natural-language explanation of why the rule was suggested |
| `AIRejectionReason` | Reason if human rejected the recommendation |
| `AIModelVersion` | Version of the DQ-Coworker model used |
| `ProfiledSampleSize` | Number of rows profiled to derive the rule |

---

## Layer-Based Check Placement

| Layer | Purpose | DQ Dimensions Enforced |
|-------|---------|------------------------|
| **Bronze** | Raw ingestion quality | Availability, Completeness (key fields), Validity (format/type), Uniqueness (dedup), Freshness, Timeliness |
| **Silver** | Transformed business data | Accuracy, Consistency, Referential Integrity, Conformity, Integrity, full Completeness |
| **Gold** | Analytical / reporting | Accuracy (reconciliation), Freshness (SLA), Completeness (KPI fields), Distribution drift, Cross-system consistency |

```
SOURCE SYSTEMS
      │
      ▼ Ingestion
  BRONZE  →  Availability, Schema, Completeness (PK), Uniqueness, Validity, Freshness
      │
      ▼ Transform / Cleanse
  SILVER  →  Referential Integrity, Consistency, Accuracy, Conformity, full Completeness
      │
      ▼ Aggregate / Enrich
  GOLD    →  Accuracy (reconciliation), Freshness (SLA), Completeness (KPIs), Drift
```

---

## Rule-to-Code Generation (Summary)

After the human-in-the-loop review is complete, the agent emits:

1. **`dq_rules.csv`** — approved DQ metadata rows ready for execution.
2. **`dq_functions.py`** — reusable Python validation library (see [dq-rule-to-code wiki](./dq-rule-to-code.md)).
3. **`dq_runner.py`** — metadata-driven dispatch router.
4. **DQ Notebook** — 17-cell platform-targeted executable notebook.

---

## Enterprise Architecture & Best Practices

### Orchestration

- Execute DQ notebooks as pipeline activities (Fabric Pipeline / ADF / Databricks Workflows / Synapse Pipelines).
- Gate layer promotion: Bronze → Silver only if Bronze P1 checks pass.
- Store all DQ results in a central **DQ Results Delta table** for trending.
- Use `WorkflowGroup` to parallelise check execution per domain.
- Schedule Gold-layer checks at report refresh cadence.

### Observability & Monitoring

- Publish DQ scores (pass %, fail count) to a Power BI / Fabric Real-Time Dashboard.
- Set up alerting via Teams / Email / PagerDuty for P1 failures.
- Enable trending on all metric dimensions to detect gradual degradation.
- Store profiling baselines in a **DQ Baseline table** for anomaly detection.
- Audit all rule changes in a **DQ Rule Audit Log**.

### Governance

- Maintain all DQ metadata in a governed **DQ Metadata Lakehouse** table.
- Version-control rule definitions using SemVer (`Version` field).
- Enforce review cycles (`ReviewCycleDays`) via pipeline alerts.
- Tag rules with regulatory obligations (`RegulatoryTag`: GDPR, SOX, PCI-DSS).
- Use `DataClassification` to enforce access-controlled DQ results.
- Allow domain teams to contribute custom rules via pull requests.

---

## Invocation Examples

**Recommend checks for a new table:**
> "I have a new Delta table `sales.transactions` with columns: `transaction_id` (PK), `customer_id` (FK), `amount` (decimal), `status` (varchar), `created_at` (timestamp). It feeds the Gold reporting layer. Recommend DQ checks."

**Generate metadata CSV:**
> "Generate a DQ metadata CSV for the Silver layer checks on the `contracts` table with columns `start_date`, `end_date`, `customer_id`, `value`."

**Generate a DQ notebook:**
> "Generate a Fabric-compatible DQ notebook for Bronze ingestion checks on the `customers` Parquet file."

**Human-in-the-loop review:**
> "Show me the recommended DQ checks for `products` table one by one so I can approve or modify them."

**Add a custom rule:**
> "Add a custom SQL check: for the `orders` table, no order should have `amount > 0` with `status = 'CANCELLED'`."
