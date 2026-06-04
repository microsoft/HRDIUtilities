# dq-coworker

> **Intelligent Data Quality (DQ) co-worker** — recommend DQ checks for any dataset, then turn them into executable PySpark notebooks for Microsoft Fabric, Azure Databricks, Azure Synapse, or local Spark.

Designing DQ checks by hand is repetitive: you eyeball a schema, decide which dimensions matter (completeness, validity, uniqueness, …), pick thresholds, then write the same null-rate, range, and reference-integrity checks again. This plugin captures that workflow so you can go from a raw table to a metadata-driven, production-ready DQ notebook in a single conversation.

## What's inside

| Skill | Input | Output |
|---|---|---|
| [`dq-rule-recommender`](skills/dq-rule-recommender/SKILL.md) | Schema or sample data + target layer (Bronze/Silver/Gold) | DQ metadata CSV with checks, thresholds, and severities across all standard dimensions |
| [`dq-rule-to-code`](skills/dq-rule-to-code/SKILL.md) | DQ metadata CSV + platform target (`FABRIC` / `DATABRICKS` / `SYNAPSE` / `LOCAL`) | `dq_functions.py`, `dq_runner.py`, and a runnable notebook using platform-native APIs |

## Prerequisites

### skills-for-fabric

To use any **Microsoft Fabric** feature of this plugin (connecting to a Fabric workspace, reading Lakehouse data, and generating Fabric-native notebooks) you must first install the **skills-for-fabric** package.

```text
/plugin install skills-for-fabric
```

> Source & documentation: [github.com/microsoft/skills-for-fabric](https://github.com/microsoft/skills-for-fabric)

`skills-for-fabric` provides the Fabric-native capabilities that DQ-Coworker builds on:

| Capability | Used by DQ-Coworker for |
|------------|------------------------|
| Workspace / Lakehouse connection | Connecting to a workspace by ID and reading files at a given path |
| `notebookutils` API surface | Secret retrieval, notebook parameter passing, and environment detection in generated notebooks |
| ADLS Gen2 (`abfss://`) path resolution | Building the correct storage path for data reads and DQ results writes |
| Fabric Pipeline integration | Running the generated DQ notebook as a Fabric Pipeline activity |

> **Note:** `skills-for-fabric` is only required when targeting Microsoft Fabric. For Azure Databricks, Azure Synapse Analytics, or local PySpark you can skip this step.

---

## Install

```text
/plugin marketplace add agency-microsoft/playground
/plugin install dq-coworker@agency-playground
```

## Usage

### 1. Recommend DQ rules for a dataset

```text
Recommend DQ checks for the silver.customer table. It's a Silver-layer
Delta table with PII; flag P1 checks for null rates and uniqueness.
```

The recommender returns a DQ metadata CSV plus a per-dimension explanation.

### 2. Generate executable DQ code

```text
Generate a Fabric notebook from this DQ metadata CSV for the
silver.customer entity, P1 + P2 only.
```

Pick the platform target (`FABRIC` / `DATABRICKS` / `SYNAPSE` / `LOCAL`) and you'll get a notebook that uses platform-native APIs for SparkSession bootstrap, secret retrieval, data reads, results writes, and alerting.

## End-to-end example — HR data in Microsoft Fabric

This walkthrough shows the full two-prompt workflow: **recommend checks** from a live Fabric Lakehouse, then **generate a production notebook** that writes results back to the same Lakehouse.

### Prompt 1 — Suggest DQ checks

```text
Use DQ-Coworker to suggest DQ checks for data stored in my Fabric workspace.

Workspace ID : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
Lakehouse ID : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
Path         : Files/hr_data
```

DQ-Coworker will:

1. **Connect** to the Fabric Lakehouse using the workspace and lakehouse IDs.
2. **Read** the files at `Files/hr_data` (Parquet / Delta / CSV auto-detected).
3. **Profile** the schema and sample rows — null rates, cardinality, data types, format patterns.
4. **Map** each column to the applicable DQ dimensions (Completeness, Validity, Uniqueness, Referential Integrity, Timeliness, …).
5. **Present** each recommended check for human approval in the structured review format.
6. **Emit** an approved DQ metadata CSV — for example:

```csv
RuleID,RuleName,DQDimension,RuleType,RuleLevel,Entity,EntityType,Attribute,WorkflowGroup,ObjectWeight,AllowedVariance,IsActive,FailedPipelineInd,ExecutionEngine,DataOwner,DataClassification,AIConfidenceScore,AIRecommendationReason
DQ-001,EmployeeID_NullCheck,Completeness,NULL_CHECK,ATTRIBUTE,hr_data,DELTA,employee_id,Bronze,P1,0,Y,Y,SPARK,HR Team,CONFIDENTIAL,0.99,Primary key; 0 % nulls detected in profiling sample
DQ-002,EmployeeID_UniqueCheck,Uniqueness,DUPLICATE_CHECK,ATTRIBUTE,hr_data,DELTA,employee_id,Bronze,P1,0,Y,Y,SPARK,HR Team,CONFIDENTIAL,0.99,Primary key must be unique across all HR records
DQ-003,Email_FormatCheck,Validity,REGEX_CHECK,ATTRIBUTE,hr_data,DELTA,email,Silver,P2,0.5,Y,N,SPARK,HR Team,CONFIDENTIAL,0.95,Corporate email pattern detected; format validation recommended
DQ-004,Department_DomainCheck,Validity,ALLOWED_VALUES_CHECK,ATTRIBUTE,hr_data,DELTA,department,Silver,P2,0,Y,N,SPARK,HR Team,INTERNAL,0.93,Low cardinality column; domain: HR/Finance/Engineering/Sales/Legal
DQ-005,HireDate_FreshnessCheck,Freshness,FRESHNESS_CHECK,ENTITY,hr_data,DELTA,last_updated_at,Gold,P1,0,Y,Y,SPARK,HR Team,CONFIDENTIAL,0.94,Reporting layer SLA: HR data must be refreshed within 24 hours
DQ-006,Salary_RangeCheck,Accuracy,RANGE_CHECK,ATTRIBUTE,hr_data,DELTA,salary,Silver,P1,0,Y,Y,SPARK,HR Team,RESTRICTED,0.97,Salary must be in [10000, 500000]; outliers detected in profiling
DQ-007,ContractDates_ConsistencyCheck,Consistency,TEMPORAL_CONSISTENCY,ATTRIBUTE,hr_data,DELTA,"contract_start,contract_end",Silver,P2,0,Y,N,SPARK,HR Team,CONFIDENTIAL,0.92,Date range pair detected; contract_end must be >= contract_start
DQ-008,ManagerID_IntegrityCheck,Integrity,REFERENTIAL_INTEGRITY,ATTRIBUTE,hr_data,DELTA,manager_id,Silver,P1,0,Y,Y,SPARK,HR Team,INTERNAL,0.96,manager_id must resolve to a valid employee_id in the same table
DQ-009,HR_RowCount_Reconciliation,Completeness,ROW_COUNT_CHECK,ENTITY,hr_data,DELTA,,Gold,P1,0.1,Y,Y,SPARK,HR Team,INTERNAL,0.98,Row count must match the source HR system extract within 0.1 %
DQ-010,HR_Schema_ConformityCheck,Conformity,SCHEMA_CONFORMITY,ENTITY,hr_data,DELTA,,Bronze,P2,0,Y,N,SPARK,Data Engineering,INTERNAL,0.91,Schema must match the agreed HR target Delta schema definition
```

---

### Prompt 2 — Generate the Fabric notebook

```text
We want to execute all these checks on top of the data.
Please create a Fabric-compatible notebook to execute these checks on my
Fabric workspace and store the logs into the Fabric Lakehouse.

Workspace ID : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
Lakehouse ID : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

DQ-Coworker will generate a **17-cell Fabric notebook** using only Fabric-native APIs:

| Cell | Purpose |
|------|---------|
| 1 | Markdown title — entity, layer, platform, timestamp |
| 2 | Imports + Fabric platform bootstrap via `notebookutils` |
| 3 | Config — Lakehouse path, metadata CSV location, entity and layer parameters |
| 4 | Read `Files/hr_data` from the Lakehouse into a Spark DataFrame |
| 5 | Schema conformity pre-check (runs first; blocks on mismatch) |
| 6 | Availability + row-count check |
| 7 | Completeness — null checks on `employee_id` and all P1 fields |
| 8 | Uniqueness — duplicate check on `employee_id` |
| 9 | Validity — email regex, department domain, salary range |
| 10 | Referential integrity — `manager_id` → `employee_id` self-join |
| 11 | Consistency — `contract_start` / `contract_end` temporal check |
| 12 | Freshness — `last_updated_at` staleness vs. 24 h SLA |
| 13 | Custom SQL / business-rule checks |
| 14 | Results aggregation + DQ score calculation |
| 15 | Write results to `Tables/dq_results` Delta table in the Lakehouse |
| 16 | Alert — Teams Adaptive Card for any P1 failures (webhook from Key Vault) |
| 17 | Markdown summary — pass/fail counts, DQ score, failed rule list |

Key platform-native patterns used throughout the notebook:

```python
# Secrets — retrieved from Azure Key Vault via mssparkutils (never hardcoded)
STORAGE_ACCOUNT = mssparkutils.credentials.getSecret(KEY_VAULT_NAME, "storage-account-name")

# Lakehouse path
LAKEHOUSE_PATH = f"abfss://bronze@{STORAGE_ACCOUNT}.dfs.core.windows.net"

# Read HR data
df = spark.read.format("delta").load(f"{LAKEHOUSE_PATH}/Files/hr_data")

# Write DQ results back to the same Lakehouse
results_df.write.format("delta").mode("append").save(f"{LAKEHOUSE_PATH}/Tables/dq_results")

# Notebook parameters (set as Fabric Pipeline activity parameters)
ENTITY_NAME    = mssparkutils.notebook.getArgument("entity_name",    "hr_data")
WORKFLOW_GROUP = mssparkutils.notebook.getArgument("workflow_group", "Bronze")
```

---

## End-to-end example — Sales data as a Fabric Lakehouse Table

This walkthrough shows the same two-prompt workflow but reading from a **managed Delta table** registered in the Fabric Lakehouse (`Tables/` section) instead of a raw file path.

### Prompt 1 — Suggest DQ checks for a Lakehouse table

```text
Use DQ-Coworker to suggest DQ checks for the silver_sales table
registered in my Fabric Lakehouse.

Workspace ID : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
Lakehouse ID : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
Table name   : silver_sales
```

DQ-Coworker will:

1. **Connect** to the Fabric Lakehouse and read the table via `spark.read.table("silver_sales")`.
2. **Profile** the schema and sample rows — null rates, cardinality, data types, format patterns.
3. **Map** each column to the applicable DQ dimensions.
4. **Present** each recommended check for human approval.
5. **Emit** an approved DQ metadata CSV — for example:

```csv
RuleID,RuleName,DQDimension,RuleType,RuleLevel,Entity,EntityType,Attribute,WorkflowGroup,ObjectWeight,AllowedVariance,IsActive,FailedPipelineInd,ExecutionEngine,DataOwner,DataClassification,AIConfidenceScore,AIRecommendationReason
DQ-001,SalesID_NullCheck,Completeness,NULL_CHECK,ATTRIBUTE,silver_sales,TABLE,sales_id,Bronze,P1,0,Y,Y,SPARK,Sales Team,INTERNAL,0.99,Primary key; 0 % nulls detected in profiling sample
DQ-002,SalesID_UniqueCheck,Uniqueness,DUPLICATE_CHECK,ATTRIBUTE,silver_sales,TABLE,sales_id,Bronze,P1,0,Y,Y,SPARK,Sales Team,INTERNAL,0.99,Primary key must be unique
DQ-003,CustomerID_IntegrityCheck,Integrity,REFERENTIAL_INTEGRITY,ATTRIBUTE,silver_sales,TABLE,customer_id,Silver,P1,0,Y,Y,SPARK,Sales Team,INTERNAL,0.97,customer_id must resolve to a valid record in the customers table
DQ-004,Amount_RangeCheck,Accuracy,RANGE_CHECK,ATTRIBUTE,silver_sales,TABLE,amount,Silver,P1,0,Y,Y,SPARK,Finance Team,RESTRICTED,0.96,Amount must be > 0; negative values detected in profiling
DQ-005,Status_DomainCheck,Validity,ALLOWED_VALUES_CHECK,ATTRIBUTE,silver_sales,TABLE,status,Silver,P2,0,Y,N,SPARK,Sales Team,INTERNAL,0.93,Low cardinality; domain: OPEN/CLOSED/CANCELLED/REFUNDED
DQ-006,SaleDate_FreshnessCheck,Freshness,FRESHNESS_CHECK,ENTITY,silver_sales,TABLE,updated_at,Gold,P1,0,Y,Y,SPARK,Sales Team,INTERNAL,0.95,Reporting SLA: sales data must be refreshed within 4 hours
DQ-007,Sales_RowCount_Reconciliation,Completeness,ROW_COUNT_CHECK,ENTITY,silver_sales,TABLE,,Gold,P1,0.1,Y,Y,SPARK,Sales Team,INTERNAL,0.98,Row count must match source system within 0.1 %
DQ-008,Sales_Schema_ConformityCheck,Conformity,SCHEMA_CONFORMITY,ENTITY,silver_sales,TABLE,,Bronze,P2,0,Y,N,SPARK,Data Engineering,INTERNAL,0.91,Schema must match the agreed Silver sales Delta schema
```

---

### Prompt 2 — Generate the Fabric notebook for the table

```text
Generate a Fabric-compatible notebook to execute these DQ checks on the
silver_sales table in my Fabric Lakehouse and write the results back.

Workspace ID : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
Lakehouse ID : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
Table name   : silver_sales
Source type  : TABLE
```

DQ-Coworker will generate a **17-cell Fabric notebook** that reads the table via `spark.read.table()` rather than an ADLS Gen2 file path:

| Cell | Purpose |
|------|---------|
| 1 | Markdown title — entity, layer, platform, timestamp |
| 2 | Imports + Fabric platform bootstrap via `notebookutils` |
| 3 | Config — `SOURCE_TYPE = TABLE`, entity name, layer, and metadata CSV location |
| 4 | Read `silver_sales` Lakehouse table via `spark.read.table("silver_sales")` |
| 5 | Schema conformity pre-check |
| 6 | Availability + row-count check |
| 7 | Completeness — null check on `sales_id` and all P1 fields |
| 8 | Uniqueness — duplicate check on `sales_id` |
| 9 | Validity — status domain check, amount range |
| 10 | Referential integrity — `customer_id` → customers table |
| 11 | Consistency checks |
| 12 | Freshness — `updated_at` staleness vs. 4 h SLA |
| 13 | Custom SQL / business-rule checks |
| 14 | Results aggregation + DQ score calculation |
| 15 | Write results to `Tables/dq_results` Delta table in the Lakehouse |
| 16 | Alert — Teams Adaptive Card for any P1 failures (webhook from Key Vault) |
| 17 | Markdown summary — pass/fail counts, DQ score, failed rule list |

Key platform-native patterns used for table-based reads:

```python
# SOURCE_TYPE drives Cell 4 — TABLE reads via spark.read.table(), FILE reads via ADLS Gen2 path
SOURCE_TYPE    = mssparkutils.notebook.getArgument("source_type", "TABLE").upper()
ENTITY_NAME    = mssparkutils.notebook.getArgument("entity_name", "silver_sales")
WORKFLOW_GROUP = mssparkutils.notebook.getArgument("workflow_group", "Silver")

# Cell 4 — read the Lakehouse managed Delta table
if SOURCE_TYPE == "TABLE":
    df = spark.read.table(ENTITY_NAME)            # e.g. spark.read.table("silver_sales")
    # or spark.read.table("my_lakehouse.silver_sales") if referencing a non-default Lakehouse
else:
    df = spark.read.format("delta").load(f"{LAKEHOUSE_PATH}/Files/{ENTITY_NAME}")

# Write DQ results back to the Lakehouse
results_df.write.format("delta").mode("append").save(f"{LAKEHOUSE_PATH}/Tables/dq_results")
```

> **Tip:** Pass `source_type = TABLE` as a Fabric Pipeline activity parameter to switch any
> existing DQ notebook from file-based to table-based reads without changing the notebook code.

---

## Standard DQ dimensions covered

Completeness · Validity · Uniqueness · Consistency · Timeliness · Accuracy · Referential Integrity

See [`dq-rule-recommender/SKILL.md`](skills/dq-rule-recommender/SKILL.md) for definitions, SQL/Python examples, and threshold guidance.

## Authors

Ashish Modi, Parteek Kumar, Himaja Yangareddy
