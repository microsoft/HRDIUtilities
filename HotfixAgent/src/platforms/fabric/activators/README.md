# Fabric Activators — Onboarding

Activator (Reflex) configurations for automatic pipeline onboarding triggers.

## Planned

- **Auto-Onboard Activator** — triggers the onboarding notebook when a new
  pipeline is created in the workspace (via Fabric event stream)
- **Re-Onboard Activator** — triggers re-onboarding when a pipeline definition
  is modified (to re-wrap with latest checkpoint logic)

## Activator Config Schema

```json
{
  "displayName": "AutoOnboard_NewPipeline",
  "type": "Reflex",
  "trigger": {
    "type": "FabricEvent",
    "event": "Microsoft.Fabric.ItemCreated",
    "filter": {
      "itemType": "DataPipeline"
    }
  },
  "action": {
    "type": "TridentNotebook",
    "notebookName": "OnboardPipelines_Checkpoint",
    "parameters": {
      "INCLUDE_PIPELINES": ["${event.itemName}"],
      "DRY_RUN": false
    }
  }
}
```

> **Note**: Fabric Activator/Reflex is in preview. The schema above is illustrative
> and may change as the feature evolves.
