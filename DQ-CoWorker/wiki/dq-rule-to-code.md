# DQ Rule to Code — Wiki

> **Skill:** `dq-rule-to-code`  
> **Role:** Converts DQ metadata rules into executable notebooks, reusable Python validation libraries, and metadata-driven dispatch routers — fully adapted to a chosen enterprise platform (Microsoft Fabric, Azure Databricks, Azure Synapse Analytics, or local PySpark).

---

## Table of Contents

1. [Overview](#overview)
2. [Code Generation Inputs](#code-generation-inputs)
3. [Reusable Validation Library (dq_functions.py)](#reusable-validation-library-dq_functionspy)
4. [Metadata-Driven Dispatch Router (dq_runner.py)](#metadata-driven-dispatch-router-dq_runnerpy)
5. [Notebook Generation Strategy](#notebook-generation-strategy)
6. [Sample Metadata CSV](#sample-metadata-csv)
7. [Enterprise DQ Architecture](#enterprise-dq-architecture)
8. [Orchestration & Monitoring](#orchestration--monitoring)
9. [Governance & Extensibility](#governance--extensibility)
10. [Platform-Specific Notebook Generation](#platform-specific-notebook-generation)

---

## Overview

The **DQ Rule to Code** generator takes the DQ metadata CSV produced by the [dq-rule-recommender](./dq-rule-recommender.md) and transforms it into production-ready, platform-native artifacts:

| Artifact | Description |
|----------|-------------|
| `dq_functions.py` | Reusable Python validation library — 14 parameterised check functions |
| `dq_runner.py` | Metadata-driven execution router that dispatches rules to functions |
| DQ Notebook | 17-cell structured notebook with platform-native connection, execution, and alerting cells |

> **Critical:** When a `Platform target` is provided (`FABRIC`, `DATABRICKS`, `SYNAPSE`, or `LOCAL`), every generated cell uses only the APIs and patterns for that platform. Platform code is never mixed in the same notebook.

---

## Code Generation Inputs

| Input | Description |
|-------|-------------|
| DQ Metadata CSV | Rows conforming to the DQ metadata schema |
| Entity name | Table / file / Delta path to validate |
| WorkflowGroup | `Bronze` / `Silver` / `Gold` — determines which rules to include |
| **Platform target** | `FABRIC` / `DATABRICKS` / `SYNAPSE` / `LOCAL` |
| ObjectWeight filter | `P1`-only, `P1+P2`, or `ALL` |
| Custom rule snippets | User-supplied SQL or Python to embed |

---

## Reusable Validation Library (`dq_functions.py`)

All 14 functions share the same canonical result contract via the `_result()` helper.

### Result Contract

Every check function returns a dict with this shape:

```python
{
    "dimension":    str,   # DQ dimension name
    "check":        str,   # Rule type constant
    "entity":       str,   # Logical entity name
    "attribute":    str,   # Column or "SCHEMA" / "ROW_COUNT"
    "passed":       bool,  # Whether the check passed
    "details":      dict,  # Counts, percentages, thresholds
    "evaluated_at": str,   # UTC ISO-8601 timestamp
}
```

### Function Catalogue

| # | Function | Dimension | Rule Type |
|---|----------|-----------|-----------|
| 1 | `check_null(df, entity, column, allowed_null_pct)` | Completeness | `NULL_CHECK` |
| 2 | `check_duplicate(df, entity, key_columns, allowed_dup_pct)` | Uniqueness | `DUPLICATE_CHECK` |
| 3 | `check_referential_integrity(child_df, parent_df, entity, child_key, parent_key, allowed_orphan_pct)` | Integrity | `REFERENTIAL_INTEGRITY` |
| 4 | `check_range(df, entity, column, min_val, max_val, allowed_invalid_pct)` | Accuracy | `RANGE_CHECK` |
| 5 | `check_regex(df, entity, column, pattern, allowed_invalid_pct)` | Validity | `REGEX_CHECK` |
| 6 | `check_allowed_values(df, entity, column, allowed_values, allowed_invalid_pct)` | Validity | `ALLOWED_VALUES_CHECK` |
| 7 | `check_freshness(df, entity, ts_column, max_stale_hours)` | Freshness | `FRESHNESS_CHECK` |
| 8 | `check_timeliness(df, entity, ts_column, max_lag_hours)` | Timeliness | `TIMELINESS_CHECK` |
| 9 | `check_distribution_anomaly(df, entity, column, baseline_mean, baseline_std, z_threshold)` | Accuracy | `DISTRIBUTION_ANOMALY` |
| 10 | `check_row_count(source_count, target_count, entity, allowed_variance_pct)` | Completeness | `ROW_COUNT_CHECK` |
| 11 | `check_schema_conformity(df, entity, expected_schema)` | Conformity | `SCHEMA_CONFORMITY` |
| 12 | `check_temporal_consistency(df, entity, start_col, end_col, allowed_invalid_pct)` | Consistency | `TEMPORAL_CONSISTENCY` |
| 13 | `check_availability_spark(spark, entity_path, entity_type)` | Availability | `AVAILABILITY_CHECK` |
| 14 | `check_custom_sql(spark_or_conn, entity, rule_name, sql, expected_count, allowed_variance_pct)` | Custom | `CUSTOM_SQL` |

#### Security Notes

- **`check_regex`** — rejects patterns with nested unbounded quantifiers to prevent ReDoS attacks.
- **`check_custom_sql`** — SQL must be pre-validated and parameterised; never pass raw user input.
- **`check_availability_spark`** — catches all exceptions and returns a `passed=False` result with the error string (no sensitive path leakage in logs).

### Key Function Signatures

```python
# 1. Null check
check_null(df, entity="customers", column="email", allowed_null_pct=0.0)

# 4. Range check
check_range(df, entity="transactions", column="amount", min_val=0.01, max_val=1_000_000)

# 5. Regex check (ReDoS-safe)
check_regex(df, entity="customers", column="email",
            pattern=r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

# 9. Distribution anomaly (z-score)
check_distribution_anomaly(df, entity="sales", column="revenue",
                           baseline_mean=50000.0, baseline_std=5000.0, z_threshold=3.0)

# 14. Custom SQL
check_custom_sql(spark, entity="orders", rule_name="CancelledWithAmount",
                 sql="SELECT * FROM orders WHERE amount > 0 AND status = 'CANCELLED'",
                 expected_count=0)
```

---

## Metadata-Driven Dispatch Router (`dq_runner.py`)

`dq_runner.py` reads the DQ metadata CSV, filters active rules by `WorkflowGroup` and `ObjectWeight`, and dispatches each rule to the correct `dq_functions.py` function.

### Key Functions

| Function | Description |
|----------|-------------|
| `load_metadata(csv_path)` | Load and validate the DQ metadata CSV; returns only `IsActive = Y` rows |
| `execute_rule(rule, context)` | Dispatch a single metadata row to its validation function |
| `run_workflow(metadata_csv, workflow_group, context, object_weight_filter)` | Execute all active rules for a given layer |
| `compute_dq_score(results, entity, layer)` | Aggregate pass/fail into a DQ score percentage |

### Dispatch Map

```python
RULE_DISPATCH = {
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
```

### DQ Score Output

```python
{
    "metric_key":    "dq_score_customers_bronze",
    "total_checks":  10,
    "passed_checks": 9,
    "failed_checks": 1,
    "dq_score":      90.0
}
```

---

## Notebook Generation Strategy

### 17-Cell Notebook Template

Every generated DQ notebook must contain exactly these 17 cells:

| Cell | Type | Purpose |
|------|------|---------|
| 1 | Markdown | Title: entity, WorkflowGroup, platform, generated timestamp |
| 2 | Python | Imports + platform bootstrap (`PLATFORM` variable) |
| 3 | Python | Config: load metadata CSV, entity / layer / path parameters |
| 4 | Python | Source connection: read entity into Spark or Pandas DataFrame |
| 5 | Python | Schema conformity pre-check (always runs first) |
| 6 | Python | Availability + row-count check |
| 7 | Python | Completeness checks (loop over `NULL_CHECK` rules) |
| 8 | Python | Uniqueness / duplicate checks |
| 9 | Python | Validity checks (`REGEX`, `ALLOWED_VALUES`, `RANGE`) |
| 10 | Python | Referential integrity checks |
| 11 | Python | Consistency checks (`TEMPORAL_CONSISTENCY`, cross-table) |
| 12 | Python | Freshness / Timeliness checks |
| 13 | Python | Custom SQL / business-rule checks |
| 14 | Python | Results aggregation + DQ score calculation |
| 15 | Python | Write results to DQ results Delta table |
| 16 | Python | Alerting — Teams / Email for P1 failures |
| 17 | Markdown | Summary report: pass/fail counts, DQ score, failed rules |

### Platform Detection (Cell 2)

```python
import os

def detect_platform() -> str:
    if os.getenv("MSSPARKUTILS_VERSION"):      return "FABRIC"
    if os.getenv("DATABRICKS_RUNTIME_VERSION"): return "DATABRICKS"
    if os.getenv("SYNAPSE_ENVIRONMENT"):        return "SYNAPSE"
    return "LOCAL"

PLATFORM = os.getenv("EXECUTION_PLATFORM", detect_platform())
print(f"Execution platform: {PLATFORM}")
```

### Results Aggregation (Cell 14)

```python
from dq_runner import compute_dq_score

score_summary = compute_dq_score(all_results, entity=ENTITY_NAME, layer=WORKFLOW_GROUP)
print(f"DQ Score  : {score_summary['dq_score']}%")
print(f"Passed    : {score_summary['passed_checks']} / {score_summary['total_checks']}")
print(f"Failed    : {score_summary['failed_checks']}")
```

---

## Sample Metadata CSV

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

## Enterprise DQ Architecture

```
SOURCE SYSTEMS  (ERP, CRM, Files, APIs, Streams)
        │ Ingest
        ▼
┌──────────────────────────────────────────────────────────────┐
│  BRONZE LAYER  (WorkflowGroup = Bronze)                      │
│  AVAILABILITY_CHECK  SCHEMA_CONFORMITY  NULL_CHECK (PK)      │
│  DUPLICATE_CHECK     REGEX_CHECK        FRESHNESS_CHECK      │
│  TIMELINESS_CHECK                                            │
│  P1 failure → FAIL pipeline (FailedPipelineInd = Y)          │
└──────────────────────────────┬───────────────────────────────┘
                               │ Promote (Bronze P1 pass required)
                               ▼
┌──────────────────────────────────────────────────────────────┐
│  SILVER LAYER  (WorkflowGroup = Silver)                      │
│  NULL_CHECK (all)  REFERENTIAL_INTEGRITY  RANGE_CHECK        │
│  ALLOWED_VALUES    TEMPORAL_CONSISTENCY   CUSTOM_SQL         │
└──────────────────────────────┬───────────────────────────────┘
                               │ Promote (Silver P1 pass required)
                               ▼
┌──────────────────────────────────────────────────────────────┐
│  GOLD LAYER  (WorkflowGroup = Gold)                          │
│  ROW_COUNT_CHECK  FRESHNESS_CHECK  DISTRIBUTION_ANOMALY      │
│  NULL_CHECK (KPI)  CUSTOM_SQL (reconciliation)               │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│  OBSERVABILITY                                               │
│  Delta Results Table → Power BI / Fabric Dashboard           │
│  P1 failures → Teams / Email / PagerDuty alert               │
│  dq_score_<entity>_<layer> → Monitoring metric               │
└──────────────────────────────────────────────────────────────┘
```

---

## Orchestration & Monitoring

### Pipeline Execution Pattern

```
Bronze Pipeline:
  1. Ingest source → Bronze Delta table
  2. Run Bronze DQ notebook  (dq_runner.run_workflow(..., "Bronze"))
  3. Gate — IF any P1 failure → fail pipeline ELSE continue
  4. Trigger Silver pipeline

Silver Pipeline:
  1. Transform Bronze → Silver
  2. Run Silver DQ notebook
  3. Gate — IF P1 failure → fail pipeline
  4. Trigger Gold pipeline

Gold Pipeline:
  1. Aggregate Silver → Gold
  2. Run Gold DQ notebook
  3. Publish DQ score metrics to dashboard
```

### DQ Results Delta Table Schema

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

### Alerting

P1 failures trigger an alert via the configured channel (Teams / Email / PagerDuty). The alert payload contains only counts, rule IDs, and check names — never raw PII values or sensitive data.

```python
# Environment variables required
ALERT_WEBHOOK_URL  # Teams incoming webhook URL (from Key Vault)
```

---

## Governance & Extensibility

| Practice | Guideline |
|----------|-----------|
| **Rule versioning** | Use `Version` (SemVer). Bump minor on threshold change, major on logic change. |
| **Audit trail** | Log every execution with `run_id`, `rule_id`, `evaluated_at`, `ApprovedBy`. |
| **Regulatory tagging** | Tag all PII/financial rules with `RegulatoryTag` (GDPR, SOX, PCI-DSS). |
| **Access control** | DQ result tables inherit column masking from the source entity. |
| **Review cycles** | Set `ReviewCycleDays = 90` for P1 rules; pipeline alerts owner when due. |
| **Custom rule PRs** | Domain teams submit custom rules as metadata CSV rows via pull request. |
| **Baseline refresh** | Recompute `BaselineValue` / `BaselineStdDev` monthly for distribution checks. |
| **No PII in logs** | DQ outputs must contain only counts, percentages, and hashed IDs. |

---

## Platform-Specific Notebook Generation

### Platform Decision Matrix

| Aspect | Microsoft Fabric | Azure Databricks | Azure Synapse Analytics | Local / PySpark |
|--------|-----------------|-----------------|------------------------|-----------------|
| SparkSession | Implicit (`notebookutils`) | Implicit (DBR) | Implicit | `SparkSession.builder` |
| Secret retrieval | `mssparkutils.credentials.getSecret()` | `dbutils.secrets.get()` | Azure Key Vault SDK + Managed Identity | `os.environ["KEY"]` |
| Delta read | `spark.read.format("delta").load("abfss://...")` | `spark.read.table("catalog.schema.table")` | `spark.read.format("delta").load("abfss://...")` | `spark.read.format("delta").load(path)` |
| Write results | `spark.write.format("delta")` to Lakehouse | `.saveAsTable()` on Unity Catalog | `spark.write.format("delta")` to ADLS | `spark.write.format("delta")` |
| File system | `abfss://container@account.dfs.core.windows.net/` | `abfss://` or `dbfs:/` | `abfss://` (ADLS Gen2) | Local path |
| Notebook params | `mssparkutils.notebook.getArgument()` | `dbutils.widgets.get()` | `mssparkutils.notebook.getArgument()` | `os.environ.get()` |
| Alerting | Power Automate / Teams webhook | Databricks Notifications / Teams webhook | Logic Apps / Teams webhook | Email / Teams webhook |

### Microsoft Fabric

**Cell 2 — Bootstrap**
```python
from notebookutils import mssparkutils
PLATFORM = "FABRIC"
print(f"Workspace: {mssparkutils.env.getWorkspaceName()}")
```

**Cell 3 — Config & Secrets**
```python
KEY_VAULT_NAME  = os.getenv("KEY_VAULT_NAME")
STORAGE_ACCOUNT = mssparkutils.credentials.getSecret(KEY_VAULT_NAME, "storage-account-name")
LAKEHOUSE_PATH  = f"abfss://bronze@{STORAGE_ACCOUNT}.dfs.core.windows.net"
ENTITY_NAME     = mssparkutils.notebook.getArgument("entity_name", "customers")
WORKFLOW_GROUP  = mssparkutils.notebook.getArgument("workflow_group", "Bronze")
```

**Cell 4 — Read Source**
```python
df = spark.read.format("delta").load(f"{LAKEHOUSE_PATH}/{ENTITY_NAME}")
```

**Cell 15 — Write Results**
```python
results_df.write.format("delta").mode("append").save(f"{LAKEHOUSE_PATH}/dq_results")
```

**Cell 16 — Alert**
```python
WEBHOOK_URL = mssparkutils.credentials.getSecret(KEY_VAULT_NAME, "teams-webhook-url")
# SSRF guard: only allow HTTPS webhook URLs
if not WEBHOOK_URL.lower().startswith("https://"):
    print("[Cell 16] WARNING: Webhook URL must use HTTPS. Alert suppressed.")
else:
    try:
        resp = requests.post(WEBHOOK_URL, json=card, timeout=10)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"[Cell 16] Alert HTTP error: {e.response.status_code}.")
    except requests.exceptions.RequestException:
        # Do not print str(e) — exception message may contain the webhook URL.
        print("[Cell 16] WARNING: Alert could not be delivered (connection error).")
```

---

### Azure Databricks

**Cell 2 — Bootstrap**
```python
PLATFORM = "DATABRICKS"
RUNTIME  = os.getenv("DATABRICKS_RUNTIME_VERSION", "unknown")
# dbutils injected automatically
```

**Cell 3 — Config & Secrets**
```python
SECRET_SCOPE    = dbutils.widgets.get("secret_scope")
STORAGE_ACCOUNT = dbutils.secrets.get(SECRET_SCOPE, "storage-account-name")
CATALOG_NAME    = dbutils.widgets.get("catalog_name")
ENTITY_NAME     = dbutils.widgets.get("entity_name")
```

**Cell 4 — Read Source**
```python
df = spark.read.table(f"{CATALOG_NAME}.{SCHEMA_NAME}.{ENTITY_NAME}")
```

**Cell 15 — Write Results**
```python
results_df.write.format("delta").mode("append") \
    .saveAsTable(f"{CATALOG_NAME}.dq_observability.dq_results")
```

---

### Azure Synapse Analytics

**Cell 3 — Config & Secrets (Managed Identity)**
```python
from azure.keyvault.secrets import SecretClient
from azure.identity import ManagedIdentityCredential

credential      = ManagedIdentityCredential()
kv_client       = SecretClient(vault_url=os.getenv("KEY_VAULT_URL"), credential=credential)
STORAGE_ACCOUNT = kv_client.get_secret("storage-account-name").value
```

**Cell 4 — Read Source**
```python
# Option A: Lake database / external table
df = spark.read.format("delta").load(f"{BASE_PATH}/{ENTITY_NAME}")
# Option B: Dedicated SQL Pool
# df = spark.read.synapsesql(f"{SQL_POOL}.dbo.{ENTITY_NAME}")
```

---

### Local / Standalone PySpark

**Cell 2 — Bootstrap**
```python
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
```

**Cell 3 — Config (all from environment variables)**
```python
BASE_PATH      = os.environ["DQ_BASE_PATH"]
METADATA_CSV   = os.environ["DQ_METADATA_CSV"]
ENTITY_NAME    = os.environ["DQ_ENTITY_NAME"]
WORKFLOW_GROUP = os.environ.get("DQ_WORKFLOW_GROUP", "Bronze")
```

---

### Platform Generation Rules (Mandatory)

1. **SparkSession** — never call `SparkSession.builder` on Fabric, Synapse, or Databricks; the session is injected. Only use it in `LOCAL` mode.
2. **Secrets** — always use the platform-native secret API; never hardcode credentials.
3. **File paths** — use `abfss://` URIs for ADLS Gen2 on Fabric/Synapse/Databricks; `dbfs:/` only for Databricks-local storage; never Windows-style paths in cloud notebooks.
4. **Notebook params** — use the platform-native parameter API listed in the matrix above.
5. **Table references** — qualify with `catalog.schema.table` for Databricks Unity Catalog; Lakehouse table names for Fabric; SQL Pool schema for Synapse dedicated pool.
6. **Results write** — use `spark.write.format("delta")` for Fabric, Synapse (Spark pool), and local. Use `.saveAsTable()` with Unity Catalog for Databricks.
7. **No PII in outputs** — result tables must contain only counts, percentages, and hashed IDs.
8. **Cell 1 title** — always include the platform name:  
   `# DQ Notebook — <Entity> | <WorkflowGroup> | Platform: <PLATFORM>`

### Default Metadata CSV Paths

| Platform | Default path |
|----------|-------------|
| Fabric | `abfss://<container>@<account>.dfs.core.windows.net/dq_metadata/dq_rules.csv` |
| Databricks | `abfss://<container>@<account>.dfs.core.windows.net/dq_metadata/dq_rules.csv` or Unity Catalog volume |
| Synapse | `abfss://<container>@<account>.dfs.core.windows.net/dq_metadata/dq_rules.csv` |
| Local | `$DQ_METADATA_CSV` environment variable |
