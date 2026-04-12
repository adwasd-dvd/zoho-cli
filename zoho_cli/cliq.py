"""Cliq scaffolding helpers and lightweight client shell."""

from __future__ import annotations

import json
import mimetypes
import re
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from zoho_cli import utils


DEFAULT_CLIQ_SCOPES = [
    "ZohoCliq.Channels.READ",
    "ZohoCliq.Users.READ",
    "ZohoCliq.Messages.READ",
    "ZohoCliq.Chats.ALL",
    "ZohoCliq.Webhooks.CREATE",
]

CLIQ_EXPORT_CHATS_SCOPE = "ZohoCliq.OrganizationChats.READ"
CLIQ_EXPORT_MESSAGES_SCOPE = "ZohoCliq.OrganizationMessages.READ"
DEFAULT_CLIQ_EXPORT_SCOPES = [
    CLIQ_EXPORT_CHATS_SCOPE,
    CLIQ_EXPORT_MESSAGES_SCOPE,
]


def missing_cliq_scopes(granted_scopes: list[str] | None) -> list[str]:
    granted = set(granted_scopes or [])
    return [s for s in DEFAULT_CLIQ_SCOPES if s not in granted]


def missing_cliq_export_scopes(granted_scopes: list[str] | None) -> list[str]:
    granted = set(granted_scopes or [])
    return [s for s in DEFAULT_CLIQ_EXPORT_SCOPES if s not in granted]


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
        parsed_base = urlparse(self.base_url)
        self._service_base_url = f"{parsed_base.scheme}://{parsed_base.netloc}"
        self._headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
        self._last_dm_history_meta: dict[str, Any] = {
            "result": "not_run",
            "candidatePaths": [],
            "attemptedPaths": [],
            "selectedPath": None,
        }

    def _collect_paginated_get(
        self,
        path: str,
        *,
        limit: int = 100,
        token_param: str = "next_page_token",
    ) -> list[dict[str, Any]]:
        """Collect list payloads across paginated GET endpoints."""
        items: list[dict[str, Any]] = []
        next_token: str | None = None
        seen_tokens: set[str] = set()

        while True:
            params: dict[str, Any] = {"limit": limit}
            if next_token:
                params[token_param] = next_token

            payload = self._get(path, params=params)
            batch = payload.get("data", [])
            if isinstance(batch, list):
                items.extend([entry for entry in batch if isinstance(entry, dict)])

            has_more = bool(payload.get("has_more") or payload.get("hasMore"))
            candidate_token = payload.get("next_page_token") or payload.get(
                "nextPageToken"
            )
            token_text = str(candidate_token).strip() if candidate_token else ""

            if not has_more:
                break
            if not token_text:
                break
            if token_text in seen_tokens:
                break

            seen_tokens.add(token_text)
            next_token = token_text

        return items

    def _collect_paginated_get_candidates(
        self,
        paths: list[str],
        *,
        limit: int = 100,
        token_param: str = "next_page_token",
        meta: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Collect paginated GET data from the first supported endpoint candidate.

        Returns an empty list when every candidate path is endpoint-miss style
        (`request_url_invalid`, 404/405, or retryable not-supported codes).
        """
        unique_paths: list[str] = []
        seen_paths: set[str] = set()
        for path in paths:
            text = path.strip()
            if not text or text in seen_paths:
                continue
            seen_paths.add(text)
            unique_paths.append(text)

        attempted_paths: list[str] = []

        last_error: tuple[int, str, str] | None = None
        saw_scope_invalid = False
        saw_candidate_miss = False
        retryable_error_codes = {
            "request_method_invalid",
            "operation_not_allowed",
            "not_supported",
            "unsupported",
            "operation_failed",
        }

        for path in unique_paths:
            attempted_paths.append(path)
            items: list[dict[str, Any]] = []
            next_token: str | None = None
            seen_tokens: set[str] = set()
            saw_success = False

            while True:
                params: dict[str, Any] = {"limit": limit}
                if next_token:
                    params[token_param] = next_token

                resp = httpx.get(
                    f"{self.base_url}{path}",
                    headers=self._headers,
                    params=params,
                    timeout=httpx.Timeout(30.0),
                )

                if not resp.is_success:
                    body = resp.text or ""
                    lowered = body.lower()
                    last_error = (resp.status_code, path, body)

                    if saw_success:
                        utils.error_exit(
                            "api_error",
                            f"HTTP {resp.status_code} GET {path}: {body}",
                        )

                    if "oauthtoken_scope_invalid" in lowered:
                        saw_scope_invalid = True
                        break

                    error_code = ""
                    try:
                        parsed = resp.json()
                        if isinstance(parsed, dict):
                            error_code = str(
                                parsed.get("code") or parsed.get("error") or ""
                            ).lower()
                    except ValueError:
                        pass

                    if (
                        resp.status_code in (404, 405)
                        or "request_url_invalid" in lowered
                        or error_code in retryable_error_codes
                    ):
                        saw_candidate_miss = True
                        break

                    utils.error_exit(
                        "api_error",
                        f"HTTP {resp.status_code} GET {path}: {body}",
                    )

                saw_success = True
                payload = resp.json()
                batch = payload.get("data", [])
                if isinstance(batch, list):
                    items.extend([entry for entry in batch if isinstance(entry, dict)])

                has_more = bool(payload.get("has_more") or payload.get("hasMore"))
                candidate_token = payload.get("next_page_token") or payload.get(
                    "nextPageToken"
                )
                token_text = str(candidate_token).strip() if candidate_token else ""

                if not has_more:
                    break
                if not token_text:
                    break
                if token_text in seen_tokens:
                    break

                seen_tokens.add(token_text)
                next_token = token_text

            if saw_success:
                if meta is not None:
                    meta.clear()
                    meta.update(
                        {
                            "result": "ok",
                            "candidatePaths": list(unique_paths),
                            "attemptedPaths": list(attempted_paths),
                            "selectedPath": path,
                        }
                    )
                return items

        if saw_scope_invalid:
            if meta is not None:
                meta.clear()
                meta.update(
                    {
                        "result": "scope_invalid",
                        "candidatePaths": list(unique_paths),
                        "attemptedPaths": list(attempted_paths),
                        "selectedPath": None,
                    }
                )
            utils.error_exit(
                "oauth_scope_invalid",
                "Cliq token is missing message-read scope for DM history. Re-run `zoho login --with-cliq --scope ZohoCliq.Messages.READ` and retry.",
            )

        if saw_candidate_miss:
            if meta is not None:
                meta.clear()
                meta.update(
                    {
                        "result": "not_supported",
                        "candidatePaths": list(unique_paths),
                        "attemptedPaths": list(attempted_paths),
                        "selectedPath": None,
                    }
                )
            return []

        if last_error is not None:
            if meta is not None:
                meta.clear()
                meta.update(
                    {
                        "result": "api_error",
                        "candidatePaths": list(unique_paths),
                        "attemptedPaths": list(attempted_paths),
                        "selectedPath": None,
                    }
                )
            status, path, body = last_error
            utils.error_exit("api_error", f"HTTP {status} GET {path}: {body}")

        if meta is not None:
            meta.clear()
            meta.update(
                {
                    "result": "api_error",
                    "candidatePaths": list(unique_paths),
                    "attemptedPaths": list(attempted_paths),
                    "selectedPath": None,
                }
            )
        utils.error_exit("api_error", "No candidate endpoint available for DM history")
        return []

    def get_all_users(self, *, limit: int = 100) -> list[dict[str, Any]]:
        """Fetch the full user list with pagination."""
        return self._collect_paginated_get("/users", limit=limit)

    def get_dm_history(self, user_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        """Fetch full DM history with one user (best-effort pagination)."""
        target = user_id.strip()
        if not target:
            utils.error_exit("invalid_user_id", "user_id cannot be empty")
        history_meta: dict[str, Any] = {}
        history = self._collect_paginated_get_candidates(
            [
                f"/conversations/{target}/messages",
                f"/buddies/{target}/messages",
                f"/users/{target}/messages",
                f"/chats/{target}/messages",
            ],
            limit=limit,
            meta=history_meta,
        )
        self._last_dm_history_meta = history_meta
        return history

    def get_last_dm_history_meta(self) -> dict[str, Any]:
        """Return metadata for the most recent `get_dm_history` call."""
        payload = dict(self._last_dm_history_meta)
        for key in ("candidatePaths", "attemptedPaths"):
            values = payload.get(key)
            if isinstance(values, list):
                payload[key] = list(values)
        return payload

    def get_chat_history(
        self,
        *,
        chat_id: str | None = None,
        channel_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch full history for a chat/channel (best-effort pagination)."""
        resolved_chat = self._resolve_chat_destination(
            chat_id=chat_id,
            channel_id=channel_id,
        )
        return self._collect_paginated_get(
            f"/chats/{resolved_chat}/messages",
            limit=limit,
        )

    @staticmethod
    def _decode_success_response(resp: httpx.Response) -> dict[str, Any]:
        """Decode a success response, tolerating 204/empty/non-JSON bodies."""
        body = (resp.text or "").strip()
        if not body:
            return {"status": "ok", "httpStatus": resp.status_code}
        try:
            return resp.json()
        except ValueError:
            return {"status": "ok", "httpStatus": resp.status_code, "raw": resp.text}

    def _get(self, path: str, params: dict | None = None) -> dict:
        resp = httpx.get(
            f"{self.base_url}{path}",
            headers=self._headers,
            params=params or {},
            timeout=httpx.Timeout(30.0),
        )
        if not resp.is_success:
            utils.error_exit(
                "api_error", f"HTTP {resp.status_code} GET {path}: {resp.text}"
            )
        return resp.json()

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict:
        resp = httpx.post(
            f"{self.base_url}{path}",
            headers=self._headers,
            json=payload,
            timeout=httpx.Timeout(30.0),
        )
        if not resp.is_success:
            utils.error_exit(
                "api_error", f"HTTP {resp.status_code} POST {path}: {resp.text}"
            )
        return self._decode_success_response(resp)

    def _post_json_with_fallback(
        self, paths: list[str], payload: dict[str, Any]
    ) -> dict:
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
                return self._decode_success_response(resp)

            body = resp.text or ""
            last_error = (resp.status_code, path, body)
            lowered = body.lower()
            scope_invalid = "oauthtoken_scope_invalid" in lowered
            if scope_invalid:
                saw_scope_invalid = True

            if (
                resp.status_code in (404, 405)
                or "request_url_invalid" in lowered
                or scope_invalid
            ):
                continue

            utils.error_exit(
                "api_error", f"HTTP {resp.status_code} POST {path}: {resp.text}"
            )

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

    def _request_with_candidates(
        self,
        candidates: list[tuple[str, str, dict[str, Any] | None]],
        *,
        scope_hint: str,
        operation_label: str,
    ) -> dict:
        """Try multiple method/path/payload candidates for mutable message operations."""
        last_error: tuple[int, str, str, str] | None = None
        preferred_error: tuple[int, str, str, str] | None = None
        saw_scope_invalid = False
        retryable_error_codes = {
            "param_missing",
            "invalid_data",
            "operation_failed",
            "extra_key_found",
            "request_method_invalid",
        }

        for method, path, payload in candidates:
            resp = httpx.request(
                method,
                f"{self.base_url}{path}",
                headers=self._headers,
                json=payload,
                timeout=httpx.Timeout(30.0),
            )
            if resp.is_success:
                return self._decode_success_response(resp)

            body = resp.text or ""
            lowered = body.lower()
            scope_invalid = "oauthtoken_scope_invalid" in lowered
            error_code = ""
            try:
                parsed = resp.json()
                if isinstance(parsed, dict):
                    error_code = str(
                        parsed.get("code") or parsed.get("error") or ""
                    ).lower()
            except ValueError:
                pass
            if scope_invalid:
                saw_scope_invalid = True

            last_error = (resp.status_code, method, path, body)
            if (
                resp.status_code in (404, 405)
                or "request_url_invalid" in lowered
                or scope_invalid
                or error_code in retryable_error_codes
            ):
                if error_code in {
                    "operation_failed",
                    "operation_not_allowed",
                    "param_missing",
                    "invalid_data",
                    "extra_key_found",
                }:
                    preferred_error = preferred_error or (
                        resp.status_code,
                        method,
                        path,
                        body,
                    )
                continue

            utils.error_exit(
                "api_error",
                f"HTTP {resp.status_code} {method} {path}: {resp.text}",
            )

        if saw_scope_invalid:
            utils.error_exit(
                "oauth_scope_invalid",
                f"Cliq token is missing required scope for {operation_label}. Re-run `zoho login --with-cliq --scope {scope_hint}` and retry.",
            )

        chosen_error = preferred_error or last_error
        if chosen_error is not None:
            status, method, path, body = chosen_error
            utils.error_exit(
                "api_error",
                f"HTTP {status} {method} {path}: {body}",
            )

        utils.error_exit(
            "api_error", f"No candidate endpoint available for {operation_label}"
        )
        return {}

    def _get_channel_descriptor(self, channel_id: str) -> dict[str, Any] | None:
        """Fetch channel metadata used for endpoint resolution."""
        try:
            resp = httpx.get(
                f"{self.base_url}/channels/{channel_id}",
                headers=self._headers,
                timeout=httpx.Timeout(30.0),
            )
        except httpx.HTTPError:
            return None

        if not resp.is_success:
            return None

        try:
            payload = resp.json()
        except ValueError:
            return None

        data = payload.get("data", payload)
        if not isinstance(data, dict):
            return None

        return data

    def resolve_chat_id(self, channel_id: str) -> str | None:
        """Resolve a Cliq channel id into its backing chat_id when available."""
        data = self._get_channel_descriptor(channel_id)
        if not isinstance(data, dict):
            return None

        chat_id = data.get("chat_id") or data.get("chatId")
        if isinstance(chat_id, str) and chat_id.strip():
            return chat_id.strip()
        return None

    def _request_with_candidates_and_not_supported(
        self,
        candidates: list[tuple[str, str, dict[str, Any] | None]],
        *,
        scope_hint: str,
        operation_label: str,
        not_supported_message: str,
    ) -> dict:
        """Try mutable candidates and emit `not_supported` for endpoint-level misses."""
        last_error: tuple[int, str, str, str] | None = None
        preferred_error: tuple[int, str, str, str] | None = None
        saw_scope_invalid = False
        saw_not_supported = False

        retryable_error_codes = {
            "param_missing",
            "invalid_data",
            "operation_failed",
            "extra_key_found",
            "request_method_invalid",
            "extra_param_found",
        }

        for method, path, payload in candidates:
            resp = httpx.request(
                method,
                f"{self.base_url}{path}",
                headers=self._headers,
                json=payload,
                timeout=httpx.Timeout(30.0),
            )
            if resp.is_success:
                return self._decode_success_response(resp)

            body = resp.text or ""
            lowered = body.lower()
            scope_invalid = "oauthtoken_scope_invalid" in lowered
            error_code = ""
            try:
                parsed = resp.json()
                if isinstance(parsed, dict):
                    error_code = str(
                        parsed.get("code") or parsed.get("error") or ""
                    ).lower()
            except ValueError:
                pass

            if scope_invalid:
                saw_scope_invalid = True

            last_error = (resp.status_code, method, path, body)

            if (
                resp.status_code in (404, 405)
                or "request_url_invalid" in lowered
                or scope_invalid
                or error_code
                in {"operation_not_allowed", "not_supported", "unsupported"}
                or error_code in {"request_method_invalid", "extra_param_found"}
            ):
                saw_not_supported = True
                continue

            if error_code in retryable_error_codes:
                preferred_error = preferred_error or (
                    resp.status_code,
                    method,
                    path,
                    body,
                )
                continue

            utils.error_exit(
                "api_error",
                f"HTTP {resp.status_code} {method} {path}: {resp.text}",
            )

        if saw_scope_invalid:
            utils.error_exit(
                "oauth_scope_invalid",
                f"Cliq token is missing required scope for {operation_label}. Re-run `zoho login --with-cliq --scope {scope_hint}` and retry.",
            )

        if preferred_error is not None:
            status, method, path, body = preferred_error
            utils.error_exit(
                "api_error",
                f"HTTP {status} {method} {path}: {body}",
            )

        if saw_not_supported:
            utils.error_exit("not_supported", not_supported_message)

        if last_error is not None:
            status, method, path, body = last_error
            utils.error_exit(
                "api_error",
                f"HTTP {status} {method} {path}: {body}",
            )

        utils.error_exit(
            "api_error", f"No candidate endpoint available for {operation_label}"
        )
        return {}

    def _get_with_candidates_and_not_supported(
        self,
        candidates: list[tuple[str, dict[str, Any] | None]],
        *,
        scope_hint: str,
        operation_label: str,
        not_supported_message: str,
    ) -> dict:
        """Try read candidates and emit `not_supported` for endpoint-level misses."""
        last_error: tuple[int, str, str] | None = None
        saw_scope_invalid = False
        saw_not_supported = False

        for path, params in candidates:
            resp = httpx.get(
                f"{self.base_url}{path}",
                headers=self._headers,
                params=params or {},
                timeout=httpx.Timeout(30.0),
            )
            if resp.is_success:
                payload = resp.json()
                if isinstance(payload, dict):
                    return payload
                return {"data": payload}

            body = resp.text or ""
            lowered = body.lower()
            error_code = ""
            try:
                parsed = resp.json()
                if isinstance(parsed, dict):
                    error_code = str(
                        parsed.get("code") or parsed.get("error") or ""
                    ).lower()
            except ValueError:
                pass

            if "oauthtoken_scope_invalid" in lowered or error_code in {
                "oauthtoken_scope_invalid",
                "oauth_scope_invalid",
                "scope_mismatch",
                "oauth_scope_mismatch",
            }:
                saw_scope_invalid = True
                last_error = (resp.status_code, path, body)
                continue

            if (
                resp.status_code in (404, 405)
                or "request_url_invalid" in lowered
                or error_code
                in {
                    "operation_not_allowed",
                    "not_supported",
                    "unsupported",
                    "request_method_invalid",
                    "extra_param_found",
                }
            ):
                saw_not_supported = True
                last_error = (resp.status_code, path, body)
                continue

            utils.error_exit("api_error", f"HTTP {resp.status_code} GET {path}: {body}")

        if saw_scope_invalid:
            utils.error_exit(
                "oauth_scope_invalid",
                f"Cliq token is missing required scope for {operation_label}. Re-run `zoho login --with-cliq --scope {scope_hint}` and retry.",
            )

        if saw_not_supported:
            utils.error_exit("not_supported", not_supported_message)

        if last_error is not None:
            status, path, body = last_error
            utils.error_exit("api_error", f"HTTP {status} GET {path}: {body}")

        utils.error_exit(
            "api_error", f"No candidate endpoint available for {operation_label}"
        )
        return {}

    def _resolve_channel_message_paths(self, channel_id: str) -> list[str]:
        """Resolve channel-id to sendable chat/unique-name message endpoints."""
        data = self._get_channel_descriptor(channel_id)
        if not isinstance(data, dict):
            return []

        paths: list[str] = []
        chat_id = data.get("chat_id") or data.get("chatId")
        if isinstance(chat_id, str) and chat_id:
            paths.append(f"/chats/{chat_id}/message")

        unique_name = (
            data.get("unique_name")
            or data.get("channel_unique_name")
            or data.get("uniqueName")
        )
        if isinstance(unique_name, str) and unique_name.strip():
            paths.append(f"/channelsbyname/{unique_name.strip()}/message")

        return paths

    @staticmethod
    def _looks_like_channel_id(channel_id: str) -> bool:
        text = (channel_id or "").strip()
        return bool(re.fullmatch(r"[A-Z]\d+", text))

    @staticmethod
    def _extract_message_id(message: dict[str, Any]) -> str:
        for key in ("id", "message_id", "messageId"):
            value = message.get(key)
            if value is not None:
                text = str(value).strip()
                if text:
                    return text
        return ""

    @staticmethod
    def _extract_sender_id(message: dict[str, Any]) -> str:
        sender = message.get("sender")
        if isinstance(sender, dict):
            for key in ("id", "zuid", "user_id", "userId"):
                value = sender.get(key)
                if value is not None:
                    text = str(value).strip()
                    if text:
                        return text

        for key in ("sender_id", "senderId", "user_id", "userId", "zuid"):
            value = message.get(key)
            if value is not None:
                text = str(value).strip()
                if text:
                    return text
        return ""

    @staticmethod
    def _extract_message_text(message: dict[str, Any]) -> str:
        for key in ("text", "message", "content", "message_text", "messageText"):
            value = message.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return ""

    @staticmethod
    def _extract_message_timestamp(message: dict[str, Any]) -> str:
        for key in (
            "time",
            "timestamp",
            "created_time",
            "createdTime",
            "time_in_millis",
            "sent_time",
        ):
            value = message.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return ""

    @classmethod
    def build_watch_context_seed(
        cls,
        messages: list[dict[str, Any]],
        *,
        since_message_id: str | None = None,
        max_messages: int = 20,
    ) -> dict[str, Any]:
        """Build a stable, incremental message payload for watch loops."""
        max_items = max(1, max_messages)
        since = (since_message_id or "").strip()

        cleaned_messages = [item for item in messages if isinstance(item, dict)]
        latest_message_id = ""
        for item in cleaned_messages:
            latest_message_id = cls._extract_message_id(item)
            if latest_message_id:
                break

        selected: list[dict[str, Any]] = []
        cursor_found = False
        truncated = False

        for item in cleaned_messages:
            mid = cls._extract_message_id(item)
            if since and mid == since:
                cursor_found = True
                break
            if len(selected) >= max_items:
                truncated = True
                break
            selected.append(item)

        normalized_messages: list[dict[str, Any]] = []
        for item in reversed(selected):
            mid = cls._extract_message_id(item)
            if not mid:
                continue
            normalized_messages.append(
                {
                    "messageId": mid,
                    "senderId": cls._extract_sender_id(item),
                    "text": cls._extract_message_text(item),
                    "timestamp": cls._extract_message_timestamp(item),
                    "raw": item,
                }
            )

        return {
            "sinceMessageId": since,
            "cursorFound": cursor_found,
            "latestMessageId": latest_message_id,
            "nextSinceMessageId": latest_message_id or since,
            "totalFetched": len(cleaned_messages),
            "newCount": len(normalized_messages),
            "truncated": truncated,
            "messages": normalized_messages,
        }

    @classmethod
    def build_watch_reply_action(
        cls,
        watch_payload: dict[str, Any],
        *,
        text: str,
        chat_id: str | None = None,
        channel_id: str | None = None,
    ) -> dict[str, Any]:
        """Build a deterministic reply-latest action from watch-context output."""
        payload_chat = str(watch_payload.get("chatId") or "").strip()
        payload_channel = str(watch_payload.get("channelId") or "").strip()

        resolved_chat = (chat_id or "").strip() or payload_chat
        resolved_channel = (channel_id or "").strip() or payload_channel

        data = watch_payload.get("messages")
        messages = (
            [item for item in data if isinstance(item, dict)]
            if isinstance(data, list)
            else []
        )

        target: dict[str, Any] | None = None
        for item in reversed(messages):
            if cls._extract_message_id(item):
                target = item
                break

        target_id = cls._extract_message_id(target or {})
        return {
            "action": "reply-latest",
            "chatId": resolved_chat,
            "channelId": resolved_channel,
            "newCount": watch_payload.get("newCount", len(messages)),
            "targetMessageId": target_id,
            "targetSenderId": cls._extract_sender_id(target or {}),
            "targetText": cls._extract_message_text(target or {}),
            "replyText": text,
            "hasTarget": bool(target_id),
        }

    def execute_watch_reply_action(
        self,
        watch_payload: dict[str, Any],
        *,
        text: str,
        chat_id: str | None = None,
        channel_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute one deterministic watch action: reply to the latest new message."""
        reply_text = text.strip()
        if not reply_text:
            utils.error_exit("invalid_text", "reply text cannot be empty")

        action = self.build_watch_reply_action(
            watch_payload,
            text=reply_text,
            chat_id=chat_id,
            channel_id=channel_id,
        )

        resolved_chat = str(action.get("chatId") or "").strip()
        resolved_channel = str(action.get("channelId") or "").strip()
        if not resolved_chat and not resolved_channel:
            utils.error_exit(
                "invalid_destination",
                "Watch payload is missing destination. Provide --chat-id/--channel-id or use payload from `zoho cliq watch-context`.",
            )

        target_id = str(action.get("targetMessageId") or "").strip()
        if not target_id:
            return {
                "status": "ok",
                **action,
                "applied": False,
                "reason": "no_new_messages",
                "result": {},
            }

        resp = self.reply_message(
            reply_text,
            message_id=target_id,
            chat_id=resolved_chat or None,
            channel_id=resolved_channel or None,
        )
        return {
            "status": "ok",
            **action,
            "applied": True,
            "result": resp.get("data", resp),
        }

    def list_messages(
        self,
        *,
        chat_id: str | None = None,
        channel_id: str | None = None,
        limit: int = 50,
    ) -> dict:
        """List messages for a chat (or a resolvable channel id)."""
        resolved_chat = self._resolve_chat_destination(
            chat_id=chat_id,
            channel_id=channel_id,
        )

        resp = httpx.get(
            f"{self.base_url}/chats/{resolved_chat}/messages",
            headers=self._headers,
            params={"limit": limit},
            timeout=httpx.Timeout(30.0),
        )
        if resp.is_success:
            return resp.json()

        body = resp.text or ""
        lowered = body.lower()
        if "oauthtoken_scope_invalid" in lowered:
            utils.error_exit(
                "oauth_scope_invalid",
                "Cliq token is missing message-read scope. Re-run `zoho login --with-cliq --scope ZohoCliq.Messages.READ` and retry.",
            )
        utils.error_exit(
            "api_error",
            f"HTTP {resp.status_code} GET /chats/{resolved_chat}/messages: {body}",
        )
        return {}

    def get_message(
        self,
        message_id: str,
        *,
        chat_id: str | None = None,
        channel_id: str | None = None,
    ) -> dict:
        """Fetch one message by id for a chat (or a resolvable channel id)."""
        resolved_chat = self._resolve_chat_destination(
            chat_id=chat_id,
            channel_id=channel_id,
        )

        mid = message_id.strip()
        if not mid:
            utils.error_exit("invalid_message_id", "message_id cannot be empty")

        resp = httpx.get(
            f"{self.base_url}/chats/{resolved_chat}/messages/{mid}",
            headers=self._headers,
            timeout=httpx.Timeout(30.0),
        )
        if resp.is_success:
            return resp.json()

        body = resp.text or ""
        lowered = body.lower()
        if "oauthtoken_scope_invalid" in lowered:
            utils.error_exit(
                "oauth_scope_invalid",
                "Cliq token is missing message-read scope. Re-run `zoho login --with-cliq --scope ZohoCliq.Messages.READ` and retry.",
            )
        utils.error_exit(
            "api_error",
            f"HTTP {resp.status_code} GET /chats/{resolved_chat}/messages/{mid}: {body}",
        )
        return {}

    def search_messages(
        self,
        query: str,
        *,
        chat_id: str | None = None,
        channel_id: str | None = None,
        limit: int = 50,
        from_time: str | None = None,
        to_time: str | None = None,
    ) -> dict:
        """Search messages for a chat/channel with endpoint and param fallbacks."""
        resolved_chat = (chat_id or "").strip()
        if not resolved_chat and channel_id:
            resolved_chat = self.resolve_chat_id(channel_id) or ""
        if not resolved_chat:
            utils.error_exit(
                "invalid_destination", "Provide --chat-id or resolvable --channel-id"
            )

        term = query.strip()
        if not term:
            utils.error_exit("invalid_query", "query cannot be empty")

        search_keys = ["search", "searchKey", "q", "keyword"]

        def _window(
            start_key: str,
            end_key: str,
            *,
            start: str | None,
            end: str | None,
        ) -> dict[str, Any]:
            payload: dict[str, Any] = {}
            if start:
                payload[start_key] = start
            if end:
                payload[end_key] = end
            return payload

        start = (from_time or "").strip() or None
        end = (to_time or "").strip() or None
        window_variants = [
            _window("from_time", "to_time", start=start, end=end),
            _window("start_time", "end_time", start=start, end=end),
            _window("from", "to", start=start, end=end),
            _window("since", "until", start=start, end=end),
        ]
        if not (start or end):
            window_variants = [{}]

        path_candidates: list[str] = []
        if resolved_chat:
            path_candidates.extend(
                [
                    f"/chats/{resolved_chat}/messages/search",
                    f"/chats/{resolved_chat}/search/messages",
                ]
            )
        if channel_id:
            path_candidates.extend(
                [
                    f"/channels/{channel_id}/messages/search",
                    f"/channels/{channel_id}/search/messages",
                ]
            )

        # Preserve order while deduplicating.
        seen_paths: set[str] = set()
        path_candidates = [
            p for p in path_candidates if not (p in seen_paths or seen_paths.add(p))
        ]

        saw_scope_invalid = False
        saw_not_supported = False
        last_error: tuple[int, str, str] | None = None
        retryable_error_codes = {
            "param_missing",
            "invalid_data",
            "operation_failed",
            "extra_key_found",
            "extra_param_found",
        }

        for path in path_candidates:
            for search_key in search_keys:
                for window in window_variants:
                    params = {search_key: term, "limit": limit, **window}
                    resp = httpx.get(
                        f"{self.base_url}{path}",
                        headers=self._headers,
                        params=params,
                        timeout=httpx.Timeout(30.0),
                    )
                    if resp.is_success:
                        return resp.json()

                    body = resp.text or ""
                    lowered = body.lower()
                    error_code = ""
                    try:
                        parsed = resp.json()
                        if isinstance(parsed, dict):
                            error_code = str(
                                parsed.get("code") or parsed.get("error") or ""
                            ).lower()
                    except ValueError:
                        pass

                    if "oauthtoken_scope_invalid" in lowered:
                        saw_scope_invalid = True
                        last_error = (resp.status_code, path, body)
                        continue

                    if (
                        resp.status_code in (404, 405)
                        or "request_url_invalid" in lowered
                        or error_code in retryable_error_codes
                        or error_code
                        in {"operation_not_allowed", "not_supported", "unsupported"}
                    ):
                        saw_not_supported = True
                        last_error = (resp.status_code, path, body)
                        continue

                    utils.error_exit(
                        "api_error",
                        f"HTTP {resp.status_code} GET {path}: {body}",
                    )

        if saw_scope_invalid:
            utils.error_exit(
                "oauth_scope_invalid",
                "Cliq token is missing message-read scope for search. Re-run `zoho login --with-cliq --scope ZohoCliq.Messages.READ` and retry.",
            )

        if saw_not_supported:
            utils.error_exit(
                "not_supported",
                "Cliq message search is not available for this token/network endpoint. Run `zoho cliq capabilities --channel-id <id>` to confirm available operations.",
            )

        if last_error is not None:
            status, path, body = last_error
            utils.error_exit("api_error", f"HTTP {status} GET {path}: {body}")

        utils.error_exit(
            "api_error", "No candidate endpoint available for message search"
        )
        return {}

    def get_message_files(
        self,
        message_id: str,
        *,
        chat_id: str | None = None,
        channel_id: str | None = None,
    ) -> dict:
        """Fetch file/attachment payloads for one message with endpoint fallbacks."""
        resolved_chat = (chat_id or "").strip()
        if not resolved_chat and channel_id:
            resolved_chat = self.resolve_chat_id(channel_id) or ""
        if not resolved_chat:
            utils.error_exit(
                "invalid_destination", "Provide --chat-id or resolvable --channel-id"
            )

        mid = message_id.strip()
        if not mid:
            utils.error_exit("invalid_message_id", "message_id cannot be empty")

        path_candidates: list[str] = [
            f"/chats/{resolved_chat}/messages/{mid}/files",
            f"/chats/{resolved_chat}/messages/{mid}/attachments",
        ]
        if channel_id:
            path_candidates.extend(
                [
                    f"/channels/{channel_id}/messages/{mid}/files",
                    f"/channels/{channel_id}/messages/{mid}/attachments",
                ]
            )

        # Preserve order while deduplicating.
        seen_paths: set[str] = set()
        path_candidates = [
            p for p in path_candidates if not (p in seen_paths or seen_paths.add(p))
        ]

        saw_scope_invalid = False
        saw_not_supported = False
        first_no_attachment_path: str | None = None
        last_error: tuple[int, str, str] | None = None

        for path in path_candidates:
            resp = httpx.get(
                f"{self.base_url}{path}",
                headers=self._headers,
                timeout=httpx.Timeout(30.0),
            )
            if resp.is_success:
                payload = resp.json()
                fetch_meta = {
                    "path": path,
                }
                if isinstance(payload, dict):
                    data_payload = payload.get("data")
                    if isinstance(data_payload, dict):
                        data_payload.setdefault("fetch", fetch_meta)
                    else:
                        payload.setdefault("fetch", fetch_meta)
                    return payload

                return {
                    "data": payload,
                    "fetch": fetch_meta,
                }

            body = resp.text or ""
            lowered = body.lower()
            error_code = ""
            try:
                parsed = resp.json()
                if isinstance(parsed, dict):
                    error_code = str(
                        parsed.get("code") or parsed.get("error") or ""
                    ).lower()
            except ValueError:
                pass

            if error_code in {
                "message_attachment_not_found",
                "no_attachments_found",
            }:
                if first_no_attachment_path is None:
                    first_no_attachment_path = path
                last_error = (resp.status_code, path, body)
                if path.endswith("/attachments"):
                    return {
                        "files": [],
                        "fetch": {"path": first_no_attachment_path},
                    }
                continue

            if "oauthtoken_scope_invalid" in lowered:
                saw_scope_invalid = True
                last_error = (resp.status_code, path, body)
                continue

            if (
                resp.status_code in (404, 405)
                or "request_url_invalid" in lowered
                or error_code
                in {"operation_not_allowed", "not_supported", "unsupported"}
            ):
                saw_not_supported = True
                last_error = (resp.status_code, path, body)
                continue

            utils.error_exit(
                "api_error",
                f"HTTP {resp.status_code} GET {path}: {body}",
            )

        if first_no_attachment_path is not None:
            return {
                "files": [],
                "fetch": {"path": first_no_attachment_path},
            }

        if saw_scope_invalid:
            utils.error_exit(
                "oauth_scope_invalid",
                "Cliq token is missing message-read scope for file retrieval. Re-run `zoho login --with-cliq --scope ZohoCliq.Messages.READ` and retry.",
            )

        if saw_not_supported:
            utils.error_exit(
                "not_supported",
                "Cliq file/attachment retrieval is not available for this token/network endpoint. Run `zoho cliq capabilities --channel-id <id>` to confirm available operations.",
            )

        if last_error is not None:
            status, path, body = last_error
            utils.error_exit("api_error", f"HTTP {status} GET {path}: {body}")

        utils.error_exit(
            "api_error", "No candidate endpoint available for message file retrieval"
        )
        return {}

    def _resolve_chat_destination(
        self,
        *,
        chat_id: str | None = None,
        channel_id: str | None = None,
    ) -> str:
        resolved_chat = (chat_id or "").strip()
        if not resolved_chat and channel_id:
            resolved_chat = self.resolve_chat_id(channel_id) or ""
        if not resolved_chat:
            utils.error_exit(
                "invalid_destination", "Provide --chat-id or resolvable --channel-id"
            )
        return resolved_chat

    def reply_message(
        self,
        text: str,
        *,
        message_id: str,
        chat_id: str | None = None,
        channel_id: str | None = None,
    ) -> dict:
        """Reply to a message in a chat/channel using endpoint/payload fallbacks."""
        resolved_chat = self._resolve_chat_destination(
            chat_id=chat_id, channel_id=channel_id
        )
        anchor = message_id.strip()
        if not anchor:
            utils.error_exit("invalid_message_id", "message_id cannot be empty")

        payloads = [
            {"text": text, "reply_to": anchor},
            {"text": text, "reply_to_msg_id": anchor},
            {"text": text, "replyTo": anchor},
        ]
        candidates: list[tuple[str, str, dict[str, Any] | None]] = []
        for payload in payloads:
            candidates.extend(
                [
                    (
                        "POST",
                        f"/chats/{resolved_chat}/messages/{anchor}/reply",
                        payload,
                    ),
                    ("POST", f"/chats/{resolved_chat}/message", payload),
                    ("POST", f"/chats/{resolved_chat}/messages", payload),
                ]
            )
        return self._request_with_candidates(
            candidates,
            scope_hint="ZohoCliq.Messages.CREATE",
            operation_label="reply",
        )

    def edit_message(
        self,
        message_id: str,
        text: str,
        *,
        chat_id: str | None = None,
        channel_id: str | None = None,
    ) -> dict:
        """Edit a message in a chat/channel using endpoint/method fallbacks."""
        resolved_chat = self._resolve_chat_destination(
            chat_id=chat_id, channel_id=channel_id
        )
        mid = message_id.strip()
        if not mid:
            utils.error_exit("invalid_message_id", "message_id cannot be empty")

        payload = {"text": text}
        candidates = [
            ("PUT", f"/chats/{resolved_chat}/messages/{mid}", payload),
            ("POST", f"/chats/{resolved_chat}/messages/{mid}", payload),
            ("PUT", f"/chats/{resolved_chat}/message/{mid}", payload),
            ("POST", f"/chats/{resolved_chat}/messages/{mid}/edit", payload),
        ]
        return self._request_with_candidates(
            candidates,
            scope_hint="ZohoCliq.Messages.UPDATE",
            operation_label="edit",
        )

    def delete_message(
        self,
        message_id: str,
        *,
        chat_id: str | None = None,
        channel_id: str | None = None,
    ) -> dict:
        """Delete a message in a chat/channel using endpoint/method fallbacks."""
        resolved_chat = self._resolve_chat_destination(
            chat_id=chat_id, channel_id=channel_id
        )
        mid = message_id.strip()
        if not mid:
            utils.error_exit("invalid_message_id", "message_id cannot be empty")

        candidates = [
            ("DELETE", f"/chats/{resolved_chat}/messages/{mid}", None),
            ("DELETE", f"/chats/{resolved_chat}/message/{mid}", None),
            ("POST", f"/chats/{resolved_chat}/messages/{mid}/delete", {}),
        ]
        return self._request_with_candidates(
            candidates,
            scope_hint="ZohoCliq.Messages.DELETE",
            operation_label="delete",
        )

    def react_message(
        self,
        message_id: str,
        emoji: str,
        *,
        remove: bool = False,
        chat_id: str | None = None,
        channel_id: str | None = None,
    ) -> dict:
        """Add or remove a reaction for a message."""
        resolved_chat = self._resolve_chat_destination(
            chat_id=chat_id, channel_id=channel_id
        )
        mid = message_id.strip()
        if not mid:
            utils.error_exit("invalid_message_id", "message_id cannot be empty")
        icon = emoji.strip()
        if not icon:
            utils.error_exit("invalid_emoji", "emoji cannot be empty")

        if remove:
            candidates = [
                (
                    "DELETE",
                    f"/chats/{resolved_chat}/messages/{mid}/reactions/{icon}",
                    None,
                ),
                (
                    "POST",
                    f"/chats/{resolved_chat}/messages/{mid}/reactions/remove",
                    {"emoji_code": icon},
                ),
                (
                    "POST",
                    f"/chats/{resolved_chat}/messageactions/delete",
                    {"message_id": mid, "emoji_code": icon},
                ),
            ]
        else:
            candidates = [
                (
                    "POST",
                    f"/chats/{resolved_chat}/messages/{mid}/reactions",
                    {"emoji_code": icon},
                ),
                (
                    "POST",
                    f"/chats/{resolved_chat}/messages/{mid}/reactions",
                    {"emoji": icon},
                ),
                (
                    "POST",
                    f"/chats/{resolved_chat}/messageactions",
                    {"message_id": mid, "emoji_code": icon},
                ),
                (
                    "POST",
                    f"/chats/{resolved_chat}/messageactions/create",
                    {"message_id": mid, "emoji_code": icon},
                ),
            ]

        return self._request_with_candidates(
            candidates,
            scope_hint="ZohoCliq.messageactions.CREATE",
            operation_label="reaction",
        )

    def create_thread(
        self,
        message_id: str,
        text: str,
        *,
        chat_id: str | None = None,
        channel_id: str | None = None,
    ) -> dict:
        """Create/send a thread message anchored to one parent message."""
        resolved_chat = self._resolve_chat_destination(
            chat_id=chat_id,
            channel_id=channel_id,
        )
        parent_message_id = message_id.strip()
        if not parent_message_id:
            utils.error_exit("invalid_message_id", "message_id cannot be empty")

        body = text.strip()
        if not body:
            utils.error_exit("invalid_text", "text cannot be empty")

        payloads = [
            {"text": body},
            {"message": body},
            {"content": body},
            {"text": body, "parent_message_id": parent_message_id},
            {"text": body, "parentMessageId": parent_message_id},
            {"text": body, "message_id": parent_message_id},
        ]

        candidates: list[tuple[str, str, dict[str, Any] | None]] = []
        for payload in payloads:
            candidates.extend(
                [
                    (
                        "POST",
                        f"/chats/{resolved_chat}/messages/{parent_message_id}/threads",
                        payload,
                    ),
                    (
                        "POST",
                        f"/chats/{resolved_chat}/messages/{parent_message_id}/thread",
                        payload,
                    ),
                    (
                        "POST",
                        f"/chats/{resolved_chat}/threads",
                        payload,
                    ),
                ]
            )

            if channel_id:
                candidates.extend(
                    [
                        (
                            "POST",
                            f"/channels/{channel_id}/messages/{parent_message_id}/threads",
                            payload,
                        ),
                        (
                            "POST",
                            f"/channels/{channel_id}/messages/{parent_message_id}/thread",
                            payload,
                        ),
                        (
                            "POST",
                            f"/channels/{channel_id}/threads",
                            payload,
                        ),
                    ]
                )

        return self._request_with_candidates_and_not_supported(
            candidates,
            scope_hint="ZohoCliq.Messages.CREATE",
            operation_label="thread-create",
            not_supported_message="Cliq thread-create endpoints are not available for this token/network endpoint. Run `zoho cliq capabilities --channel-id <id>` and confirm thread operations for the target conversation.",
        )

    def reply_thread(
        self,
        thread_id: str,
        text: str,
        *,
        chat_id: str | None = None,
        channel_id: str | None = None,
    ) -> dict:
        """Reply to a thread."""
        resolved_chat = self._resolve_chat_destination(
            chat_id=chat_id,
            channel_id=channel_id,
        )
        target_thread = thread_id.strip()
        if not target_thread:
            utils.error_exit("invalid_thread_id", "thread_id cannot be empty")

        body = text.strip()
        if not body:
            utils.error_exit("invalid_text", "text cannot be empty")

        payloads = [
            {"text": body},
            {"message": body},
            {"content": body},
            {"text": body, "thread_id": target_thread},
            {"text": body, "threadId": target_thread},
        ]

        candidates: list[tuple[str, str, dict[str, Any] | None]] = []
        for payload in payloads:
            candidates.extend(
                [
                    (
                        "POST",
                        f"/chats/{resolved_chat}/threads/{target_thread}/messages",
                        payload,
                    ),
                    (
                        "POST",
                        f"/chats/{resolved_chat}/threads/{target_thread}/reply",
                        payload,
                    ),
                    (
                        "POST",
                        f"/chats/{resolved_chat}/messages/{target_thread}/reply",
                        payload,
                    ),
                ]
            )

            if channel_id:
                candidates.extend(
                    [
                        (
                            "POST",
                            f"/channels/{channel_id}/threads/{target_thread}/messages",
                            payload,
                        ),
                        (
                            "POST",
                            f"/channels/{channel_id}/threads/{target_thread}/reply",
                            payload,
                        ),
                        (
                            "POST",
                            f"/channels/{channel_id}/messages/{target_thread}/reply",
                            payload,
                        ),
                    ]
                )

        return self._request_with_candidates_and_not_supported(
            candidates,
            scope_hint="ZohoCliq.Messages.CREATE",
            operation_label="thread-reply",
            not_supported_message="Cliq thread-reply endpoints are not available for this token/network endpoint. Run `zoho cliq capabilities --channel-id <id>` and confirm thread operations for the target conversation.",
        )

    def list_threads(
        self,
        *,
        chat_id: str | None = None,
        channel_id: str | None = None,
        message_id: str | None = None,
        limit: int = 50,
    ) -> dict:
        """List threads for a chat/channel, optionally scoped to one parent message."""
        resolved_chat = self._resolve_chat_destination(
            chat_id=chat_id,
            channel_id=channel_id,
        )
        limit_value = max(1, limit)
        anchor = (message_id or "").strip()

        candidates: list[tuple[str, dict[str, Any] | None]] = []
        if anchor:
            candidates.extend(
                [
                    (
                        f"/chats/{resolved_chat}/messages/{anchor}/threads",
                        {"limit": limit_value},
                    ),
                    (
                        f"/chats/{resolved_chat}/messages/{anchor}/thread",
                        {"limit": limit_value},
                    ),
                    (
                        f"/chats/{resolved_chat}/threads",
                        {"message_id": anchor, "limit": limit_value},
                    ),
                ]
            )

            if channel_id:
                candidates.extend(
                    [
                        (
                            f"/channels/{channel_id}/messages/{anchor}/threads",
                            {"limit": limit_value},
                        ),
                        (
                            f"/channels/{channel_id}/messages/{anchor}/thread",
                            {"limit": limit_value},
                        ),
                    ]
                )
        else:
            candidates.extend(
                [
                    (f"/chats/{resolved_chat}/threads", {"limit": limit_value}),
                    (f"/chats/{resolved_chat}/thread", {"limit": limit_value}),
                ]
            )
            if channel_id:
                candidates.extend(
                    [
                        (f"/channels/{channel_id}/threads", {"limit": limit_value}),
                        (f"/channels/{channel_id}/thread", {"limit": limit_value}),
                    ]
                )

        return self._get_with_candidates_and_not_supported(
            candidates,
            scope_hint="ZohoCliq.Messages.READ",
            operation_label="threads",
            not_supported_message="Cliq thread-list endpoints are not available for this token/network endpoint. Run `zoho cliq capabilities --channel-id <id>` and confirm thread operations for the target conversation.",
        )

    def list_scheduled_messages(
        self,
        *,
        chat_id: str | None = None,
        channel_id: str | None = None,
        limit: int = 50,
    ) -> dict:
        """List scheduled messages for a chat/channel."""
        resolved_chat = self._resolve_chat_destination(
            chat_id=chat_id,
            channel_id=channel_id,
        )
        limit_value = max(1, limit)

        candidates: list[tuple[str, dict[str, Any] | None]] = [
            (f"/chats/{resolved_chat}/scheduled", {"limit": limit_value}),
            (f"/chats/{resolved_chat}/messages/scheduled", {"limit": limit_value}),
            (f"/chats/{resolved_chat}/scheduled/messages", {"limit": limit_value}),
            (f"/chats/{resolved_chat}/schedule", {"limit": limit_value}),
        ]

        if channel_id:
            candidates.extend(
                [
                    (f"/channels/{channel_id}/scheduled", {"limit": limit_value}),
                    (
                        f"/channels/{channel_id}/messages/scheduled",
                        {"limit": limit_value},
                    ),
                    (
                        f"/channels/{channel_id}/scheduled/messages",
                        {"limit": limit_value},
                    ),
                ]
            )

        return self._get_with_candidates_and_not_supported(
            candidates,
            scope_hint="ZohoCliq.Messages.READ",
            operation_label="scheduled",
            not_supported_message="Cliq scheduled-message list endpoints are not available for this token/network endpoint. Run `zoho cliq capabilities --channel-id <id>` and confirm scheduled-message operations for the target conversation.",
        )

    def schedule_message(
        self,
        text: str,
        schedule_at: str,
        *,
        chat_id: str | None = None,
        channel_id: str | None = None,
    ) -> dict:
        """Schedule one message for a chat/channel."""
        resolved_chat = self._resolve_chat_destination(
            chat_id=chat_id,
            channel_id=channel_id,
        )

        body = text.strip()
        if not body:
            utils.error_exit("invalid_text", "text cannot be empty")

        scheduled_for = schedule_at.strip()
        if not scheduled_for:
            utils.error_exit("invalid_schedule_at", "schedule_at cannot be empty")

        payloads = [
            {"text": body, "time": scheduled_for},
            {"text": body, "scheduled_time": scheduled_for},
            {"text": body, "scheduled_at": scheduled_for},
            {"text": body, "schedule_time": scheduled_for},
            {"text": body, "send_at": scheduled_for},
            {"message": body, "scheduled_time": scheduled_for},
            {"content": body, "scheduled_time": scheduled_for},
        ]

        candidates: list[tuple[str, str, dict[str, Any] | None]] = []
        for payload in payloads:
            candidates.extend(
                [
                    ("POST", f"/chats/{resolved_chat}/scheduled", payload),
                    ("POST", f"/chats/{resolved_chat}/messages/scheduled", payload),
                    ("POST", f"/chats/{resolved_chat}/scheduled/messages", payload),
                    ("POST", f"/chats/{resolved_chat}/schedule", payload),
                ]
            )

            if channel_id:
                candidates.extend(
                    [
                        ("POST", f"/channels/{channel_id}/scheduled", payload),
                        (
                            "POST",
                            f"/channels/{channel_id}/messages/scheduled",
                            payload,
                        ),
                        (
                            "POST",
                            f"/channels/{channel_id}/scheduled/messages",
                            payload,
                        ),
                    ]
                )

        return self._request_with_candidates_and_not_supported(
            candidates,
            scope_hint="ZohoCliq.Messages.CREATE",
            operation_label="schedule",
            not_supported_message="Cliq scheduled-message create endpoints are not available for this token/network endpoint. Run `zoho cliq capabilities --channel-id <id>` and confirm scheduled-message operations for the target conversation.",
        )

    def get_scheduled_message(
        self,
        scheduled_id: str,
        *,
        chat_id: str | None = None,
        channel_id: str | None = None,
    ) -> dict:
        """Get one scheduled message by id for a chat/channel."""
        resolved_chat = self._resolve_chat_destination(
            chat_id=chat_id,
            channel_id=channel_id,
        )
        target_scheduled_id = scheduled_id.strip()
        if not target_scheduled_id:
            utils.error_exit("invalid_scheduled_id", "scheduled_id cannot be empty")

        candidates: list[tuple[str, dict[str, Any] | None]] = [
            (f"/chats/{resolved_chat}/scheduled/{target_scheduled_id}", None),
            (
                f"/chats/{resolved_chat}/messages/scheduled/{target_scheduled_id}",
                None,
            ),
            (
                f"/chats/{resolved_chat}/scheduled/messages/{target_scheduled_id}",
                None,
            ),
            (f"/chats/{resolved_chat}/schedule/{target_scheduled_id}", None),
        ]

        if channel_id:
            candidates.extend(
                [
                    (
                        f"/channels/{channel_id}/scheduled/{target_scheduled_id}",
                        None,
                    ),
                    (
                        f"/channels/{channel_id}/messages/scheduled/{target_scheduled_id}",
                        None,
                    ),
                ]
            )

        return self._get_with_candidates_and_not_supported(
            candidates,
            scope_hint="ZohoCliq.Messages.READ",
            operation_label="scheduled-get",
            not_supported_message="Cliq scheduled-message get endpoints are not available for this token/network endpoint. Run `zoho cliq capabilities --channel-id <id>` and confirm scheduled-message operations for the target conversation.",
        )

    def cancel_scheduled_message(
        self,
        scheduled_id: str,
        *,
        chat_id: str | None = None,
        channel_id: str | None = None,
    ) -> dict:
        """Cancel one scheduled message by id for a chat/channel."""
        resolved_chat = self._resolve_chat_destination(
            chat_id=chat_id,
            channel_id=channel_id,
        )
        target_scheduled_id = scheduled_id.strip()
        if not target_scheduled_id:
            utils.error_exit("invalid_scheduled_id", "scheduled_id cannot be empty")

        candidates: list[tuple[str, str, dict[str, Any] | None]] = [
            ("DELETE", f"/chats/{resolved_chat}/scheduled/{target_scheduled_id}", None),
            (
                "DELETE",
                f"/chats/{resolved_chat}/messages/scheduled/{target_scheduled_id}",
                None,
            ),
            (
                "DELETE",
                f"/chats/{resolved_chat}/scheduled/messages/{target_scheduled_id}",
                None,
            ),
            ("DELETE", f"/chats/{resolved_chat}/schedule/{target_scheduled_id}", None),
            (
                "POST",
                f"/chats/{resolved_chat}/scheduled/{target_scheduled_id}/cancel",
                {},
            ),
            (
                "POST",
                f"/chats/{resolved_chat}/messages/scheduled/{target_scheduled_id}/cancel",
                {},
            ),
        ]

        if channel_id:
            candidates.extend(
                [
                    (
                        "DELETE",
                        f"/channels/{channel_id}/scheduled/{target_scheduled_id}",
                        None,
                    ),
                    (
                        "DELETE",
                        f"/channels/{channel_id}/messages/scheduled/{target_scheduled_id}",
                        None,
                    ),
                    (
                        "POST",
                        f"/channels/{channel_id}/scheduled/{target_scheduled_id}/cancel",
                        {},
                    ),
                ]
            )

        return self._request_with_candidates_and_not_supported(
            candidates,
            scope_hint="ZohoCliq.Messages.DELETE",
            operation_label="scheduled-cancel",
            not_supported_message="Cliq scheduled-message cancel endpoints are not available for this token/network endpoint. Run `zoho cliq capabilities --channel-id <id>` and confirm scheduled-message operations for the target conversation.",
        )

    def post_to_bot(
        self,
        bot_id: str,
        text: str,
        *,
        title: str | None = None,
    ) -> dict:
        """Post one message to a bot using endpoint/payload fallbacks."""
        target_bot = bot_id.strip()
        if not target_bot:
            utils.error_exit("invalid_bot_id", "bot_id cannot be empty")

        body = text.strip()
        if not body:
            utils.error_exit("invalid_text", "text cannot be empty")

        title_text = (title or "").strip()
        payloads: list[dict[str, Any]] = [
            {"text": body},
            {"message": body},
            {"content": body},
        ]
        if title_text:
            payloads.extend(
                [
                    {"text": body, "title": title_text},
                    {"message": body, "title": title_text},
                    {"content": body, "title": title_text},
                ]
            )

        candidates: list[tuple[str, str, dict[str, Any] | None]] = []
        for payload in payloads:
            candidates.extend(
                [
                    ("POST", f"/bots/{target_bot}/message", payload),
                    ("POST", f"/bots/{target_bot}/messages", payload),
                    ("POST", f"/bots/{target_bot}/send", payload),
                    ("POST", f"/bot/{target_bot}/message", payload),
                ]
            )

        return self._request_with_candidates_and_not_supported(
            candidates,
            scope_hint="ZohoCliq.Webhooks.CREATE",
            operation_label="post-to-bot",
            not_supported_message="Cliq bot post endpoints are not available for this token/network endpoint. Capture one capabilities snapshot and continue with non-bot operations for this network.",
        )

    def list_bot_subscribers(
        self,
        bot_id: str,
        *,
        limit: int = 50,
    ) -> dict:
        """List subscribers/followers for one bot."""
        target_bot = bot_id.strip()
        if not target_bot:
            utils.error_exit("invalid_bot_id", "bot_id cannot be empty")

        limit_value = max(1, limit)
        candidates: list[tuple[str, dict[str, Any] | None]] = [
            (f"/bots/{target_bot}/subscribers", {"limit": limit_value}),
            (f"/bots/{target_bot}/followers", {"limit": limit_value}),
            (f"/bots/{target_bot}/members", {"limit": limit_value}),
            (f"/bot/{target_bot}/subscribers", {"limit": limit_value}),
        ]

        return self._get_with_candidates_and_not_supported(
            candidates,
            scope_hint="ZohoCliq.Bots.READ",
            operation_label="bot-subscribers",
            not_supported_message="Cliq bot-subscriber endpoints are not available for this token/network endpoint. Capture one capabilities snapshot and continue with non-bot operations for this network.",
        )

    def list_thread_followers(
        self,
        thread_id: str,
        *,
        chat_id: str | None = None,
        channel_id: str | None = None,
        limit: int = 50,
    ) -> dict:
        """List followers/subscribers for one thread."""
        resolved_chat = self._resolve_chat_destination(
            chat_id=chat_id,
            channel_id=channel_id,
        )
        target_thread = thread_id.strip()
        if not target_thread:
            utils.error_exit("invalid_thread_id", "thread_id cannot be empty")

        limit_value = max(1, limit)
        candidates: list[tuple[str, dict[str, Any] | None]] = [
            (
                f"/chats/{resolved_chat}/threads/{target_thread}/followers",
                {"limit": limit_value},
            ),
            (
                f"/chats/{resolved_chat}/threads/{target_thread}/subscribers",
                {"limit": limit_value},
            ),
            (
                f"/chats/{resolved_chat}/threads/{target_thread}/members",
                {"limit": limit_value},
            ),
            (
                f"/chats/{resolved_chat}/messages/{target_thread}/followers",
                {"limit": limit_value},
            ),
        ]

        if channel_id:
            candidates.extend(
                [
                    (
                        f"/channels/{channel_id}/threads/{target_thread}/followers",
                        {"limit": limit_value},
                    ),
                    (
                        f"/channels/{channel_id}/threads/{target_thread}/subscribers",
                        {"limit": limit_value},
                    ),
                ]
            )

        return self._get_with_candidates_and_not_supported(
            candidates,
            scope_hint="ZohoCliq.Messages.READ",
            operation_label="thread-followers",
            not_supported_message="Cliq thread-follower endpoints are not available for this token/network endpoint. Run `zoho cliq capabilities --channel-id <id>` and confirm thread operations for the target conversation.",
        )

    def get_thread_state(
        self,
        thread_id: str,
        *,
        chat_id: str | None = None,
        channel_id: str | None = None,
    ) -> dict:
        """Get one thread's state payload."""
        resolved_chat = self._resolve_chat_destination(
            chat_id=chat_id,
            channel_id=channel_id,
        )
        target_thread = thread_id.strip()
        if not target_thread:
            utils.error_exit("invalid_thread_id", "thread_id cannot be empty")

        candidates: list[tuple[str, dict[str, Any] | None]] = [
            (f"/chats/{resolved_chat}/threads/{target_thread}/state", None),
            (f"/chats/{resolved_chat}/threads/{target_thread}", None),
            (f"/chats/{resolved_chat}/messages/{target_thread}/thread/state", None),
        ]
        if channel_id:
            candidates.extend(
                [
                    (f"/channels/{channel_id}/threads/{target_thread}/state", None),
                    (f"/channels/{channel_id}/threads/{target_thread}", None),
                ]
            )

        return self._get_with_candidates_and_not_supported(
            candidates,
            scope_hint="ZohoCliq.Messages.READ",
            operation_label="thread-state-get",
            not_supported_message="Cliq thread-state read endpoints are not available for this token/network endpoint. Run `zoho cliq capabilities --channel-id <id>` and confirm thread operations for the target conversation.",
        )

    def update_thread_state(
        self,
        thread_id: str,
        state: str,
        *,
        chat_id: str | None = None,
        channel_id: str | None = None,
    ) -> dict:
        """Update one thread's state."""
        resolved_chat = self._resolve_chat_destination(
            chat_id=chat_id,
            channel_id=channel_id,
        )
        target_thread = thread_id.strip()
        if not target_thread:
            utils.error_exit("invalid_thread_id", "thread_id cannot be empty")

        next_state = state.strip()
        if not next_state:
            utils.error_exit("invalid_state", "state cannot be empty")

        payloads = [
            {"state": next_state},
            {"thread_state": next_state},
            {"status": next_state},
            {"threadStatus": next_state},
        ]

        candidates: list[tuple[str, str, dict[str, Any] | None]] = []
        for payload in payloads:
            candidates.extend(
                [
                    (
                        "POST",
                        f"/chats/{resolved_chat}/threads/{target_thread}/state",
                        payload,
                    ),
                    (
                        "PUT",
                        f"/chats/{resolved_chat}/threads/{target_thread}/state",
                        payload,
                    ),
                    (
                        "PATCH",
                        f"/chats/{resolved_chat}/threads/{target_thread}/state",
                        payload,
                    ),
                    (
                        "POST",
                        f"/chats/{resolved_chat}/threads/{target_thread}",
                        payload,
                    ),
                ]
            )

            if channel_id:
                candidates.extend(
                    [
                        (
                            "POST",
                            f"/channels/{channel_id}/threads/{target_thread}/state",
                            payload,
                        ),
                        (
                            "PUT",
                            f"/channels/{channel_id}/threads/{target_thread}/state",
                            payload,
                        ),
                        (
                            "POST",
                            f"/channels/{channel_id}/threads/{target_thread}",
                            payload,
                        ),
                    ]
                )

        return self._request_with_candidates_and_not_supported(
            candidates,
            scope_hint="ZohoCliq.Messages.UPDATE",
            operation_label="thread-state-update",
            not_supported_message="Cliq thread-state update endpoints are not available for this token/network endpoint. Run `zoho cliq capabilities --channel-id <id>` and confirm thread operations for the target conversation.",
        )

    def channels(self, *, limit: int = 50) -> dict:
        """List channels."""
        return self._get("/channels", {"limit": limit})

    def chats(self, *, limit: int = 50) -> dict:
        """List chats (DM/group conversation descriptors)."""
        resp = httpx.get(
            f"{self.base_url}/chats",
            headers=self._headers,
            params={"limit": limit},
            timeout=httpx.Timeout(30.0),
        )
        if resp.is_success:
            return resp.json()

        body = resp.text or ""
        lowered = body.lower()
        if "oauthtoken_scope_invalid" in lowered:
            utils.error_exit(
                "oauth_scope_invalid",
                "Cliq token is missing chat-read scope. Run `zoho cliq status --check-auth` to inspect granted scopes, then re-run `zoho login --with-cliq --scope ZohoCliq.Chats.ALL` and retry.",
            )
        if resp.status_code in (404, 405) or "request_url_invalid" in lowered:
            utils.error_exit(
                "not_supported",
                "Cliq chat listing endpoint is not available for this token/network endpoint.",
            )

        utils.error_exit("api_error", f"HTTP {resp.status_code} GET /chats: {body}")
        return {}

    def export_conversations(self) -> dict:
        """Export conversation descriptors via maintenance bulk-export API."""
        candidates: list[tuple[str, dict[str, Any] | None]] = [
            (
                "/maintenanceapi/v2/chats",
                {
                    "fields": "title,chat_id",
                },
            ),
            (
                "/maintenanceapi/v2/chats?fields=title,chat_id",
                None,
            ),
        ]

        saw_scope_invalid = False
        saw_not_supported = False
        last_error: tuple[int, str, str] | None = None

        for path, params in candidates:
            resp = httpx.get(
                f"{self._service_base_url}{path}",
                headers=self._headers,
                params=params,
                timeout=httpx.Timeout(30.0),
            )

            if resp.is_success:
                payload = resp.json()
                if isinstance(payload, dict):
                    return payload
                return {"data": payload}

            body = resp.text or ""
            lowered = body.lower()
            code = ""
            try:
                parsed = resp.json()
                if isinstance(parsed, dict):
                    code = str(parsed.get("code") or parsed.get("error") or "").lower()
            except ValueError:
                pass

            last_error = (resp.status_code, path, body)

            if "oauthtoken_scope_invalid" in lowered or code in {
                "oauthtoken_scope_invalid",
                "oauth_scope_invalid",
                "scope_mismatch",
                "oauth_scope_mismatch",
            }:
                saw_scope_invalid = True
                continue

            if (
                resp.status_code in (404, 405)
                or "request_url_invalid" in lowered
                or code in {"operation_not_allowed", "not_supported", "unsupported"}
            ):
                saw_not_supported = True
                continue

            utils.error_exit("api_error", f"HTTP {resp.status_code} GET {path}: {body}")

        if saw_scope_invalid:
            utils.error_exit(
                "oauth_scope_invalid",
                f"Cliq token is missing organization-chat export scope. Re-run `zoho login --with-cliq --with-cliq-export` (or add `--scope {CLIQ_EXPORT_CHATS_SCOPE}`) and retry.",
            )

        if saw_not_supported:
            utils.error_exit(
                "not_supported",
                "Cliq export conversations endpoint is not available for this token/network endpoint.",
            )

        if last_error is not None:
            status, path, body = last_error
            utils.error_exit("api_error", f"HTTP {status} GET {path}: {body}")

        utils.error_exit(
            "api_error", "No candidate endpoint available for export conversations"
        )
        return {}

    def export_chat_messages(self, chat_id: str) -> dict:
        """Export one chat's messages via maintenance bulk-export API."""
        resolved_chat = chat_id.strip()
        if not resolved_chat:
            utils.error_exit("invalid_destination", "chat_id cannot be empty")

        path = f"/maintenanceapi/v2/chats/{resolved_chat}/messages"
        resp = httpx.get(
            f"{self._service_base_url}{path}",
            headers=self._headers,
            timeout=httpx.Timeout(30.0),
        )

        if resp.is_success:
            payload = resp.json()
            if isinstance(payload, dict):
                return payload
            return {"data": payload}

        body = resp.text or ""
        lowered = body.lower()
        code = ""
        try:
            parsed = resp.json()
            if isinstance(parsed, dict):
                code = str(parsed.get("code") or parsed.get("error") or "").lower()
        except ValueError:
            pass

        if "oauthtoken_scope_invalid" in lowered or code in {
            "oauthtoken_scope_invalid",
            "oauth_scope_invalid",
            "scope_mismatch",
            "oauth_scope_mismatch",
        }:
            utils.error_exit(
                "oauth_scope_invalid",
                f"Cliq token is missing organization-message export scope. Re-run `zoho login --with-cliq --with-cliq-export` (or add `--scope {CLIQ_EXPORT_MESSAGES_SCOPE}`) and retry.",
            )

        if (
            resp.status_code in (404, 405)
            or "request_url_invalid" in lowered
            or code in {"operation_not_allowed", "not_supported", "unsupported"}
        ):
            utils.error_exit(
                "not_supported",
                "Cliq export chat-messages endpoint is not available for this token/network endpoint.",
            )

        utils.error_exit("api_error", f"HTTP {resp.status_code} GET {path}: {body}")
        return {}

    def users(self, *, limit: int = 50) -> dict:
        """List users."""
        return self._get("/users", {"limit": limit})

    @staticmethod
    def infer_message_types(message: dict[str, Any]) -> list[str]:
        """Infer coarse content types from a raw Cliq message payload."""

        def _as_list(value: Any) -> list[Any]:
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                return [value]
            if isinstance(value, str):
                text = value.strip()
                if text:
                    return [text]
            return []

        types: set[str] = set()

        text_value = str(
            message.get("text")
            or message.get("content")
            or message.get("message")
            or message.get("message_text")
            or message.get("plain_text")
            or ""
        ).strip()
        if text_value:
            types.add("text")

        for key in (
            "reactions",
            "reaction",
            "messageactions",
            "messageActions",
        ):
            if message.get(key):
                types.add("reaction")
                break

        for key in ("sticker", "stickers", "emoji", "emojis"):
            if message.get(key):
                types.add("sticker")
                break

        attachment_items: list[Any] = []
        for key in (
            "attachments",
            "attachment",
            "files",
            "file",
            "slides",
            "cards",
            "card",
            "media",
            "unfurled_details",
            "unfurledDetails",
            "preview",
            "previews",
        ):
            attachment_items.extend(_as_list(message.get(key)))

        content_payload = message.get("content")
        if isinstance(content_payload, dict):
            for key in (
                "attachments",
                "attachment",
                "files",
                "file",
                "image",
                "images",
                "audio",
                "voice",
                "thumbnail",
                "preview",
                "url",
            ):
                attachment_items.extend(_as_list(content_payload.get(key)))

        for item in attachment_items:
            blob = str(item).lower()
            if any(
                token in blob
                for token in (
                    "voice",
                    "audio/",
                    ".mp3",
                    ".m4a",
                    ".wav",
                    ".ogg",
                    ".opus",
                    ".aac",
                    ".amr",
                    ".flac",
                    ".webm",
                )
            ):
                types.add("voice")
            elif any(
                token in blob
                for token in (
                    "image",
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".gif",
                    ".webp",
                    ".bmp",
                    ".heic",
                    ".svg",
                )
            ):
                types.add("image")
            elif any(token in blob for token in ("video", ".mp4", ".mov", ".mkv")):
                types.add("video")
            else:
                types.add("file")

        if not types:
            types.add("unknown")

        return sorted(types)

    def whoami(self, *, account_email: str | None = None, limit: int = 500) -> dict:
        """Best-effort identity lookup for the active Cliq token."""

        attempts: list[dict[str, Any]] = []
        for path in ("/users/me", "/users/self", "/users/current"):
            resp = httpx.get(
                f"{self.base_url}{path}",
                headers=self._headers,
                timeout=httpx.Timeout(30.0),
            )
            if resp.is_success:
                payload = resp.json()
                data = payload.get("data", payload)
                user = data if isinstance(data, dict) else {}
                return {
                    "status": "ok",
                    "source": path,
                    "configuredAccount": (account_email or "").strip(),
                    "user": {
                        "userId": str(
                            user.get("zuid")
                            or user.get("user_id")
                            or user.get("id")
                            or ""
                        ),
                        "name": str(
                            user.get("display_name")
                            or user.get("name")
                            or user.get("full_name")
                            or ""
                        ),
                        "email": str(user.get("email_id") or user.get("email") or ""),
                        "raw": user,
                    },
                    "attempts": attempts,
                }

            body = resp.text or ""
            code = ""
            message = body[:200]
            try:
                parsed = resp.json()
                if isinstance(parsed, dict):
                    code = str(parsed.get("code") or parsed.get("error") or "")
                    message = str(
                        parsed.get("message")
                        or parsed.get("error_description")
                        or message
                    )
            except ValueError:
                pass
            attempts.append(
                {
                    "path": path,
                    "httpStatus": resp.status_code,
                    "code": code,
                    "message": message,
                }
            )

        configured = (account_email or "").strip()
        if configured:
            directory_resp = httpx.get(
                f"{self.base_url}/users",
                headers=self._headers,
                params={"limit": limit},
                timeout=httpx.Timeout(30.0),
            )
            if directory_resp.is_success:
                payload = directory_resp.json()
                users = payload.get("data", payload)
                if not isinstance(users, list):
                    users = []

                configured_lc = configured.lower()
                match: dict[str, Any] | None = None
                for user in users:
                    if not isinstance(user, dict):
                        continue
                    email = str(user.get("email_id") or user.get("email") or "").strip()
                    if email and email.lower() == configured_lc:
                        match = user
                        break

                if match is not None:
                    return {
                        "status": "best_effort",
                        "source": "users.email_match",
                        "configuredAccount": configured,
                        "user": {
                            "userId": str(
                                match.get("zuid")
                                or match.get("user_id")
                                or match.get("id")
                                or ""
                            ),
                            "name": str(
                                match.get("display_name")
                                or match.get("name")
                                or match.get("full_name")
                                or ""
                            ),
                            "email": str(
                                match.get("email_id") or match.get("email") or ""
                            ),
                            "raw": match,
                        },
                        "attempts": attempts,
                        "warning": "Direct /users/me lookup was unavailable; result is inferred from directory email match.",
                    }
            else:
                body = directory_resp.text or ""
                code = ""
                message = body[:200]
                try:
                    parsed = directory_resp.json()
                    if isinstance(parsed, dict):
                        code = str(parsed.get("code") or parsed.get("error") or "")
                        message = str(
                            parsed.get("message")
                            or parsed.get("error_description")
                            or message
                        )
                except ValueError:
                    pass
                attempts.append(
                    {
                        "path": "/users",
                        "httpStatus": directory_resp.status_code,
                        "code": code,
                        "message": message,
                    }
                )

        return {
            "status": "unknown",
            "source": "unresolved",
            "configuredAccount": configured,
            "user": {},
            "attempts": attempts,
            "warning": "Unable to resolve active Cliq identity from current token/network endpoints.",
        }

    def resolve_users(
        self,
        query: str,
        *,
        by: str = "auto",
        limit: int = 500,
    ) -> dict:
        """Resolve user ids by email or display name from the user directory."""
        needle = query.strip()
        if not needle:
            utils.error_exit("invalid_query", "query cannot be empty")

        mode = by.strip().lower()
        if mode not in {"auto", "email", "name"}:
            utils.error_exit(
                "invalid_query_mode", "--by must be one of: auto, email, name"
            )

        payload = self.users(limit=limit)
        users = payload.get("data", payload)
        if not isinstance(users, list):
            users = []

        needle_lc = needle.lower()
        email_first = mode == "email" or (mode == "auto" and "@" in needle_lc)
        name_only = mode == "name"

        matches: list[dict[str, Any]] = []
        for user in users:
            if not isinstance(user, dict):
                continue

            name = str(
                user.get("display_name")
                or user.get("name")
                or user.get("full_name")
                or ""
            ).strip()
            email = str(user.get("email_id") or user.get("email") or "").strip()
            user_id = str(
                user.get("zuid") or user.get("user_id") or user.get("id") or ""
            ).strip()
            if not user_id:
                continue

            name_lc = name.lower()
            email_lc = email.lower()

            email_exact = bool(email) and email_lc == needle_lc
            name_exact = bool(name) and name_lc == needle_lc
            email_hit = bool(email) and needle_lc in email_lc
            name_hit = bool(name) and needle_lc in name_lc

            matched = False
            if name_only:
                matched = name_hit
            elif email_first:
                matched = email_hit or name_exact
            else:
                matched = email_hit or name_hit

            if not matched:
                continue

            score = 0
            if email_exact:
                score += 100
            if name_exact:
                score += 90
            if email_hit:
                score += 40
            if name_hit:
                score += 30

            matches.append(
                {
                    "userId": user_id,
                    "name": name,
                    "email": email,
                    "emailExact": email_exact,
                    "nameExact": name_exact,
                    "score": score,
                }
            )

        matches.sort(
            key=lambda item: (
                -int(item.get("score", 0)),
                str(item.get("name", "")).lower(),
                str(item.get("email", "")).lower(),
            )
        )

        return {
            "query": needle,
            "by": mode,
            "count": len(matches),
            "matches": matches,
        }

    def _resolve_user_target(self, user_id: str) -> str:
        """Best-effort normalization for user destinations.

        Cliq send endpoints usually accept canonical user ids reliably.
        When callers pass an email-like identifier, attempt one directory
        lookup and fall back to the original value if lookup is unavailable.
        """
        target = (user_id or "").strip()
        if not target or "@" not in target:
            return target

        try:
            resolved = self.resolve_users(target, by="email", limit=200)
        except SystemExit:
            return target

        matches = resolved.get("matches") if isinstance(resolved, dict) else []
        if not isinstance(matches, list) or not matches:
            return target

        for match in matches:
            if not isinstance(match, dict):
                continue
            if match.get("emailExact"):
                user_match = str(match.get("userId") or "").strip()
                if user_match:
                    return user_match

        for match in matches:
            if not isinstance(match, dict):
                continue
            user_match = str(match.get("userId") or "").strip()
            if user_match:
                return user_match

        return target

    def _candidate_user_targets(self, user_id: str) -> list[str]:
        """Build a fallback chain for user-target endpoints.

        Keep the original input first for backward compatibility, then append
        one resolved canonical id when available.
        """
        raw_target = (user_id or "").strip()
        if not raw_target:
            return []

        resolved_target = self._resolve_user_target(raw_target)
        candidates = [raw_target]
        if resolved_target and resolved_target != raw_target:
            candidates.append(resolved_target)

        seen: set[str] = set()
        return [
            target for target in candidates if not (target in seen or seen.add(target))
        ]

    def list_members(
        self,
        *,
        channel_id: str | None = None,
        chat_id: str | None = None,
    ) -> dict:
        """List members for a channel/chat with endpoint fallbacks."""
        resolved_chat = (chat_id or "").strip()

        candidates: list[str] = []
        if channel_id:
            candidates.append(f"/channels/{channel_id}/members")
        if resolved_chat:
            candidates.append(f"/chats/{resolved_chat}/members")

        if not candidates:
            utils.error_exit(
                "invalid_destination", "Provide --chat-id or resolvable --channel-id"
            )

        last_error: tuple[int, str, str] | None = None
        for path in candidates:
            resp = httpx.get(
                f"{self.base_url}{path}",
                headers=self._headers,
                timeout=httpx.Timeout(30.0),
            )
            if resp.is_success:
                return resp.json()
            body = resp.text or ""
            last_error = (resp.status_code, path, body)
            lowered = body.lower()
            if resp.status_code in (404, 405) or "request_url_invalid" in lowered:
                continue
            if "oauthtoken_scope_invalid" in lowered:
                utils.error_exit(
                    "oauth_scope_invalid",
                    "Cliq token is missing required member-read scope. Re-run `zoho login --with-cliq --scope ZohoCliq.Channels.READ` and retry.",
                )
            utils.error_exit("api_error", f"HTTP {resp.status_code} GET {path}: {body}")

        if last_error is not None:
            status, path, body = last_error
            utils.error_exit("api_error", f"HTTP {status} GET {path}: {body}")
        utils.error_exit(
            "api_error", "No candidate endpoint available for members list"
        )
        return {}

    def add_member(
        self,
        member_id: str,
        *,
        channel_id: str | None = None,
        chat_id: str | None = None,
    ) -> dict:
        """Add a member to a channel/chat with endpoint/payload fallbacks."""
        target_member = member_id.strip()
        if not target_member:
            utils.error_exit("invalid_member_id", "member_id cannot be empty")

        resolved_chat = (chat_id or "").strip()
        if not resolved_chat and channel_id:
            resolved_chat = self.resolve_chat_id(channel_id) or ""

        payloads = [
            {"user_id": target_member},
            {"member_id": target_member},
            {"user": target_member},
            {"users": [target_member]},
            {"members": [target_member]},
            {"user_ids": [target_member]},
            {"member_ids": [target_member]},
        ]

        candidates: list[tuple[str, str, dict[str, Any] | None]] = []
        if channel_id:
            for payload in payloads:
                candidates.extend(
                    [
                        ("POST", f"/channels/{channel_id}/members", payload),
                        ("POST", f"/channels/{channel_id}/members/add", payload),
                        ("POST", f"/channels/{channel_id}/participants/add", payload),
                        ("PUT", f"/channels/{channel_id}/members", payload),
                    ]
                )
            candidates.extend(
                [
                    ("PUT", f"/channels/{channel_id}/members/{target_member}", None),
                    (
                        "POST",
                        f"/channels/{channel_id}/members/{target_member}",
                        None,
                    ),
                ]
            )
        if resolved_chat:
            for payload in payloads:
                candidates.extend(
                    [
                        ("POST", f"/chats/{resolved_chat}/members", payload),
                        ("POST", f"/chats/{resolved_chat}/members/add", payload),
                        ("POST", f"/chats/{resolved_chat}/participants/add", payload),
                        ("PUT", f"/chats/{resolved_chat}/members", payload),
                    ]
                )
            candidates.extend(
                [
                    ("PUT", f"/chats/{resolved_chat}/members/{target_member}", None),
                    (
                        "POST",
                        f"/chats/{resolved_chat}/members/{target_member}",
                        None,
                    ),
                ]
            )

        if not candidates:
            utils.error_exit(
                "invalid_destination", "Provide --chat-id or resolvable --channel-id"
            )

        return self._request_with_candidates(
            candidates,
            scope_hint="ZohoCliq.Channels.ALL",
            operation_label="member-add",
        )

    def remove_member(
        self,
        member_id: str,
        *,
        channel_id: str | None = None,
        chat_id: str | None = None,
    ) -> dict:
        """Remove a member from a channel/chat with endpoint/payload fallbacks."""
        target_member = member_id.strip()
        if not target_member:
            utils.error_exit("invalid_member_id", "member_id cannot be empty")

        resolved_chat = (chat_id or "").strip()
        if not resolved_chat and channel_id:
            resolved_chat = self.resolve_chat_id(channel_id) or ""

        payloads = [
            {"user_id": target_member},
            {"member_id": target_member},
            {"user": target_member},
            {"users": [target_member]},
            {"members": [target_member]},
            {"user_ids": [target_member]},
            {"member_ids": [target_member]},
        ]

        candidates: list[tuple[str, str, dict[str, Any] | None]] = []
        if channel_id:
            candidates.append(
                ("DELETE", f"/channels/{channel_id}/members/{target_member}", None)
            )
            candidates.append(
                ("DELETE", f"/channels/{channel_id}/participants/{target_member}", None)
            )
            for payload in payloads:
                candidates.extend(
                    [
                        ("POST", f"/channels/{channel_id}/members/remove", payload),
                        (
                            "POST",
                            f"/channels/{channel_id}/participants/remove",
                            payload,
                        ),
                    ]
                )
        if resolved_chat:
            candidates.append(
                ("DELETE", f"/chats/{resolved_chat}/members/{target_member}", None)
            )
            candidates.append(
                ("DELETE", f"/chats/{resolved_chat}/participants/{target_member}", None)
            )
            for payload in payloads:
                candidates.extend(
                    [
                        ("POST", f"/chats/{resolved_chat}/members/remove", payload),
                        (
                            "POST",
                            f"/chats/{resolved_chat}/participants/remove",
                            payload,
                        ),
                    ]
                )

        if not candidates:
            utils.error_exit(
                "invalid_destination", "Provide --chat-id or resolvable --channel-id"
            )

        return self._request_with_candidates(
            candidates,
            scope_hint="ZohoCliq.Channels.ALL",
            operation_label="member-remove",
        )

    def create_channel(
        self,
        name: str,
        *,
        level: str = "organization",
    ) -> dict:
        """Create a channel."""
        payload = {"name": name.strip(), "level": level.strip()}
        if not payload["name"]:
            utils.error_exit("invalid_name", "channel name cannot be empty")

        return self._request_with_candidates(
            [("POST", "/channels", payload)],
            scope_hint="ZohoCliq.Channels.ALL",
            operation_label="channel-create",
        )

    def rename_channel(self, channel_id: str, name: str) -> dict:
        """Rename a channel."""
        cid = channel_id.strip()
        if not cid:
            utils.error_exit("invalid_channel_id", "channel_id cannot be empty")

        target_name = name.strip()
        if not target_name:
            utils.error_exit("invalid_name", "channel name cannot be empty")

        payloads = [
            {"name": target_name},
            {"new_name": target_name},
            {"channel_name": target_name},
        ]

        candidates: list[tuple[str, str, dict[str, Any] | None]] = []
        for payload in payloads:
            candidates.extend(
                [
                    ("POST", f"/channels/{cid}/rename", payload),
                    ("PUT", f"/channels/{cid}", payload),
                    ("PATCH", f"/channels/{cid}", payload),
                    ("POST", f"/channels/{cid}", payload),
                    ("POST", f"/channels/{cid}/update", payload),
                ]
            )

        return self._request_with_candidates(
            candidates,
            scope_hint="ZohoCliq.Channels.ALL",
            operation_label="channel-rename",
        )

    def update_channel_topic(self, channel_id: str, topic: str) -> dict:
        """Update a channel topic."""
        cid = channel_id.strip()
        if not cid:
            utils.error_exit("invalid_channel_id", "channel_id cannot be empty")

        target_topic = topic.strip()
        if not target_topic:
            utils.error_exit("invalid_topic", "channel topic cannot be empty")

        payloads = [
            {"topic": target_topic},
            {"description": target_topic},
            {"channel_topic": target_topic},
        ]

        candidates: list[tuple[str, str, dict[str, Any] | None]] = []
        for payload in payloads:
            candidates.extend(
                [
                    ("POST", f"/channels/{cid}/topic", payload),
                    ("PUT", f"/channels/{cid}", payload),
                    ("PATCH", f"/channels/{cid}", payload),
                    ("POST", f"/channels/{cid}", payload),
                    ("POST", f"/channels/{cid}/update", payload),
                ]
            )

        return self._request_with_candidates(
            candidates,
            scope_hint="ZohoCliq.Channels.ALL",
            operation_label="channel-topic",
        )

    def archive_channel(self, channel_id: str, *, unarchive: bool = False) -> dict:
        """Archive/unarchive a channel."""
        cid = channel_id.strip()
        if not cid:
            utils.error_exit("invalid_channel_id", "channel_id cannot be empty")

        path = f"/channels/{cid}/unarchive" if unarchive else f"/channels/{cid}/archive"
        return self._request_with_candidates(
            [("POST", path, {})],
            scope_hint="ZohoCliq.Channels.ALL",
            operation_label="channel-unarchive" if unarchive else "channel-archive",
        )

    def delete_channel(self, channel_id: str) -> dict:
        """Delete a channel."""
        cid = channel_id.strip()
        if not cid:
            utils.error_exit("invalid_channel_id", "channel_id cannot be empty")

        return self._request_with_candidates(
            [
                ("DELETE", f"/channels/{cid}", None),
                ("POST", f"/channels/{cid}/delete", {}),
            ],
            scope_hint="ZohoCliq.Channels.ALL",
            operation_label="channel-delete",
        )

    def _probe_request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            resp = httpx.request(
                method,
                f"{self.base_url}{path}",
                headers=self._headers,
                params=params or {},
                json=payload,
                timeout=httpx.Timeout(30.0),
            )
        except httpx.HTTPError as exc:
            return {
                "ok": False,
                "status": "transport_error",
                "error": str(exc),
            }

        body = resp.text or ""
        code = ""
        message = ""
        try:
            parsed = resp.json()
            if isinstance(parsed, dict):
                code = str(parsed.get("code") or parsed.get("error") or "")
                message = str(
                    parsed.get("message") or parsed.get("error_description") or ""
                )
        except ValueError:
            pass

        if resp.is_success:
            return {
                "ok": True,
                "httpStatus": resp.status_code,
                "code": code or "ok",
            }

        lowered = body.lower()
        status = "error"
        if resp.status_code in (401, 403):
            status = "forbidden_or_scope"
        elif resp.status_code == 429:
            status = "rate_limited"
        elif resp.status_code in (404, 405) or "request_url_invalid" in lowered:
            status = "not_supported"

        return {
            "ok": False,
            "httpStatus": resp.status_code,
            "status": status,
            "code": code,
            "message": message or body[:200],
        }

    def probe_capabilities(
        self,
        *,
        channel_id: str | None = None,
        user_id: str | None = None,
        message_id: str | None = None,
    ) -> dict[str, Any]:
        """Probe currently-available Cliq read endpoints for this token/org."""
        checks: list[dict[str, Any]] = [
            {
                "name": "channels.list",
                "kind": "read",
                "method": "GET",
                "path": "/channels",
                "params": {"limit": 1},
            },
            {
                "name": "users.list",
                "kind": "read",
                "method": "GET",
                "path": "/users",
                "params": {"limit": 1},
            },
        ]

        resolved_chat_id = self.resolve_chat_id(channel_id) if channel_id else None

        if channel_id:
            checks.extend(
                [
                    {
                        "name": "channels.get",
                        "kind": "read",
                        "method": "GET",
                        "path": f"/channels/{channel_id}",
                        "params": {},
                    },
                    {
                        "name": "chats.messages.list",
                        "kind": "read",
                        "method": "GET",
                        "path": f"/chats/{resolved_chat_id or channel_id}/messages",
                        "params": {"limit": 1},
                    },
                    {
                        "name": "channels.messages.list",
                        "kind": "read",
                        "method": "GET",
                        "path": f"/channels/{channel_id}/messages",
                        "params": {"limit": 1},
                    },
                ]
            )

        probe_message_id = (message_id or "").strip()
        if probe_message_id:
            target_chat = (resolved_chat_id or channel_id or "").strip()
            if target_chat:
                checks.extend(
                    [
                        {
                            "name": "chats.messages.get",
                            "kind": "read",
                            "method": "GET",
                            "path": f"/chats/{target_chat}/messages/{probe_message_id}",
                            "params": {},
                        },
                        {
                            "name": "chats.messages.files",
                            "kind": "read",
                            "method": "GET",
                            "path": f"/chats/{target_chat}/messages/{probe_message_id}/files",
                            "params": {},
                        },
                        {
                            "name": "chats.messages.attachments",
                            "kind": "read",
                            "method": "GET",
                            "path": f"/chats/{target_chat}/messages/{probe_message_id}/attachments",
                            "params": {},
                        },
                    ]
                )

            if channel_id:
                checks.extend(
                    [
                        {
                            "name": "channels.messages.get",
                            "kind": "read",
                            "method": "GET",
                            "path": f"/channels/{channel_id}/messages/{probe_message_id}",
                            "params": {},
                        },
                        {
                            "name": "channels.messages.files",
                            "kind": "read",
                            "method": "GET",
                            "path": f"/channels/{channel_id}/messages/{probe_message_id}/files",
                            "params": {},
                        },
                        {
                            "name": "channels.messages.attachments",
                            "kind": "read",
                            "method": "GET",
                            "path": f"/channels/{channel_id}/messages/{probe_message_id}/attachments",
                            "params": {},
                        },
                    ]
                )

        if user_id:
            checks.extend(
                [
                    {
                        "name": "users.get",
                        "kind": "read",
                        "method": "GET",
                        "path": f"/users/{user_id}",
                        "params": {},
                    },
                    {
                        "name": "buddies.get",
                        "kind": "read",
                        "method": "GET",
                        "path": f"/buddies/{user_id}",
                        "params": {},
                    },
                ]
            )

        results: list[dict[str, Any]] = []
        for check in checks:
            probe = self._probe_request(
                check["method"],
                check["path"],
                params=check.get("params"),
            )
            results.append(
                {
                    "name": check["name"],
                    "kind": check["kind"],
                    "method": check["method"],
                    "path": check["path"],
                    **probe,
                }
            )

        ok_count = sum(1 for item in results if item.get("ok"))
        return {
            "checks": results,
            "summary": {
                "total": len(results),
                "ok": ok_count,
                "blocked": len(results) - ok_count,
            },
        }

    def send_message(
        self,
        text: str,
        *,
        channel_id: Optional[str] = None,
        user_id: Optional[str] = None,
        attachment: dict[str, Any] | None = None,
        card: dict[str, Any] | None = None,
        strict_media: bool = False,
    ) -> dict:
        """Send a message to either a channel or a user."""
        if bool(channel_id) == bool(user_id):
            raise ValueError("Provide exactly one of channel_id or user_id")

        msg_text = text.strip()
        if not msg_text and not attachment and not card:
            utils.error_exit(
                "invalid_message",
                "Provide --text, --sticker, or one media option (--image-url/--file-url/--audio-url/--voice-url)",
            )

        payloads: list[dict[str, Any]] = []
        base_payload: dict[str, Any] = {}
        if msg_text:
            base_payload["text"] = msg_text

        if attachment:
            payloads.append({**base_payload, "attachments": attachment})
        if card:
            payloads.append({**base_payload, "card": card})
        if msg_text:
            payloads.append(dict(base_payload))
        elif attachment and isinstance(attachment.get("url"), str):
            payloads.append({"text": str(attachment.get("url", "")).strip()})

        if strict_media and (attachment or card):
            payloads = [
                payload
                for payload in payloads
                if "attachments" in payload or "card" in payload
            ]

        # Preserve order while deduplicating payload variants.
        seen_payloads: set[str] = set()
        unique_payloads: list[dict[str, Any]] = []
        for payload in payloads:
            key = repr(sorted(payload.items(), key=lambda kv: kv[0]))
            if key in seen_payloads:
                continue
            seen_payloads.add(key)
            unique_payloads.append(payload)

        if not unique_payloads:
            unique_payloads = [dict(base_payload)]

        paths: list[str]
        if channel_id:
            resolved_candidates = self._resolve_channel_message_paths(channel_id)
            raw_candidates = [
                f"/chats/{channel_id}/message",
                f"/channels/{channel_id}/message",
            ]
            if not self._looks_like_channel_id(channel_id):
                raw_candidates.insert(0, f"/channelsbyname/{channel_id}/message")
            candidates = resolved_candidates + raw_candidates

            seen: set[str] = set()
            paths = [p for p in candidates if not (p in seen or seen.add(p))]
        else:
            paths = []
            for target_user in self._candidate_user_targets(user_id or ""):
                paths.extend(
                    [
                        f"/buddies/{target_user}/message",
                        f"/buddies/{target_user}/messages",
                        f"/users/{target_user}/message",
                        f"/users/{target_user}/messages",
                    ]
                )

        candidates: list[tuple[str, str, dict[str, Any] | None]] = []
        for payload in unique_payloads:
            for path in paths:
                candidates.append(("POST", path, payload))

        return self._request_with_candidates(
            candidates,
            scope_hint="ZohoCliq.Webhooks.CREATE",
            operation_label="send",
        )

    def send_local_file_message(
        self,
        file_path: str,
        *,
        text: str = "",
        channel_id: Optional[str] = None,
        user_id: Optional[str] = None,
        media_kind: str = "file",
    ) -> dict:
        """Send a local file via multipart form-data to a channel or user."""
        if bool(channel_id) == bool(user_id):
            raise ValueError("Provide exactly one of channel_id or user_id")

        path_obj = Path(file_path).expanduser()
        if not path_obj.exists() or not path_obj.is_file():
            utils.error_exit("invalid_file", f"File not found: {path_obj}")

        msg_text = text.strip()
        guessed_mime = mimetypes.guess_type(path_obj.name)[0] or (
            "audio/mp4" if media_kind == "voice" else "application/octet-stream"
        )

        destination_paths: list[str]
        if channel_id:
            resolved_candidates = self._resolve_channel_message_paths(channel_id)
            raw_candidates = [
                f"/chats/{channel_id}/message",
                f"/channels/{channel_id}/message",
            ]
            if not self._looks_like_channel_id(channel_id):
                raw_candidates.insert(0, f"/channelsbyname/{channel_id}/message")
            base_message_paths = resolved_candidates + raw_candidates

            expanded_candidates: list[str] = []
            file_share_candidates: list[str] = []
            for candidate in base_message_paths:
                expanded_candidates.append(candidate)
                if candidate.endswith("/message"):
                    expanded_candidates.append(f"{candidate}s")
                    file_share_candidates.append(
                        f"{candidate[: -len('/message')]}/files"
                    )

            seen: set[str] = set()
            destination_paths = [
                p
                for p in (expanded_candidates + file_share_candidates)
                if not (p in seen or seen.add(p))
            ]
        else:
            destination_paths = []
            for target_user in self._candidate_user_targets(user_id or ""):
                destination_paths.extend(
                    [
                        f"/buddies/{target_user}/message",
                        f"/buddies/{target_user}/messages",
                        f"/users/{target_user}/message",
                        f"/users/{target_user}/messages",
                        f"/buddies/{target_user}/files",
                        f"/users/{target_user}/files",
                    ]
                )

        message_file_fields = ["file", "attachment", "files", "attachments"]
        if media_kind == "voice":
            message_file_fields = ["voice", "audio", "file", "attachment"]
        elif media_kind == "image":
            message_file_fields = ["image", "photo", "file", "attachment"]

        message_form_data: list[dict[str, Any]] = []
        if msg_text:
            message_form_data.append({"text": msg_text})
            if media_kind in {"image", "file"}:
                message_form_data.append({"caption": msg_text})
        message_form_data.append({})

        # Bound attempt fan-out to avoid long hangs on non-responsive endpoints.
        request_timeout = httpx.Timeout(20.0, connect=8.0, read=8.0, write=12.0)
        max_attempts = 40
        attempts = 0

        last_error: tuple[int, str, str, str] | None = None
        saw_scope_invalid = False
        saw_endpoint_limitation = False
        saw_non_limitation_failure = False
        attempt_summaries: list[str] = []
        seen_attempt_summaries: set[str] = set()
        retryable_codes = {
            "param_missing",
            "invalid_data",
            "operation_failed",
            "extra_key_found",
            "extra_param_found",
            "request_url_invalid",
            "input_json_invalid",
        }

        def _record_attempt(
            status: int,
            send_path: str,
            field_name: str,
            code: str,
            body: str,
        ) -> None:
            error_code = code
            if not error_code:
                stripped = body.strip()
                error_code = stripped.split()[0].lower() if stripped else "unknown"
            summary = (
                f"{send_path} field={field_name} status={status} code={error_code}"
            )
            if summary in seen_attempt_summaries:
                return
            seen_attempt_summaries.add(summary)
            attempt_summaries.append(summary)

        def _attempt_suffix() -> str:
            if not attempt_summaries:
                return ""
            preview = "; ".join(attempt_summaries[:12])
            if len(attempt_summaries) > 12:
                preview = f"{preview}; ..."
            return f" | attempts: {preview}"

        stop_early = False
        for send_path in destination_paths:
            if send_path.endswith("/files"):
                path_file_fields = ["files", "file"]
                path_form_data = (
                    [
                        {"comments": json.dumps([msg_text], ensure_ascii=False)},
                        {},
                    ]
                    if msg_text
                    else [{}]
                )
            else:
                path_file_fields = message_file_fields
                path_form_data = message_form_data

            skip_current_path = False
            for field_name in path_file_fields:
                for form_data in path_form_data:
                    attempts += 1
                    if attempts > max_attempts:
                        stop_early = True
                        break

                    try:
                        with path_obj.open("rb") as handle:
                            files = [
                                (
                                    field_name,
                                    (path_obj.name, handle, guessed_mime),
                                )
                            ]
                            resp = httpx.post(
                                f"{self.base_url}{send_path}",
                                headers=self._headers,
                                data=form_data,
                                files=files,
                                timeout=request_timeout,
                            )
                    except httpx.TimeoutException as exc:
                        body = f"timeout: {exc.__class__.__name__}"
                        last_error = (599, send_path, field_name, body)
                        saw_non_limitation_failure = True
                        _record_attempt(599, send_path, field_name, "timeout", body)
                        continue

                    if resp.is_success:
                        decoded = self._decode_success_response(resp)
                        upload_meta = {
                            "path": send_path,
                            "field": field_name,
                            "fileName": path_obj.name,
                            "mimeType": guessed_mime,
                        }
                        data_payload = decoded.get("data")
                        if isinstance(data_payload, dict):
                            data_payload.setdefault("upload", upload_meta)
                        else:
                            decoded["upload"] = upload_meta
                        return decoded

                    body = resp.text or ""
                    lowered = body.lower()
                    code = ""
                    try:
                        parsed = resp.json()
                        if isinstance(parsed, dict):
                            code = str(
                                parsed.get("code") or parsed.get("error") or ""
                            ).lower()
                    except ValueError:
                        pass

                    last_error = (resp.status_code, send_path, field_name, body)
                    _record_attempt(resp.status_code, send_path, field_name, code, body)
                    if "oauthtoken_scope_invalid" in lowered:
                        saw_scope_invalid = True
                        continue

                    endpoint_miss = (
                        resp.status_code in (404, 405)
                        or "request_url_invalid" in lowered
                        or code
                        in {
                            "request_method_invalid",
                            "operation_failed",
                            "operation_not_allowed",
                            "not_supported",
                            "unsupported",
                        }
                    )

                    if endpoint_miss:
                        saw_endpoint_limitation = True
                        skip_current_path = True
                        break

                    if code in retryable_codes:
                        saw_non_limitation_failure = True
                        continue

                    if resp.status_code == 408:
                        saw_non_limitation_failure = True
                        continue

                    utils.error_exit(
                        "api_error",
                        f"HTTP {resp.status_code} POST {send_path} (field={field_name}): {body}{_attempt_suffix()}",
                    )

                if stop_early or skip_current_path:
                    break
            if stop_early:
                break

        if saw_scope_invalid:
            utils.error_exit(
                "oauth_scope_invalid",
                "Cliq token is missing scope for local file upload send. Re-run `zoho login --with-cliq` and include chat/message/media scopes, then retry.",
            )

        if last_error is not None:
            status, send_path, field_name, body = last_error
            capped_note = (
                " (attempt cap reached)"
                if stop_early or attempts >= max_attempts
                else ""
            )
            if (
                saw_endpoint_limitation
                and not saw_non_limitation_failure
                and not stop_early
            ):
                utils.error_exit(
                    "not_supported",
                    "Cliq local multipart upload endpoints are not supported for this token/network target. Text send can still succeed; collect `attempts:` evidence and treat this as endpoint limitation."
                    + _attempt_suffix(),
                )
            utils.error_exit(
                "api_error",
                f"HTTP {status} POST {send_path} (field={field_name}): {body}{capped_note}{_attempt_suffix()}",
            )

        utils.error_exit("api_error", "No candidate endpoint available for file send")
        return {}


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
