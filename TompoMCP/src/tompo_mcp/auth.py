"""
Authentication for TOMPo MCP.

Uses DefaultAzureCredential (Azure CLI / VS Code) by default.
Also accepts a raw bearer token for Fabric Notebook scenarios.
"""

from __future__ import annotations

import logging
from typing import Optional

from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)

_credential: Optional[DefaultAzureCredential] = None


def _get_credential() -> DefaultAzureCredential:
    global _credential
    if _credential is None:
        _credential = DefaultAzureCredential(
            exclude_shared_token_cache_credential=True,
        )
        logger.info("DefaultAzureCredential initialized")
    return _credential


class TokenProvider:
    """Provides bearer tokens for Fabric/Power BI API calls.

    If initialized with a raw token string, uses it directly (Fabric Notebook).
    Otherwise uses DefaultAzureCredential (az login / VS Code identity).
    """

    def __init__(self, token: Optional[str] = None) -> None:
        self._raw_token = token

    def get_powerbi_token(self) -> str:
        if self._raw_token:
            return self._raw_token
        cred = _get_credential()
        result = cred.get_token("https://analysis.windows.net/powerbi/api/.default")
        return result.token

    def get_fabric_token(self) -> str:
        if self._raw_token:
            return self._raw_token
        cred = _get_credential()
        result = cred.get_token("https://api.fabric.microsoft.com/.default")
        return result.token

    def get_graph_token(self) -> str:
        if self._raw_token:
            return self._raw_token
        cred = _get_credential()
        result = cred.get_token("https://graph.microsoft.com/.default")
        return result.token
