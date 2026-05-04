"""Core HTTP client with shared request/response handling."""

import logging
from typing import Optional

import httpx

from zoho_cli.core.errors import ApiError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(30.0)


class HttpClient:
    """Shared HTTP client for Zoho API calls."""

    def __init__(self, base_url: str, auth_token: Optional[str] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = (
            {"Authorization": f"Zoho-oauthtoken {auth_token}"} if auth_token else {}
        )
        self._client = httpx.Client(headers=self.headers, timeout=DEFAULT_TIMEOUT)

    def get(self, path: str, params: Optional[dict] = None) -> dict:
        """GET request with automatic error handling."""
        url = f"{self.base_url}{path}"
        logger.debug("GET %s params=%s", url, params)
        resp = self._client.get(url, headers=self.headers, params=params or {})
        return self._handle_response(resp)

    def post_json(self, path: str, payload: dict) -> dict:
        """POST with JSON body."""
        url = f"{self.base_url}{path}"
        logger.debug("POST %s", url)
        resp = self._client.post(url, headers=self.headers, json=payload)
        return self._handle_response(resp)

    def post_multipart(
        self, path: str, data: dict, files: list[tuple], long_timeout: bool = False
    ) -> dict:
        """POST with multipart form data."""
        url = f"{self.base_url}{path}"
        logger.debug("POST (multipart) %s", url)
        timeout = httpx.Timeout(120.0) if long_timeout else DEFAULT_TIMEOUT
        resp = self._client.post(
            url, headers=self.headers, data=data, files=files, timeout=timeout
        )
        return self._handle_response(resp)

    def put(self, path: str, payload: dict) -> dict:
        """PUT request with JSON body."""
        url = f"{self.base_url}{path}"
        logger.debug("PUT %s", url)
        resp = self._client.put(url, headers=self.headers, json=payload)
        return self._handle_response(resp)

    def delete(self, path: str) -> dict:
        """DELETE request."""
        url = f"{self.base_url}{path}"
        logger.debug("DELETE %s", url)
        resp = self._client.delete(url, headers=self.headers)
        return self._handle_response(resp)

    def get_bytes(self, path: str) -> bytes:
        """GET request returning raw bytes."""
        url = f"{self.base_url}{path}"
        logger.debug("GET (binary) %s", url)
        resp = self._client.get(url, headers=self.headers, timeout=httpx.Timeout(120.0))
        return self._handle_binary_response(resp)

    def _handle_response(self, resp: httpx.Response) -> dict:
        """Handle JSON response and raise on error."""
        logger.debug("→ %s", resp.status_code)
        if not resp.is_success:
            raise ApiError.from_response(resp)
        return resp.json()

    def _handle_binary_response(self, resp: httpx.Response) -> bytes:
        """Handle binary response and raise on error."""
        logger.debug("→ %s", resp.status_code)
        if not resp.is_success:
            raise ApiError.from_response(resp)
        return resp.content
