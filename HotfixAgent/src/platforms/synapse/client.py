"""Synapse Analytics REST API client — stub.

TODO: Implement using Azure Management API:
  https://management.azure.com/subscriptions/{sub}/resourceGroups/{rg}/
  providers/Microsoft.Synapse/workspaces/{ws}/pipelines

Key differences from Fabric:
  - Uses ARM API (management.azure.com) instead of Fabric API
  - Pipeline definitions use ADF-compatible JSON schema
  - Auth via DefaultAzureCredential with management.azure.com scope
  - Pipeline runs accessed via /pipelineruns endpoint
  - Activity runs accessed via /activityruns endpoint
"""

from __future__ import annotations

from typing import Any, Optional

from src.platforms.base import ActivityStatus, PipelineInfo, PipelinePlatformAdapter


class SynapseClient(PipelinePlatformAdapter):
    """Synapse Analytics adapter — not yet implemented."""

    def __init__(self, subscription_id: str, resource_group: str, workspace_name: str):
        self._subscription_id = subscription_id
        self._resource_group = resource_group
        self._workspace_name = workspace_name
        raise NotImplementedError("Synapse adapter is planned for a future release.")

    def list_pipelines(self, workspace_id: str) -> list[PipelineInfo]:
        raise NotImplementedError

    def get_definition(self, workspace_id: str, pipeline_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def update_definition(self, workspace_id: str, pipeline_id: str, definition: dict[str, Any]) -> None:
        raise NotImplementedError

    def resolve_activity_statuses(self, workspace_id: str, pipeline_id: str, run_id: str) -> list[ActivityStatus]:
        raise NotImplementedError

    def trigger_pipeline(self, workspace_id: str, pipeline_id: str, parameters: Optional[dict] = None) -> str:
        raise NotImplementedError
