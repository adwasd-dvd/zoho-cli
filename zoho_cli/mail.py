"""High-level mail helpers: folder resolution, message formatting."""

import logging
from typing import Optional

from zoho_cli import utils
from zoho_cli.api import ZohoMailClient

logger = logging.getLogger(__name__)


# ── folder resolution ─────────────────────────────────────────────────────────

def resolve_folder_id(client: ZohoMailClient, account_id: str, folder_name: str) -> str:
    """Resolve a folder name or ID to its folderId string."""
    resp = client.get_folders(account_id)
    folders = resp.get("data", [])

    # Accept a numeric-looking string as a direct folderId
    if folder_name.isdigit():
        for f in folders:
            if str(f.get("folderId")) == folder_name:
                return folder_name
        return folder_name  # pass through and let the API reject it if wrong

    name_lower = folder_name.lower()
    # Exact name match
    for f in folders:
        if f.get("folderName", "").lower() == name_lower:
            return str(f["folderId"])
    # folderType match (Inbox, Sent, Drafts, Trash, Spam, …)
    for f in folders:
        if f.get("folderType", "").lower() == name_lower:
            return str(f["folderId"])

    utils.error_exit("folder_not_found", f"Folder '{folder_name}' not found")
    return ""  # unreachable


def find_folder_for_message(
    client: ZohoMailClient, account_id: str, message_id: str
) -> Optional[str]:
    """Search all folders to find which one contains the given message."""
    resp = client.get_folders(account_id)
    folders = resp.get("data", [])

    for folder in folders:
        folder_id = str(folder["folderId"])
        try:
            msgs = client.get_messages(account_id, folder_id, limit=200)
            for msg in msgs.get("data", []):
                if str(msg.get("messageId")) == message_id:
                    return folder_id
        except SystemExit:
            # skip folders that return errors (e.g. empty or access-restricted)
            continue

    return None


def resolve_message_folder_id(
    client: ZohoMailClient,
    account_id: str,
    message_id: str,
    folder_id: Optional[str] = None,
) -> str:
    """Resolve folder_id or locate the message folder, exiting if not found."""
    fid = folder_id or find_folder_for_message(client, account_id, message_id)
    if not fid:
        utils.error_exit("message_not_found", f"Message {message_id} not found in any folder.")
    return fid


# ── message formatters ────────────────────────────────────────────────────────

def _to_list(val) -> list:
    if not val:
        return []
    if isinstance(val, list):
        return val
    return [val]


def format_message_summary(msg: dict) -> dict:
    """Normalise a raw API message object into the CLI list/search schema."""
    return {
        "messageId": str(msg.get("messageId", "")),
        "folderId": str(msg.get("folderId", "")),
        "subject": msg.get("subject", ""),
        "from": msg.get("sender", msg.get("fromAddress", msg.get("from", ""))),
        "to": _to_list(msg.get("toAddress", msg.get("to", []))),
        "date": msg.get("receivedTime", msg.get("sentDateInGMT", msg.get("date", ""))),
        "unread": not bool(msg.get("isRead", False)),
        "hasAttachments": bool(msg.get("hasAttachment", False)),
        "tags": msg.get("tags", []),
    }


def format_message_content(msg: dict) -> dict:
    """Normalise a raw API content object into the CLI get schema."""
    return {
        "messageId": str(msg.get("messageId", "")),
        "folderId": str(msg.get("folderId", "")),
        "subject": msg.get("subject", ""),
        "from": msg.get("sender", msg.get("fromAddress", msg.get("from", ""))),
        "to": _to_list(msg.get("toAddress", msg.get("to", []))),
        "cc": _to_list(msg.get("ccAddress", msg.get("cc", []))),
        "bcc": _to_list(msg.get("bccAddress", msg.get("bcc", []))),
        "date": msg.get("receivedTime", msg.get("sentDateInGMT", msg.get("date", ""))),
        "unread": not bool(msg.get("isRead", False)),
        "tags": msg.get("tags", []),
        "hasAttachments": bool(msg.get("hasAttachment", False)),
        "textBody": msg.get("textBody", msg.get("content", "")),
        "htmlBody": msg.get("htmlBody", ""),
    }


def fetch_message_content(
    client: ZohoMailClient,
    account_id: str,
    folder_id: str,
    message_id: str,
) -> dict:
    """Fetch and normalize full message content."""
    resp = client.get_message_content(account_id, folder_id, message_id)
    return format_message_content(resp.get("data", resp))


def format_attachment(att: dict) -> dict:
    # Defensive handling for unexpected attachment types (e.g., string IDs)
    if isinstance(att, str):
        return {
            "attachmentId": att,
            "fileName": "",
            "size": 0,
        }
    if not isinstance(att, dict):
        raise ValueError(f"Expected dict or str for attachment, got {type(att)}")

    return {
        "attachmentId": str(att.get("attachmentId", att.get("attachId", ""))),
        "fileName": att.get("attachmentName", att.get("fileName", "")),
        "size": int(att.get("attachmentSize", att.get("size", 0) or 0)),
    }


def list_attachments(client: ZohoMailClient, account_id: str, folder_id: str,
                     message_id: str) -> list[dict]:
    """List attachments for a message.
    
    Returns a normalized list of attachment dicts with keys:
    - attachmentId
    - fileName  
    - size
    
    Handles various API response shapes (dict/list, nested structures).
    """
    resp = client.get_attachment_info(account_id, folder_id, message_id)
    data = resp.get("data", {}) or {}
    raw_atts: list[dict | str] = []

    if isinstance(data, dict):
        raw_atts.extend(data.get("attachments", []) or [])
        raw_atts.extend(data.get("inline", []) or [])
    elif isinstance(data, list):
        # Compatible with future variations or other return types
        raw_atts.extend(data)

    return [format_attachment(a) for a in raw_atts if isinstance(a, (dict, str))]


# ── message composition helpers ──────────────────────────────────────────────

def _prefixed_subject(subject: str, prefix: str) -> str:
    if subject.lower().startswith(prefix.lower()):
        return subject
    return f"{prefix} {subject}"


def _plaintext_payload(from_address: str, to_address: str, subject: str, body: str) -> dict:
    return {
        "fromAddress": from_address,
        "toAddress": to_address,
        "subject": subject,
        "mailFormat": "plaintext",
        "content": body,
    }


def build_send_payload(
    from_address: str,
    to_addresses: list[str],
    subject: str,
    *,
    text: str | None = None,
    html_body: str | None = None,
    cc_addresses: list[str] | None = None,
    bcc_addresses: list[str] | None = None,
) -> dict:
    if not text and not html_body:
        raise ValueError("text or html_body is required")

    payload: dict = {
        "fromAddress": from_address,
        "toAddress": ",".join(to_addresses),
        "subject": subject,
        "mailFormat": "html" if html_body else "plaintext",
        "content": html_body or text or "",
    }
    if cc_addresses:
        payload["ccAddress"] = ",".join(cc_addresses)
    if bcc_addresses:
        payload["bccAddress"] = ",".join(bcc_addresses)
    if text and html_body:
        payload["altText"] = text
    return payload


def build_reply_payload(
    from_address: str,
    to_address: str,
    subject: str,
    text: str,
    *,
    quote_original: bool = False,
    original_text: str | None = None,
) -> dict:
    body = text
    if quote_original and original_text:
        quoted = "\n".join(f"> {line}" for line in original_text.splitlines())
        body = f"{text}\n\n{quoted}"

    return _plaintext_payload(
        from_address,
        to_address,
        _prefixed_subject(subject, "Re:"),
        body,
    )


def build_forward_payload(
    from_address: str,
    to_addresses: list[str],
    subject: str,
    original_from: str,
    original_subject: str,
    *,
    note: str | None = None,
    original_text: str = "",
) -> dict:
    forwarded_block = (
        "\n\n---------- Forwarded message ----------\n"
        f"From: {original_from}\n"
        f"Subject: {original_subject}\n\n"
        f"{original_text}"
    )
    body = (note or "") + forwarded_block

    return _plaintext_payload(
        from_address,
        ",".join(to_addresses),
        _prefixed_subject(subject, "Fwd:"),
        body,
    )


def build_send_status_extra(response: dict) -> dict:
    """Normalize send/reply/forward API responses for CLI status output."""
    payload = response.get("data", response) if isinstance(response, dict) else {}
    if not isinstance(payload, dict):
        payload = {}

    extra: dict[str, str] = {"messageId": str(payload.get("messageId", ""))}
    send_status = payload.get("status")
    if send_status not in (None, ""):
        extra["sendStatus"] = str(send_status)
    return extra
