# Troubleshooting Guide

### Common Issues & Solutions

#### ⚠️ Authentication Errors

**Symptom:** `Error: Not authenticated` or `401 Unauthorized`

**Solutions:**
- Ensure you're logged in: `fab auth login`
- Verify you have Admin access to the Fabric workspace
- Re-authenticate if credentials have expired

#### ⚠️ Resource Conflicts

**Symptom:** `Resource already exists` or `409 Conflict`

**Solutions:**
- The script is idempotent — simply **re-run the deployment**
- Existing resources are detected and skipped automatically
- If conflicts persist, verify resource names in `fabric_config.json`
- Check for manual changes in the Fabric portal that conflict with config

#### ⚠️ Missing Prerequisites

**Symptom:** `Command not found` or `Module not found`

**Solutions:**
- Verify Python 3.10+ is installed: `python --version`
- Install Fabric CLI: `pip install ms-fabric-cli`
- Ensure all tools are in your PATH environment variable

#### ⚠️ Configuration Issues

**Symptom:** `Missing required parameter` or `Invalid configuration`

**Solutions:**
- Double-check all **required parameters** are filled in `fabric_config.json`
- Verify GUIDs are in correct format
- Ensure workspace name matches exactly (case-sensitive)
- Validate JSON syntax

#### ⚠️ Lakehouse Creation Failures

**Symptom:** `Failed to create lakehouse` or `Insufficient capacity`

**Solutions:**
- **Check Fabric capacity** — ensure you have available capacity units
- **Verify lakehouse name availability** — names must be unique in the workspace
- **Check workspace permissions** — ensure you have Admin access
- **Try a different name** — update `fabricLakehouseName` in `fabric_config.json`
- **Review logs** — check `Logs/runninglog_*.txt` for detailed error messages

#### ⚠️ Connection Creation Failures

**Symptom:** `Failed to create connection` or `Invalid credentials`

**Solutions:**
- Ensure the storage account exists and matches `storageAccountName` in config
- Verify `fabricWorkspaceIdentity` GUID is correct
- Check that Workspace Identity is enabled in workspace settings
- **Retry with custom connection name** — add `connectionName` explicitly to `connectionConfiguration` in config

#### ⚠️ Shortcut Creation Failures

**Symptom:** `Failed to create shortcut` or `Invalid path`

**Solutions:**
- Ensure **connection was created successfully** (check previous step)
- Verify Workspace Identity has **Storage Blob Data Contributor** role on the storage account
- Confirm container names in `shortcutConfiguration` match existing containers
- Check the storage account is accessible and not behind firewall rules
- **Re-run deployment** — shortcuts are idempotent and will retry

#### ⚠️ Model/Report Binding Failures

**Symptom:** `##semanticModelId## not replaced` or `Report failed to load`

**Solutions:**
- **Verify naming convention** — report name must match model name:
  - ✅ `SalesAnalysis.SemanticModel` + `SalesAnalysis.Report`
  - ❌ `SalesAnalysis.SemanticModel` + `Dashboard.Report`
- Ensure semantic model deployed successfully before report
- Check `modelConfiguration` in `fabric_config.json` — model IDs should be populated
- Review `definition.pbir` to confirm placeholder syntax is correct

#### ⚠️ Pipeline/Notebook Binding Failures

**Symptom:** `##NotebookName## not replaced` or `Notebook not found`

**Solutions:**
- Ensure notebook was deployed before pipeline
- Verify placeholder matches notebook folder name (without `.Notebook` suffix):
  - ✅ `DataIngestion.Notebook` → use `##DataIngestion##`
  - ❌ `DataIngestion.Notebook` → don't use `##DataIngestion.Notebook##`
- Check `notebookConfiguration` in `fabric_config.json` for notebook IDs
- Review pipeline JSON for correct placeholder format

#### 📋 Log Analysis

If deployment fails, check the logs for detailed diagnostic information:

```bash
# Human-readable execution log
cat Logs/runninglog_DDMMYYYY.txt

# Structured CSV audit trail (open in Excel)
open Logs/deployment_log_DDMMYYYY.csv
```

**CSV columns:** Timestamp, Status, Component, Action, Result, ErrorDetails

### 💡 Best Practices

- ✅ **Test in non-production first** — always validate in dev before prod
- ✅ **Review configuration carefully** — double-check all GUIDs and names
- ✅ **Check permissions before deployment** — verify access on all resources
- ✅ **Keep logs for audit** — retain deployment logs for troubleshooting
- ✅ **Save Config file** — Do not forget to save the config file after updates
- ✅ **Use version control** — track changes to code artifacts
- ✅ **Document custom configurations** — note any deviations from defaults
