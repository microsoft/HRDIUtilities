# Worked Example — "Contoso Retail" Dev Workspace

> A complete, end-to-end walkthrough of `/fabric-cli-deploy full` against a fresh Contoso Retail dev workspace. Use this as the canonical reference for what a "good" deployment looks like.

---

## Scenario

The Contoso Retail data team is bootstrapping a brand-new Fabric workspace for their store-telemetry pipeline. They have:

- A new (empty) Fabric workspace named **`contoso_dev_fabric_ws`** in tenant `contoso`.
- ADLS Gen2 storage account `contosostorage` with three containers: `bronze`, `silver`, `gold`.
- Four exported notebooks, one pipeline, one semantic model, one report on local disk, with `##placeholder##` tokens substituted in for tenant-specific IDs.
- An SPN object ID `abcd1234-...` they want granted `Member` on the workspace.

They want a single command to wire it all up.

---

## 1. Entity Decomposition

The deployment touches **eight distinct entity classes**. The skill maps each to a config block in `fabric_config.json`:

| # | Entity | Config block | Count in this example |
|---|---|---|---|
| 1 | **Workspace** | `fabricWorkspaceName`, `tenantName`, `environmentName` | 1 |
| 2 | **Lakehouse** | `fabricLakehouseName` | 1 (`contoso_lakehouse`) |
| 3 | **Connection (ADLS)** | `connectionConfiguration` | 1 (`adls_connection`) |
| 4 | **Shortcuts** | `shortcutConfiguration.shortcuts[]` | 3 (`bronze`, `silver`, `gold`) |
| 5 | **Spark Pool** | `poolConfiguration` | 1 (`analyticssparkpool`) |
| 6 | **OneLake Folders** | `folderConfiguration` | 4 (`archive`, `metadata`, `metadata/v1`, `metadata/v2`) |
| 7 | **Workspace RBAC** | `SPNObjectID` | 1 SPN as `Member` |
| 8 | **Code Artifacts** | files under `Code/Fabric/**` | 4 notebooks + 1 pipeline + 1 model + 1 report = 7 |

---

## 2. Relationships (Dependency Graph)

Artifacts cannot be deployed in arbitrary order. The graph below is what the skill (via `oneinstaller.py`) enforces:

```
                ┌────────────────────────┐
                │   Workspace (assumed   │
                │   pre-existing or new) │
                └───────────┬────────────┘
                            │
            ┌───────────────┼─────────────────────────┐
            │               │                         │
            ▼               ▼                         ▼
     ┌────────────┐  ┌──────────────┐         ┌──────────────┐
     │  Lakehouse │  │  Spark Pool  │         │  Workspace   │
     │            │  │  (independent│         │  RBAC (SPN)  │
     └─────┬──────┘  │   of others) │         └──────────────┘
           │         └──────────────┘
           │
   ┌───────┼──────────────┬───────────────┐
   ▼       ▼              ▼               ▼
┌──────┐ ┌──────────┐ ┌─────────┐  ┌───────────────┐
│ ADLS │ │ OneLake  │ │Notebooks│  │ Pipelines     │
│ Conn │ │ Folders  │ │         │  │  (ref         │
└──┬───┘ └──────────┘ └────┬────┘  │   notebooks)  │
   │                       │       └──────┬────────┘
   ▼                       │              │
┌──────────┐               │              │
│Shortcuts │               │              │
│(bronze,  │               │              │
│ silver,  │               │              ▼
│ gold)    │               │       ┌──────────────┐
└──────────┘               │       │ Semantic     │
                           │       │ Model        │
                           │       └──────┬───────┘
                           │              │
                           ▼              ▼
                       (referenced)  ┌──────────┐
                                     │  Report  │
                                     │ (binds   │
                                     │ to model)│
                                     └──────────┘
```

**Rules the skill enforces:**
- **Shortcut** requires both **Lakehouse** AND **Connection** to be ready.
- **Pipeline** activity that calls a notebook must resolve the notebook's GUID **after** notebook import — handled by the `##NotebookName##` token swap.
- **Report** binds to **Semantic Model** GUID — handled by the `##semanticModelId##` token swap.
- **Spark Pool** and **Workspace RBAC** are independent and run in parallel-safe order.

---

## 3. Deployment Order (Generation Order)

```
Phase A — Pre-flight
  A1  python --version            ≥ 3.10
  A2  fab --version                installed
  A3  fab auth status              authenticated
  A4  read fabric_config.json     parse + structural check
  A5  list Code/Fabric/**          inventory + placeholder hygiene

Phase B — Infrastructure (oneinstaller.py without --skip-infra)
  B1  Lakehouse           create-if-missing
  B2  Connection (ADLS)   create-if-missing
  B3  Shortcuts × 3       create-if-missing (depend on B1 + B2)
  B4  Spark Pool          create-or-update-in-place
  B5  OneLake Folders × 4 create-if-missing (depend on B1)
  B6  Workspace RBAC      assign-or-skip (depend on workspace)

Phase C — Code (oneinstaller.py without --skip-code)
  C1  Notebooks × 4       force re-import (-f)
  C2  Pipelines × 1       force re-import (-f) — tokens for notebook IDs resolved
  C3  Semantic Model × 1  force re-import (-f)
  C4  Report × 1          force re-import (-f) — token for model ID resolved

Phase D — Summary
  D1  read newest Logs/deployment_log_*.csv
  D2  aggregate counts
  D3  emit final summary block (SKILL §9)
```

---

## 4. Resulting File Tree

After running `/fabric-cli-deploy full`, the local repo has the following state (the skill makes no changes outside `Logs/` and, if `update-config` was used, `Config/`):

```
FabricCLI/
├── Config/
│   └── fabric_config.json                       ← unchanged (we used `--verb full`, not `update-config`)
├── Code/
│   └── Fabric/
│       ├── Notebooks/
│       │   ├── 01_Ingest_StoreSales.Notebook/
│       │   │   ├── .platform
│       │   │   └── notebook-content.ipynb
│       │   ├── 02_Clean_StoreSales.Notebook/
│       │   ├── 03_Aggregate_Daily.Notebook/
│       │   └── 04_Publish_Gold.Notebook/
│       ├── Pipelines/
│       │   └── Daily_Sales.DataPipeline/
│       │       ├── .platform
│       │       └── pipeline-content.json
│       ├── Models/
│       │   └── Sales_SemanticModel.SemanticModel/
│       │       ├── .platform
│       │       └── definition/
│       │           ├── model.tmdl
│       │           └── tables/*.tmdl
│       └── Reports/
│           └── Sales_Daily.Report/
│               ├── .platform
│               └── definition.pbir
├── DeploymentScrips/
│   ├── oneinstaller.py
│   ├── fabric_infra_deploy.py
│   ├── fabric_code_deploy.py
│   └── shared_logger.py
├── Logs/                                        ← NEW (created by the run)
│   ├── runninglog_15052026.txt                  ← detailed text log
│   └── deployment_log_15052026.csv              ← structured audit CSV
└── Plugin/
    └── fabric-cli-deploy/                       ← this plugin (Agency layout)
        ├── .claude-plugin/
        │   └── plugin.json
        ├── README.md
        ├── skills/
        │   └── SKILL.md
        ├── prompts/
        ├── schemas/
        └── examples/
```

---

## 5. Sample Validation / Log Output

### 5a. Pre-flight checkpoint stream

```
[1/6] ✓ Intake resolved — verb=full workspace=contoso_dev_fabric_ws env=dev
[2/6] ✓ Pre-flight OK — Python 3.11.4, fab 1.2.3, authenticated as svc-contoso@contoso.com
[3/6] ✓ Config validated — 11 required keys present, 0 optional warnings
[4/6] ✓ Artifacts inventoried — 4 notebooks, 1 pipeline, 1 model, 1 report
[5/6] ⏳ Deploying — running `python DeploymentScrips/oneinstaller.py` (this can take 5–15 min)…
```

### 5b. Sample rows from `Logs/deployment_log_15052026.csv` (abridged)

```csv
timestamp,artifact_name,artifact_type,status,command,duration_seconds
2026-05-15T17:14:38Z,contoso_lakehouse,lakehouse,CREATED,"fab create contoso_dev_fabric_ws.Workspace/contoso_lakehouse.Lakehouse",4.2
2026-05-15T17:14:43Z,adls_connection,connection,CREATED,"fab create .connections/adls_connection.Connection --params type=AzureDataLakeStorage,...",6.1
2026-05-15T17:14:50Z,bronze,shortcut,CREATED,"fab create ...Lakehouse/Files/bronze.Shortcut --params target.type=AdlsGen2,...",2.0
2026-05-15T17:14:52Z,silver,shortcut,CREATED,"fab create ...Lakehouse/Files/silver.Shortcut --params target.type=AdlsGen2,...",2.0
2026-05-15T17:14:54Z,gold,shortcut,CREATED,"fab create ...Lakehouse/Files/gold.Shortcut --params target.type=AdlsGen2,...",2.0
2026-05-15T17:14:57Z,analyticssparkpool,spark_pool,CREATED,"fab set ...Workspace/.sparkpools.json -q ...",3.5
2026-05-15T17:15:01Z,archive,folder,CREATED,"fab mkdir ...Lakehouse/Files/archive",1.1
2026-05-15T17:15:03Z,metadata/v1,folder,CREATED,"fab mkdir ...Lakehouse/Files/metadata/v1",1.1
2026-05-15T17:15:05Z,workspace_access,rbac,CREATED,"fab acl set contoso_dev_fabric_ws.Workspace -I abcd1234-... -R Member",1.8
2026-05-15T17:15:09Z,01_Ingest_StoreSales,notebook,SUCCESS,"fab import ... -f",6.4
2026-05-15T17:15:16Z,02_Clean_StoreSales,notebook,SUCCESS,"fab import ... -f",5.9
2026-05-15T17:15:22Z,03_Aggregate_Daily,notebook,SUCCESS,"fab import ... -f",6.0
2026-05-15T17:15:28Z,04_Publish_Gold,notebook,SUCCESS,"fab import ... -f",5.7
2026-05-15T17:15:35Z,Daily_Sales,pipeline,SUCCESS,"fab import ... -f",7.2
2026-05-15T17:15:43Z,Sales_SemanticModel,semantic_model,SUCCESS,"fab import ... -f",9.1
2026-05-15T17:15:53Z,Sales_Daily,report,SUCCESS,"fab import ... -f",4.6
```

### 5c. Tail of `Logs/runninglog_15052026.txt` (excerpt)

```
17:15:53 [INFO ] Code deployment complete: 7/7 artifacts succeeded, 0 failed.
17:15:53 [INFO ] Total wall-clock: 1m 15s
17:15:53 [INFO ] Audit CSV: Logs/deployment_log_15052026.csv
17:15:53 [INFO ] Exit code: 0
```

---

## 6. Final User-Facing Summary (Verbatim)

This is what the skill emits in chat after Phase 6. It matches SKILL §9 byte-for-byte:

```
============================================================
  Microsoft Fabric Deployment Summary
============================================================
  Workspace : contoso_dev_fabric_ws
  Tenant    : contoso
  Env       : dev
  Verb      : full
  Started   : 2026-05-15T17:14:37Z
  Duration  : 1m 15s

Infrastructure
  Lakehouse        : contoso_lakehouse        [created]
  Connection       : adls_connection          [created]
  Shortcuts        : 3 total                  [3 created, 0 reused, 0 failed]
  Spark Pool       : analyticssparkpool       [created]
  OneLake Folders  : 4 total                  [4 created, 0 reused]
  Workspace Access : SPN abcd1234-…           [created]

Code Artifacts
  Notebooks        : 4 total                  [4 succeeded, 0 failed]
  Pipelines        : 1 total                  [1 succeeded, 0 failed]
  Semantic Models  : 1 total                  [1 succeeded, 0 failed]
  Reports          : 1 total                  [1 succeeded, 0 failed]

Warnings
  (none)

Failures
  (none)

Logs
  - Detailed : Logs/runninglog_15052026.txt
  - Audit CSV: Logs/deployment_log_15052026.csv

Next steps
  1. Open the workspace in the Fabric portal.
  2. Validate pipeline schedules and data refreshes.
  3. Re-run `/fabric-cli-deploy validate` after any code edit.
============================================================
```

---

## 7. Re-Run Behavior (Idempotency Demo)

The same command, run a second time **without changes**, produces this summary (note `reused` vs `created`, code is always force-imported):

```
============================================================
  Microsoft Fabric Deployment Summary
============================================================
  Workspace : contoso_dev_fabric_ws
  Tenant    : contoso
  Env       : dev
  Verb      : full
  Started   : 2026-05-15T18:02:11Z
  Duration  : 0m 48s

Infrastructure
  Lakehouse        : contoso_lakehouse        [reused]
  Connection       : adls_connection          [reused]
  Shortcuts        : 3 total                  [0 created, 3 reused, 0 failed]
  Spark Pool       : analyticssparkpool       [updated]
  OneLake Folders  : 4 total                  [0 created, 4 reused]
  Workspace Access : SPN abcd1234-…           [reused]

Code Artifacts
  Notebooks        : 4 total                  [4 succeeded, 0 failed]
  Pipelines        : 1 total                  [1 succeeded, 0 failed]
  Semantic Models  : 1 total                  [1 succeeded, 0 failed]
  Reports          : 1 total                  [1 succeeded, 0 failed]

Warnings
  (none)

Failures
  (none)

Logs
  - Detailed : Logs/runninglog_15052026.txt
  - Audit CSV: Logs/deployment_log_15052026.csv

Next steps
  1. Open the workspace in the Fabric portal.
  2. Validate pipeline schedules and data refreshes.
  3. Re-run `/fabric-cli-deploy validate` after any code edit.
============================================================
```

---

## 8. Partial-Failure Example

If the `Sales_SemanticModel` artifact were malformed, the skill would surface this **partial** summary (header changes to `PARTIAL`, failure row populated):

```
============================================================
  Microsoft Fabric Deployment Summary (PARTIAL — see Failures)
============================================================
  ...
Code Artifacts
  Notebooks        : 4 total                  [4 succeeded, 0 failed]
  Pipelines        : 1 total                  [1 succeeded, 0 failed]
  Semantic Models  : 1 total                  [0 succeeded, 1 failed]
  Reports          : 1 total                  [0 succeeded, 1 failed]

Warnings
  - Report Sales_Daily skipped because its bound model Sales_SemanticModel failed.

Failures
  - Sales_SemanticModel (semantic_model): TMDL parse error at definition/tables/Calendar.tmdl line 14.

Logs
  - Detailed : Logs/runninglog_15052026.txt
  - Audit CSV: Logs/deployment_log_15052026.csv

Next steps
  1. Fix definition/tables/Calendar.tmdl and re-run `/fabric-cli-deploy code-only`.
  2. Or re-export the model with `fab export "<source>.SemanticModel" -f`.
============================================================
```
