# MaskIQ

**Data Protection & De-identification Agent** — Detect, analyze, and de-identify PII/PHI in structured data using Microsoft Presidio SDK with configurable anonymization strategies.

MaskIQ runs as an AI agent inside VS Code. It scans every text column in your CSV files, identifies sensitive entities (names, emails, SSNs, phone numbers, addresses, and more), and applies your chosen anonymization strategy — producing clean, de-identified output files and a full PII detection report.

---

## Prerequisites

| Requirement | Details |
|---|---|
| **VS Code** | Version 1.100 or later |
| **GitHub Copilot** | Active subscription with Chat enabled |
| **Python** | 3.10+ (managed automatically by the agent if using a Copilot-supported environment) |
| **Skills for Fabric (for Fabric deployment examples)** | Install and configure [skills-for-fabric](https://github.com/microsoft/skills-for-fabric) before running Fabric workspace/lakehouse deployment prompts |
| **Azure Synapse access (for Synapse deployment examples)** | Access to a Synapse workspace with Spark notebook support and linked storage |
| **Databricks Agent Skills (for Databricks deployment examples)** | Install and configure [databricks-agent-skills](https://github.com/databricks/databricks-agent-skills/) before running Databricks workspace deployment prompts |

---

## Local Setup

### 1. Clone This Repository

```powershell
git clone <REPO_URL>
cd MaskIQ
```

### 2. Open The Folder In VS Code

From the repository root:

```powershell
code .
```

Or in VS Code, use **File > Open Folder...** and select the cloned `MaskIQ` folder.

### 3. Run MaskIQ Locally

1. Open Copilot Chat in VS Code (`Ctrl+Shift+I`)
2. Type `/` and select **MaskIQ** from the slash command list
3. Run a command, for example:

```text
/MaskIQ my_data/ fake
```

This runs the workflow locally from this folder.

---

## Core Capabilities

MaskIQ provides enterprise-grade data de-identification and masking capabilities:

- **Multi-Source Support**: Mask sensitive data from diverse source systems including local files, cloud storage, data warehouses, and analytics platforms.

- **Automatic Referential Integrity Detection**: Intelligently identifies relationships between files and tables, ensuring the same PII value is consistently anonymized across all related datasets — preserving join keys and cross-file consistency.

- **Multi-Platform Notebook Generation**: Generates deployment-ready notebooks compatible with:
  - **Microsoft Fabric** — with `notebookutils.fs.*` APIs and Lakehouse integration
  - **Azure Synapse** — with `mssparkutils.fs.*` APIs and ADLS support
  - **Databricks** — with `dbutils.fs.*` APIs and catalog/volume support

- **Flexible Anonymization Strategies**: Choose from `replace`, `redact`, `mask`, `hash`, `encrypt`, `fake`, or `mixed` approaches depending on privacy vs. data utility trade-offs.

- **Custom Masking Rules**: Override default strategy behavior on a per-entity or per-column basis using structured JSON rules or natural-language instructions.

- **Comprehensive PII Detection**: Detects and reports 12+ entity types (names, emails, SSNs, phone numbers, locations, credit cards, IP addresses, URLs, and more) with confidence scores and full audit trails.

- **Validation & Reporting**: Automatically re-scans de-identified output to confirm zero residual PII and generates before/after comparison reports.

---

## Usage

### Quick Start

Open Copilot Chat and run:

```
/MaskIQ my_data/ fake
```

That's it. The agent handles everything end-to-end: environment setup, PII scanning, de-identification, validation, and reporting.

### Syntax

```
/MaskIQ <data_source> <strategy>
```

| Parameter | Required | Description |
|---|---|---|
| `data_source` | Yes | Path to a CSV file, a folder of CSVs, or a glob pattern |
| `strategy` | No | Anonymization strategy (defaults to `replace`) |

### Data Source Formats

| Format | Example |
|---|---|
| Folder of CSVs | `hr_org_compensation_changes_locations/` |
| Single CSV file | `sales/customers.csv` |
| Glob pattern | `data/*.csv` or `reports/2025_*.csv` |

### Strategies

| Strategy | Privacy | Data Utility | Reversible | Best For |
|---|---|---|---|---|
| `replace` | Moderate | Low | No | Quick inspection, debugging PII detection |
| `redact` | High | Very Low | No | Maximum privacy, regulatory compliance |
| `mask` | Moderate | Moderate | No | Customer-facing reports, partial visibility |
| `hash` | High | High (joins) | No | Analytics pipelines, data warehousing |
| `encrypt` | Very High | High (with key) | **Yes** | Legal holds, secure data transfer |
| `fake` | High | Very High | No | Demos, testing, sharing with third parties |
| `mixed` | Configurable | Maximized | Varies | Production pipelines, complex compliance |

### Examples

```bash
# Replace PII with entity type tags (default)
/MaskIQ hr_data/ replace

# Generate realistic fake data for a demo environment
/MaskIQ sales/customers.csv fake

# Hash PII for analytics while preserving join-ability across tables
/MaskIQ hr_org_compensation_changes_locations/ hash

# Encrypt PII (reversible — key is managed securely and not displayed by default)
/MaskIQ finance_records/ encrypt

# Remove all PII without a trace
/MaskIQ patient_records/ redact

# Partially mask PII for support tickets
/MaskIQ customer_data/ mask

# Apply different strategies per entity type
/MaskIQ financial_data/ mixed
```

### Fabric, Synapse, And Databricks Deployment Prompt Examples

Use these natural-language prompts in Copilot Chat when you want MaskIQ to both de-identify data and prepare notebook deployment for a target platform.

Fabric example (dummy IDs):

```text
Generate masked data using MaskIQ and deploy as a Fabric notebook in workspace 11111111-2222-3333-4444-555555555555 using lakehouse aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee, source data in SyntheticLake/Files/EmpDatawithDepartment/. Apply the strategy fake for de-identification.
```

Databricks example (dummy values):

```text
Generate masked data using MaskIQ and deploy as a Databricks notebook in workspace https://adb-1234567890123456.7.azuredatabricks.net, catalog main, schema demo, and volume SyntheticLake.EmpDatawithDepartment. Apply the strategy fake for de-identification.
```

Synapse example (dummy values):

```text
Generate masked data using MaskIQ and prepare an Azure Synapse notebook for workspace my-synapse-workspace, writing outputs to abfss://maskiq@contosodata.dfs.core.windows.net/curated/hr/. Apply the strategy fake for de-identification and use mssparkutils.fs APIs for file operations.
```

Notes:
- Replace dummy values with your real workspace and storage details.
- For Microsoft Fabric notebooks, use notebookutils.fs.* APIs.
- For Azure Synapse notebooks, use mssparkutils.fs.* APIs.
- For Databricks notebooks, use dbutils.fs.* APIs.

---

## Enterprise Use Cases — Microsoft Fabric

MaskIQ supports advanced de-identification scenarios for Microsoft Fabric deployments. Below are validated use cases with detailed prompts:

### Use Case 1: Source and Target Data in Same Lakehouse

**Status**: ✅ **Validated**

**Scenario**: Read source CSV/table from a Fabric Lakehouse and write masked output back to the same Lakehouse in a separate folder or table.

**Prompt**:
```text
Generate masked data using MaskIQ and deploy the solution as a Microsoft Fabric notebook in workspace 11111111-2222-3333-4444-555555555555.
Read the source data from lakehouse aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee at path SyntheticLake/Files/EmpDatawithDepartment/.
Write the masked output to a different lakehouse <TARGET_LAKEHOUSE_ID> within the same workspace.
Apply the fake strategy for de-identification on all PII columns while preserving schema consistency and referential integrity across related datasets.
Ensure the notebook is compatible with Fabric runtime and supports scalable execution.
```

**Key Points**:
- Both source and target use the same workspace and lakehouse.
- Masking is applied inline during notebook execution.
- Output folder structure is automatically organized under `/Curated/` or user-specified path.
- Referential integrity is preserved across all input files.

---

### Use Case 2: Source and Target Data in Different Lakehouses (Same Workspace)

**Status**: ✅ **Validated**

**Scenario**: Read from one Lakehouse and write de-identified output to a separate Lakehouse within the same Fabric workspace.

**Prompt**:
```text
Generate masked data using MaskIQ and deploy the solution as a Microsoft Fabric notebook.
Read the source data from Workspace A, lakehouse aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee, path SyntheticLake/Files/EmpDatawithDepartment/.
Write the masked output to a different lakehouse <TARGET_LAKEHOUSE_ID> within the same workspace.
Apply the fake strategy for de-identification on all PII columns while preserving schema consistency and referential integrity across related datasets.
Ensure the notebook is compatible with Fabric runtime and supports scalable execution.
```

**Key Points**:
- Source and target are in the same workspace but different Lakehouses.
- Notebook uses `notebookutils.fs.cp()` to transfer data between Lakehouses.
- No cross-workspace authentication overhead.
- Ideal for separating raw data (source) from curated masked data (target).

---

### Use Case 3: Source and Target Data in Different Fabric Workspaces

**Status**: ⏳ **In Development**

**Scenario**: Read from a Fabric Lakehouse in one workspace and write masked output to a different workspace.

**Prompt**:
```text
Generate masked data using MaskIQ and deploy the solution as a Microsoft Fabric notebook.
Read the source data from Workspace A, lakehouse aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee, path SyntheticLake/Files/EmpDatawithDepartment/.
Write the masked output to Workspace B, lakehouse yyyyyyyy-zzzz-xxxx-wwww-vvvvvvvvvvvv.
Apply the fake strategy for de-identification on all sensitive/PII columns while maintaining data relationships and structural integrity.
Ensure secure cross-workspace access (using appropriate authentication/linked services), and make the notebook fully deployable and executable in Fabric with proper configuration handling.
```

**Prerequisites**:
- Source Workspace must have permission to access the Target Workspace.
- Appropriate linked services or managed identities must be configured.
- Cross-workspace network access must be allowed.

**Key Points**:
- Advanced scenario for multi-team or multi-tenant environments.
- Requires authentication setup between workspaces.
- Ideal for sharing de-identified data across organizational boundaries while maintaining security.

---

### Use Case 4: Incremental Masking with Watermark Tracking

**Status**: ⏳ **In Development**

**Scenario**: On first run, process the entire dataset. On subsequent runs, mask only newly added or changed records based on date columns.

**Prompt**:
```text
Generate masked data using MaskIQ and deploy the solution as a Microsoft Fabric notebook in workspace 11111111-2222-3333-4444-555555555555.
Read the source data from lakehouse aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee at path SyntheticLake/Files/EmpDatawithDepartment/.
Write the masked output to a different lakehouse <TARGET_LAKEHOUSE_ID> within the same workspace.
Apply the fake strategy for de-identification on all PII columns while preserving schema consistency and referential integrity across related datasets.

Incremental Masking Requirement:
• On the first run, process and mask the entire dataset (full load).
• On subsequent runs, perform incremental masking only on newly added or changed records.
• Use date-based columns to identify new data:
  ◦ Employee table → JoinDate
  ◦ Department table → CreationDate
• Maintain a checkpoint/watermark (e.g., max processed date) to track previously processed records.
• Ensure no reprocessing of already masked records unless data changes.

The notebook should:
• Be fully compatible with Microsoft Fabric runtime (PySpark).
• Include logic for watermark storage (e.g., metadata table or file).
• Handle schema evolution gracefully.
• Support scalable execution for large datasets.
• Include logging for full vs incremental runs and number of records processed.
```

**Key Points**:
- Watermark stored as metadata table or control file.
- Filters input using date columns (JoinDate, CreationDate, LastModifiedDate, etc.).
- Significantly reduces processing time on large datasets by avoiding reprocessing.
- Maintains audit log of full vs. incremental runs.
- Ideal for production pipelines with frequent data updates.

---

### Use Case 5: Custom Column-Level Masking Rules

**Status**: ⏳ **In Development**

**Scenario**: Apply entity-level masking but override with custom rules for specific columns (e.g., partial masking, conditional masking).

**Prompt**:
```text
Generate masked data using MaskIQ and deploy the solution as a Microsoft Fabric notebook in workspace 11111111-2222-3333-4444-555555555555.
Read the source data from lakehouse aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee at path SyntheticLake/Files/EmpDatawithDepartment/.
Write the masked output to lakehouse <TARGET_LAKEHOUSE_ID>.
Apply standard de-identification strategies (e.g., fake) for all PII columns while preserving schema consistency and referential integrity.

Custom Masking Rule Requirement:
• Implement a column-level custom masking rule for the Employee table:
  ◦ Column: PhoneNumber
    ▪ Logic: Mask the first 5 characters with * and keep the remaining characters unchanged
    ▪ Example: +1-555-1234 → +1-***-1234
  ◦ Column: Salary
    ▪ Logic: Mask only if value > 100,000
    ▪ Example: 150000 → (masked as fake value), 75000 → (kept unchanged)
  ◦ Column: Email
    ▪ Logic: Mask email only for external users (domain not in allowed list @company.com)
    ▪ Example: john.doe@company.com → (kept unchanged), sarah@external.com → (masked)

The notebook should:
• Parse and validate custom rules before applying transformations.
• Apply entity-level strategy as default, then override with custom rules per column.
• Maintain referential integrity across related tables.
• Generate a rule application report showing which rules were applied to which columns.
• Be fully compatible with Microsoft Fabric runtime.
```

**Key Points**:
- Custom rules override base strategy on a column-by-column basis.
- Supports partial masking (e.g., keep last N characters).
- Supports conditional masking (e.g., based on value ranges or domain patterns).
- Format-preserving where applicable (phone patterns, date patterns).
- Comprehensive audit log of rule application per record.
- Ideal for compliance-heavy use cases with nuanced masking policies.

---

## How It Works

When you invoke MaskIQ, the agent:

1. **Validates inputs** — Checks that the data source exists, contains CSV files, and the strategy is valid
2. **Sets up the environment** — Installs Presidio, spaCy NLP models, Faker, and dependencies
3. **Creates a Jupyter notebook** — All processing is done in a structured, reproducible notebook
4. **Loads and profiles data** — Reads all CSVs, reports shape, types, null counts
5. **Detects PII** — Scans every text column using Presidio Analyzer with built-in and custom recognizers
6. **Generates a PII report** — Detailed log of every entity found: file, column, entity type, confidence score
7. **Applies anonymization** — De-identifies data using the selected strategy with referential integrity
8. **Validates output** — Re-scans de-identified data to confirm zero residual PII
9. **Exports results** — Saves de-identified CSVs, PII detection report, and visualizations

### Output Structure

All outputs are saved in a dedicated project folder:

```
deidentified_hr_org_compensation/
├── presidio_hr_org_compensation.ipynb    # Complete notebook with all code
├── deidentified_employees.csv            # De-identified data files
├── deidentified_departments.csv
├── deidentified_compensation.csv
├── pii_detection_report.csv              # Full PII detection log
```

### Supported PII Entities

| Entity | Description |
|---|---|
| `PERSON` | Full person names |
| `EMAIL_ADDRESS` | Email addresses |
| `PHONE_NUMBER` | Phone numbers (any format) |
| `LOCATION` | Cities, states, countries, addresses |
| `DATE_TIME` | Dates and times |
| `US_SSN` | Social Security Numbers |
| `CREDIT_CARD` | Credit/debit card numbers |
| `IP_ADDRESS` | IPv4 and IPv6 addresses |
| `URL` | Web URLs |
| `IBAN_CODE` | International bank account numbers |
| `US_DRIVER_LICENSE` | Driver license numbers |
| `US_PASSPORT` | Passport numbers |

Custom recognizers are also created for domain-specific patterns like Employee IDs, Badge Numbers, and internal email domains.

---

## Choosing a Strategy

Not sure which strategy to use? Here's a quick guide:

| Your Goal | Use |
|---|---|
| "I just want to see what PII exists" | `replace` |
| "I need to share data with a vendor" | `fake` |
| "Regulatory audit / compliance" | `redact` |
| "I need to join tables after de-identification" | `hash` or `fake` |
| "I might need the original data back later" | `encrypt` |
| "Different rules for different data types" | `mixed` |
| "Building a demo or test environment" | `fake` |
| "Customer-facing, partial visibility needed" | `mask` |

---

## Referential Integrity

When using `hash`, `fake`, or `mixed` strategies, MaskIQ ensures the **same PII value produces the same anonymized output** across all files in a session.

For example, if `employees.csv` has `manager_name = "John Doe"` and `org_changes.csv` has `approved_by = "John Doe"`, both will be anonymized to the **same value** — so table joins still work after de-identification.

---

## Troubleshooting

| Issue | Solution |
|---|---|
| `/MaskIQ` doesn't appear in slash commands | Verify the plugin is in the correct directory and restart VS Code |
| `spacy model not found` error | The agent auto-downloads `en_core_web_lg`. If it fails, run: `python -m spacy download en_core_web_lg` |
| Out of memory on large files | Split files > 500MB into smaller chunks before processing |
| Low PII detection accuracy | Presidio's confidence threshold is 0.7 by default. Some entity types may need custom recognizers |
| Notebook cells fail to execute | Ensure Python 3.10+ is available and the kernel is set correctly |

---

## Plugin Structure

```
MaskIQ/
├── .github/
│   ├── instructions/
│   │   ├── copilot-instructions.md
│   │   ├── general-coding.instructions.md
│   │   └── python-coding.instructions.md
│   └── prompts/
│       └── MaskIQ.prompt.md
├── end-to-end-flow.md
└── README.md
```

<!-- Contains AI-generated edits. -->