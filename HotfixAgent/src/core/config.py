"""Application configuration loaded from environment variables and Key Vault.

Uses pydantic-settings for type-safe configuration with .env file support.
"""

from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class HotfixAgentSettings(BaseSettings):
    """Central configuration for HotfixAgent."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Fabric Workspace ──
    workspace_id: str = ""
    checkpoint_lakehouse: str = ""
    checkpoint_table: str = "pipeline_activity_checkpoints"
    backup_table: str = "pipeline_definition_backups"
    helper_notebook_name: str = "_checkpoint_helper"

    # ── Agent Notification ──
    agent_workspace_id: str = ""
    agent_pipeline_name: str = "PipelineMonitoring"
    agent_pipeline_id: str = ""
    notify_agent_on_failure: bool = True

    # ── Azure Key Vault ──
    key_vault_url: Optional[str] = None

    # ── Teams ──
    teams_webhook_url: Optional[str] = None

    # ── API Base URLs ──
    fabric_api_url: str = "https://api.fabric.microsoft.com/v1"
    management_api_url: str = "https://management.azure.com"


def get_settings() -> HotfixAgentSettings:
    """Load settings from environment / .env file."""
    return HotfixAgentSettings()
