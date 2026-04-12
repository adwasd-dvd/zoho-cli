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
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A51821%2Fcallback" in result.output
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
    assert payload["messages"][0]["messageId"] == "M3"


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
