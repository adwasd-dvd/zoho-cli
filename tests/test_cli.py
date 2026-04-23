"""Tests for zoho_cli.cli — Typer commands via CliRunner, HTTP mocked with respx."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx
from typer.testing import CliRunner

from zoho_cli import auth
from zoho_cli.cli import app

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

MAIL_BASE = "https://mail.zoho.com/api"
ACCOUNTS_BASE = "https://accounts.zoho.com"
ACCOUNT_EMAIL = "test@example.com"
ACCOUNT_ID = "ACC123"

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_config(tmp_path: Path) -> Path:
    """Write a minimal valid config.json to tmp_path and return its path."""
    cfg = {
        "client_id": "test_id",
        "client_secret": "test_secret",
        "default_account": ACCOUNT_EMAIL,
        "accounts": {
            ACCOUNT_EMAIL: {
                "accountId": ACCOUNT_ID,
                "scopes": [
                    "ZohoMail.messages.ALL",
                    "ZohoMail.folders.ALL",
                    "ZohoMail.accounts.READ",
                ],
            }
        },
    }
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg))
    return cfg_path


@pytest.fixture
def mock_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch keyring so get_password returns a valid JSON token, set_password is a no-op."""
    token_data = json.dumps(
        {
            "refresh_token": "rtoken123",
            "scopes": ["ZohoMail.messages.ALL"],
            "created_at": "2025-01-01T00:00:00+00:00",
        }
    )
    monkeypatch.setattr("keyring.get_password", lambda service, username: token_data)
    monkeypatch.setattr(
        "keyring.set_password", lambda service, username, password: None
    )


@pytest.fixture
def mock_token_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch auth.refresh_access_token to return a fake access token directly."""
    monkeypatch.setattr(
        auth, "refresh_access_token", lambda *a, **kw: "fake-access-token"
    )
    monkeypatch.setattr(
        auth,
        "refresh_access_token_info",
        lambda *a, **kw: {
            "access_token": "fake-access-token",
            "scopes": [
                "ZohoMail.messages.ALL",
                "ZohoMail.folders.ALL",
                "ZohoMail.accounts.READ",
            ],
            "api_domain": "https://www.zohoapis.com",
            "token_type": "Bearer",
        },
    )


def _cfg_env(cfg_path: Path) -> dict[str, str]:
    """Build an env dict that points the CLI at the test config file."""
    return {"ZOHO_CONFIG": str(cfg_path)}


def test_root_help_is_module_first_and_hides_mail_support_aliases() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0, result.output
    assert "Zoho CLI" in result.output
    assert "mail" in result.output
    assert "cliq" in result.output
    assert "crm" in result.output
    assert " attachment  " not in result.output
    assert " folders     " not in result.output
    assert " labels      " not in result.output


def test_mail_help_includes_support_subgroups_under_mail() -> None:
    result = runner.invoke(app, ["mail", "--help"])

    assert result.exit_code == 0, result.output
    assert "attachment" in result.output
    assert "folders" in result.output
    assert "labels" in result.output


def test_legacy_mail_support_root_aliases_still_work() -> None:
    result = runner.invoke(app, ["attachment", "--help"])

    assert result.exit_code == 0, result.output
    assert "Download and display content of an attachment." in result.output


def test_login_no_browser_defaults_to_localhost_redirect_when_unset(
    mock_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When redirect_uri is unset, --no-browser should print a localhost-based auth URL."""

    monkeypatch.setattr(auth, "discover_accounts_server", lambda _cid: ACCOUNTS_BASE)
    monkeypatch.setattr("click.prompt", lambda *_a, **_kw: "abc123")
    monkeypatch.setattr(
        auth,
        "exchange_code",
        lambda *_a, **_kw: {
            "access_token": "token123",
            "refresh_token": "refresh123",
            "scope": "ZohoMail.messages.ALL",
        },
    )
    monkeypatch.setattr(auth, "discover_account_id", lambda *_a, **_kw: ACCOUNT_ID)
    monkeypatch.setattr("zoho_cli.storage.store_token", lambda *_a, **_kw: None)

    result = runner.invoke(
        app,
        [
            "--config",
            str(mock_config),
            "--account",
            ACCOUNT_EMAIL,
            "login",
            "--no-browser",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "https://accounts.zoho.com/oauth/v2/auth?" in result.output
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A" in result.output
    assert "%2Fcallback" in result.output
    assert "example.com%2Fzoho%2Foauth%2Fcallback" not in result.output


def test_login_no_browser_uses_redirect_from_pasted_url_for_exchange(
    mock_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Manual flow should exchange code with the redirect URI extracted from pasted redirect URL."""

    pasted = "https://example.com/zoho/oauth/callback?code=abc123"
    seen: dict[str, str] = {}

    monkeypatch.setattr(auth, "discover_accounts_server", lambda _cid: ACCOUNTS_BASE)
    monkeypatch.setattr("click.prompt", lambda *_a, **_kw: pasted)

    def _exchange_code(
        code: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        accounts_base_url: str | None = None,
    ) -> dict[str, str]:
        seen["code"] = code
        seen["redirect_uri"] = redirect_uri
        return {
            "access_token": "token123",
            "refresh_token": "refresh123",
            "scope": "ZohoMail.messages.ALL",
        }

    monkeypatch.setattr(auth, "exchange_code", _exchange_code)
    monkeypatch.setattr(auth, "discover_account_id", lambda *_a, **_kw: ACCOUNT_ID)
    monkeypatch.setattr("zoho_cli.storage.store_token", lambda *_a, **_kw: None)

    result = runner.invoke(
        app,
        [
            "--config",
            str(mock_config),
            "--account",
            ACCOUNT_EMAIL,
            "login",
            "--no-browser",
        ],
    )

    assert result.exit_code == 0, result.output
    assert seen["code"] == "abc123"
    assert seen["redirect_uri"] == "https://example.com/zoho/oauth/callback"


def test_login_no_browser_accepts_localhost_callback_without_paste(
    mock_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Manual flow can proceed from captured localhost callback when paste input is empty."""

    class _FakeServer:
        def serve_forever(self, poll_interval: float = 0.5) -> None:
            return None

        def shutdown(self) -> None:
            return None

        def server_close(self) -> None:
            return None

    seen: dict[str, str | None] = {}
    callback_result = {
        "code": "code-from-callback",
        "accounts_server": ACCOUNTS_BASE,
        "requested_scopes": ["ZohoMail.messages.ALL", "ZohoCRM.modules.ALL"],
    }

    monkeypatch.setattr(auth, "discover_accounts_server", lambda _cid: ACCOUNTS_BASE)
    monkeypatch.setattr(
        auth,
        "create_callback_server",
        lambda *_a, **_kw: (
            _FakeServer(),
            "http://localhost:51821/callback",
            callback_result,
        ),
    )
    monkeypatch.setattr("click.prompt", lambda *_a, **_kw: "")

    def _exchange_code(
        code: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        accounts_base_url: str | None = None,
    ) -> dict[str, str]:
        seen["code"] = code
        seen["redirect_uri"] = redirect_uri
        seen["accounts_base_url"] = accounts_base_url
        return {
            "access_token": "token123",
            "refresh_token": "refresh123",
            "scope": "ZohoMail.messages.ALL,ZohoCRM.modules.ALL",
        }

    monkeypatch.setattr(auth, "exchange_code", _exchange_code)
    monkeypatch.setattr(auth, "discover_account_id", lambda *_a, **_kw: ACCOUNT_ID)
    monkeypatch.setattr("zoho_cli.storage.store_token", lambda *_a, **_kw: None)

    result = runner.invoke(
        app,
        [
            "--config",
            str(mock_config),
            "--account",
            ACCOUNT_EMAIL,
            "login",
            "--no-browser",
            "--with-crm",
        ],
    )

    assert result.exit_code == 0, result.output
    assert seen["code"] == "code-from-callback"
    assert seen["redirect_uri"] == "http://localhost:51821/callback"
    assert seen["accounts_base_url"] == ACCOUNTS_BASE


def test_login_no_browser_with_cliq_export_includes_export_scopes(
    mock_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--with-cliq-export should include maintenance export scopes in auth URL."""

    monkeypatch.setattr(auth, "discover_accounts_server", lambda _cid: ACCOUNTS_BASE)
    monkeypatch.setattr("click.prompt", lambda *_a, **_kw: "abc123")
    monkeypatch.setattr(
        auth,
        "exchange_code",
        lambda *_a, **_kw: {
            "access_token": "token123",
            "refresh_token": "refresh123",
            "scope": "ZohoMail.messages.ALL",
        },
    )
    monkeypatch.setattr(auth, "discover_account_id", lambda *_a, **_kw: ACCOUNT_ID)
    monkeypatch.setattr("zoho_cli.storage.store_token", lambda *_a, **_kw: None)

    result = runner.invoke(
        app,
        [
            "--config",
            str(mock_config),
            "--account",
            ACCOUNT_EMAIL,
            "login",
            "--no-browser",
            "--with-cliq",
            "--with-cliq-export",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "ZohoCliq.OrganizationChats.READ" in result.output
    assert "ZohoCliq.OrganizationMessages.READ" in result.output


# ---------------------------------------------------------------------------
# mail search
# ---------------------------------------------------------------------------


def test_mail_search_short_query(mock_config: Path, mock_token_refresh: Any) -> None:
    """A single-character query is rejected with exit code 1 and an invalid_query error."""
    result = runner.invoke(app, ["mail", "search", "X"], env=_cfg_env(mock_config))
    assert result.exit_code == 1
    assert "invalid_query" in result.output


@respx.mock
def test_mail_search_valid(mock_config: Path, mock_token_refresh: Any) -> None:
    """A valid search query returns exit code 0 and a JSON list of message summaries."""
    respx.get(f"{MAIL_BASE}/accounts/{ACCOUNT_ID}/messages/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "messageId": "1001",
                        "subject": "Invoice Q1",
                        "sender": "billing@vendor.com",
                        "receivedTime": "1700000000000",
                        "isRead": False,
                    }
                ]
            },
        )
    )
    result = runner.invoke(
        app, ["mail", "search", "invoice"], env=_cfg_env(mock_config)
    )
    assert result.exit_code == 0, result.output
    messages = json.loads(result.output)
    assert isinstance(messages, list)
    assert len(messages) == 1
    assert messages[0]["messageId"] == "1001"
    assert messages[0]["subject"] == "Invoice Q1"


@respx.mock
def test_mail_search_returns_empty_list(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    """A search that finds no messages returns an empty JSON list."""
    respx.get(f"{MAIL_BASE}/accounts/{ACCOUNT_ID}/messages/search").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    result = runner.invoke(
        app, ["mail", "search", "nomatches"], env=_cfg_env(mock_config)
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == []


# ---------------------------------------------------------------------------
# mail list
# ---------------------------------------------------------------------------


@respx.mock
def test_mail_list(mock_config: Path, mock_token_refresh: Any) -> None:
    """mail list resolves the Inbox folder and returns a JSON list of messages."""
    # mail list first resolves the folder name via get_folders, then fetches messages.
    respx.get(f"{MAIL_BASE}/accounts/{ACCOUNT_ID}/folders").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "folderId": "FOLD1",
                        "folderName": "Inbox",
                        "folderType": "Inbox",
                        "unreadCount": 2,
                    }
                ]
            },
        )
    )
    respx.get(f"{MAIL_BASE}/accounts/{ACCOUNT_ID}/messages/view").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "messageId": "2001",
                        "subject": "Hello World",
                        "sender": "alice@example.com",
                        "receivedTime": "1700000000000",
                        "isRead": True,
                        "folderId": "FOLD1",
                    }
                ]
            },
        )
    )
    result = runner.invoke(app, ["mail", "list"], env=_cfg_env(mock_config))
    assert result.exit_code == 0, result.output
    messages = json.loads(result.output)
    assert isinstance(messages, list)
    assert len(messages) == 1
    assert messages[0]["messageId"] == "2001"
    assert messages[0]["subject"] == "Hello World"
    assert messages[0]["from"] == "alice@example.com"


@respx.mock
def test_mail_list_limit_option(mock_config: Path, mock_token_refresh: Any) -> None:
    """The --limit option is forwarded to the API."""
    respx.get(f"{MAIL_BASE}/accounts/{ACCOUNT_ID}/folders").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"folderId": "F1", "folderName": "Inbox", "folderType": "Inbox"}
                ]
            },
        )
    )
    route = respx.get(f"{MAIL_BASE}/accounts/{ACCOUNT_ID}/messages/view").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    result = runner.invoke(
        app, ["mail", "list", "--limit", "5"], env=_cfg_env(mock_config)
    )
    assert result.exit_code == 0, result.output
    called_params = dict(route.calls.last.request.url.params)
    assert called_params["limit"] == "5"


@respx.mock
def test_mail_get_normalizes_nested_content_response(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    """mail get should return normalized message content fields via shared helper."""
    respx.get(f"{MAIL_BASE}/accounts/{ACCOUNT_ID}/messages/view").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "messageId": "M1",
                        "folderId": "F1",
                        "subject": "Status",
                        "sender": "alice@example.com",
                        "toAddress": "bob@example.com",
                        "receivedTime": "1700000000000",
                    }
                ]
            },
        )
    )
    route = respx.get(
        f"{MAIL_BASE}/accounts/{ACCOUNT_ID}/folders/F1/messages/M1/content"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "messageId": "M1",
                    "folderId": "F1",
                    "subject": "Status",
                    "sender": "alice@example.com",
                    "toAddress": "bob@example.com",
                    "textBody": "Original body",
                }
            },
        )
    )

    result = runner.invoke(
        app,
        ["mail", "get", "M1", "--folder-id", "F1"],
        env=_cfg_env(mock_config),
    )

    assert route.called
    assert result.exit_code == 0, result.output
    msg = json.loads(result.output)
    assert msg["messageId"] == "M1"
    assert msg["from"] == "alice@example.com"
    assert msg["to"] == ["bob@example.com"]
    assert msg["textBody"] == "Original body"


@respx.mock
def test_mail_get_hydrates_missing_metadata_from_folder_summary(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    """mail get should hydrate missing subject/from fields from folder message summary."""
    respx.get(f"{MAIL_BASE}/accounts/{ACCOUNT_ID}/messages/view").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "messageId": "M1",
                        "folderId": "F1",
                        "subject": "Security notice",
                        "sender": "Zoho Team",
                        "toAddress": "ai-dev@happy-distro.co.uk",
                        "receivedTime": "1700000000000",
                        "hasAttachment": True,
                    }
                ]
            },
        )
    )
    respx.get(f"{MAIL_BASE}/accounts/{ACCOUNT_ID}/folders/F1/messages/M1/content").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "messageId": "M1",
                    "content": "body only",
                }
            },
        )
    )

    result = runner.invoke(
        app,
        ["mail", "get", "M1", "--folder-id", "F1"],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    msg = json.loads(result.output)
    assert msg["subject"] == "Security notice"
    assert msg["from"] == "Zoho Team"
    assert msg["folderId"] == "F1"
    assert msg["hasAttachments"] is True


# ---------------------------------------------------------------------------
# mail send
# ---------------------------------------------------------------------------


@respx.mock
def test_mail_send_plaintext(mock_config: Path, mock_token_refresh: Any) -> None:
    """mail send should post a plaintext payload and return success status JSON."""
    route = respx.post(f"{MAIL_BASE}/accounts/{ACCOUNT_ID}/messages").mock(
        return_value=httpx.Response(200, json={"data": {"messageId": "S1"}})
    )

    result = runner.invoke(
        app,
        [
            "mail",
            "send",
            "--to",
            "to@example.com",
            "--subject",
            "Status",
            "--text",
            "Body",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(route.calls.last.request.content.decode("utf-8"))
    assert payload == {
        "fromAddress": ACCOUNT_EMAIL,
        "toAddress": "to@example.com",
        "subject": "Status",
        "mailFormat": "plaintext",
        "content": "Body",
    }
    status = json.loads(result.output)
    assert status["status"] == "ok"
    assert status["messageId"] == "S1"


@respx.mock
def test_mail_reply_sends_prefixed_payload_and_status(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    """mail reply should fetch original message, send reply payload, and return send status."""
    respx.get(f"{MAIL_BASE}/accounts/{ACCOUNT_ID}/messages/view").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "messageId": "M1",
                        "folderId": "F1",
                        "subject": "Status",
                        "sender": "alice@example.com",
                    }
                ]
            },
        )
    )
    respx.get(f"{MAIL_BASE}/accounts/{ACCOUNT_ID}/folders/F1/messages/M1/content").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "messageId": "M1",
                    "subject": "Status",
                    "sender": "alice@example.com",
                    "textBody": "Original body",
                }
            },
        )
    )
    send_route = respx.post(f"{MAIL_BASE}/accounts/{ACCOUNT_ID}/messages").mock(
        return_value=httpx.Response(
            200, json={"data": {"messageId": "R1", "status": "queued"}}
        )
    )

    result = runner.invoke(
        app,
        [
            "mail",
            "reply",
            "M1",
            "--folder-id",
            "F1",
            "--text",
            "Looks good",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(send_route.calls.last.request.content.decode("utf-8"))
    assert payload == {
        "fromAddress": ACCOUNT_EMAIL,
        "toAddress": "alice@example.com",
        "subject": "Re: Status",
        "mailFormat": "plaintext",
        "content": "Looks good",
    }
    status = json.loads(result.output)
    assert status["status"] == "ok"
    assert status["messageId"] == "R1"
    assert status["sendStatus"] == "queued"


@respx.mock
def test_mail_forward_sends_forward_payload_and_status(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    """mail forward should include forwarded block and return send status."""
    respx.get(f"{MAIL_BASE}/accounts/{ACCOUNT_ID}/messages/view").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "messageId": "M1",
                        "folderId": "F1",
                        "subject": "Status",
                        "sender": "alice@example.com",
                    }
                ]
            },
        )
    )
    respx.get(f"{MAIL_BASE}/accounts/{ACCOUNT_ID}/folders/F1/messages/M1/content").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "messageId": "M1",
                    "subject": "Status",
                    "sender": "alice@example.com",
                    "textBody": "Original body",
                }
            },
        )
    )
    send_route = respx.post(f"{MAIL_BASE}/accounts/{ACCOUNT_ID}/messages").mock(
        return_value=httpx.Response(
            200, json={"data": {"messageId": "F1", "status": "accepted"}}
        )
    )

    result = runner.invoke(
        app,
        [
            "mail",
            "forward",
            "M1",
            "--folder-id",
            "F1",
            "--to",
            "a@example.com",
            "--to",
            "b@example.com",
            "--text",
            "FYI",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(send_route.calls.last.request.content.decode("utf-8"))
    assert payload["fromAddress"] == ACCOUNT_EMAIL
    assert payload["toAddress"] == "a@example.com,b@example.com"
    assert payload["subject"] == "Fwd: Status"
    assert payload["mailFormat"] == "plaintext"
    assert "---------- Forwarded message ----------" in payload["content"]
    assert "From: alice@example.com" in payload["content"]
    assert "Subject: Status" in payload["content"]
    assert payload["content"].startswith("FYI")

    status = json.loads(result.output)
    assert status["status"] == "ok"
    assert status["messageId"] == "F1"
    assert status["sendStatus"] == "accepted"


# ---------------------------------------------------------------------------
# mail attachments
# ---------------------------------------------------------------------------


@respx.mock
def test_mail_attachments_includes_string_attachment_ids(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    """mail attachments should normalize both dict and string attachment entries."""
    respx.get(
        f"{MAIL_BASE}/accounts/{ACCOUNT_ID}/folders/F1/messages/M1/attachmentinfo"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "attachments": [
                        {
                            "attachmentId": "A1",
                            "attachmentName": "report.csv",
                            "attachmentSize": 42,
                        },
                        "A2",
                    ]
                }
            },
        )
    )

    result = runner.invoke(
        app,
        ["mail", "attachments", "M1", "--folder-id", "F1"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output

    atts = json.loads(result.output)
    assert atts == [
        {"attachmentId": "A1", "fileName": "report.csv", "size": 42},
        {"attachmentId": "A2", "fileName": "", "size": 0},
    ]


# ---------------------------------------------------------------------------
# mail download-attachment
# ---------------------------------------------------------------------------


@respx.mock
def test_mail_download_attachment_parse_failure_is_non_fatal(
    tmp_path: Path, mock_config: Path, mock_token_refresh: Any
) -> None:
    """--parse parse failures should return a warning payload, not crash."""
    attachment_route = respx.get(
        f"{MAIL_BASE}/accounts/{ACCOUNT_ID}/folders/F1/messages/M1/attachments/A1"
    ).mock(return_value=httpx.Response(200, content=b"hello"))

    out_file = tmp_path / "exports" / "attachment.txt"

    with patch(
        "zoho_cli.parse.parse_attachment",
        side_effect=RuntimeError("forced parse error"),
    ):
        result = runner.invoke(
            app,
            [
                "mail",
                "download-attachment",
                "M1",
                "A1",
                "--folder-id",
                "F1",
                "--out",
                str(out_file),
                "--parse",
            ],
            env=_cfg_env(mock_config),
        )

    assert attachment_route.called
    assert result.exit_code == 0, result.output
    assert out_file.read_bytes() == b"hello"
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["warning"] == "Parse failed: forced parse error"


@respx.mock
def test_mail_download_attachment_parse_success_returns_structured_json(
    tmp_path: Path, mock_config: Path, mock_token_refresh: Any
) -> None:
    """--parse success should keep stdout as one machine-readable JSON payload."""
    respx.get(
        f"{MAIL_BASE}/accounts/{ACCOUNT_ID}/folders/F1/messages/M1/attachments/A1"
    ).mock(return_value=httpx.Response(200, content=b"hello"))

    out_file = tmp_path / "exports" / "attachment.txt"

    with patch("zoho_cli.parse.parse_attachment", return_value="parsed attachment"):
        result = runner.invoke(
            app,
            [
                "mail",
                "download-attachment",
                "M1",
                "A1",
                "--folder-id",
                "F1",
                "--out",
                str(out_file),
                "--parse",
            ],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["parsed"]["fileName"] == "attachment.txt"
    assert payload["parsed"]["content"] == "parsed attachment"


@respx.mock
def test_mail_download_attachment_accepts_absolute_volumes_out_path(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    """Absolute /Volumes paths should be used directly for --out."""
    attachment_route = respx.get(
        f"{MAIL_BASE}/accounts/{ACCOUNT_ID}/folders/F1/messages/M1/attachments/A1"
    ).mock(return_value=httpx.Response(200, content=b"hello"))

    out_file = Path("/Volumes/Happy Work Drive/zoho/mail-exports/attachment.txt")

    with (
        patch("pathlib.Path.mkdir", autospec=True, return_value=None) as mkdir_mock,
        patch("pathlib.Path.write_bytes", autospec=True, return_value=5) as write_mock,
    ):
        result = runner.invoke(
            app,
            [
                "mail",
                "download-attachment",
                "M1",
                "A1",
                "--folder-id",
                "F1",
                "--out",
                str(out_file),
            ],
            env=_cfg_env(mock_config),
        )

    assert attachment_route.called
    assert result.exit_code == 0, result.output

    mkdir_mock.assert_called_once_with(out_file.parent, parents=True, exist_ok=True)
    write_path, write_data = write_mock.call_args.args
    assert write_path == out_file
    assert write_data == b"hello"

    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["path"].startswith("/Volumes/")
    assert payload["path"].endswith("/zoho/mail-exports/attachment.txt")


# ---------------------------------------------------------------------------
# attachment content
# ---------------------------------------------------------------------------


@respx.mock
def test_attachment_content_with_filename(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    """attachment content should download and parse the named attachment."""
    respx.get(
        f"{MAIL_BASE}/accounts/{ACCOUNT_ID}/folders/F1/messages/M1/attachmentinfo"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "attachments": [
                        {
                            "attachmentId": "A1",
                            "attachmentName": "report.txt",
                            "attachmentSize": 5,
                        }
                    ]
                }
            },
        )
    )
    download_route = respx.get(
        f"{MAIL_BASE}/accounts/{ACCOUNT_ID}/folders/F1/messages/M1/attachments/A1"
    ).mock(return_value=httpx.Response(200, content=b"hello"))

    with patch("zoho_cli.parse.parse_attachment", return_value="parsed attachment"):
        result = runner.invoke(
            app,
            ["attachment", "content", "M1", "report.txt", "--folder-id", "F1"],
            env=_cfg_env(mock_config),
        )

    assert download_route.called
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["messageId"] == "M1"
    assert payload["attachmentId"] == "A1"
    assert payload["fileName"] == "report.txt"
    assert payload["content"] == "parsed attachment"


@respx.mock
def test_attachment_content_missing_filename_returns_not_found(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    """attachment content should error when the requested filename is missing."""
    respx.get(
        f"{MAIL_BASE}/accounts/{ACCOUNT_ID}/folders/F1/messages/M1/attachmentinfo"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "attachments": [
                        {
                            "attachmentId": "A1",
                            "attachmentName": "report.txt",
                            "attachmentSize": 5,
                        }
                    ]
                }
            },
        )
    )

    result = runner.invoke(
        app,
        ["attachment", "content", "M1", "missing.txt", "--folder-id", "F1"],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 1
    assert "not_found" in result.output


# ---------------------------------------------------------------------------
# folders list
# ---------------------------------------------------------------------------


@respx.mock
def test_folders_list(mock_config: Path, mock_token_refresh: Any) -> None:
    """folders list returns exit code 0 and a JSON list of formatted folder objects."""
    respx.get(f"{MAIL_BASE}/accounts/{ACCOUNT_ID}/folders").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "folderId": "F1",
                        "folderName": "Inbox",
                        "folderType": "Inbox",
                        "unreadCount": 5,
                        "messageCount": 100,
                        "isArchived": 0,
                    },
                    {
                        "folderId": "F2",
                        "folderName": "Sent",
                        "folderType": "Sent",
                        "unreadCount": 0,
                        "messageCount": 42,
                        "isArchived": 0,
                    },
                ]
            },
        )
    )
    result = runner.invoke(app, ["folders", "list"], env=_cfg_env(mock_config))
    assert result.exit_code == 0, result.output
    folders = json.loads(result.output)
    assert isinstance(folders, list)
    assert len(folders) == 2
    folder_names = {f["folderName"] for f in folders}
    assert folder_names == {"Inbox", "Sent"}
    # Verify the formatter ran (folderId stringified, counts present)
    inbox = next(f for f in folders if f["folderName"] == "Inbox")
    assert inbox["folderId"] == "F1"
    assert inbox["unreadCount"] == 5


# ---------------------------------------------------------------------------
# cliq status
# ---------------------------------------------------------------------------


def test_cliq_status_scaffold_info(mock_config: Path) -> None:
    """cliq status returns scaffold readiness and inferred base URL."""
    result = runner.invoke(app, ["cliq", "status"], env=_cfg_env(mock_config))
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    assert payload["module"] == "cliq"
    assert payload["scaffold"] == "ready"
    assert payload["hasAccount"] is True
    assert payload["hasAccountId"] is True
    assert payload["baseUrl"] == "https://cliq.zoho.com/api/v2"
    assert payload["oauthReady"] is False
    assert "ZohoCliq.Channels.READ" in payload["missingScopes"]
    assert payload["exportOauthReady"] is False
    assert "ZohoCliq.OrganizationChats.READ" in payload["missingExportScopes"]
    assert payload["exportNext"][0].startswith("re-auth with Cliq export scopes")
    assert (
        f"zoho --config {mock_config} --account test@example.com login --with-cliq --with-cliq-export"
        in payload["exportNext"][0]
    )
    assert (
        f"zoho --config {mock_config} --account test@example.com login --with-cliq --scope"
        " ZohoCliq.OrganizationChats.READ --scope"
        " ZohoCliq.OrganizationMessages.READ"
    ) in payload["exportNext"][0]


def test_cliq_status_check_auth(mock_config: Path, mock_token_refresh: Any) -> None:
    """--check-auth verifies OAuth refresh via shared account wiring."""
    result = runner.invoke(
        app,
        ["cliq", "status", "--check-auth"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    assert payload["auth"] == "ok"


def test_cliq_status_oauth_ready_when_scopes_present(tmp_path: Path) -> None:
    cfg = {
        "client_id": "test_id",
        "client_secret": "test_secret",
        "default_account": ACCOUNT_EMAIL,
        "accounts": {
            ACCOUNT_EMAIL: {
                "accountId": ACCOUNT_ID,
                "scopes": [
                    "ZohoMail.messages.ALL",
                    "ZohoCliq.Channels.READ",
                    "ZohoCliq.Users.READ",
                    "ZohoCliq.Messages.READ",
                    "ZohoCliq.Chats.ALL",
                    "ZohoCliq.Webhooks.CREATE",
                ],
            }
        },
    }
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg))

    result = runner.invoke(app, ["cliq", "status"], env=_cfg_env(cfg_path))
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["oauthReady"] is True
    assert payload["missingScopes"] == []
    assert payload["exportOauthReady"] is False
    assert payload["missingExportScopes"] == [
        "ZohoCliq.OrganizationChats.READ",
        "ZohoCliq.OrganizationMessages.READ",
    ]
    assert (
        payload["exportNext"][1]
        == f"verify export scope readiness: `zoho --config {cfg_path} --account test@example.com cliq status --check-auth`"
    )


def test_cliq_status_export_oauth_ready_when_export_scopes_present(
    tmp_path: Path,
) -> None:
    cfg = {
        "client_id": "test_id",
        "client_secret": "test_secret",
        "default_account": ACCOUNT_EMAIL,
        "accounts": {
            ACCOUNT_EMAIL: {
                "accountId": ACCOUNT_ID,
                "scopes": [
                    "ZohoMail.messages.ALL",
                    "ZohoCliq.Channels.READ",
                    "ZohoCliq.Users.READ",
                    "ZohoCliq.Messages.READ",
                    "ZohoCliq.Chats.ALL",
                    "ZohoCliq.Webhooks.CREATE",
                    "ZohoCliq.OrganizationChats.READ",
                    "ZohoCliq.OrganizationMessages.READ",
                ],
            }
        },
    }
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg))

    result = runner.invoke(app, ["cliq", "status"], env=_cfg_env(cfg_path))
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["oauthReady"] is True
    assert payload["missingScopes"] == []
    assert payload["exportOauthReady"] is True
    assert payload["missingExportScopes"] == []
    assert "exportNext" not in payload


def test_cliq_status_export_next_includes_network_hint(tmp_path: Path) -> None:
    cfg = {
        "client_id": "test_id",
        "client_secret": "test_secret",
        "default_account": ACCOUNT_EMAIL,
        "accounts": {
            ACCOUNT_EMAIL: {
                "accountId": ACCOUNT_ID,
                "scopes": [
                    "ZohoMail.messages.ALL",
                    "ZohoCliq.Channels.READ",
                    "ZohoCliq.Users.READ",
                    "ZohoCliq.Messages.READ",
                    "ZohoCliq.Chats.ALL",
                    "ZohoCliq.Webhooks.CREATE",
                ],
            }
        },
    }
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg))

    result = runner.invoke(
        app,
        ["cliq", "status", "--network", "happydistrouklimited"],
        env=_cfg_env(cfg_path),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["exportOauthReady"] is False
    assert payload["exportNext"][1].endswith(
        f"`zoho --config {cfg_path} --account test@example.com cliq status --check-auth --network happydistrouklimited`"
    )


@respx.mock
def test_cliq_capabilities(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.get("https://cliq.zoho.com/api/v2/channels").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    respx.get("https://cliq.zoho.com/api/v2/users").mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    result = runner.invoke(app, ["cliq", "capabilities"], env=_cfg_env(mock_config))
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    assert payload["module"] == "cliq"
    assert payload["capabilityStage"] == "cliq-100"
    assert payload["summary"]["total"] == 2
    assert payload["inputs"]["messageId"] == ""


@respx.mock
def test_cliq_capabilities_with_message_probe(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/channels").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    respx.get("https://cliq.zoho.com/api/v2/users").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(200, json={"data": {"chat_id": "CT_1"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/O1/messages").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M1"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/files").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/attachments").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/O1/messages/M1").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M1"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/O1/messages/M1/files").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/O1/messages/M1/attachments").mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "capabilities",
            "--channel-id",
            "O1",
            "--message-id",
            "M1",
        ],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    assert payload["inputs"]["messageId"] == "M1"
    assert payload["summary"]["total"] == 11


def test_cliq_capabilities_message_probe_requires_channel(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    result = runner.invoke(
        app,
        ["cliq", "capabilities", "--message-id", "M1"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 1
    assert "invalid_destination" in result.output


@respx.mock
def test_cliq_messages_from_channel(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(200, json={"data": {"chat_id": "CT_1"}})
    )
    route = respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "M1", "text": "hello"}]})
    )

    result = runner.invoke(
        app,
        ["cliq", "messages", "--channel-id", "O1", "--limit", "2"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["chatId"] == "CT_1"
    assert payload["count"] == 1
    assert payload["typedMessages"][0]["messageId"] == "M1"
    assert "text" in payload["typedMessages"][0]["types"]
    assert dict(route.calls.last.request.url.params) == {"limit": "2"}


@respx.mock
def test_cliq_search_from_channel(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(200, json={"data": {"chat_id": "CT_1"}})
    )
    route = respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/search").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "M1"}]})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "search",
            "deploy",
            "--channel-id",
            "O1",
            "--limit",
            "3",
            "--from-time",
            "1710000000",
            "--to-time",
            "1710009999",
        ],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["chatId"] == "CT_1"
    assert payload["query"] == "deploy"
    assert payload["count"] == 1
    assert dict(route.calls.last.request.url.params)["limit"] == "3"


def test_cliq_search_requires_destination(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    result = runner.invoke(
        app,
        ["cliq", "search", "deploy"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 1
    assert "invalid_destination" in result.output


@respx.mock
def test_cliq_file_from_channel(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(200, json={"data": {"chat_id": "CT_1"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/files").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "F1"}]})
    )

    result = runner.invoke(
        app,
        ["cliq", "file", "M1", "--channel-id", "O1"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["chatId"] == "CT_1"
    assert payload["messageId"] == "M1"
    assert payload["sourcePath"] == "/chats/CT_1/messages/M1/files"
    assert payload["count"] == 1
    assert payload["files"][0]["id"] == "F1"
    assert payload["messageTypes"] == []
    assert payload["retrievalResult"] == "attachments_found"


@respx.mock
def test_cliq_file_reports_media_visible_without_attachment_payload(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(200, json={"data": {"chat_id": "CT_1"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "id": "M1",
                    "type": "card",
                    "content": {"text": "remote image"},
                    "unfurled_details": {
                        "url": "https://upload.wikimedia.org/wikipedia/commons/3/3f/JPEG_example_flower.jpg"
                    },
                }
            },
        )
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/files").mock(
        return_value=httpx.Response(
            400,
            json={
                "code": "message_attachment_not_found",
                "message": "No attachment found for this message.",
            },
        )
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/attachments").mock(
        return_value=httpx.Response(
            400,
            json={
                "code": "no_attachments_found",
                "message": "No attachment found for this message.",
            },
        )
    )

    result = runner.invoke(
        app,
        ["cliq", "file", "M1", "--channel-id", "O1"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 0
    assert "image" in payload["messageTypes"]
    assert payload["retrievalResult"] == "media_visible_without_attachment_payload"
    assert payload["sourcePath"] == "/chats/CT_1/messages/M1/files"


def test_cliq_file_requires_destination(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    result = runner.invoke(
        app,
        ["cliq", "file", "M1"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 1
    assert "invalid_destination" in result.output


@respx.mock
def test_cliq_message_get_from_channel(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(200, json={"data": {"chat_id": "CT_1"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M1", "text": "hello"}})
    )

    result = runner.invoke(
        app,
        ["cliq", "message", "M1", "--channel-id", "O1"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["chatId"] == "CT_1"
    assert payload["message"]["id"] == "M1"
    assert "text" in payload["messageTypes"]


@respx.mock
def test_cliq_context_with_anchor(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(200, json={"data": {"chat_id": "CT_1"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages").mock(
        return_value=httpx.Response(
            200, json={"data": [{"id": "M3"}, {"id": "M2"}, {"id": "M1"}]}
        )
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "text": "middle"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "context",
            "--channel-id",
            "O1",
            "--message-id",
            "M2",
            "--before",
            "1",
            "--after",
            "1",
            "--limit",
            "10",
        ],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["anchorInWindow"] is True
    assert len(payload["messages"]) == 3
    assert len(payload["typedMessages"]) == 3


@respx.mock
def test_cliq_context_from_chat_id_typed_dm_matrix(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_DM/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "M3",
                        "attachments": [
                            {
                                "mimeType": "audio/ogg",
                                "url": "https://example.com/voice-note.ogg",
                            }
                        ],
                    },
                    {
                        "id": "M2",
                        "attachments": [
                            {
                                "contentType": "image/png",
                                "url": "https://example.com/pic.png",
                            }
                        ],
                    },
                    {"id": "M1", "text": "plain text ping"},
                ]
            },
        )
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "context",
            "--chat-id",
            "CT_DM",
            "--before",
            "2",
            "--after",
            "0",
            "--limit",
            "10",
        ],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    assert payload["chatId"] == "CT_DM"
    assert payload["channelId"] == ""

    typed_by_id = {
        item["messageId"]: item["types"] for item in payload["typedMessages"]
    }
    assert typed_by_id["M3"] == ["voice"]
    assert typed_by_id["M2"] == ["image"]
    assert typed_by_id["M1"] == ["text"]


@respx.mock
def test_cliq_watch_context_from_channel(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(200, json={"data": {"chat_id": "CT_1"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"id": "M3", "text": "third"},
                    {"id": "M2", "text": "second"},
                    {"id": "M1", "text": "first"},
                ]
            },
        )
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-context",
            "--channel-id",
            "O1",
            "--since-message-id",
            "M2",
            "--limit",
            "10",
            "--max-messages",
            "5",
        ],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["chatId"] == "CT_1"
    assert payload["cursor"]["cursorFound"] is True
    assert payload["newCount"] == 1
    assert payload["watchIntake"]["triggerMode"] == "web-notification-first"
    assert payload["watchIntake"]["pollFallback"]["mode"] == "adaptive"
    assert payload["watchIntake"]["consume"]["actionId"] == "watch-loop"
    assert payload["operatorWorkflow"]["packageId"] == "cliq-195"
    assert (
        payload["operatorWorkflow"]["externalEscalation"]["actionHint"][
            "bridgeActionId"
        ]
        == "notify-mail"
    )
    assert (
        payload["operatorWorkflow"]["externalEscalation"]["handoff"]["contractId"]
        == "cliq-195-escalation-handoff-v1"
    )
    assert payload["operatorWorkflow"]["externalEscalation"]["handoff"][
        "payloadTemplate"
    ] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "recipient": "",
        "summary": "",
        "reason": "",
    }
    assert payload["operatorWorkflow"]["externalEscalation"]["handoff"][
        "envelopeHints"
    ] == {
        "templateRoot": "payloadTemplate",
        "targetPath": "payloadTemplate.target",
        "fieldMap": {
            "to": "payloadTemplate.recipient",
            "subject": "payloadTemplate.summary",
            "body": "payloadTemplate.reason",
        },
    }
    assert payload["operatorWorkflow"]["externalEscalation"]["handoff"][
        "envelopeDefaults"
    ] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "to": "",
        "subject": "",
        "body": "",
    }
    assert payload["escalationEnvelope"] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "to": "",
        "subject": "",
        "body": "",
    }
    assert payload["escalationEnvelopeMetadata"] == {
        "source": "top-level-alias",
        "sourcePath": "escalationEnvelope",
        "fromTopLevelAlias": True,
        "fromNestedFallback": False,
        "usedFieldFallback": False,
        "fieldSources": {
            "target": {
                "source": "top-level-alias",
                "sourcePath": "escalationEnvelope.target",
                "fromTopLevelAlias": True,
                "fromNestedFallback": False,
                "usedFallback": False,
            },
            "to": {
                "source": "top-level-alias",
                "sourcePath": "escalationEnvelope.to",
                "fromTopLevelAlias": True,
                "fromNestedFallback": False,
                "usedFallback": False,
            },
            "subject": {
                "source": "top-level-alias",
                "sourcePath": "escalationEnvelope.subject",
                "fromTopLevelAlias": True,
                "fromNestedFallback": False,
                "usedFallback": False,
            },
            "body": {
                "source": "top-level-alias",
                "sourcePath": "escalationEnvelope.body",
                "fromTopLevelAlias": True,
                "fromNestedFallback": False,
                "usedFallback": False,
            },
        },
    }
    assert payload["messages"][0]["messageId"] == "M3"


@respx.mock
def test_cliq_watch_context_watch_act_second_pass_noop_after_cursor_advance(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    channel_route = respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(200, json={"data": {"chat_id": "CT_1"}})
    )
    messages_route = respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"id": "M3", "text": "third"},
                    {"id": "M2", "text": "second"},
                    {"id": "M1", "text": "first"},
                ]
            },
        )
    )

    first_watch_result = runner.invoke(
        app,
        [
            "cliq",
            "watch-context",
            "--channel-id",
            "O1",
            "--since-message-id",
            "M2",
            "--limit",
            "10",
            "--max-messages",
            "5",
        ],
        env=_cfg_env(mock_config),
    )
    assert first_watch_result.exit_code == 0, first_watch_result.output
    first_watch_payload = json.loads(first_watch_result.output)
    assert first_watch_payload["newCount"] == 1
    assert first_watch_payload["messages"] == [
        {
            "messageId": "M3",
            "senderId": "",
            "text": "third",
            "timestamp": "",
            "raw": {"id": "M3", "text": "third"},
        }
    ]
    assert (
        first_watch_payload["watchIntake"]["consume"]["ackAction"] == "read-ack-latest"
    )
    assert first_watch_payload["operatorWorkflow"]["packageId"] == "cliq-195"

    reply_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M3/reply"
    ).mock(return_value=httpx.Response(200, json={"data": {"id": "M4"}}))
    read_ack_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M3/read"
    ).mock(
        return_value=httpx.Response(200, json={"data": {"id": "M3", "status": "ok"}})
    )

    first_act_result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--text",
            "ack",
        ],
        input=json.dumps(first_watch_payload),
        env=_cfg_env(mock_config),
    )
    assert first_act_result.exit_code == 0, first_act_result.output
    assert reply_route.called
    assert read_ack_route.called
    first_act_payload = json.loads(first_act_result.output)
    assert first_act_payload["applied"] is True
    assert first_act_payload["targetMessageId"] == "M3"
    assert first_act_payload["readAck"]["required"] is True
    assert first_act_payload["readAck"]["applied"] is True
    assert first_act_payload["watchIntake"]["consume"]["ackAction"] == "read-ack-latest"
    assert first_act_payload["operatorWorkflow"]["packageId"] == "cliq-195"

    second_watch_result = runner.invoke(
        app,
        [
            "cliq",
            "watch-context",
            "--channel-id",
            "O1",
            "--since-message-id",
            first_watch_payload["cursor"]["nextSinceMessageId"],
            "--limit",
            "10",
            "--max-messages",
            "5",
        ],
        env=_cfg_env(mock_config),
    )
    assert second_watch_result.exit_code == 0, second_watch_result.output
    second_watch_payload = json.loads(second_watch_result.output)
    assert second_watch_payload["cursor"]["cursorFound"] is True
    assert second_watch_payload["newCount"] == 0
    assert second_watch_payload["messages"] == []
    assert (
        second_watch_payload["watchIntake"]["consume"]["ackAction"] == "read-ack-latest"
    )
    assert second_watch_payload["operatorWorkflow"]["packageId"] == "cliq-195"

    second_act_result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--text",
            "ack",
        ],
        input=json.dumps(second_watch_payload),
        env=_cfg_env(mock_config),
    )
    assert second_act_result.exit_code == 0, second_act_result.output
    second_act_payload = json.loads(second_act_result.output)
    assert second_act_payload["status"] == "ok"
    assert second_act_payload["applied"] is False
    assert second_act_payload["reason"] == "no_new_messages"
    assert second_act_payload["readAck"]["required"] is True
    assert second_act_payload["readAck"]["applied"] is False
    assert second_act_payload["readAck"]["reason"] == "no_new_messages"
    assert channel_route.call_count == 2
    assert messages_route.call_count == 2


def test_cliq_watch_context_requires_destination(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    result = runner.invoke(app, ["cliq", "watch-context"], env=_cfg_env(mock_config))
    assert result.exit_code == 1
    assert "invalid_destination" in result.output


@respx.mock
def test_cliq_watch_act_replies_to_latest_message(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "newCount": 2,
                "messages": [
                    {"messageId": "M1", "senderId": "U1", "text": "first"},
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/reply"
    ).mock(return_value=httpx.Response(200, json={"data": {"id": "M3"}}))
    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--text",
            "ack",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["applied"] is True
    assert payload["targetMessageId"] == "M2"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "default:reply-latest"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "default:reply-latest",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_preserves_watch_intake_metadata_in_result(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "watchIntake": {
                    "triggerMode": "web-notification-first",
                    "consume": {
                        "ackAction": "read-ack-latest",
                        "ackRequired": True,
                    },
                },
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "defaultAction": "notify-mail",
                        "actionHint": {
                            "watchActAction": "read-ack-latest",
                            "bridgeActionId": "notify-mail",
                        },
                        "handoff": {
                            "contractId": "cliq-195-escalation-handoff-v1",
                            "payloadTemplate": {
                                "target": {
                                    "kind": "external-contact",
                                    "channel": "mail",
                                    "defaultAction": "notify-mail",
                                },
                                "recipient": "",
                                "summary": "",
                                "reason": "",
                            },
                            "envelopeHints": {
                                "templateRoot": "payloadTemplate",
                                "targetPath": "payloadTemplate.target",
                                "fieldMap": {
                                    "to": "payloadTemplate.recipient",
                                    "subject": "payloadTemplate.summary",
                                    "body": "payloadTemplate.reason",
                                },
                            },
                            "envelopeDefaults": {
                                "target": {
                                    "kind": "external-contact",
                                    "channel": "mail",
                                    "defaultAction": "notify-mail",
                                },
                                "to": "",
                                "subject": "",
                                "body": "",
                            },
                        },
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/reply"
    ).mock(return_value=httpx.Response(200, json={"data": {"id": "M3"}}))
    ack_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read"
    ).mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--text",
            "ack",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    assert ack_route.called
    payload = json.loads(result.output)
    assert payload["watchIntake"]["triggerMode"] == "web-notification-first"
    assert payload["watchIntake"]["consume"]["ackAction"] == "read-ack-latest"
    assert payload["operatorWorkflow"]["packageId"] == "cliq-195"
    assert (
        payload["operatorWorkflow"]["externalEscalation"]["defaultAction"]
        == "notify-mail"
    )
    assert (
        payload["operatorWorkflow"]["externalEscalation"]["actionHint"][
            "watchActAction"
        ]
        == "read-ack-latest"
    )
    assert (
        payload["operatorWorkflow"]["externalEscalation"]["handoff"]["contractId"]
        == "cliq-195-escalation-handoff-v1"
    )
    assert payload["operatorWorkflow"]["externalEscalation"]["handoff"][
        "payloadTemplate"
    ] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "recipient": "",
        "summary": "",
        "reason": "",
    }
    assert payload["operatorWorkflow"]["externalEscalation"]["handoff"][
        "envelopeHints"
    ] == {
        "templateRoot": "payloadTemplate",
        "targetPath": "payloadTemplate.target",
        "fieldMap": {
            "to": "payloadTemplate.recipient",
            "subject": "payloadTemplate.summary",
            "body": "payloadTemplate.reason",
        },
    }
    assert payload["operatorWorkflow"]["externalEscalation"]["handoff"][
        "envelopeDefaults"
    ] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "to": "",
        "subject": "",
        "body": "",
    }
    assert payload["readAck"]["required"] is True
    assert payload["readAck"]["applied"] is True
    assert payload["readAck"]["messageId"] == "M2"
    assert payload["escalationEnvelope"] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "to": "",
        "subject": "",
        "body": "",
    }


@respx.mock
def test_cliq_watch_act_prefers_top_level_escalation_envelope(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "escalationEnvelope": {
                    "to": "ops@happy-distro.co.uk",
                },
                "operatorWorkflow": {
                    "externalEscalation": {
                        "handoff": {
                            "envelopeDefaults": {
                                "target": {
                                    "kind": "external-contact",
                                    "channel": "mail",
                                    "defaultAction": "notify-mail",
                                },
                                "to": "fallback@happy-distro.co.uk",
                                "subject": "Fallback subject",
                                "body": "Fallback body",
                            }
                        }
                    }
                },
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/reply"
    ).mock(return_value=httpx.Response(200, json={"data": {"id": "M3"}}))

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--text",
            "ack",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["escalationEnvelope"] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "to": "ops@happy-distro.co.uk",
        "subject": "Fallback subject",
        "body": "Fallback body",
    }
    assert payload["escalationEnvelopeMetadata"] == {
        "source": "mixed",
        "sourcePath": "mixed",
        "fromTopLevelAlias": True,
        "fromNestedFallback": True,
        "usedFieldFallback": True,
        "fieldSources": {
            "target": {
                "source": "nested-envelope-defaults",
                "sourcePath": (
                    "operatorWorkflow.externalEscalation.handoff."
                    "envelopeDefaults.target"
                ),
                "fromTopLevelAlias": False,
                "fromNestedFallback": True,
                "usedFallback": True,
            },
            "to": {
                "source": "top-level-alias",
                "sourcePath": "escalationEnvelope.to",
                "fromTopLevelAlias": True,
                "fromNestedFallback": False,
                "usedFallback": False,
            },
            "subject": {
                "source": "nested-envelope-defaults",
                "sourcePath": (
                    "operatorWorkflow.externalEscalation.handoff."
                    "envelopeDefaults.subject"
                ),
                "fromTopLevelAlias": False,
                "fromNestedFallback": True,
                "usedFallback": True,
            },
            "body": {
                "source": "nested-envelope-defaults",
                "sourcePath": (
                    "operatorWorkflow.externalEscalation.handoff.envelopeDefaults.body"
                ),
                "fromTopLevelAlias": False,
                "fromNestedFallback": True,
                "usedFallback": True,
            },
        },
    }


@respx.mock
def test_cliq_watch_act_reads_stdin_when_watch_file_not_provided(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/reply"
    ).mock(return_value=httpx.Response(200, json={"data": {"id": "M3"}}))

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--text",
            "ack",
        ],
        input=json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "newCount": 2,
                "messages": [
                    {"messageId": "M1", "senderId": "U1", "text": "first"},
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        ),
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["applied"] is True
    assert payload["targetMessageId"] == "M2"


def test_cliq_watch_act_no_messages_returns_noop(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch-empty.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "newCount": 0,
                "messages": [],
            }
        )
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--text",
            "ack",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["applied"] is False
    assert payload["reason"] == "no_new_messages"


def test_cliq_watch_act_reply_latest_requires_text(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 1
    assert "invalid_text" in result.output


@respx.mock
def test_cliq_watch_act_read_ack_latest(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "newCount": 2,
                "messages": [
                    {"messageId": "M1", "senderId": "U1", "text": "first"},
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--action",
            "read-ack-latest",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["action"] == "read-ack-latest"
    assert payload["applied"] is True
    assert payload["targetMessageId"] == "M2"
    assert payload["actionSource"] == "explicit-override"
    assert payload["actionSourcePath"] == "--action"
    assert payload["actionSourceMetadata"] == {
        "source": "explicit-override",
        "sourcePath": "--action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": False,
        "fromExplicitOverride": True,
    }


@respx.mock
def test_cliq_watch_act_uses_top_level_watch_payload_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "actionId": "read-ack-latest",
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.actionId"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_top_level_watch_payload_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "actionID": "read-ack-latest",
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.actionID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_top_level_watch_payload_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "actionid": "read-ack-latest",
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.actionid"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_top_level_watch_payload_action_snake_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "action_id": "read-ack-latest",
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.action_id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_top_level_watch_payload_action_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "action": "read-ack-latest",
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.action"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_top_level_watch_payload_default_action_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "defaultAction": "read-ack-latest",
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.defaultAction"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.defaultAction",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_top_level_watch_payload_default_action_snake_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "default_action": "read-ack-latest",
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.default_action"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.default_action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_top_level_watch_payload_default_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "defaultActionId": "read-ack-latest",
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.defaultActionId"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.defaultActionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_top_level_watch_payload_default_action_snake_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "default_action_id": "read-ack-latest",
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.default_action_id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.default_action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_top_level_watch_payload_default_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "defaultActionID": "read-ack-latest",
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.defaultActionID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.defaultActionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_top_level_watch_payload_default_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "defaultAction_id": "read-ack-latest",
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.defaultAction_id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.defaultAction_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_top_level_watch_payload_default_action_snake_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "default_actionId": "read-ack-latest",
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.default_actionId"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.default_actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_top_level_watch_payload_default_action_snake_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "default_actionID": "read-ack-latest",
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.default_actionID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.default_actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_top_level_watch_payload_default_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "defaultActionid": "read-ack-latest",
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.defaultActionid"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.defaultActionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_top_level_watch_payload_default_action_snake_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "default_actionid": "read-ack-latest",
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.default_actionid"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.default_actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_top_level_watch_payload_bridge_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "bridgeActionId": "read-ack-latest",
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.bridgeActionId"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.bridgeActionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_top_level_watch_payload_bridge_action_snake_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "bridge_action_id": "read-ack-latest",
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.bridge_action_id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.bridge_action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_top_level_watch_payload_bridge_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "bridgeAction_id": "read-ack-latest",
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.bridgeAction_id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.bridgeAction_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_top_level_watch_payload_bridge_action_snake_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "bridge_actionId": "read-ack-latest",
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.bridge_actionId"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.bridge_actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_top_level_watch_payload_bridge_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "bridgeActionid": "read-ack-latest",
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.bridgeActionid"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.bridgeActionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_top_level_watch_payload_bridge_action_snake_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "bridge_actionid": "read-ack-latest",
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.bridge_actionid"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.bridge_actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_top_level_watch_payload_bridge_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "bridgeActionID": "read-ack-latest",
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.bridgeActionID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.bridgeActionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_top_level_watch_payload_bridge_action_snake_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "bridge_actionID": "read-ack-latest",
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.bridge_actionID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.bridge_actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_uses_watch_hint(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "actionHint": {
                            "watchActAction": "read-ack-latest",
                        }
                    },
                },
                "newCount": 2,
                "messages": [
                    {"messageId": "M1", "senderId": "U1", "text": "first"},
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["action"] == "read-ack-latest"
    assert payload["applied"] is True
    assert payload["targetMessageId"] == "M2"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.watchActAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.watchActAction",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_operator_workflow_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "action_hint": {
                            "watch_act_action": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.watch_act_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.watch_act_action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_action_hint_watch_act_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "watchActAction": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.watchActAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.watchActAction",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_action_hint_watch_act_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "watch_act_action": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.watch_act_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.watch_act_action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_action_hint_watch_act_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "watch_act_action": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.watch_act_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.watch_act_action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_action_hint_watch_act_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "watchActAction": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.watchActAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.watchActAction",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_top_level_watch_act_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "watch_act_action": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.watch_act_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.watch_act_action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_top_level_watch_act_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "watchActAction": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.watchActAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.watchActAction",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_top_level_watch_act_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "watchActAction": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.watchActAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.watchActAction",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_top_level_watch_act_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "watch_act_action": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.watch_act_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.watch_act_action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_default_action_fallback(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "action_hint": {
                            "default_action": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.default_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.default_action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_action_hint_default_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "defaultAction": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.defaultAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.defaultAction",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_action_hint_default_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "default_action": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.default_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.default_action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_action_hint_default_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "defaultActionId": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.defaultActionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.defaultActionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_action_hint_default_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "default_action_id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.default_action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.default_action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_action_hint_default_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "defaultActionID": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.defaultActionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.defaultActionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_action_hint_default_action_snake_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "default_actionID": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.default_actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.default_actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_action_hint_default_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "defaultActionID": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.defaultActionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.defaultActionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_action_hint_default_action_snake_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "default_actionID": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.default_actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.default_actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_action_hint_default_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "defaultAction_id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.defaultAction_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.defaultAction_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_action_hint_default_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "default_actionId": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.default_actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.default_actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_action_hint_default_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "defaultAction_id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.defaultAction_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.defaultAction_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_action_hint_default_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "default_actionId": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.default_actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.default_actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_action_hint_default_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "default_action": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.default_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.default_action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_action_hint_default_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "defaultAction": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.defaultAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.defaultAction",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_top_level_default_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "defaultAction": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.defaultAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.defaultAction",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_top_level_default_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "default_action": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.default_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.default_action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_top_level_default_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "defaultAction": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.defaultAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.defaultAction",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_top_level_default_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "default_action": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.default_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.default_action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_top_level_default_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "defaultAction_id": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.defaultAction_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.defaultAction_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_top_level_default_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "default_actionId": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.default_actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.default_actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_top_level_default_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "defaultActionId": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.defaultActionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.defaultActionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_top_level_default_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "default-action-id": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.default-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.default-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_top_level_default_action_kebab_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "default-action": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.default-action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.default-action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_top_level_default_action_kebab_compact_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "default-actionid": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.default-actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.default-actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_top_level_default_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "default-actionID": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.default-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.default-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_top_level_default_action_kebab_mixed_case_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "default-actionId": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.default-actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.default-actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_top_level_default_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "default-actionID": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.default-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.default-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_top_level_default_action_kebab_mixed_case_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "default-actionId": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.default-actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.default-actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_top_level_default_action_kebab_compact_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "default-actionid": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.default-actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.default-actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_top_level_default_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "default_action_id": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.default_action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.default_action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_top_level_default_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "defaultActionID": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.defaultActionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.defaultActionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_top_level_default_action_snake_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "default_actionID": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.default_actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.default_actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_top_level_default_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "defaultActionid": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.defaultActionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.defaultActionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_top_level_default_action_snake_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "default_actionid": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.default_actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.default_actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_camel_case_escalation_alias_top_level_default_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "default-action-id": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.default-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.default-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_camel_case_escalation_alias_top_level_default_action_kebab_compact_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "default-actionid": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.default-actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.default-actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_camel_case_escalation_alias_top_level_default_action_kebab_mixed_case_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "default-actionId": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.default-actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.default-actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_camel_case_escalation_alias_top_level_default_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "default-actionID": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.default-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.default-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_camel_case_escalation_alias_top_level_default_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "defaultActionid": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.defaultActionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.defaultActionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_snake_case_escalation_alias_top_level_default_action_snake_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "default_actionid": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.default_actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.default_actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_snake_case_escalation_alias_top_level_default_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "default-action-id": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.default-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.default-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_snake_case_escalation_alias_top_level_default_action_kebab_compact_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "default-actionid": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.default-actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.default-actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_snake_case_escalation_alias_top_level_default_action_kebab_mixed_case_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "default-actionId": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.default-actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.default-actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_snake_case_escalation_alias_top_level_default_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "default-actionID": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.default-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.default-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_action_hint_top_level_action_fallback(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "action_hint": {
                            "action": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_action_hint_top_level_action_fallback(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "actionHint": {
                            "action": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_action_hint_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "action": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_action_hint_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "action": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_action_hint_top_level_action_id_fallback(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "action_hint": {
                            "action_id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_action_hint_top_level_action_id_fallback(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "actionHint": {
                            "actionId": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_action_hint_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "actionId": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_action_hint_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "action_id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_action_hint_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "actionId": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_action_hint_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "action_id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_camel_case_escalation_alias_action_hint_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "actionId": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_snake_case_escalation_alias_action_hint_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "action_id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_action_hint_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "actionID": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_action_hint_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "actionID": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_action_hint_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "actionID": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_action_hint_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "actionID": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_camel_case_escalation_alias_action_hint_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "actionID": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_snake_case_escalation_alias_action_hint_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "actionID": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_action_hint_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "actionid": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_action_hint_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "actionid": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_camel_case_escalation_alias_action_hint_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "actionid": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_snake_case_escalation_alias_action_hint_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "actionid": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_action_hint_top_level_bridge_action_id_fallback(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "action_hint": {
                            "bridge_action_id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.bridge_action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.bridge_action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_action_hint_top_level_bridge_action_id_camel_case_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "action_hint": {
                            "bridgeActionId": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.bridgeActionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.bridgeActionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_action_hint_top_level_bridge_action_id_fallback(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "actionHint": {
                            "bridgeActionId": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.bridgeActionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.bridgeActionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_action_hint_top_level_bridge_action_id_snake_case_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "actionHint": {
                            "bridge_action_id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.bridge_action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.bridge_action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_action_hint_bridge_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "bridgeActionId": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.bridgeActionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.bridgeActionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_action_hint_bridge_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "bridge_action_id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.bridge_action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.bridge_action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_action_hint_bridge_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "bridgeAction_id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.bridgeAction_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.bridgeAction_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_action_hint_bridge_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "bridge_actionId": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.bridge_actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.bridge_actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_action_hint_bridge_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "bridgeAction_id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.bridgeAction_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.bridgeAction_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_action_hint_bridge_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "bridge_actionId": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.bridge_actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.bridge_actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_action_hint_bridge_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "bridge-action-id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.bridge-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.bridge-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_action_hint_bridge_action_kebab_snake_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "bridge-action_id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.bridge-action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.bridge-action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_action_hint_bridge_action_kebab_snake_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "bridge-action_id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.bridge-action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.bridge-action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_action_hint_bridge_action_kebab_compact_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "bridge-actionid": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.bridge-actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.bridge-actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_action_hint_bridge_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "bridge-action-id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.bridge-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.bridge-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_action_hint_bridge_action_kebab_compact_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "bridge-actionid": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.bridge-actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.bridge-actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_action_hint_bridge_action_kebab_mixed_case_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "bridge-actionId": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.bridge-actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.bridge-actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_action_hint_bridge_action_kebab_mixed_case_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "bridge-actionId": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.bridge-actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.bridge-actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_camel_case_escalation_alias_action_hint_bridge_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "actionHint": {
                            "bridge-action-id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.bridge-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.bridge-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_camel_case_escalation_alias_action_hint_bridge_action_kebab_mixed_case_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "actionHint": {
                            "bridge-actionId": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.bridge-actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.bridge-actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_camel_case_escalation_alias_action_hint_bridge_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "actionHint": {
                            "bridge-actionID": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.bridge-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.bridge-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_snake_case_escalation_alias_action_hint_bridge_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "action_hint": {
                            "bridge-action-id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.bridge-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.bridge-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_snake_case_escalation_alias_action_hint_bridge_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "action_hint": {
                            "bridge-actionID": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.bridge-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.bridge-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_action_hint_bridge_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "bridge-actionID": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.bridge-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.bridge-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_action_hint_bridge_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "bridge-actionID": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.bridge-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.bridge-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_action_hint_bridge_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "bridgeActionID": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.bridgeActionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.bridgeActionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_action_hint_bridge_action_snake_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "bridge_actionID": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.bridge_actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.bridge_actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_action_hint_bridge_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "bridgeActionid": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.bridgeActionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.bridgeActionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_action_hint_bridge_action_snake_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "bridge_actionid": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.bridge_actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.bridge_actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_camel_case_escalation_alias_action_hint_bridge_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "actionHint": {
                            "bridgeActionid": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.bridgeActionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.bridgeActionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_snake_case_escalation_alias_action_hint_bridge_action_snake_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "action_hint": {
                            "bridge_actionid": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.bridge_actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.bridge_actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_action_hint_default_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "defaultActionid": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.defaultActionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.defaultActionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_action_hint_default_action_snake_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "default_actionid": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.default_actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.default_actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_camel_case_escalation_alias_action_hint_default_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "defaultActionid": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.defaultActionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.defaultActionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_snake_case_escalation_alias_action_hint_default_action_snake_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "default_actionid": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.default_actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.default_actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_action_hint_default_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "default-action-id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.default-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.default-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_action_hint_default_action_kebab_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "default-action": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.default-action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.default-action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_action_hint_default_action_kebab_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "default-action": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.default-action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.default-action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_action_hint_default_action_kebab_compact_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "default-actionid": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.default-actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.default-actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_action_hint_default_action_kebab_compact_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "default-actionid": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.default-actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.default-actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_camel_case_escalation_alias_action_hint_default_action_kebab_compact_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "actionHint": {
                            "default-actionid": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.default-actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.default-actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_action_hint_default_action_kebab_mixed_case_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "default-actionId": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.default-actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.default-actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_action_hint_default_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "default-actionID": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.default-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.default-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_camel_case_escalation_alias_action_hint_default_action_kebab_mixed_case_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "actionHint": {
                            "default-actionId": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.default-actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.default-actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_camel_case_escalation_alias_action_hint_default_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "actionHint": {
                            "default-actionID": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.default-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.default-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_snake_case_escalation_alias_action_hint_default_action_kebab_compact_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "action_hint": {
                            "default-actionid": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.default-actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.default-actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_snake_case_escalation_alias_action_hint_default_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "action_hint": {
                            "default-actionID": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.default-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.default-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_snake_case_escalation_alias_action_hint_default_action_kebab_mixed_case_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "action_hint": {
                            "default-actionId": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.default-actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.default-actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_action_hint_default_action_kebab_mixed_case_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "default-actionId": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.default-actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.default-actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_action_hint_default_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "default-actionID": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.default-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.default-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_action_hint_default_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "default-action-id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.default-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.default-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_camel_case_escalation_alias_action_hint_default_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "actionHint": {
                            "default-action-id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.default-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.default-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_snake_case_escalation_alias_action_hint_default_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "action_hint": {
                            "default-action-id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.default-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.default-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_action_hint_bridge_action_id_camel_case_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionHint": {
                            "bridgeActionId": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.bridgeActionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.bridgeActionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_action_hint_bridge_action_id_snake_case_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_hint": {
                            "bridge_action_id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.bridge_action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.bridge_action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_top_level_action_fallback(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert payload["actionSourcePath"] == "operatorWorkflow.externalEscalation.action"
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_top_level_action_fallback(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "action": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert payload["actionSourcePath"] == "operator_workflow.external_escalation.action"
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_top_level_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "action": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert payload["actionSourcePath"] == "operatorWorkflow.external_escalation.action"
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_top_level_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert payload["actionSourcePath"] == "operator_workflow.externalEscalation.action"
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_top_level_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionId": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.external_escalation.actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_top_level_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "action_id": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.externalEscalation.action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_top_level_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionID": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.external_escalation.actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_top_level_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "actionID": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.externalEscalation.actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_top_level_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionid": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.external_escalation.actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_top_level_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "actionid": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.externalEscalation.actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_camel_case_escalation_alias_top_level_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "actionid": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert payload["actionSourcePath"] == "operatorWorkflow.externalEscalation.actionid"
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_snake_case_escalation_alias_top_level_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "actionid": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.external_escalation.actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_top_level_bridge_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "bridge_action_id": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.bridge_action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.bridge_action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_top_level_bridge_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "bridgeActionId": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.bridgeActionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.bridgeActionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_top_level_bridge_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "bridge-action-id": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.bridge-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.bridge-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_top_level_bridge_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "bridge-action-id": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.bridge-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.bridge-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_camel_case_escalation_alias_top_level_bridge_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "bridge-action-id": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.bridge-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.bridge-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_top_level_bridge_action_kebab_compact_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "bridge-actionid": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.bridge-actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.bridge-actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_top_level_bridge_action_kebab_snake_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "bridge-action_id": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.bridge-action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.bridge-action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_top_level_bridge_action_kebab_snake_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "bridge-action_id": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.bridge-action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.bridge-action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_camel_case_escalation_alias_top_level_bridge_action_kebab_snake_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "bridge-action_id": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.bridge-action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.bridge-action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_snake_case_escalation_alias_top_level_bridge_action_kebab_snake_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "bridge-action_id": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.bridge-action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.bridge-action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_camel_case_escalation_alias_top_level_bridge_action_kebab_mixed_case_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "bridge-actionId": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.bridge-actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.bridge-actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_camel_case_escalation_alias_top_level_bridge_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "bridge-actionID": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.bridge-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.bridge-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_top_level_bridge_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "bridge-actionID": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.bridge-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.bridge-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_top_level_bridge_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "bridge-actionID": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.bridge-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.bridge-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_snake_case_escalation_alias_top_level_bridge_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "bridge-action-id": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.bridge-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.bridge-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_top_level_bridge_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "bridgeActionID": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.bridgeActionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.bridgeActionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_camel_case_escalation_alias_top_level_bridge_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "bridgeActionID": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.bridgeActionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.bridgeActionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_camel_case_escalation_alias_top_level_bridge_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "bridgeAction_id": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.bridgeAction_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.bridgeAction_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_top_level_bridge_action_snake_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "bridge_actionID": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.bridge_actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.bridge_actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_top_level_bridge_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "bridgeAction_id": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.bridgeAction_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.bridgeAction_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_top_level_bridge_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "bridge_actionId": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.bridge_actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.bridge_actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_snake_case_escalation_alias_top_level_bridge_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "bridgeActionid": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.bridgeActionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.bridgeActionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_camel_case_escalation_alias_top_level_bridge_action_snake_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "bridge_actionid": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.bridge_actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.bridge_actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_camel_case_workflow_camel_case_escalation_alias_top_level_bridge_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "externalEscalation": {
                        "bridgeActionid": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.bridgeActionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.bridgeActionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_escalation_action_accepts_snake_case_workflow_snake_case_escalation_alias_top_level_bridge_action_snake_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "external_escalation": {
                        "bridge_actionid": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.bridge_actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.bridge_actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_internal_loop_hint(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "action_hint": {
                            "watch_act_action": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internal_loop.action_hint.watch_act_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internal_loop.action_hint.watch_act_action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_internal_loop_hint_top_level_action(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "action_hint": {
                            "action": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internal_loop.action_hint.action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internal_loop.action_hint.action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_internal_loop_hint_top_level_action(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "actionHint": {
                            "action": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.internalLoop.actionHint.action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internalLoop.actionHint.action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_internal_loop_hint_top_level_action_id(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "action_hint": {
                            "action_id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internal_loop.action_hint.action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internal_loop.action_hint.action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_internal_loop_hint_top_level_action_id(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "actionHint": {
                            "actionId": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internalLoop.actionHint.actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internalLoop.actionHint.actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_internal_loop_hint_top_level_bridge_action_id(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "action_hint": {
                            "bridge_action_id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internal_loop.action_hint.bridge_action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internal_loop.action_hint.bridge_action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_internal_loop_hint_top_level_bridge_action_id(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "actionHint": {
                            "bridgeActionId": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internalLoop.actionHint.bridgeActionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internalLoop.actionHint.bridgeActionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_internal_loop_hint_watch_act_action(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "actionHint": {
                            "watchActAction": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internalLoop.actionHint.watchActAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internalLoop.actionHint.watchActAction",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_hint_watch_act_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "actionHint": {
                            "watchActAction": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internal_loop.actionHint.watchActAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionHint.watchActAction",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_hint_watch_act_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "action_hint": {
                            "watch_act_action": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.watch_act_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.watch_act_action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_hint_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "actionHint": {
                            "action_id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internal_loop.actionHint.action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionHint.action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_hint_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "actionHint": {
                            "actionid": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internal_loop.actionHint.actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionHint.actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_hint_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "actionHint": {
                            "actionID": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internal_loop.actionHint.actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionHint.actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_hint_bridge_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "actionHint": {
                            "bridgeActionId": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internal_loop.actionHint.bridgeActionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionHint.bridgeActionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_hint_bridge_action_snake_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "actionHint": {
                            "bridge_action_id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internal_loop.actionHint.bridge_action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionHint.bridge_action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_hint_bridge_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "actionHint": {
                            "bridgeActionID": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internal_loop.actionHint.bridgeActionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionHint.bridgeActionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_hint_bridge_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "actionHint": {
                            "bridgeAction_id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internal_loop.actionHint.bridgeAction_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionHint.bridgeAction_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_hint_bridge_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "actionHint": {
                            "bridge-action-id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internal_loop.actionHint.bridge-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionHint.bridge-action-id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_hint_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "actionHint": {
                            "action": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internal_loop.actionHint.action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionHint.action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_hint_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "action_hint": {
                            "action": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_hint_bridge_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "action_hint": {
                            "bridgeActionId": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.bridgeActionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.bridgeActionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_hint_bridge_action_snake_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "action_hint": {
                            "bridge_action_id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.bridge_action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.bridge_action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_hint_bridge_action_snake_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "action_hint": {
                            "bridge_actionID": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.bridge_actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.bridge_actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_hint_bridge_action_snake_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "action_hint": {
                            "bridge_actionId": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.bridge_actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.bridge_actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_hint_bridge_action_kebab_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "action_hint": {
                            "bridge-actionId": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.bridge-actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.bridge-actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_hint_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "action_hint": {
                            "action_id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_hint_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "action_hint": {
                            "actionid": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_hint_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "action_hint": {
                            "actionID": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_internal_loop_top_level_watch_act_action(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "watch_act_action": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internal_loop.watch_act_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internal_loop.watch_act_action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_internal_loop_top_level_watch_act_action(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "watchActAction": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operatorWorkflow.internalLoop.watchActAction"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internalLoop.watchActAction",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_top_level_watch_act_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "watchActAction": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.internal_loop.watchActAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.watchActAction",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_top_level_watch_act_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "watch_act_action": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.internalLoop.watch_act_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.watch_act_action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_internal_loop_top_level_action(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "action": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operator_workflow.internal_loop.action"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internal_loop.action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_internal_loop_top_level_action(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "action": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operatorWorkflow.internalLoop.action"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internalLoop.action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_top_level_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "action": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operatorWorkflow.internal_loop.action"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_top_level_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "action": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operator_workflow.internalLoop.action"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_internal_loop_top_level_action_id(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "action_id": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operator_workflow.internal_loop.action_id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internal_loop.action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_internal_loop_top_level_action_id(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "actionId": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operatorWorkflow.internalLoop.actionId"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internalLoop.actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_top_level_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "actionId": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operatorWorkflow.internal_loop.actionId"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_top_level_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "action_id": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operator_workflow.internalLoop.action_id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_top_level_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "actionID": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operatorWorkflow.internal_loop.actionID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_top_level_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "actionID": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operator_workflow.internalLoop.actionID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_top_level_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "actionid": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operatorWorkflow.internal_loop.actionid"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_top_level_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "actionid": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operator_workflow.internalLoop.actionid"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_top_level_bridge_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "bridgeActionId": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.internal_loop.bridgeActionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.bridgeActionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_top_level_bridge_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "bridge_action_id": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.internalLoop.bridge_action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.bridge_action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_top_level_bridge_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "bridge-action-id": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.internal_loop.bridge-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.bridge-action-id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_top_level_bridge_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "bridge-action-id": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.internalLoop.bridge-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.bridge-action-id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_top_level_bridge_action_id_snake_case_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "bridge_action_id": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.internal_loop.bridge_action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.bridge_action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_top_level_bridge_action_id_camel_case_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "bridgeActionId": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.internalLoop.bridgeActionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.bridgeActionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_top_level_bridge_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "bridgeActionID": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.internal_loop.bridgeActionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.bridgeActionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_top_level_bridge_action_snake_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "bridge_actionID": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.internalLoop.bridge_actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.bridge_actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_top_level_bridge_action_snake_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "bridge_actionID": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.internal_loop.bridge_actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.bridge_actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_top_level_bridge_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "bridgeActionID": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.internalLoop.bridgeActionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.bridgeActionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_top_level_bridge_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "bridgeAction_id": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.internal_loop.bridgeAction_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.bridgeAction_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_top_level_bridge_action_snake_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "bridge_actionId": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.internalLoop.bridge_actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.bridge_actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_top_level_bridge_action_snake_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "bridge_actionId": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.internal_loop.bridge_actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.bridge_actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_top_level_bridge_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "bridgeAction_id": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.internalLoop.bridgeAction_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.bridgeAction_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_internal_loop_top_level_default_action(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "defaultAction": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operatorWorkflow.internalLoop.defaultAction"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internalLoop.defaultAction",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_internal_loop_top_level_default_action(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "default_action": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.internal_loop.default_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internal_loop.default_action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_top_level_default_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "defaultAction": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operatorWorkflow.internal_loop.defaultAction"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.defaultAction",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_top_level_default_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "default_action": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.internalLoop.default_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.default_action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_top_level_default_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "defaultAction_id": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.internal_loop.defaultAction_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.defaultAction_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_top_level_default_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "default_actionId": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.internalLoop.default_actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.default_actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_top_level_default_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "defaultActionID": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.internal_loop.defaultActionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.defaultActionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_top_level_default_action_snake_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "default_actionID": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.internalLoop.default_actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.default_actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_top_level_default_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "defaultActionid": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.internal_loop.defaultActionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.defaultActionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_top_level_default_action_snake_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "default_actionid": "read-ack-latest",
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.internalLoop.default_actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.default_actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_internal_loop_hint_default_action(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "action_hint": {
                            "default_action": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internal_loop.action_hint.default_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internal_loop.action_hint.default_action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_internal_loop_hint_default_action(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "actionHint": {
                            "defaultAction": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internalLoop.actionHint.defaultAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internalLoop.actionHint.defaultAction",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_hint_default_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "action_hint": {
                            "defaultAction": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internalLoop.action_hint.defaultAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internalLoop.action_hint.defaultAction",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_hint_default_action_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "actionHint": {
                            "default_action": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internal_loop.actionHint.default_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internal_loop.actionHint.default_action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_hint_default_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "actionHint": {
                            "defaultAction_id": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internal_loop.actionHint.defaultAction_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionHint.defaultAction_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_hint_default_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "action_hint": {
                            "default_actionId": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.default_actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.default_actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_hint_default_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "actionHint": {
                            "defaultActionID": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internal_loop.actionHint.defaultActionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionHint.defaultActionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_hint_default_action_snake_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "action_hint": {
                            "default_actionID": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.default_actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.default_actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_snake_case_internal_loop_hint_default_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "actionHint": {
                            "defaultActionid": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internal_loop.actionHint.defaultActionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionHint.defaultActionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_camel_case_internal_loop_hint_default_action_snake_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "action_hint": {
                            "default_actionid": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.default_actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.default_actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_camel_case_workflow_camel_case_internal_loop_hint_snake_default_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {
                    "packageId": "cliq-195",
                    "internalLoop": {
                        "action_hint": {
                            "defaultActionid": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internalLoop.action_hint.defaultActionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internalLoop.action_hint.defaultActionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


@respx.mock
def test_cliq_watch_act_uses_snake_case_workflow_snake_case_internal_loop_hint_camel_default_action_snake_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operator_workflow": {
                    "packageId": "cliq-195",
                    "internal_loop": {
                        "actionHint": {
                            "default_actionid": "read-ack-latest",
                        }
                    },
                },
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 0, result.output
    assert route.called
    payload = json.loads(result.output)
    assert payload["action"] == "read-ack-latest"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internal_loop.actionHint.default_actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internal_loop.actionHint.default_actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_watch_act_escalation_action_requires_hint_or_action(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    watch_file = tmp_path / "watch.json"
    watch_file.write_text(
        json.dumps(
            {
                "chatId": "CT_1",
                "channelId": "O1",
                "operatorWorkflow": {"packageId": "cliq-195"},
                "newCount": 1,
                "messages": [
                    {"messageId": "M2", "senderId": "U2", "text": "latest"},
                ],
            }
        )
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "watch-act",
            "--watch-file",
            str(watch_file),
            "--escalation-action",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 1
    assert "invalid_action" in result.output
    assert "--escalation-action requires" in result.output


def test_cliq_messages_requires_destination(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    result = runner.invoke(app, ["cliq", "messages"], env=_cfg_env(mock_config))
    assert result.exit_code == 1
    assert "invalid_destination" in result.output


@respx.mock
def test_cliq_reply_from_channel(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(200, json={"data": {"chat_id": "CT_1"}})
    )
    respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/reply").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2"}})
    )

    result = runner.invoke(
        app,
        ["cliq", "reply", "M1", "--channel-id", "O1", "--text", "hello"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"


@respx.mock
def test_cliq_edit_message(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.put("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M1", "text": "new"}})
    )

    result = runner.invoke(
        app,
        ["cliq", "edit", "M1", "--chat-id", "CT_1", "--text", "new"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"


@respx.mock
def test_cliq_delete_message(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.delete("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1").mock(
        return_value=httpx.Response(204, text="")
    )

    result = runner.invoke(
        app,
        ["cliq", "delete", "M1", "--chat-id", "CT_1"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"


@respx.mock
def test_cliq_react_add(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/reactions").mock(
        return_value=httpx.Response(200, json={"data": {"status": "ok"}})
    )

    result = runner.invoke(
        app,
        ["cliq", "react", "M1", "--chat-id", "CT_1", "--emoji", ":thumbsup:"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"


def test_cliq_reply_requires_destination(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    result = runner.invoke(
        app,
        ["cliq", "reply", "M1", "--text", "hello"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 1
    assert "invalid_destination" in result.output


@respx.mock
def test_cliq_members_from_channel(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.get("https://cliq.zoho.com/api/v2/channels/O1/members").mock(
        return_value=httpx.Response(200, json={"members": [{"id": "U1"}]})
    )

    result = runner.invoke(
        app,
        ["cliq", "members", "--channel-id", "O1"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["members"][0]["id"] == "U1"


def test_cliq_member_add_requires_destination(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    result = runner.invoke(
        app,
        ["cliq", "member-add", "U1"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 1
    assert "invalid_destination" in result.output


@respx.mock
def test_cliq_member_add(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.get("https://cliq.zoho.com/api/v2/channels/O2").mock(
        return_value=httpx.Response(200, json={"data": {"chat_id": "CT_2"}})
    )
    respx.post("https://cliq.zoho.com/api/v2/channels/O2/members").mock(
        return_value=httpx.Response(200, json={"data": {"status": "ok"}})
    )

    result = runner.invoke(
        app,
        ["cliq", "member-add", "U1", "--channel-id", "O2"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"


@respx.mock
def test_cliq_member_remove(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.get("https://cliq.zoho.com/api/v2/channels/O2").mock(
        return_value=httpx.Response(200, json={"data": {"chat_id": "CT_2"}})
    )
    respx.delete("https://cliq.zoho.com/api/v2/channels/O2/members/U1").mock(
        return_value=httpx.Response(204, text="")
    )

    result = runner.invoke(
        app,
        ["cliq", "member-remove", "U1", "--channel-id", "O2"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"


@respx.mock
def test_cliq_channel_create(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.post("https://cliq.zoho.com/api/v2/channels").mock(
        return_value=httpx.Response(200, json={"channel_id": "O2", "name": "ops"})
    )

    result = runner.invoke(
        app,
        ["cliq", "channel-create", "--name", "ops", "--level", "organization"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"


@respx.mock
def test_cliq_channel_rename(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.post("https://cliq.zoho.com/api/v2/channels/O2/rename").mock(
        return_value=httpx.Response(200, json={"channel_id": "O2", "name": "ops-2"})
    )

    result = runner.invoke(
        app,
        ["cliq", "channel-rename", "O2", "--name", "ops-2"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["name"] == "ops-2"


@respx.mock
def test_cliq_channel_topic(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.post("https://cliq.zoho.com/api/v2/channels/O2/topic").mock(
        return_value=httpx.Response(204, text="")
    )

    result = runner.invoke(
        app,
        ["cliq", "channel-topic", "O2", "--topic", "deploy updates"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["topic"] == "deploy updates"


@respx.mock
def test_cliq_channel_archive(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.post("https://cliq.zoho.com/api/v2/channels/O2/archive").mock(
        return_value=httpx.Response(204, text="")
    )

    result = runner.invoke(
        app,
        ["cliq", "channel-archive", "O2"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"


@respx.mock
def test_cliq_channel_unarchive(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.post("https://cliq.zoho.com/api/v2/channels/O2/unarchive").mock(
        return_value=httpx.Response(204, text="")
    )

    result = runner.invoke(
        app,
        ["cliq", "channel-unarchive", "O2"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["unarchive"] is True


def test_cliq_channel_delete_requires_force(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    result = runner.invoke(
        app,
        ["cliq", "channel-delete", "O2"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 1
    assert "confirm_required" in result.output


@respx.mock
def test_cliq_channel_delete(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.delete("https://cliq.zoho.com/api/v2/channels/O2").mock(
        return_value=httpx.Response(204, text="")
    )

    result = runner.invoke(
        app,
        ["cliq", "channel-delete", "O2", "--force"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"


def test_cliq_thread_create_from_channel(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.resolve_chat_id.return_value = "C1"
    mock_client.create_thread.return_value = {"data": {"thread_id": "T1"}}

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "cliq",
                "thread-create",
                "M1",
                "--channel-id",
                "O2",
                "--text",
                "hello thread",
            ],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["chatId"] == "C1"
    mock_client.create_thread.assert_called_once_with(
        "M1",
        "hello thread",
        chat_id="C1",
        channel_id="O2",
    )


def test_cliq_threads_from_channel(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.resolve_chat_id.return_value = "C1"
    mock_client.list_threads.return_value = {"data": [{"id": "T1"}, {"id": "T2"}]}

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "threads", "--channel-id", "O2", "--limit", "2"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["chatId"] == "C1"
    assert payload["count"] == 2
    assert payload["threads"][0]["id"] == "T1"


def test_cliq_scheduled_from_channel(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.resolve_chat_id.return_value = "C1"
    mock_client.list_scheduled_messages.return_value = {
        "data": [{"id": "S1"}, {"id": "S2"}]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "scheduled", "--channel-id", "O2", "--limit", "2"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["chatId"] == "C1"
    assert payload["count"] == 2
    assert payload["scheduled"][0]["id"] == "S1"
    mock_client.list_scheduled_messages.assert_called_once_with(
        chat_id="C1",
        channel_id="O2",
        limit=2,
    )


def test_cliq_schedule_from_channel(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.resolve_chat_id.return_value = "C1"
    mock_client.schedule_message.return_value = {"data": {"id": "S1"}}

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "cliq",
                "schedule",
                "--channel-id",
                "O2",
                "--text",
                "hello schedule",
                "--when",
                "2026-04-13T10:00:00Z",
            ],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["chatId"] == "C1"
    assert payload["scheduledId"] == "S1"
    mock_client.schedule_message.assert_called_once_with(
        "hello schedule",
        "2026-04-13T10:00:00Z",
        chat_id="C1",
        channel_id="O2",
    )


def test_cliq_post_to_bot(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.post_to_bot.return_value = {"data": {"id": "BM1"}}

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "cliq",
                "post-to-bot",
                "bot-123",
                "--text",
                "hello bot",
                "--title",
                "Automation ping",
            ],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["botId"] == "bot-123"
    assert payload["messageId"] == "BM1"
    mock_client.post_to_bot.assert_called_once_with(
        "bot-123",
        "hello bot",
        title="Automation ping",
    )


def test_cliq_bot_subscribers(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_bot_subscribers.return_value = {
        "data": [{"id": "U1"}, {"id": "U2"}]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "bot-subscribers", "bot-123", "--limit", "2"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["botId"] == "bot-123"
    assert payload["count"] == 2
    mock_client.list_bot_subscribers.assert_called_once_with("bot-123", limit=2)


def test_cliq_trigger_bot(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.trigger_bot_call.return_value = {"data": {"id": "BC1"}}

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "cliq",
                "trigger-bot",
                "bot-123",
                "daily_digest",
                "--inputs-json",
                '{"limit": 5}',
            ],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["botId"] == "bot-123"
    assert payload["callName"] == "daily_digest"
    assert payload["callId"] == "BC1"
    mock_client.trigger_bot_call.assert_called_once_with(
        "bot-123",
        "daily_digest",
        inputs={"limit": 5},
    )


def test_cliq_trigger_bot_rejects_invalid_inputs_json(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    result = runner.invoke(
        app,
        [
            "cliq",
            "trigger-bot",
            "bot-123",
            "daily_digest",
            "--inputs-json",
            "{not-json}",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code != 0
    assert "invalid_inputs_json" in result.output


def test_cliq_scheduled_get_from_channel(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.resolve_chat_id.return_value = "C1"
    mock_client.get_scheduled_message.return_value = {
        "data": {"id": "S1", "text": "hello"}
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "scheduled-get", "S1", "--channel-id", "O2"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["chatId"] == "C1"
    assert payload["scheduledId"] == "S1"
    assert payload["scheduled"]["id"] == "S1"
    mock_client.get_scheduled_message.assert_called_once_with(
        "S1",
        chat_id="C1",
        channel_id="O2",
    )


def test_cliq_scheduled_cancel_from_channel(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.resolve_chat_id.return_value = "C1"
    mock_client.cancel_scheduled_message.return_value = {"status": "ok"}

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "scheduled-cancel", "S1", "--channel-id", "O2"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["chatId"] == "C1"
    assert payload["scheduledId"] == "S1"
    mock_client.cancel_scheduled_message.assert_called_once_with(
        "S1",
        chat_id="C1",
        channel_id="O2",
    )


def test_cliq_leave_from_channel(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.resolve_chat_id.return_value = "C1"
    mock_client.leave_chat.return_value = {"data": {"left": True}}

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "leave", "--channel-id", "O2"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["chatId"] == "C1"
    assert payload["channelId"] == "O2"
    mock_client.leave_chat.assert_called_once_with(
        chat_id="C1",
        channel_id="O2",
    )


def test_cliq_mute_from_channel(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.resolve_chat_id.return_value = "C1"
    mock_client.set_chat_mute.return_value = {"data": {"muted": True}}

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "mute", "--channel-id", "O2"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["chatId"] == "C1"
    assert payload["channelId"] == "O2"
    assert payload["muted"] is True
    mock_client.set_chat_mute.assert_called_once_with(
        chat_id="C1",
        channel_id="O2",
        muted=True,
    )


def test_cliq_unmute_from_channel(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.resolve_chat_id.return_value = "C1"
    mock_client.set_chat_mute.return_value = {"data": {"muted": False}}

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "unmute", "--channel-id", "O2"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["chatId"] == "C1"
    assert payload["channelId"] == "O2"
    assert payload["muted"] is False
    mock_client.set_chat_mute.assert_called_once_with(
        chat_id="C1",
        channel_id="O2",
        muted=False,
    )


def test_cliq_pin_from_channel(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.resolve_chat_id.return_value = "C1"
    mock_client.set_chat_pin.return_value = {"data": {"pinned": True}}

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "pin", "--channel-id", "O2"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["chatId"] == "C1"
    assert payload["channelId"] == "O2"
    assert payload["pinned"] is True
    mock_client.set_chat_pin.assert_called_once_with(
        chat_id="C1",
        channel_id="O2",
        pinned=True,
    )


def test_cliq_unpin_from_channel(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.resolve_chat_id.return_value = "C1"
    mock_client.set_chat_pin.return_value = {"data": {"pinned": False}}

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "unpin", "--channel-id", "O2"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["chatId"] == "C1"
    assert payload["channelId"] == "O2"
    assert payload["pinned"] is False
    mock_client.set_chat_pin.assert_called_once_with(
        chat_id="C1",
        channel_id="O2",
        pinned=False,
    )


def test_cliq_pinned_from_channel(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.resolve_chat_id.return_value = "C1"
    mock_client.list_pinned_messages.return_value = {
        "data": [{"id": "M1"}, {"id": "M2"}]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "pinned", "--channel-id", "O2", "--limit", "10"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["chatId"] == "C1"
    assert payload["channelId"] == "O2"
    assert payload["count"] == 2
    assert payload["pinnedMessages"][0]["id"] == "M1"
    mock_client.list_pinned_messages.assert_called_once_with(
        chat_id="C1",
        channel_id="O2",
        limit=10,
    )


def test_cliq_thread_followers(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.resolve_chat_id.return_value = "C1"
    mock_client.list_thread_followers.return_value = {
        "data": [{"user_id": "U1"}, {"user_id": "U2"}]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "cliq",
                "thread-followers",
                "T1",
                "--channel-id",
                "O2",
                "--limit",
                "10",
            ],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["threadId"] == "T1"
    assert payload["count"] == 2
    mock_client.list_thread_followers.assert_called_once_with(
        "T1",
        chat_id="C1",
        channel_id="O2",
        limit=10,
    )


def test_cliq_thread_state_update(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.resolve_chat_id.return_value = "C1"
    mock_client.update_thread_state.return_value = {"data": {"state": "closed"}}

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "cliq",
                "thread-state",
                "T1",
                "--channel-id",
                "O2",
                "--state",
                "closed",
            ],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["threadId"] == "T1"
    assert payload["state"] == "closed"


def test_cliq_thread_state_read(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.resolve_chat_id.return_value = "C1"
    mock_client.get_thread_state.return_value = {"data": {"state": "open"}}

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "thread-state", "T1", "--channel-id", "O2"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["threadId"] == "T1"
    assert payload["state"] == "open"


# ---------------------------------------------------------------------------
# crm status
# ---------------------------------------------------------------------------


def test_crm_status_scaffold_info(mock_config: Path) -> None:
    """crm status returns scaffold readiness and inferred base URL."""
    result = runner.invoke(app, ["crm", "status"], env=_cfg_env(mock_config))
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    assert payload["module"] == "crm"
    assert payload["scaffold"] == "ready"
    assert payload["hasAccount"] is True
    assert payload["hasAccountId"] is True
    assert payload["baseUrl"] == "https://www.zohoapis.com/crm/v2"
    assert payload["oauthReady"] is False
    assert "ZohoCRM.modules.ALL" in payload["missingScopes"]


def test_crm_status_oauth_ready_when_scopes_present(tmp_path: Path) -> None:
    cfg = {
        "client_id": "test_id",
        "client_secret": "test_secret",
        "default_account": ACCOUNT_EMAIL,
        "accounts": {
            ACCOUNT_EMAIL: {
                "accountId": ACCOUNT_ID,
                "scopes": [
                    "ZohoMail.messages.ALL",
                    "ZohoCRM.modules.ALL",
                    "ZohoCRM.settings.ALL",
                ],
            }
        },
    }
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg))

    result = runner.invoke(app, ["crm", "status"], env=_cfg_env(cfg_path))
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["oauthReady"] is True
    assert payload["missingScopes"] == []


def test_crm_status_check_auth(mock_config: Path, mock_token_refresh: Any) -> None:
    """--check-auth verifies OAuth refresh via shared account wiring."""
    result = runner.invoke(
        app,
        ["crm", "status", "--check-auth"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    assert payload["auth"] == "ok"


@respx.mock
def test_crm_modules(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.get("https://www.zohoapis.com/crm/v2/settings/modules").mock(
        return_value=httpx.Response(
            200, json={"data": [{"api_name": "Leads", "module_name": "Leads"}]}
        )
    )

    result = runner.invoke(
        app, ["crm", "modules", "--limit", "2"], env=_cfg_env(mock_config)
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload[0]["api_name"] == "Leads"


@respx.mock
def test_crm_fields(mock_config: Path, mock_token_refresh: Any) -> None:
    route = respx.get("https://www.zohoapis.com/crm/v2/settings/fields").mock(
        return_value=httpx.Response(200, json={"data": [{"api_name": "Company"}]})
    )

    result = runner.invoke(
        app,
        ["crm", "fields", "--module", "Leads", "--limit", "5", "--page", "2"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload[0]["api_name"] == "Company"
    assert dict(route.calls.last.request.url.params) == {
        "module": "Leads",
        "per_page": "5",
        "page": "2",
    }


@respx.mock
def test_crm_list(mock_config: Path, mock_token_refresh: Any) -> None:
    route = respx.get("https://www.zohoapis.com/crm/v2/Leads").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "1001"}]})
    )

    result = runner.invoke(
        app,
        [
            "crm",
            "list",
            "--module",
            "Leads",
            "--limit",
            "2",
            "--page",
            "3",
            "--field",
            "Last_Name",
            "--field",
            "Email",
        ],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload[0]["id"] == "1001"
    assert dict(route.calls.last.request.url.params) == {
        "per_page": "2",
        "page": "3",
        "fields": "Last_Name,Email",
    }


@respx.mock
def test_crm_get(mock_config: Path, mock_token_refresh: Any) -> None:
    route = respx.get("https://www.zohoapis.com/crm/v2/Leads/1001").mock(
        return_value=httpx.Response(
            200, json={"data": [{"id": "1001", "Company": "Acme"}]}
        )
    )

    result = runner.invoke(
        app,
        ["crm", "get", "1001", "--module", "Leads", "--field", "Company"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["id"] == "1001"
    assert payload["Company"] == "Acme"
    assert dict(route.calls.last.request.url.params) == {"fields": "Company"}


@respx.mock
def test_crm_search_with_criteria(mock_config: Path, mock_token_refresh: Any) -> None:
    route = respx.get("https://www.zohoapis.com/crm/v2/Leads/search").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "1002"}]})
    )

    result = runner.invoke(
        app,
        [
            "crm",
            "search",
            "--module",
            "Leads",
            "--criteria",
            "(Last_Name:equals:Wang)",
            "--limit",
            "2",
            "--page",
            "4",
        ],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload[0]["id"] == "1002"
    assert dict(route.calls.last.request.url.params) == {
        "per_page": "2",
        "page": "4",
        "criteria": "(Last_Name:equals:Wang)",
    }


def test_crm_search_requires_exactly_one_query_mode(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    result = runner.invoke(
        app,
        [
            "crm",
            "search",
            "--module",
            "Leads",
            "--word",
            "acme",
            "--criteria",
            "(Last_Name:equals:Wang)",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 1
    assert "invalid_query" in result.output


@respx.mock
def test_cliq_channels(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.get("https://cliq.zoho.com/api/v2/channels").mock(
        return_value=httpx.Response(
            200, json={"data": [{"id": "C1", "name": "General"}]}
        )
    )

    result = runner.invoke(
        app, ["cliq", "channels", "--limit", "3"], env=_cfg_env(mock_config)
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload[0]["id"] == "C1"


@respx.mock
def test_cliq_channels_with_network(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.get(
        "https://cliq.zoho.com/network/happydistrouklimited/api/v2/channels"
    ).mock(
        return_value=httpx.Response(200, json={"data": [{"id": "C2", "name": "Ops"}]})
    )

    result = runner.invoke(
        app,
        ["cliq", "channels", "--network", "happydistrouklimited", "--limit", "2"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload[0]["id"] == "C2"


@respx.mock
def test_cliq_chats(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.get("https://cliq.zoho.com/api/v2/chats").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"id": "CT_1", "name": "DM David", "type": "direct"}]},
        )
    )

    result = runner.invoke(
        app, ["cliq", "chats", "--limit", "2"], env=_cfg_env(mock_config)
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["chats"][0]["chatId"] == "CT_1"
    assert payload["chats"][0]["type"] == "direct"


@respx.mock
def test_cliq_users(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.get("https://cliq.zoho.com/api/v2/users").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "U1", "name": "Alice"}]})
    )

    result = runner.invoke(
        app, ["cliq", "users", "--limit", "2"], env=_cfg_env(mock_config)
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload[0]["id"] == "U1"


def test_cliq_teams(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_teams.return_value = {
        "data": [{"team_id": "TM_1", "name": "Ops Team"}]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "teams", "--limit", "3"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["teams"][0]["teamId"] == "TM_1"
    assert payload["teams"][0]["name"] == "Ops Team"
    mock_client.list_teams.assert_called_once_with(limit=3)


def test_cliq_departments(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_departments.return_value = {
        "data": [{"department_id": "DP_1", "name": "Operations"}]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "departments", "--limit", "4"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["departments"][0]["departmentId"] == "DP_1"
    assert payload["departments"][0]["name"] == "Operations"
    mock_client.list_departments.assert_called_once_with(limit=4)


def test_cliq_roles(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_roles.return_value = {
        "data": [{"role_id": "RL_1", "name": "Manager"}]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "roles", "--limit", "5"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["roles"][0]["roleId"] == "RL_1"
    assert payload["roles"][0]["name"] == "Manager"
    mock_client.list_roles.assert_called_once_with(limit=5)


def test_cliq_designations(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_designations.return_value = {
        "data": [{"designation_id": "DG_1", "name": "Shift Lead"}]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "designations", "--limit", "6"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["designations"][0]["designationId"] == "DG_1"
    assert payload["designations"][0]["name"] == "Shift Lead"
    mock_client.list_designations.assert_called_once_with(limit=6)


def test_cliq_user_status(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_user_statuses.return_value = {
        "data": [{"status_id": "ST_1", "name": "Available"}]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "user-status", "--limit", "7"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["statuses"][0]["statusId"] == "ST_1"
    assert payload["statuses"][0]["name"] == "Available"
    mock_client.list_user_statuses.assert_called_once_with(limit=7)


def test_cliq_userfields(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_user_fields.return_value = {
        "data": [
            {
                "field_id": "UF_1",
                "label": "Department",
                "field_type": "text",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "userfields", "--limit", "9"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["userFields"][0]["fieldId"] == "UF_1"
    assert payload["userFields"][0]["label"] == "Department"
    assert payload["userFields"][0]["type"] == "text"
    mock_client.list_user_fields.assert_called_once_with(limit=9)


def test_cliq_events(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_events.return_value = {
        "data": [
            {
                "event_id": "EV_1",
                "title": "Daily Sync",
                "start_time": "2026-04-12T20:00:00Z",
                "end_time": "2026-04-12T20:30:00Z",
                "status": "scheduled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "events", "--limit", "8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["events"][0]["eventId"] == "EV_1"
    assert payload["events"][0]["title"] == "Daily Sync"
    assert payload["events"][0]["startsAt"] == "2026-04-12T20:00:00Z"
    assert payload["events"][0]["endsAt"] == "2026-04-12T20:30:00Z"
    assert payload["events"][0]["status"] == "scheduled"
    mock_client.list_events.assert_called_once_with(limit=8)


def test_cliq_reminders(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_reminders.return_value = {
        "data": [
            {
                "reminder_id": "RM_1",
                "title": "Submit status update",
                "remind_at": "2026-04-12T21:00:00Z",
                "status": "scheduled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "reminders", "--limit", "6"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["reminders"][0]["reminderId"] == "RM_1"
    assert payload["reminders"][0]["title"] == "Submit status update"
    assert payload["reminders"][0]["dueAt"] == "2026-04-12T21:00:00Z"
    assert payload["reminders"][0]["status"] == "scheduled"
    mock_client.list_reminders.assert_called_once_with(limit=6)


def test_cliq_meetings(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_meetings.return_value = {
        "data": [
            {
                "meeting_id": "MT_1",
                "title": "Weekly Sync",
                "start_time": "2026-04-12T22:00:00Z",
                "end_time": "2026-04-12T22:30:00Z",
                "status": "scheduled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "meetings", "--limit", "5"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["meetings"][0]["meetingId"] == "MT_1"
    assert payload["meetings"][0]["title"] == "Weekly Sync"
    assert payload["meetings"][0]["startsAt"] == "2026-04-12T22:00:00Z"
    assert payload["meetings"][0]["endsAt"] == "2026-04-12T22:30:00Z"
    assert payload["meetings"][0]["status"] == "scheduled"
    mock_client.list_meetings.assert_called_once_with(limit=5)


def test_cliq_databases(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_databases.return_value = {
        "data": [
            {
                "database_id": "DB_1",
                "name": "Operations DB",
                "database_type": "records",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "databases", "--limit", "7"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["databases"][0]["databaseId"] == "DB_1"
    assert payload["databases"][0]["name"] == "Operations DB"
    assert payload["databases"][0]["type"] == "records"
    mock_client.list_databases.assert_called_once_with(limit=7)


def test_cliq_widgets(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_widgets.return_value = {
        "data": [
            {
                "widget_id": "WG_1",
                "name": "Ticker Board",
                "widget_type": "ticker",
                "status": "active",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "widgets", "--limit", "6"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["widgets"][0]["widgetId"] == "WG_1"
    assert payload["widgets"][0]["name"] == "Ticker Board"
    assert payload["widgets"][0]["type"] == "ticker"
    assert payload["widgets"][0]["status"] == "active"
    mock_client.list_widgets.assert_called_once_with(limit=6)


def test_cliq_map_tickers(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_map_tickers.return_value = {
        "data": [
            {
                "ticker_id": "TK_1",
                "name": "Ops Ticker",
                "symbol": "OPS",
                "status": "active",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "map-tickers", "--limit", "8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["mapTickers"][0]["tickerId"] == "TK_1"
    assert payload["mapTickers"][0]["name"] == "Ops Ticker"
    assert payload["mapTickers"][0]["symbol"] == "OPS"
    assert payload["mapTickers"][0]["status"] == "active"
    mock_client.list_map_tickers.assert_called_once_with(limit=8)


def test_cliq_custom_domains(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_custom_domains.return_value = {
        "data": [
            {
                "domain_id": "CD_1",
                "domain": "chat.example.com",
                "status": "active",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "custom-domains", "--limit", "17"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["customDomains"][0]["domainId"] == "CD_1"
    assert payload["customDomains"][0]["domain"] == "chat.example.com"
    assert payload["customDomains"][0]["status"] == "active"
    mock_client.list_custom_domains.assert_called_once_with(limit=17)


def test_cliq_custom_emails(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_custom_emails.return_value = {
        "data": [
            {
                "email_id": "CE_1",
                "email": "alerts@example.com",
                "status": "verified",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "custom-emails", "--limit", "19"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["customEmails"][0]["emailId"] == "CE_1"
    assert payload["customEmails"][0]["email"] == "alerts@example.com"
    assert payload["customEmails"][0]["status"] == "verified"
    mock_client.list_custom_emails.assert_called_once_with(limit=19)


def test_cliq_apps(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_apps.return_value = {
        "data": [
            {
                "app_id": "AP_1",
                "name": "Helpdesk Bot",
                "status": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "apps", "--limit", "9"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["apps"][0]["appId"] == "AP_1"
    assert payload["apps"][0]["name"] == "Helpdesk Bot"
    assert payload["apps"][0]["status"] == "enabled"
    mock_client.list_apps.assert_called_once_with(limit=9)


def test_cliq_apps_accepts_nested_apps_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_apps.return_value = {
        "data": {
            "apps": [
                {
                    "appId": "AP_2",
                    "app_name": "Ops Relay",
                    "state": "disabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "apps", "--limit", "7"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["apps"][0]["appId"] == "AP_2"
    assert payload["apps"][0]["name"] == "Ops Relay"
    assert payload["apps"][0]["status"] == "disabled"
    mock_client.list_apps.assert_called_once_with(limit=7)


def test_cliq_apps_accepts_single_app_dict_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_apps.return_value = {
        "data": {
            "appId": "AP_3",
            "name": "Ops Bridge",
            "state": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "apps", "--limit", "5"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["apps"][0]["appId"] == "AP_3"
    assert payload["apps"][0]["name"] == "Ops Bridge"
    assert payload["apps"][0]["status"] == "enabled"
    mock_client.list_apps.assert_called_once_with(limit=5)


def test_cliq_apps_accepts_top_level_single_app_dict_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_apps.return_value = {
        "appId": "AP_4",
        "name": "Ops Inspector",
        "state": "active",
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "apps", "--limit", "6"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["apps"][0]["appId"] == "AP_4"
    assert payload["apps"][0]["name"] == "Ops Inspector"
    assert payload["apps"][0]["status"] == "active"
    mock_client.list_apps.assert_called_once_with(limit=6)


def test_cliq_apps_accepts_data_records_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_apps.return_value = {
        "data": {
            "records": [
                {
                    "id": "AP_5R",
                    "name": "Ops Alerts",
                    "state": "active",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "apps", "--limit", "4"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["apps"][0]["appId"] == "AP_5R"
    assert payload["apps"][0]["name"] == "Ops Alerts"
    assert payload["apps"][0]["status"] == "active"
    mock_client.list_apps.assert_called_once_with(limit=4)


def test_cliq_apps_accepts_data_records_record_row_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_apps.return_value = {
        "data": {
            "records": {
                "record": {
                    "item": {
                        "id": "AP_5RR",
                        "name": "Ops Alerts Wrapped",
                        "state": "active",
                    }
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "apps", "--limit", "4"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["apps"][0]["appId"] == "AP_5RR"
    assert payload["apps"][0]["name"] == "Ops Alerts Wrapped"
    assert payload["apps"][0]["status"] == "active"
    mock_client.list_apps.assert_called_once_with(limit=4)


def test_cliq_apps_accepts_top_level_response_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_apps.return_value = {
        "response": {
            "data": {
                "records": {
                    "record": [
                        {
                            "item": {
                                "appId": "AP_RESP",
                                "name": "Ops Response Wrapper",
                                "state": "active",
                            }
                        }
                    ]
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "apps", "--limit", "3"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["apps"][0]["appId"] == "AP_RESP"
    assert payload["apps"][0]["name"] == "Ops Response Wrapper"
    assert payload["apps"][0]["status"] == "active"
    mock_client.list_apps.assert_called_once_with(limit=3)


def test_cliq_apps_accepts_top_level_payload_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_apps.return_value = {
        "payload": {
            "response": {
                "data": {
                    "records": {
                        "record": [
                            {
                                "item": {
                                    "appId": "AP_PAYLOAD",
                                    "name": "Ops Payload Wrapper",
                                    "state": "active",
                                }
                            }
                        ]
                    }
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "apps", "--limit", "2"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["apps"][0]["appId"] == "AP_PAYLOAD"
    assert payload["apps"][0]["name"] == "Ops Payload Wrapper"
    assert payload["apps"][0]["status"] == "active"
    mock_client.list_apps.assert_called_once_with(limit=2)


def test_cliq_apps_accepts_deep_data_records_record_item_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_apps.return_value = {
        "payload": {
            "response": {
                "result": {
                    "data": {
                        "records": {
                            "record": [
                                {
                                    "item": {
                                        "payload": {
                                            "response": {
                                                "result": {
                                                    "data": {
                                                        "records": {
                                                            "record": {
                                                                "item": {
                                                                    "app": {
                                                                        "item": {
                                                                            "appId": "AP_DEEP_APPS",
                                                                            "name": "Ops Deep Apps Wrapper",
                                                                            "state": "active",
                                                                        }
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "apps", "--limit", "3"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["apps"][0]["appId"] == "AP_DEEP_APPS"
    assert payload["apps"][0]["name"] == "Ops Deep Apps Wrapper"
    assert payload["apps"][0]["status"] == "active"
    mock_client.list_apps.assert_called_once_with(limit=3)


def test_cliq_apps_accepts_top_level_app_wrapper_dict_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_apps.return_value = {
        "app": {
            "appId": "AP_5",
            "name": "Ops Escalator",
            "state": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "apps", "--limit", "4"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["apps"][0]["appId"] == "AP_5"
    assert payload["apps"][0]["name"] == "Ops Escalator"
    assert payload["apps"][0]["status"] == "enabled"
    mock_client.list_apps.assert_called_once_with(limit=4)


def test_cliq_apps_accepts_data_list_wrapped_app_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_apps.return_value = {
        "data": [
            {
                "app": {
                    "appId": "AP_6",
                    "name": "Escalations",
                    "status": "active",
                }
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "apps", "--limit", "4"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["apps"][0]["appId"] == "AP_6"
    assert payload["apps"][0]["name"] == "Escalations"
    assert payload["apps"][0]["status"] == "active"


def test_cliq_apps_accepts_data_list_wrapped_item_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_apps.return_value = {
        "data": [
            {
                "item": {
                    "appId": "AP_6I",
                    "name": "Escalations Item Wrapper",
                    "status": "active",
                }
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "apps", "--limit", "4"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["apps"][0]["appId"] == "AP_6I"
    assert payload["apps"][0]["name"] == "Escalations Item Wrapper"
    assert payload["apps"][0]["status"] == "active"


def test_cliq_app_get(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app.return_value = {
        "data": {
            "app_id": "AP_9",
            "name": "Ops Assistant",
            "status": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-get", "AP_9"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["app"]["appId"] == "AP_9"
    assert payload["app"]["name"] == "Ops Assistant"
    assert payload["app"]["status"] == "enabled"
    mock_client.get_app.assert_called_once_with("AP_9")


def test_cliq_app_get_accepts_apps_list_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app.return_value = {
        "apps": [
            {
                "appId": "AP_10",
                "name": "Status Robot",
                "app_status": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-get", "AP_10"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["app"]["appId"] == "AP_10"
    assert payload["app"]["name"] == "Status Robot"
    assert payload["app"]["status"] == "enabled"
    mock_client.get_app.assert_called_once_with("AP_10")


def test_cliq_app_get_accepts_data_records_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app.return_value = {
        "data": {
            "records": [
                {
                    "id": "AP_12R",
                    "name": "Ops Escalator",
                    "state": "active",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-get", "AP_12R"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["app"]["appId"] == "AP_12R"
    assert payload["app"]["name"] == "Ops Escalator"
    assert payload["app"]["status"] == "active"
    mock_client.get_app.assert_called_once_with("AP_12R")


def test_cliq_app_get_accepts_data_records_record_item_row_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app.return_value = {
        "data": {
            "records": {
                "record": [
                    {
                        "item": {
                            "id": "AP_12RRI",
                            "name": "Ops Escalator Record Item",
                            "state": "enabled",
                        }
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-get", "AP_12RRI"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["app"]["appId"] == "AP_12RRI"
    assert payload["app"]["name"] == "Ops Escalator Record Item"
    assert payload["app"]["status"] == "enabled"
    mock_client.get_app.assert_called_once_with("AP_12RRI")


def test_cliq_app_get_accepts_top_level_response_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app.return_value = {
        "response": {
            "data": {
                "record": {
                    "item": {
                        "app": {
                            "appId": "AP_RESP_GET",
                            "name": "Ops Response Detail",
                            "state": "enabled",
                        }
                    }
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-get", "AP_RESP_GET"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["app"]["appId"] == "AP_RESP_GET"
    assert payload["app"]["name"] == "Ops Response Detail"
    assert payload["app"]["status"] == "enabled"
    mock_client.get_app.assert_called_once_with("AP_RESP_GET")


def test_cliq_app_get_accepts_top_level_payload_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app.return_value = {
        "payload": {
            "response": {
                "data": {
                    "record": {
                        "item": {
                            "app": {
                                "appId": "AP_PAYLOAD_GET",
                                "name": "Ops Payload Detail",
                                "state": "active",
                            }
                        }
                    }
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-get", "AP_PAYLOAD_GET"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["app"]["appId"] == "AP_PAYLOAD_GET"
    assert payload["app"]["name"] == "Ops Payload Detail"
    assert payload["app"]["status"] == "active"
    mock_client.get_app.assert_called_once_with("AP_PAYLOAD_GET")


def test_cliq_app_get_accepts_deep_data_records_record_item_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app.return_value = {
        "payload": {
            "response": {
                "result": {
                    "data": {
                        "records": {
                            "record": {
                                "item": {
                                    "payload": {
                                        "response": {
                                            "result": {
                                                "data": {
                                                    "records": {
                                                        "record": {
                                                            "item": {
                                                                "app": {
                                                                    "app_id": "AP_DEEP_GET",
                                                                    "name": "Ops Deep Payload Detail",
                                                                    "state": "enabled",
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-get", "AP_DEEP_GET"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["app"]["appId"] == "AP_DEEP_GET"
    assert payload["app"]["name"] == "Ops Deep Payload Detail"
    assert payload["app"]["status"] == "enabled"
    mock_client.get_app.assert_called_once_with("AP_DEEP_GET")


def test_cliq_app_get_accepts_top_level_apps_dict_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app.return_value = {
        "apps": {
            "appId": "AP_11",
            "name": "Ops Triage",
            "state": "active",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-get", "AP_11"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["app"]["appId"] == "AP_11"
    assert payload["app"]["name"] == "Ops Triage"
    assert payload["app"]["status"] == "active"
    mock_client.get_app.assert_called_once_with("AP_11")


def test_cliq_app_get_accepts_top_level_app_wrapper_list_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app.return_value = {
        "app": [
            {
                "appId": "AP_12",
                "name": "Ops Escalator",
                "status": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-get", "AP_12"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["app"]["appId"] == "AP_12"
    assert payload["app"]["name"] == "Ops Escalator"
    assert payload["app"]["status"] == "enabled"
    mock_client.get_app.assert_called_once_with("AP_12")


def test_cliq_app_get_accepts_top_level_app_wrapper_list_row_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app.return_value = {
        "app": [
            {
                "app": {
                    "id": "AP_12B",
                    "name": "Ops Escalator Wrapped",
                    "status": "enabled",
                }
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-get", "AP_12B"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["app"]["appId"] == "AP_12B"
    assert payload["app"]["name"] == "Ops Escalator Wrapped"
    assert payload["app"]["status"] == "enabled"
    mock_client.get_app.assert_called_once_with("AP_12B")


def test_cliq_app_permissions(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_permissions.return_value = {
        "data": [
            {
                "permission_id": "P_1",
                "scope": "ZohoCliq.Messages.READ",
                "status": "granted",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-permissions", "AP_1", "--limit", "7"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_1"
    assert payload["count"] == 1
    assert payload["permissions"][0]["permissionId"] == "P_1"
    assert payload["permissions"][0]["scope"] == "ZohoCliq.Messages.READ"
    assert payload["permissions"][0]["status"] == "granted"
    mock_client.list_app_permissions.assert_called_once_with("AP_1", limit=7)


def test_cliq_app_permissions_accepts_nested_permissions_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_permissions.return_value = {
        "data": {
            "permissions": [
                {
                    "id": "P_2",
                    "name": "ZohoCliq.Apps.READ",
                    "state": "active",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-permissions", "AP_2"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["permissions"][0]["permissionId"] == "P_2"
    assert payload["permissions"][0]["scope"] == "ZohoCliq.Apps.READ"
    assert payload["permissions"][0]["status"] == "active"


def test_cliq_app_permissions_accepts_single_permission_dict_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_permissions.return_value = {
        "data": {
            "permissionId": "P_3",
            "permission": "ZohoCliq.CustomDomains.READ",
            "mode": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-permissions", "AP_3"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["permissions"][0]["permissionId"] == "P_3"
    assert payload["permissions"][0]["scope"] == "ZohoCliq.CustomDomains.READ"
    assert payload["permissions"][0]["status"] == "enabled"


def test_cliq_app_permissions_accepts_top_level_single_permission_dict_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_permissions.return_value = {
        "id": "P_4",
        "scope": "ZohoCliq.Apps.READ",
        "state": "active",
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-permissions", "AP_4"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["permissions"][0]["permissionId"] == "P_4"
    assert payload["permissions"][0]["scope"] == "ZohoCliq.Apps.READ"
    assert payload["permissions"][0]["status"] == "active"


def test_cliq_app_permissions_accepts_data_records_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_permissions.return_value = {
        "data": {
            "records": [
                {
                    "id": "P_4R",
                    "scope": "ZohoCliq.Apps.READ",
                    "status": "enabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-permissions", "AP_3", "--limit", "3"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["permissions"][0]["permissionId"] == "P_4R"
    assert payload["permissions"][0]["scope"] == "ZohoCliq.Apps.READ"
    assert payload["permissions"][0]["status"] == "enabled"
    mock_client.list_app_permissions.assert_called_once_with("AP_3", limit=3)


def test_cliq_app_permissions_accepts_data_records_record_row_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_permissions.return_value = {
        "data": {
            "records": {
                "record": {
                    "item": {
                        "id": "P_4RR",
                        "scope": "ZohoCliq.Apps.UPDATE",
                        "status": "enabled",
                    }
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-permissions", "AP_3", "--limit", "3"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["permissions"][0]["permissionId"] == "P_4RR"
    assert payload["permissions"][0]["scope"] == "ZohoCliq.Apps.UPDATE"
    assert payload["permissions"][0]["status"] == "enabled"
    mock_client.list_app_permissions.assert_called_once_with("AP_3", limit=3)


def test_cliq_app_permissions_accepts_data_records_record_item_list_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_permissions.return_value = {
        "data": {
            "records": {
                "record": [
                    {
                        "item": {
                            "permission": {
                                "permissionId": "P_4RIL",
                                "scope": "ZohoCliq.Apps.RECORD.ITEM",
                                "status": "enabled",
                            }
                        }
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-permissions", "AP_3", "--limit", "3"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["permissions"][0]["permissionId"] == "P_4RIL"
    assert payload["permissions"][0]["scope"] == "ZohoCliq.Apps.RECORD.ITEM"
    assert payload["permissions"][0]["status"] == "enabled"
    mock_client.list_app_permissions.assert_called_once_with("AP_3", limit=3)


def test_cliq_app_permissions_accepts_top_level_response_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_permissions.return_value = {
        "response": {
            "result": {
                "data": {
                    "records": {
                        "record": [
                            {
                                "item": {
                                    "permissionId": "P_9R",
                                    "scope": "ZohoCliq.Messages.READ",
                                    "state": "enabled",
                                }
                            }
                        ]
                    }
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-permissions", "AP_9", "--limit", "5"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_9"
    assert payload["count"] == 1
    assert payload["permissions"][0]["permissionId"] == "P_9R"
    assert payload["permissions"][0]["scope"] == "ZohoCliq.Messages.READ"
    assert payload["permissions"][0]["status"] == "enabled"


def test_cliq_app_permissions_accepts_top_level_payload_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_permissions.return_value = {
        "payload": {
            "response": {
                "result": {
                    "data": {
                        "records": {
                            "record": [
                                {
                                    "item": {
                                        "permissionId": "P_9P",
                                        "scope": "ZohoCliq.Messages.WRITE",
                                        "state": "enabled",
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-permissions", "AP_9", "--limit", "5"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_9"
    assert payload["count"] == 1
    assert payload["permissions"][0]["permissionId"] == "P_9P"
    assert payload["permissions"][0]["scope"] == "ZohoCliq.Messages.WRITE"
    assert payload["permissions"][0]["status"] == "enabled"


def test_cliq_app_permissions_accepts_deep_data_records_record_item_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_permissions.return_value = {
        "payload": {
            "response": {
                "result": {
                    "data": {
                        "records": {
                            "record": [
                                {
                                    "item": {
                                        "item": {
                                            "item": {
                                                "permission": {
                                                    "permission_id": "P_9D",
                                                    "scope": "ZohoCliq.Messages.Deep",
                                                    "status": "enabled",
                                                }
                                            }
                                        }
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-permissions", "AP_9", "--limit", "5"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_9"
    assert payload["count"] == 1
    assert payload["permissions"][0]["permissionId"] == "P_9D"
    assert payload["permissions"][0]["scope"] == "ZohoCliq.Messages.Deep"
    assert payload["permissions"][0]["status"] == "enabled"


def test_cliq_app_permissions_accepts_top_level_permission_wrapper_dict_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_permissions.return_value = {
        "permission": {
            "permissionId": "P_5",
            "permission": "ZohoCliq.Bots.READ",
            "mode": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-permissions", "AP_5"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["permissions"][0]["permissionId"] == "P_5"
    assert payload["permissions"][0]["scope"] == "ZohoCliq.Bots.READ"
    assert payload["permissions"][0]["status"] == "enabled"


def test_cliq_app_permissions_accepts_data_list_wrapped_permission_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_permissions.return_value = {
        "data": [
            {
                "permission": {
                    "permissionId": "P_5",
                    "permission": "ZohoCliq.Permissions.READ",
                    "status": "active",
                }
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-permissions", "AP_4", "--limit", "5"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["permissions"][0]["permissionId"] == "P_5"
    assert payload["permissions"][0]["scope"] == "ZohoCliq.Permissions.READ"
    assert payload["permissions"][0]["status"] == "active"


def test_cliq_app_permissions_accepts_data_list_wrapped_item_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_permissions.return_value = {
        "data": [
            {
                "item": {
                    "permissionId": "P_5I",
                    "scope": "ZohoCliq.Bot.Calls.CREATE",
                    "state": "enabled",
                }
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-permissions", "AP_4", "--limit", "5"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["permissions"][0]["permissionId"] == "P_5I"
    assert payload["permissions"][0]["scope"] == "ZohoCliq.Bot.Calls.CREATE"
    assert payload["permissions"][0]["status"] == "enabled"


def test_cliq_app_permission_get(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_permission.return_value = {
        "data": {
            "permission_id": "P_10",
            "scope": "ZohoCliq.Apps.READ",
            "status": "active",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-permission-get", "AP_7", "P_10"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_7"
    assert payload["permission"]["permissionId"] == "P_10"
    assert payload["permission"]["scope"] == "ZohoCliq.Apps.READ"
    assert payload["permission"]["status"] == "active"
    mock_client.get_app_permission.assert_called_once_with("AP_7", "P_10")


def test_cliq_app_permission_get_accepts_nested_permissions_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_permission.return_value = {
        "data": {
            "permissions": [
                {
                    "permissionId": "P_11",
                    "permission": "ZohoCliq.Messages.READ",
                    "state": "enabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-permission-get", "AP_8", "P_11"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["permission"]["permissionId"] == "P_11"
    assert payload["permission"]["scope"] == "ZohoCliq.Messages.READ"
    assert payload["permission"]["status"] == "enabled"


def test_cliq_app_permission_get_accepts_data_list_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_permission.return_value = {
        "data": [
            {
                "id": "P_12",
                "scope": "ZohoCliq.Files.READ",
                "mode": "active",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-permission-get", "AP_9", "P_12"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_9"
    assert payload["permission"]["permissionId"] == "P_12"
    assert payload["permission"]["scope"] == "ZohoCliq.Files.READ"
    assert payload["permission"]["status"] == "active"
    mock_client.get_app_permission.assert_called_once_with("AP_9", "P_12")


def test_cliq_app_permission_get_accepts_data_list_wrapped_permissions_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_permission.return_value = {
        "data": [
            {
                "permissions": {
                    "permissionId": "P_14",
                    "permission": "ZohoCliq.Chats.ALL",
                    "state": "enabled",
                }
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-permission-get", "AP_11", "P_14"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_11"
    assert payload["permission"]["permissionId"] == "P_14"
    assert payload["permission"]["scope"] == "ZohoCliq.Chats.ALL"
    assert payload["permission"]["status"] == "enabled"
    mock_client.get_app_permission.assert_called_once_with("AP_11", "P_14")


def test_cliq_app_permission_get_accepts_data_records_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_permission.return_value = {
        "data": {
            "records": [
                {
                    "id": "P_17R",
                    "scope": "ZohoCliq.Apps.WRITE",
                    "status": "enabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-permission-get", "AP_14", "P_17R"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_14"
    assert payload["permission"]["permissionId"] == "P_17R"
    assert payload["permission"]["scope"] == "ZohoCliq.Apps.WRITE"
    assert payload["permission"]["status"] == "enabled"
    mock_client.get_app_permission.assert_called_once_with("AP_14", "P_17R")


def test_cliq_app_permission_get_accepts_data_records_record_row_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_permission.return_value = {
        "data": {
            "records": [
                {
                    "record": {
                        "permissionId": "P_17RR",
                        "scope": "ZohoCliq.Admin.READ",
                        "state": "enabled",
                    }
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-permission-get", "AP_14", "P_17RR"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_14"
    assert payload["permission"]["permissionId"] == "P_17RR"
    assert payload["permission"]["scope"] == "ZohoCliq.Admin.READ"
    assert payload["permission"]["status"] == "enabled"
    mock_client.get_app_permission.assert_called_once_with("AP_14", "P_17RR")


def test_cliq_app_permission_get_accepts_top_level_permissions_dict_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_permission.return_value = {
        "permissions": {
            "permissionId": "P_13",
            "permission": "ZohoCliq.Chats.ALL",
            "state": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-permission-get", "AP_10", "P_13"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_10"
    assert payload["permission"]["permissionId"] == "P_13"
    assert payload["permission"]["scope"] == "ZohoCliq.Chats.ALL"
    assert payload["permission"]["status"] == "enabled"
    mock_client.get_app_permission.assert_called_once_with("AP_10", "P_13")


def test_cliq_app_permission_get_accepts_top_level_permission_wrapper_list_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_permission.return_value = {
        "permission": [
            {
                "permissionId": "P_14",
                "scope": "ZohoCliq.Tasks.READ",
                "state": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-permission-get", "AP_11", "P_14"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_11"
    assert payload["permission"]["permissionId"] == "P_14"
    assert payload["permission"]["scope"] == "ZohoCliq.Tasks.READ"
    assert payload["permission"]["status"] == "enabled"
    mock_client.get_app_permission.assert_called_once_with("AP_11", "P_14")


def test_cliq_app_permission_get_accepts_top_level_permission_wrapper_list_row_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_permission.return_value = {
        "permission": [
            {
                "permission": {
                    "permissionId": "P_15",
                    "scope": "ZohoCliq.Files.READ",
                    "state": "enabled",
                }
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-permission-get", "AP_12", "P_15"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_12"
    assert payload["permission"]["permissionId"] == "P_15"
    assert payload["permission"]["scope"] == "ZohoCliq.Files.READ"
    assert payload["permission"]["status"] == "enabled"
    mock_client.get_app_permission.assert_called_once_with("AP_12", "P_15")


def test_cliq_app_permission_get_accepts_data_records_record_item_nested_permission_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_permission.return_value = {
        "data": {
            "records": {
                "record": [
                    {
                        "item": {
                            "permission": {
                                "permission": {
                                    "permissionId": "P_15RI",
                                    "scope": "ZohoCliq.Apps.READ",
                                    "status": "enabled",
                                }
                            }
                        }
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-permission-get", "AP_12", "P_15RI"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_12"
    assert payload["permission"]["permissionId"] == "P_15RI"
    assert payload["permission"]["scope"] == "ZohoCliq.Apps.READ"
    assert payload["permission"]["status"] == "enabled"
    mock_client.get_app_permission.assert_called_once_with("AP_12", "P_15RI")


def test_cliq_app_permission_get_accepts_top_level_response_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_permission.return_value = {
        "response": {
            "result": {
                "data": {
                    "records": {
                        "record": [
                            {
                                "item": {
                                    "permission": {
                                        "permissionId": "P_15R",
                                        "scope": "ZohoCliq.Files.READ",
                                        "state": "enabled",
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-permission-get", "AP_12", "P_15R"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_12"
    assert payload["permission"]["permissionId"] == "P_15R"
    assert payload["permission"]["scope"] == "ZohoCliq.Files.READ"
    assert payload["permission"]["status"] == "enabled"
    mock_client.get_app_permission.assert_called_once_with("AP_12", "P_15R")


def test_cliq_app_permission_get_accepts_top_level_payload_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_permission.return_value = {
        "payload": {
            "response": {
                "result": {
                    "data": {
                        "records": {
                            "record": [
                                {
                                    "item": {
                                        "permission": {
                                            "permissionId": "P_15P",
                                            "scope": "ZohoCliq.Messages.READ",
                                            "state": "enabled",
                                        }
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-permission-get", "AP_12", "P_15P"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_12"
    assert payload["permission"]["permissionId"] == "P_15P"
    assert payload["permission"]["scope"] == "ZohoCliq.Messages.READ"
    assert payload["permission"]["status"] == "enabled"
    mock_client.get_app_permission.assert_called_once_with("AP_12", "P_15P")


def test_cliq_app_permission_get_accepts_deep_data_records_record_item_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_permission.return_value = {
        "payload": {
            "response": {
                "result": {
                    "data": {
                        "records": {
                            "record": [
                                {
                                    "item": {
                                        "item": {
                                            "item": {
                                                "permission": {
                                                    "permission_id": "P_15D",
                                                    "scope": "ZohoCliq.Apps.Permission.Deep",
                                                    "status": "enabled",
                                                }
                                            }
                                        }
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-permission-get", "AP_12", "P_15D"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_12"
    assert payload["permission"]["permissionId"] == "P_15D"
    assert payload["permission"]["scope"] == "ZohoCliq.Apps.Permission.Deep"
    assert payload["permission"]["status"] == "enabled"
    mock_client.get_app_permission.assert_called_once_with("AP_12", "P_15D")


def test_cliq_app_installs(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_installs.return_value = {
        "data": [
            {
                "install_id": "I_1",
                "user_id": "U_1",
                "display_name": "Alice Ops",
                "status": "active",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-installs", "AP_1", "--limit", "11"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_1"
    assert payload["count"] == 1
    assert payload["installs"][0]["installId"] == "I_1"
    assert payload["installs"][0]["subjectId"] == "U_1"
    assert payload["installs"][0]["name"] == "Alice Ops"
    assert payload["installs"][0]["status"] == "active"
    mock_client.list_app_installs.assert_called_once_with("AP_1", limit=11)


def test_cliq_app_installs_accepts_subject_id_alias(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_installs.return_value = {
        "data": [
            {
                "installId": "I_1S",
                "subjectId": "S_1S",
                "name": "Subject Alias Install",
                "state": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-installs", "AP_1S"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["installs"][0]["installId"] == "I_1S"
    assert payload["installs"][0]["subjectId"] == "S_1S"
    assert payload["installs"][0]["name"] == "Subject Alias Install"
    assert payload["installs"][0]["status"] == "enabled"
    mock_client.list_app_installs.assert_called_once_with("AP_1S", limit=50)


def test_cliq_app_installs_accepts_nested_installs_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_installs.return_value = {
        "data": {
            "installs": [
                {
                    "id": "I_2",
                    "memberId": "M_2",
                    "name": "Bot Installer",
                    "state": "enabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-installs", "AP_2"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["installs"][0]["installId"] == "I_2"
    assert payload["installs"][0]["subjectId"] == "M_2"
    assert payload["installs"][0]["name"] == "Bot Installer"
    assert payload["installs"][0]["status"] == "enabled"
    mock_client.list_app_installs.assert_called_once_with("AP_2", limit=50)


def test_cliq_app_installs_accepts_single_install_dict_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_installs.return_value = {
        "data": {
            "installId": "I_3",
            "targetId": "U_3",
            "name": "Nightly Bot",
            "mode": "active",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-installs", "AP_3"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["installs"][0]["installId"] == "I_3"
    assert payload["installs"][0]["subjectId"] == "U_3"
    assert payload["installs"][0]["name"] == "Nightly Bot"
    assert payload["installs"][0]["status"] == "active"


def test_cliq_app_installs_accepts_top_level_single_install_dict_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_installs.return_value = {
        "installId": "I_4",
        "chatId": "C_4",
        "display_name": "Escalation Bot",
        "status": "enabled",
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-installs", "AP_4"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["installs"][0]["installId"] == "I_4"
    assert payload["installs"][0]["subjectId"] == "C_4"
    assert payload["installs"][0]["name"] == "Escalation Bot"
    assert payload["installs"][0]["status"] == "enabled"


def test_cliq_app_installs_accepts_data_records_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_installs.return_value = {
        "data": {
            "records": [
                {
                    "id": "I_2R",
                    "name": "Nightly Bot",
                    "state": "active",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-installs", "AP_6", "--limit", "2"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["installs"][0]["installId"] == "I_2R"
    assert payload["installs"][0]["name"] == "Nightly Bot"
    assert payload["installs"][0]["status"] == "active"
    mock_client.list_app_installs.assert_called_once_with("AP_6", limit=2)


def test_cliq_app_installs_accepts_data_records_record_row_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_installs.return_value = {
        "data": {
            "records": {
                "record": {
                    "item": {
                        "id": "I_2RR",
                        "name": "Nightly Bot Wrapped",
                        "state": "active",
                    }
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-installs", "AP_6", "--limit", "2"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["installs"][0]["installId"] == "I_2RR"
    assert payload["installs"][0]["name"] == "Nightly Bot Wrapped"
    assert payload["installs"][0]["status"] == "active"
    mock_client.list_app_installs.assert_called_once_with("AP_6", limit=2)


def test_cliq_app_installs_accepts_data_records_record_item_list_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_installs.return_value = {
        "data": {
            "records": {
                "record": [
                    {
                        "item": {
                            "install": {
                                "installId": "I_2RIL",
                                "name": "Nightly Bot Wrapped Item",
                                "status": "active",
                            }
                        }
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-installs", "AP_6", "--limit", "2"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["installs"][0]["installId"] == "I_2RIL"
    assert payload["installs"][0]["name"] == "Nightly Bot Wrapped Item"
    assert payload["installs"][0]["status"] == "active"
    mock_client.list_app_installs.assert_called_once_with("AP_6", limit=2)


def test_cliq_app_installs_accepts_top_level_install_wrapper_dict_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_installs.return_value = {
        "install": {
            "installId": "I_5",
            "userId": "U_5",
            "name": "Ops Pager",
            "state": "active",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-installs", "AP_5"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["installs"][0]["installId"] == "I_5"
    assert payload["installs"][0]["subjectId"] == "U_5"
    assert payload["installs"][0]["name"] == "Ops Pager"
    assert payload["installs"][0]["status"] == "active"


def test_cliq_app_installs_accepts_data_list_wrapped_install_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_installs.return_value = {
        "data": [
            {
                "install": {
                    "installId": "INS_5",
                    "name": "Ops App",
                    "userId": "U_9",
                    "status": "enabled",
                }
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-installs", "AP_4", "--limit", "9"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["installs"][0]["installId"] == "INS_5"
    assert payload["installs"][0]["name"] == "Ops App"
    assert payload["installs"][0]["subjectId"] == "U_9"
    assert payload["installs"][0]["status"] == "enabled"


def test_cliq_app_installs_accepts_data_list_wrapped_item_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_installs.return_value = {
        "data": [
            {
                "item": {
                    "installId": "INS_5I",
                    "name": "Ops App Item",
                    "memberId": "M_9",
                    "state": "active",
                }
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-installs", "AP_4", "--limit", "9"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["installs"][0]["installId"] == "INS_5I"
    assert payload["installs"][0]["name"] == "Ops App Item"
    assert payload["installs"][0]["subjectId"] == "M_9"
    assert payload["installs"][0]["status"] == "active"


def test_cliq_app_installs_accepts_top_level_response_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_installs.return_value = {
        "response": {
            "result": {
                "data": {
                    "records": {
                        "record": {
                            "item": {
                                "install": {
                                    "installId": "I_5R",
                                    "memberId": "M_5R",
                                    "name": "Ops Pager Wrapped",
                                    "status": "active",
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-installs", "AP_5", "--limit", "2"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["installs"][0]["installId"] == "I_5R"
    assert payload["installs"][0]["subjectId"] == "M_5R"
    assert payload["installs"][0]["name"] == "Ops Pager Wrapped"
    assert payload["installs"][0]["status"] == "active"
    mock_client.list_app_installs.assert_called_once_with("AP_5", limit=2)


def test_cliq_app_installs_accepts_top_level_payload_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_installs.return_value = {
        "payload": {
            "response": {
                "data": {
                    "records": {
                        "record": {
                            "item": {
                                "install": {
                                    "installId": "I_5P",
                                    "memberId": "M_5P",
                                    "name": "Ops Pager Payload",
                                    "status": "active",
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-installs", "AP_5", "--limit", "2"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["installs"][0]["installId"] == "I_5P"
    assert payload["installs"][0]["subjectId"] == "M_5P"
    assert payload["installs"][0]["name"] == "Ops Pager Payload"
    assert payload["installs"][0]["status"] == "active"
    mock_client.list_app_installs.assert_called_once_with("AP_5", limit=2)


def test_cliq_app_installs_accepts_deep_data_records_record_item_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    nested_row: dict[str, Any] = {
        "installId": "I_5D",
        "subject_id": "M_5D",
        "display_name": "Ops Pager Deep",
        "state": "enabled",
    }
    for _ in range(10):
        nested_row = {"item": nested_row}

    mock_client.list_app_installs.return_value = {
        "payload": {
            "response": {
                "result": {
                    "data": {
                        "records": {
                            "record": [nested_row],
                        }
                    }
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-installs", "AP_5", "--limit", "2"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["installs"][0]["installId"] == "I_5D"
    assert payload["installs"][0]["subjectId"] == "M_5D"
    assert payload["installs"][0]["name"] == "Ops Pager Deep"
    assert payload["installs"][0]["status"] == "enabled"
    mock_client.list_app_installs.assert_called_once_with("AP_5", limit=2)


def test_cliq_app_install_get(mock_config: Path, mock_token_refresh: Any) -> None:
    mock_client = MagicMock()
    mock_client.get_app_install.return_value = {
        "data": {
            "install_id": "INS_10",
            "member_id": "M_1",
            "name": "Deploy Bot",
            "status": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-install-get", "AP_7", "INS_10"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_7"
    assert payload["install"]["installId"] == "INS_10"
    assert payload["install"]["subjectId"] == "M_1"
    assert payload["install"]["name"] == "Deploy Bot"
    assert payload["install"]["status"] == "enabled"
    mock_client.get_app_install.assert_called_once_with("AP_7", "INS_10")


def test_cliq_app_install_get_accepts_nested_installs_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_install.return_value = {
        "data": {
            "installs": [
                {
                    "id": "INS_11",
                    "userId": "U_2",
                    "title": "Ops Workflow",
                    "state": "active",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-install-get", "AP_8", "INS_11"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_8"
    assert payload["install"]["installId"] == "INS_11"
    assert payload["install"]["subjectId"] == "U_2"
    assert payload["install"]["name"] == "Ops Workflow"
    assert payload["install"]["status"] == "active"
    mock_client.get_app_install.assert_called_once_with("AP_8", "INS_11")


def test_cliq_app_install_get_accepts_data_list_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_install.return_value = {
        "data": [
            {
                "id": "INS_12",
                "target_id": "U_3",
                "display_name": "Support Bot",
                "state": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-install-get", "AP_9", "INS_12"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_9"
    assert payload["install"]["installId"] == "INS_12"
    assert payload["install"]["subjectId"] == "U_3"
    assert payload["install"]["name"] == "Support Bot"
    assert payload["install"]["status"] == "enabled"
    mock_client.get_app_install.assert_called_once_with("AP_9", "INS_12")


def test_cliq_app_install_get_accepts_data_list_wrapped_installs_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_install.return_value = {
        "data": [
            {
                "installs": {
                    "installId": "INS_14",
                    "chatId": "C_14",
                    "title": "Incident Flow",
                    "mode": "active",
                }
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-install-get", "AP_11", "INS_14"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_11"
    assert payload["install"]["installId"] == "INS_14"
    assert payload["install"]["subjectId"] == "C_14"
    assert payload["install"]["name"] == "Incident Flow"
    assert payload["install"]["status"] == "active"
    mock_client.get_app_install.assert_called_once_with("AP_11", "INS_14")


def test_cliq_app_install_get_accepts_top_level_response_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_install.return_value = {
        "response": {
            "result": {
                "data": {
                    "records": {
                        "record": {
                            "item": {
                                "install": {
                                    "installId": "INS_14R",
                                    "chatId": "C_14R",
                                    "title": "Incident Flow Wrapped",
                                    "mode": "active",
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-install-get", "AP_11", "INS_14R"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_11"
    assert payload["install"]["installId"] == "INS_14R"
    assert payload["install"]["subjectId"] == "C_14R"
    assert payload["install"]["name"] == "Incident Flow Wrapped"
    assert payload["install"]["status"] == "active"
    mock_client.get_app_install.assert_called_once_with("AP_11", "INS_14R")


def test_cliq_app_install_get_accepts_top_level_payload_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_install.return_value = {
        "payload": {
            "result": {
                "data": {
                    "records": {
                        "record": {
                            "item": {
                                "install": {
                                    "installId": "INS_14P",
                                    "chatId": "C_14P",
                                    "title": "Incident Flow Payload",
                                    "mode": "active",
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-install-get", "AP_11", "INS_14P"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_11"
    assert payload["install"]["installId"] == "INS_14P"
    assert payload["install"]["subjectId"] == "C_14P"
    assert payload["install"]["name"] == "Incident Flow Payload"
    assert payload["install"]["status"] == "active"
    mock_client.get_app_install.assert_called_once_with("AP_11", "INS_14P")


def test_cliq_app_install_get_accepts_deep_data_records_record_item_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_install.return_value = {
        "payload": {
            "response": {
                "result": {
                    "data": {
                        "records": {
                            "record": {
                                "item": {
                                    "payload": {
                                        "response": {
                                            "result": {
                                                "data": {
                                                    "records": {
                                                        "record": {
                                                            "item": {
                                                                "install": {
                                                                    "installId": "INS_14D",
                                                                    "subjectId": "C_14D",
                                                                    "title": "Deep Install Wrapper",
                                                                    "state": "enabled",
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-install-get", "AP_11", "INS_14D"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_11"
    assert payload["install"]["installId"] == "INS_14D"
    assert payload["install"]["subjectId"] == "C_14D"
    assert payload["install"]["name"] == "Deep Install Wrapper"
    assert payload["install"]["status"] == "enabled"
    mock_client.get_app_install.assert_called_once_with("AP_11", "INS_14D")


def test_cliq_app_install_get_accepts_data_records_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_install.return_value = {
        "data": {
            "records": [
                {
                    "id": "I_10R",
                    "name": "Incident Bot",
                    "state": "active",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-install-get", "AP_8", "I_10R"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_8"
    assert payload["install"]["installId"] == "I_10R"
    assert payload["install"]["name"] == "Incident Bot"
    assert payload["install"]["status"] == "active"
    mock_client.get_app_install.assert_called_once_with("AP_8", "I_10R")


def test_cliq_app_install_get_accepts_data_records_record_row_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_install.return_value = {
        "data": {
            "records": [
                {
                    "record": {
                        "installId": "I_10RR",
                        "userId": "U_10RR",
                        "name": "Incident Bot 2",
                        "mode": "enabled",
                    }
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-install-get", "AP_8", "I_10RR"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_8"
    assert payload["install"]["installId"] == "I_10RR"
    assert payload["install"]["subjectId"] == "U_10RR"
    assert payload["install"]["name"] == "Incident Bot 2"
    assert payload["install"]["status"] == "enabled"
    mock_client.get_app_install.assert_called_once_with("AP_8", "I_10RR")


def test_cliq_app_install_get_accepts_top_level_installs_dict_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_install.return_value = {
        "installs": {
            "installId": "INS_13",
            "chatId": "C_13",
            "title": "Escalation Route",
            "mode": "active",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-install-get", "AP_10", "INS_13"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_10"
    assert payload["install"]["installId"] == "INS_13"
    assert payload["install"]["subjectId"] == "C_13"
    assert payload["install"]["name"] == "Escalation Route"
    assert payload["install"]["status"] == "active"
    mock_client.get_app_install.assert_called_once_with("AP_10", "INS_13")


def test_cliq_app_install_get_accepts_top_level_install_wrapper_list_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_install.return_value = {
        "install": [
            {
                "installId": "INS_15",
                "chatId": "C_15",
                "title": "Shift Handoff",
                "mode": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-install-get", "AP_12", "INS_15"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_12"
    assert payload["install"]["installId"] == "INS_15"
    assert payload["install"]["subjectId"] == "C_15"
    assert payload["install"]["name"] == "Shift Handoff"
    assert payload["install"]["status"] == "enabled"
    mock_client.get_app_install.assert_called_once_with("AP_12", "INS_15")


def test_cliq_app_install_get_accepts_top_level_install_wrapper_list_row_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_install.return_value = {
        "install": [
            {
                "install": {
                    "installId": "INS_16",
                    "chatId": "C_16",
                    "title": "Pager Duty",
                    "mode": "active",
                }
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-install-get", "AP_13", "INS_16"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["install"]["installId"] == "INS_16"
    assert payload["install"]["subjectId"] == "C_16"
    assert payload["install"]["name"] == "Pager Duty"
    assert payload["install"]["status"] == "active"
    mock_client.get_app_install.assert_called_once_with("AP_13", "INS_16")


def test_cliq_app_install_get_accepts_data_records_record_item_nested_install_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_install.return_value = {
        "data": {
            "records": {
                "record": [
                    {
                        "item": {
                            "install": {
                                "install": {
                                    "installId": "INS_16RI",
                                    "chatId": "C_16RI",
                                    "title": "Pager Duty",
                                    "mode": "active",
                                }
                            }
                        }
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-install-get", "AP_13", "INS_16RI"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["install"]["installId"] == "INS_16RI"
    assert payload["install"]["subjectId"] == "C_16RI"
    assert payload["install"]["name"] == "Pager Duty"
    assert payload["install"]["status"] == "active"
    mock_client.get_app_install.assert_called_once_with("AP_13", "INS_16RI")


def test_cliq_app_commands(mock_config: Path, mock_token_refresh: Any) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "command_id": "CMD_1",
                "name": "deploy",
                "description": "Trigger deployment",
                "status": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_1", "--limit", "9"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_1"
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_1"
    assert payload["commands"][0]["name"] == "deploy"
    assert payload["commands"][0]["description"] == "Trigger deployment"
    assert payload["commands"][0]["status"] == "enabled"
    mock_client.list_app_commands.assert_called_once_with("AP_1", limit=9)


def test_cliq_app_commands_accepts_nested_commands_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": {
            "commands": [
                {
                    "id": "CMD_2",
                    "title": "triage",
                    "helpText": "Open triage workflow",
                    "state": "active",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_2"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commands"][0]["commandId"] == "CMD_2"
    assert payload["commands"][0]["name"] == "triage"
    assert payload["commands"][0]["description"] == "Open triage workflow"
    assert payload["commands"][0]["status"] == "active"
    mock_client.list_app_commands.assert_called_once_with("AP_2", limit=50)


def test_cliq_app_commands_accepts_single_command_dict_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": {
            "commandId": "CMD_3",
            "command": "notify_oncall",
            "summary": "Notify on-call contact",
            "mode": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_3"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_3"
    assert payload["commands"][0]["name"] == "notify_oncall"
    assert payload["commands"][0]["description"] == "Notify on-call contact"
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_top_level_single_command_dict_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "commandId": "CMD_4",
        "name": "daily_digest",
        "summary": "Send daily digest",
        "state": "active",
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_4"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_4"
    assert payload["commands"][0]["name"] == "daily_digest"
    assert payload["commands"][0]["description"] == "Send daily digest"
    assert payload["commands"][0]["status"] == "active"


def test_cliq_app_commands_accepts_data_records_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": {
            "records": [
                {
                    "id": "CMD_11R",
                    "name": "daily_digest",
                    "status": "enabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_7", "--limit", "3"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_11R"
    assert payload["commands"][0]["name"] == "daily_digest"
    assert payload["commands"][0]["status"] == "enabled"
    mock_client.list_app_commands.assert_called_once_with("AP_7", limit=3)


def test_cliq_app_commands_accepts_data_records_record_row_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": {
            "records": {
                "record": {
                    "item": {
                        "id": "CMD_11RR",
                        "action": "daily_digest_wrapped",
                        "state": "enabled",
                    }
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_7", "--limit", "3"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_11RR"
    assert payload["commands"][0]["name"] == "daily_digest_wrapped"
    assert payload["commands"][0]["status"] == "enabled"
    mock_client.list_app_commands.assert_called_once_with("AP_7", limit=3)


def test_cliq_app_commands_accepts_data_records_record_item_list_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": {
            "records": {
                "record": [
                    {
                        "item": {
                            "command": {
                                "commandId": "CMD_11RIL",
                                "name": "daily_digest_record_item",
                                "status": "enabled",
                            }
                        }
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_7", "--limit", "3"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_11RIL"
    assert payload["commands"][0]["name"] == "daily_digest_record_item"
    assert payload["commands"][0]["status"] == "enabled"
    mock_client.list_app_commands.assert_called_once_with("AP_7", limit=3)


def test_cliq_app_commands_accepts_top_level_command_wrapper_dict_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "command": {
            "commandId": "CMD_5",
            "name": "incident_resolve",
            "summary": "Resolve the active incident",
            "mode": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_5"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_5"
    assert payload["commands"][0]["name"] == "incident_resolve"
    assert payload["commands"][0]["description"] == "Resolve the active incident"
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_uppercase_command_wrapper_dict_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "COMMAND": {
            "COMMANDID": "CMD_5UP",
            "ACTIONNAME": "incident_resolve_upper",
            "SUMMARY": "Resolve via uppercase wrapper",
            "MODE": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_5"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_5UP"
    assert payload["commands"][0]["name"] == "incident_resolve_upper"
    assert payload["commands"][0]["description"] == "Resolve via uppercase wrapper"
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_data_list_wrapped_command_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "command": {
                    "commandId": "CMD_7",
                    "name": "escalate",
                    "summary": "Escalate incidents",
                    "status": "active",
                }
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_4", "--limit", "5"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_7"
    assert payload["commands"][0]["name"] == "escalate"
    assert payload["commands"][0]["description"] == "Escalate incidents"
    assert payload["commands"][0]["status"] == "active"


def test_cliq_app_commands_accepts_data_list_wrapped_item_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "item": {
                    "commandId": "CMD_7I",
                    "name": "escalate_item",
                    "summary": "Escalate incidents via item wrapper",
                    "state": "enabled",
                }
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_4", "--limit", "5"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_7I"
    assert payload["commands"][0]["name"] == "escalate_item"
    assert (
        payload["commands"][0]["description"] == "Escalate incidents via item wrapper"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_nested_action_wrapper_dict_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": {
            "action": {
                "commandId": "CMD_6",
                "action": "triage_incident",
                "summary": "Triage a new incident",
                "mode": "active",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_6"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_6"
    assert payload["commands"][0]["name"] == "triage_incident"
    assert payload["commands"][0]["description"] == "Triage a new incident"
    assert payload["commands"][0]["status"] == "active"


def test_cliq_app_commands_accepts_top_level_response_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "response": {
            "data": {
                "records": {
                    "record": [
                        {
                            "item": {
                                "command": {
                                    "commandId": "CMD_6R",
                                    "name": "triage_incident_response",
                                    "summary": "Triage from response envelope",
                                    "mode": "active",
                                }
                            }
                        }
                    ]
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_6"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_6R"
    assert payload["commands"][0]["name"] == "triage_incident_response"
    assert payload["commands"][0]["description"] == "Triage from response envelope"
    assert payload["commands"][0]["status"] == "active"


def test_cliq_app_commands_accepts_top_level_payload_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "result": {
                "data": {
                    "records": {
                        "record": [
                            {
                                "item": {
                                    "command": {
                                        "commandId": "CMD_8PW",
                                        "name": "deploy_release_payload",
                                        "summary": "Deploy release payload wrapped",
                                        "mode": "enabled",
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_8"
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8PW"
    assert payload["commands"][0]["name"] == "deploy_release_payload"
    assert payload["commands"][0]["description"] == "Deploy release payload wrapped"
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_deep_data_records_record_item_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    nested_row: dict[str, Any] = {
        "command": {
            "commandId": "CMD_8DEEP",
            "name": "deep_payload_command",
            "summary": "Deep payload list wrapper",
            "mode": "enabled",
        }
    }
    for _ in range(9):
        nested_row = {"item": nested_row}

    mock_client.list_app_commands.return_value = {
        "payload": {
            "result": {
                "data": {
                    "records": {
                        "record": [nested_row],
                    }
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_8"
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8DEEP"
    assert payload["commands"][0]["name"] == "deep_payload_command"
    assert payload["commands"][0]["description"] == "Deep payload list wrapper"
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_command_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": {
            "commands": [
                {
                    "command_id": "CMD_8ALIAS",
                    "command_name": "deploy_release_alias",
                    "summary": "Deploy release from command_name",
                    "mode": "enabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_8"
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8ALIAS"
    assert payload["commands"][0]["name"] == "deploy_release_alias"
    assert payload["commands"][0]["description"] == "Deploy release from command_name"
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_command_name_camel_case_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": {
            "commands": [
                {
                    "command_id": "CMD_8CAMEL",
                    "commandName": "deploy_release_camel_alias",
                    "summary": "Deploy release from commandName",
                    "mode": "enabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_8"
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8CAMEL"
    assert payload["commands"][0]["name"] == "deploy_release_camel_alias"
    assert payload["commands"][0]["description"] == "Deploy release from commandName"
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_action_id_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": {
            "commands": [
                {
                    "actionId": "ACT_8ALIAS",
                    "actionName": "incident_ack_alias",
                    "summary": "ack now",
                    "state": "enabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_8"
    assert payload["commands"][0]["commandId"] == "ACT_8ALIAS"
    assert payload["commands"][0]["name"] == "incident_ack_alias"
    assert payload["commands"][0]["description"] == "ack now"
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_action_id_pascal_case_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": {
            "commands": [
                {
                    "ActionID": "ACT_8PASCAL",
                    "actionName": "incident_ack_pascal_alias",
                    "summary": "ack now via pascal id",
                    "state": "enabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_8"
    assert payload["commands"][0]["commandId"] == "ACT_8PASCAL"
    assert payload["commands"][0]["name"] == "incident_ack_pascal_alias"
    assert payload["commands"][0]["description"] == "ack now via pascal id"
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_actionid_lowercase_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {
                    "actionid": "ACT_8LOWER",
                    "actionName": "incident_ack_lowercase_actionid_alias",
                    "summary": "ack now via lowercase actionid",
                    "state": "enabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_8"
    assert payload["commands"][0]["commandId"] == "ACT_8LOWER"
    assert payload["commands"][0]["name"] == "incident_ack_lowercase_actionid_alias"
    assert payload["commands"][0]["description"] == "ack now via lowercase actionid"
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_flat_lower_command_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {
                    "commandid": "CMD_8LOWERNAME",
                    "actionname": "incident_ack_flat_lower_name_alias",
                    "summary": "ack now via flat-lower name alias",
                    "state": "enabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_8"
    assert payload["commands"][0]["commandId"] == "CMD_8LOWERNAME"
    assert payload["commands"][0]["name"] == "incident_ack_flat_lower_name_alias"
    assert payload["commands"][0]["description"] == "ack now via flat-lower name alias"
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_uppercase_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {
                    "COMMANDID": "CMD_8UPPER",
                    "ACTIONNAME": "incident_ack_uppercase_alias",
                    "SUMMARY": "ack now via uppercase aliases",
                    "STATUS": "enabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_8"
    assert payload["commands"][0]["commandId"] == "CMD_8UPPER"
    assert payload["commands"][0]["name"] == "incident_ack_uppercase_alias"
    assert payload["commands"][0]["description"] == "ack now via uppercase aliases"
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_command_id_pascal_case_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {
                    "CommandID": "CMD_8PASCALID",
                    "actionName": "incident_ack_pascal_command_id_alias",
                    "summary": "ack via pascal command id",
                    "state": "enabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_8"
    assert payload["commands"][0]["commandId"] == "CMD_8PASCALID"
    assert payload["commands"][0]["name"] == "incident_ack_pascal_command_id_alias"
    assert payload["commands"][0]["description"] == "ack via pascal command id"
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_pascal_case_description_and_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {
                    "CommandID": "CMD_13PASCALDESC",
                    "ActionName": "deploy_from_pascal_description_alias",
                    "Description": "dispatch pascal description alias",
                    "Status": "enabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_13"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["commands"][0]["commandId"] == "CMD_13PASCALDESC"
    assert payload["commands"][0]["name"] == "deploy_from_pascal_description_alias"
    assert payload["commands"][0]["description"] == "dispatch pascal description alias"
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_command_prefixed_description_and_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {
                    "commandID": "CMD_13PREFIXED",
                    "actionName": "deploy_list_prefixed_alias",
                    "commandDescription": "dispatch list prefixed alias",
                    "commandStatus": "enabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_13"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["commands"][0]["commandId"] == "CMD_13PREFIXED"
    assert payload["commands"][0]["name"] == "deploy_list_prefixed_alias"
    assert payload["commands"][0]["description"] == "dispatch list prefixed alias"
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_flat_lower_command_prefixed_description_and_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {
                    "commandID": "CMD_13FLATLOWERPREFIXED",
                    "actionName": "deploy_flat_lower_prefixed_alias",
                    "commanddescription": "dispatch flat lower prefixed alias",
                    "commandstatus": "enabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_13"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["commands"][0]["commandId"] == "CMD_13FLATLOWERPREFIXED"
    assert payload["commands"][0]["name"] == "deploy_flat_lower_prefixed_alias"
    assert payload["commands"][0]["description"] == "dispatch flat lower prefixed alias"
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_pascal_case_command_prefixed_description_and_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {
                    "commandID": "CMD_13PREFIXEDPASCAL",
                    "actionName": "deploy_prefixed_pascal_alias",
                    "CommandDescription": "dispatch prefixed pascal alias",
                    "CommandStatus": "enabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_13"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["commands"][0]["commandId"] == "CMD_13PREFIXEDPASCAL"
    assert payload["commands"][0]["name"] == "deploy_prefixed_pascal_alias"
    assert payload["commands"][0]["description"] == "dispatch prefixed pascal alias"
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_command_mode_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {
                    "commandID": "CMD_13MODEALIAS",
                    "actionName": "deploy_command_mode_alias",
                    "Description": "dispatch command mode alias",
                    "commandMode": "disabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_13"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["commands"][0]["commandId"] == "CMD_13MODEALIAS"
    assert payload["commands"][0]["name"] == "deploy_command_mode_alias"
    assert payload["commands"][0]["description"] == "dispatch command mode alias"
    assert payload["commands"][0]["status"] == "disabled"


def test_cliq_app_commands_accepts_kebab_command_mode_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {
                    "commandID": "CMD_13KEBABMODEALIAS",
                    "actionName": "deploy_command_kebab_mode_alias",
                    "Description": "dispatch command kebab mode alias",
                    "command-mode": "enabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_13"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["commands"][0]["commandId"] == "CMD_13KEBABMODEALIAS"
    assert payload["commands"][0]["name"] == "deploy_command_kebab_mode_alias"
    assert payload["commands"][0]["description"] == "dispatch command kebab mode alias"
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_kebab_command_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {
                    "commandID": "CMD_13KEBABSTATUSALIAS",
                    "actionName": "deploy_command_kebab_status_alias",
                    "Description": "dispatch command kebab status alias",
                    "command-status": "enabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_13"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["commands"][0]["commandId"] == "CMD_13KEBABSTATUSALIAS"
    assert payload["commands"][0]["name"] == "deploy_command_kebab_status_alias"
    assert (
        payload["commands"][0]["description"] == "dispatch command kebab status alias"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_kebab_upper_tail_command_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {
                    "commandID": "CMD_13KEBABUPPERSTATUSALIAS",
                    "actionName": "deploy_command_kebab_upper_status_alias",
                    "Description": "dispatch command kebab+upper status alias",
                    "command-STATUS": "disabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_13"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["commands"][0]["commandId"] == "CMD_13KEBABUPPERSTATUSALIAS"
    assert payload["commands"][0]["name"] == "deploy_command_kebab_upper_status_alias"
    assert (
        payload["commands"][0]["description"]
        == "dispatch command kebab+upper status alias"
    )
    assert payload["commands"][0]["status"] == "disabled"


def test_cliq_app_commands_accepts_kebab_upper_tail_command_mode_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {
                    "commandID": "CMD_13KEBABUPPERMODEALIAS",
                    "actionName": "deploy_command_kebab_upper_mode_alias",
                    "Description": "dispatch command kebab+upper mode alias",
                    "command-MODE": "enabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_13"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["commands"][0]["commandId"] == "CMD_13KEBABUPPERMODEALIAS"
    assert payload["commands"][0]["name"] == "deploy_command_kebab_upper_mode_alias"
    assert (
        payload["commands"][0]["description"]
        == "dispatch command kebab+upper mode alias"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_snake_pascal_tail_command_mode_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {
                    "commandID": "CMD_13SNAKEPASCALMODEALIAS",
                    "actionName": "deploy_command_snake_pascal_mode_alias",
                    "Description": "dispatch command snake+Pascal mode alias",
                    "command_Mode": "disabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_13"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["commands"][0]["commandId"] == "CMD_13SNAKEPASCALMODEALIAS"
    assert payload["commands"][0]["name"] == "deploy_command_snake_pascal_mode_alias"
    assert (
        payload["commands"][0]["description"]
        == "dispatch command snake+Pascal mode alias"
    )
    assert payload["commands"][0]["status"] == "disabled"


def test_cliq_app_commands_accepts_snake_upper_tail_command_mode_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {
                    "commandID": "CMD_13SNAKEUPPERMODEALIAS",
                    "actionName": "deploy_command_snake_upper_mode_alias",
                    "Description": "dispatch command snake+upper mode alias",
                    "command_MODE": "enabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_13"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["commands"][0]["commandId"] == "CMD_13SNAKEUPPERMODEALIAS"
    assert payload["commands"][0]["name"] == "deploy_command_snake_upper_mode_alias"
    assert (
        payload["commands"][0]["description"]
        == "dispatch command snake+upper mode alias"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_snake_upper_tail_pascal_prefix_command_mode_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {
                    "commandID": "CMD_13SNAKEUPPERPASCALMODEALIAS",
                    "actionName": "deploy_command_snake_upper_pascal_mode_alias",
                    "Description": "dispatch command snake+upper Pascal mode alias",
                    "Command_MODE": "disabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_13"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["commands"][0]["commandId"] == "CMD_13SNAKEUPPERPASCALMODEALIAS"
    assert (
        payload["commands"][0]["name"] == "deploy_command_snake_upper_pascal_mode_alias"
    )
    assert (
        payload["commands"][0]["description"]
        == "dispatch command snake+upper Pascal mode alias"
    )
    assert payload["commands"][0]["status"] == "disabled"


def test_cliq_app_commands_accepts_snake_pascal_tail_command_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {
                    "commandID": "CMD_13SNAKEPASCALSTATUSALIAS",
                    "actionName": "deploy_command_snake_pascal_status_alias",
                    "Description": "dispatch command snake+Pascal status alias",
                    "command_Status": "enabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_13"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["commands"][0]["commandId"] == "CMD_13SNAKEPASCALSTATUSALIAS"
    assert payload["commands"][0]["name"] == "deploy_command_snake_pascal_status_alias"
    assert (
        payload["commands"][0]["description"]
        == "dispatch command snake+Pascal status alias"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_snake_upper_tail_command_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {
                    "commandID": "CMD_13SNAKEUPPERSTATUSALIAS",
                    "actionName": "deploy_command_snake_upper_status_alias",
                    "Description": "dispatch command snake+upper status alias",
                    "command_STATUS": "disabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_13"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["commands"][0]["commandId"] == "CMD_13SNAKEUPPERSTATUSALIAS"
    assert payload["commands"][0]["name"] == "deploy_command_snake_upper_status_alias"
    assert (
        payload["commands"][0]["description"]
        == "dispatch command snake+upper status alias"
    )
    assert payload["commands"][0]["status"] == "disabled"


def test_cliq_app_commands_accepts_command_prefixed_help_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "CommandID": "CMD_13PASCALHELP",
                "actionName": "deploy_pascal_help",
                "CommandHelpText": "deploy through command help text",
                "ActionHelp": "deploy through action help",
                "commandStatus": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["--config", str(mock_config), "cliq", "app-commands", "AP_13"],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commands"][0]["commandId"] == "CMD_13PASCALHELP"
    assert payload["commands"][0]["name"] == "deploy_pascal_help"
    assert payload["commands"][0]["description"] == "deploy through command help text"
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_flat_lower_command_prefixed_help_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "CommandID": "CMD_13LOWERHELP",
                "actionName": "deploy_lower_help",
                "commandhelptext": "deploy through lower command help text",
                "actionhelp": "deploy through lower action help",
                "commandStatus": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["--config", str(mock_config), "cliq", "app-commands", "AP_13"],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commands"][0]["commandId"] == "CMD_13LOWERHELP"
    assert payload["commands"][0]["name"] == "deploy_lower_help"
    assert (
        payload["commands"][0]["description"]
        == "deploy through lower command help text"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_kebab_command_prefixed_help_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "CommandID": "CMD_13KEBABHELP",
                "actionName": "deploy_kebab_help",
                "command-help-text": "deploy through kebab command help text",
                "action-help": "deploy through kebab action help",
                "commandStatus": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["--config", str(mock_config), "cliq", "app-commands", "AP_13"],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commands"][0]["commandId"] == "CMD_13KEBABHELP"
    assert payload["commands"][0]["name"] == "deploy_kebab_help"
    assert (
        payload["commands"][0]["description"]
        == "deploy through kebab command help text"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_kebab_command_prefixed_helptext_camel_tail_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "CommandID": "CMD_13KEBABHELPMIXED",
                "actionName": "deploy_kebab_help_mixed",
                "command-helpText": "deploy through kebab command help mixed alias",
                "commandStatus": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["--config", str(mock_config), "cliq", "app-commands", "AP_13"],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commands"][0]["commandId"] == "CMD_13KEBABHELPMIXED"
    assert payload["commands"][0]["name"] == "deploy_kebab_help_mixed"
    assert (
        payload["commands"][0]["description"]
        == "deploy through kebab command help mixed alias"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_snake_camel_tail_command_prefixed_helptext_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "CommandID": "CMD_13SNAKEHELPMIXED",
                "actionName": "deploy_snake_help_mixed",
                "command_helpText": "deploy through snake command help mixed alias",
                "commandStatus": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["--config", str(mock_config), "cliq", "app-commands", "AP_13"],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commands"][0]["commandId"] == "CMD_13SNAKEHELPMIXED"
    assert payload["commands"][0]["name"] == "deploy_snake_help_mixed"
    assert (
        payload["commands"][0]["description"]
        == "deploy through snake command help mixed alias"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_snake_pascal_tail_command_prefixed_helptext_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "CommandID": "CMD_13SNAKEPASCALTAILHELP",
                "actionName": "deploy_snake_pascal_tail_help",
                "command_HelpText": "deploy through snake+Pascal-tail command help",
                "commandStatus": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["--config", str(mock_config), "cliq", "app-commands", "AP_13"],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commands"][0]["commandId"] == "CMD_13SNAKEPASCALTAILHELP"
    assert payload["commands"][0]["name"] == "deploy_snake_pascal_tail_help"
    assert (
        payload["commands"][0]["description"]
        == "deploy through snake+Pascal-tail command help"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_snake_pascal_camel_title_tail_command_prefixed_helptext_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "CommandID": "CMD_13SNAKEPASCALCAMELTITLETAILHELP",
                "actionName": "deploy_snake_pascal_camel_title_tail_help",
                "command_Helptext": "deploy through snake+Pascal-camel-title-tail command help",
                "commandStatus": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["--config", str(mock_config), "cliq", "app-commands", "AP_13"],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commands"][0]["commandId"] == "CMD_13SNAKEPASCALCAMELTITLETAILHELP"
    assert payload["commands"][0]["name"] == "deploy_snake_pascal_camel_title_tail_help"
    assert (
        payload["commands"][0]["description"]
        == "deploy through snake+Pascal-camel-title-tail command help"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_snake_pascal_triple_command_prefixed_help_text_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "CommandID": "CMD_13SNAKEPASCALTRIPLEHELP",
                "actionName": "deploy_snake_pascal_triple_help",
                "command_Help_Text": "deploy through snake+Pascal triple command help",
                "commandStatus": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["--config", str(mock_config), "cliq", "app-commands", "AP_13"],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commands"][0]["commandId"] == "CMD_13SNAKEPASCALTRIPLEHELP"
    assert payload["commands"][0]["name"] == "deploy_snake_pascal_triple_help"
    assert (
        payload["commands"][0]["description"]
        == "deploy through snake+Pascal triple command help"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_snake_upper_tail_triple_command_prefixed_help_text_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "CommandID": "CMD_13SNAKEUPPERTRIPLEHELP",
                "actionName": "deploy_snake_upper_triple_help",
                "command_HELP_TEXT": "deploy through snake+upper-tail triple command help",
                "commandStatus": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["--config", str(mock_config), "cliq", "app-commands", "AP_13"],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commands"][0]["commandId"] == "CMD_13SNAKEUPPERTRIPLEHELP"
    assert payload["commands"][0]["name"] == "deploy_snake_upper_triple_help"
    assert (
        payload["commands"][0]["description"]
        == "deploy through snake+upper-tail triple command help"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_pascal_snake_triple_command_prefixed_help_text_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "CommandID": "CMD_13PASCALSNAKETRIPLEHELP",
                "actionName": "deploy_pascal_snake_triple_help",
                "Command_Help_Text": "deploy through Pascal+snake triple command help",
                "commandStatus": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["--config", str(mock_config), "cliq", "app-commands", "AP_13"],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commands"][0]["commandId"] == "CMD_13PASCALSNAKETRIPLEHELP"
    assert payload["commands"][0]["name"] == "deploy_pascal_snake_triple_help"
    assert (
        payload["commands"][0]["description"]
        == "deploy through Pascal+snake triple command help"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_pascal_snake_lower_tail_command_prefixed_help_text_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "CommandID": "CMD_13PASCALSNAKELOWERHELP",
                "actionName": "deploy_pascal_snake_lower_help",
                "Command_help_text": "deploy through Pascal+snake lower-tail command help",
                "commandStatus": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["--config", str(mock_config), "cliq", "app-commands", "AP_13"],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commands"][0]["commandId"] == "CMD_13PASCALSNAKELOWERHELP"
    assert payload["commands"][0]["name"] == "deploy_pascal_snake_lower_help"
    assert (
        payload["commands"][0]["description"]
        == "deploy through Pascal+snake lower-tail command help"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_pascal_snake_kebab_pascal_tail_command_prefixed_help_text_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "CommandID": "CMD_13PASCALSNAKEKEBABPASCALHELP",
                "actionName": "deploy_pascal_snake_kebab_pascal_help",
                "Command_help-Text": "deploy through Pascal+snake+kebab Pascal-tail command help",
                "commandStatus": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["--config", str(mock_config), "cliq", "app-commands", "AP_13"],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commands"][0]["commandId"] == "CMD_13PASCALSNAKEKEBABPASCALHELP"
    assert payload["commands"][0]["name"] == "deploy_pascal_snake_kebab_pascal_help"
    assert (
        payload["commands"][0]["description"]
        == "deploy through Pascal+snake+kebab Pascal-tail command help"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_kebab_pascal_tail_command_prefixed_help_text_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "CommandID": "CMD_13KEBABPASCALTAILHELP",
                "actionName": "deploy_kebab_pascal_tail_help",
                "command-HelpText": "deploy through kebab+Pascal-tail command help",
                "commandStatus": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["--config", str(mock_config), "cliq", "app-commands", "AP_13"],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commands"][0]["commandId"] == "CMD_13KEBABPASCALTAILHELP"
    assert payload["commands"][0]["name"] == "deploy_kebab_pascal_tail_help"
    assert (
        payload["commands"][0]["description"]
        == "deploy through kebab+Pascal-tail command help"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_kebab_upper_tail_triple_command_prefixed_help_text_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "CommandID": "CMD_13KEBABUPPERTRIPLEHELP",
                "actionName": "deploy_kebab_upper_triple_help",
                "command-HELP-TEXT": "deploy through kebab+upper-tail triple command help",
                "commandStatus": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["--config", str(mock_config), "cliq", "app-commands", "AP_13"],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commands"][0]["commandId"] == "CMD_13KEBABUPPERTRIPLEHELP"
    assert payload["commands"][0]["name"] == "deploy_kebab_upper_triple_help"
    assert (
        payload["commands"][0]["description"]
        == "deploy through kebab+upper-tail triple command help"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_snake_kebab_upper_tail_triple_command_prefixed_help_text_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "CommandID": "CMD_13SNAKEKEBABUPPERTRIPLEHELP",
                "actionName": "deploy_snake_kebab_upper_triple_help",
                "command_HELP-TEXT": "deploy through snake+kebab upper-tail triple command help",
                "commandStatus": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["--config", str(mock_config), "cliq", "app-commands", "AP_13"],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commands"][0]["commandId"] == "CMD_13SNAKEKEBABUPPERTRIPLEHELP"
    assert payload["commands"][0]["name"] == "deploy_snake_kebab_upper_triple_help"
    assert (
        payload["commands"][0]["description"]
        == "deploy through snake+kebab upper-tail triple command help"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_kebab_upper_snake_tail_triple_command_prefixed_help_text_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "CommandID": "CMD_13KEBABUPPERSNAKETRIPLEHELP",
                "actionName": "deploy_kebab_upper_snake_triple_help",
                "command-HELP_TEXT": "deploy through kebab+upper+snake-tail triple command help",
                "commandStatus": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["--config", str(mock_config), "cliq", "app-commands", "AP_13"],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commands"][0]["commandId"] == "CMD_13KEBABUPPERSNAKETRIPLEHELP"
    assert payload["commands"][0]["name"] == "deploy_kebab_upper_snake_triple_help"
    assert (
        payload["commands"][0]["description"]
        == "deploy through kebab+upper+snake-tail triple command help"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_kebab_camel_title_command_prefixed_helptext_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "CommandID": "CMD_13KEBABCAMELTITLEHELP",
                "actionName": "deploy_kebab_camel_title_help",
                "command-Helptext": "deploy through kebab+camel-title command help",
                "commandStatus": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["--config", str(mock_config), "cliq", "app-commands", "AP_13"],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commands"][0]["commandId"] == "CMD_13KEBABCAMELTITLEHELP"
    assert payload["commands"][0]["name"] == "deploy_kebab_camel_title_help"
    assert (
        payload["commands"][0]["description"]
        == "deploy through kebab+camel-title command help"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_kebab_snake_tail_command_prefixed_help_text_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "CommandID": "CMD_13KEBABSNAKETAILHELP",
                "actionName": "deploy_kebab_snake_tail_help",
                "command-help_text": "deploy through kebab+snake-tail command help",
                "commandStatus": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["--config", str(mock_config), "cliq", "app-commands", "AP_13"],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commands"][0]["commandId"] == "CMD_13KEBABSNAKETAILHELP"
    assert payload["commands"][0]["name"] == "deploy_kebab_snake_tail_help"
    assert (
        payload["commands"][0]["description"]
        == "deploy through kebab+snake-tail command help"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_uppercase_kebab_command_prefixed_helptext_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "COMMANDID": "CMD_13UPPERKEBABHELPTEXT",
                "ACTIONNAME": "deploy_upper_kebab_helptext",
                "COMMAND-HELPTEXT": "deploy through uppercase-kebab command helptext",
                "ACTION-HELPTEXT": "deploy through uppercase-kebab action helptext",
                "COMMANDSTATUS": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["--config", str(mock_config), "cliq", "app-commands", "AP_13"],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commands"][0]["commandId"] == "CMD_13UPPERKEBABHELPTEXT"
    assert payload["commands"][0]["name"] == "deploy_upper_kebab_helptext"
    assert (
        payload["commands"][0]["description"]
        == "deploy through uppercase-kebab command helptext"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_uppercase_snake_command_prefixed_helptext_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "COMMANDID": "CMD_13UPPERSNAKEHELPTEXT",
                "ACTIONNAME": "deploy_upper_snake_helptext",
                "COMMAND_HELPTEXT": "deploy through uppercase-snake command helptext",
                "ACTION_HELPTEXT": "deploy through uppercase-snake action helptext",
                "COMMANDSTATUS": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["--config", str(mock_config), "cliq", "app-commands", "AP_13"],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commands"][0]["commandId"] == "CMD_13UPPERSNAKEHELPTEXT"
    assert payload["commands"][0]["name"] == "deploy_upper_snake_helptext"
    assert (
        payload["commands"][0]["description"]
        == "deploy through uppercase-snake command helptext"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_snake_upper_tail_command_prefixed_helptext_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "CommandID": "CMD_13SNAKEUPPERTAILHELPTEXT",
                "actionName": "deploy_snake_upper_tail_helptext",
                "command_HELPTEXT": "deploy through snake+upper-tail command helptext",
                "commandStatus": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["--config", str(mock_config), "cliq", "app-commands", "AP_13"],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commands"][0]["commandId"] == "CMD_13SNAKEUPPERTAILHELPTEXT"
    assert payload["commands"][0]["name"] == "deploy_snake_upper_tail_helptext"
    assert (
        payload["commands"][0]["description"]
        == "deploy through snake+upper-tail command helptext"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_pascal_snake_upper_tail_command_prefixed_helptext_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "CommandID": "CMD_13PASCALSNAKEUPPERTAILHELPTEXT",
                "actionName": "deploy_pascal_snake_upper_tail_helptext",
                "Command_HELPTEXT": "deploy through Pascal+snake upper-tail command helptext",
                "commandStatus": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["--config", str(mock_config), "cliq", "app-commands", "AP_13"],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commands"][0]["commandId"] == "CMD_13PASCALSNAKEUPPERTAILHELPTEXT"
    assert payload["commands"][0]["name"] == "deploy_pascal_snake_upper_tail_helptext"
    assert (
        payload["commands"][0]["description"]
        == "deploy through Pascal+snake upper-tail command helptext"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_pascal_kebab_command_prefixed_help_text_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "CommandID": "CMD_13PASCALKEBABHELP",
                "actionName": "deploy_pascal_kebab_help",
                "Command-HelpText": "deploy through Pascal-kebab command help text",
                "commandStatus": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["--config", str(mock_config), "cliq", "app-commands", "AP_13"],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commands"][0]["commandId"] == "CMD_13PASCALKEBABHELP"
    assert payload["commands"][0]["name"] == "deploy_pascal_kebab_help"
    assert (
        payload["commands"][0]["description"]
        == "deploy through Pascal-kebab command help text"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_uppercase_command_prefixed_help_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "COMMANDID": "CMD_13UPPERHELP",
                "ACTIONNAME": "deploy_upper_help",
                "COMMANDHELP": "deploy through uppercase command help",
                "ACTIONHELP": "deploy through uppercase action help",
                "COMMANDSTATUS": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["--config", str(mock_config), "cliq", "app-commands", "AP_13"],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commands"][0]["commandId"] == "CMD_13UPPERHELP"
    assert payload["commands"][0]["name"] == "deploy_upper_help"
    assert (
        payload["commands"][0]["description"] == "deploy through uppercase command help"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_uppercase_snake_command_prefixed_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": [
            {
                "COMMAND_ID": "CMD_13UPPERSNAKE",
                "ACTION_NAME": "deploy_upper_snake_alias",
                "COMMAND_DESCRIPTION": "deploy through uppercase snake description",
                "COMMAND_STATUS": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["--config", str(mock_config), "cliq", "app-commands", "AP_13"],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commands"][0]["commandId"] == "CMD_13UPPERSNAKE"
    assert payload["commands"][0]["name"] == "deploy_upper_snake_alias"
    assert (
        payload["commands"][0]["description"]
        == "deploy through uppercase snake description"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_help_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {
                    "ActionID": "CMD_13HELPALIAS",
                    "Help": "dispatch help alias",
                    "Mode": "enabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_13"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["commands"][0]["commandId"] == "CMD_13HELPALIAS"
    assert payload["commands"][0]["description"] == "dispatch help alias"
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_helptext_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {
                    "ActionID": "CMD_13HELPTEXTALIAS",
                    "helptext": "dispatch helptext alias",
                    "Mode": "enabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_13"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["commands"][0]["commandId"] == "CMD_13HELPTEXTALIAS"
    assert payload["commands"][0]["description"] == "dispatch helptext alias"
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_command_name_pascal_case_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "data": {
            "commands": [
                {
                    "commandId": "CMD_8PASCALNAME",
                    "CommandName": "deploy_from_command_name_pascal_alias",
                    "summary": "deploy via command-name pascal alias",
                    "state": "enabled",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_8"
    assert payload["commands"][0]["commandId"] == "CMD_8PASCALNAME"
    assert payload["commands"][0]["name"] == "deploy_from_command_name_pascal_alias"
    assert (
        payload["commands"][0]["description"] == "deploy via command-name pascal alias"
    )
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_pascal_case_command_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {
                    "Command": {
                        "CommandID": "CMD_17PASCALWRAP",
                        "CommandName": "deploy_from_pascal_command_wrapper",
                        "Summary": "Deploy from PascalCase wrapper",
                        "Status": "enabled",
                    }
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_17"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert len(payload["commands"]) == 1
    assert payload["commands"][0]["commandId"] == "CMD_17PASCALWRAP"
    assert payload["commands"][0]["name"] == "deploy_from_pascal_command_wrapper"
    assert payload["commands"][0]["description"] == "Deploy from PascalCase wrapper"
    assert payload["commands"][0]["status"] == "enabled"


def test_cliq_app_commands_accepts_top_level_command_name_camel_case_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "commandName": "deploy_top_level_camel_alias",
        "summary": "Deploy from top-level camelCase alias.",
        "commandId": "CMD_8TOPCAMEL",
        "status": "enabled",
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8TOPCAMEL"
    assert payload["commands"][0]["name"] == "deploy_top_level_camel_alias"


def test_cliq_app_commands_accepts_response_command_name_camel_case_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "response": {
            "commandName": "deploy_response_camel_alias",
            "description": "Deploy from response camelCase alias.",
            "commandId": "CMD_8RESPCAMEL",
            "status": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8RESPCAMEL"
    assert payload["commands"][0]["name"] == "deploy_response_camel_alias"


def test_cliq_app_commands_prefers_command_rows_over_metadata_in_data_list(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {
                    "meta": {"cursor": "CURSOR_APP_COMMANDS"},
                    "status": "ok",
                },
                {
                    "command": {
                        "command_id": "CMD_8METAFIRST",
                        "name": "deploy_from_command_row",
                        "description": "use command row, not metadata",
                        "status": "enabled",
                    }
                },
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8METAFIRST"
    assert payload["commands"][0]["name"] == "deploy_from_command_row"


def test_cliq_app_commands_prefers_pascal_action_id_row_over_metadata_in_data_list(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {
                    "meta": {"cursor": "CURSOR_APP_COMMANDS"},
                    "status": "ok",
                },
                {"ActionID": "CMD_8ACTIONID"},
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8ACTIONID"
    assert payload["commands"][0]["name"] == ""


def test_cliq_app_commands_prefers_wrapped_action_row_over_wrapped_metadata_in_payload_data_list(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {"payload": {"meta": {"page": 1, "has_more": False}}},
                {
                    "payload": {
                        "action_id": "CMD_8WRAPPEDACTION",
                        "action_name": "deploy_wrapped_action",
                        "action_description": "use wrapped action row, not wrapped metadata",
                        "action_status": "enabled",
                    }
                },
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8WRAPPEDACTION"
    assert payload["commands"][0]["name"] == "deploy_wrapped_action"
    assert (
        payload["commands"][0]["description"]
        == "use wrapped action row, not wrapped metadata"
    )


def test_cliq_app_commands_prefers_helptext_row_over_metadata_in_data_list(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {"meta": {"page": 1, "has_more": False}},
                {"helptext": "Run remediation workflow"},
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["description"] == "Run remediation workflow"


def test_cliq_app_commands_prefers_command_prefixed_help_row_over_metadata_in_data_list(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {
                    "meta": {"cursor": "CURSOR_APP_COMMANDS"},
                    "status": "ok",
                },
                {
                    "meta": {"source": "maintenance"},
                    "CommandHelpText": "Run remediation workflow via command help",
                },
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert (
        payload["commands"][0]["description"]
        == "Run remediation workflow via command help"
    )


def test_cliq_app_commands_skips_empty_data_list_and_uses_commands_list(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [],
            "commands": [
                {
                    "command": {
                        "command_id": "CMD_8FALLBACKLIST",
                        "name": "deploy_from_commands_list",
                        "description": "fallback to commands list when data is empty",
                        "status": "enabled",
                    }
                }
            ],
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8FALLBACKLIST"
    assert payload["commands"][0]["name"] == "deploy_from_commands_list"


def test_cliq_app_commands_skips_metadata_only_data_list_and_uses_commands_list(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {
                    "meta": {"cursor": "CURSOR_APP_COMMANDS"},
                    "status": "ok",
                }
            ],
            "commands": [
                {
                    "command": {
                        "command_id": "CMD_8FALLBACKMETA",
                        "name": "deploy_from_commands_after_metadata",
                        "description": "fallback when data is metadata-only",
                        "status": "enabled",
                    }
                }
            ],
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8FALLBACKMETA"
    assert payload["commands"][0]["name"] == "deploy_from_commands_after_metadata"


def test_cliq_app_commands_prefers_action_hint_row_with_meta_over_metadata_only_data_list(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "payload": {
            "data": [
                {
                    "meta": {"cursor": "CURSOR_APP_COMMANDS"},
                    "status": "ok",
                }
            ],
            "commands": [
                {
                    "meta": {"source": "command_alias_row"},
                    "action": "deploy_from_action_alias_with_meta",
                    "action_help": "fallback when command row is metadata-tagged",
                }
            ],
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["name"] == "deploy_from_action_alias_with_meta"
    assert (
        payload["commands"][0]["description"]
        == "fallback when command row is metadata-tagged"
    )


def test_cliq_app_commands_accepts_display_name_camel_case_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "response": {
            "data": {
                "commands": [
                    {
                        "command_id": "CMD_8DISPLAY",
                        "displayName": "incident_resolved_display_alias",
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8DISPLAY"
    assert payload["commands"][0]["name"] == "incident_resolved_display_alias"


def test_cliq_app_commands_accepts_flat_lower_command_display_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "response": {
            "data": {
                "commands": [
                    {
                        "commandid": "CMD_8DISPLAYLOWER",
                        "commanddisplayname": "incident_resolved_command_display_alias",
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8DISPLAYLOWER"
    assert payload["commands"][0]["name"] == "incident_resolved_command_display_alias"


def test_cliq_app_commands_accepts_mixed_case_command_display_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "response": {
            "data": {
                "commands": [
                    {
                        "commandid": "CMD_8DISPLAYMIXED",
                        "commanddisplayName": "incident_resolved_command_display_mixed_alias",
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8DISPLAYMIXED"
    assert (
        payload["commands"][0]["name"]
        == "incident_resolved_command_display_mixed_alias"
    )


def test_cliq_app_commands_accepts_camel_title_command_displayname_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "response": {
            "data": {
                "commands": [
                    {
                        "commandid": "CMD_8DISPLAYCAMELTITLE",
                        "commandDisplayname": "incident_resolved_command_display_camel_title_alias",
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8DISPLAYCAMELTITLE"
    assert (
        payload["commands"][0]["name"]
        == "incident_resolved_command_display_camel_title_alias"
    )


def test_cliq_app_commands_accepts_snake_command_displayname_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "response": {
            "data": {
                "commands": [
                    {
                        "commandid": "CMD_8DISPLAYSNAKE",
                        "command_displayname": "incident_resolved_command_display_snake_alias",
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8DISPLAYSNAKE"
    assert (
        payload["commands"][0]["name"]
        == "incident_resolved_command_display_snake_alias"
    )


def test_cliq_app_commands_accepts_snake_camel_command_display_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "response": {
            "data": {
                "commands": [
                    {
                        "commandid": "CMD_8DISPLAYSNAKECAMEL",
                        "command_displayName": "incident_resolved_command_display_snake_camel_alias",
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8DISPLAYSNAKECAMEL"
    assert (
        payload["commands"][0]["name"]
        == "incident_resolved_command_display_snake_camel_alias"
    )


def test_cliq_app_commands_accepts_snake_pascal_command_display_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "response": {
            "data": {
                "commands": [
                    {
                        "commandid": "CMD_8DISPLAYSNAKEPASCAL",
                        "command_DisplayName": "incident_resolved_command_display_snake_pascal_alias",
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8DISPLAYSNAKEPASCAL"
    assert (
        payload["commands"][0]["name"]
        == "incident_resolved_command_display_snake_pascal_alias"
    )


def test_cliq_app_commands_accepts_pascal_snake_command_display_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "response": {
            "data": {
                "commands": [
                    {
                        "commandid": "CMD_8DISPLAYPASCALSNAKE",
                        "Command_DisplayName": "incident_resolved_command_display_pascal_snake_alias",
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8DISPLAYPASCALSNAKE"
    assert (
        payload["commands"][0]["name"]
        == "incident_resolved_command_display_pascal_snake_alias"
    )


def test_cliq_app_commands_accepts_pascal_snake_camel_title_command_display_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "response": {
            "data": {
                "commands": [
                    {
                        "commandid": "CMD_8DISPLAYPASCALSNAKECAMELTITLE",
                        "Command_Displayname": "incident_resolved_command_display_pascal_snake_camel_title_alias",
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8DISPLAYPASCALSNAKECAMELTITLE"
    assert (
        payload["commands"][0]["name"]
        == "incident_resolved_command_display_pascal_snake_camel_title_alias"
    )


def test_cliq_app_commands_accepts_pascal_snake_triple_command_display_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "response": {
            "data": {
                "commands": [
                    {
                        "commandid": "CMD_8DISPLAYPASCALSNAKETRIPLE",
                        "Command_Display_Name": "incident_resolved_command_display_pascal_snake_triple_alias",
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8DISPLAYPASCALSNAKETRIPLE"
    assert (
        payload["commands"][0]["name"]
        == "incident_resolved_command_display_pascal_snake_triple_alias"
    )


def test_cliq_app_commands_accepts_camel_snake_command_display_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "response": {
            "data": {
                "commands": [
                    {
                        "commandid": "CMD_8DISPLAYCAMELSNAKE",
                        "commandDisplay_name": "incident_resolved_command_display_camel_snake_alias",
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8DISPLAYCAMELSNAKE"
    assert (
        payload["commands"][0]["name"]
        == "incident_resolved_command_display_camel_snake_alias"
    )


def test_cliq_app_commands_accepts_kebab_command_display_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "response": {
            "data": {
                "commands": [
                    {
                        "commandid": "CMD_8DISPLAYKEBAB",
                        "command-display-name": "incident_resolved_command_display_kebab_alias",
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8DISPLAYKEBAB"
    assert (
        payload["commands"][0]["name"]
        == "incident_resolved_command_display_kebab_alias"
    )


def test_cliq_app_commands_accepts_kebab_command_displayname_camel_tail_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "response": {
            "data": {
                "commands": [
                    {
                        "commandid": "CMD_8DISPLAYKEBABNAMEMIXED",
                        "command-displayName": "incident_resolved_command_display_kebab_name_mixed_alias",
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8DISPLAYKEBABNAMEMIXED"
    assert (
        payload["commands"][0]["name"]
        == "incident_resolved_command_display_kebab_name_mixed_alias"
    )


def test_cliq_app_commands_accepts_kebab_pascal_tail_command_display_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "response": {
            "data": {
                "commands": [
                    {
                        "commandid": "CMD_8DISPLAYKEBABPASCALTAIL",
                        "command-Display-Name": "incident_resolved_command_display_kebab_pascal_tail_alias",
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8DISPLAYKEBABPASCALTAIL"
    assert (
        payload["commands"][0]["name"]
        == "incident_resolved_command_display_kebab_pascal_tail_alias"
    )


def test_cliq_app_commands_accepts_pascal_kebab_command_display_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "response": {
            "data": {
                "commands": [
                    {
                        "CommandID": "CMD_8DISPLAYPASCALKEBAB",
                        "Command-Display-Name": "incident_resolved_command_display_pascal_kebab_alias",
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8DISPLAYPASCALKEBAB"
    assert (
        payload["commands"][0]["name"]
        == "incident_resolved_command_display_pascal_kebab_alias"
    )


def test_cliq_app_commands_accepts_pascal_kebab_command_displayname_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "response": {
            "data": {
                "commands": [
                    {
                        "CommandID": "CMD_8DISPLAYPASCALKEBABNAME",
                        "Command-DisplayName": "incident_resolved_command_display_pascal_kebab_name_alias",
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8DISPLAYPASCALKEBABNAME"
    assert (
        payload["commands"][0]["name"]
        == "incident_resolved_command_display_pascal_kebab_name_alias"
    )


def test_cliq_app_commands_accepts_uppercase_kebab_command_display_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "response": {
            "data": {
                "commands": [
                    {
                        "COMMANDID": "CMD_8DISPLAYUPPERKEBAB",
                        "COMMAND-DISPLAY-NAME": "incident_resolved_command_display_upper_kebab_alias",
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8DISPLAYUPPERKEBAB"
    assert (
        payload["commands"][0]["name"]
        == "incident_resolved_command_display_upper_kebab_alias"
    )


def test_cliq_app_commands_accepts_uppercase_kebab_command_displayname_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "response": {
            "data": {
                "commands": [
                    {
                        "COMMANDID": "CMD_8DISPLAYUPPERKEBABNAME",
                        "COMMAND-DISPLAYNAME": "incident_resolved_command_display_upper_kebab_name_alias",
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8DISPLAYUPPERKEBABNAME"
    assert (
        payload["commands"][0]["name"]
        == "incident_resolved_command_display_upper_kebab_name_alias"
    )


def test_cliq_app_commands_accepts_uppercase_snake_command_displayname_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "response": {
            "data": {
                "commands": [
                    {
                        "COMMANDID": "CMD_8DISPLAYUPPERSNAKE",
                        "COMMAND_DISPLAYNAME": "incident_resolved_command_display_upper_snake_alias",
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8DISPLAYUPPERSNAKE"
    assert (
        payload["commands"][0]["name"]
        == "incident_resolved_command_display_upper_snake_alias"
    )


def test_cliq_app_commands_accepts_uppercase_flat_command_display_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "response": {
            "data": {
                "commands": [
                    {
                        "COMMANDID": "CMD_8DISPLAYUPPERFLAT",
                        "COMMANDDISPLAY": "incident_resolved_command_display_upper_flat_alias",
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8DISPLAYUPPERFLAT"
    assert (
        payload["commands"][0]["name"]
        == "incident_resolved_command_display_upper_flat_alias"
    )


def test_cliq_app_commands_accepts_uppercase_snake_command_display_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "response": {
            "data": {
                "commands": [
                    {
                        "COMMANDID": "CMD_8DISPLAYUPPERSNAKESHORT",
                        "COMMAND_DISPLAY": "incident_resolved_command_display_upper_snake_short_alias",
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8DISPLAYUPPERSNAKESHORT"
    assert (
        payload["commands"][0]["name"]
        == "incident_resolved_command_display_upper_snake_short_alias"
    )


def test_cliq_app_commands_accepts_command_display_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "response": {
            "data": {
                "commands": [
                    {
                        "commandid": "CMD_8DISPLAYPLAIN",
                        "command_display": "incident_resolved_command_display_alias",
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8DISPLAYPLAIN"
    assert payload["commands"][0]["name"] == "incident_resolved_command_display_alias"


def test_cliq_app_commands_accepts_snake_pascal_command_display_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "response": {
            "data": {
                "commands": [
                    {
                        "commandid": "CMD_8DISPLAYSNAKEPASCALSHORT",
                        "command_Display": "incident_resolved_command_display_snake_pascal_short_alias",
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8DISPLAYSNAKEPASCALSHORT"
    assert (
        payload["commands"][0]["name"]
        == "incident_resolved_command_display_snake_pascal_short_alias"
    )


def test_cliq_app_commands_accepts_camel_command_display_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "response": {
            "data": {
                "commands": [
                    {
                        "commandid": "CMD_8DISPLAYCAMEL",
                        "commandDisplay": "incident_resolved_command_display_camel_alias",
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8DISPLAYCAMEL"
    assert (
        payload["commands"][0]["name"]
        == "incident_resolved_command_display_camel_alias"
    )


def test_cliq_app_commands_accepts_flat_lower_command_display_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.list_app_commands.return_value = {
        "response": {
            "data": {
                "commands": [
                    {
                        "commandid": "CMD_8DISPLAYFLAT",
                        "commanddisplay": "incident_resolved_command_display_flat_alias",
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-commands", "AP_8"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["commands"][0]["commandId"] == "CMD_8DISPLAYFLAT"
    assert (
        payload["commands"][0]["name"] == "incident_resolved_command_display_flat_alias"
    )


def test_cliq_app_command_get(mock_config: Path, mock_token_refresh: Any) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "command_id": "CMD_10",
            "name": "deploy",
            "description": "Trigger deployment",
            "status": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_7", "CMD_10"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_7"
    assert payload["command"]["commandId"] == "CMD_10"
    assert payload["command"]["name"] == "deploy"
    assert payload["command"]["description"] == "Trigger deployment"
    assert payload["command"]["status"] == "enabled"
    mock_client.get_app_command.assert_called_once_with("AP_7", "CMD_10")


def test_cliq_app_command_get_accepts_nested_commands_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "commands": [
                {
                    "id": "CMD_11",
                    "title": "triage",
                    "helpText": "Open triage workflow",
                    "state": "active",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_8", "CMD_11"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_8"
    assert payload["command"]["commandId"] == "CMD_11"
    assert payload["command"]["name"] == "triage"
    assert payload["command"]["description"] == "Open triage workflow"
    assert payload["command"]["status"] == "active"
    mock_client.get_app_command.assert_called_once_with("AP_8", "CMD_11")


def test_cliq_app_command_get_accepts_data_list_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": [
            {
                "id": "CMD_12",
                "command": "notify_oncall",
                "summary": "Notify the on-call engineer",
                "mode": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_9", "CMD_12"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_9"
    assert payload["command"]["commandId"] == "CMD_12"
    assert payload["command"]["name"] == "notify_oncall"
    assert payload["command"]["description"] == "Notify the on-call engineer"
    assert payload["command"]["status"] == "enabled"
    mock_client.get_app_command.assert_called_once_with("AP_9", "CMD_12")


def test_cliq_app_command_get_accepts_data_list_wrapped_commands_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": [
            {
                "commands": {
                    "commandId": "CMD_14",
                    "name": "incident_ack",
                    "summary": "Acknowledge incident",
                    "mode": "active",
                }
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_11", "CMD_14"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_11"
    assert payload["command"]["commandId"] == "CMD_14"
    assert payload["command"]["name"] == "incident_ack"
    assert payload["command"]["description"] == "Acknowledge incident"
    assert payload["command"]["status"] == "active"
    mock_client.get_app_command.assert_called_once_with("AP_11", "CMD_14")


def test_cliq_app_command_get_accepts_data_records_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "records": [
                {
                    "id": "CMD_14R",
                    "name": "incident_ack",
                    "summary": "Acknowledge incident",
                    "mode": "active",
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_11", "CMD_14R"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_11"
    assert payload["command"]["commandId"] == "CMD_14R"
    assert payload["command"]["name"] == "incident_ack"
    assert payload["command"]["description"] == "Acknowledge incident"
    assert payload["command"]["status"] == "active"
    mock_client.get_app_command.assert_called_once_with("AP_11", "CMD_14R")


def test_cliq_app_command_get_accepts_data_records_record_row_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "records": [
                {
                    "record": {
                        "commandId": "CMD_14RR",
                        "name": "incident_ack_v2",
                        "summary": "Acknowledge incident v2",
                        "mode": "enabled",
                    }
                }
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_11", "CMD_14RR"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_11"
    assert payload["command"]["commandId"] == "CMD_14RR"
    assert payload["command"]["name"] == "incident_ack_v2"
    assert payload["command"]["description"] == "Acknowledge incident v2"
    assert payload["command"]["status"] == "enabled"
    mock_client.get_app_command.assert_called_once_with("AP_11", "CMD_14RR")


def test_cliq_app_command_get_accepts_top_level_commands_dict_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "commands": {
            "commandId": "CMD_13",
            "name": "daily_digest",
            "summary": "Send a daily digest",
            "state": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_10", "CMD_13"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_10"
    assert payload["command"]["commandId"] == "CMD_13"
    assert payload["command"]["name"] == "daily_digest"
    assert payload["command"]["description"] == "Send a daily digest"
    assert payload["command"]["status"] == "enabled"
    mock_client.get_app_command.assert_called_once_with("AP_10", "CMD_13")


def test_cliq_app_command_get_accepts_top_level_command_wrapper_list_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "command": [
            {
                "commandId": "CMD_15",
                "name": "incident_close",
                "summary": "Close active incident",
                "mode": "enabled",
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_12", "CMD_15"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_12"
    assert payload["command"]["commandId"] == "CMD_15"
    assert payload["command"]["name"] == "incident_close"
    assert payload["command"]["description"] == "Close active incident"
    assert payload["command"]["status"] == "enabled"
    mock_client.get_app_command.assert_called_once_with("AP_12", "CMD_15")


def test_cliq_app_command_get_accepts_top_level_command_wrapper_list_row_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "command": [
            {
                "command": {
                    "commandId": "CMD_16",
                    "name": "incident_escalate",
                    "summary": "Escalate incident",
                    "mode": "enabled",
                }
            }
        ]
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_13", "CMD_16"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["command"]["commandId"] == "CMD_16"
    assert payload["command"]["name"] == "incident_escalate"
    assert payload["command"]["description"] == "Escalate incident"
    assert payload["command"]["status"] == "enabled"
    mock_client.get_app_command.assert_called_once_with("AP_13", "CMD_16")


def test_cliq_app_command_get_accepts_nested_action_wrapper_dict_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "action": {
                "commandId": "CMD_16",
                "action": "sync_status",
                "summary": "Sync incident status",
                "mode": "enabled",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_13", "CMD_16"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["command"]["commandId"] == "CMD_16"
    assert payload["command"]["name"] == "sync_status"
    assert payload["command"]["description"] == "Sync incident status"
    assert payload["command"]["status"] == "enabled"
    mock_client.get_app_command.assert_called_once_with("AP_13", "CMD_16")


def test_cliq_app_command_get_accepts_uppercase_action_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "ACTION": {
            "ACTIONID": "CMD_16UP",
            "ACTION": "sync_status_upper",
            "SUMMARY": "Sync incident status via uppercase wrapper",
            "MODE": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_13", "CMD_16UP"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["command"]["commandId"] == "CMD_16UP"
    assert payload["command"]["name"] == "sync_status_upper"
    assert (
        payload["command"]["description"]
        == "Sync incident status via uppercase wrapper"
    )
    assert payload["command"]["status"] == "enabled"
    mock_client.get_app_command.assert_called_once_with("AP_13", "CMD_16UP")


def test_cliq_app_command_get_accepts_top_level_result_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "result": {
            "data": {
                "records": {
                    "record": [
                        {
                            "item": {
                                "command": {
                                    "commandId": "CMD_16RW",
                                    "name": "sync_status_wrapped",
                                    "summary": "Sync incident status wrapped",
                                    "mode": "enabled",
                                }
                            }
                        }
                    ]
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_13", "CMD_16RW"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["command"]["commandId"] == "CMD_16RW"
    assert payload["command"]["name"] == "sync_status_wrapped"
    assert payload["command"]["description"] == "Sync incident status wrapped"
    assert payload["command"]["status"] == "enabled"
    mock_client.get_app_command.assert_called_once_with("AP_13", "CMD_16RW")


def test_cliq_app_command_get_accepts_top_level_payload_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "response": {
                "data": {
                    "records": {
                        "record": [
                            {
                                "item": {
                                    "command": {
                                        "commandId": "CMD_16PW",
                                        "name": "sync_status_payload",
                                        "summary": "Sync incident status payload wrapped",
                                        "mode": "enabled",
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_13", "CMD_16PW"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["command"]["commandId"] == "CMD_16PW"
    assert payload["command"]["name"] == "sync_status_payload"
    assert payload["command"]["description"] == "Sync incident status payload wrapped"
    assert payload["command"]["status"] == "enabled"
    mock_client.get_app_command.assert_called_once_with("AP_13", "CMD_16PW")


def test_cliq_app_command_get_prefers_command_row_over_metadata_in_data_list(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": [
                {"meta": {"page": 1, "has_more": False}},
                {
                    "command": {
                        "commandId": "CMD_16ML",
                        "name": "incident_sync",
                        "summary": "Sync incident metadata",
                        "mode": "enabled",
                    }
                },
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_13", "CMD_16ML"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["command"]["commandId"] == "CMD_16ML"
    assert payload["command"]["name"] == "incident_sync"
    assert payload["command"]["description"] == "Sync incident metadata"
    assert payload["command"]["status"] == "enabled"
    mock_client.get_app_command.assert_called_once_with("AP_13", "CMD_16ML")


def test_cliq_app_command_get_prefers_helptext_row_over_metadata_in_data_list(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": [
                {"meta": {"page": 1, "has_more": False}},
                {"helptext": "Run remediation workflow"},
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_13", "CMD_16HT"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"]["description"] == "Run remediation workflow"
    mock_client.get_app_command.assert_called_once_with("AP_13", "CMD_16HT")


def test_cliq_app_command_get_prefers_command_prefixed_help_row_over_metadata_in_data_list(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": [
                {"meta": {"page": 1, "has_more": False}},
                {"CommandHelpText": "Rotate on-call token"},
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_13", "CMD_16CHT"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"]["description"] == "Rotate on-call token"
    mock_client.get_app_command.assert_called_once_with("AP_13", "CMD_16CHT")


def test_cliq_app_command_get_prefers_pascal_action_id_row_over_metadata_in_data_list(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": [
                {"meta": {"page": 1, "has_more": False}},
                {"ActionID": "CMD_16ACTIONID"},
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_13", "CMD_16ACTIONID"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["command"]["commandId"] == "CMD_16ACTIONID"
    assert payload["command"]["name"] == ""
    mock_client.get_app_command.assert_called_once_with("AP_13", "CMD_16ACTIONID")


def test_cliq_app_command_get_prefers_action_id_row_over_metadata_in_nested_payload_data_list(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": [
                {"meta": {"page": 1, "has_more": False}},
                {
                    "action_id": "CMD_16SNAKEACTION",
                    "action_name": "incident_replay",
                    "action_description": "Replay incident timeline",
                    "action_status": "enabled",
                },
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_13", "CMD_16SNAKEACTION"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["command"]["commandId"] == "CMD_16SNAKEACTION"
    assert payload["command"]["name"] == "incident_replay"
    assert payload["command"]["description"] == "Replay incident timeline"
    assert payload["command"]["status"] == "enabled"
    mock_client.get_app_command.assert_called_once_with("AP_13", "CMD_16SNAKEACTION")


def test_cliq_app_command_get_prefers_wrapped_action_row_over_wrapped_metadata_in_payload_data_list(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": [
                {"payload": {"meta": {"page": 1, "has_more": False}}},
                {
                    "payload": {
                        "action_id": "CMD_16WRAPPED",
                        "action_name": "incident_wrap",
                        "action_description": "Wrapped action row",
                        "action_status": "enabled",
                    }
                },
            ]
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_13", "CMD_16WRAPPED"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["command"]["commandId"] == "CMD_16WRAPPED"
    assert payload["command"]["name"] == "incident_wrap"
    assert payload["command"]["description"] == "Wrapped action row"
    assert payload["command"]["status"] == "enabled"
    assert payload["command"]["raw"]["action_id"] == "CMD_16WRAPPED"
    mock_client.get_app_command.assert_called_once_with("AP_13", "CMD_16WRAPPED")


def test_cliq_app_command_get_accepts_data_records_record_item_nested_command_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "records": {
                "record": [
                    {
                        "item": {
                            "command": {
                                "command": {
                                    "commandId": "CMD_16RI",
                                    "name": "incident_escalate",
                                    "summary": "Escalate incident",
                                    "mode": "enabled",
                                }
                            }
                        }
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_13", "CMD_16RI"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_13"
    assert payload["command"]["commandId"] == "CMD_16RI"
    assert payload["command"]["name"] == "incident_escalate"
    assert payload["command"]["description"] == "Escalate incident"
    assert payload["command"]["status"] == "enabled"
    mock_client.get_app_command.assert_called_once_with("AP_13", "CMD_16RI")


def test_cliq_app_command_get_accepts_deep_data_records_record_item_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "records": {
                "record": [
                    {
                        "item": {
                            "record": {
                                "item": {
                                    "record": {
                                        "item": {
                                            "record": {
                                                "item": {
                                                    "command": {
                                                        "commandId": "CMD_17RR",
                                                        "name": "workflow_refresh",
                                                        "summary": "Refresh workflow",
                                                        "mode": "enabled",
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_14RR", "CMD_17RR"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_14RR"
    assert payload["command"]["commandId"] == "CMD_17RR"
    assert payload["command"]["name"] == "workflow_refresh"
    assert payload["command"]["description"] == "Refresh workflow"
    assert payload["command"]["status"] == "enabled"
    mock_client.get_app_command.assert_called_once_with("AP_14RR", "CMD_17RR")


def test_cliq_app_command_get_accepts_extra_deep_record_item_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()

    deep_row: dict[str, Any] = {
        "commandId": "CMD_17DEEP",
        "name": "incident_recover_deep",
        "summary": "Recover incident from deep wrapper chain",
        "mode": "enabled",
    }
    for _ in range(4):
        deep_row = {"record": {"item": deep_row}}

    mock_client.get_app_command.return_value = {
        "data": {
            "records": {
                "record": [
                    {
                        "item": deep_row,
                    }
                ]
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17DEEP", "CMD_17DEEP"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17DEEP"
    assert payload["command"]["commandId"] == "CMD_17DEEP"
    assert payload["command"]["name"] == "incident_recover_deep"
    assert (
        payload["command"]["description"] == "Recover incident from deep wrapper chain"
    )
    assert payload["command"]["status"] == "enabled"
    mock_client.get_app_command.assert_called_once_with("AP_17DEEP", "CMD_17DEEP")


def test_cliq_app_command_get_accepts_command_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "command": {
                "command_id": "CMD_17ALIAS",
                "command_name": "publish_release_alias",
                "summary": "Publish release from command_name",
                "mode": "enabled",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "CMD_17ALIAS"
    assert payload["command"]["name"] == "publish_release_alias"
    assert payload["command"]["description"] == "Publish release from command_name"
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_pascal_case_action_wrapper_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "Action": {
                    "ActionID": "ACT_17PASCALWRAP",
                    "ActionName": "deploy_from_pascal_action_wrapper",
                    "Summary": "Deploy from PascalCase action wrapper",
                    "Status": "enabled",
                }
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "ACT_17PASCALWRAP"
    assert payload["command"]["name"] == "deploy_from_pascal_action_wrapper"
    assert payload["command"]["description"] == "Deploy from PascalCase action wrapper"
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_payload_data_action_name_camel_case_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "actionName": "deploy_from_payload_data_camel_alias",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["name"] == "deploy_from_payload_data_camel_alias"


def test_cliq_app_command_get_accepts_payload_data_display_name_camel_case_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "command_id": "CMD_17DISPLAY",
                "displayName": "deploy_from_payload_data_display_alias",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "CMD_17DISPLAY"
    assert payload["command"]["name"] == "deploy_from_payload_data_display_alias"


def test_cliq_app_command_get_accepts_flat_lower_command_display_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "commandid": "CMD_17DISPLAYLOWER",
                "commanddisplayname": "deploy_from_payload_data_command_display_alias",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "CMD_17DISPLAYLOWER"
    assert (
        payload["command"]["name"] == "deploy_from_payload_data_command_display_alias"
    )


def test_cliq_app_command_get_accepts_snake_command_displayname_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "commandid": "CMD_17DISPLAYSNAKE",
                "command_displayname": "deploy_from_payload_data_command_display_snake_alias",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "CMD_17DISPLAYSNAKE"
    assert (
        payload["command"]["name"]
        == "deploy_from_payload_data_command_display_snake_alias"
    )


def test_cliq_app_command_get_accepts_mixed_case_action_display_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "actionid": "ACT_17DISPLAYMIXED",
                "actiondisplayName": "deploy_from_payload_data_action_display_mixed_alias",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "ACT_17DISPLAYMIXED"
    assert (
        payload["command"]["name"]
        == "deploy_from_payload_data_action_display_mixed_alias"
    )


def test_cliq_app_command_get_accepts_camel_title_action_displayname_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "actionid": "ACT_17DISPLAYCAMELTITLE",
                "actionDisplayname": "deploy_from_payload_data_action_display_camel_title_alias",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "ACT_17DISPLAYCAMELTITLE"
    assert (
        payload["command"]["name"]
        == "deploy_from_payload_data_action_display_camel_title_alias"
    )


def test_cliq_app_command_get_accepts_snake_camel_action_display_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "actionid": "ACT_17DISPLAYSNAKECAMEL",
                "action_displayName": "deploy_from_payload_data_action_display_snake_camel_alias",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "ACT_17DISPLAYSNAKECAMEL"
    assert (
        payload["command"]["name"]
        == "deploy_from_payload_data_action_display_snake_camel_alias"
    )


def test_cliq_app_command_get_accepts_snake_pascal_action_display_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "actionid": "ACT_17DISPLAYSNAKEPASCAL",
                "action_DisplayName": "deploy_from_payload_data_action_display_snake_pascal_alias",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "ACT_17DISPLAYSNAKEPASCAL"
    assert (
        payload["command"]["name"]
        == "deploy_from_payload_data_action_display_snake_pascal_alias"
    )


def test_cliq_app_command_get_accepts_pascal_snake_action_display_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "actionid": "ACT_17DISPLAYPASCALSNAKE",
                "Action_DisplayName": "deploy_from_payload_data_action_display_pascal_snake_alias",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "ACT_17DISPLAYPASCALSNAKE"
    assert (
        payload["command"]["name"]
        == "deploy_from_payload_data_action_display_pascal_snake_alias"
    )


def test_cliq_app_command_get_accepts_pascal_snake_camel_title_action_display_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "actionid": "ACT_17DISPLAYPASCALSNAKECAMELTITLE",
                "Action_Displayname": "deploy_from_payload_data_action_display_pascal_snake_camel_title_alias",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "ACT_17DISPLAYPASCALSNAKECAMELTITLE"
    assert (
        payload["command"]["name"]
        == "deploy_from_payload_data_action_display_pascal_snake_camel_title_alias"
    )


def test_cliq_app_command_get_accepts_pascal_snake_triple_action_display_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "actionid": "ACT_17DISPLAYPASCALSNAKETRIPLE",
                "Action_Display_Name": "deploy_from_payload_data_action_display_pascal_snake_triple_alias",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "ACT_17DISPLAYPASCALSNAKETRIPLE"
    assert (
        payload["command"]["name"]
        == "deploy_from_payload_data_action_display_pascal_snake_triple_alias"
    )


def test_cliq_app_command_get_accepts_camel_snake_action_display_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "actionid": "ACT_17DISPLAYCAMELSNAKE",
                "actionDisplay_name": "deploy_from_payload_data_action_display_camel_snake_alias",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "ACT_17DISPLAYCAMELSNAKE"
    assert (
        payload["command"]["name"]
        == "deploy_from_payload_data_action_display_camel_snake_alias"
    )


def test_cliq_app_command_get_accepts_kebab_action_display_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "actionid": "ACT_17DISPLAYKEBAB",
                "action-display-name": "deploy_from_payload_data_action_display_kebab_alias",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "ACT_17DISPLAYKEBAB"
    assert (
        payload["command"]["name"]
        == "deploy_from_payload_data_action_display_kebab_alias"
    )


def test_cliq_app_command_get_accepts_kebab_action_displayname_camel_tail_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "actionid": "ACT_17DISPLAYKEBABNAMEMIXED",
                "action-displayName": "deploy_from_payload_data_action_display_kebab_name_mixed_alias",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "ACT_17DISPLAYKEBABNAMEMIXED"
    assert (
        payload["command"]["name"]
        == "deploy_from_payload_data_action_display_kebab_name_mixed_alias"
    )


def test_cliq_app_command_get_accepts_kebab_pascal_tail_action_display_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "actionid": "ACT_17DISPLAYKEBABPASCALTAIL",
                "action-Display-Name": "deploy_from_payload_data_action_display_kebab_pascal_tail_alias",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "ACT_17DISPLAYKEBABPASCALTAIL"
    assert (
        payload["command"]["name"]
        == "deploy_from_payload_data_action_display_kebab_pascal_tail_alias"
    )


def test_cliq_app_command_get_accepts_pascal_kebab_action_display_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "ActionID": "ACT_17DISPLAYPASCALKEBAB",
                "Action-Display-Name": "deploy_from_payload_data_action_display_pascal_kebab_alias",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "ACT_17DISPLAYPASCALKEBAB"
    assert (
        payload["command"]["name"]
        == "deploy_from_payload_data_action_display_pascal_kebab_alias"
    )


def test_cliq_app_command_get_accepts_pascal_kebab_action_displayname_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "ActionID": "ACT_17DISPLAYPASCALKEBABNAME",
                "Action-DisplayName": "deploy_from_payload_data_action_display_pascal_kebab_name_alias",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "ACT_17DISPLAYPASCALKEBABNAME"
    assert (
        payload["command"]["name"]
        == "deploy_from_payload_data_action_display_pascal_kebab_name_alias"
    )


def test_cliq_app_command_get_accepts_uppercase_kebab_action_display_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "ACTIONID": "ACT_17DISPLAYUPPERKEBAB",
                "ACTION-DISPLAY-NAME": "deploy_from_payload_data_action_display_upper_kebab_alias",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "ACT_17DISPLAYUPPERKEBAB"
    assert (
        payload["command"]["name"]
        == "deploy_from_payload_data_action_display_upper_kebab_alias"
    )


def test_cliq_app_command_get_accepts_uppercase_kebab_action_displayname_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "ACTIONID": "ACT_17DISPLAYUPPERKEBABNAME",
                "ACTION-DISPLAYNAME": "deploy_from_payload_data_action_display_upper_kebab_name_alias",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "ACT_17DISPLAYUPPERKEBABNAME"
    assert (
        payload["command"]["name"]
        == "deploy_from_payload_data_action_display_upper_kebab_name_alias"
    )


def test_cliq_app_command_get_accepts_uppercase_snake_action_displayname_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "ACTIONID": "ACT_17DISPLAYUPPERSNAKE",
                "ACTION_DISPLAYNAME": "deploy_from_payload_data_action_display_upper_snake_alias",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "ACT_17DISPLAYUPPERSNAKE"
    assert (
        payload["command"]["name"]
        == "deploy_from_payload_data_action_display_upper_snake_alias"
    )


def test_cliq_app_command_get_accepts_uppercase_flat_action_display_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "ACTIONID": "ACT_17DISPLAYUPPERFLAT",
                "ACTIONDISPLAY": "deploy_from_payload_data_action_display_upper_flat_alias",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "ACT_17DISPLAYUPPERFLAT"
    assert (
        payload["command"]["name"]
        == "deploy_from_payload_data_action_display_upper_flat_alias"
    )


def test_cliq_app_command_get_accepts_uppercase_snake_action_display_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "ACTIONID": "ACT_17DISPLAYUPPERSNAKESHORT",
                "ACTION_DISPLAY": "deploy_from_payload_data_action_display_upper_snake_short_alias",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "ACT_17DISPLAYUPPERSNAKESHORT"
    assert (
        payload["command"]["name"]
        == "deploy_from_payload_data_action_display_upper_snake_short_alias"
    )


def test_cliq_app_command_get_accepts_action_display_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "actionid": "ACT_17DISPLAYPLAIN",
                "action_display": "deploy_from_payload_data_action_display_alias",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "ACT_17DISPLAYPLAIN"
    assert payload["command"]["name"] == "deploy_from_payload_data_action_display_alias"


def test_cliq_app_command_get_accepts_snake_pascal_action_display_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "actionid": "ACT_17DISPLAYSNAKEPASCALSHORT",
                "action_Display": "deploy_from_payload_data_action_display_snake_pascal_short_alias",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "ACT_17DISPLAYSNAKEPASCALSHORT"
    assert (
        payload["command"]["name"]
        == "deploy_from_payload_data_action_display_snake_pascal_short_alias"
    )


def test_cliq_app_command_get_accepts_camel_action_display_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "actionid": "ACT_17DISPLAYCAMEL",
                "actionDisplay": "deploy_from_payload_data_action_display_camel_alias",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "ACT_17DISPLAYCAMEL"
    assert (
        payload["command"]["name"]
        == "deploy_from_payload_data_action_display_camel_alias"
    )


def test_cliq_app_command_get_accepts_flat_lower_action_display_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "actionid": "ACT_17DISPLAYFLAT",
                "actiondisplay": "deploy_from_payload_data_action_display_flat_alias",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "ACT_17DISPLAYFLAT"
    assert (
        payload["command"]["name"]
        == "deploy_from_payload_data_action_display_flat_alias"
    )


def test_cliq_app_command_get_accepts_payload_data_action_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "action_name": "deploy_from_payload_data_alias",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["name"] == "deploy_from_payload_data_alias"


def test_cliq_app_command_get_accepts_action_id_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "actionId": "ACT_17ALIAS",
            "actionName": "deploy_from_action_id_alias",
            "summary": "dispatch alias",
            "state": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "ACT_17ALIAS"
    assert payload["command"]["name"] == "deploy_from_action_id_alias"
    assert payload["command"]["description"] == "dispatch alias"
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_action_id_pascal_case_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "ActionID": "ACT_17PASCAL",
            "actionName": "deploy_from_action_id_pascal_alias",
            "summary": "dispatch pascal alias",
            "state": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "ACT_17PASCAL"
    assert payload["command"]["name"] == "deploy_from_action_id_pascal_alias"
    assert payload["command"]["description"] == "dispatch pascal alias"
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_actionid_lowercase_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "actionid": "ACT_17LOWER",
            "actionName": "deploy_from_actionid_lowercase_alias",
            "summary": "dispatch lowercase actionid alias",
            "state": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "ACT_17LOWER"
    assert payload["command"]["name"] == "deploy_from_actionid_lowercase_alias"
    assert payload["command"]["description"] == "dispatch lowercase actionid alias"
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_commandid_lowercase_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "commandid": "CMD_17LOWERID",
            "actionName": "deploy_from_commandid_lowercase_alias",
            "summary": "dispatch lowercase commandid alias",
            "state": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "CMD_17LOWERID"
    assert payload["command"]["name"] == "deploy_from_commandid_lowercase_alias"
    assert payload["command"]["description"] == "dispatch lowercase commandid alias"
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_flat_lower_command_name_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "commandid": "CMD_17LOWERNAME",
            "commandname": "deploy_from_flat_lower_command_name_alias",
            "summary": "dispatch flat-lower command-name alias",
            "state": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "CMD_17LOWERNAME"
    assert payload["command"]["name"] == "deploy_from_flat_lower_command_name_alias"
    assert payload["command"]["description"] == "dispatch flat-lower command-name alias"
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_uppercase_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "ACTIONID": "ACT_17UPPER",
                "DISPLAYNAME": "deploy_from_uppercase_alias",
                "HELPTEXT": "dispatch uppercase aliases",
                "MODE": "enabled",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "ACT_17UPPER"
    assert payload["command"]["name"] == "deploy_from_uppercase_alias"
    assert payload["command"]["description"] == "dispatch uppercase aliases"
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_command_id_pascal_case_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "commandID": "CMD_17PASCALID",
                "actionName": "deploy_from_command_id_pascal_alias",
                "summary": "dispatch command id pascal alias",
                "state": "enabled",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "CMD_17PASCALID"
    assert payload["command"]["name"] == "deploy_from_command_id_pascal_alias"
    assert payload["command"]["description"] == "dispatch command id pascal alias"
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_pascal_case_description_and_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "commandID": "CMD_17PASCALDESC",
                "ActionName": "deploy_get_pascal_description_alias",
                "Description": "dispatch get pascal description alias",
                "Status": "enabled",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "CMD_17PASCALDESC"
    assert payload["command"]["name"] == "deploy_get_pascal_description_alias"
    assert payload["command"]["description"] == "dispatch get pascal description alias"
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_command_prefixed_description_and_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "commandID": "CMD_17PREFIXED",
                "actionName": "deploy_get_prefixed_alias",
                "commandDescription": "dispatch get prefixed alias",
                "commandStatus": "enabled",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "CMD_17PREFIXED"
    assert payload["command"]["name"] == "deploy_get_prefixed_alias"
    assert payload["command"]["description"] == "dispatch get prefixed alias"
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_flat_lower_command_prefixed_description_and_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "commandID": "CMD_17FLATLOWERPREFIXED",
                "actionName": "deploy_get_flat_lower_prefixed_alias",
                "commanddescription": "dispatch get flat lower prefixed alias",
                "commandstatus": "enabled",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "CMD_17FLATLOWERPREFIXED"
    assert payload["command"]["name"] == "deploy_get_flat_lower_prefixed_alias"
    assert payload["command"]["description"] == "dispatch get flat lower prefixed alias"
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_pascal_case_command_prefixed_description_and_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "commandID": "CMD_17PREFIXEDPASCAL",
                "actionName": "deploy_get_prefixed_pascal_alias",
                "CommandDescription": "dispatch get prefixed pascal alias",
                "CommandStatus": "enabled",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "CMD_17PREFIXEDPASCAL"
    assert payload["command"]["name"] == "deploy_get_prefixed_pascal_alias"
    assert payload["command"]["description"] == "dispatch get prefixed pascal alias"
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_action_mode_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "commandID": "CMD_17ACTIONMODEALIAS",
                "actionName": "deploy_get_action_mode_alias",
                "Description": "dispatch get action mode alias",
                "action_mode": "disabled",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "CMD_17ACTIONMODEALIAS"
    assert payload["command"]["name"] == "deploy_get_action_mode_alias"
    assert payload["command"]["description"] == "dispatch get action mode alias"
    assert payload["command"]["status"] == "disabled"


def test_cliq_app_command_get_accepts_kebab_action_mode_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "commandID": "CMD_17ACTIONKEBABMODEALIAS",
                "actionName": "deploy_get_action_kebab_mode_alias",
                "Description": "dispatch get action kebab mode alias",
                "action-mode": "enabled",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "CMD_17ACTIONKEBABMODEALIAS"
    assert payload["command"]["name"] == "deploy_get_action_kebab_mode_alias"
    assert payload["command"]["description"] == "dispatch get action kebab mode alias"
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_kebab_action_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "commandID": "CMD_17ACTIONKEBABSTATUSALIAS",
                "actionName": "deploy_get_action_kebab_status_alias",
                "Description": "dispatch get action kebab status alias",
                "action-status": "disabled",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "CMD_17ACTIONKEBABSTATUSALIAS"
    assert payload["command"]["name"] == "deploy_get_action_kebab_status_alias"
    assert payload["command"]["description"] == "dispatch get action kebab status alias"
    assert payload["command"]["status"] == "disabled"


def test_cliq_app_command_get_accepts_kebab_upper_tail_action_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "commandID": "CMD_17ACTIONKEBABUPPERSTATUSALIAS",
                "actionName": "deploy_get_action_kebab_upper_status_alias",
                "Description": "dispatch get action kebab+upper status alias",
                "action-STATUS": "enabled",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "CMD_17ACTIONKEBABUPPERSTATUSALIAS"
    assert payload["command"]["name"] == "deploy_get_action_kebab_upper_status_alias"
    assert (
        payload["command"]["description"]
        == "dispatch get action kebab+upper status alias"
    )
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_kebab_upper_tail_action_mode_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "commandID": "CMD_17ACTIONKEBABUPPERMODEALIAS",
                "actionName": "deploy_get_action_kebab_upper_mode_alias",
                "Description": "dispatch get action kebab+upper mode alias",
                "action-MODE": "disabled",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "CMD_17ACTIONKEBABUPPERMODEALIAS"
    assert payload["command"]["name"] == "deploy_get_action_kebab_upper_mode_alias"
    assert (
        payload["command"]["description"]
        == "dispatch get action kebab+upper mode alias"
    )
    assert payload["command"]["status"] == "disabled"


def test_cliq_app_command_get_accepts_snake_pascal_tail_action_mode_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "commandID": "CMD_17ACTIONSNAKEPASCALMODEALIAS",
                "actionName": "deploy_get_action_snake_pascal_mode_alias",
                "Description": "dispatch get action snake+Pascal mode alias",
                "action_Mode": "enabled",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "CMD_17ACTIONSNAKEPASCALMODEALIAS"
    assert payload["command"]["name"] == "deploy_get_action_snake_pascal_mode_alias"
    assert (
        payload["command"]["description"]
        == "dispatch get action snake+Pascal mode alias"
    )
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_snake_upper_tail_action_mode_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "commandID": "CMD_17ACTIONSNAKEUPPERMODEALIAS",
                "actionName": "deploy_get_action_snake_upper_mode_alias",
                "Description": "dispatch get action snake+upper mode alias",
                "action_MODE": "disabled",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "CMD_17ACTIONSNAKEUPPERMODEALIAS"
    assert payload["command"]["name"] == "deploy_get_action_snake_upper_mode_alias"
    assert (
        payload["command"]["description"]
        == "dispatch get action snake+upper mode alias"
    )
    assert payload["command"]["status"] == "disabled"


def test_cliq_app_command_get_accepts_snake_upper_tail_pascal_prefix_action_mode_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "commandID": "CMD_17ACTIONSNAKEUPPERPASCALMODEALIAS",
                "actionName": "deploy_get_action_snake_upper_pascal_mode_alias",
                "Description": "dispatch get action snake+upper Pascal mode alias",
                "Action_MODE": "enabled",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "CMD_17ACTIONSNAKEUPPERPASCALMODEALIAS"
    assert (
        payload["command"]["name"] == "deploy_get_action_snake_upper_pascal_mode_alias"
    )
    assert (
        payload["command"]["description"]
        == "dispatch get action snake+upper Pascal mode alias"
    )
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_snake_pascal_tail_action_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "commandID": "CMD_17ACTIONSNAKEPASCALSTATUSALIAS",
                "actionName": "deploy_get_action_snake_pascal_status_alias",
                "Description": "dispatch get action snake+Pascal status alias",
                "action_Status": "disabled",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "CMD_17ACTIONSNAKEPASCALSTATUSALIAS"
    assert payload["command"]["name"] == "deploy_get_action_snake_pascal_status_alias"
    assert (
        payload["command"]["description"]
        == "dispatch get action snake+Pascal status alias"
    )
    assert payload["command"]["status"] == "disabled"


def test_cliq_app_command_get_accepts_snake_upper_tail_action_status_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "commandID": "CMD_17ACTIONSNAKEUPPERSTATUSALIAS",
                "actionName": "deploy_get_action_snake_upper_status_alias",
                "Description": "dispatch get action snake+upper status alias",
                "action_STATUS": "enabled",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "CMD_17ACTIONSNAKEUPPERSTATUSALIAS"
    assert payload["command"]["name"] == "deploy_get_action_snake_upper_status_alias"
    assert (
        payload["command"]["description"]
        == "dispatch get action snake+upper status alias"
    )
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_command_prefixed_help_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "CommandID": "CMD_17PASCALHELP",
            "actionName": "detail_pascal_help",
            "CommandHelpText": "detail through command help text",
            "ActionHelp": "detail through action help",
            "commandStatus": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "cliq",
                "app-command-get",
                "AP_17",
                "CMD_17PASCALHELP",
            ],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"]["commandId"] == "CMD_17PASCALHELP"
    assert payload["command"]["name"] == "detail_pascal_help"
    assert payload["command"]["description"] == "detail through command help text"
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_flat_lower_command_prefixed_help_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "CommandID": "CMD_17LOWERHELP",
            "actionName": "detail_lower_help",
            "commandhelptext": "detail through lower command help text",
            "actionhelp": "detail through lower action help",
            "commandStatus": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "cliq",
                "app-command-get",
                "AP_17",
                "CMD_17LOWERHELP",
            ],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"]["commandId"] == "CMD_17LOWERHELP"
    assert payload["command"]["name"] == "detail_lower_help"
    assert payload["command"]["description"] == "detail through lower command help text"
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_kebab_action_prefixed_help_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "CommandID": "CMD_17KEBABHELP",
            "actionName": "detail_kebab_help",
            "action-help-text": "detail through kebab action help text",
            "commandStatus": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "cliq",
                "app-command-get",
                "AP_17",
                "CMD_17KEBABHELP",
            ],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"]["commandId"] == "CMD_17KEBABHELP"
    assert payload["command"]["name"] == "detail_kebab_help"
    assert payload["command"]["description"] == "detail through kebab action help text"
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_kebab_action_prefixed_helptext_camel_tail_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "CommandID": "CMD_17KEBABHELPMIXED",
            "actionName": "detail_kebab_help_mixed",
            "action-helpText": "detail through kebab action help mixed alias",
            "commandStatus": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "cliq",
                "app-command-get",
                "AP_17",
                "CMD_17KEBABHELPMIXED",
            ],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"]["commandId"] == "CMD_17KEBABHELPMIXED"
    assert payload["command"]["name"] == "detail_kebab_help_mixed"
    assert (
        payload["command"]["description"]
        == "detail through kebab action help mixed alias"
    )
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_snake_camel_tail_action_prefixed_helptext_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "CommandID": "CMD_17SNAKEHELPMIXED",
            "actionName": "detail_snake_help_mixed",
            "action_helpText": "detail through snake action help mixed alias",
            "commandStatus": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "cliq",
                "app-command-get",
                "AP_17",
                "CMD_17SNAKEHELPMIXED",
            ],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"]["commandId"] == "CMD_17SNAKEHELPMIXED"
    assert payload["command"]["name"] == "detail_snake_help_mixed"
    assert (
        payload["command"]["description"]
        == "detail through snake action help mixed alias"
    )
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_snake_pascal_tail_action_prefixed_helptext_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "CommandID": "CMD_17SNAKEPASCALTAILHELP",
            "actionName": "detail_snake_pascal_tail_help",
            "action_HelpText": "detail through snake+Pascal-tail action help",
            "commandStatus": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "cliq",
                "app-command-get",
                "AP_17",
                "CMD_17SNAKEPASCALTAILHELP",
            ],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"]["commandId"] == "CMD_17SNAKEPASCALTAILHELP"
    assert payload["command"]["name"] == "detail_snake_pascal_tail_help"
    assert (
        payload["command"]["description"]
        == "detail through snake+Pascal-tail action help"
    )
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_snake_pascal_camel_title_tail_action_prefixed_helptext_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "CommandID": "CMD_17SNAKEPASCALCAMELTITLETAILHELP",
            "actionName": "detail_snake_pascal_camel_title_tail_help",
            "action_Helptext": "detail through snake+Pascal-camel-title-tail action help",
            "commandStatus": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "cliq",
                "app-command-get",
                "AP_17",
                "CMD_17SNAKEPASCALCAMELTITLETAILHELP",
            ],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"]["commandId"] == "CMD_17SNAKEPASCALCAMELTITLETAILHELP"
    assert payload["command"]["name"] == "detail_snake_pascal_camel_title_tail_help"
    assert (
        payload["command"]["description"]
        == "detail through snake+Pascal-camel-title-tail action help"
    )
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_snake_pascal_triple_action_prefixed_help_text_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "CommandID": "CMD_17SNAKEPASCALTRIPLEHELP",
            "actionName": "detail_snake_pascal_triple_help",
            "action_Help_Text": "detail through snake+Pascal triple action help",
            "commandStatus": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "cliq",
                "app-command-get",
                "AP_17",
                "CMD_17SNAKEPASCALTRIPLEHELP",
            ],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"]["commandId"] == "CMD_17SNAKEPASCALTRIPLEHELP"
    assert payload["command"]["name"] == "detail_snake_pascal_triple_help"
    assert (
        payload["command"]["description"]
        == "detail through snake+Pascal triple action help"
    )
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_snake_upper_tail_triple_action_prefixed_help_text_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "CommandID": "CMD_17SNAKEUPPERTRIPLEHELP",
            "actionName": "detail_snake_upper_triple_help",
            "action_HELP_TEXT": "detail through snake+upper-tail triple action help",
            "commandStatus": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "cliq",
                "app-command-get",
                "AP_17",
                "CMD_17SNAKEUPPERTRIPLEHELP",
            ],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"]["commandId"] == "CMD_17SNAKEUPPERTRIPLEHELP"
    assert payload["command"]["name"] == "detail_snake_upper_triple_help"
    assert (
        payload["command"]["description"]
        == "detail through snake+upper-tail triple action help"
    )
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_pascal_snake_triple_action_prefixed_help_text_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "CommandID": "CMD_17PASCALSNAKETRIPLEHELP",
            "actionName": "detail_pascal_snake_triple_help",
            "Action_Help_Text": "detail through Pascal+snake triple action help",
            "commandStatus": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "cliq",
                "app-command-get",
                "AP_17",
                "CMD_17PASCALSNAKETRIPLEHELP",
            ],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"]["commandId"] == "CMD_17PASCALSNAKETRIPLEHELP"
    assert payload["command"]["name"] == "detail_pascal_snake_triple_help"
    assert (
        payload["command"]["description"]
        == "detail through Pascal+snake triple action help"
    )
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_pascal_snake_lower_tail_action_prefixed_help_text_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "CommandID": "CMD_17PASCALSNAKELOWERHELP",
            "actionName": "detail_pascal_snake_lower_help",
            "Action_help_text": "detail through Pascal+snake lower-tail action help",
            "commandStatus": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "cliq",
                "app-command-get",
                "AP_17",
                "CMD_17PASCALSNAKELOWERHELP",
            ],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"]["commandId"] == "CMD_17PASCALSNAKELOWERHELP"
    assert payload["command"]["name"] == "detail_pascal_snake_lower_help"
    assert (
        payload["command"]["description"]
        == "detail through Pascal+snake lower-tail action help"
    )
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_pascal_snake_kebab_pascal_tail_action_prefixed_help_text_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "CommandID": "CMD_17PASCALSNAKEKEBABPASCALHELP",
            "actionName": "detail_pascal_snake_kebab_pascal_help",
            "Action_help-Text": "detail through Pascal+snake+kebab Pascal-tail action help",
            "commandStatus": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "cliq",
                "app-command-get",
                "AP_17",
                "CMD_17PASCALSNAKEKEBABPASCALHELP",
            ],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"]["commandId"] == "CMD_17PASCALSNAKEKEBABPASCALHELP"
    assert payload["command"]["name"] == "detail_pascal_snake_kebab_pascal_help"
    assert (
        payload["command"]["description"]
        == "detail through Pascal+snake+kebab Pascal-tail action help"
    )
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_kebab_pascal_tail_action_prefixed_help_text_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "CommandID": "CMD_17KEBABPASCALTAILHELP",
            "actionName": "detail_kebab_pascal_tail_help",
            "action-Help-Text": "detail through kebab+Pascal-tail action help",
            "commandStatus": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "cliq",
                "app-command-get",
                "AP_17",
                "CMD_17KEBABPASCALTAILHELP",
            ],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"]["commandId"] == "CMD_17KEBABPASCALTAILHELP"
    assert payload["command"]["name"] == "detail_kebab_pascal_tail_help"
    assert (
        payload["command"]["description"]
        == "detail through kebab+Pascal-tail action help"
    )
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_kebab_upper_tail_triple_action_prefixed_help_text_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "CommandID": "CMD_17KEBABUPPERTRIPLEHELP",
            "actionName": "detail_kebab_upper_triple_help",
            "action-HELP-TEXT": "detail through kebab+upper-tail triple action help",
            "commandStatus": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "cliq",
                "app-command-get",
                "AP_17",
                "CMD_17KEBABUPPERTRIPLEHELP",
            ],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"]["commandId"] == "CMD_17KEBABUPPERTRIPLEHELP"
    assert payload["command"]["name"] == "detail_kebab_upper_triple_help"
    assert (
        payload["command"]["description"]
        == "detail through kebab+upper-tail triple action help"
    )
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_snake_kebab_upper_tail_triple_action_prefixed_help_text_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "CommandID": "CMD_17SNAKEKEBABUPPERTRIPLEHELP",
            "actionName": "detail_snake_kebab_upper_triple_help",
            "action_HELP-TEXT": "detail through snake+kebab upper-tail triple action help",
            "commandStatus": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "cliq",
                "app-command-get",
                "AP_17",
                "CMD_17SNAKEKEBABUPPERTRIPLEHELP",
            ],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"]["commandId"] == "CMD_17SNAKEKEBABUPPERTRIPLEHELP"
    assert payload["command"]["name"] == "detail_snake_kebab_upper_triple_help"
    assert (
        payload["command"]["description"]
        == "detail through snake+kebab upper-tail triple action help"
    )
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_kebab_upper_snake_tail_triple_action_prefixed_help_text_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "CommandID": "CMD_17KEBABUPPERSNAKETRIPLEHELP",
            "actionName": "detail_kebab_upper_snake_triple_help",
            "action-HELP_TEXT": "detail through kebab+upper+snake-tail triple action help",
            "commandStatus": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "cliq",
                "app-command-get",
                "AP_17",
                "CMD_17KEBABUPPERSNAKETRIPLEHELP",
            ],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"]["commandId"] == "CMD_17KEBABUPPERSNAKETRIPLEHELP"
    assert payload["command"]["name"] == "detail_kebab_upper_snake_triple_help"
    assert (
        payload["command"]["description"]
        == "detail through kebab+upper+snake-tail triple action help"
    )
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_kebab_camel_title_action_prefixed_helptext_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "CommandID": "CMD_17KEBABCAMELTITLEHELP",
            "actionName": "detail_kebab_camel_title_help",
            "action-Helptext": "detail through kebab+camel-title action help",
            "commandStatus": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "cliq",
                "app-command-get",
                "AP_17",
                "CMD_17KEBABCAMELTITLEHELP",
            ],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"]["commandId"] == "CMD_17KEBABCAMELTITLEHELP"
    assert payload["command"]["name"] == "detail_kebab_camel_title_help"
    assert (
        payload["command"]["description"]
        == "detail through kebab+camel-title action help"
    )
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_kebab_snake_tail_action_prefixed_help_text_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "CommandID": "CMD_17KEBABSNAKETAILHELP",
            "actionName": "detail_kebab_snake_tail_help",
            "action-help_text": "detail through kebab+snake-tail action help",
            "commandStatus": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "cliq",
                "app-command-get",
                "AP_17",
                "CMD_17KEBABSNAKETAILHELP",
            ],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"]["commandId"] == "CMD_17KEBABSNAKETAILHELP"
    assert payload["command"]["name"] == "detail_kebab_snake_tail_help"
    assert (
        payload["command"]["description"]
        == "detail through kebab+snake-tail action help"
    )
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_uppercase_kebab_action_prefixed_helptext_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "COMMANDID": "CMD_17UPPERKEBABHELPTEXT",
            "ACTIONNAME": "detail_upper_kebab_helptext",
            "ACTION-HELPTEXT": "detail through uppercase-kebab action helptext",
            "COMMANDSTATUS": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "cliq",
                "app-command-get",
                "AP_17",
                "CMD_17UPPERKEBABHELPTEXT",
            ],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"]["commandId"] == "CMD_17UPPERKEBABHELPTEXT"
    assert payload["command"]["name"] == "detail_upper_kebab_helptext"
    assert (
        payload["command"]["description"]
        == "detail through uppercase-kebab action helptext"
    )
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_uppercase_snake_action_prefixed_helptext_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "COMMANDID": "CMD_17UPPERSNAKEHELPTEXT",
            "ACTIONNAME": "detail_upper_snake_helptext",
            "ACTION_HELPTEXT": "detail through uppercase-snake action helptext",
            "COMMANDSTATUS": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "cliq",
                "app-command-get",
                "AP_17",
                "CMD_17UPPERSNAKEHELPTEXT",
            ],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"]["commandId"] == "CMD_17UPPERSNAKEHELPTEXT"
    assert payload["command"]["name"] == "detail_upper_snake_helptext"
    assert (
        payload["command"]["description"]
        == "detail through uppercase-snake action helptext"
    )
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_snake_upper_tail_action_prefixed_helptext_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "CommandID": "CMD_17SNAKEUPPERTAILHELPTEXT",
            "actionName": "detail_snake_upper_tail_helptext",
            "action_HELPTEXT": "detail through snake+upper-tail action helptext",
            "commandStatus": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "cliq",
                "app-command-get",
                "AP_17",
                "CMD_17SNAKEUPPERTAILHELPTEXT",
            ],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"]["commandId"] == "CMD_17SNAKEUPPERTAILHELPTEXT"
    assert payload["command"]["name"] == "detail_snake_upper_tail_helptext"
    assert (
        payload["command"]["description"]
        == "detail through snake+upper-tail action helptext"
    )
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_pascal_snake_upper_tail_action_prefixed_helptext_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "CommandID": "CMD_17PASCALSNAKEUPPERTAILHELPTEXT",
            "actionName": "detail_pascal_snake_upper_tail_helptext",
            "Action_HELPTEXT": "detail through Pascal+snake upper-tail action helptext",
            "commandStatus": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "cliq",
                "app-command-get",
                "AP_17",
                "CMD_17PASCALSNAKEUPPERTAILHELPTEXT",
            ],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"]["commandId"] == "CMD_17PASCALSNAKEUPPERTAILHELPTEXT"
    assert payload["command"]["name"] == "detail_pascal_snake_upper_tail_helptext"
    assert (
        payload["command"]["description"]
        == "detail through Pascal+snake upper-tail action helptext"
    )
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_pascal_kebab_action_prefixed_help_text_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "CommandID": "CMD_17PASCALKEBABHELP",
            "actionName": "detail_pascal_kebab_help",
            "Action-HelpText": "detail through Pascal-kebab action help text",
            "commandStatus": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "cliq",
                "app-command-get",
                "AP_17",
                "CMD_17PASCALKEBABHELP",
            ],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"]["commandId"] == "CMD_17PASCALKEBABHELP"
    assert payload["command"]["name"] == "detail_pascal_kebab_help"
    assert (
        payload["command"]["description"]
        == "detail through Pascal-kebab action help text"
    )
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_uppercase_command_prefixed_help_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "COMMANDID": "CMD_17UPPERHELP",
            "ACTIONNAME": "detail_upper_help",
            "COMMANDHELP": "detail through uppercase command help",
            "ACTIONHELP": "detail through uppercase action help",
            "COMMANDSTATUS": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "cliq",
                "app-command-get",
                "AP_17",
                "CMD_17UPPERHELP",
            ],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"]["commandId"] == "CMD_17UPPERHELP"
    assert payload["command"]["name"] == "detail_upper_help"
    assert payload["command"]["description"] == "detail through uppercase command help"
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_uppercase_snake_command_prefixed_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "data": {
            "COMMAND_ID": "CMD_17UPPERSNAKE",
            "ACTION_NAME": "detail_upper_snake_alias",
            "COMMAND_DESCRIPTION": "detail through uppercase snake description",
            "COMMAND_STATUS": "enabled",
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "cliq",
                "app-command-get",
                "AP_17",
                "CMD_17UPPERSNAKE",
            ],
            obj={},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"]["commandId"] == "CMD_17UPPERSNAKE"
    assert payload["command"]["name"] == "detail_upper_snake_alias"
    assert (
        payload["command"]["description"]
        == "detail through uppercase snake description"
    )
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_help_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "ActionID": "CMD_17HELPALIAS",
                "Help": "dispatch get help alias",
                "Mode": "enabled",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "CMD_17HELPALIAS"
    assert payload["command"]["description"] == "dispatch get help alias"
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_helptext_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "ActionID": "CMD_17HELPTEXTALIAS",
                "helptext": "dispatch get helptext alias",
                "Mode": "enabled",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17ALIAS"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "CMD_17HELPTEXTALIAS"
    assert payload["command"]["description"] == "dispatch get helptext alias"
    assert payload["command"]["status"] == "enabled"


def test_cliq_app_command_get_accepts_payload_data_action_name_pascal_case_alias_shape(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    mock_client = MagicMock()
    mock_client.get_app_command.return_value = {
        "payload": {
            "data": {
                "commandId": "CMD_17PASCALNAME",
                "ActionName": "deploy_from_payload_data_action_name_pascal_alias",
                "summary": "deploy via pascal action-name alias",
                "state": "enabled",
            }
        }
    }

    with patch("zoho_cli.cli._get_cliq_client", return_value=mock_client):
        result = runner.invoke(
            app,
            ["cliq", "app-command-get", "AP_17", "CMD_17PASCALNAME"],
            env=_cfg_env(mock_config),
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["appId"] == "AP_17"
    assert payload["command"]["commandId"] == "CMD_17PASCALNAME"
    assert (
        payload["command"]["name"]
        == "deploy_from_payload_data_action_name_pascal_alias"
    )
    assert payload["command"]["description"] == "deploy via pascal action-name alias"
    assert payload["command"]["status"] == "enabled"


@respx.mock
def test_cliq_export_chats_list(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.get("https://cliq.zoho.com/maintenanceapi/v2/chats").mock(
        return_value=httpx.Response(
            200,
            json={
                "list": [
                    {
                        "chat_id": "CT_1",
                        "title": "DM David",
                        "chat_type": "direct",
                    }
                ]
            },
        )
    )

    result = runner.invoke(app, ["cliq", "export-chats"], env=_cfg_env(mock_config))
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["chats"][0]["chatId"] == "CT_1"


@respx.mock
def test_cliq_export_chats_list_accepts_nested_data_shape(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    respx.get("https://cliq.zoho.com/maintenanceapi/v2/chats").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "chats": [
                        {
                            "chatId": "CT_2",
                            "name": "Ops",
                            "type": "channel",
                        }
                    ]
                }
            },
        )
    )

    result = runner.invoke(app, ["cliq", "export-chats"], env=_cfg_env(mock_config))
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["chats"][0]["chatId"] == "CT_2"
    assert payload["chats"][0]["title"] == "Ops"


@respx.mock
def test_cliq_export_chats_messages_and_out(
    mock_config: Path,
    mock_token_refresh: Any,
    tmp_path: Path,
) -> None:
    respx.get("https://cliq.zoho.com/maintenanceapi/v2/chats/CT_1/messages").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"id": "M1", "text": "hello"}]},
        )
    )

    out_file = tmp_path / "chat-export.json"
    result = runner.invoke(
        app,
        [
            "cliq",
            "export-chats",
            "--chat-id",
            "CT_1",
            "--out",
            str(out_file),
        ],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["chatId"] == "CT_1"
    assert payload["count"] == 1
    assert payload["savedTo"] == str(out_file)
    file_payload = json.loads(out_file.read_text())
    assert file_payload["messages"][0]["id"] == "M1"


@respx.mock
def test_cliq_export_chats_messages_accepts_messages_key(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    respx.get("https://cliq.zoho.com/maintenanceapi/v2/chats/CT_2/messages").mock(
        return_value=httpx.Response(
            200,
            json={"messages": [{"id": "M2", "text": "hello from messages key"}]},
        )
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "export-chats",
            "--chat-id",
            "CT_2",
        ],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["chatId"] == "CT_2"
    assert payload["count"] == 1
    assert payload["messages"][0]["id"] == "M2"


@respx.mock
def test_cliq_user_resolve_email(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.get("https://cliq.zoho.com/api/v2/users").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "zuid": "U1",
                        "display_name": "David Wang",
                        "email_id": "david@happy-distro.com",
                    }
                ]
            },
        )
    )

    result = runner.invoke(
        app,
        ["cliq", "user-resolve", "david@happy-distro.com", "--by", "email"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["matches"][0]["userId"] == "U1"


@respx.mock
def test_cliq_user_resolve_name(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.get("https://cliq.zoho.com/api/v2/users").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "zuid": "U1",
                        "display_name": "David Wang",
                        "email_id": "david@happy-distro.com",
                    },
                    {
                        "zuid": "U2",
                        "display_name": "Alice",
                        "email_id": "alice@happy-distro.com",
                    },
                ]
            },
        )
    )

    result = runner.invoke(
        app,
        ["cliq", "user-resolve", "david", "--by", "name"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["matches"][0]["name"] == "David Wang"


@respx.mock
def test_cliq_whoami_from_users_me(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.get("https://cliq.zoho.com/api/v2/users/me").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "zuid": "U_SELF",
                    "display_name": "Ai Dev",
                    "email_id": "ai-dev@happy-distro.co.uk",
                }
            },
        )
    )

    result = runner.invoke(app, ["cliq", "whoami"], env=_cfg_env(mock_config))
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["source"] == "/users/me"
    assert payload["user"]["userId"] == "U_SELF"


@respx.mock
def test_cliq_whoami_fallback_to_email_match(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/users/me").mock(
        return_value=httpx.Response(403, json={"code": "inactive_appaccount_user"})
    )
    respx.get("https://cliq.zoho.com/api/v2/users/self").mock(
        return_value=httpx.Response(403, json={"code": "inactive_appaccount_user"})
    )
    respx.get("https://cliq.zoho.com/api/v2/users/current").mock(
        return_value=httpx.Response(404, json={"code": "request_url_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/users").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "zuid": "U_MATCH",
                        "display_name": "Ai Dev",
                        "email_id": ACCOUNT_EMAIL,
                    }
                ]
            },
        )
    )

    result = runner.invoke(app, ["cliq", "whoami"], env=_cfg_env(mock_config))
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "best_effort"
    assert payload["user"]["userId"] == "U_MATCH"
    assert "warning" in payload


@respx.mock
def test_cliq_send_channel(mock_config: Path, mock_token_refresh: Any) -> None:
    respx.post("https://cliq.zoho.com/api/v2/channelsbyname/C1/message").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.post("https://cliq.zoho.com/api/v2/chats/C1/message").mock(
        return_value=httpx.Response(200, json={"data": {"message_id": "M1"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/C1").mock(
        return_value=httpx.Response(404, text="not_found")
    )

    result = runner.invoke(
        app,
        ["cliq", "send", "--channel-id", "C1", "--text", "hello"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"


@respx.mock
def test_cliq_send_channel_accepts_204_empty_body(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    respx.post("https://cliq.zoho.com/api/v2/channelsbyname/C1/message").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.post("https://cliq.zoho.com/api/v2/chats/C1/message").mock(
        return_value=httpx.Response(204, text="")
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/C1").mock(
        return_value=httpx.Response(404, text="not_found")
    )

    result = runner.invoke(
        app,
        ["cliq", "send", "--channel-id", "C1", "--text", "hello"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"


@respx.mock
def test_cliq_send_channel_with_image_url(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    route = respx.post("https://cliq.zoho.com/api/v2/chats/C1/message").mock(
        return_value=httpx.Response(200, json={"data": {"message_id": "M2"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/C1").mock(
        return_value=httpx.Response(404, text="not_found")
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "send",
            "--channel-id",
            "C1",
            "--text",
            "look",
            "--image-url",
            "https://example.com/image.jpg",
            "--title",
            "Screenshot",
        ],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output

    body = json.loads(route.calls.last.request.content.decode("utf-8"))
    assert body["attachments"]["url"] == "https://example.com/image.jpg"
    assert body["attachments"]["title"] == "Screenshot"

    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["media"]["imageUrl"] == "https://example.com/image.jpg"


@respx.mock
def test_cliq_send_channel_with_voice_url(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    route = respx.post("https://cliq.zoho.com/api/v2/chats/C1/message").mock(
        return_value=httpx.Response(200, json={"data": {"message_id": "M3"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/C1").mock(
        return_value=httpx.Response(404, text="not_found")
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "send",
            "--channel-id",
            "C1",
            "--voice-url",
            "https://example.com/voice.ogg",
            "--text",
            "voice",
        ],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output

    body = json.loads(route.calls.last.request.content.decode("utf-8"))
    assert body["attachments"]["url"] == "https://example.com/voice.ogg"

    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["media"]["voiceUrl"] == "https://example.com/voice.ogg"


@respx.mock
def test_cliq_send_channel_with_local_voice_file(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    sample = tmp_path / "voice.m4a"
    sample.write_bytes(b"voice-bytes")

    route = respx.post("https://cliq.zoho.com/api/v2/chats/C1/message").mock(
        return_value=httpx.Response(200, json={"data": {"message_id": "M3"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/C1").mock(
        return_value=httpx.Response(404, text="not_found")
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "send",
            "--channel-id",
            "C1",
            "--voice-url",
            str(sample),
            "--text",
            "voice",
        ],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output

    raw = route.calls.last.request.content
    assert b'name="voice"' in raw
    assert b'filename="voice.m4a"' in raw

    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["media"]["localPath"] == str(sample)
    assert payload["result"]["upload"]["path"] == "/chats/C1/message"
    assert payload["result"]["upload"]["field"] == "voice"


@respx.mock
def test_cliq_send_channel_with_local_image_file(
    tmp_path: Path,
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    sample = tmp_path / "image.png"
    sample.write_bytes(b"png-bytes")

    route = respx.post("https://cliq.zoho.com/api/v2/chats/C1/message").mock(
        return_value=httpx.Response(200, json={"data": {"message_id": "M3"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/C1").mock(
        return_value=httpx.Response(404, text="not_found")
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "send",
            "--channel-id",
            "C1",
            "--image-url",
            str(sample),
            "--text",
            "image",
        ],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output

    raw = route.calls.last.request.content
    assert b'name="image"' in raw
    assert b'filename="image.png"' in raw

    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["media"]["localPath"] == str(sample)
    assert payload["result"]["upload"]["path"] == "/chats/C1/message"
    assert payload["result"]["upload"]["field"] == "image"


def test_cliq_send_rejects_missing_local_file(
    mock_config: Path,
    mock_token_refresh: Any,
) -> None:
    result = runner.invoke(
        app,
        [
            "cliq",
            "send",
            "--channel-id",
            "C1",
            "--voice-url",
            "/tmp/definitely-missing-file-zoho-cli.m4a",
        ],
        env=_cfg_env(mock_config),
    )

    assert result.exit_code == 1
    assert "invalid_file" in result.output


@respx.mock
def test_cliq_voice_send_command(mock_config: Path, mock_token_refresh: Any) -> None:
    route = respx.post("https://cliq.zoho.com/api/v2/chats/C1/message").mock(
        return_value=httpx.Response(200, json={"data": {"message_id": "M4"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/C1").mock(
        return_value=httpx.Response(404, text="not_found")
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "voice-send",
            "--channel-id",
            "C1",
            "--voice-url",
            "https://example.com/voice.ogg",
            "--text",
            "voice send",
        ],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output

    body = json.loads(route.calls.last.request.content.decode("utf-8"))
    assert body["attachments"]["url"] == "https://example.com/voice.ogg"


@respx.mock
def test_cliq_voice_from_channel_filters_audio_files(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(200, json={"data": {"chat_id": "CT_1"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/files").mock(
        return_value=httpx.Response(
            200,
            json={
                "files": [
                    {
                        "id": "A1",
                        "mimeType": "audio/ogg",
                        "url": "https://example.com/voice.ogg",
                    },
                    {
                        "id": "A2",
                        "mimeType": "image/png",
                        "url": "https://example.com/image.png",
                    },
                ]
            },
        )
    )

    result = runner.invoke(
        app,
        ["cliq", "voice", "M1", "--channel-id", "O1"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["voiceFiles"][0]["id"] == "A1"
    assert payload["allFilesCount"] == 2
    assert payload["sourcePath"] == "/chats/CT_1/messages/M1/files"


@respx.mock
def test_cliq_voice_handles_message_without_attachments(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(200, json={"data": {"chat_id": "CT_1"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/files").mock(
        return_value=httpx.Response(
            400,
            json={
                "code": "message_attachment_not_found",
                "message": "No attachment found for this message.",
            },
        )
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/attachments").mock(
        return_value=httpx.Response(
            400,
            json={
                "code": "no_attachments_found",
                "message": "No attachments.",
            },
        )
    )

    result = runner.invoke(
        app,
        ["cliq", "voice", "M1", "--channel-id", "O1"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 0
    assert payload["voiceFiles"] == []
    assert payload["messageTypes"] == []
    assert payload["retrievalResult"] == "no_attachment_payload"
    assert payload["sourcePath"] == "/chats/CT_1/messages/M1/files"


def test_cliq_send_requires_content(mock_config: Path, mock_token_refresh: Any) -> None:
    result = runner.invoke(
        app, ["cliq", "send", "--channel-id", "C1"], env=_cfg_env(mock_config)
    )
    assert result.exit_code == 1
    assert "invalid_message" in result.output


def test_cliq_send_rejects_multiple_media_options(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    result = runner.invoke(
        app,
        [
            "cliq",
            "send",
            "--channel-id",
            "C1",
            "--image-url",
            "https://example.com/a.jpg",
            "--file-url",
            "https://example.com/a.pdf",
        ],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 1
    assert "invalid_media" in result.output


def test_cliq_voice_requires_destination(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    result = runner.invoke(app, ["cliq", "voice", "M1"], env=_cfg_env(mock_config))
    assert result.exit_code == 1
    assert "invalid_destination" in result.output


def test_cliq_send_requires_destination(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    result = runner.invoke(
        app, ["cliq", "send", "--text", "hello"], env=_cfg_env(mock_config)
    )
    assert result.exit_code == 1
    assert "invalid_destination" in result.output


@respx.mock
def test_cliq_notify_mail_to_channel(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    respx.get(f"{MAIL_BASE}/accounts/{ACCOUNT_ID}/folders/F1/messages/M1/content").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "messageId": "M1",
                    "subject": "Status",
                    "sender": "alice@example.com",
                    "textBody": "Original body",
                }
            },
        )
    )
    respx.post("https://cliq.zoho.com/api/v2/channelsbyname/C1/message").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    send_route = respx.post("https://cliq.zoho.com/api/v2/chats/C1/message").mock(
        return_value=httpx.Response(200, json={"data": {"message_id": "CM1"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/C1").mock(
        return_value=httpx.Response(404, text="not_found")
    )

    result = runner.invoke(
        app,
        [
            "cliq",
            "notify-mail",
            "M1",
            "--folder-id",
            "F1",
            "--channel-id",
            "C1",
            "--include-body",
        ],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 0, result.output

    payload = json.loads(send_route.calls.last.request.content.decode("utf-8"))
    assert "📧 New Mail" in payload["text"]
    assert "Subject: Status" in payload["text"]

    out = json.loads(result.output)
    assert out["status"] == "ok"
    assert out["subject"] == "Status"


def test_cliq_notify_mail_requires_destination(
    mock_config: Path, mock_token_refresh: Any
) -> None:
    result = runner.invoke(
        app,
        ["cliq", "notify-mail", "M1", "--folder-id", "F1"],
        env=_cfg_env(mock_config),
    )
    assert result.exit_code == 1
    assert "invalid_destination" in result.output


# ---------------------------------------------------------------------------
# config show
# ---------------------------------------------------------------------------


def test_config_show(mock_config: Path) -> None:
    """config show outputs JSON with client_secret redacted as '***'."""
    result = runner.invoke(app, ["config", "show"], env=_cfg_env(mock_config))
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["client_id"] == "test_id"
    # Secret must be redacted
    assert data["client_secret"] == "***"
    assert data["default_account"] == ACCOUNT_EMAIL


def test_config_show_preserves_accounts(mock_config: Path) -> None:
    """config show preserves the accounts section in its output."""
    result = runner.invoke(app, ["config", "show"], env=_cfg_env(mock_config))
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert ACCOUNT_EMAIL in data["accounts"]
    assert data["accounts"][ACCOUNT_EMAIL]["accountId"] == ACCOUNT_ID


# ---------------------------------------------------------------------------
# config path
# ---------------------------------------------------------------------------


def test_config_path_cmd(mock_config: Path) -> None:
    """config path outputs JSON containing a config_path key."""
    result = runner.invoke(app, ["config", "path"], env=_cfg_env(mock_config))
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert "config_path" in data
    assert str(mock_config) == data["config_path"]


def test_config_path_cmd_exists_flag(mock_config: Path) -> None:
    """config path reports exists: true when the config file is present."""
    result = runner.invoke(app, ["config", "path"], env=_cfg_env(mock_config))
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["exists"] is True


def test_config_path_cmd_nonexistent(tmp_path: Path) -> None:
    """config path reports exists: false for a path that does not exist."""
    missing = str(tmp_path / "nonexistent.json")
    result = runner.invoke(app, ["config", "path"], env={"ZOHO_CONFIG": missing})
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["exists"] is False
    assert data["config_path"] == missing


# ---------------------------------------------------------------------------
# Error propagation — missing account_id
# ---------------------------------------------------------------------------


def test_no_account_id_exits(tmp_path: Path, mock_token_refresh: Any) -> None:
    """An account entry without accountId causes exit code 1."""
    cfg = {
        "client_id": "cid",
        "client_secret": "csec",
        "default_account": ACCOUNT_EMAIL,
        "accounts": {ACCOUNT_EMAIL: {"scopes": []}},  # no accountId
    }
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg))
    result = runner.invoke(app, ["folders", "list"], env=_cfg_env(cfg_path))
    assert result.exit_code == 1
    assert "no_account_id" in result.output


# ---------------------------------------------------------------------------
# Keyring-based token flow (no mock_token_refresh fixture)
# ---------------------------------------------------------------------------


@respx.mock
def test_mail_search_via_keyring(
    mock_config: Path, mock_keyring: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Full flow: keyring provides refresh token → token exchange → search API."""
    # Token refresh HTTP call
    respx.post(f"{ACCOUNTS_BASE}/oauth/v2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "live-token"})
    )
    # Search API call
    respx.get(f"{MAIL_BASE}/accounts/{ACCOUNT_ID}/messages/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "messageId": "9001",
                        "subject": "Keyring test",
                        "sender": "bob@example.com",
                    }
                ]
            },
        )
    )
    result = runner.invoke(
        app, ["mail", "search", "keyring test"], env=_cfg_env(mock_config)
    )
    assert result.exit_code == 0, result.output
    messages = json.loads(result.output)
    assert messages[0]["messageId"] == "9001"
