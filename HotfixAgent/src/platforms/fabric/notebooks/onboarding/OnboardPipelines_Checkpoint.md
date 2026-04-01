# Self-Healing Agent — Pipeline Checkpoint Onboarding

## End-to-End Technical Documentation

> **Notebook**: `OnboardPipelines_Checkpoint.ipynb`
> **Runtime**: Microsoft Fabric Synapse Notebook (PySpark + Delta Lake)
> **API**: Fabric REST API (`sempy.fabric.FabricRestClient`)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [How Checkpoint Wrapping Works](#3-how-checkpoint-wrapping-works)
4. [Notebook Cells — Step by Step](#4-notebook-cells--step-by-step)
5. [Helper Notebook (`_checkpoint_helper`)](#5-helper-notebook-_checkpoint_helper)
6. [Transform Logic Deep Dive](#6-transform-logic-deep-dive)
7. [Parameter Type Rules (Critical)](#7-parameter-type-rules-critical)
8. [Re-Onboarding (Already Onboarded Pipelines)](#8-re-onboarding-already-onboarded-pipelines)
9. [Checkpoint Table Schema](#9-checkpoint-table-schema)
10. [Backup Table Schema](#10-backup-table-schema)
11. [Self-Healing Agent Workflow](#11-self-healing-agent-workflow)
12. [Retry Policy Design](#12-retry-policy-design)
13. [Rollback & Reset](#13-rollback--reset)
14. [Limitations & Edge Cases](#14-limitations--edge-cases)
15. [Configuration Reference](#15-configuration-reference)
16. [Troubleshooting](#16-troubleshooting)

---

## 1. Overview

The **Self-Healing Agent** makes Microsoft Fabric data pipelines resilient to failures. It does this by transforming pipeline definitions to inject **checkpoint logic** — recording which activities have completed, so that on re-run, already-successful activities are skipped and only the failed (or not-yet-run) activities execute.

### What it does

| Before Onboarding | After Onboarding |
|---|---|
| Pipeline runs all activities every time | Skips activities already marked COMPLETED |
| Failure → manual investigation | Failure → error details captured in checkpoint table |
| Retries burn time on permanent failures | Retry = 0 → immediate failure → agent performs RCA |
| Re-run after fix → starts from scratch | Re-run after fix → resumes from failure point |
| No execution history | Full activity-level execution log in Delta table |

### What gets deployed

1. **Checkpoint Delta table** — stores per-activity completion/failure records
2. **Backup Delta table** — stores original pipeline definitions for rollback
3. **`_checkpoint_helper` notebook** — lightweight notebook called by pipelines to check/update checkpoints
4. **Modified pipeline definitions** — original activities wrapped with IfCondition + checkpoint logic

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ONBOARDED PIPELINE                           │
│                                                                 │
│  ┌──────────┐    ┌──────────┐                                   │
│  │_chk_load │───▶│_chk_var  │  (SetVariable: _completed_list)   │
│  │(notebook)│    │          │                                    │
│  └──────────┘    └────┬─────┘                                   │
│                       │                                         │
│          ┌────────────┼────────────┐                             │
│          ▼            ▼            ▼                             │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │
│  │ _chk_if_A    │ │ _chk_if_B    │ │ _chk_if_C    │             │
│  │(IfCondition) │ │(IfCondition) │ │(IfCondition) │             │
│  │              │ │              │ │              │             │
│  │ if NOT in    │ │ if NOT in    │ │ if NOT in    │             │
│  │ completed:   │ │ completed:   │ │ completed:   │             │
│  │  ┌────────┐  │ │  ┌────────┐  │ │  ┌────────┐  │             │
│  │  │   A    │  │ │  │   B    │  │ │  │   C    │  │             │
│  │  │(ret=0) │  │ │  │(ret=0) │  │ │  │(ret=0) │  │             │
│  │  └───┬────┘  │ │  └───┬────┘  │ │  └───┬────┘  │             │
│  │   ┌──┴───┐   │ │   ┌──┴───┐   │ │   ┌──┴───┐   │             │
│  │   │ OK?  │   │ │   │ OK?  │   │ │   │ OK?  │   │             │
│  │  ┌┴┐   ┌┴┐  │ │  ┌┴┐   ┌┴┐  │ │  ┌┴┐   ┌┴┐  │             │
│  │  │✓│   │✗│  │ │  │✓│   │✗│  │ │  │✓│   │✗│  │             │
│  │  │U│   │F│  │ │  │U│   │F│  │ │  │U│   │F│  │             │
│  │  │P│   │A│  │ │  │P│   │A│  │ │  │P│   │A│  │             │
│  │  │D│   │I│  │ │  │D│   │I│  │ │  │D│   │I│  │             │
│  │  └─┘   │L│  │ │  └─┘   │L│  │ │  └─┘   │L│  │             │
│  │        └┬┘  │ │        └┬┘  │ │        └┬┘  │             │
│  │         ▼   │ │         ▼   │ │         ▼   │             │
│  │     RE_FAIL │ │     RE_FAIL │ │     RE_FAIL │             │
│  └──────────────┘ └──────────────┘ └──────────────┘             │
│          │            │            │                             │
│          └────────────┼────────────┘                             │
│                       ▼                                         │
│               ┌──────────────┐                                  │
│               │ _chk_reset   │  (clears checkpoints on          │
│               │ (notebook)   │   full success)                  │
│               └──────────────┘                                  │
└─────────────────────────────────────────────────────────────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │  Checkpoint Delta     │
            │  Table (Lakehouse)    │
            │                       │
            │  pipeline_name        │
            │  activity_name        │
            │  status (COMPLETED/   │
            │          FAILED)      │
            │  error_message        │
            │  run_id               │
            │  ...                  │
            └───────────────────────┘
```

---

## 3. How Checkpoint Wrapping Works

### Original Pipeline

```
Activity A → Activity B → Activity C
```

### After Onboarding

```
_chk_load → _chk_var → _chk_if_A → _chk_if_B → _chk_if_C → _chk_reset
```

Each `_chk_if_X` is an **IfCondition** that checks:

```
@not(contains(concat(',', variables('_completed_list'), ','), ',ActivityName,'))
```

- If the activity is **NOT** in the completed list → execute it (True branch)
- If it **IS** in the completed list → skip it (False branch, empty)

### Inside each IfCondition (True branch)

| Activity | Type | Trigger | Purpose |
|---|---|---|---|
| `X` (original) | Original type | — | The actual business logic (retry = 0) |
| `_chk_upd_X` | TridentNotebook | `X` Succeeded | Write `COMPLETED` to checkpoint table |
| `_chk_fail_X` | TridentNotebook | `X` Failed | Write `FAILED` + error message to checkpoint table |
| `_chk_re_fail_X` | Fail | `_chk_fail_X` Succeeded | Re-raise the error so the IfCondition fails |

### Dependency Remapping

Original dependencies between activities are **remapped** to point to the IfCondition wrappers:

| Original | Remapped |
|---|---|
| `B depends on A` | `_chk_if_B depends on _chk_if_A` |
| `A has no deps` | `_chk_if_A depends on _chk_var` |
| `A depends on inactive X` | `_chk_if_A depends on _chk_var` |

---

## 4. Notebook Cells — Step by Step

### Cell 1: Markdown — Introduction

Overview of the self-healing agent, how checkpoint wrapping works, retry policy design, limitations, and what gets deployed.

### Cell 2: Parameters (Cell 2)

```python
WORKSPACE_ID         = ""       # Fabric workspace GUID
CHECKPOINT_LAKEHOUSE = ""       # Lakehouse name
CHECKPOINT_TABLE     = "pipeline_activity_checkpoints"
HELPER_NOTEBOOK_NAME = "_checkpoint_helper"
BACKUP_TABLE         = "pipeline_definition_backups"
INCLUDE_PIPELINES    = []       # fnmatch patterns (empty = all)
EXCLUDE_PIPELINES    = ["_shadow*", "_checkpoint*"]
DRY_RUN              = True     # True = preview, False = apply
```

### Cell 3: Initialize (Cell 3)

- Imports: `json`, `copy`, `time`, `re`, `base64`, `logging`, `fnmatch`, `sempy.fabric`
- Creates `FabricRestClient` and `SparkSession`
- Defines `_wait_for_long_operation()` for Fabric REST 202 async responses

### Cell 4: Create Checkpoint & Backup Tables (Cell 4)

- Creates the checkpoint Delta table with `CREATE TABLE IF NOT EXISTS`
- Adds columns for existing tables via `ALTER TABLE ADD COLUMNS` (safe upgrade)
- Creates the backup Delta table for original pipeline definitions

### Cell 5: Deploy Helper Notebook (Cell 5)

- Builds the `_checkpoint_helper` notebook in `.ipynb` JSON format
- Contains 3 cells: `%%configure` (Lakehouse binding), parameters cell, logic cell
- Creates or updates via Fabric REST API
- Returns `helper_notebook_id` (GUID) used by transform logic

### Cell 6: Discover Pipelines (Cell 6)

- Lists all `DataPipeline` items in workspace via REST API
- Applies `INCLUDE_PIPELINES` / `EXCLUDE_PIPELINES` fnmatch filters
- Produces `filtered_pipelines` list

### Cell 7: Transform Logic (Cell 7)

The core `transform_pipeline()` function. See [Section 6](#6-transform-logic-deep-dive) for full details.

### Cell 8: Preview / Dry Run (Cell 8)

- Fetches each pipeline definition via `getDefinition` REST API
- Debugs: shows TridentNotebook activities, `externalReferences`, all `referenceName`/`notebookId` values
- Calls `transform_pipeline()` and shows before/after summary
- Tracks `preview_results` for the apply step

### Cell 9: Apply Changes (Cell 9)

- **Only runs when `DRY_RUN = False`**
- For each pipeline in `preview_results` with status `READY`:
  1. Backs up original definition to the backup Delta table (MERGE upsert)
  2. Updates pipeline definition via `updateDefinition` REST API
- Shows success/failure summary

### Cell 10: Verify Onboarding (Cell 10)

- Re-fetches each onboarded pipeline definition
- Checks for presence of: `_chk_load`, `_chk_var`, `_chk_if_*`, `_chk_upd_*`, `_chk_fail_*`, `_chk_re_fail_*`, `_completed_list` variable

### Cell 11: Monitor Checkpoints (Cell 11)

- Queries checkpoint table: shows all records ordered by `pipeline_name`, `resolved_at`
- Displays counts: total, completed, failed, distinct pipelines

### Cell 12: Rollback (Cell 12)

- Commented-out code for:
  - **Option A**: Rollback a specific pipeline by name
  - **Option B**: Rollback ALL backed-up pipelines
- Reads backup from Delta table, pushes original definition back via REST API

### Cell 13: Reset Checkpoints (Cell 13)

- Commented-out code for:
  - **Option A**: Clear checkpoints for a specific pipeline
  - **Option B**: Clear ALL checkpoint records

---

## 5. Helper Notebook (`_checkpoint_helper`)

A lightweight notebook deployed to the workspace, called by checkpoint activities in the pipeline.

### Structure

| Cell | Content |
|---|---|
| 1 | `%%configure` — binds to the checkpoint Lakehouse |
| 2 | Parameters cell (tagged `parameters`) — receives values from pipeline |
| 3 | Logic cell — executes the checkpoint operation |

### Parameters

| Parameter | Description |
|---|---|
| `mode` | `CHECK_ALL`, `UPDATE`, or `RESET` |
| `checkpoint_lakehouse` | Lakehouse name |
| `checkpoint_table` | Delta table name |
| `pipeline_name` | `@pipeline().Pipeline` (resolved at runtime) |
| `pipeline_id` | Pipeline item GUID |
| `run_id` | `@pipeline().RunId` (resolved at runtime) |
| `activity_name` | Name of the activity being checkpointed |
| `activity_type` | Type of the activity (e.g., `Copy`, `TridentNotebook`) |
| `status` | `COMPLETED` or `FAILED` |
| `error_message` | Error details (for FAILED) |
| `original_retry_count` | Original retry policy value before onboarding |

### Mode: `CHECK_ALL` (called by `_chk_load`)

1. Check if any `FAILED` records exist for the pipeline
2. **If failures exist** (partial run): return comma-separated list of `COMPLETED` activity names → those will be skipped on re-run
3. **If no failures** (full success or first run): DELETE all checkpoint records → return empty string → all activities run fresh
4. On any exception: return empty string (safe fallback — run everything)

**Key insight**: The "auto-reset on success" is built into `CHECK_ALL`. If the last run completed all activities (no FAILED records), checkpoints are cleared automatically on the next run.

### Mode: `UPDATE` (called by `_chk_upd_*` and `_chk_fail_*`)

- **MERGE** into checkpoint table: upsert on `(pipeline_name, activity_name)`
- On match: updates status, run_id, error_message, etc.
- On no match: inserts new row
- Error messages truncated to 500 chars
- Returns `"OK"`

### Mode: `RESET` (called by `_chk_reset`)

Sent after all activities succeed. Currently handled by the `else` branch (returns `"UNKNOWN_MODE"` with exit code 0). The actual reset happens in `CHECK_ALL` on the next run when it detects no FAILED records.

### Null Safety

All parameters have null guards at the top of the logic cell:

```python
pipeline_name = pipeline_name or ""
activity_name = activity_name or ""
# ... etc.
```

This prevents `NoneType` errors if Fabric expression evaluation passes `None`.

---

## 6. Transform Logic Deep Dive

### Function: `transform_pipeline(pipeline_def, helper_notebook_id, pipeline_item_id)`

**Returns**: `(modified_def, stats_dict)`

### Step-by-step flow

#### 1. Connection Auto-Detection

```python
_find_notebook_connection(activities)
```

Recursively scans all activities (including inside IfCondition, ForEach, Switch, Until) for `TridentNotebook` activities with `externalReferences.connection`. This connection is applied to all checkpoint notebook activities.

#### 2. Build Notebook Activity Factory

```python
_make_notebook_activity(name, depends_on, policy, parameters, extra_props=None)
```

Creates a `TridentNotebook` activity dict with:
- `notebookId`: the helper notebook GUID
- `workspaceId`: the workspace GUID
- `parameters`: all using `"type": "string"` (see [Section 7](#7-parameter-type-rules-critical))
- `externalReferences.connection`: auto-detected from existing activities

#### 3. Re-Onboard Check

If `_chk_load` already exists in the pipeline (previously onboarded):
- **Unwrap** original activities from `_chk_if_*` IfCondition wrappers
- **Restore** original dependencies (remap `_chk_if_X` back to `X`, drop `_chk_var` deps)
- **Recover** original retry counts from `_chk_upd_*` parameters (`original_retry_count`)
- **Discard** all `_chk_*` activities
- Re-wrap from scratch with latest checkpoint logic

#### 4. Classify Activities

Each activity is classified as **active** or **inactive**:

```python
is_inactive = (
    act.get("state", "").lower() == "inactive"
    or act.get("inactive", False) is True
    or act.get("policy", {}).get("state", "").lower() == "inactive"
)
```

- **Active**: wrapped with IfCondition + checkpoint
- **Inactive (deactivated)**: preserved as-is (Fabric already skips them)

#### 5. Validate Activity Names

Activity names containing commas are rejected — the checkpoint skip-list uses comma-delimited matching.

#### 6. Add Pipeline Variable

```python
variables["_completed_list"] = {"type": "String", "defaultValue": ""}
```

Stores the comma-separated list of completed activities during pipeline execution.

#### 7. Create `_chk_load`

Calls helper notebook with `mode=CHECK_ALL`. Returns completed activity list.

#### 8. Create `_chk_var`

`SetVariable` activity: stores the `_chk_load` output into `_completed_list` variable.

```python
"value": {
    "value": "@string(activity('_chk_load').output.result.exitValue)",
    "type": "Expression"
}
```

#### 9. Wrap Each Active Activity

For each active activity:

| Step | What | Details |
|---|---|---|
| Remap deps | Point to wrappers | `A` → `_chk_if_A`, entry points → `_chk_var` |
| Override retry | Set to 0 | Save original in `retry_overrides` |
| `_chk_upd_X` | Success checkpoint | Notebook: `mode=UPDATE, status=COMPLETED` |
| `_chk_fail_X` | Failure capture | Notebook: `mode=UPDATE, status=FAILED, error_message=@activity('X').error.message` |
| `_chk_re_fail_X` | Re-raise error | Fail activity: propagates error so IfCondition fails |
| `_chk_if_X` | Wrapper | IfCondition: skip if in completed list |

#### 10. Create `_chk_reset`

Depends on ALL `_chk_if_*` activities succeeding. Calls helper notebook with `mode=RESET`.

#### 11. Sanitize Retry Intervals

```python
_fix_retry_intervals(modified)
```

Recursively ensures `retryIntervalInSeconds >= 30` everywhere — Fabric enforces this minimum.

#### 12. Build Modified Definition

Deep-copies the original pipeline definition, replaces `activities` and `variables`, returns `(modified, stats)`.

---

## 7. Parameter Type Rules (Critical)

> **This is the most important technical detail for correct operation.**

### TridentNotebook Parameters

**ALL** parameters passed to `TridentNotebook` activities MUST use `"type": "string"`:

```python
"pipeline_name": {"value": "@pipeline().Pipeline", "type": "string"}
"run_id":        {"value": "@pipeline().RunId",     "type": "string"}
"activity_name": {"value": "MyActivity",            "type": "string"}
```

**Why not `"type": "Expression"`?**

Fabric's pipeline engine evaluates `@` expressions in the value field regardless of the `type` field. When `"type": "Expression"` is used for a TridentNotebook `RunNotebookParameter`:

1. Pipeline engine evaluates the expression (e.g., `@pipeline().Pipeline` → `"My_Pipeline"`)
2. Replaces the parameter object with the raw resolved value (a plain string)
3. Notebook engine tries to deserialize it as a `RunNotebookParameter` object
4. **Fails with**: `Error converting value 'My_Pipeline' to RunNotebookParameter. Path 'pipeline_name'`

### Where `"type": "Expression"` IS Valid

| Context | Activity Type | Example |
|---|---|---|
| SetVariable `.value` | SetVariable | `"value": {"value": "@string(...)", "type": "Expression"}` |
| IfCondition `.expression` | IfCondition | `"expression": {"value": "@not(...)", "type": "Expression"}` |
| Fail `.message` | Fail | `"message": {"value": "@activity('X').error.message", "type": "Expression"}` |

These are **pipeline-level constructs**, not notebook parameters. The pipeline engine handles them directly.

### Summary Table

| Location | `"type": "string"` | `"type": "Expression"` |
|---|---|---|
| TridentNotebook `parameters` | **CORRECT** | **BREAKS** — causes RunNotebookParameter error |
| SetVariable `value` | ✗ | **CORRECT** |
| IfCondition `expression` | ✗ | **CORRECT** |
| Fail `message` | ✗ | **CORRECT** |

---

## 8. Re-Onboarding (Already Onboarded Pipelines)

When `transform_pipeline()` detects an already-onboarded pipeline (has `_chk_load`), it performs a **full unwrap + re-wrap**:

### Unwrap Process

```
For each _chk_if_X IfCondition:
  1. Extract original activity from ifTrueActivities (non-_chk_ activity)
  2. Recover original retry count from _chk_upd_X parameters
  3. Reconstruct original dependencies:
     - _chk_var dependency → was an entry point (no deps)
     - _chk_if_Y dependency → restore to Y
     - Other dependencies → keep as-is
  4. Restore original retry count on the activity policy
```

### Why Re-Onboard?

- Ensures latest checkpoint logic is applied (bug fixes, parameter type changes)
- Handles changes to the helper notebook ID or connection
- Preserves original activity behavior across multiple onboarding cycles
- Original retry counts are stored in `_chk_upd_X` parameters and recovered each time

---

## 9. Checkpoint Table Schema

**Table**: `{CHECKPOINT_LAKEHOUSE}.{CHECKPOINT_TABLE}`

| Column | Type | Description |
|---|---|---|
| `pipeline_name` | STRING NOT NULL | Pipeline display name |
| `pipeline_id` | STRING | Pipeline item GUID |
| `activity_name` | STRING NOT NULL | Activity name |
| `activity_type` | STRING | Activity type (Copy, TridentNotebook, etc.) |
| `status` | STRING NOT NULL | `COMPLETED` or `FAILED` |
| `run_id` | STRING | Pipeline run GUID |
| `error_message` | STRING | Error details (truncated to 500 chars) |
| `resolved_at` | TIMESTAMP | When the checkpoint was written |
| `resolution_method` | STRING | Always `PIPELINE_CHECKPOINT` |
| `needs_rerun` | BOOLEAN | `false` for COMPLETED, `true` for FAILED |
| `original_retry_count` | STRING | Original retry policy value |
| `failure_category` | STRING | Set by agent: `TRANSIENT`, `PERMANENT`, `DATA_QUALITY`, `AUTH` |
| `rca_notes` | STRING | Agent's root-cause analysis notes |

### Key: `(pipeline_name, activity_name)`

The MERGE operation upserts on this composite key. This means:
- One record per activity per pipeline
- Re-runs overwrite the previous status
- **Not keyed on `run_id`** — see [concurrent runs limitation](#14-limitations--edge-cases)

---

## 10. Backup Table Schema

**Table**: `{CHECKPOINT_LAKEHOUSE}.{BACKUP_TABLE}`

| Column | Type | Description |
|---|---|---|
| `pipeline_id` | STRING NOT NULL | Pipeline item GUID |
| `pipeline_name` | STRING | Pipeline display name |
| `definition_json` | STRING | Full original pipeline JSON (stringified) |
| `backed_up_at` | TIMESTAMP | When the backup was taken |

Backups are upserted on `pipeline_id` — only the latest backup is retained per pipeline.

---

## 11. Self-Healing Agent Workflow

After a pipeline fails with checkpoint onboarding:

```
1. Pipeline fails at Activity B
   └─ _chk_upd_A wrote COMPLETED (A succeeded)
   └─ _chk_fail_B wrote FAILED + error_message (B failed)
   └─ _chk_re_fail_B re-raised the error → pipeline marked FAILED

2. Self-healing agent queries checkpoint table:
   SELECT * FROM checkpoint WHERE status = 'FAILED'
   → Finds: pipeline=X, activity=B, error="Column 'foo' not found"

3. Agent classifies failure:
   UPDATE checkpoint SET failure_category = 'DATA_QUALITY',
                         rca_notes = 'Source schema changed...'
   WHERE pipeline_name = 'X' AND activity_name = 'B'

4. Agent fixes root cause (schema mapping, auth token, etc.)

5. Agent resets the FAILED checkpoint (optional):
   UPDATE checkpoint SET status = 'PENDING'
   -- or: DELETE WHERE pipeline_name = 'X' AND activity_name = 'B'

6. Agent re-runs pipeline:
   └─ _chk_load returns "A" (completed list)
   └─ _chk_if_A → A is completed → SKIP
   └─ _chk_if_B → B is not completed → EXECUTE
   └─ B succeeds → _chk_upd_B writes COMPLETED
   └─ _chk_if_C → C is not completed → EXECUTE
   └─ All succeed → _chk_reset clears checkpoints
```

---

## 12. Retry Policy Design

### Why Retry = 0?

| Scenario | Without Onboarding | With Onboarding |
|---|---|---|
| Transient failure (network blip) | Retries N times, may self-recover | Fails once → agent decides if retry is appropriate |
| Permanent failure (schema, auth) | Retries N times, wastes time/compute | Fails once → error captured → agent fixes root cause |
| Bad data from upstream | Downstream retries with same bad input | Fails once → agent traces to upstream |

### How Original Retry is Preserved

- Original retry value stored in `_chk_upd_X` parameter: `original_retry_count`
- Also stored in the backup table (full original definition)
- On re-onboard: recovered from `_chk_upd_X` and restored if unwrapping

### Retry Interval Enforcement

Fabric requires `retryIntervalInSeconds >= 30`. The `_fix_retry_intervals()` function recursively scans the entire modified definition and corrects any values below 30.

---

## 13. Rollback & Reset

### Rollback (Restore Original Pipeline)

```python
# Option A: Specific pipeline
backup = spark.sql(f"""
    SELECT definition_json FROM {LAKEHOUSE}.{BACKUP_TABLE}
    WHERE pipeline_name = 'My_Pipeline'
    ORDER BY backed_up_at DESC LIMIT 1
""").collect()[0]

b64 = base64.b64encode(backup["definition_json"].encode()).decode()
body = {"definition": {"parts": [{"path": "pipeline-content.json",
         "payload": b64, "payloadType": "InlineBase64"}]}}
rest_client.post(f".../items/{pipeline_id}/updateDefinition", json=body)
```

### Reset Checkpoints (Force Full Re-Run)

```sql
-- Specific pipeline
DELETE FROM lakehouse.pipeline_activity_checkpoints
WHERE pipeline_name = 'My_Pipeline';

-- All pipelines
DELETE FROM lakehouse.pipeline_activity_checkpoints WHERE 1=1;
```

---

## 14. Limitations & Edge Cases

| Limitation | Details |
|---|---|
| **Concurrent runs** | Checkpoint is keyed on `(pipeline_name, activity_name)`, not `run_id`. Run one instance at a time, or reset checkpoints between runs. |
| **Inner activities** | Activities inside `ForEach`, `Switch`, `Until` are NOT individually checkpointed — the parent control activity is the checkpoint unit. |
| **"Skipped" dependency condition** | If any activity uses `dependencyConditions: ["Skipped"]`, the IfCondition wrapper changes behavior (it succeeds rather than "skips" when completed). Review these pipelines manually. |
| **SecureInput/SecureOutput** | Error details may be masked for activities with secure settings — the error object is still captured but content may be redacted by Fabric. |
| **Activity names with commas** | Not supported — the skip-list uses comma-delimited matching. An assertion prevents onboarding these. |
| **Overhead** | Adds ~30-60s per activity (helper notebook execution time for checkpoint read/write). |
| **Helper notebook failure** | If `_checkpoint_helper` fails, the pipeline fails. Checkpoint infrastructure is a hard dependency. |
| **Connection auto-detection** | If no existing TridentNotebook exists in the pipeline, checkpoint activities will have no `externalReferences.connection`. May need manual setup. |

---

## 15. Configuration Reference

| Parameter | Default | Description |
|---|---|---|
| `WORKSPACE_ID` | (required) | Fabric workspace GUID |
| `CHECKPOINT_LAKEHOUSE` | (required) | Lakehouse name for checkpoint/backup tables |
| `CHECKPOINT_TABLE` | `pipeline_activity_checkpoints` | Delta table for checkpoint records |
| `HELPER_NOTEBOOK_NAME` | `_checkpoint_helper` | Notebook name deployed to workspace |
| `BACKUP_TABLE` | `pipeline_definition_backups` | Delta table for original definitions |
| `INCLUDE_PIPELINES` | `[]` (all) | fnmatch patterns for pipelines to include |
| `EXCLUDE_PIPELINES` | `["_shadow*", "_checkpoint*"]` | fnmatch patterns for pipelines to exclude |
| `DRY_RUN` | `True` | `True` = preview only, `False` = apply changes |

---

## 16. Troubleshooting

### Error: "Error converting value to RunNotebookParameter"

**Cause**: A TridentNotebook parameter has `"type": "Expression"` instead of `"type": "string"`.

**Fix**: Ensure ALL notebook parameters use `"type": "string"`. See [Section 7](#7-parameter-type-rules-critical).

### Error: `UnboundLocalError` on `_find_notebook_connection` or `_make_notebook_activity`

**Cause**: Function definitions are placed after the "already onboarded" check that calls them.

**Fix**: Move both function definitions to before the re-onboard check in the transform cell.

### Pipeline shows 202 on `updateDefinition`

**Expected**: Fabric returns 202 for long-running operations. The `_wait_for_long_operation()` helper polls until 200.

### Helper notebook returns "UNKNOWN_MODE"

**Cause**: The helper notebook currently handles `CHECK_ALL` and `UPDATE` modes. `RESET` mode hits the `else` branch.

**Impact**: None — `_chk_reset` completes successfully (exit code 0). Actual reset happens via `CHECK_ALL` on the next run (clears records when no FAILED rows exist).

### Re-onboarding doesn't pick up latest changes

**Cause**: The unwrap logic extracts originals from IfCondition wrappers. If the pipeline was manually modified after onboarding, those changes may be in unexpected locations.

**Fix**: Rollback to original definition first, then re-onboard.

### Checkpoint table has stale records

**Fix**: Use Cell 13 (Reset Checkpoints) to clear records, or query and delete specific rows.

---

## Appendix: Activity Naming Convention

| Activity Name Pattern | Type | Purpose |
|---|---|---|
| `_chk_load` | TridentNotebook | Load completed activity list from checkpoint table |
| `_chk_var` | SetVariable | Store completed list in pipeline variable |
| `_chk_if_{name}` | IfCondition | Skip wrapper — checks if activity was already completed |
| `_chk_upd_{name}` | TridentNotebook | Write COMPLETED to checkpoint table |
| `_chk_fail_{name}` | TridentNotebook | Write FAILED + error to checkpoint table |
| `_chk_re_fail_{name}` | Fail | Re-raise the error to propagate failure |
| `_chk_reset` | TridentNotebook | Clear checkpoints after full success |
