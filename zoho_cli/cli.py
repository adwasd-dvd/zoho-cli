"""zoho CLI — all subcommands.

Output:
- Default → JSON to stdout (pipe-friendly, agent-friendly)
- --md    → Markdown tables/text
- stderr  → errors, debug, interactive prompts (never pollutes stdout)
"""

# ruff: noqa: E402

from __future__ import annotations

import json
import sys

# Fail fast with a clear message if any runtime dependency is missing
# (e.g. Homebrew formula may omit transitive deps like idna)
_REQUIRED_DEPS = ("idna", "httpx", "typer", "keyring", "platformdirs")
for _dep in _REQUIRED_DEPS:
    try:
        __import__(_dep)
    except ImportError:
        print(
            f"zoho-cli: missing dependency '{_dep}'.\n"
            "Reinstall with:  pip install zoho-cli   or   brew reinstall zoho-cli",
            file=sys.stderr,
        )
        sys.exit(1)

from importlib.metadata import version
from pathlib import Path
from typing import Any, List, Optional
import tempfile

# Import parse module for content extraction
from zoho_cli import parse as _parse

import click
import typer

from zoho_cli import (
    auth,
    cliq as _cliq,
    config as _config,
    crm as _crm,
    folders as _folders,
    mail as _mail,
    storage,
    utils,
)
from zoho_cli.api import ZohoMailClient
from zoho_cli.cliq import ZohoCliqClient
from zoho_cli.crm import ZohoCrmClient


def _get_version() -> str:
    try:
        from zoho_cli import __version__

        return __version__
    except Exception:
        return version("zoho-cli")


# ── app setup ─────────────────────────────────────────────────────────────────

app = typer.Typer(
    name="zoho",
    no_args_is_help=True,
    add_completion=False,
    help=f"Zoho Mail CLI (v{_get_version()}) — JSON by default, Markdown with --md.",
)
mail_app = typer.Typer(no_args_is_help=True, help="Message operations.")
attachment_subapp = typer.Typer(
    no_args_is_help=True,
    name="attachment",
    help="Attachment management (download & parse).",
)
folders_app = typer.Typer(no_args_is_help=True, help="Folder management.")
labels_app = typer.Typer(no_args_is_help=True, help="Label management.")
cliq_app = typer.Typer(no_args_is_help=True, help="Cliq operations (scaffold).")
crm_app = typer.Typer(no_args_is_help=True, help="CRM operations (scaffold).")
config_app = typer.Typer(no_args_is_help=True, help="Configuration helpers.")

app.add_typer(mail_app, name="mail")
app.add_typer(attachment_subapp, name="attachment")
app.add_typer(folders_app, name="folders")
app.add_typer(labels_app, name="labels")
app.add_typer(cliq_app, name="cliq")
app.add_typer(crm_app, name="crm")
app.add_typer(config_app, name="config")

# ── global state ──────────────────────────────────────────────────────────────


class _State:
    account: Optional[str] = None
    config_path: Optional[str] = None
    debug: bool = False
    md: bool = False


_S = _State()


# Handle -v/--version before Typer requires a subcommand
if len(sys.argv) > 1 and set(sys.argv[1:]) <= {"-v", "--version"}:
    print(_get_version())
    sys.exit(0)


@app.callback()
def _global(
    account: Optional[str] = typer.Option(
        None,
        "--account",
        "-a",
        envvar="ZOHO_ACCOUNT",
        help="Account e-mail to use.",
    ),
    config_path: Optional[str] = typer.Option(
        None,
        "--config",
        envvar="ZOHO_CONFIG",
        help="Path to config.json.",
    ),
    debug: bool = typer.Option(False, "--debug", help="Log HTTP/debug to stderr."),
    md: bool = typer.Option(False, "--md", help="Markdown output instead of JSON."),
    version_flag: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit.",
    ),
) -> None:
    if version_flag:
        print(_get_version())
        raise typer.Exit(0)
    _S.account = account
    _S.config_path = config_path
    _S.debug = debug
    _S.md = md
    utils.configure(md=md)
    if debug:
        utils.setup_debug()


# ── shared helpers ────────────────────────────────────────────────────────────


def _cfg() -> dict:
    return _config.load(_S.config_path)


def _require_account(cfg: dict) -> str:
    email = _S.account or _config.default_account(cfg)
    if not email:
        utils.error_exit(
            "no_account",
            "No account specified. Use --account or set default_account in config.",
        )
    return email  # type: ignore[return-value]


def _require_credentials(cfg: dict) -> tuple[str, str]:
    cid = (cfg.get("client_id") or "").strip()
    csec = (cfg.get("client_secret") or "").strip()
    if not cid or not csec:
        utils.error_exit(
            "missing_credentials",
            "client_id and client_secret must be set. Run: zoho config init",
        )
    return cid, csec  # type: ignore[return-value]


def _get_client(cfg: dict, email: str) -> ZohoMailClient:
    cid, csec = _require_credentials(cfg)
    account_cfg = cfg.get("accounts", {}).get(email, {})
    access_token = auth.refresh_access_token(
        email,
        cid,
        csec,
        accounts_base_url=account_cfg.get("accounts_server"),
    )
    return ZohoMailClient(access_token, mail_base_url=account_cfg.get("mail_base_url"))


def _get_cliq_client(
    cfg: dict, email: str, network: Optional[str] = None
) -> ZohoCliqClient:
    cid, csec = _require_credentials(cfg)
    account_cfg = cfg.get("accounts", {}).get(email, {})
    access_token = auth.refresh_access_token(
        email,
        cid,
        csec,
        accounts_base_url=account_cfg.get("accounts_server"),
    )
    return ZohoCliqClient(
        access_token,
        base_url=_cliq.infer_cliq_base_url(
            mail_base_url=account_cfg.get("mail_base_url"),
            accounts_server=account_cfg.get("accounts_server"),
            network=network or account_cfg.get("cliq_network"),
        ),
    )


def _get_crm_client(cfg: dict, email: str) -> ZohoCrmClient:
    cid, csec = _require_credentials(cfg)
    account_cfg = cfg.get("accounts", {}).get(email, {})
    access_token = auth.refresh_access_token(
        email,
        cid,
        csec,
        accounts_base_url=account_cfg.get("accounts_server"),
    )
    return ZohoCrmClient(
        access_token,
        base_url=_crm.infer_crm_base_url(
            mail_base_url=account_cfg.get("mail_base_url"),
            accounts_server=account_cfg.get("accounts_server"),
        ),
    )


def _require_account_id(cfg: dict, email: str) -> str:
    aid = cfg.get("accounts", {}).get(email, {}).get("accountId")
    if not aid:
        utils.error_exit(
            "no_account_id",
            f"No accountId for {email}. Run: zoho login --account {email}",
        )
    return str(aid)  # type: ignore[return-value]


def _stderr(msg: str) -> None:
    print(msg, file=sys.stderr)


def _send_and_report(
    client: ZohoMailClient,
    account_id: str,
    payload: dict,
    success_message: str,
    *,
    attachment_paths: Optional[list[str]] = None,
) -> None:
    send_resp = client.send_message(
        account_id, payload, attachment_paths=attachment_paths
    )
    utils.output_status(success_message, extra=_mail.build_send_status_extra(send_resp))


def _mail_message_context(
    cfg: dict,
    message_id: str,
    folder_id: Optional[str] = None,
) -> tuple[str, ZohoMailClient, str, str]:
    """Build shared mail command context for message-scoped operations."""
    email = _require_account(cfg)
    client = _get_client(cfg, email)
    account_id = _require_account_id(cfg, email)
    resolved_folder_id = _mail.resolve_message_folder_id(
        client, account_id, message_id, folder_id
    )
    return email, client, account_id, resolved_folder_id


def _download_attachment_to_path(
    client: ZohoMailClient,
    account_id: str,
    folder_id: str,
    message_id: str,
    attachment_id: str,
    out_path: Path,
) -> int:
    """Download an attachment and persist it to out_path, returning byte size."""
    data = client.download_attachment(account_id, folder_id, message_id, attachment_id)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    return len(data)


def _parse_attachment_content(path: Path) -> str:
    """Parse attachment content or exit for unsupported file types."""
    content = _parse.parse_attachment(path)
    if content is None:
        utils.error_exit("unsupported_format", f"Unsupported file type: {path.suffix}")
    return content


def _md_parsed_attachment_content(payload: dict) -> None:
    """Render parsed attachment content in markdown mode."""
    print(f"=== Content of {payload.get('fileName', 'attachment')} ===")
    print(payload.get("content", ""))


def _select_attachment_target(
    attachments: list[dict],
    message_id: str,
    file_name: Optional[str] = None,
) -> dict:
    """Select an attachment either by filename filter or interactive choice."""
    if file_name:
        matches = [
            a for a in attachments if file_name.lower() in a.get("fileName", "").lower()
        ]
        if not matches:
            utils.error_exit(
                "not_found", f"No attachment found with name '{file_name}'"
            )
        return matches[0]

    print(f"Attachments for message {message_id}:")
    for i, att in enumerate(attachments, 1):
        print(f"  {i}. {att['fileName']} ({utils.format_size(att['size'])})")
    choice = input("\nEnter attachment number: ")
    try:
        idx = int(choice) - 1
        if not (0 <= idx < len(attachments)):
            utils.error_exit("invalid_choice", "Invalid selection")
        return attachments[idx]
    except ValueError:
        utils.error_exit("invalid_input", "Please enter a number")
    return {}  # unreachable


def _resolve_label_id(
    client: "ZohoMailClient", account_id: str, name_or_id: str
) -> str:
    """Resolve a label name or numeric ID to a labelId string."""
    if name_or_id.isdigit():
        return name_or_id
    resp = client.get_labels(account_id)
    for lbl in resp.get("data", []):
        if lbl.get("labelName", "").lower() == name_or_id.lower():
            return str(lbl["labelId"])
    utils.error_exit(
        "label_not_found", f"Label '{name_or_id}' not found. Run: zoho labels list"
    )
    return ""  # unreachable


# ── markdown renderers ────────────────────────────────────────────────────────


def _md_mail_list(messages: list) -> None:
    rows = [
        [
            m.get("messageId", ""),
            m.get("from", ""),
            m.get("subject", "(no subject)"),
            utils.format_date(m.get("date", "")),
            "●" if m.get("unread") else "",
        ]
        for m in messages
    ]
    print(utils.md_table(["ID", "FROM", "SUBJECT", "DATE", "UNREAD"], rows))


def _md_folders(folders: list) -> None:
    rows = [
        [
            f.get("folderName", ""),
            f.get("folderType", ""),
            str(f.get("unreadCount", 0)),
            str(f.get("messageCount", "")),
        ]
        for f in folders
    ]
    print(utils.md_table(["NAME", "TYPE", "UNREAD", "MESSAGES"], rows))


def _md_attachments(atts: list) -> None:
    rows = [
        [
            a.get("attachmentId", ""),
            a.get("fileName", ""),
            utils.format_size(a.get("size", 0)),
        ]
        for a in atts
    ]
    print(utils.md_table(["ID", "FILE NAME", "SIZE"], rows))


def _md_message(msg: dict) -> None:
    lines = [
        f"**Subject:** {msg.get('subject', '')}",
        f"**From:** {msg.get('from', '')}",
        f"**To:** {', '.join(msg.get('to', []))}",
    ]
    if msg.get("cc"):
        lines.append(f"**CC:** {', '.join(msg['cc'])}")
    lines += [
        f"**Date:** {utils.format_date(msg.get('date', ''))}",
        f"**Unread:** {'yes' if msg.get('unread') else 'no'}",
        "",
        "---",
        "",
        msg.get("textBody") or msg.get("htmlBody") or "_No body_",
    ]
    print("\n".join(lines))


def _cliq_typed_message_view(message: dict[str, Any]) -> dict[str, Any]:
    mid = _cliq.ZohoCliqClient._extract_message_id(message)
    text = str(
        message.get("text")
        or message.get("content")
        or message.get("message")
        or message.get("message_text")
        or ""
    ).strip()
    sender_raw = (
        message.get("sender")
        or message.get("from")
        or message.get("author")
        or message.get("display_name")
        or ""
    )
    if isinstance(sender_raw, dict):
        sender = str(
            sender_raw.get("name")
            or sender_raw.get("display_name")
            or sender_raw.get("id")
            or ""
        ).strip()
    else:
        sender = str(sender_raw).strip()
    return {
        "messageId": mid,
        "types": _cliq.ZohoCliqClient.infer_message_types(message),
        "sender": sender,
        "textPreview": text[:160],
    }


def _cliq_typed_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        _cliq_typed_message_view(item) for item in messages if isinstance(item, dict)
    ]


# ══════════════════════════════════════════════════════════════════════════════
# zoho login
# ══════════════════════════════════════════════════════════════════════════════


@app.command("login")
def login(
    account: Optional[str] = typer.Option(
        None,
        "--account",
        "-a",
        envvar="ZOHO_ACCOUNT",
        help="Account e-mail.",
    ),
    port: int = typer.Option(
        51821,
        "--port",
        help="Local port for the OAuth callback server.",
    ),
    no_browser: bool = typer.Option(
        False,
        "--no-browser",
        help="Print the URL instead of opening a browser (headless/remote use).",
    ),
    with_cliq: bool = typer.Option(
        False,
        "--with-cliq",
        help="Include recommended Cliq OAuth scopes in this login flow.",
    ),
    with_crm: bool = typer.Option(
        False,
        "--with-crm",
        help="Include recommended CRM OAuth scopes in this login flow.",
    ),
    scope: List[str] = typer.Option(
        [],
        "--scope",
        help="Additional OAuth scope(s) to include (repeatable).",
    ),
) -> None:
    """Authenticate via Zoho OAuth 2.0."""
    cfg = _cfg()
    email = account or _S.account or _config.default_account(cfg)
    if not email:
        email = click.prompt("Account e-mail", err=True)

    client_id = (cfg.get("client_id") or "").strip() or None
    client_secret = (cfg.get("client_secret") or "").strip() or None

    if not client_id:
        client_id = click.prompt("Zoho OAuth Client ID", err=True).strip()
        cfg["client_id"] = client_id
    if not client_secret:
        client_secret = click.prompt(
            "Zoho OAuth Client Secret", hide_input=True, err=True
        ).strip()
        cfg["client_secret"] = client_secret

    import os

    scopes = auth.merge_scopes(
        auth.DEFAULT_SCOPES,
        _cliq.DEFAULT_CLIQ_SCOPES if with_cliq else [],
        _crm.DEFAULT_CRM_SCOPES if with_crm else [],
        auth.parse_scope_values(list(scope)),
    )

    if no_browser:
        # ── manual paste flow (headless / remote) ─────────────────────────
        # Detect region first (no local server needed).
        forced_accounts_url = _config.infer_accounts_server(cfg)
        if not forced_accounts_url:
            _stderr("Auto-detecting your Zoho region…")
            forced_accounts_url = auth.discover_accounts_server(client_id)
            _stderr(f"Detected: {forced_accounts_url}")
        os.environ["ZOHO_ACCOUNTS_BASE_URL"] = forced_accounts_url

        default_redirect_uri = f"http://localhost:{port}/callback"
        configured_redirect = str(cfg.get("redirect_uri") or "").strip()
        if configured_redirect in {
            "",
            "https://example.com/zoho/oauth/callback",  # legacy default
        }:
            redirect_uri = default_redirect_uri
        else:
            redirect_uri = configured_redirect
        auth_url = auth.build_auth_url(client_id, redirect_uri, scopes)
        _stderr("\n── Zoho OAuth Login (manual) ──────────────────────────────")
        _stderr("1. Open this URL in your browser:\n")
        _stderr(f"   {auth_url}\n")
        _stderr("2. Approve access.")
        _stderr("3. Copy the full redirect URL and paste it below.")
        _stderr("────────────────────────────────────────────────────────────\n")
        raw_url = click.prompt("Paste the full redirect URL here", err=True)
        code, accounts_server = auth.parse_redirect(raw_url)
    else:
        # ── browser flow with local callback server ────────────────────────
        # Bind the port NOW — before region detection — so it is held during
        # the ~8 s probe window and ready the instant the browser redirects.
        cb_server, redirect_uri, _cb_result = auth.create_callback_server(
            port,
            requested_scopes=scopes,
        )
        _stderr(f"Listening on {redirect_uri} …")

        # Detect region while the server is already bound.
        forced_accounts_url = _config.infer_accounts_server(cfg)
        if not forced_accounts_url:
            _stderr("Auto-detecting your Zoho region…")
            forced_accounts_url = auth.discover_accounts_server(client_id)
            _stderr(f"Detected: {forced_accounts_url}")
        os.environ["ZOHO_ACCOUNTS_BASE_URL"] = forced_accounts_url

        redirect_uri, code, accounts_server = auth.browser_login_flow(
            client_id,
            scopes,
            preferred_port=port,
            _server=cb_server,
            _redirect_uri=redirect_uri,
            _result=_cb_result,
        )

    token_resp = auth.exchange_code(
        code,
        client_id,
        client_secret,
        redirect_uri,
        accounts_base_url=accounts_server,
    )
    access_token = token_resp["access_token"]
    granted_scopes = auth.parse_scope_value(token_resp.get("scope")) or scopes
    refresh_token = token_resp.get("refresh_token")

    if not refresh_token:
        # Zoho omits refresh_token when:
        #   - the app's "Access Type" in the API console is set to "Online", or
        #   - the user previously authorized this app (tokens are not re-issued).
        # Fall back to the refresh_token already in storage, if one exists.
        existing = storage.load_token(email)
        refresh_token = (existing or {}).get("refresh_token")
        if not refresh_token:
            utils.error_exit(
                "oauth_no_refresh_token",
                "Zoho did not return a refresh_token.\n\n"
                "To fix, revoke the app's existing authorization so Zoho issues a fresh one:\n"
                "  1. Open https://accounts.zoho.com/apiauthstatus  (use .eu/.in/etc. for your region)\n"
                "  2. Find 'zoho-cli' and click Revoke\n"
                "  3. Run `zoho login` again\n\n"
                "If the problem persists, check that your API Console client has 'Access Type: Offline'.",
            )
        _stderr(
            "Note: Zoho did not issue a new refresh_token; keeping the existing stored one."
        )

    storage.store_token(
        email, refresh_token, granted_scopes, accounts_server=accounts_server
    )

    # Derive regional Mail API URL from the accounts server
    mail_base: Optional[str] = None
    if accounts_server:
        mail_base = accounts_server.replace("accounts.", "mail.").rstrip("/") + "/api"

    account_id = auth.discover_account_id(access_token, mail_base_url=mail_base)

    cfg.setdefault("accounts", {})[email] = {
        "accountId": account_id,
        "scopes": granted_scopes,
        **({"accounts_server": accounts_server} if accounts_server else {}),
        **({"mail_base_url": mail_base} if mail_base else {}),
    }
    if not cfg.get("default_account"):
        cfg["default_account"] = email
    # Cache the regional server at the top level so future `zoho login` calls
    # auto-detect the right server without needing --region
    if accounts_server and not cfg.get("accounts_server"):
        cfg["accounts_server"] = accounts_server
    _config.save(cfg, _S.config_path)

    if utils.is_md_mode():
        _stderr(f"\n✓  Connected as {email}  (accountId: {account_id})\n")
        _stderr("Next steps:\n")
        _stderr("  zoho folders list")
        _stderr("  zoho mail list")
        _stderr('  zoho mail search "invoice"')
        _stderr("  zoho mail list | jq '.[].subject'")
    else:
        utils.output_status(
            f"Logged in as {email}",
            extra={"account": email, "scopes": granted_scopes, "accountId": account_id},
        )


# ══════════════════════════════════════════════════════════════════════════════
# zoho mail …
# ══════════════════════════════════════════════════════════════════════════════


@mail_app.command("list")
def mail_list(
    folder: str = typer.Option("Inbox", "--folder", "-f", help="Folder name or ID."),
    limit: int = typer.Option(50, "--limit", "-n", help="Max messages."),
) -> None:
    """List messages in a folder."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_client(cfg, email)
    account_id = _require_account_id(cfg, email)

    folder_id = _mail.resolve_folder_id(client, account_id, folder)
    resp = client.get_messages(account_id, folder_id, limit=limit)
    messages = [_mail.format_message_summary(m) for m in resp.get("data", [])]
    utils.output(messages, md_render=_md_mail_list)


@mail_app.command("search")
def mail_search(
    query: str = typer.Argument(..., help="Search query."),
    limit: int = typer.Option(50, "--limit", "-n", help="Max results."),
) -> None:
    """Search messages."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_client(cfg, email)
    account_id = _require_account_id(cfg, email)

    if len(query.strip()) < 2:
        utils.error_exit("invalid_query", "Search query must be at least 2 characters.")
    # Zoho search API requires qualifier syntax (e.g. "entire:word").
    # Auto-wrap bare words so users can just type plain text naturally.
    if ":" not in query:
        query = f"entire:{query}"
    resp = client.search_messages(account_id, query, limit=limit)
    messages = [_mail.format_message_summary(m) for m in resp.get("data", [])]
    utils.output(messages, md_render=_md_mail_list)


@mail_app.command("get")
def mail_get(
    message_id: str = typer.Argument(..., help="Message ID."),
    folder_id: Optional[str] = typer.Option(
        None, "--folder-id", help="Folder ID (skips auto-scan)."
    ),
) -> None:
    """Get full message content."""
    cfg = _cfg()
    _, client, account_id, fid = _mail_message_context(cfg, message_id, folder_id)

    msg = _mail.fetch_message_content(client, account_id, fid, message_id)
    utils.output(msg, md_render=_md_message)


@mail_app.command("attachments")
def mail_attachments(
    message_id: str = typer.Argument(..., help="Message ID."),
    folder_id: Optional[str] = typer.Option(None, "--folder-id", help="Folder ID."),
) -> None:
    """List attachments for a message."""
    cfg = _cfg()
    _, client, account_id, fid = _mail_message_context(cfg, message_id, folder_id)

    atts = _mail.list_attachments(client, account_id, fid, message_id)
    utils.output(atts, md_render=_md_attachments)


@mail_app.command("download-attachment")
def mail_download_attachment(
    message_id: str = typer.Argument(..., help="Message ID."),
    attachment_id: str = typer.Argument(..., help="Attachment ID."),
    out: str = typer.Option(..., "--out", "-o", help="Output file path."),
    folder_id: Optional[str] = typer.Option(None, "--folder-id", help="Folder ID."),
    parse: bool = typer.Option(
        False,
        "--parse",
        "-p",
        help="Auto-parse and display content after download (supported: txt, md, json, csv, xlsx, pdf, docx).",
    ),
) -> None:
    """Download an attachment to a file."""
    cfg = _cfg()
    _, client, account_id, fid = _mail_message_context(cfg, message_id, folder_id)

    out_path = Path(out)
    size = _download_attachment_to_path(
        client, account_id, fid, message_id, attachment_id, out_path
    )
    saved_message = f"Saved {out_path.name} ({utils.format_size(size)})"
    saved_payload = {"path": str(out_path.resolve()), "size": size}

    if not parse:
        utils.output_status(saved_message, extra=saved_payload)
        return

    try:
        content = _parse_attachment_content(out_path)
    except RuntimeError as e:
        warning = f"Parse failed: {e}"
        if utils.is_md_mode():
            utils.output_status(saved_message, extra=saved_payload)
            utils.output_status(
                "Attachment parsed with warning", extra={"warning": warning}
            )
        else:
            utils.output_json({"status": "ok", **saved_payload, "warning": warning})
        return

    if utils.is_md_mode():
        utils.output_status(saved_message, extra=saved_payload)
        _md_parsed_attachment_content({"fileName": out_path.name, "content": content})
    else:
        utils.output_json(
            {
                "status": "ok",
                **saved_payload,
                "parsed": {"fileName": out_path.name, "content": content},
            }
        )


@mail_app.command("send")
def mail_send(
    to: List[str] = typer.Option(..., "--to", help="Recipient (repeatable)."),
    subject: str = typer.Option(..., "--subject", "-s", help="Subject line."),
    text: Optional[str] = typer.Option(None, "--text", help="Plain-text body."),
    html_file: Optional[str] = typer.Option(
        None, "--html-file", help="Path to HTML body file."
    ),
    cc: List[str] = typer.Option([], "--cc", help="CC address (repeatable)."),
    bcc: List[str] = typer.Option([], "--bcc", help="BCC address (repeatable)."),
    attach: List[str] = typer.Option(
        [], "--attach", help="Attachment path (repeatable)."
    ),
    from_addr: Optional[str] = typer.Option(
        None, "--from", help="Sender address override."
    ),
) -> None:
    """Send an email."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_client(cfg, email)
    account_id = _require_account_id(cfg, email)

    html_body: Optional[str] = None
    if html_file:
        p = Path(html_file)
        if not p.exists():
            utils.error_exit("file_not_found", f"HTML file not found: {html_file}")
        html_body = p.read_text()

    if not text and not html_body:
        utils.error_exit("missing_body", "Provide --text and/or --html-file.")

    payload = _mail.build_send_payload(
        from_address=from_addr or email,
        to_addresses=to,
        subject=subject,
        text=text,
        html_body=html_body,
        cc_addresses=cc,
        bcc_addresses=bcc,
    )

    _send_and_report(
        client,
        account_id,
        payload,
        f"Sent to {', '.join(to)}",
        attachment_paths=attach or None,
    )


# ── bulk helpers ──────────────────────────────────────────────────────────────


def _bulk(mode: str, ids: list[str], label: str, **extra) -> None:
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_client(cfg, email)
    account_id = _require_account_id(cfg, email)

    resp = client.update_message(account_id, mode, ids, **extra)
    status = resp.get("data", {})
    updated = status.get("updatedMessages", ids)
    failed = status.get("failedMessages", [])
    n = len(updated)
    utils.output_status(
        f"{label}: {n} message{'s' if n != 1 else ''}",
        extra={"updated": updated, "failed": failed},
    )


@mail_app.command("mark-read")
def mail_mark_read(ids: List[str] = typer.Argument(...)) -> None:
    """Mark messages as read."""
    _bulk("markAsRead", list(ids), "Marked read")


@mail_app.command("mark-unread")
def mail_mark_unread(ids: List[str] = typer.Argument(...)) -> None:
    """Mark messages as unread."""
    _bulk("markAsUnread", list(ids), "Marked unread")


@mail_app.command("move")
def mail_move(
    ids: List[str] = typer.Argument(...),
    to: str = typer.Option(..., "--to", help="Destination folder name or ID."),
) -> None:
    """Move messages to a folder."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_client(cfg, email)
    account_id = _require_account_id(cfg, email)

    folder_id = _mail.resolve_folder_id(client, account_id, to)
    resp = client.update_message(
        account_id, "moveMessage", list(ids), destfolderId=folder_id
    )
    status = resp.get("data", {})
    utils.output_status(
        f"Moved {len(ids)} message(s) to {to}",
        extra={
            "updated": status.get("updatedMessages", list(ids)),
            "failed": status.get("failedMessages", []),
        },
    )


@mail_app.command("spam")
def mail_spam(ids: List[str] = typer.Argument(...)) -> None:
    """Mark messages as spam."""
    _bulk("moveToSpam", list(ids), "Marked as spam")


@mail_app.command("not-spam")
def mail_not_spam(ids: List[str] = typer.Argument(...)) -> None:
    """Mark messages as not spam."""
    _bulk("markNotSpam", list(ids), "Marked as not spam")


@mail_app.command("archive")
def mail_archive(ids: List[str] = typer.Argument(...)) -> None:
    """Archive messages."""
    _bulk("archiveMails", list(ids), "Archived")


@mail_app.command("unarchive")
def mail_unarchive(ids: List[str] = typer.Argument(...)) -> None:
    """Unarchive messages."""
    _bulk("unArchiveMails", list(ids), "Unarchived")


@mail_app.command("delete")
def mail_delete(
    ids: List[str] = typer.Argument(...),
    permanent: bool = typer.Option(False, "--permanent", help="Hard delete."),
) -> None:
    """Delete messages (Trash by default; --permanent for hard delete)."""
    mode = "hardDelete" if permanent else "moveToTrash"
    label = "Permanently deleted" if permanent else "Moved to Trash"
    _bulk(mode, list(ids), label)


@mail_app.command("reply")
def mail_reply(
    message_id: str = typer.Argument(..., help="Message ID to reply to."),
    text: str = typer.Option(..., "--text", "-t", help="Reply body."),
    folder_id: Optional[str] = typer.Option(
        None, "--folder-id", help="Folder ID (skips auto-scan)."
    ),
    quote: bool = typer.Option(False, "--quote", help="Append quoted original."),
) -> None:
    """Reply to a message."""
    cfg = _cfg()
    email, client, account_id, fid = _mail_message_context(cfg, message_id, folder_id)

    msg = _mail.fetch_message_content(client, account_id, fid, message_id)
    to_addr = msg["from"]
    payload = _mail.build_reply_payload(
        from_address=email,
        to_address=to_addr,
        subject=msg["subject"],
        text=text,
        quote_original=quote,
        original_text=msg.get("textBody"),
    )
    _send_and_report(client, account_id, payload, f"Reply sent to {to_addr}")


@mail_app.command("forward")
def mail_forward(
    message_id: str = typer.Argument(..., help="Message ID to forward."),
    to: List[str] = typer.Option(..., "--to", help="Recipient (repeatable)."),
    text: Optional[str] = typer.Option(
        None, "--text", "-t", help="Optional note before the forwarded message."
    ),
    folder_id: Optional[str] = typer.Option(
        None, "--folder-id", help="Folder ID (skips auto-scan)."
    ),
) -> None:
    """Forward a message to one or more recipients."""
    cfg = _cfg()
    email, client, account_id, fid = _mail_message_context(cfg, message_id, folder_id)

    msg = _mail.fetch_message_content(client, account_id, fid, message_id)
    payload = _mail.build_forward_payload(
        from_address=email,
        to_addresses=to,
        subject=msg["subject"],
        original_from=msg["from"],
        original_subject=msg["subject"],
        note=text,
        original_text=msg.get("textBody", ""),
    )
    _send_and_report(client, account_id, payload, f"Forwarded to {', '.join(to)}")


@mail_app.command("flag")
def mail_flag(
    ids: List[str] = typer.Argument(...),
    type: str = typer.Option(
        "important", "--type", help="Flag type: important, followup, info, clear."
    ),
) -> None:
    """Flag messages (important / follow-up / info) or clear flags."""
    valid = {"important", "followup", "info", "clear"}
    if type not in valid:
        utils.error_exit(
            "invalid_flag", f"--type must be one of: {', '.join(sorted(valid))}"
        )
    flagid = "flag_not_set" if type == "clear" else type
    label = "Cleared flag" if type == "clear" else f"Flagged as {type}"
    _bulk("setFlag", list(ids), label, flagid=flagid)


@mail_app.command("tag")
def mail_tag(
    ids: List[str] = typer.Argument(...),
    label: str = typer.Option(..., "--label", "-l", help="Label name or ID."),
) -> None:
    """Apply a label to messages."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_client(cfg, email)
    account_id = _require_account_id(cfg, email)
    label_id = _resolve_label_id(client, account_id, label)
    resp = client.update_message(account_id, "applyLabel", list(ids), labelId=label_id)
    status = resp.get("data", {})
    updated = status.get("updatedMessages", list(ids))
    utils.output_status(
        f"Applied label '{label}' to {len(updated)} message(s)",
        extra={"updated": updated},
    )


@mail_app.command("untag")
def mail_untag(
    ids: List[str] = typer.Argument(...),
    label: str = typer.Option(..., "--label", "-l", help="Label name or ID."),
) -> None:
    """Remove a label from messages."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_client(cfg, email)
    account_id = _require_account_id(cfg, email)
    label_id = _resolve_label_id(client, account_id, label)
    resp = client.update_message(account_id, "removeLabel", list(ids), labelId=label_id)
    status = resp.get("data", {})
    updated = status.get("updatedMessages", list(ids))
    utils.output_status(
        f"Removed label '{label}' from {len(updated)} message(s)",
        extra={"updated": updated},
    )


@mail_app.command("untag-all")
def mail_untag_all(ids: List[str] = typer.Argument(...)) -> None:
    """Remove all labels from messages."""
    _bulk("removeAllLabels", list(ids), "Removed all labels")


# ══════════════════════════════════════════════════════════════════════════════
# zoho folders …
# ══════════════════════════════════════════════════════════════════════════════


@folders_app.command("list")
def folders_list() -> None:
    """List all folders."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_client(cfg, email)
    account_id = _require_account_id(cfg, email)

    resp = client.get_folders(account_id)
    result = [_folders.format_folder(f) for f in resp.get("data", [])]
    utils.output(result, md_render=_md_folders)


@folders_app.command("create")
def folders_create(
    name: str = typer.Argument(..., help="New folder name."),
    parent_id: Optional[str] = typer.Option(
        None, "--parent-id", help="Parent folder ID."
    ),
) -> None:
    """Create a custom folder."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_client(cfg, email)
    account_id = _require_account_id(cfg, email)

    resp = client.create_folder(account_id, name, parent_id=parent_id)
    utils.output_status(
        f"Created folder '{name}'",
        extra={"folder": _folders.format_folder(resp.get("data", {}))},
    )


@folders_app.command("rename")
def folders_rename(
    folder_id: str = typer.Argument(..., help="Folder ID."),
    name: str = typer.Argument(..., help="New name."),
) -> None:
    """Rename a folder."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_client(cfg, email)
    account_id = _require_account_id(cfg, email)

    resp = client.update_folder(account_id, folder_id, name)
    utils.output_status(
        f"Renamed to '{name}'",
        extra={"folder": _folders.format_folder(resp.get("data", {}))},
    )


@folders_app.command("delete")
def folders_delete(folder_id: str = typer.Argument(..., help="Folder ID.")) -> None:
    """Delete a custom folder."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_client(cfg, email)
    account_id = _require_account_id(cfg, email)

    client.delete_folder(account_id, folder_id)
    utils.output_status(f"Deleted folder {folder_id}", extra={"folderId": folder_id})


@folders_app.command("empty")
def folders_empty(
    folder_id: str = typer.Argument(..., help="Folder ID to empty."),
) -> None:
    """Delete all messages in a folder (e.g. empty Trash)."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_client(cfg, email)
    account_id = _require_account_id(cfg, email)
    client.folder_operation(account_id, folder_id, "emptyFolder")
    utils.output_status(f"Emptied folder {folder_id}", extra={"folderId": folder_id})


@folders_app.command("mark-read")
def folders_mark_read(folder_id: str = typer.Argument(..., help="Folder ID.")) -> None:
    """Mark all messages in a folder as read."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_client(cfg, email)
    account_id = _require_account_id(cfg, email)
    client.folder_operation(account_id, folder_id, "markAsRead")
    utils.output_status(
        f"Marked all messages as read in folder {folder_id}",
        extra={"folderId": folder_id},
    )


@folders_app.command("move")
def folders_move(
    folder_id: str = typer.Argument(..., help="Folder ID to move."),
    parent_folder_id: str = typer.Option(
        ..., "--parent-id", help="New parent folder ID."
    ),
) -> None:
    """Move a folder under a new parent."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_client(cfg, email)
    account_id = _require_account_id(cfg, email)
    client.folder_operation(
        account_id, folder_id, "move", parentFolderId=parent_folder_id
    )
    utils.output_status(
        f"Moved folder {folder_id}",
        extra={"folderId": folder_id, "parentFolderId": parent_folder_id},
    )


# ══════════════════════════════════════════════════════════════════════════════
# zoho labels …
# ══════════════════════════════════════════════════════════════════════════════


def _md_labels(lbls: list) -> None:
    rows = [
        [
            label.get("labelId", ""),
            label.get("labelName", ""),
            label.get("color", ""),
        ]
        for label in lbls
    ]
    print(utils.md_table(["ID", "NAME", "COLOR"], rows))


@labels_app.command("list")
def labels_list() -> None:
    """List all labels."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_client(cfg, email)
    account_id = _require_account_id(cfg, email)
    resp = client.get_labels(account_id)
    result = [
        {
            "labelId": str(label.get("labelId", "")),
            "labelName": label.get("labelName", ""),
            "color": label.get("color", ""),
        }
        for label in resp.get("data", [])
    ]
    utils.output(result, md_render=_md_labels)


@labels_app.command("create")
def labels_create(
    name: str = typer.Argument(..., help="Label name."),
    color: Optional[str] = typer.Option(
        None, "--color", help="Hex color, e.g. #FF0000."
    ),
) -> None:
    """Create a new label."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_client(cfg, email)
    account_id = _require_account_id(cfg, email)
    resp = client.create_label(account_id, name, color=color)
    lbl = resp.get("data", resp)
    utils.output_status(
        f"Created label '{name}'", extra={"labelId": str(lbl.get("labelId", ""))}
    )


@labels_app.command("delete")
def labels_delete(label_id: str = typer.Argument(..., help="Label ID.")) -> None:
    """Delete a label."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_client(cfg, email)
    account_id = _require_account_id(cfg, email)
    client.delete_label(account_id, label_id)
    utils.output_status(f"Deleted label {label_id}", extra={"labelId": label_id})


# ══════════════════════════════════════════════════════════════════════════════
# zoho cliq …
# ══════════════════════════════════════════════════════════════════════════════


@cliq_app.command("status")
def cliq_status(
    check_auth: bool = typer.Option(
        False, "--check-auth", help="Verify OAuth refresh for the selected account."
    ),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Show Cliq scaffold readiness and inferred API endpoint."""
    cfg = _cfg()
    email = _S.account or _config.default_account(cfg)
    account_cfg = cfg.get("accounts", {}).get(email, {}) if email else {}

    payload: dict = {
        "module": "cliq",
        "scaffold": "ready",
        "account": email or "",
        "hasAccount": bool(email),
        "hasAccountId": bool(account_cfg.get("accountId")),
        "baseUrl": _cliq.infer_cliq_base_url(
            mail_base_url=account_cfg.get("mail_base_url"),
            accounts_server=account_cfg.get("accounts_server"),
            network=network or account_cfg.get("cliq_network"),
        ),
        "requiredScopes": _cliq.DEFAULT_CLIQ_SCOPES,
        "grantedScopes": account_cfg.get("scopes", []),
        "next": [
            "discover capability matrix",
            "implement messages/context read plane",
            "implement watch/reply/edit/delete operations",
        ],
    }

    payload["missingScopes"] = _cliq.missing_cliq_scopes(
        payload.get("grantedScopes", [])
    )
    payload["oauthReady"] = len(payload["missingScopes"]) == 0

    if check_auth and email:
        cid, csec = _require_credentials(cfg)
        token_info = auth.refresh_access_token_info(
            email,
            cid,
            csec,
            accounts_base_url=account_cfg.get("accounts_server"),
        )
        payload["auth"] = "ok"
        live_scopes = token_info.get("scopes", [])
        if live_scopes:
            payload["grantedScopes"] = live_scopes
            payload["missingScopes"] = _cliq.missing_cliq_scopes(live_scopes)
            payload["oauthReady"] = len(payload["missingScopes"]) == 0

    utils.output(payload)


@cliq_app.command("capabilities")
def cliq_capabilities(
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
    channel_id: Optional[str] = typer.Option(
        None,
        "--channel-id",
        help="Optional channel/chat id for deeper endpoint probes.",
    ),
    user_id: Optional[str] = typer.Option(
        None, "--user-id", help="Optional user id for deeper endpoint probes."
    ),
    message_id: Optional[str] = typer.Option(
        None,
        "--message-id",
        help="Optional message id for deeper message/file/attachment probes (requires --channel-id).",
    ),
) -> None:
    """Probe currently-available Cliq read capabilities for this token and org."""
    if (message_id or "").strip() and not (channel_id or "").strip():
        utils.error_exit(
            "invalid_destination",
            "Provide --channel-id when using --message-id for message/file capability probes",
        )

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    probe = client.probe_capabilities(
        channel_id=channel_id,
        user_id=user_id,
        message_id=message_id,
    )
    payload = {
        "module": "cliq",
        "capabilityStage": "cliq-100",
        "account": email,
        "baseUrl": client.base_url,
        "inputs": {
            "network": network or "",
            "channelId": channel_id or "",
            "userId": user_id or "",
            "messageId": message_id or "",
        },
        **probe,
    }
    utils.output(payload)


@cliq_app.command("channels")
def cliq_channels(
    limit: int = typer.Option(50, "--limit", "-n", help="Max channels to return."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List Cliq channels."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resp = client.channels(limit=limit)
    data = resp.get("data", resp)
    utils.output(data)


@cliq_app.command("chats")
def cliq_chats(
    limit: int = typer.Option(50, "--limit", "-n", help="Max chats to return."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List Cliq chats (DM/group conversation descriptors)."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resp = client.chats(limit=limit)
    data = resp.get("data", resp)
    if not isinstance(data, list):
        data = []

    views: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        views.append(
            {
                "chatId": str(
                    row.get("id") or row.get("chat_id") or row.get("chatId") or ""
                ),
                "name": str(
                    row.get("name") or row.get("title") or row.get("display_name") or ""
                ),
                "type": str(
                    row.get("type") or row.get("chat_type") or row.get("chatType") or ""
                ),
                "raw": row,
            }
        )

    utils.output(
        {
            "count": len(views),
            "chats": views,
        }
    )


@cliq_app.command("users")
def cliq_users(
    limit: int = typer.Option(50, "--limit", "-n", help="Max users to return."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List Cliq users."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resp = client.users(limit=limit)
    data = resp.get("data", resp)
    utils.output(data)


@cliq_app.command("export-chats")
def cliq_export_chats(
    chat_id: Optional[str] = typer.Option(
        None,
        "--chat-id",
        help="Export messages for one chat id; omit to export conversation descriptors.",
    ),
    out: Optional[Path] = typer.Option(
        None,
        "--out",
        help="Optional output JSON file path.",
    ),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Export Cliq chats or one chat's message history via maintenance API."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    payload: dict[str, Any]
    if (chat_id or "").strip():
        resolved_chat = (chat_id or "").strip()
        resp = client.export_chat_messages(resolved_chat)
        data = resp.get("data", resp)
        messages = data if isinstance(data, list) else []
        payload = {
            "chatId": resolved_chat,
            "count": len(messages),
            "messages": messages,
        }
    else:
        resp = client.export_conversations()
        rows = resp.get("list", [])
        if not isinstance(rows, list):
            rows = []

        chats: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            chats.append(
                {
                    "chatId": str(
                        row.get("chat_id") or row.get("chatId") or row.get("id") or ""
                    ),
                    "title": str(
                        row.get("title")
                        or row.get("name")
                        or row.get("display_name")
                        or ""
                    ),
                    "type": str(row.get("chat_type") or row.get("type") or ""),
                    "raw": row,
                }
            )

        payload = {
            "count": len(chats),
            "chats": chats,
        }

    if out is not None:
        out_path = out.expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        payload["savedTo"] = str(out_path)

    utils.output(payload)


@cliq_app.command("whoami")
def cliq_whoami(
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
    limit: int = typer.Option(
        500,
        "--limit",
        "-n",
        help="Directory scan size for email-match fallback.",
    ),
) -> None:
    """Best-effort identity check for the current Cliq token."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    result = client.whoami(account_email=email, limit=limit)
    utils.output(
        {
            "account": email,
            "baseUrl": client.base_url,
            **result,
        }
    )


@cliq_app.command("user-resolve")
def cliq_user_resolve(
    query: str = typer.Argument(..., help="User lookup query (email or display name)."),
    by: str = typer.Option("auto", "--by", help="Match mode: auto|email|name."),
    limit: int = typer.Option(500, "--limit", "-n", help="Max users to scan."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Resolve user ids by email or display name."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    result = client.resolve_users(query, by=by, limit=limit)
    utils.output(result)


@cliq_app.command("members")
def cliq_members(
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Channel id (preferred for member listing)."
    ),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Chat id."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List members for a channel/chat."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip()
    resp = client.list_members(chat_id=resolved_chat, channel_id=channel_id)
    members = resp.get("members", resp.get("data", resp))
    if not isinstance(members, list):
        members = []

    utils.output(
        {
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "count": len(members),
            "members": members,
        }
    )


@cliq_app.command("channel-create")
def cliq_channel_create(
    name: str = typer.Option(..., "--name", help="Channel display name."),
    level: str = typer.Option(
        "organization",
        "--level",
        help="Channel level (for example: organization/team).",
    ),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Create a Cliq channel."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resp = client.create_channel(name, level=level)
    data = resp.get("data", resp)
    utils.output_status(
        "Cliq channel created",
        extra={
            "name": name,
            "level": level,
            "result": data,
        },
    )


@cliq_app.command("channel-rename")
def cliq_channel_rename(
    channel_id: str = typer.Argument(..., help="Target channel id."),
    name: str = typer.Option(..., "--name", help="New channel display name."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Rename a Cliq channel."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resp = client.rename_channel(channel_id, name)
    data = resp.get("data", resp)
    utils.output_status(
        "Cliq channel renamed",
        extra={
            "channelId": channel_id,
            "name": name,
            "result": data,
        },
    )


@cliq_app.command("channel-topic")
def cliq_channel_topic(
    channel_id: str = typer.Argument(..., help="Target channel id."),
    topic: str = typer.Option(..., "--topic", help="Channel topic/description."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Update a Cliq channel topic."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resp = client.update_channel_topic(channel_id, topic)
    data = resp.get("data", resp)
    utils.output_status(
        "Cliq channel topic updated",
        extra={
            "channelId": channel_id,
            "topic": topic,
            "result": data,
        },
    )


@cliq_app.command("member-add")
def cliq_member_add(
    member_id: str = typer.Argument(..., help="Member/user id to add."),
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Target channel id."
    ),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Target chat id."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Add a member to a channel/chat."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    resp = client.add_member(
        member_id,
        chat_id=resolved_chat,
        channel_id=channel_id,
    )
    data = resp.get("data", resp)
    utils.output_status(
        "Cliq member added",
        extra={
            "memberId": member_id,
            "chatId": resolved_chat,
            "channelId": channel_id or "",
            "result": data,
        },
    )


@cliq_app.command("member-remove")
def cliq_member_remove(
    member_id: str = typer.Argument(..., help="Member/user id to remove."),
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Target channel id."
    ),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Target chat id."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Remove a member from a channel/chat."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    resp = client.remove_member(
        member_id,
        chat_id=resolved_chat,
        channel_id=channel_id,
    )
    data = resp.get("data", resp)
    utils.output_status(
        "Cliq member removed",
        extra={
            "memberId": member_id,
            "chatId": resolved_chat,
            "channelId": channel_id or "",
            "result": data,
        },
    )


@cliq_app.command("channel-archive")
def cliq_channel_archive(
    channel_id: str = typer.Argument(..., help="Target channel id."),
    unarchive: bool = typer.Option(
        False, "--unarchive", help="Unarchive instead of archiving."
    ),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Archive or unarchive a Cliq channel."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resp = client.archive_channel(channel_id, unarchive=unarchive)
    data = resp.get("data", resp)
    utils.output_status(
        "Cliq channel unarchived" if unarchive else "Cliq channel archived",
        extra={"channelId": channel_id, "unarchive": unarchive, "result": data},
    )


@cliq_app.command("channel-delete")
def cliq_channel_delete(
    channel_id: str = typer.Argument(..., help="Target channel id."),
    force: bool = typer.Option(False, "--force", help="Confirm channel deletion."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Delete a Cliq channel."""
    if not force:
        utils.error_exit("confirm_required", "Add --force to delete a channel")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resp = client.delete_channel(channel_id)
    data = resp.get("data", resp)
    utils.output_status(
        "Cliq channel deleted",
        extra={"channelId": channel_id, "result": data},
    )


@cliq_app.command("channel-unarchive")
def cliq_channel_unarchive(
    channel_id: str = typer.Argument(..., help="Target channel id."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Unarchive a Cliq channel."""
    cliq_channel_archive(channel_id=channel_id, unarchive=True, network=network)


@cliq_app.command("search")
def cliq_search(
    query: str = typer.Argument(..., help="Search query text."),
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Source channel id (resolved to chat_id)."
    ),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Source chat id."),
    limit: int = typer.Option(50, "--limit", "-n", help="Max results to return."),
    from_time: Optional[str] = typer.Option(
        None,
        "--from-time",
        help="Search window start (passed through to Cliq API).",
    ),
    to_time: Optional[str] = typer.Option(
        None,
        "--to-time",
        help="Search window end (passed through to Cliq API).",
    ),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Search messages for a channel/chat with keyword + optional time window."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    resp = client.search_messages(
        query,
        chat_id=resolved_chat,
        channel_id=channel_id,
        limit=limit,
        from_time=from_time,
        to_time=to_time,
    )
    data = resp.get("data", resp)
    messages: list[dict] = []
    if isinstance(data, list):
        messages = [item for item in data if isinstance(item, dict)]
    elif isinstance(data, dict):
        for key in ("messages", "results", "items", "data"):
            candidate = data.get(key)
            if isinstance(candidate, list):
                messages = [item for item in candidate if isinstance(item, dict)]
                break

    utils.output(
        {
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "query": query,
            "window": {
                "fromTime": from_time or "",
                "toTime": to_time or "",
            },
            "count": len(messages),
            "messages": messages,
        }
    )


@cliq_app.command("file")
def cliq_file(
    message_id: str = typer.Argument(..., help="Cliq message id."),
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Source channel id (resolved to chat_id)."
    ),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Source chat id."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Retrieve file/attachment metadata for one message in a channel/chat."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    message_types: list[str] = []
    try:
        message_resp = client.get_message(
            message_id,
            chat_id=resolved_chat,
            channel_id=channel_id,
        )
        message_data = (
            message_resp.get("data", message_resp)
            if isinstance(message_resp, dict)
            else {}
        )
        if isinstance(message_data, dict):
            message_types = client.infer_message_types(message_data)
    except Exception:
        message_types = []

    resp = client.get_message_files(
        message_id,
        chat_id=resolved_chat,
        channel_id=channel_id,
    )
    fetch_meta = resp.get("fetch") if isinstance(resp, dict) else None
    if not isinstance(fetch_meta, dict):
        fetch_meta = {}

    data = resp.get("data", resp)
    files: list[dict] = []
    if isinstance(data, list):
        files = [item for item in data if isinstance(item, dict)]
    elif isinstance(data, dict):
        for key in ("files", "attachments", "items", "data"):
            candidate = data.get(key)
            if isinstance(candidate, list):
                files = [item for item in candidate if isinstance(item, dict)]
                break

    media_types = {"image", "file", "voice"}
    retrieval_result = "attachments_found"
    if not files:
        retrieval_result = (
            "media_visible_without_attachment_payload"
            if any(t in media_types for t in message_types)
            else "no_attachment_payload"
        )

    utils.output(
        {
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "messageId": message_id,
            "messageTypes": message_types,
            "retrievalResult": retrieval_result,
            "sourcePath": str(fetch_meta.get("path") or ""),
            "count": len(files),
            "files": files,
        }
    )


@cliq_app.command("voice")
def cliq_voice(
    message_id: str = typer.Argument(..., help="Cliq message id."),
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Source channel id (resolved to chat_id)."
    ),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Source chat id."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Retrieve voice/audio attachment metadata from one Cliq message."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    message_types: list[str] = []
    try:
        message_resp = client.get_message(
            message_id,
            chat_id=resolved_chat,
            channel_id=channel_id,
        )
        message_data = (
            message_resp.get("data", message_resp)
            if isinstance(message_resp, dict)
            else {}
        )
        if isinstance(message_data, dict):
            message_types = client.infer_message_types(message_data)
    except Exception:
        message_types = []

    resp = client.get_message_files(
        message_id,
        chat_id=resolved_chat,
        channel_id=channel_id,
    )
    fetch_meta = resp.get("fetch") if isinstance(resp, dict) else None
    if not isinstance(fetch_meta, dict):
        fetch_meta = {}

    data = resp.get("data", resp)
    files: list[dict] = []
    if isinstance(data, list):
        files = [item for item in data if isinstance(item, dict)]
    elif isinstance(data, dict):
        for key in ("files", "attachments", "items", "data"):
            candidate = data.get(key)
            if isinstance(candidate, list):
                files = [item for item in candidate if isinstance(item, dict)]
                break

    def _is_voice(item: dict) -> bool:
        value = " ".join(
            str(item.get(k) or "")
            for k in (
                "type",
                "mime_type",
                "mimeType",
                "content_type",
                "contentType",
                "file_type",
                "fileType",
                "name",
                "file_name",
                "fileName",
                "title",
                "url",
            )
        ).lower()
        if "audio" in value or "voice" in value:
            return True
        return any(
            ext in value
            for ext in (
                ".mp3",
                ".m4a",
                ".wav",
                ".ogg",
                ".aac",
                ".flac",
                ".opus",
                ".webm",
                ".amr",
            )
        )

    voice_files = [item for item in files if _is_voice(item)]

    media_types = {"image", "file", "voice"}
    retrieval_result = "voice_found"
    if not voice_files:
        if files:
            retrieval_result = "attachments_found_but_no_voice"
        else:
            retrieval_result = (
                "media_visible_without_attachment_payload"
                if any(t in media_types for t in message_types)
                else "no_attachment_payload"
            )

    utils.output(
        {
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "messageId": message_id,
            "messageTypes": message_types,
            "retrievalResult": retrieval_result,
            "sourcePath": str(fetch_meta.get("path") or ""),
            "count": len(voice_files),
            "voiceFiles": voice_files,
            "allFilesCount": len(files),
        }
    )


@cliq_app.command("messages")
def cliq_messages(
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Source channel id (resolved to chat_id)."
    ),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Source chat id."),
    limit: int = typer.Option(50, "--limit", "-n", help="Max messages to return."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List messages for a channel/chat."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    resp = client.list_messages(
        chat_id=resolved_chat, channel_id=channel_id, limit=limit
    )
    messages = resp.get("data", resp)
    if not isinstance(messages, list):
        messages = []

    utils.output(
        {
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "count": len(messages),
            "messages": messages,
            "typedMessages": _cliq_typed_messages(messages),
        }
    )


@cliq_app.command("message")
def cliq_message(
    message_id: str = typer.Argument(..., help="Cliq message id."),
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Source channel id (resolved to chat_id)."
    ),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Source chat id."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Get one message by id from a channel/chat."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    resp = client.get_message(message_id, chat_id=resolved_chat, channel_id=channel_id)
    message = resp.get("data", resp)
    if isinstance(message, list):
        message = message[0] if message else {}
    utils.output(
        {
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "message": message,
            "messageTypes": _cliq.ZohoCliqClient.infer_message_types(
                message if isinstance(message, dict) else {}
            ),
        }
    )


@cliq_app.command("context")
def cliq_context(
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Source channel id (resolved to chat_id)."
    ),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Source chat id."),
    message_id: Optional[str] = typer.Option(
        None, "--message-id", help="Anchor message id (optional)."
    ),
    before: int = typer.Option(3, "--before", help="Messages before anchor."),
    after: int = typer.Option(3, "--after", help="Messages after anchor."),
    limit: int = typer.Option(40, "--limit", "-n", help="Max messages to fetch."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Build a local context window for a channel/chat (optionally around one message)."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")
    if before < 0 or after < 0:
        utils.error_exit("invalid_window", "--before/--after must be >= 0")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    resp = client.list_messages(
        chat_id=resolved_chat, channel_id=channel_id, limit=limit
    )
    messages = resp.get("data", resp)
    if not isinstance(messages, list):
        messages = []

    anchor: dict | None = None
    anchor_idx: int | None = None
    if message_id:
        msg_resp = client.get_message(
            message_id, chat_id=resolved_chat, channel_id=channel_id
        )
        anchor_data = msg_resp.get("data", msg_resp)
        if isinstance(anchor_data, list):
            anchor = anchor_data[0] if anchor_data else None
        elif isinstance(anchor_data, dict):
            anchor = anchor_data

        for idx, item in enumerate(messages):
            if not isinstance(item, dict):
                continue
            if _cliq.ZohoCliqClient._extract_message_id(item) == message_id:
                anchor_idx = idx
                break

    if anchor_idx is None:
        slice_size = before + after + 1
        context_messages = messages[:slice_size]
    else:
        start = max(0, anchor_idx - before)
        end = anchor_idx + after + 1
        context_messages = messages[start:end]

    utils.output(
        {
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "anchorMessageId": message_id or "",
            "anchorInWindow": anchor_idx is not None,
            "window": {"before": before, "after": after},
            "totalFetched": len(messages),
            "anchor": anchor or {},
            "anchorTypes": _cliq.ZohoCliqClient.infer_message_types(
                anchor if isinstance(anchor, dict) else {}
            ),
            "messages": context_messages,
            "typedMessages": _cliq_typed_messages(
                [item for item in context_messages if isinstance(item, dict)]
            ),
        }
    )


@cliq_app.command("watch-context")
def cliq_watch_context(
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Source channel id (resolved to chat_id)."
    ),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Source chat id."),
    since_message_id: Optional[str] = typer.Option(
        None,
        "--since-message-id",
        help="Last processed message id cursor from a previous watch pass.",
    ),
    limit: int = typer.Option(50, "--limit", "-n", help="Max messages to fetch."),
    max_messages: int = typer.Option(
        20,
        "--max-messages",
        help="Max new messages to emit in one watch payload.",
    ),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Emit a stable incremental context payload for OpenClaw-style watch loops."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")
    if limit < 1 or max_messages < 1:
        utils.error_exit("invalid_limit", "--limit/--max-messages must be >= 1")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    fetch_limit = max(limit, max_messages)
    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    resp = client.list_messages(
        chat_id=resolved_chat,
        channel_id=channel_id,
        limit=fetch_limit,
    )
    data = resp.get("data", resp)
    messages = (
        [item for item in data if isinstance(item, dict)]
        if isinstance(data, list)
        else []
    )

    watch = _cliq.ZohoCliqClient.build_watch_context_seed(
        messages,
        since_message_id=since_message_id,
        max_messages=max_messages,
    )

    utils.output(
        {
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "cursor": {
                "sinceMessageId": watch["sinceMessageId"],
                "cursorFound": watch["cursorFound"],
                "latestMessageId": watch["latestMessageId"],
                "nextSinceMessageId": watch["nextSinceMessageId"],
            },
            "totalFetched": watch["totalFetched"],
            "newCount": watch["newCount"],
            "truncated": watch["truncated"],
            "messages": watch["messages"],
        }
    )


@cliq_app.command("watch-act")
def cliq_watch_act(
    watch_file: str = typer.Option(
        "-",
        "--watch-file",
        help="Path to watch-context JSON payload (use '-' to read from stdin).",
    ),
    text: str = typer.Option(..., "--text", "-t", help="Reply text to send."),
    channel_id: Optional[str] = typer.Option(
        None,
        "--channel-id",
        help="Override destination channel id from payload.",
    ),
    chat_id: Optional[str] = typer.Option(
        None,
        "--chat-id",
        help="Override destination chat id from payload.",
    ),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Execute one deterministic action from watch payload (reply to latest message)."""
    raw = ""
    source = watch_file.strip()
    if source == "-":
        raw = sys.stdin.read()
    else:
        payload_path = Path(source)
        if not payload_path.exists():
            utils.error_exit("file_not_found", f"Watch payload not found: {source}")
        raw = payload_path.read_text()

    try:
        watch_payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        utils.error_exit("invalid_watch_payload", f"Invalid JSON payload: {exc}")

    if not isinstance(watch_payload, dict):
        utils.error_exit("invalid_watch_payload", "Watch payload must be a JSON object")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    result = client.execute_watch_reply_action(
        watch_payload,
        text=text,
        chat_id=chat_id,
        channel_id=channel_id,
    )
    utils.output(result)


@cliq_app.command("reply")
def cliq_reply(
    message_id: str = typer.Argument(..., help="Anchor message id to reply to."),
    text: str = typer.Option(..., "--text", "-t", help="Reply message text."),
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Destination channel id (resolved to chat_id)."
    ),
    chat_id: Optional[str] = typer.Option(
        None, "--chat-id", help="Destination chat id."
    ),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Reply to a Cliq message."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    resp = client.reply_message(
        text,
        message_id=message_id,
        chat_id=resolved_chat,
        channel_id=channel_id,
    )
    data = resp.get("data", resp)
    utils.output_status(
        "Cliq reply sent",
        extra={
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "replyTo": message_id,
            "result": data,
        },
    )


@cliq_app.command("edit")
def cliq_edit(
    message_id: str = typer.Argument(..., help="Target message id."),
    text: str = typer.Option(..., "--text", "-t", help="Updated message text."),
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Destination channel id (resolved to chat_id)."
    ),
    chat_id: Optional[str] = typer.Option(
        None, "--chat-id", help="Destination chat id."
    ),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Edit a Cliq message."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    resp = client.edit_message(
        message_id,
        text,
        chat_id=resolved_chat,
        channel_id=channel_id,
    )
    data = resp.get("data", resp)
    utils.output_status(
        "Cliq message edited",
        extra={
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "messageId": message_id,
            "result": data,
        },
    )


@cliq_app.command("delete")
def cliq_delete(
    message_id: str = typer.Argument(..., help="Target message id."),
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Destination channel id (resolved to chat_id)."
    ),
    chat_id: Optional[str] = typer.Option(
        None, "--chat-id", help="Destination chat id."
    ),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Delete a Cliq message."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    resp = client.delete_message(
        message_id,
        chat_id=resolved_chat,
        channel_id=channel_id,
    )
    data = resp.get("data", resp)
    utils.output_status(
        "Cliq message deleted",
        extra={
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "messageId": message_id,
            "result": data,
        },
    )


@cliq_app.command("react")
def cliq_react(
    message_id: str = typer.Argument(..., help="Target message id."),
    emoji: str = typer.Option(..., "--emoji", help="Emoji to add/remove as reaction."),
    remove: bool = typer.Option(
        False, "--remove", help="Remove reaction instead of adding it."
    ),
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Destination channel id (resolved to chat_id)."
    ),
    chat_id: Optional[str] = typer.Option(
        None, "--chat-id", help="Destination chat id."
    ),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Add/remove a reaction to a Cliq message."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    resp = client.react_message(
        message_id,
        emoji,
        remove=remove,
        chat_id=resolved_chat,
        channel_id=channel_id,
    )
    data = resp.get("data", resp)
    utils.output_status(
        "Cliq reaction removed" if remove else "Cliq reaction added",
        extra={
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "messageId": message_id,
            "emoji": emoji,
            "remove": remove,
            "result": data,
        },
    )


@cliq_app.command("voice-send")
def cliq_voice_send(
    voice_url: str = typer.Option(..., "--voice-url", help="Voice/audio URL to send."),
    text: Optional[str] = typer.Option(
        None, "--text", "-t", help="Optional message text."
    ),
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Destination channel id."
    ),
    user_id: Optional[str] = typer.Option(
        None, "--user-id", help="Destination user id."
    ),
    title: Optional[str] = typer.Option(
        None, "--title", help="Optional voice card title."
    ),
    button_label: Optional[str] = typer.Option(
        None, "--button-label", help="Optional voice card button label."
    ),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Send a voice/audio message link to a channel or user."""
    cliq_send(
        text=text,
        channel_id=channel_id,
        user_id=user_id,
        image_url=None,
        file_url=None,
        audio_url=None,
        voice_url=voice_url,
        title=title,
        button_label=button_label,
        sticker=None,
        network=network,
    )


@cliq_app.command("send")
def cliq_send(
    text: Optional[str] = typer.Option(None, "--text", "-t", help="Message text."),
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Destination channel id."
    ),
    user_id: Optional[str] = typer.Option(
        None, "--user-id", help="Destination user id."
    ),
    image_url: Optional[str] = typer.Option(
        None,
        "--image-url",
        help="Image URL to send as a rich media attachment card.",
    ),
    file_url: Optional[str] = typer.Option(
        None,
        "--file-url",
        help="File URL to send as a rich media attachment card.",
    ),
    audio_url: Optional[str] = typer.Option(
        None,
        "--audio-url",
        help="Audio/voice URL to send as a rich media attachment card.",
    ),
    voice_url: Optional[str] = typer.Option(
        None,
        "--voice-url",
        help="Alias for --audio-url (voice message URL).",
    ),
    title: Optional[str] = typer.Option(
        None,
        "--title",
        help="Optional media title override for --image-url/--file-url/--audio-url.",
    ),
    button_label: Optional[str] = typer.Option(
        None,
        "--button-label",
        help="Optional attachment button label. Defaults by media type.",
    ),
    sticker: Optional[str] = typer.Option(
        None,
        "--sticker",
        help="Sticker/emoji shortcode appended to the outgoing text.",
    ),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Send a Cliq message to a channel or user (text + rich-link media)."""
    if bool(channel_id) == bool(user_id):
        utils.error_exit(
            "invalid_destination", "Provide exactly one of channel_id or user_id"
        )

    media_inputs = [
        ("image", (image_url or "").strip()),
        ("file", (file_url or "").strip()),
        ("audio", (audio_url or "").strip()),
        ("audio", (voice_url or "").strip()),
    ]
    selected_media = [(kind, url) for kind, url in media_inputs if url]
    if len(selected_media) > 1:
        utils.error_exit(
            "invalid_media",
            "Provide only one of --image-url, --file-url, --audio-url, or --voice-url per send operation",
        )

    text_payload = (text or "").strip()
    sticker_payload = (sticker or "").strip()
    if sticker_payload:
        text_payload = (
            f"{text_payload} {sticker_payload}".strip()
            if text_payload
            else sticker_payload
        )

    attachment: dict | None = None
    card: dict | None = None
    local_media_path: Path | None = None
    selected_media_kind = ""
    if selected_media:
        media_kind, media_url = selected_media[0]
        selected_media_kind = media_kind
        candidate_path = Path(media_url).expanduser()
        if candidate_path.exists() and candidate_path.is_file():
            local_media_path = candidate_path
        elif media_url.startswith("/"):
            utils.error_exit("invalid_file", f"File not found: {candidate_path}")

        # Ensure link-preview style media still appears even when rich payload
        # variants are accepted but attachment fields are ignored by endpoint.
        if local_media_path is None and media_url.startswith(("http://", "https://")):
            if media_url not in text_payload:
                text_payload = (
                    f"{text_payload}\n{media_url}".strip()
                    if text_payload
                    else media_url
                )

        default_title = {
            "image": "Image",
            "file": "File",
            "audio": "Audio",
        }.get(media_kind, "Attachment")
        default_button = {
            "image": "View",
            "file": "Download",
            "audio": "Listen",
        }.get(media_kind, "Open")

        attachment = {
            "title": (title or "").strip() or default_title,
            "url": media_url,
            "button_label": (button_label or "").strip() or default_button,
        }
        if media_kind == "image":
            card = {
                "title": attachment["title"],
                "thumbnail": media_url,
            }

    if not text_payload and not attachment:
        utils.error_exit(
            "invalid_message",
            "Provide --text/--sticker or one media option (--image-url/--file-url/--audio-url/--voice-url)",
        )

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    if local_media_path is not None:
        resp = client.send_local_file_message(
            str(local_media_path),
            text=text_payload,
            channel_id=channel_id,
            user_id=user_id,
            media_kind="voice"
            if selected_media_kind == "audio"
            else selected_media_kind,
        )
    else:
        resp = client.send_message(
            text_payload,
            channel_id=channel_id,
            user_id=user_id,
            attachment=attachment,
            card=card,
            strict_media=bool(selected_media),
        )

    data = resp.get("data", resp)
    utils.output_status(
        "Cliq message sent",
        extra={
            "result": data,
            "media": {
                "imageUrl": (image_url or "").strip(),
                "fileUrl": (file_url or "").strip(),
                "audioUrl": (audio_url or "").strip(),
                "voiceUrl": (voice_url or "").strip(),
                "localPath": str(local_media_path) if local_media_path else "",
                "sticker": sticker_payload,
            },
        },
    )


@cliq_app.command("notify-mail")
def cliq_notify_mail(
    message_id: str = typer.Argument(..., help="Mail message ID to notify."),
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Destination Cliq channel id."
    ),
    user_id: Optional[str] = typer.Option(
        None, "--user-id", help="Destination Cliq user id."
    ),
    folder_id: Optional[str] = typer.Option(
        None, "--folder-id", help="Mail folder id (skip folder scan)."
    ),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
    include_body: bool = typer.Option(
        False, "--include-body", help="Include a short message body snippet."
    ),
) -> None:
    """Send a compact Mail summary into Cliq as a notification message."""
    if bool(channel_id) == bool(user_id):
        utils.error_exit(
            "invalid_destination", "Provide exactly one of channel_id or user_id"
        )

    cfg = _cfg()
    email = _require_account(cfg)

    mail_client, account_id, fid = _mail_message_context(cfg, message_id, folder_id)[1:]
    message = _mail.fetch_message_content(mail_client, account_id, fid, message_id)
    text = _cliq.build_mail_notification_text(message, include_body=include_body)

    cliq_client = _get_cliq_client(cfg, email, network=network)
    resp = cliq_client.send_message(text, channel_id=channel_id, user_id=user_id)

    data = resp.get("data", resp)
    utils.output_status(
        "Cliq mail notification sent",
        extra={
            "messageId": message_id,
            "subject": message.get("subject", ""),
            "result": data,
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# zoho crm …
# ══════════════════════════════════════════════════════════════════════════════


@crm_app.command("status")
def crm_status(
    check_auth: bool = typer.Option(
        False, "--check-auth", help="Verify OAuth refresh for the selected account."
    ),
) -> None:
    """Show CRM scaffold readiness and inferred API endpoint."""
    cfg = _cfg()
    email = _S.account or _config.default_account(cfg)
    account_cfg = cfg.get("accounts", {}).get(email, {}) if email else {}

    payload: dict = {
        "module": "crm",
        "scaffold": "ready",
        "account": email or "",
        "hasAccount": bool(email),
        "hasAccountId": bool(account_cfg.get("accountId")),
        "baseUrl": _crm.infer_crm_base_url(
            mail_base_url=account_cfg.get("mail_base_url"),
            accounts_server=account_cfg.get("accounts_server"),
        ),
        "requiredScopes": _crm.DEFAULT_CRM_SCOPES,
        "grantedScopes": account_cfg.get("scopes", []),
        "next": [
            "implement modules list",
            "implement fields list",
            "implement record get/list/search",
        ],
    }

    payload["missingScopes"] = _crm.missing_crm_scopes(payload.get("grantedScopes", []))
    payload["oauthReady"] = len(payload["missingScopes"]) == 0

    if check_auth and email:
        cid, csec = _require_credentials(cfg)
        token_info = auth.refresh_access_token_info(
            email,
            cid,
            csec,
            accounts_base_url=account_cfg.get("accounts_server"),
        )
        payload["auth"] = "ok"
        live_scopes = token_info.get("scopes", [])
        if live_scopes:
            payload["grantedScopes"] = live_scopes
            payload["missingScopes"] = _crm.missing_crm_scopes(live_scopes)
            payload["oauthReady"] = len(payload["missingScopes"]) == 0

    utils.output(payload)


@crm_app.command("modules")
def crm_modules(
    limit: int = typer.Option(50, "--limit", "-n", help="Max modules to return."),
    page: int = typer.Option(1, "--page", help="Result page number."),
) -> None:
    """List CRM modules (read-only scaffold endpoint)."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_crm_client(cfg, email)

    resp = client.modules(limit=limit, page=page)
    data = resp.get("data", resp)
    utils.output(data)


@crm_app.command("fields")
def crm_fields(
    module: str = typer.Option(
        ..., "--module", "-m", help="CRM module API name (for example Leads)."
    ),
    limit: int = typer.Option(200, "--limit", "-n", help="Max fields to return."),
    page: int = typer.Option(1, "--page", help="Result page number."),
) -> None:
    """List fields for a CRM module."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_crm_client(cfg, email)

    resp = client.fields(module, limit=limit, page=page)
    data = resp.get("data", resp)
    utils.output(data)


@crm_app.command("list")
def crm_list(
    module: str = typer.Option(
        ..., "--module", "-m", help="CRM module API name (for example Leads)."
    ),
    limit: int = typer.Option(50, "--limit", "-n", help="Max records to return."),
    page: int = typer.Option(1, "--page", help="Result page number."),
    fields: List[str] = typer.Option(
        [], "--field", help="Field API name to include (repeatable)."
    ),
) -> None:
    """List records from a CRM module."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_crm_client(cfg, email)

    resp = client.list_records(module, limit=limit, page=page, fields=list(fields))
    data = resp.get("data", resp)
    utils.output(data)


@crm_app.command("get")
def crm_get(
    record_id: str = typer.Argument(..., help="CRM record ID."),
    module: str = typer.Option(
        ..., "--module", "-m", help="CRM module API name (for example Leads)."
    ),
    fields: List[str] = typer.Option(
        [], "--field", help="Field API name to include (repeatable)."
    ),
) -> None:
    """Get a single CRM record by id."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_crm_client(cfg, email)

    resp = client.get_record(module, record_id, fields=list(fields))
    data = resp.get("data", resp)
    if isinstance(data, list) and data:
        utils.output(data[0])
        return
    utils.output(data)


@crm_app.command("search")
def crm_search(
    module: str = typer.Option(
        ..., "--module", "-m", help="CRM module API name (for example Leads)."
    ),
    criteria: Optional[str] = typer.Option(
        None, "--criteria", help="CRM criteria expression."
    ),
    word: Optional[str] = typer.Option(
        None, "--word", help="CRM free-text search term."
    ),
    limit: int = typer.Option(50, "--limit", "-n", help="Max records to return."),
    page: int = typer.Option(1, "--page", help="Result page number."),
) -> None:
    """Search records in a CRM module."""
    if bool(criteria) == bool(word):
        utils.error_exit("invalid_query", "Provide exactly one of --criteria or --word")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_crm_client(cfg, email)

    resp = client.search_records(
        module,
        criteria=criteria,
        word=word,
        limit=limit,
        page=page,
    )
    data = resp.get("data", resp)
    utils.output(data)


# ══════════════════════════════════════════════════════════════════════════════
# zoho config …
# ══════════════════════════════════════════════════════════════════════════════


@config_app.command("show")
def config_show() -> None:
    """Dump the current config as JSON (client_secret redacted)."""
    cfg = dict(_cfg())
    if "client_secret" in cfg:
        cfg["client_secret"] = "***"
    utils.output_json(cfg)


@config_app.command("path")
def config_path_cmd() -> None:
    """Show the config file path."""
    p = _config.config_path(_S.config_path)
    utils.output_json({"config_path": str(p), "exists": p.exists()})


@config_app.command("init")
def config_init() -> None:
    """First-time setup wizard — configure credentials and optionally log in."""
    cfg = _cfg()
    p = _config.config_path(_S.config_path)
    is_first_run = not p.exists()

    # ── header ────────────────────────────────────────────────────────────────
    _stderr("")
    _stderr("══════════════════════════════════════════════════")
    _stderr(
        "  zoho-cli — "
        + ("First-Time Setup" if is_first_run else "Update Configuration")
    )
    _stderr("══════════════════════════════════════════════════")
    _stderr("")

    _stderr("Get your credentials at:  https://api-console.zoho.com/")
    _stderr("")
    _stderr("  1. Click 'Add Client' → 'Server-based Application'")
    _stderr("  2. Add redirect URI:   http://localhost:51821/callback")
    _stderr("  3. Copy the Client ID and Secret from that page.")
    _stderr("")
    if is_first_run:
        _stderr("Press Ctrl+C at any time to abort.")
    else:
        _stderr(f"Config: {p}  (press Enter to keep existing values)")
    _stderr("")

    # ── prompt helpers ────────────────────────────────────────────────────────
    def _required(label: str, **kw) -> str:
        """Keep prompting until the user provides a non-empty value."""
        while True:
            val = click.prompt(label, err=True, **kw).strip()
            if val:
                return val
            _stderr("  (this field is required)")

    def _optional(label: str, current: str, **kw) -> str:
        return click.prompt(label, default=current, err=True, **kw).strip()

    # ── credentials ───────────────────────────────────────────────────────────
    existing_id = cfg.get("client_id", "")
    existing_sec = cfg.get("client_secret", "")

    if existing_id:
        cfg["client_id"] = _optional("Zoho OAuth Client ID", existing_id)
    else:
        cfg["client_id"] = _required("Zoho OAuth Client ID")

    if existing_sec:
        cfg["client_secret"] = _optional(
            "Zoho OAuth Client Secret",
            existing_sec,
            hide_input=True,
            confirmation_prompt=False,
        )
    else:
        cfg["client_secret"] = _required(
            "Zoho OAuth Client Secret",
            hide_input=True,
            confirmation_prompt=False,
        )

    # ── account e-mail ────────────────────────────────────────────────────────
    existing_email = cfg.get("default_account", "")
    if existing_email:
        cfg["default_account"] = _optional("Default account e-mail", existing_email)
    else:
        cfg["default_account"] = _required("Default account e-mail")

    # ── redirect URI (advanced, only shown when updating) ─────────────────────
    if not is_first_run:
        cfg["redirect_uri"] = _optional(
            "Redirect URI (--no-browser mode)",
            cfg.get("redirect_uri", "http://localhost:51821/callback"),
        )

    # ── save ──────────────────────────────────────────────────────────────────
    _config.save(cfg, _S.config_path)
    _stderr("")
    _stderr(f"✓  Config saved → {p}")
    _stderr("")

    # ── offer to log in immediately ───────────────────────────────────────────
    if click.confirm("Log in now via browser OAuth?", default=True, err=True):
        _stderr("")
        login(account=cfg["default_account"], port=51821, no_browser=False)


# ── attachment content subcommand (方案 C) ────────────────────────────────────────
@attachment_subapp.command("content")
def attachment_content(
    message_id: str = typer.Argument(..., help="Message ID."),
    file_name: Optional[str] = typer.Argument(
        None, help="Attachment filename (optional)."
    ),
    folder_id: Optional[str] = typer.Option(None, "--folder-id", help="Folder ID."),
) -> None:
    """Download and display content of an attachment.

    Supported formats: txt, md, json, csv, xlsx, pdf, docx
    """
    cfg = _cfg()
    _, client, account_id, fid = _mail_message_context(cfg, message_id, folder_id)

    # List attachments first to help user identify the right one
    atts = _mail.list_attachments(client, account_id, fid, message_id)

    if not atts:
        utils.error_exit(
            "no_attachments", f"No attachments found for message {message_id}"
        )
    target = _select_attachment_target(atts, message_id, file_name)

    # Download to temp file
    suffix = Path(target.get("fileName") or "").suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
    _download_attachment_to_path(
        client, account_id, fid, message_id, target["attachmentId"], tmp_path
    )

    try:
        content = _parse_attachment_content(tmp_path)
        utils.output(
            {
                "messageId": message_id,
                "attachmentId": target["attachmentId"],
                "fileName": target["fileName"],
                "content": content,
            },
            md_render=_md_parsed_attachment_content,
        )
    finally:
        # Cleanup temp file
        tmp_path.unlink(missing_ok=True)
