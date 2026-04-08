"""Low-level Zoho Mail HTTP client.

Each method maps closely to one Zoho Mail REST endpoint.
All errors call utils.error_exit() so callers never need to check status codes.
"""

import logging
import mimetypes
from pathlib import Path
import time
from typing import Any, Optional

import httpx

from zoho_cli import config as _config
from zoho_cli import utils

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0)


class ZohoMailClient:
    _RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}

    def __init__(self, access_token: str, mail_base_url: Optional[str] = None) -> None:
        self.access_token = access_token
        self.base_url = (mail_base_url or _config.mail_base_url()).rstrip("/")
        self._headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}

    def _request_with_retry(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json_payload: Optional[dict] = None,
        data: Optional[dict] = None,
        files: Optional[list[tuple]] = None,
        timeout: Optional[httpx.Timeout] = None,
    ) -> httpx.Response:
        url = f"{self.base_url}{path}"
        max_attempts = 3
        attempt = 0

        while True:
            attempt += 1
            try:
                logger.debug("%s %s attempt=%s", method, url, attempt)
                resp = httpx.request(
                    method,
                    url,
                    headers=self._headers,
                    params=params or {},
                    json=json_payload,
                    data=data,
                    files=files,
                    timeout=timeout or _TIMEOUT,
                )
                logger.debug("→ %s", resp.status_code)
            except (httpx.TimeoutException, httpx.NetworkError, httpx.TransportError) as e:
                if attempt >= max_attempts:
                    utils.error_exit("api_error", f"{method} {path} failed after {attempt} attempts: {e}")
                backoff = min(0.5 * (2 ** (attempt - 1)), 5.0)
                logger.debug("retrying %s %s after transport error: %s", method, path, e)
                time.sleep(backoff)
                continue

            if resp.is_success:
                return resp

            if resp.status_code in self._RETRYABLE_STATUS and attempt < max_attempts:
                retry_after_header = (resp.headers.get("retry-after") or "").strip()
                retry_after: Optional[float] = None
                if retry_after_header:
                    try:
                        retry_after = max(0.0, float(retry_after_header))
                    except ValueError:
                        retry_after = None
                backoff = retry_after if retry_after is not None else min(0.5 * (2 ** (attempt - 1)), 5.0)
                logger.debug(
                    "retrying %s %s after HTTP %s, sleep=%ss",
                    method,
                    path,
                    resp.status_code,
                    backoff,
                )
                time.sleep(backoff)
                continue

            utils.error_exit("api_error", f"HTTP {resp.status_code} {method} {path}: {resp.text}")

        # unreachable
        raise RuntimeError("unreachable")

    # ── internal request helpers ──────────────────────────────────────────────

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        resp = self._request_with_retry("GET", path, params=params)
        return resp.json()

    def _post_json(self, path: str, payload: dict) -> dict:
        resp = self._request_with_retry("POST", path, json_payload=payload)
        return resp.json()

    def _post_multipart(self, path: str, data: dict, files: list[tuple]) -> dict:
        resp = self._request_with_retry(
            "POST",
            path,
            data=data,
            files=files,
            timeout=httpx.Timeout(120.0),
        )
        return resp.json()

    def _put(self, path: str, payload: dict) -> dict:
        resp = self._request_with_retry("PUT", path, json_payload=payload)
        return resp.json()

    def _delete(self, path: str) -> dict:
        resp = self._request_with_retry("DELETE", path)
        return resp.json()

    def _get_bytes(self, path: str) -> bytes:
        resp = self._request_with_retry("GET", path, timeout=httpx.Timeout(120.0))
        return resp.content

    # ── account ───────────────────────────────────────────────────────────────

    def get_accounts(self) -> dict:
        return self._get("/accounts")

    # ── folders ───────────────────────────────────────────────────────────────

    def get_folders(self, account_id: str) -> dict:
        return self._get(f"/accounts/{account_id}/folders")

    def create_folder(self, account_id: str, folder_name: str, parent_id: Optional[str] = None) -> dict:
        payload: dict[str, Any] = {"folderName": folder_name}
        if parent_id:
            payload["parentId"] = parent_id
        return self._post_json(f"/accounts/{account_id}/folders", payload)

    def update_folder(self, account_id: str, folder_id: str, folder_name: str) -> dict:
        return self._put(f"/accounts/{account_id}/folders/{folder_id}", {"folderName": folder_name})

    def delete_folder(self, account_id: str, folder_id: str) -> dict:
        return self._delete(f"/accounts/{account_id}/folders/{folder_id}")

    def folder_operation(self, account_id: str, folder_id: str, mode: str, **extra) -> dict:
        """Generic folder mode operation (emptyFolder, markAsRead, move, etc.)."""
        payload: dict[str, Any] = {"mode": mode}
        payload.update(extra)
        return self._put(f"/accounts/{account_id}/folders/{folder_id}", payload)

    # ── labels ────────────────────────────────────────────────────────────────

    def get_labels(self, account_id: str) -> dict:
        return self._get(f"/accounts/{account_id}/labels")

    def create_label(self, account_id: str, name: str, color: Optional[str] = None) -> dict:
        payload: dict[str, Any] = {"labelName": name}
        if color:
            payload["color"] = color
        return self._post_json(f"/accounts/{account_id}/labels", payload)

    def delete_label(self, account_id: str, label_id: str) -> dict:
        return self._delete(f"/accounts/{account_id}/labels/{label_id}")

    # ── messages ──────────────────────────────────────────────────────────────

    def get_messages(
        self,
        account_id: str,
        folder_id: str,
        limit: int = 50,
        start: int = 0,
    ) -> dict:
        params: dict[str, Any] = {"folderId": folder_id, "limit": limit}
        if start:
            params["start"] = start
        return self._get(f"/accounts/{account_id}/messages/view", params)

    def search_messages(self, account_id: str, query: str, limit: int = 50) -> dict:
        return self._get(
            f"/accounts/{account_id}/messages/search",
            {"searchKey": query, "limit": limit},
        )

    def get_message_content(
        self, account_id: str, folder_id: str, message_id: str
    ) -> dict:
        return self._get(
            f"/accounts/{account_id}/folders/{folder_id}/messages/{message_id}/content"
        )

    def update_message(self, account_id: str, mode: str, message_ids: list[str], **extra) -> dict:
        payload: dict[str, Any] = {"mode": mode, "messageId": message_ids}
        payload.update(extra)
        return self._put(f"/accounts/{account_id}/updatemessage", payload)

    # ── attachments ───────────────────────────────────────────────────────────

    def get_attachment_info(
        self, account_id: str, folder_id: str, message_id: str
    ) -> dict:
        return self._get(
            f"/accounts/{account_id}/folders/{folder_id}/messages/{message_id}/attachmentinfo"
        )

    def download_attachment(
        self,
        account_id: str,
        folder_id: str,
        message_id: str,
        attachment_id: str,
    ) -> bytes:
        return self._get_bytes(
            f"/accounts/{account_id}/folders/{folder_id}/messages/{message_id}/attachments/{attachment_id}"
        )

    # ── send ──────────────────────────────────────────────────────────────────

    def send_message(
        self,
        account_id: str,
        payload: dict,
        attachment_paths: Optional[list[str]] = None,
    ) -> dict:
        if not attachment_paths:
            return self._post_json(f"/accounts/{account_id}/messages", payload)

        # Build multipart request when attachments are present
        data = {k: v for k, v in payload.items() if isinstance(v, str)}
        # lists need to be serialised as repeated keys; httpx handles list values
        for k, v in payload.items():
            if isinstance(v, list):
                data[k] = v  # type: ignore[assignment]

        files: list[tuple] = []
        handles = []
        try:
            for fpath in attachment_paths:
                p = Path(fpath)
                if not p.exists():
                    utils.error_exit("file_not_found", f"Attachment not found: {fpath}")
                mime = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
                fh = open(p, "rb")
                handles.append(fh)
                files.append(("attachment", (p.name, fh, mime)))
            return self._post_multipart(f"/accounts/{account_id}/messages", data, files)
        finally:
            for fh in handles:
                fh.close()
