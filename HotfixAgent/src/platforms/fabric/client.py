"""Fabric REST API client implementing the PipelinePlatformAdapter interface.

All Fabric-specific API calls are centralized here so that notebooks,
CLI scripts, and tests can share the same logic.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, Optional

from src.core.api_client import RestClient
from src.core.auth import get_fabric_token_provider
from src.core.config import HotfixAgentSettings
from src.platforms.base import ActivityStatus, PipelineInfo, PipelinePlatformAdapter

logger = logging.getLogger(__name__)


class FabricClient(PipelinePlatformAdapter):
    """Fabric REST API adapter."""

    def __init__(self, settings: Optional[HotfixAgentSettings] = None):
        self._settings = settings or HotfixAgentSettings()
        self._client = RestClient(
            base_url=self._settings.fabric_api_url,
            token_provider=get_fabric_token_provider(),
        )

    # ── PipelinePlatformAdapter implementation ──────────────────────

    def list_pipelines(self, workspace_id: str) -> list[PipelineInfo]:
        resp = self._client.get(f"/workspaces/{workspace_id}/items?type=DataPipeline")
        resp.raise_for_status()
        return [
            PipelineInfo(
                id=p["id"],
                name=p["displayName"],
                workspace_id=workspace_id,
                platform="fabric",
            )
            for p in resp.json().get("value", [])
        ]

    def get_definition(self, workspace_id: str, pipeline_id: str) -> dict[str, Any]:
        resp = self._client.post_and_wait(f"/workspaces/{workspace_id}/items/{pipeline_id}/getDefinition")
        resp.raise_for_status()

        for part in resp.json().get("definition", {}).get("parts", []):
            if part.get("path") == "pipeline-content.json":
                return json.loads(base64.b64decode(part["payload"]).decode("utf-8"))

        raise ValueError(f"No pipeline-content.json found for {pipeline_id}")

    def update_definition(self, workspace_id: str, pipeline_id: str, definition: dict[str, Any]) -> None:
        b64_payload = base64.b64encode(json.dumps(definition).encode("utf-8")).decode("utf-8")
        body = {
            "definition": {
                "parts": [
                    {
                        "path": "pipeline-content.json",
                        "payload": b64_payload,
                        "payloadType": "InlineBase64",
                    }
                ]
            }
        }
        resp = self._client.post_and_wait(f"/workspaces/{workspace_id}/items/{pipeline_id}/updateDefinition", json=body)
        if resp.status_code not in (200, 204):
            raise RuntimeError(f"Update failed: HTTP {resp.status_code} — {resp.text[:300]}")

    def resolve_activity_statuses(self, workspace_id: str, pipeline_id: str, run_id: str) -> list[ActivityStatus]:
        # Delegate to the dedicated ActivityResolver for full child-job correlation
        from src.platforms.fabric.activity_resolver import ActivityResolver

        resolver = ActivityResolver(self._client, workspace_id)
        return resolver.resolve(pipeline_id, run_id)

    def trigger_pipeline(self, workspace_id: str, pipeline_id: str, parameters: Optional[dict] = None) -> str:
        body: dict[str, Any] = {}
        if parameters:
            body["executionData"] = {"parameters": parameters}

        resp = self._client.post(
            f"/workspaces/{workspace_id}/items/{pipeline_id}/jobs/instances?jobType=Pipeline",
            json=body,
        )
        if resp.status_code not in (200, 201, 202):
            raise RuntimeError(f"Trigger failed: HTTP {resp.status_code} — {resp.text[:300]}")

        return resp.headers.get("x-ms-operation-id", resp.json().get("id", "unknown"))

    # ── Fabric-specific helpers ─────────────────────────────────────

    def get_item(self, workspace_id: str, item_id: str) -> dict[str, Any]:
        """Fetch a single workspace item's metadata."""
        resp = self._client.get(f"/workspaces/{workspace_id}/items/{item_id}")
        resp.raise_for_status()
        return resp.json()

    def list_items(self, workspace_id: str, item_type: Optional[str] = None) -> list[dict[str, Any]]:
        """List workspace items, optionally filtered by type."""
        url = f"/workspaces/{workspace_id}/items"
        if item_type:
            url += f"?type={item_type}"
        resp = self._client.get(url)
        resp.raise_for_status()
        return resp.json().get("value", [])

    def create_item(self, workspace_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """Create a new item in the workspace."""
        resp = self._client.post_and_wait(f"/workspaces/{workspace_id}/items", json=body)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Create failed: HTTP {resp.status_code} — {resp.text[:300]}")
        return resp.json()
