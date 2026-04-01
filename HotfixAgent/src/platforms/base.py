"""Abstract base class for pipeline platform adapters.

Each platform (Fabric, Synapse, ADF) implements this interface so that
the onboarding, shadow-creation, and monitoring logic can work
across all platforms without code changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class PipelineInfo:
    """Minimal pipeline metadata."""

    id: str
    name: str
    workspace_id: str
    platform: str  # "fabric" | "synapse" | "adf"


@dataclass
class ActivityStatus:
    """Status of a single activity within a pipeline run."""

    name: str
    activity_type: str
    status: str  # "Succeeded" | "Failed" | "Cancelled" | "InProgress" | "NotRun"
    error_message: Optional[str] = None
    duration_seconds: Optional[float] = None


class PipelinePlatformAdapter(ABC):
    """Interface that every pipeline platform must implement."""

    @abstractmethod
    def list_pipelines(self, workspace_id: str) -> list[PipelineInfo]:
        """Return all pipelines in the workspace."""
        ...

    @abstractmethod
    def get_definition(self, workspace_id: str, pipeline_id: str) -> dict[str, Any]:
        """Return the pipeline definition JSON."""
        ...

    @abstractmethod
    def update_definition(self, workspace_id: str, pipeline_id: str, definition: dict[str, Any]) -> None:
        """Push an updated pipeline definition."""
        ...

    @abstractmethod
    def resolve_activity_statuses(self, workspace_id: str, pipeline_id: str, run_id: str) -> list[ActivityStatus]:
        """Return per-activity status for a specific pipeline run."""
        ...

    @abstractmethod
    def trigger_pipeline(self, workspace_id: str, pipeline_id: str, parameters: Optional[dict] = None) -> str:
        """Trigger a pipeline run and return the run ID."""
        ...
