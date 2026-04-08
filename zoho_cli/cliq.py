"""Cliq scaffolding helpers and lightweight client shell."""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from zoho_cli import utils


DEFAULT_CLIQ_SCOPES = [
    "ZohoCliq.Channels.ALL",
    "ZohoCliq.Users.ALL",
    "ZohoCliq.Messages.ALL",
]


def missing_cliq_scopes(granted_scopes: list[str] | None) -> list[str]:
    granted = set(granted_scopes or [])
    return [s for s in DEFAULT_CLIQ_SCOPES if s not in granted]


def infer_cliq_base_url(
    *,
    mail_base_url: str | None = None,
    accounts_server: str | None = None,
    network: str | None = None,
) -> str:
    """Infer Cliq API base URL from known Zoho region hosts."""
    if network:
        return f"https://cliq.zoho.com/network/{network}/api/v2"

    if mail_base_url:
        parsed = urlparse(mail_base_url)
        host = parsed.netloc
        if host.startswith("mail."):
            return f"{parsed.scheme}://{host.replace('mail.', 'cliq.', 1)}/api/v2"

    if accounts_server:
        parsed = urlparse(accounts_server)
        host = parsed.netloc
        if host.startswith("accounts."):
            return f"{parsed.scheme}://{host.replace('accounts.', 'cliq.', 1)}/api/v2"

    return "https://cliq.zoho.com/api/v2"


class ZohoCliqClient:
    """Minimal Cliq client shell for phase-1 scaffolding."""

    def __init__(self, access_token: str, base_url: str | None = None) -> None:
        self.base_url = (base_url or infer_cliq_base_url()).rstrip("/")
        self._headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}

    def _get(self, path: str, params: dict | None = None) -> dict:
        resp = httpx.get(
            f"{self.base_url}{path}",
            headers=self._headers,
            params=params or {},
            timeout=httpx.Timeout(30.0),
        )
        if not resp.is_success:
            utils.error_exit("api_error", f"HTTP {resp.status_code} GET {path}: {resp.text}")
        return resp.json()

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict:
        resp = httpx.post(
            f"{self.base_url}{path}",
            headers=self._headers,
            json=payload,
            timeout=httpx.Timeout(30.0),
        )
        if not resp.is_success:
            utils.error_exit("api_error", f"HTTP {resp.status_code} POST {path}: {resp.text}")
        return resp.json()

    def channels(self, *, limit: int = 50) -> dict:
        """List channels."""
        return self._get("/channels", {"limit": limit})

    def users(self, *, limit: int = 50) -> dict:
        """List users."""
        return self._get("/users", {"limit": limit})

    def send_message(
        self,
        text: str,
        *,
        channel_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> dict:
        """Send a message to either a channel or a user."""
        if bool(channel_id) == bool(user_id):
            raise ValueError("Provide exactly one of channel_id or user_id")

        payload = {"text": text}
        if channel_id:
            return self._post_json(f"/channels/{channel_id}/message", payload)
        return self._post_json(f"/users/{user_id}/message", payload)
