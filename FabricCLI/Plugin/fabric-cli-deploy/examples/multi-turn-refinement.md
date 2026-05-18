# Multi-Turn Refinement Examples

Four conversations that demonstrate how the skill iteratively negotiates the right deployment with the user.

---

## Conversation A — From "deploy fabric" to a fully-formed run

```
[turn 1] User:  deploy fabric
[turn 1] Skill: Which verb do you want?
                  (full / infra-only / code-only / validate / plan / update-config / status)

[turn 2] User:  full
[turn 2] Skill: Workspace name?

[turn 3] User:  acme_dev_ws
[turn 3] Skill: Environment? (dev / test / prod)

[turn 4] User:  dev
[turn 4] Skill: [1/6] ✓ Intake resolved — verb=full workspace=acme_dev_ws env=dev
                [2/6] ✗ Pre-flight FAILED — `fab` CLI not found on PATH.
                
                Remediation (F-02):
                  Install with:  pip install ms-fabric-cli
                  Then run:      fab auth login
                
                Have you completed install? (yes / cancel)

[turn 5] User:  yes
[turn 5] Skill: [2/6] ✓ Pre-flight OK — fab 1.2.3, Python 3.11.4, authenticated as you@acme.com
                [3/6] ✓ Config validated — 9 required keys present
                [4/6] ✓ Artifacts inventoried — 2 notebooks, 0 pipelines, 0 models, 0 reports
                
                Note: no pipelines/models/reports found under Code/Fabric. Proceed anyway?

[turn 6] User:  yes
[turn 6] Skill: [5/6] ⏳ Deploying…
                [6/6] ✓ Summary ready
                
                (final summary block per SKILL §9)
```

---

## Conversation B — Config refinement before deploy

```
[turn 1] User:  /fabric-cli-deploy update-config
[turn 1] Skill: Workspace name? (leave blank to keep existing)

[turn 2] User:  contoso_test_fabric_ws
[turn 2] Skill: Environment?

[turn 3] User:  test
[turn 3] Skill: Storage account name for ADLS shortcuts? (leave blank to skip shortcut creation)

[turn 4] User:  contosostorage
[turn 4] Skill: SPN object ID for workspace RBAC? (leave blank to skip)

[turn 5] User:  (blank)
[turn 5] Skill: Here's the proposed diff to Config/fabric_config.json:
                
                ```diff
                -    "fabricWorkspaceName": { "value": "contose_dev_fabric_ws" },
                +    "fabricWorkspaceName": { "value": "contoso_test_fabric_ws" },
                -    "environmentName":     { "value": "dev" },
                +    "environmentName":     { "value": "test" },
                -    "storageAccountName":  { "value": "Contosostorage" },
                +    "storageAccountName":  { "value": "contosostorage" },
                ```
                
                Apply? (yes/no)

[turn 6] User:  yes
[turn 6] Skill: ✓ Config updated. Re-run `/fabric-cli-deploy full` when ready.
```

---

## Conversation C — Recovering from a placeholder-hygiene failure (F-05)

```
[turn 1] User:  /fabric-cli-deploy full
[turn 1] Skill: [1/6] ✓ Intake resolved
                [2/6] ✓ Pre-flight OK
                [3/6] ✓ Config validated
                [4/6] ✗ Placeholder hygiene violation
                
                File:   Code/Fabric/Notebooks/01_Ingest_StoreSales.Notebook/notebook-content.ipynb
                Line:   42
                Found:  "lakehouseId": "8f4e1c20-***-***-***-************"   (literal GUID)
                Expect: "lakehouseId": "##fabricLakehouseId##"
                
                Remediation (F-05): edit the notebook to use the placeholder, then re-run
                `/fabric-cli-deploy validate`. Halting before deployment to avoid drift.

[turn 2] User:  fixed it
[turn 2] Skill: Re-running validation… (no implicit retry; user must re-trigger)
                Please re-invoke: /fabric-cli-deploy validate

[turn 3] User:  /fabric-cli-deploy validate
[turn 3] Skill: [4/6] ✓ Artifacts inventoried — placeholders OK
                Ready to deploy. Re-invoke `/fabric-cli-deploy full` to proceed.
```

---

## Conversation D — Production deployment with typed confirmation

```
[turn 1] User:  /fabric-cli-deploy full --env prod --workspace acme_prod_fabric_ws
[turn 1] Skill: ⚠ Production deployment requested.
                Please retype the workspace name exactly to confirm:
                  acme_prod_fabric_ws

[turn 2] User:  acme-prod-fabric-ws        (note: hyphens instead of underscores)
[turn 2] Skill: Confirmation does not match. Aborted. No changes made.
                
                Re-invoke when ready and type the name exactly as configured.

[turn 3] User:  acme_prod_fabric_ws
[turn 3] Skill: ✓ Production confirmation accepted.
                [1/6] ✓ Intake resolved — verb=full workspace=acme_prod_fabric_ws env=prod
                [2/6] …
```

---

## Conversation E — Partial failure: one notebook fails, others succeed

```
[turn 1] User:  /fabric-cli-deploy full --workspace contoso_dev_fabric_ws --env dev
[turn 1] Skill: [1/6] ✓ Intake resolved — verb=full workspace=contoso_dev_fabric_ws env=dev
                [2/6] ✓ Pre-flight OK — fab 1.6.1, Python 3.11.4, authenticated as you@contoso.com
                [3/6] ✓ Config validated — 9 required keys present
                [4/6] ✓ Artifacts inventoried — 4 notebooks, 1 pipeline, 1 model, 1 report
                [5/6] ⏳ Deploying… (running oneinstaller.py, this can take 5–15 min)
                [6/6] ✓ Summary ready (PARTIAL — see Failures)

                ============================================================
                  Microsoft Fabric Deployment Summary (PARTIAL — see Failures)
                ============================================================
                  Workspace : contoso_dev_fabric_ws
                  Tenant    : contoso
                  Env       : dev
                  Verb      : full
                  Started   : 2026-05-16T14:08:02Z
                  Duration  : 6m 41s

                Infrastructure
                  Lakehouse        : contoso_lakehouse        [reused]
                  Connection       : adls_connection          [reused]
                  Shortcuts        : 3 total                  [0 created, 3 reused, 0 failed]
                  Spark Pool       : analyticssparkpool       [updated]
                  OneLake Folders  : 4 total                  [0 created, 4 reused]
                  Workspace Access : SPN abcd1234-…           [reused]

                Code Artifacts
                  Notebooks        : 4 total                  [3 succeeded, 1 failed]
                  Pipelines        : 1 total                  [0 succeeded, 1 failed]
                  Semantic Models  : 1 total                  [1 succeeded, 0 failed]
                  Reports          : 1 total                  [1 succeeded, 0 failed]

                Warnings
                  (none)

                Failures
                  - Notebook  03_Transform_Sales.Notebook  FAILED
                      Reason: invalid notebook-content.ipynb (unparseable JSON at line 218)
                      Action: re-export with `fab export` or fix the JSON manually.
                  - Pipeline  StoreSalesRefresh.DataPipeline  FAILED
                      Reason: references unknown notebook id (depends on 03_Transform_Sales).
                      Action: redeploy 03_Transform_Sales first, then re-run `code-only`.

                Logs
                  - Detailed : Logs/runninglog_16052026.txt
                  - Audit CSV: Logs/deployment_log_16052026.csv

                Next steps
                  1. Open the workspace in the Fabric portal.
                  2. Validate pipeline schedules and data refreshes.
                  3. Re-run `/fabric-cli-deploy validate` after any code edit.
                ============================================================

                Two artifacts failed (per F-08). I did **not** auto-retry; both
                are logical failures that need a human fix. Suggested
                remediation is per-artifact above.

[turn 2] User:  fix the notebook and re-deploy just that one
[turn 2] Skill: I can't surgically redeploy a single artifact in v1.0 — `oneinstaller.py`
                runs the whole code phase in one pass. The safe path is:
                  1. Fix Code/Fabric/Notebooks/03_Transform_Sales.Notebook/notebook-content.ipynb
                  2. Run `/fabric-cli-deploy validate` to confirm placeholder hygiene + JSON parse.
                  3. Run `/fabric-cli-deploy code-only` to re-import all code artifacts
                     (the 3 already-succeeded notebooks will be force-overwritten with
                     identical content — idempotent by §2.2).

[turn 3] User:  ok done step 1, run validate
[turn 3] Skill: /fabric-cli-deploy validate
                [4/6] ✓ Artifacts inventoried — placeholders OK, JSON parses on all 4 notebooks
                Ready to deploy. Re-invoke `/fabric-cli-deploy code-only` to proceed.
```
