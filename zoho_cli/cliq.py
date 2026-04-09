"""Cliq scaffolding helpers and lightweight client shell."""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from zoho_cli import utils


DEFAULT_CLIQ_SCOPES = [
    "ZohoCliq.Channels.READ",
    "ZohoCliq.Users.READ",
    "ZohoCliq.Messages.READ",
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

    def _resolve_channel_message_paths(self, channel_id: str) -> list[str]:
        """Resolve channel-id to sendable chat/unique-name message endpoints."""
        data = self._get_channel_descriptor(channel_id)
        if not isinstance(data, dict):
            return []

        paths: list[str] = []
        chat_id = self.resolve_chat_id(channel_id)
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
        resolved_chat = (chat_id or "").strip()
        if not resolved_chat and channel_id:
            resolved_chat = self.resolve_chat_id(channel_id) or ""
        if not resolved_chat and channel_id:
            resolved_chat = self.resolve_chat_id(channel_id) or ""
        if not resolved_chat:
            utils.error_exit(
                "invalid_destination", "Provide --chat-id or resolvable --channel-id"
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
        resolved_chat = (chat_id or "").strip()
        if not resolved_chat and channel_id:
            resolved_chat = self.resolve_chat_id(channel_id) or ""
        if not resolved_chat and channel_id:
            resolved_chat = self.resolve_chat_id(channel_id) or ""
        if not resolved_chat:
            utils.error_exit(
                "invalid_destination", "Provide --chat-id or resolvable --channel-id"
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
        last_error: tuple[int, str, str] | None = None

        for path in path_candidates:
            resp = httpx.get(
                f"{self.base_url}{path}",
                headers=self._headers,
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

            if error_code in {
                "message_attachment_not_found",
                "no_attachments_found",
            }:
                return {"files": []}

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

    def channels(self, *, limit: int = 50) -> dict:
        """List channels."""
        return self._get("/channels", {"limit": limit})

    def users(self, *, limit: int = 50) -> dict:
        """List users."""
        return self._get("/users", {"limit": limit})

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
            candidates = [
                f"/channelsbyname/{channel_id}/message",
                f"/chats/{channel_id}/message",
            ]
            candidates.extend(self._resolve_channel_message_paths(channel_id))

            seen: set[str] = set()
            paths = [p for p in candidates if not (p in seen or seen.add(p))]
        else:
            paths = [
                f"/buddies/{user_id}/message",
                f"/users/{user_id}/message",
            ]

        candidates: list[tuple[str, str, dict[str, Any] | None]] = []
        for payload in unique_payloads:
            for path in paths:
                candidates.append(("POST", path, payload))

        return self._request_with_candidates(
            candidates,
            scope_hint="ZohoCliq.Webhooks.CREATE",
            operation_label="send",
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
