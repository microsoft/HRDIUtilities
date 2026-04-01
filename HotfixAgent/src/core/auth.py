"""Azure authentication wrapper with token caching.

Uses DefaultAzureCredential for seamless authentication across:
- Local development (Azure CLI / VS Code)
- Fabric notebook context (managed identity)
- CI/CD pipelines (service principal via env vars)
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)

_FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"
_MANAGEMENT_SCOPE = "https://management.azure.com/.default"


class TokenProvider:
    """Thread-safe token provider with automatic refresh."""

    def __init__(self, scope: str = _FABRIC_SCOPE, credential: Optional[DefaultAzureCredential] = None):
        self._scope = scope
        self._credential = credential or DefaultAzureCredential()
        self._token: Optional[str] = None
        self._expires_at: float = 0.0
        self._lock = threading.Lock()

    def get_token(self) -> str:
        """Return a valid access token, refreshing if expired."""
        with self._lock:
            if self._token and time.time() < self._expires_at - 60:
                return self._token
            token_response = self._credential.get_token(self._scope)
            self._token = token_response.token
            self._expires_at = token_response.expires_on
            logger.debug("Token refreshed, expires at %s", self._expires_at)
            return self._token

    @property
    def headers(self) -> dict[str, str]:
        """Return Authorization header dict."""
        return {"Authorization": f"Bearer {self.get_token()}"}


def get_fabric_token_provider() -> TokenProvider:
    """Create a TokenProvider for the Fabric REST API."""
    return TokenProvider(scope=_FABRIC_SCOPE)


def get_management_token_provider() -> TokenProvider:
    """Create a TokenProvider for Azure Resource Manager (Synapse, ADF)."""
    return TokenProvider(scope=_MANAGEMENT_SCOPE)
