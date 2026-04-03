# Fabric Pipelines — Onboarding

Pipeline definitions that support the HotfixAgent onboarding workflow.

## PipelineMonitoring

The `PipelineMonitoring` pipeline is triggered by the checkpoint helper notebook
when a pipeline activity fails. It calls the AI Foundry agent (PipelineAgent)
to perform root-cause analysis.

### Pipeline Parameters

| Parameter | Type | Description |
|---|---|---|
| `Type` | string | Event type (e.g., `PipelineActivityFailure`) |
| `Source` | string | Always `SelfHealingAgent` |
| `WorkspaceId` | string | Source workspace GUID |
| `WorkspaceName` | string | Source workspace display name |
| `JobInstanceId` | string | Pipeline run ID |
| `PipelineName` | string | Failed pipeline name |
| `PipelineId` | string | Failed pipeline GUID |
| `ActivityName` | string | Failed activity name |
| `ActivityType` | string | Activity type (e.g., `TridentNotebook`) |
| `ErrorMessage` | string | First 500 chars of error message |

### Deployment

This pipeline is created manually in the Agent workspace. The notebook-based
onboarding tool auto-resolves the pipeline ID by name (`PipelineMonitoring`).
