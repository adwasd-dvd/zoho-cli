"""Cliq scaffolding helpers and lightweight client shell."""

from __future__ import annotations

import json
import mimetypes
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from zoho_cli import config as zoho_config
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

UNSUPPORTED_THRESHOLD_DEFAULT = 3
UNSUPPORTED_TRACKER_VERSION = 1


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

    _HANDOFF_SOURCE_PATH_MARKERS: tuple[str, ...] = (
        ".handoff.envelopeDefaults",
        ".handoff.envelope_defaults",
        ".handoff.envelope-defaults",
        ".hand_off.envelopeDefaults",
        ".hand_off.envelope_defaults",
        ".hand_off.envelope-defaults",
        ".hand-off.envelopeDefaults",
        ".hand-off.envelope_defaults",
        ".hand-off.envelope-defaults",
        ".handoff.payloadTemplate",
        ".handoff.payload_template",
        ".handoff.payload-template",
        ".hand_off.payloadTemplate",
        ".hand_off.payload_template",
        ".hand_off.payload-template",
        ".hand-off.payloadTemplate",
        ".hand-off.payload_template",
        ".hand-off.payload-template",
    )

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

    @staticmethod
    def _unsupported_threshold() -> int:
        raw = (os.environ.get("ZOHO_CLIQ_UNSUPPORTED_THRESHOLD") or "").strip()
        if not raw:
            return UNSUPPORTED_THRESHOLD_DEFAULT
        try:
            value = int(raw)
        except ValueError:
            return UNSUPPORTED_THRESHOLD_DEFAULT
        return max(1, value)

    @staticmethod
    def _force_unsupported_recheck_enabled() -> bool:
        raw = (os.environ.get("ZOHO_CLIQ_FORCE_UNSUPPORTED_RECHECK") or "").strip()
        return raw.lower() in {"1", "true", "yes", "on"}

    def _unsupported_tracker_path(self) -> Path:
        override = (os.environ.get("ZOHO_CLIQ_UNSUPPORTED_TRACKER_PATH") or "").strip()
        if override:
            return Path(override).expanduser()
        return zoho_config.config_path().parent / "cliq_unsupported_tracker.json"

    def _unsupported_operation_key(self, operation_label: str) -> str:
        label = operation_label.strip().lower() or "unknown-operation"
        return f"{self.base_url}::{label}"

    def _read_unsupported_tracker(self) -> dict[str, Any]:
        path = self._unsupported_tracker_path()
        if not path.exists():
            return {"version": UNSUPPORTED_TRACKER_VERSION, "operations": {}}

        try:
            raw = path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            return {"version": UNSUPPORTED_TRACKER_VERSION, "operations": {}}

        if not raw:
            return {"version": UNSUPPORTED_TRACKER_VERSION, "operations": {}}

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return {"version": UNSUPPORTED_TRACKER_VERSION, "operations": {}}

        if not isinstance(payload, dict):
            return {"version": UNSUPPORTED_TRACKER_VERSION, "operations": {}}

        operations = payload.get("operations")
        if not isinstance(operations, dict):
            operations = {}

        return {
            "version": UNSUPPORTED_TRACKER_VERSION,
            "operations": operations,
        }

    def _write_unsupported_tracker(self, payload: dict[str, Any]) -> None:
        path = self._unsupported_tracker_path()
        data = {
            "version": UNSUPPORTED_TRACKER_VERSION,
            "operations": payload.get("operations", {}),
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            return

    @staticmethod
    def _as_non_negative_int(value: Any) -> int:
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return 0

    def _read_operation_unsupported_entry(self, operation_label: str) -> dict[str, Any]:
        payload = self._read_unsupported_tracker()
        operations = payload.get("operations", {})
        if not isinstance(operations, dict):
            return {}
        entry = operations.get(self._unsupported_operation_key(operation_label))
        if isinstance(entry, dict):
            return entry
        return {}

    def _clear_operation_unsupported_entry(self, operation_label: str) -> None:
        payload = self._read_unsupported_tracker()
        operations = payload.get("operations", {})
        if not isinstance(operations, dict):
            return

        key = self._unsupported_operation_key(operation_label)
        entry = operations.get(key)
        if not isinstance(entry, dict):
            return

        entry["unsupportedConsecutiveCount"] = 0
        entry["postReleaseDeferred"] = False
        entry["lastUnsupportedSignal"] = None
        entry["updatedAt"] = (
            datetime.now(tz=timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
        operations[key] = entry
        payload["operations"] = operations
        self._write_unsupported_tracker(payload)

    def _record_unsupported_signal(
        self,
        operation_label: str,
        *,
        signal_code: str,
    ) -> dict[str, Any]:
        payload = self._read_unsupported_tracker()
        operations = payload.get("operations", {})
        if not isinstance(operations, dict):
            operations = {}

        key = self._unsupported_operation_key(operation_label)
        current_entry = operations.get(key)
        entry = dict(current_entry) if isinstance(current_entry, dict) else {}

        threshold = self._unsupported_threshold()
        consecutive = self._as_non_negative_int(
            entry.get("unsupportedConsecutiveCount")
        )
        consecutive += 1
        deferred = bool(entry.get("postReleaseDeferred")) or consecutive >= threshold

        entry.update(
            {
                "unsupportedConsecutiveCount": consecutive,
                "unsupportedThreshold": threshold,
                "lastUnsupportedSignal": signal_code,
                "postReleaseDeferred": deferred,
                "updatedAt": datetime.now(tz=timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
            }
        )

        operations[key] = entry
        payload["operations"] = operations
        self._write_unsupported_tracker(payload)
        return entry

    def _deferred_suffix(self, entry: dict[str, Any]) -> str:
        consecutive = self._as_non_negative_int(
            entry.get("unsupportedConsecutiveCount")
        )
        threshold = max(
            1,
            self._as_non_negative_int(
                entry.get("unsupportedThreshold") or self._unsupported_threshold()
            ),
        )
        return (
            " This operation has been post-release deferred after "
            f"{consecutive} consecutive unsupported signals (threshold {threshold}). "
            "Capability-gated isolation is active, continue unrelated features."
        )

    def _guard_deferred_operation(
        self,
        *,
        operation_label: str,
        signal_code: str,
        message: str,
    ) -> None:
        if self._force_unsupported_recheck_enabled():
            return

        entry = self._read_operation_unsupported_entry(operation_label)
        if not bool(entry.get("postReleaseDeferred")):
            return

        exit_signal = signal_code
        last_signal = entry.get("lastUnsupportedSignal")
        if isinstance(last_signal, str) and last_signal.strip():
            exit_signal = last_signal.strip()

        utils.error_exit(exit_signal, f"{message}{self._deferred_suffix(entry)}")

    def _error_exit_unsupported_signal(
        self,
        *,
        operation_label: str,
        signal_code: str,
        message: str,
    ) -> None:
        entry = self._record_unsupported_signal(
            operation_label,
            signal_code=signal_code,
        )

        if bool(entry.get("postReleaseDeferred")):
            utils.error_exit(signal_code, f"{message}{self._deferred_suffix(entry)}")

        utils.error_exit(signal_code, message)

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
        self._guard_deferred_operation(
            operation_label=operation_label,
            signal_code="not_supported",
            message=not_supported_message,
        )

        last_error: tuple[int, str, str, str] | None = None
        preferred_error: tuple[int, str, str, str] | None = None
        saw_scope_invalid = False
        saw_not_supported = False
        saw_inactive_appaccount = False

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
                self._clear_operation_unsupported_entry(operation_label)
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
                or "inactive_appaccount_user" in lowered
                or error_code
                in {
                    "inactive_appaccount_user",
                    "operation_not_allowed",
                    "not_supported",
                    "unsupported",
                }
                or error_code in {"request_method_invalid", "extra_param_found"}
            ):
                if (
                    "inactive_appaccount_user" in lowered
                    or error_code == "inactive_appaccount_user"
                ):
                    saw_inactive_appaccount = True
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
            self._error_exit_unsupported_signal(
                operation_label=operation_label,
                signal_code=(
                    "inactive_appaccount_user"
                    if saw_inactive_appaccount
                    else "not_supported"
                ),
                message=not_supported_message,
            )

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
        self._guard_deferred_operation(
            operation_label=operation_label,
            signal_code="not_supported",
            message=not_supported_message,
        )

        last_error: tuple[int, str, str] | None = None
        saw_scope_invalid = False
        saw_not_supported = False
        saw_inactive_appaccount = False

        for path, params in candidates:
            resp = httpx.get(
                f"{self.base_url}{path}",
                headers=self._headers,
                params=params or {},
                timeout=httpx.Timeout(30.0),
            )
            if resp.is_success:
                payload = resp.json()
                self._clear_operation_unsupported_entry(operation_label)
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
                or "inactive_appaccount_user" in lowered
                or error_code
                in {
                    "inactive_appaccount_user",
                    "operation_not_allowed",
                    "not_supported",
                    "unsupported",
                    "request_method_invalid",
                    "extra_param_found",
                }
            ):
                if (
                    "inactive_appaccount_user" in lowered
                    or error_code == "inactive_appaccount_user"
                ):
                    saw_inactive_appaccount = True
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
            self._error_exit_unsupported_signal(
                operation_label=operation_label,
                signal_code=(
                    "inactive_appaccount_user"
                    if saw_inactive_appaccount
                    else "not_supported"
                ),
                message=not_supported_message,
            )

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

    @staticmethod
    def _extract_watch_intake(watch_payload: dict[str, Any]) -> dict[str, Any]:
        intake = watch_payload.get("watchIntake")
        if isinstance(intake, dict):
            return intake

        snake_intake = watch_payload.get("watch_intake")
        if isinstance(snake_intake, dict):
            return snake_intake

        kebab_intake = watch_payload.get("watch-intake")
        if isinstance(kebab_intake, dict):
            return kebab_intake

        return {}

    @staticmethod
    def _coerce_bool_flag(value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"1", "true", "yes", "y", "on"}:
                return True
            if lowered in {"0", "false", "no", "n", "off"}:
                return False
        return None

    @staticmethod
    def _normalize_alias_key(key: str) -> str:
        return "".join(ch for ch in key.lower() if ch.isalnum())

    @classmethod
    def _collect_alias_values(
        cls,
        payload: dict[str, Any],
        ordered_normalized_keys: tuple[str, ...],
    ) -> list[Any]:
        if not isinstance(payload, dict):
            return []

        buckets: dict[str, list[Any]] = {
            normalized_key: [] for normalized_key in ordered_normalized_keys
        }
        for key, value in payload.items():
            if not isinstance(key, str):
                continue
            normalized_key = cls._normalize_alias_key(key)
            if normalized_key in buckets:
                buckets[normalized_key].append(value)

        values: list[Any] = []
        for normalized_key in ordered_normalized_keys:
            values.extend(buckets[normalized_key])
        return values

    @classmethod
    def _consume_contract_requires_read_ack(
        cls,
        consume: dict[str, Any],
    ) -> bool | None:
        required_candidates = cls._collect_alias_values(
            consume,
            ("ackrequired",),
        )
        for required_raw in required_candidates:
            required_flag = cls._coerce_bool_flag(required_raw)
            if required_flag is not None:
                return required_flag

        ack_action_candidates = cls._collect_alias_values(
            consume,
            ("ackaction", "ackactionid", "actionid", "defaultactionid"),
        )
        for candidate in ack_action_candidates:
            value = str(candidate or "").strip().lower()
            if value:
                return value == "read-ack-latest"

        return None

    @classmethod
    def _watch_consume_requires_read_ack(cls, watch_payload: dict[str, Any]) -> bool:
        intake = cls._extract_watch_intake(watch_payload)

        consume: dict[str, Any] | None = None
        if isinstance(intake, dict):
            consume = intake.get("consume")
            if not isinstance(consume, dict):
                consume = intake.get("consumePolicy")
            if not isinstance(consume, dict):
                consume = intake.get("consume_policy")
            if not isinstance(consume, dict):
                consume = intake.get("consume-policy")
            if not isinstance(consume, dict):
                for key, candidate in intake.items():
                    if not isinstance(key, str) or not isinstance(candidate, dict):
                        continue
                    normalized_key = cls._normalize_alias_key(key)
                    if normalized_key in {"consume", "consumepolicy"}:
                        consume = candidate
                        break

        if isinstance(consume, dict):
            read_ack_required = cls._consume_contract_requires_read_ack(consume)
            if read_ack_required is not None:
                return read_ack_required

        operator_workflow = cls._extract_operator_workflow(watch_payload)
        if not isinstance(operator_workflow, dict):
            return False

        internal_loop = operator_workflow.get("internalLoop")
        if isinstance(internal_loop, dict):
            internal_consume = internal_loop.get("consumePolicy")
            if isinstance(internal_consume, dict):
                read_ack_required = cls._consume_contract_requires_read_ack(
                    internal_consume
                )
                if read_ack_required is not None:
                    return read_ack_required

            internal_hint = internal_loop.get("actionHint")
            if isinstance(internal_hint, dict):
                read_ack_action = str(internal_hint.get("readAckAction") or "")
                read_ack_action_value = read_ack_action.strip().lower()
                if read_ack_action_value:
                    return read_ack_action_value == "read-ack-latest"

        external_escalation = operator_workflow.get("externalEscalation")
        if isinstance(external_escalation, dict):
            external_consume = external_escalation.get("consumePolicy")
            if isinstance(external_consume, dict):
                read_ack_required = cls._consume_contract_requires_read_ack(
                    external_consume
                )
                if read_ack_required is not None:
                    return read_ack_required

            external_hint = external_escalation.get("actionHint")
            if isinstance(external_hint, dict):
                external_hint_actions = cls._collect_alias_values(
                    external_hint,
                    ("readackaction", "watchactaction"),
                )
                for action_raw in external_hint_actions:
                    action_value = str(action_raw or "").strip().lower()
                    if action_value:
                        return action_value == "read-ack-latest"

        return False

    @staticmethod
    def _extract_first_dict_alias_with_source(
        payload: dict[str, Any],
        alias_keys: tuple[str, ...],
    ) -> tuple[dict[str, Any], str]:
        for alias_key in alias_keys:
            value = payload.get(alias_key)
            if isinstance(value, dict):
                return value, alias_key
        return {}, ""

    @staticmethod
    def _select_existing_alias_key(
        payload: dict[str, Any],
        alias_keys: tuple[str, ...],
    ) -> str:
        for alias_key in alias_keys:
            if alias_key in payload:
                return alias_key
        return alias_keys[0] if alias_keys else ""

    @staticmethod
    def _extract_operator_workflow_with_source(
        watch_payload: dict[str, Any],
    ) -> tuple[dict[str, Any], str]:
        return ZohoCliqClient._extract_first_dict_alias_with_source(
            watch_payload,
            ("operatorWorkflow", "operator_workflow", "operator-workflow"),
        )

    @staticmethod
    def _normalize_operator_workflow_package_version(value: Any) -> str:
        if value is None or isinstance(value, bool):
            return ""

        package_version = str(value).strip()
        if not package_version:
            return ""

        def _normalize_whole_number_version_candidate(candidate: str) -> str:
            normalized_candidate = candidate.strip()
            if normalized_candidate.startswith("+"):
                normalized_candidate = normalized_candidate[1:].strip()
            if not normalized_candidate:
                return ""

            if re.fullmatch(r"\d+\.0+", normalized_candidate):
                return str(int(normalized_candidate.split(".", 1)[0]))
            if normalized_candidate.isdigit():
                return str(int(normalized_candidate))
            if re.fullmatch(r"\d+(?:\.0+)?[eE][+-]?\d+", normalized_candidate):
                try:
                    numeric_value = float(normalized_candidate)
                except ValueError:
                    return ""
                if numeric_value.is_integer():
                    return str(int(numeric_value))
            return ""

        if package_version.startswith(("V", "v")):
            normalized_suffix = package_version[1:].strip()
            normalized_numeric_suffix = _normalize_whole_number_version_candidate(
                normalized_suffix
            )
            if normalized_numeric_suffix:
                normalized_suffix = normalized_numeric_suffix
            return f"v{normalized_suffix}" if normalized_suffix else ""

        normalized_numeric_version = _normalize_whole_number_version_candidate(
            package_version
        )
        if normalized_numeric_version:
            return f"v{normalized_numeric_version}"

        return package_version

    @classmethod
    def _extract_operator_workflow(
        cls, watch_payload: dict[str, Any]
    ) -> dict[str, Any]:
        workflow, _source_root = cls._extract_operator_workflow_with_source(
            watch_payload
        )
        if not isinstance(workflow, dict):
            return {}

        normalized_workflow = dict(workflow)
        package_id = str(normalized_workflow.get("packageId") or "").strip().lower()
        package_version = cls._normalize_operator_workflow_package_version(
            normalized_workflow.get("packageVersion")
        )
        package_contract_id = str(
            normalized_workflow.get("packageContractId") or ""
        ).strip()
        package_scope = str(normalized_workflow.get("packageScope") or "").strip()

        cliq_195_contract_prefix = "cliq-195-operator-workflow-"
        contract_lower = package_contract_id.lower()
        if not package_id and contract_lower.startswith(cliq_195_contract_prefix):
            package_id = "cliq-195"
            normalized_workflow["packageId"] = package_id
            if not package_version:
                derived_version = package_contract_id[
                    len(cliq_195_contract_prefix) :
                ].strip()
                if derived_version:
                    package_version = cls._normalize_operator_workflow_package_version(
                        derived_version
                    )
                    normalized_workflow["packageVersion"] = package_version

        if package_id == "cliq-195":
            normalized_workflow["packageId"] = package_id
            if not package_version:
                derived_version = ""
                if contract_lower.startswith(cliq_195_contract_prefix):
                    derived_version = package_contract_id[
                        len(cliq_195_contract_prefix) :
                    ].strip()
                package_version = (
                    cls._normalize_operator_workflow_package_version(derived_version)
                    or "v1"
                )
                normalized_workflow["packageVersion"] = package_version
            else:
                normalized_workflow["packageVersion"] = package_version

            canonical_contract_id = f"{package_id}-operator-workflow-{package_version}"
            if not package_contract_id:
                normalized_workflow["packageContractId"] = canonical_contract_id
            elif package_contract_id != canonical_contract_id:
                normalized_workflow["packageContractId"] = canonical_contract_id
            else:
                normalized_workflow["packageContractId"] = package_contract_id

            if not package_scope:
                normalized_workflow["packageScope"] = "operator-workflows"
            elif package_scope != "operator-workflows":
                normalized_workflow["packageScope"] = "operator-workflows"
            else:
                normalized_workflow["packageScope"] = package_scope

        return normalized_workflow

    @staticmethod
    def _extract_handoff_source_path(
        field_sources: dict[str, dict[str, Any]],
    ) -> str:
        for key in ("target", "to", "subject", "body"):
            source = field_sources.get(key)
            if not isinstance(source, dict):
                continue
            source_path = str(source.get("sourcePath") or "")
            if not source_path:
                continue
            for marker in ZohoCliqClient._HANDOFF_SOURCE_PATH_MARKERS:
                marker_index = source_path.find(marker)
                if marker_index >= 0:
                    handoff_root = marker.rsplit(".", 1)[0]
                    return source_path[: marker_index + len(handoff_root)]
        return ""

    @classmethod
    def _build_nested_handoff_field_sources(
        cls,
        *,
        source: str,
        source_root: str,
        payload: dict[str, Any],
        field_alias_keys: dict[str, tuple[str, ...]],
    ) -> dict[str, dict[str, Any]]:
        return {
            key: cls._build_escalation_envelope_field_source_metadata(
                source=source,
                source_path=(
                    f"{source_root}.{cls._select_existing_alias_key(payload, alias_keys)}"
                ),
                from_top_level_alias=False,
                from_nested_fallback=True,
            )
            for key, alias_keys in field_alias_keys.items()
        }

    @staticmethod
    def _build_external_handoff_envelope_defaults(
        payload_template: dict[str, Any],
    ) -> dict[str, Any]:
        target = payload_template.get("target")
        to_value = (
            payload_template.get("recipient")
            if "recipient" in payload_template
            else payload_template.get("to")
        )
        subject_value = (
            payload_template.get("summary")
            if "summary" in payload_template
            else payload_template.get("subject")
        )
        body_value = (
            payload_template.get("reason")
            if "reason" in payload_template
            else payload_template.get("body")
        )
        return {
            "target": dict(target) if isinstance(target, dict) else {},
            "to": str(to_value or ""),
            "subject": str(subject_value or ""),
            "body": str(body_value or ""),
        }

    @staticmethod
    def _normalize_external_handoff_envelope_defaults(
        envelope: dict[str, Any],
    ) -> dict[str, Any]:
        target = envelope.get("target")
        to_value = envelope.get("to") if "to" in envelope else envelope.get("recipient")
        subject_value = (
            envelope.get("subject")
            if "subject" in envelope
            else envelope.get("summary")
        )
        body_value = (
            envelope.get("body") if "body" in envelope else envelope.get("reason")
        )
        return {
            "target": dict(target) if isinstance(target, dict) else {},
            "to": str(to_value or ""),
            "subject": str(subject_value or ""),
            "body": str(body_value or ""),
        }

    @classmethod
    def _extract_external_handoff_envelope_defaults(
        cls,
        watch_payload: dict[str, Any],
    ) -> dict[str, Any]:
        envelope, _metadata = (
            cls._extract_external_handoff_envelope_defaults_with_metadata(watch_payload)
        )
        return envelope

    @staticmethod
    def _build_escalation_envelope_field_source_metadata(
        *,
        source: str,
        source_path: str,
        from_top_level_alias: bool,
        from_nested_fallback: bool,
    ) -> dict[str, Any]:
        return {
            "source": source,
            "sourcePath": source_path,
            "fromTopLevelAlias": from_top_level_alias,
            "fromNestedFallback": from_nested_fallback,
            "usedFallback": from_nested_fallback,
        }

    @classmethod
    def _extract_external_handoff_envelope_defaults_with_metadata(
        cls,
        watch_payload: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
        workflow, workflow_source_root = cls._extract_operator_workflow_with_source(
            watch_payload
        )

        if not workflow_source_root:
            return {}, {}

        escalation, escalation_key = cls._extract_first_dict_alias_with_source(
            workflow,
            ("externalEscalation", "external_escalation", "external-escalation"),
        )
        if not escalation_key:
            return {}, {}
        escalation_source_root = f"{workflow_source_root}.{escalation_key}"

        handoff, handoff_key = cls._extract_first_dict_alias_with_source(
            escalation,
            ("handoff", "hand_off", "hand-off"),
        )
        if not handoff_key:
            return {}, {}

        envelope_defaults, envelope_defaults_key = (
            cls._extract_first_dict_alias_with_source(
                handoff,
                ("envelopeDefaults", "envelope_defaults", "envelope-defaults"),
            )
        )

        if envelope_defaults_key:
            source_root = (
                f"{escalation_source_root}.{handoff_key}.{envelope_defaults_key}"
            )
            envelope_field_keys: dict[str, tuple[str, ...]] = {
                "target": ("target",),
                "to": ("to", "recipient"),
                "subject": ("subject", "summary"),
                "body": ("body", "reason"),
            }
            field_sources = cls._build_nested_handoff_field_sources(
                source="nested-envelope-defaults",
                source_root=source_root,
                payload=envelope_defaults,
                field_alias_keys=envelope_field_keys,
            )

            return (
                cls._normalize_external_handoff_envelope_defaults(envelope_defaults),
                field_sources,
            )

        payload_template, payload_template_key = (
            cls._extract_first_dict_alias_with_source(
                handoff,
                ("payloadTemplate", "payload_template", "payload-template"),
            )
        )

        if payload_template_key:
            source_root = (
                f"{escalation_source_root}.{handoff_key}.{payload_template_key}"
            )
            payload_template_field_keys: dict[str, tuple[str, ...]] = {
                "target": ("target",),
                "to": ("recipient", "to"),
                "subject": ("summary", "subject"),
                "body": ("reason", "body"),
            }
            field_sources = cls._build_nested_handoff_field_sources(
                source="nested-payload-template",
                source_root=source_root,
                payload=payload_template,
                field_alias_keys=payload_template_field_keys,
            )

            return (
                cls._build_external_handoff_envelope_defaults(payload_template),
                field_sources,
            )
        return {}, {}

    @classmethod
    def _resolve_escalation_envelope_alias_with_metadata(
        cls,
        watch_payload: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        alias_payload, alias_source_root = cls._extract_first_dict_alias_with_source(
            watch_payload,
            ("escalationEnvelope", "escalation_envelope", "escalation-envelope"),
        )
        alias: dict[str, Any] | None
        if alias_source_root:
            alias = alias_payload
        else:
            alias = None
        fallback, fallback_sources = (
            cls._extract_external_handoff_envelope_defaults_with_metadata(watch_payload)
        )
        fields = ("target", "to", "subject", "body")

        if not isinstance(alias, dict):
            if not fallback:
                return {}, {
                    "source": "",
                    "sourcePath": "",
                    "fromTopLevelAlias": False,
                    "fromNestedFallback": False,
                    "usedFieldFallback": False,
                    "fieldSources": {},
                }
            fallback_source_path = cls._extract_handoff_source_path(fallback_sources)
            return {key: fallback[key] for key in fields}, {
                "source": "nested-fallback",
                "sourcePath": fallback_source_path,
                "fromTopLevelAlias": False,
                "fromNestedFallback": True,
                "usedFieldFallback": True,
                "fieldSources": {key: fallback_sources[key] for key in fields},
            }

        normalized_alias = cls._normalize_external_handoff_envelope_defaults(alias)
        field_sources: dict[str, dict[str, Any]] = {}
        resolved: dict[str, Any] = {}
        alias_field_keys: dict[str, tuple[str, ...]] = {
            "target": ("target",),
            "to": ("to", "recipient"),
            "subject": ("subject", "summary"),
            "body": ("body", "reason"),
        }

        for key in fields:
            selected_alias_key = cls._select_existing_alias_key(
                alias,
                alias_field_keys[key],
            )
            alias_key = selected_alias_key if selected_alias_key in alias else ""

            if alias_key:
                resolved[key] = normalized_alias[key]
                field_sources[key] = (
                    cls._build_escalation_envelope_field_source_metadata(
                        source="top-level-alias",
                        source_path=f"{alias_source_root}.{alias_key}",
                        from_top_level_alias=True,
                        from_nested_fallback=False,
                    )
                )
                continue
            if key in fallback_sources:
                resolved[key] = fallback[key]
                field_sources[key] = fallback_sources[key]
                continue
            resolved[key] = normalized_alias[key]
            field_sources[key] = cls._build_escalation_envelope_field_source_metadata(
                source="implicit-empty",
                source_path="",
                from_top_level_alias=False,
                from_nested_fallback=False,
            )

        alias_count = sum(
            1 for item in field_sources.values() if item.get("fromTopLevelAlias")
        )
        fallback_count = sum(
            1 for item in field_sources.values() if item.get("fromNestedFallback")
        )
        implicit_count = len(field_sources) - alias_count - fallback_count

        source = "mixed"
        source_path = "mixed"
        if alias_count == len(fields):
            source = "top-level-alias"
            source_path = alias_source_root
        elif fallback_count == len(fields):
            source = "nested-fallback"
            source_path = cls._extract_handoff_source_path(field_sources)
        elif implicit_count == len(fields):
            source = "implicit-empty"
            source_path = ""

        return resolved, {
            "source": source,
            "sourcePath": source_path,
            "fromTopLevelAlias": alias_count > 0,
            "fromNestedFallback": fallback_count > 0,
            "usedFieldFallback": fallback_count > 0,
            "fieldSources": field_sources,
        }

    @classmethod
    def extract_escalation_envelope_alias(
        cls,
        watch_payload: dict[str, Any],
    ) -> dict[str, Any]:
        envelope, _metadata = cls._resolve_escalation_envelope_alias_with_metadata(
            watch_payload
        )
        return envelope

    @classmethod
    def extract_escalation_envelope_alias_metadata(
        cls,
        watch_payload: dict[str, Any],
    ) -> dict[str, Any]:
        _envelope, metadata = cls._resolve_escalation_envelope_alias_with_metadata(
            watch_payload
        )
        return metadata

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

        internal_default_action = "reply-latest"
        external_default_action = "notify-mail"
        operator_workflow_package_id = "cliq-195"
        operator_workflow_package_version = "v1"
        operator_workflow_package_contract_id = (
            f"{operator_workflow_package_id}-operator-workflow-"
            f"{operator_workflow_package_version}"
        )

        payload_template = {
            "target": {
                "kind": "external-contact",
                "channel": "mail",
                "defaultAction": external_default_action,
            },
            "recipient": "",
            "summary": "",
            "reason": "",
        }
        envelope_hints = {
            "templateRoot": "payloadTemplate",
            "targetPath": "payloadTemplate.target",
            "fieldMap": {
                "to": "payloadTemplate.recipient",
                "subject": "payloadTemplate.summary",
                "body": "payloadTemplate.reason",
            },
        }

        escalation_envelope = cls._build_external_handoff_envelope_defaults(
            payload_template
        )
        handoff_envelope_defaults = cls._normalize_external_handoff_envelope_defaults(
            escalation_envelope
        )
        watch_consume = {
            "ackAction": "read-ack-latest",
            "ackRequired": True,
            "actionId": "watch-loop",
        }
        watch_loop_action = watch_consume["actionId"]
        watch_ack_action = watch_consume["ackAction"]
        watch_intake_consume = dict(watch_consume)
        internal_consume_policy = dict(watch_consume)
        external_consume_policy = dict(watch_consume)

        payload = {
            "sinceMessageId": since,
            "cursorFound": cursor_found,
            "latestMessageId": latest_message_id,
            "nextSinceMessageId": latest_message_id or since,
            "totalFetched": len(cleaned_messages),
            "newCount": len(normalized_messages),
            "truncated": truncated,
            "escalationEnvelope": escalation_envelope,
            "watchIntake": {
                "triggerMode": "web-notification-first",
                "pollFallback": {
                    "mode": "adaptive",
                    "transport": "api-poll",
                    "cursorField": "cursor.nextSinceMessageId",
                },
                "consume": watch_intake_consume,
            },
            "operatorWorkflow": {
                "packageId": operator_workflow_package_id,
                "packageVersion": operator_workflow_package_version,
                "packageContractId": operator_workflow_package_contract_id,
                "packageScope": "operator-workflows",
                "internalLoop": {
                    "contractId": "cliq-195-internal-loop-v1",
                    "mode": watch_loop_action,
                    "defaultAction": internal_default_action,
                    "consumePolicy": internal_consume_policy,
                    "actionHint": {
                        "watchActAction": internal_default_action,
                        "readAckAction": watch_consume["ackAction"],
                        "bridgeActionId": internal_default_action,
                    },
                },
                "externalEscalation": {
                    "contractId": "cliq-195-external-escalation-v1",
                    "mode": "human-review",
                    "defaultAction": external_default_action,
                    "consumePolicy": external_consume_policy,
                    "actionHint": {
                        "watchActAction": watch_ack_action,
                        "readAckAction": watch_ack_action,
                        "bridgeActionId": external_default_action,
                    },
                    "handoff": {
                        "contractId": "cliq-195-escalation-handoff-v1",
                        "target": "external-contact",
                        "requiredFields": ["recipient", "summary", "reason"],
                        "payloadTemplate": payload_template,
                        "envelopeHints": envelope_hints,
                        "envelopeDefaults": handoff_envelope_defaults,
                    },
                },
            },
            "messages": normalized_messages,
        }
        payload["escalationEnvelopeMetadata"] = (
            cls.extract_escalation_envelope_alias_metadata(payload)
        )

        return payload

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
        watch_intake = cls._extract_watch_intake(watch_payload)
        operator_workflow = cls._extract_operator_workflow(watch_payload)

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
        escalation_envelope = cls.extract_escalation_envelope_alias(watch_payload)
        escalation_envelope_metadata = cls.extract_escalation_envelope_alias_metadata(
            watch_payload
        )
        return {
            "action": "reply-latest",
            "chatId": resolved_chat,
            "channelId": resolved_channel,
            "escalationEnvelope": escalation_envelope,
            "escalationEnvelopeMetadata": escalation_envelope_metadata,
            "watchIntake": watch_intake,
            "operatorWorkflow": operator_workflow,
            "newCount": watch_payload.get("newCount", len(messages)),
            "targetMessageId": target_id,
            "targetSenderId": cls._extract_sender_id(target or {}),
            "targetText": cls._extract_message_text(target or {}),
            "replyText": text,
            "hasTarget": bool(target_id),
        }

    @classmethod
    def build_watch_read_ack_action(
        cls,
        watch_payload: dict[str, Any],
        *,
        chat_id: str | None = None,
        channel_id: str | None = None,
        message_id: str | None = None,
    ) -> dict[str, Any]:
        """Build a deterministic read-ack action from watch-context output."""
        payload_chat = str(watch_payload.get("chatId") or "").strip()
        payload_channel = str(watch_payload.get("channelId") or "").strip()

        resolved_chat = (chat_id or "").strip() or payload_chat
        resolved_channel = (channel_id or "").strip() or payload_channel
        watch_intake = cls._extract_watch_intake(watch_payload)
        operator_workflow = cls._extract_operator_workflow(watch_payload)

        data = watch_payload.get("messages")
        messages = (
            [item for item in data if isinstance(item, dict)]
            if isinstance(data, list)
            else []
        )

        explicit_target = (message_id or "").strip()
        target: dict[str, Any] | None = None
        if explicit_target:
            for item in reversed(messages):
                if cls._extract_message_id(item) == explicit_target:
                    target = item
                    break
        else:
            for item in reversed(messages):
                if cls._extract_message_id(item):
                    target = item
                    break

        target_id = explicit_target or cls._extract_message_id(target or {})
        escalation_envelope = cls.extract_escalation_envelope_alias(watch_payload)
        escalation_envelope_metadata = cls.extract_escalation_envelope_alias_metadata(
            watch_payload
        )
        return {
            "action": "read-ack-latest",
            "chatId": resolved_chat,
            "channelId": resolved_channel,
            "escalationEnvelope": escalation_envelope,
            "escalationEnvelopeMetadata": escalation_envelope_metadata,
            "watchIntake": watch_intake,
            "operatorWorkflow": operator_workflow,
            "newCount": watch_payload.get("newCount", len(messages)),
            "targetMessageId": target_id,
            "targetSenderId": cls._extract_sender_id(target or {}),
            "targetText": cls._extract_message_text(target or {}),
            "hasTarget": bool(target_id),
            "ackRequired": bool(target_id),
        }

    def execute_watch_read_ack_action(
        self,
        watch_payload: dict[str, Any],
        *,
        chat_id: str | None = None,
        channel_id: str | None = None,
        message_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute one deterministic watch action: read-ack the latest new message."""
        action = self.build_watch_read_ack_action(
            watch_payload,
            chat_id=chat_id,
            channel_id=channel_id,
            message_id=message_id,
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

        resp = self.read_ack_message(
            target_id,
            chat_id=resolved_chat or None,
            channel_id=resolved_channel or None,
        )
        return {
            "status": "ok",
            **action,
            "applied": True,
            "result": resp.get("data", resp),
        }

    def execute_watch_reply_action(
        self,
        watch_payload: dict[str, Any],
        *,
        text: str,
        chat_id: str | None = None,
        channel_id: str | None = None,
        auto_read_ack: bool | None = None,
    ) -> dict[str, Any]:
        """Execute one deterministic watch action: reply to the latest new message."""
        reply_text = text.strip()
        if not reply_text:
            utils.error_exit("invalid_text", "reply text cannot be empty")

        read_ack_required = (
            bool(auto_read_ack)
            if auto_read_ack is not None
            else self._watch_consume_requires_read_ack(watch_payload)
        )

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
                "readAck": {
                    "required": read_ack_required,
                    "applied": False,
                    "reason": "no_new_messages",
                    "result": {},
                },
                "result": {},
            }

        resp = self.reply_message(
            reply_text,
            message_id=target_id,
            chat_id=resolved_chat or None,
            channel_id=resolved_channel or None,
        )

        read_ack_applied = False
        read_ack_result: dict[str, Any] = {}
        if read_ack_required:
            ack_resp = self.read_ack_message(
                target_id,
                chat_id=resolved_chat or None,
                channel_id=resolved_channel or None,
            )
            read_ack_applied = True
            read_ack_result = ack_resp.get("data", ack_resp)

        return {
            "status": "ok",
            **action,
            "applied": True,
            "readAck": {
                "required": read_ack_required,
                "applied": read_ack_applied,
                "messageId": target_id if read_ack_applied else "",
                "result": read_ack_result,
            },
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
        """Fetch one message by id with endpoint fallbacks."""
        resolved_chat = self._resolve_chat_destination(
            chat_id=chat_id,
            channel_id=channel_id,
        )

        mid = message_id.strip()
        if not mid:
            utils.error_exit("invalid_message_id", "message_id cannot be empty")

        candidates: list[tuple[str, dict[str, Any] | None]] = [
            (f"/chats/{resolved_chat}/messages/{mid}", None),
            (f"/chats/{resolved_chat}/messages/{mid}/messages", None),
        ]

        target_channel = (channel_id or "").strip()
        if target_channel:
            candidates.extend(
                [
                    (f"/channels/{target_channel}/messages/{mid}", None),
                    (f"/channels/{target_channel}/messages/{mid}/messages", None),
                ]
            )

        return self._get_with_candidates_and_not_supported(
            candidates,
            scope_hint="ZohoCliq.Messages.READ",
            operation_label="message-get",
            not_supported_message="Cliq message retrieval endpoints are not available for this token/network endpoint. Run `zoho cliq capabilities --channel-id <id> --message-id <mid>` to confirm message-get operations for the target conversation.",
        )

    def get_message_reactions(
        self,
        message_id: str,
        *,
        chat_id: str | None = None,
        channel_id: str | None = None,
    ) -> dict:
        """Get reactions for one message in a chat/channel."""
        resolved_chat = self._resolve_chat_destination(
            chat_id=chat_id,
            channel_id=channel_id,
        )

        mid = message_id.strip()
        if not mid:
            utils.error_exit("invalid_message_id", "message_id cannot be empty")

        candidates: list[tuple[str, dict[str, Any] | None]] = [
            (f"/chats/{resolved_chat}/messages/{mid}/reactions", None),
            (f"/chats/{resolved_chat}/messages/{mid}/messages/reactions", None),
            (f"/chats/{resolved_chat}/messageactions", {"message_id": mid}),
            (f"/chats/{resolved_chat}/messageactions/{mid}", None),
        ]

        if channel_id:
            candidates.extend(
                [
                    (f"/channels/{channel_id}/messages/{mid}/reactions", None),
                    (
                        f"/channels/{channel_id}/messages/{mid}/messages/reactions",
                        None,
                    ),
                    (
                        f"/channels/{channel_id}/messageactions",
                        {"message_id": mid},
                    ),
                    (f"/channels/{channel_id}/messageactions/{mid}", None),
                ]
            )

        return self._get_with_candidates_and_not_supported(
            candidates,
            scope_hint="ZohoCliq.Messages.READ",
            operation_label="message-reactions-get",
            not_supported_message="Cliq message-reaction read endpoints are not available for this token/network endpoint. Run `zoho cliq capabilities --channel-id <id>` and confirm message-reaction operations for the target conversation.",
        )

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
        not_supported_message = (
            "Cliq message search is not available for this token/network endpoint. "
            "Run `zoho cliq capabilities --channel-id <id>` to confirm available operations."
        )
        self._guard_deferred_operation(
            operation_label="search-messages",
            signal_code="not_supported",
            message=not_supported_message,
        )

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
                        self._clear_operation_unsupported_entry("search-messages")
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
                        or "inactive_appaccount_user" in lowered
                        or error_code in retryable_error_codes
                        or error_code
                        in {
                            "inactive_appaccount_user",
                            "operation_not_allowed",
                            "not_supported",
                            "unsupported",
                        }
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
            self._error_exit_unsupported_signal(
                operation_label="search-messages",
                signal_code="not_supported",
                message=not_supported_message,
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
        not_supported_message = (
            "Cliq file/attachment retrieval is not available for this token/network endpoint. "
            "Run `zoho cliq capabilities --channel-id <id>` to confirm available operations."
        )
        self._guard_deferred_operation(
            operation_label="message-files",
            signal_code="not_supported",
            message=not_supported_message,
        )

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
                self._clear_operation_unsupported_entry("message-files")
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
                    self._clear_operation_unsupported_entry("message-files")
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
                or "inactive_appaccount_user" in lowered
                or error_code
                in {
                    "inactive_appaccount_user",
                    "operation_not_allowed",
                    "not_supported",
                    "unsupported",
                }
            ):
                saw_not_supported = True
                last_error = (resp.status_code, path, body)
                continue

            utils.error_exit(
                "api_error",
                f"HTTP {resp.status_code} GET {path}: {body}",
            )

        if first_no_attachment_path is not None:
            self._clear_operation_unsupported_entry("message-files")
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
            self._error_exit_unsupported_signal(
                operation_label="message-files",
                signal_code="not_supported",
                message=not_supported_message,
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

    def read_ack_message(
        self,
        message_id: str,
        *,
        chat_id: str | None = None,
        channel_id: str | None = None,
    ) -> dict:
        """Mark a message as read/acknowledged using endpoint/method fallbacks."""
        resolved_chat = self._resolve_chat_destination(
            chat_id=chat_id,
            channel_id=channel_id,
        )
        mid = message_id.strip()
        if not mid:
            utils.error_exit("invalid_message_id", "message_id cannot be empty")

        candidates: list[tuple[str, str, dict[str, Any] | None]] = [
            ("POST", f"/chats/{resolved_chat}/messages/{mid}/read", {}),
            ("POST", f"/chats/{resolved_chat}/messages/{mid}/ack", {}),
            ("PUT", f"/chats/{resolved_chat}/messages/{mid}/read", {}),
            ("POST", f"/chats/{resolved_chat}/messages/read", {"message_id": mid}),
            ("POST", f"/chats/{resolved_chat}/messages/read", {"messageId": mid}),
        ]

        if channel_id:
            target_channel = channel_id.strip()
            if target_channel:
                candidates.extend(
                    [
                        ("POST", f"/channels/{target_channel}/messages/{mid}/read", {}),
                        ("POST", f"/channels/{target_channel}/messages/{mid}/ack", {}),
                    ]
                )

        return self._request_with_candidates_and_not_supported(
            candidates,
            scope_hint="ZohoCliq.Messages.READ",
            operation_label="message-read-ack",
            not_supported_message="Cliq read-ack endpoints are not available for this token/network endpoint. Run `zoho cliq capabilities --channel-id <id>` and confirm read-ack operations for the target conversation.",
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

    def _remove_reaction_best_effort(
        self,
        message_id: str,
        emoji: str,
        *,
        chat_id: str | None = None,
        channel_id: str | None = None,
    ) -> dict[str, Any]:
        """Try to remove one reaction, but do not hard-fail when absent."""
        resolved_chat = self._resolve_chat_destination(
            chat_id=chat_id, channel_id=channel_id
        )
        mid = message_id.strip()
        if not mid:
            utils.error_exit("invalid_message_id", "message_id cannot be empty")
        icon = emoji.strip()
        if not icon:
            utils.error_exit("invalid_emoji", "emoji cannot be empty")

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

        retryable_error_codes = {
            "param_missing",
            "invalid_data",
            "operation_failed",
            "operation_not_allowed",
            "extra_key_found",
            "request_method_invalid",
            "extra_param_found",
        }
        last_error: tuple[int, str, str, str] | None = None
        saw_scope_invalid = False

        for method, path, payload in candidates:
            resp = httpx.request(
                method,
                f"{self.base_url}{path}",
                headers=self._headers,
                json=payload,
                timeout=httpx.Timeout(30.0),
            )
            if resp.is_success:
                return {
                    "removed": True,
                    "result": self._decode_success_response(resp),
                    "method": method,
                    "path": path,
                }

            body = resp.text or ""
            lowered = body.lower()
            scope_invalid = "oauthtoken_scope_invalid" in lowered
            if scope_invalid:
                saw_scope_invalid = True

            error_code = ""
            try:
                parsed = resp.json()
                if isinstance(parsed, dict):
                    error_code = str(
                        parsed.get("code") or parsed.get("error") or ""
                    ).lower()
            except ValueError:
                pass

            last_error = (resp.status_code, method, path, body)
            if (
                resp.status_code in (404, 405)
                or "request_url_invalid" in lowered
                or "not found" in lowered
                or error_code in retryable_error_codes
            ):
                continue

            return {
                "removed": False,
                "method": method,
                "path": path,
                "statusCode": resp.status_code,
                "error": body,
            }

        if saw_scope_invalid:
            utils.error_exit(
                "oauth_scope_invalid",
                "Cliq token is missing required scope for reaction cleanup. Re-run `zoho login --with-cliq --scope ZohoCliq.messageactions.CREATE` and retry.",
            )

        if last_error is None:
            return {"removed": False}

        status, method, path, body = last_error
        return {
            "removed": False,
            "method": method,
            "path": path,
            "statusCode": status,
            "error": body,
        }

    def set_message_status_reaction(
        self,
        message_id: str,
        *,
        emoji: str,
        tracked_status_emojis: list[str] | None = None,
        chat_id: str | None = None,
        channel_id: str | None = None,
    ) -> dict[str, Any]:
        """Replace any known status reaction with the requested status emoji."""
        tracked: list[str] = []
        for icon in tracked_status_emojis or []:
            normalized = str(icon or "").strip()
            if normalized and normalized not in tracked:
                tracked.append(normalized)

        target_emoji = emoji.strip()
        if not target_emoji:
            utils.error_exit("invalid_emoji", "emoji cannot be empty")

        removed: list[str] = []
        remove_failures: list[dict[str, Any]] = []
        for icon in tracked:
            if icon == target_emoji:
                continue
            outcome = self._remove_reaction_best_effort(
                message_id,
                icon,
                chat_id=chat_id,
                channel_id=channel_id,
            )
            if outcome.get("removed"):
                removed.append(icon)
            elif outcome.get("error"):
                remove_failures.append(
                    {
                        "emoji": icon,
                        "statusCode": outcome.get("statusCode", 0),
                        "method": outcome.get("method", ""),
                        "path": outcome.get("path", ""),
                        "error": outcome.get("error", ""),
                    }
                )

        applied = self.react_message(
            message_id,
            target_emoji,
            remove=False,
            chat_id=chat_id,
            channel_id=channel_id,
        )

        return {
            "emoji": target_emoji,
            "removed": removed,
            "removeFailures": remove_failures,
            "result": applied.get("data", applied),
        }

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
            {"text": body, "thread_message_id": parent_message_id},
            {"text": body, "threadMessageId": parent_message_id},
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
                        (
                            "POST",
                            f"/channels/{channel_id}/message",
                            payload,
                        ),
                        (
                            "POST",
                            f"/channels/{channel_id}/messages",
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
                    (
                        "POST",
                        f"/chats/{target_thread}/message",
                        payload,
                    ),
                    (
                        "POST",
                        f"/chats/{target_thread}/messages",
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

    def leave_chat(
        self,
        *,
        chat_id: str | None = None,
        channel_id: str | None = None,
    ) -> dict:
        """Leave one chat/channel conversation."""
        resolved_chat = self._resolve_chat_destination(
            chat_id=chat_id,
            channel_id=channel_id,
        )

        candidates: list[tuple[str, str, dict[str, Any] | None]] = [
            ("DELETE", f"/chats/{resolved_chat}/members/me", None),
            ("POST", f"/chats/{resolved_chat}/leave", {}),
            ("POST", f"/chats/{resolved_chat}/members/leave", {}),
            ("DELETE", f"/chats/{resolved_chat}/member/me", None),
            ("POST", f"/chats/{resolved_chat}/exit", {}),
        ]

        if channel_id:
            candidates.extend(
                [
                    ("DELETE", f"/channels/{channel_id}/members/me", None),
                    ("POST", f"/channels/{channel_id}/leave", {}),
                    ("POST", f"/channels/{channel_id}/members/leave", {}),
                ]
            )

        return self._request_with_candidates_and_not_supported(
            candidates,
            scope_hint="ZohoCliq.Channels.UPDATE",
            operation_label="leave",
            not_supported_message="Cliq leave endpoints are not available for this token/network endpoint. Run `zoho cliq capabilities --channel-id <id>` and confirm chat control operations for the target conversation.",
        )

    def set_chat_mute(
        self,
        *,
        chat_id: str | None = None,
        channel_id: str | None = None,
        muted: bool,
    ) -> dict:
        """Mute or unmute one chat/channel conversation."""
        resolved_chat = self._resolve_chat_destination(
            chat_id=chat_id,
            channel_id=channel_id,
        )

        state = "mute" if muted else "unmute"
        body = {"muted": muted}
        candidates: list[tuple[str, str, dict[str, Any] | None]] = [
            ("POST", f"/chats/{resolved_chat}/{state}", {}),
            ("POST", f"/chats/{resolved_chat}/notifications/{state}", {}),
            ("POST", f"/chats/{resolved_chat}/members/me/{state}", {}),
            ("PATCH", f"/chats/{resolved_chat}/notifications", body),
            ("PUT", f"/chats/{resolved_chat}/notifications", body),
        ]

        if channel_id:
            candidates.extend(
                [
                    ("POST", f"/channels/{channel_id}/{state}", {}),
                    ("POST", f"/channels/{channel_id}/notifications/{state}", {}),
                    ("PATCH", f"/channels/{channel_id}/notifications", body),
                    ("PUT", f"/channels/{channel_id}/notifications", body),
                ]
            )

        return self._request_with_candidates_and_not_supported(
            candidates,
            scope_hint="ZohoCliq.Channels.UPDATE",
            operation_label=state,
            not_supported_message=f"Cliq {state} endpoints are not available for this token/network endpoint. Run `zoho cliq capabilities --channel-id <id>` and confirm chat control operations for the target conversation.",
        )

    def set_chat_pin(
        self,
        *,
        chat_id: str | None = None,
        channel_id: str | None = None,
        pinned: bool,
    ) -> dict:
        """Pin or unpin one chat/channel conversation."""
        resolved_chat = self._resolve_chat_destination(
            chat_id=chat_id,
            channel_id=channel_id,
        )

        state = "pin" if pinned else "unpin"
        body = {"pinned": pinned}
        candidates: list[tuple[str, str, dict[str, Any] | None]] = [
            ("POST", f"/chats/{resolved_chat}/{state}", {}),
            ("POST", f"/chats/{resolved_chat}/messages/{state}", {}),
            ("POST", f"/chats/{resolved_chat}/settings/{state}", {}),
            ("PATCH", f"/chats/{resolved_chat}/settings", body),
            ("PUT", f"/chats/{resolved_chat}/settings", body),
        ]

        if channel_id:
            candidates.extend(
                [
                    ("POST", f"/channels/{channel_id}/{state}", {}),
                    ("POST", f"/channels/{channel_id}/messages/{state}", {}),
                    ("PATCH", f"/channels/{channel_id}/settings", body),
                    ("PUT", f"/channels/{channel_id}/settings", body),
                ]
            )

        return self._request_with_candidates_and_not_supported(
            candidates,
            scope_hint="ZohoCliq.Channels.UPDATE",
            operation_label=state,
            not_supported_message=f"Cliq {state} endpoints are not available for this token/network endpoint. Run `zoho cliq capabilities --channel-id <id>` and confirm chat control operations for the target conversation.",
        )

    def list_pinned_messages(
        self,
        *,
        chat_id: str | None = None,
        channel_id: str | None = None,
        limit: int = 50,
    ) -> dict:
        """List pinned messages for one chat/channel conversation."""
        resolved_chat = self._resolve_chat_destination(
            chat_id=chat_id,
            channel_id=channel_id,
        )
        limit_value = max(1, limit)

        candidates: list[tuple[str, dict[str, Any] | None]] = [
            (f"/chats/{resolved_chat}/pinned", {"limit": limit_value}),
            (f"/chats/{resolved_chat}/messages/pinned", {"limit": limit_value}),
            (f"/chats/{resolved_chat}/pinned/messages", {"limit": limit_value}),
            (f"/chats/{resolved_chat}/pins", {"limit": limit_value}),
        ]

        if channel_id:
            candidates.extend(
                [
                    (f"/channels/{channel_id}/pinned", {"limit": limit_value}),
                    (
                        f"/channels/{channel_id}/messages/pinned",
                        {"limit": limit_value},
                    ),
                    (
                        f"/channels/{channel_id}/pinned/messages",
                        {"limit": limit_value},
                    ),
                    (f"/channels/{channel_id}/pins", {"limit": limit_value}),
                ]
            )

        return self._get_with_candidates_and_not_supported(
            candidates,
            scope_hint="ZohoCliq.Messages.READ",
            operation_label="pinned",
            not_supported_message="Cliq pinned-message endpoints are not available for this token/network endpoint. Run `zoho cliq capabilities --channel-id <id>` and confirm chat control operations for the target conversation.",
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

    def trigger_bot_call(
        self,
        bot_id: str,
        call_name: str,
        *,
        inputs: dict[str, Any] | None = None,
    ) -> dict:
        """Trigger one named bot call/action using endpoint/payload fallbacks."""
        target_bot = bot_id.strip()
        if not target_bot:
            utils.error_exit("invalid_bot_id", "bot_id cannot be empty")

        target_call = call_name.strip()
        if not target_call:
            utils.error_exit("invalid_call_name", "call_name cannot be empty")

        payload_inputs: dict[str, Any] = {}
        if isinstance(inputs, dict):
            payload_inputs = dict(inputs)

        payloads: list[dict[str, Any]] = [
            {
                "call_name": target_call,
                "inputs": payload_inputs,
            },
            {
                "name": target_call,
                "arguments": payload_inputs,
            },
            {
                "action": target_call,
                "params": payload_inputs,
            },
        ]

        candidates: list[tuple[str, str, dict[str, Any] | None]] = []
        for payload in payloads:
            candidates.extend(
                [
                    ("POST", f"/bots/{target_bot}/calls", payload),
                    ("POST", f"/bots/{target_bot}/call", payload),
                    ("POST", f"/bots/{target_bot}/trigger", payload),
                    ("POST", f"/bots/{target_bot}/actions/{target_call}", payload),
                    ("POST", f"/bots/{target_bot}/execute", payload),
                    ("POST", f"/bot/{target_bot}/call", payload),
                ]
            )

        return self._request_with_candidates_and_not_supported(
            candidates,
            scope_hint="ZohoCliq.Webhooks.CREATE",
            operation_label="trigger-bot",
            not_supported_message="Cliq bot trigger/call endpoints are not available for this token/network endpoint. Capture one capabilities snapshot and continue with non-bot operations for this network.",
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
                f"/threads/{target_thread}/followers",
                {"limit": limit_value},
            ),
            (
                f"/chats/{resolved_chat}/threads/{target_thread}/subscribers",
                {"limit": limit_value},
            ),
            (
                f"/threads/{target_thread}/nonfollowers",
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
            (f"/threads/{target_thread}", None),
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
                    (
                        "PUT",
                        f"/threads/{target_thread}",
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
        not_supported_message = "Cliq chat listing endpoint is not available for this token/network endpoint."
        self._guard_deferred_operation(
            operation_label="chats-list",
            signal_code="not_supported",
            message=not_supported_message,
        )

        resp = httpx.get(
            f"{self.base_url}/chats",
            headers=self._headers,
            params={"limit": limit},
            timeout=httpx.Timeout(30.0),
        )
        if resp.is_success:
            self._clear_operation_unsupported_entry("chats-list")
            return resp.json()

        body = resp.text or ""
        lowered = body.lower()
        code = ""
        try:
            parsed = resp.json()
            if isinstance(parsed, dict):
                code = str(parsed.get("code") or parsed.get("error") or "").lower()
        except ValueError:
            pass

        if "oauthtoken_scope_invalid" in lowered:
            utils.error_exit(
                "oauth_scope_invalid",
                "Cliq token is missing chat-read scope. Run `zoho cliq status --check-auth` to inspect granted scopes, then re-run `zoho login --with-cliq --scope ZohoCliq.Chats.ALL` and retry.",
            )
        if (
            resp.status_code in (404, 405)
            or "request_url_invalid" in lowered
            or "inactive_appaccount_user" in lowered
            or code
            in {
                "inactive_appaccount_user",
                "operation_not_allowed",
                "not_supported",
                "unsupported",
            }
        ):
            signal = (
                "inactive_appaccount_user"
                if "inactive_appaccount_user" in lowered
                or code == "inactive_appaccount_user"
                else "not_supported"
            )
            self._error_exit_unsupported_signal(
                operation_label="chats-list",
                signal_code=signal,
                message=not_supported_message,
            )

        utils.error_exit("api_error", f"HTTP {resp.status_code} GET /chats: {body}")
        return {}

    def export_conversations(self) -> dict:
        """Export conversation descriptors via maintenance bulk-export API."""
        not_supported_message = "Cliq export conversations endpoint is not available for this token/network endpoint."
        inactive_message = (
            "Cliq maintenance export is blocked because this account is inactive for "
            "app-account export APIs. Activate the account in Cliq admin or use an "
            "active org account, then retry."
        )
        self._guard_deferred_operation(
            operation_label="export-conversations",
            signal_code="not_supported",
            message=not_supported_message,
        )

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
        saw_inactive_appaccount = False
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
                self._clear_operation_unsupported_entry("export-conversations")
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
                "inactive_appaccount_user" in lowered
                or code == "inactive_appaccount_user"
            ):
                saw_inactive_appaccount = True
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
                f"Cliq token is missing organization-chat export scope. Re-run `zoho login --with-cliq --scope {CLIQ_EXPORT_CHATS_SCOPE}` and retry.",
            )

        if saw_inactive_appaccount:
            self._error_exit_unsupported_signal(
                operation_label="export-conversations",
                signal_code="inactive_appaccount_user",
                message=inactive_message,
            )

        if saw_not_supported:
            self._error_exit_unsupported_signal(
                operation_label="export-conversations",
                signal_code="not_supported",
                message=not_supported_message,
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
        not_supported_message = "Cliq export chat-messages endpoint is not available for this token/network endpoint."
        inactive_message = (
            "Cliq maintenance export is blocked because this account is inactive for "
            "app-account export APIs. Activate the account in Cliq admin or use an "
            "active org account, then retry."
        )
        self._guard_deferred_operation(
            operation_label="export-chat-messages",
            signal_code="not_supported",
            message=not_supported_message,
        )

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
            self._clear_operation_unsupported_entry("export-chat-messages")
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
                f"Cliq token is missing organization-message export scope. Re-run `zoho login --with-cliq --scope {CLIQ_EXPORT_MESSAGES_SCOPE}` and retry.",
            )

        if "inactive_appaccount_user" in lowered or code == "inactive_appaccount_user":
            self._error_exit_unsupported_signal(
                operation_label="export-chat-messages",
                signal_code="inactive_appaccount_user",
                message=inactive_message,
            )

        if (
            resp.status_code in (404, 405)
            or "request_url_invalid" in lowered
            or code in {"operation_not_allowed", "not_supported", "unsupported"}
        ):
            self._error_exit_unsupported_signal(
                operation_label="export-chat-messages",
                signal_code="not_supported",
                message=not_supported_message,
            )

        utils.error_exit("api_error", f"HTTP {resp.status_code} GET {path}: {body}")
        return {}

    def users(self, *, limit: int = 50) -> dict:
        """List users."""
        return self._get("/users", {"limit": limit})

    def list_teams(self, *, limit: int = 50) -> dict:
        """List organization teams (cliq-190 first org-admin slice)."""
        return self._get_with_candidates_and_not_supported(
            [
                ("/teams", {"limit": limit}),
                ("/teams", None),
                ("/admin/teams", {"limit": limit}),
                ("/admin/teams", None),
            ],
            scope_hint="ZohoCliq.Teams.READ",
            operation_label="teams-list",
            not_supported_message="Cliq org-admin team listing endpoints are not available for this token/network endpoint.",
        )

    def list_departments(self, *, limit: int = 50) -> dict:
        """List organization departments (cliq-190 second org-admin slice)."""
        return self._get_with_candidates_and_not_supported(
            [
                ("/departments", {"limit": limit}),
                ("/departments", None),
                ("/admin/departments", {"limit": limit}),
                ("/admin/departments", None),
            ],
            scope_hint="ZohoCliq.Departments.READ",
            operation_label="departments-list",
            not_supported_message="Cliq org-admin department listing endpoints are not available for this token/network endpoint.",
        )

    def list_roles(self, *, limit: int = 50) -> dict:
        """List organization roles (cliq-190 third org-admin slice)."""
        return self._get_with_candidates_and_not_supported(
            [
                ("/roles", {"limit": limit}),
                ("/roles", None),
                ("/admin/roles", {"limit": limit}),
                ("/admin/roles", None),
            ],
            scope_hint="ZohoCliq.Roles.READ",
            operation_label="roles-list",
            not_supported_message="Cliq org-admin role listing endpoints are not available for this token/network endpoint.",
        )

    def list_designations(self, *, limit: int = 50) -> dict:
        """List organization designations (cliq-190 fourth org-admin slice)."""
        return self._get_with_candidates_and_not_supported(
            [
                ("/designations", {"limit": limit}),
                ("/designations", None),
                ("/admin/designations", {"limit": limit}),
                ("/admin/designations", None),
            ],
            scope_hint="ZohoCliq.Designations.READ",
            operation_label="designations-list",
            not_supported_message="Cliq org-admin designation listing endpoints are not available for this token/network endpoint.",
        )

    def list_user_statuses(self, *, limit: int = 50) -> dict:
        """List organization user-status values (cliq-190 fifth org-admin slice)."""
        return self._get_with_candidates_and_not_supported(
            [
                ("/userstatus", {"limit": limit}),
                ("/userstatus", None),
                ("/admin/userstatus", {"limit": limit}),
                ("/admin/userstatus", None),
            ],
            scope_hint="ZohoCliq.Statuses.READ",
            operation_label="user-status-list",
            not_supported_message="Cliq org-admin user-status listing endpoints are not available for this token/network endpoint.",
        )

    def list_user_fields(self, *, limit: int = 50) -> dict:
        """List organization user-field definitions (cliq-190 sixth org-admin slice)."""
        return self._get_with_candidates_and_not_supported(
            [
                ("/userfields", {"limit": limit}),
                ("/userfields", None),
                ("/admin/userfields", {"limit": limit}),
                ("/admin/userfields", None),
            ],
            scope_hint="ZohoCliq.UserFields.READ",
            operation_label="userfields-list",
            not_supported_message="Cliq org-admin userfields listing endpoints are not available for this token/network endpoint.",
        )

    def list_events(self, *, limit: int = 50) -> dict:
        """List collaboration events (cliq-191 first collaboration slice)."""
        return self._get_with_candidates_and_not_supported(
            [
                ("/events", {"limit": limit}),
                ("/events", None),
                ("/admin/events", {"limit": limit}),
                ("/admin/events", None),
            ],
            scope_hint="ZohoCliq.Events.READ",
            operation_label="events-list",
            not_supported_message="Cliq collaboration event listing endpoints are not available for this token/network endpoint.",
        )

    def list_reminders(self, *, limit: int = 50) -> dict:
        """List collaboration reminders (cliq-191 reminders slice)."""
        return self._get_with_candidates_and_not_supported(
            [
                ("/reminders", {"limit": limit}),
                ("/reminders", None),
                ("/admin/reminders", {"limit": limit}),
                ("/admin/reminders", None),
            ],
            scope_hint="ZohoCliq.Reminders.READ",
            operation_label="reminders-list",
            not_supported_message="Cliq collaboration reminder listing endpoints are not available for this token/network endpoint.",
        )

    def list_meetings(self, *, limit: int = 50) -> dict:
        """List collaboration calls/meetings (cliq-191 calls-and-meetings slice)."""
        return self._get_with_candidates_and_not_supported(
            [
                ("/meetings", {"limit": limit}),
                ("/meetings", None),
                ("/calls", {"limit": limit}),
                ("/calls", None),
                ("/admin/meetings", {"limit": limit}),
                ("/admin/meetings", None),
                ("/admin/calls", {"limit": limit}),
                ("/admin/calls", None),
            ],
            scope_hint="ZohoCliq.Calls.READ",
            operation_label="meetings-list",
            not_supported_message="Cliq collaboration calls/meetings listing endpoints are not available for this token/network endpoint.",
        )

    def list_databases(self, *, limit: int = 50) -> dict:
        """List platform-extension databases (cliq-192 first slice)."""
        return self._get_with_candidates_and_not_supported(
            [
                ("/databases", {"limit": limit}),
                ("/databases", None),
                ("/database", {"limit": limit}),
                ("/database", None),
                ("/admin/databases", {"limit": limit}),
                ("/admin/databases", None),
            ],
            scope_hint="ZohoCliq.Databases.READ",
            operation_label="databases-list",
            not_supported_message="Cliq platform database listing endpoints are not available for this token/network endpoint.",
        )

    def list_widgets(self, *, limit: int = 50) -> dict:
        """List platform-extension widgets (cliq-192 second slice)."""
        return self._get_with_candidates_and_not_supported(
            [
                ("/widgets", {"limit": limit}),
                ("/widgets", None),
                ("/widget", {"limit": limit}),
                ("/widget", None),
                ("/admin/widgets", {"limit": limit}),
                ("/admin/widgets", None),
            ],
            scope_hint="ZohoCliq.Widgets.READ",
            operation_label="widgets-list",
            not_supported_message="Cliq platform widget listing endpoints are not available for this token/network endpoint.",
        )

    def list_map_tickers(self, *, limit: int = 50) -> dict:
        """List platform map tickers (cliq-192 third slice)."""
        return self._get_with_candidates_and_not_supported(
            [
                ("/map/tickers", {"limit": limit}),
                ("/map/tickers", None),
                ("/map/ticker", {"limit": limit}),
                ("/map/ticker", None),
                ("/admin/map/tickers", {"limit": limit}),
                ("/admin/map/tickers", None),
                ("/admin/map/ticker", {"limit": limit}),
                ("/admin/map/ticker", None),
            ],
            scope_hint="ZohoCliq.Tickers.READ",
            operation_label="map-tickers-list",
            not_supported_message="Cliq platform map ticker listing endpoints are not available for this token/network endpoint.",
        )

    def list_custom_domains(self, *, limit: int = 50) -> dict:
        """List platform custom domains (cliq-192 fourth slice)."""
        return self._get_with_candidates_and_not_supported(
            [
                ("/customdomains", {"limit": limit}),
                ("/customdomains", None),
                ("/customdomain", {"limit": limit}),
                ("/customdomain", None),
                ("/admin/customdomains", {"limit": limit}),
                ("/admin/customdomains", None),
                ("/admin/customdomain", {"limit": limit}),
                ("/admin/customdomain", None),
            ],
            scope_hint="ZohoCliq.CustomDomains.READ",
            operation_label="custom-domains-list",
            not_supported_message="Cliq platform custom domain listing endpoints are not available for this token/network endpoint.",
        )

    def list_custom_emails(self, *, limit: int = 50) -> dict:
        """List platform custom emails (cliq-192 fifth slice)."""
        return self._get_with_candidates_and_not_supported(
            [
                ("/customemails", {"limit": limit}),
                ("/customemails", None),
                ("/customemail", {"limit": limit}),
                ("/customemail", None),
                ("/admin/customemails", {"limit": limit}),
                ("/admin/customemails", None),
                ("/admin/customemail", {"limit": limit}),
                ("/admin/customemail", None),
            ],
            scope_hint="ZohoCliq.CustomEmails.READ",
            operation_label="custom-emails-list",
            not_supported_message="Cliq platform custom email listing endpoints are not available for this token/network endpoint.",
        )

    def list_apps(self, *, limit: int = 50) -> dict:
        """List app-governance apps (cliq-193 first slice)."""
        return self._get_with_candidates_and_not_supported(
            [
                ("/apps", {"limit": limit}),
                ("/apps", None),
                ("/app", {"limit": limit}),
                ("/app", None),
                ("/admin/apps", {"limit": limit}),
                ("/admin/apps", None),
                ("/admin/app", {"limit": limit}),
                ("/admin/app", None),
            ],
            scope_hint="ZohoCliq.Apps.READ",
            operation_label="apps-list",
            not_supported_message="Cliq app-governance app listing endpoints are not available for this token/network endpoint.",
        )

    def get_app(self, app_id: str) -> dict:
        """Fetch one app-governance app by id (cliq-193 second slice)."""
        resolved_app_id = app_id.strip()
        if not resolved_app_id:
            utils.error_exit("invalid_app_id", "app_id cannot be empty")

        return self._get_with_candidates_and_not_supported(
            [
                (f"/apps/{resolved_app_id}", None),
                (f"/app/{resolved_app_id}", None),
                (f"/admin/apps/{resolved_app_id}", None),
                (f"/admin/app/{resolved_app_id}", None),
            ],
            scope_hint="ZohoCliq.Apps.READ",
            operation_label="app-get",
            not_supported_message="Cliq app-governance app-detail endpoints are not available for this token/network endpoint.",
        )

    def list_app_permissions(self, app_id: str, *, limit: int = 50) -> dict:
        """List app-governance permissions/scopes for one app (cliq-193 third slice)."""
        resolved_app_id = app_id.strip()
        if not resolved_app_id:
            utils.error_exit("invalid_app_id", "app_id cannot be empty")

        return self._get_with_candidates_and_not_supported(
            [
                (f"/apps/{resolved_app_id}/permissions", {"limit": limit}),
                (f"/apps/{resolved_app_id}/permissions", None),
                (f"/app/{resolved_app_id}/permissions", {"limit": limit}),
                (f"/app/{resolved_app_id}/permissions", None),
                (f"/admin/apps/{resolved_app_id}/permissions", {"limit": limit}),
                (f"/admin/apps/{resolved_app_id}/permissions", None),
                (f"/admin/app/{resolved_app_id}/permissions", {"limit": limit}),
                (f"/admin/app/{resolved_app_id}/permissions", None),
            ],
            scope_hint="ZohoCliq.Apps.READ",
            operation_label="app-permissions-list",
            not_supported_message="Cliq app-governance app-permissions endpoints are not available for this token/network endpoint.",
        )

    def get_app_permission(self, app_id: str, permission_id: str) -> dict:
        """Fetch one app-governance permission by id (cliq-193 eighth slice)."""
        resolved_app_id = app_id.strip()
        if not resolved_app_id:
            utils.error_exit("invalid_app_id", "app_id cannot be empty")

        resolved_permission_id = permission_id.strip()
        if not resolved_permission_id:
            utils.error_exit("invalid_permission_id", "permission_id cannot be empty")

        return self._get_with_candidates_and_not_supported(
            [
                (
                    f"/apps/{resolved_app_id}/permissions/{resolved_permission_id}",
                    None,
                ),
                (f"/app/{resolved_app_id}/permissions/{resolved_permission_id}", None),
                (
                    f"/admin/apps/{resolved_app_id}/permissions/{resolved_permission_id}",
                    None,
                ),
                (
                    f"/admin/app/{resolved_app_id}/permissions/{resolved_permission_id}",
                    None,
                ),
            ],
            scope_hint="ZohoCliq.Apps.READ",
            operation_label="app-permission-get",
            not_supported_message="Cliq app-governance app-permission detail endpoints are not available for this token/network endpoint.",
        )

    def list_app_installs(self, app_id: str, *, limit: int = 50) -> dict:
        """List app-governance installs for one app (cliq-193 fourth slice)."""
        resolved_app_id = app_id.strip()
        if not resolved_app_id:
            utils.error_exit("invalid_app_id", "app_id cannot be empty")

        return self._get_with_candidates_and_not_supported(
            [
                (f"/apps/{resolved_app_id}/installs", {"limit": limit}),
                (f"/apps/{resolved_app_id}/installs", None),
                (f"/app/{resolved_app_id}/installs", {"limit": limit}),
                (f"/app/{resolved_app_id}/installs", None),
                (f"/admin/apps/{resolved_app_id}/installs", {"limit": limit}),
                (f"/admin/apps/{resolved_app_id}/installs", None),
                (f"/admin/app/{resolved_app_id}/installs", {"limit": limit}),
                (f"/admin/app/{resolved_app_id}/installs", None),
            ],
            scope_hint="ZohoCliq.Apps.READ",
            operation_label="app-installs-list",
            not_supported_message="Cliq app-governance app-install endpoints are not available for this token/network endpoint.",
        )

    def get_app_install(self, app_id: str, install_id: str) -> dict:
        """Fetch one app-governance install by id (cliq-193 seventh slice)."""
        resolved_app_id = app_id.strip()
        if not resolved_app_id:
            utils.error_exit("invalid_app_id", "app_id cannot be empty")

        resolved_install_id = install_id.strip()
        if not resolved_install_id:
            utils.error_exit("invalid_install_id", "install_id cannot be empty")

        return self._get_with_candidates_and_not_supported(
            [
                (f"/apps/{resolved_app_id}/installs/{resolved_install_id}", None),
                (f"/app/{resolved_app_id}/installs/{resolved_install_id}", None),
                (f"/admin/apps/{resolved_app_id}/installs/{resolved_install_id}", None),
                (f"/admin/app/{resolved_app_id}/installs/{resolved_install_id}", None),
            ],
            scope_hint="ZohoCliq.Apps.READ",
            operation_label="app-install-get",
            not_supported_message="Cliq app-governance app-install detail endpoints are not available for this token/network endpoint.",
        )

    def list_app_commands(self, app_id: str, *, limit: int = 50) -> dict:
        """List app-governance commands for one app (cliq-193 fifth slice)."""
        resolved_app_id = app_id.strip()
        if not resolved_app_id:
            utils.error_exit("invalid_app_id", "app_id cannot be empty")

        return self._get_with_candidates_and_not_supported(
            [
                (f"/apps/{resolved_app_id}/commands", {"limit": limit}),
                (f"/apps/{resolved_app_id}/commands", None),
                (f"/app/{resolved_app_id}/commands", {"limit": limit}),
                (f"/app/{resolved_app_id}/commands", None),
                (f"/admin/apps/{resolved_app_id}/commands", {"limit": limit}),
                (f"/admin/apps/{resolved_app_id}/commands", None),
                (f"/admin/app/{resolved_app_id}/commands", {"limit": limit}),
                (f"/admin/app/{resolved_app_id}/commands", None),
            ],
            scope_hint="ZohoCliq.Apps.READ",
            operation_label="app-commands-list",
            not_supported_message="Cliq app-governance app-command endpoints are not available for this token/network endpoint.",
        )

    def get_app_command(self, app_id: str, command_id: str) -> dict:
        """Fetch one app-governance command by id (cliq-193 sixth slice)."""
        resolved_app_id = app_id.strip()
        if not resolved_app_id:
            utils.error_exit("invalid_app_id", "app_id cannot be empty")

        resolved_command_id = command_id.strip()
        if not resolved_command_id:
            utils.error_exit("invalid_command_id", "command_id cannot be empty")

        return self._get_with_candidates_and_not_supported(
            [
                (f"/apps/{resolved_app_id}/commands/{resolved_command_id}", None),
                (f"/app/{resolved_app_id}/commands/{resolved_command_id}", None),
                (f"/admin/apps/{resolved_app_id}/commands/{resolved_command_id}", None),
                (f"/admin/app/{resolved_app_id}/commands/{resolved_command_id}", None),
            ],
            scope_hint="ZohoCliq.Apps.READ",
            operation_label="app-command-get",
            not_supported_message="Cliq app-governance app-command detail endpoints are not available for this token/network endpoint.",
        )

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
                    {
                        "name": "chats.threads.list",
                        "kind": "read",
                        "method": "GET",
                        "path": f"/chats/{resolved_chat_id or channel_id}/threads",
                        "params": {"limit": 1},
                    },
                    {
                        "name": "channels.threads.list",
                        "kind": "read",
                        "method": "GET",
                        "path": f"/channels/{channel_id}/threads",
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
                            "name": "chats.messages.get.alt",
                            "kind": "read",
                            "method": "GET",
                            "path": f"/chats/{target_chat}/messages/{probe_message_id}/messages",
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
                            "name": "chats.messages.reactions",
                            "kind": "read",
                            "method": "GET",
                            "path": f"/chats/{target_chat}/messages/{probe_message_id}/reactions",
                            "params": {},
                        },
                        {
                            "name": "chats.messages.reactions.alt",
                            "kind": "read",
                            "method": "GET",
                            "path": f"/chats/{target_chat}/messages/{probe_message_id}/messages/reactions",
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
                            "name": "channels.messages.get.alt",
                            "kind": "read",
                            "method": "GET",
                            "path": f"/channels/{channel_id}/messages/{probe_message_id}/messages",
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
                            "name": "channels.messages.reactions",
                            "kind": "read",
                            "method": "GET",
                            "path": f"/channels/{channel_id}/messages/{probe_message_id}/reactions",
                            "params": {},
                        },
                        {
                            "name": "channels.messages.reactions.alt",
                            "kind": "read",
                            "method": "GET",
                            "path": f"/channels/{channel_id}/messages/{probe_message_id}/messages/reactions",
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

        not_supported_message = (
            "Cliq local multipart upload endpoints are not supported for this token/"
            "network target. Text send can still succeed; collect `attempts:` "
            "evidence and treat this as endpoint limitation."
        )
        self._guard_deferred_operation(
            operation_label="send-local-file-message",
            signal_code="not_supported",
            message=not_supported_message,
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
                        self._clear_operation_unsupported_entry(
                            "send-local-file-message"
                        )
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
                        or "inactive_appaccount_user" in lowered
                        or code
                        in {
                            "inactive_appaccount_user",
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
                self._error_exit_unsupported_signal(
                    operation_label="send-local-file-message",
                    signal_code="not_supported",
                    message=not_supported_message + _attempt_suffix(),
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
