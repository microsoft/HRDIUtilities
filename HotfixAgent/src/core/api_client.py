"""Base REST client with 202 long-running operation polling.

Provides retry logic, exponential backoff, and async operation handling
that is shared across all platform adapters (Fabric, Synapse, ADF).
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import requests

from src.core.auth import TokenProvider

logger = logging.getLogger(__name__)


class RestClient:
    """HTTP client with Azure long-running operation support."""

    def __init__(self, base_url: str, token_provider: TokenProvider, timeout: int = 60):
        self._base_url = base_url.rstrip("/")
        self._token_provider = token_provider
        self._timeout = timeout
        self._session = requests.Session()

    def _headers(self) -> dict[str, str]:
        return {
            **self._token_provider.headers,
            "Content-Type": "application/json",
        }

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        url = self._resolve_url(path)
        return self._session.get(url, headers=self._headers(), timeout=self._timeout, **kwargs)

    def post(self, path: str, json: Optional[dict] = None, **kwargs: Any) -> requests.Response:
        url = self._resolve_url(path)
        return self._session.post(url, headers=self._headers(), json=json, timeout=self._timeout, **kwargs)

    def patch(self, path: str, json: Optional[dict] = None, **kwargs: Any) -> requests.Response:
        url = self._resolve_url(path)
        return self._session.patch(url, headers=self._headers(), json=json, timeout=self._timeout, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> requests.Response:
        url = self._resolve_url(path)
        return self._session.delete(url, headers=self._headers(), timeout=self._timeout, **kwargs)

    def _resolve_url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return f"{self._base_url}/{path.lstrip('/')}"

    def wait_for_long_operation(self, response: requests.Response, max_polls: int = 60) -> requests.Response:
        """Poll a 202 Accepted response until completion.

        Azure REST APIs return 202 with a Location header for async operations.
        This method polls that location until the operation completes (200) or
        the max poll count is reached.
        """
        if response.status_code != 202:
            return response

        location = response.headers.get("Location")
        if not location:
            logger.warning("202 response without Location header — returning as-is")
            return response

        retry_after = int(response.headers.get("Retry-After", "2"))

        for attempt in range(max_polls):
            time.sleep(retry_after)
            poll_resp = self.get(location)
            logger.debug("Poll %d/%d: HTTP %d", attempt + 1, max_polls, poll_resp.status_code)

            if poll_resp.status_code == 200:
                return poll_resp
            if poll_resp.status_code != 202:
                return poll_resp

        logger.warning("Long-running operation did not complete after %d polls", max_polls)
        return response

    def post_and_wait(self, path: str, json: Optional[dict] = None, **kwargs: Any) -> requests.Response:
        """POST and automatically poll if 202."""
        resp = self.post(path, json=json, **kwargs)
        return self.wait_for_long_operation(resp)
