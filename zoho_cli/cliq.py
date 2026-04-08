"""Cliq scaffolding helpers and lightweight client shell."""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from zoho_cli import utils


DEFAULT_CLIQ_SCOPES = [
    "ZohoCliq.Channels.READ",
    "ZohoCliq.Users.READ",
    "ZohoCliq.Messages.CREATE",
    "ZohoCliq.Webhooks.CREATE",
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

    def _post_json_with_fallback(self, paths: list[str], payload: dict[str, Any]) -> dict:
        """Try multiple POST paths, falling back on request_url_invalid/404 style misses."""
        last_error: tuple[int, str, str] | None = None
        saw_scope_invalid = False
        for path in paths:
            resp = httpx.post(
                f"{self.base_url}{path}",
                headers=self._headers,
                json=payload,
                timeout=httpx.Timeout(30.0),
            )
            if resp.is_success:
                return resp.json()

            body = resp.text or ""
            last_error = (resp.status_code, path, body)
            lowered = body.lower()
            scope_invalid = "oauthtoken_scope_invalid" in lowered
            if scope_invalid:
                saw_scope_invalid = True

            if resp.status_code in (404, 405) or "request_url_invalid" in lowered or scope_invalid:
                continue

            utils.error_exit("api_error", f"HTTP {resp.status_code} POST {path}: {resp.text}")

        if saw_scope_invalid:
            utils.error_exit(
                "oauth_scope_invalid",
                "Cliq token is missing required message scope. Re-run `zoho login --with-cliq` and grant `ZohoCliq.Webhooks.CREATE`, then retry.",
            )

        if last_error is not None:
            status, path, body = last_error
            utils.error_exit("api_error", f"HTTP {status} POST {path}: {body}")

        utils.error_exit("api_error", "No candidate endpoint available for request")
        return {}

    def _resolve_channel_message_paths(self, channel_id: str) -> list[str]:
        """Resolve channel-id to sendable chat/unique-name message endpoints."""
        try:
            resp = httpx.get(
                f"{self.base_url}/channels/{channel_id}",
                headers=self._headers,
                timeout=httpx.Timeout(30.0),
            )
        except httpx.HTTPError:
            return []

        if not resp.is_success:
            return []

        try:
            payload = resp.json()
        except ValueError:
            return []

        data = payload.get("data", payload)
        if not isinstance(data, dict):
            return []

        paths: list[str] = []
        chat_id = data.get("chat_id") or data.get("chatId")
        if isinstance(chat_id, str) and chat_id.strip():
            paths.append(f"/chats/{chat_id.strip()}/message")

        unique_name = (
            data.get("unique_name")
            or data.get("channel_unique_name")
            or data.get("uniqueName")
        )
        if isinstance(unique_name, str) and unique_name.strip():
            paths.append(f"/channelsbyname/{unique_name.strip()}/message")

        return paths

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
            candidates = [
                f"/channelsbyname/{channel_id}/message",
                f"/chats/{channel_id}/message",
            ]
            candidates.extend(self._resolve_channel_message_paths(channel_id))

            seen: set[str] = set()
            paths = [p for p in candidates if not (p in seen or seen.add(p))]
            return self._post_json_with_fallback(paths, payload)

        return self._post_json_with_fallback(
            [
                f"/buddies/{user_id}/message",
                f"/users/{user_id}/message",
            ],
            payload,
        )


def build_mail_notification_text(
    message: dict,
    *,
    include_body: bool = False,
    max_body_chars: int = 240,
) -> str:
    """Build a compact mail notification body for Cliq messages."""
    subject = (message.get("subject") or "(no subject)").strip()
    sender = (message.get("from") or "unknown").strip()
    message_id = str(message.get("messageId") or "")

    lines = [
        "📧 New Mail",
        f"From: {sender}",
        f"Subject: {subject}",
    ]

    if message_id:
        lines.append(f"Message ID: {message_id}")

    if include_body:
        body = (message.get("textBody") or "").replace("\n", " ").strip()
        if body:
            snippet = body[:max_body_chars]
            if len(body) > max_body_chars:
                snippet += "..."
            lines.append(f"Snippet: {snippet}")

    return "\n".join(lines)
