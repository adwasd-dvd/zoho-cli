"""zoho CLI — all subcommands.

Output:
- Default → JSON to stdout (pipe-friendly, agent-friendly)
- --md    → Markdown tables/text
- stderr  → errors, debug, interactive prompts (never pollutes stdout)
"""

# ruff: noqa: E402

from __future__ import annotations

from functools import partial
import json
import os
import shlex
import shutil
import subprocess
import sys
import threading
from urllib.parse import urlparse

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
from zoho_cli.commands.root import register_builtin_root_typers
from zoho_cli.crm import ZohoCrmClient
from zoho_cli.registry import register_root_commands


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
membrane_app = typer.Typer(
    no_args_is_help=True,
    help="Membrane bridge operations (experimental).",
)


register_root_commands(
    app,
    registrars=(
        partial(
            register_builtin_root_typers,
            mail_app=mail_app,
            attachment_app=attachment_subapp,
            folders_app=folders_app,
            labels_app=labels_app,
            cliq_app=cliq_app,
            crm_app=crm_app,
            config_app=config_app,
            membrane_app=membrane_app,
        ),
    ),
)

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


def _require_membrane_binary() -> str:
    membrane_bin = shutil.which("membrane")
    if membrane_bin:
        return membrane_bin
    utils.error_exit(
        "membrane_cli_missing",
        "Membrane CLI not found. Install with: npm install -g @membranehq/cli",
    )


def _run_membrane_command(
    args: list[str],
    *,
    expect_json: bool = True,
) -> Any:
    membrane_bin = _require_membrane_binary()
    command = [membrane_bin, *args]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )

    stdout_text = (completed.stdout or "").strip()
    stderr_text = (completed.stderr or "").strip()

    if completed.returncode != 0:
        detail = stderr_text or stdout_text or f"exit code {completed.returncode}"
        utils.error_exit(
            "membrane_command_failed",
            f"{detail} (cmd: {shlex.join(command)})",
        )

    if not expect_json:
        return {
            "status": "ok",
            "command": command,
            "stdout": stdout_text,
            "stderr": stderr_text,
        }

    if not stdout_text:
        return {}

    try:
        return json.loads(stdout_text)
    except json.JSONDecodeError:
        utils.error_exit(
            "membrane_invalid_json",
            f"Membrane output is not valid JSON (cmd: {shlex.join(command)}).",
        )


_MEMBRANE_PRESET_ALIASES: dict[str, str] = {
    "cliq": "zoho-cliq",
    "crm": "zoho-crm",
    "zoho-cliq": "zoho-cliq",
    "zoho-crm": "zoho-crm",
}

_MEMBRANE_PRESET_ENV_VARS: dict[str, str] = {
    "zoho-cliq": "ZOHO_MEMBRANE_CLIQ_CONNECTION_ID",
    "zoho-crm": "ZOHO_MEMBRANE_CRM_CONNECTION_ID",
}


def _normalize_membrane_preset(preset: str) -> str:
    normalized = preset.strip().lower()
    return _MEMBRANE_PRESET_ALIASES.get(normalized, normalized)


def _resolve_membrane_connection_id(
    *,
    connection_id: Optional[str],
    preset: Optional[str],
    cfg: Optional[dict] = None,
    email: Optional[str] = None,
) -> str:
    if connection_id:
        return connection_id.strip()

    if not preset:
        utils.error_exit(
            "missing_connection_id",
            "Provide --connection-id or --preset for membrane bridge calls.",
        )

    normalized_preset = _normalize_membrane_preset(preset)
    env_name = _MEMBRANE_PRESET_ENV_VARS.get(normalized_preset)

    if env_name and os.environ.get(env_name):
        return os.environ[env_name].strip()

    cfg_data = cfg if cfg is not None else _cfg()
    account_email = email or _config.default_account(cfg_data)
    account_cfg = (
        cfg_data.get("accounts", {}).get(account_email, {}) if account_email else {}
    )

    account_map = account_cfg.get("membrane_connections", {})
    if isinstance(account_map, dict):
        value = account_map.get(normalized_preset)
        if isinstance(value, str) and value.strip():
            return value.strip()

    global_map = cfg_data.get("membrane_connections", {})
    if isinstance(global_map, dict):
        value = global_map.get(normalized_preset)
        if isinstance(value, str) and value.strip():
            return value.strip()

    env_hint = env_name or "ZOHO_MEMBRANE_<PRODUCT>_CONNECTION_ID"
    utils.error_exit(
        "missing_membrane_preset_connection",
        (
            f"No membrane connection id found for preset '{normalized_preset}'. "
            "Set --connection-id directly, or configure "
            f"accounts.<email>.membrane_connections.{normalized_preset}, "
            f"membrane_connections.{normalized_preset}, or env {env_hint}."
        ),
    )


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
    with_cliq_export: bool = typer.Option(
        False,
        "--with-cliq-export",
        help="Include Cliq maintenance export OAuth scopes in this login flow.",
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
    redirect_uri: Optional[str] = typer.Option(
        None,
        "--redirect-uri",
        help="Override OAuth redirect URI (useful with --no-browser).",
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
        _cliq.DEFAULT_CLIQ_EXPORT_SCOPES if with_cliq_export else [],
        _crm.DEFAULT_CRM_SCOPES if with_crm else [],
        auth.parse_scope_values(list(scope)),
    )

    if no_browser:
        # ── manual flow (headless / remote) ────────────────────────────────
        # Detect region first.
        forced_accounts_url = _config.infer_accounts_server(cfg)
        if not forced_accounts_url:
            _stderr("Auto-detecting your Zoho region…")
            forced_accounts_url = auth.discover_accounts_server(client_id)
            _stderr(f"Detected: {forced_accounts_url}")
        os.environ["ZOHO_ACCOUNTS_BASE_URL"] = forced_accounts_url

        configured_redirect = str(cfg.get("redirect_uri") or "").strip()
        manual_override = (redirect_uri or "").strip()
        localhost_redirect = f"http://localhost:{port}/callback"
        legacy_redirect = "https://example.com/zoho/oauth/callback"

        if manual_override:
            redirect_uri = manual_override
        elif configured_redirect:
            if configured_redirect == legacy_redirect:
                # Legacy default from early bootstrap should not leak into
                # no-browser auth URLs when user didn't explicitly set it.
                redirect_uri = localhost_redirect
            else:
                redirect_uri = configured_redirect
        else:
            # Unset redirect in no-browser mode must default to localhost.
            redirect_uri = localhost_redirect

        callback_server = None
        callback_result: dict[str, Any] | None = None
        callback_thread: threading.Thread | None = None

        parsed_redirect = urlparse(redirect_uri)
        is_local_callback = parsed_redirect.hostname in {"localhost", "127.0.0.1"}
        if is_local_callback:
            preferred_port = parsed_redirect.port or port
            callback_server, redirect_uri, callback_result = (
                auth.create_callback_server(
                    preferred_port,
                    requested_scopes=scopes,
                )
            )
            callback_thread = threading.Thread(
                target=callback_server.serve_forever,
                kwargs={"poll_interval": 0.2},
                daemon=True,
            )
            callback_thread.start()

        auth_url = auth.build_auth_url(client_id, redirect_uri, scopes)

        _stderr("\n── Zoho OAuth Login (manual) ──────────────────────────────")
        _stderr("1. Open this URL in your browser:\n")
        _stderr(f"   {auth_url}\n")
        _stderr("2. Approve access.")
        _stderr("3. Copy the full redirect URL (or just the code) and paste it below.")
        if is_local_callback:
            _stderr("4. If localhost shows Connected, you can just press Enter below.")
        _stderr("────────────────────────────────────────────────────────────\n")
        prompt_label = "Paste the full redirect URL here"
        if is_local_callback:
            prompt_label += " (or press Enter)"

        try:
            if is_local_callback:
                raw_url = click.prompt(
                    prompt_label,
                    default="",
                    show_default=False,
                    err=True,
                ).strip()
            else:
                raw_url = click.prompt(prompt_label, err=True).strip()

            if raw_url:
                parsed_redirect_uri = auth.extract_redirect_uri(raw_url)
                if parsed_redirect_uri:
                    redirect_uri = parsed_redirect_uri
                code, accounts_server = auth.parse_redirect(raw_url)
            elif callback_result and callback_result.get("code"):
                code = str(callback_result["code"])
                accounts_server = callback_result.get("accounts_server")
            else:
                utils.error_exit(
                    "oauth_missing_redirect",
                    "No redirect URL pasted and no localhost callback was captured. "
                    "Re-run login and paste the full redirect URL (or use browser mode).",
                )
        finally:
            if callback_server:
                callback_server.shutdown()
                callback_server.server_close()
            if callback_thread:
                callback_thread.join(timeout=1)
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


@membrane_app.command("doctor")
def membrane_doctor() -> None:
    """Check membrane CLI availability/version for bridge mode."""
    membrane_bin = _require_membrane_binary()
    result = _run_membrane_command(["--version"], expect_json=False)
    utils.output(
        {
            "status": "ok",
            "bin": membrane_bin,
            "version": result.get("stdout") or "unknown",
        }
    )


@membrane_app.command("discover")
def membrane_discover(
    connector: str = typer.Option(
        ...,
        "--connector",
        help="Connector slug to discover (for example: zoho-cliq, zoho-crm).",
    ),
) -> None:
    """Discover connector IDs from Membrane registry."""
    payload = _run_membrane_command(
        ["search", connector, "--elementType=connector", "--json"]
    )
    utils.output(payload)


@membrane_app.command("connections")
def membrane_connections() -> None:
    """List existing Membrane connections."""
    payload = _run_membrane_command(["connection", "list", "--json"])
    utils.output(payload)


@membrane_app.command("actions")
def membrane_actions(
    connection_id: Optional[str] = typer.Option(
        None,
        "--connection-id",
        help="Membrane connection ID.",
    ),
    preset: Optional[str] = typer.Option(
        None,
        "--preset",
        help="Connection preset alias (for example: zoho-cliq, zoho-crm).",
    ),
    intent: str = typer.Option(
        "QUERY",
        "--intent",
        help="Intent hint for action discovery.",
    ),
) -> None:
    """List available actions for a Membrane connection."""
    cfg = _cfg()
    email = _S.account or _config.default_account(cfg)
    resolved_connection_id = _resolve_membrane_connection_id(
        connection_id=connection_id,
        preset=preset,
        cfg=cfg,
        email=email,
    )

    payload = _run_membrane_command(
        [
            "action",
            "list",
            f"--intent={intent}",
            f"--connectionId={resolved_connection_id}",
            "--json",
        ]
    )
    utils.output(payload)


@membrane_app.command("run")
def membrane_run(
    action_id: str = typer.Argument(..., help="Action ID to execute."),
    connection_id: Optional[str] = typer.Option(
        None,
        "--connection-id",
        help="Membrane connection ID.",
    ),
    preset: Optional[str] = typer.Option(
        None,
        "--preset",
        help="Connection preset alias (for example: zoho-cliq, zoho-crm).",
    ),
    input_json: Optional[str] = typer.Option(
        None,
        "--input-json",
        help="JSON string passed to --input.",
    ),
) -> None:
    """Run one Membrane action and return raw JSON response."""
    cfg = _cfg()
    email = _S.account or _config.default_account(cfg)
    resolved_connection_id = _resolve_membrane_connection_id(
        connection_id=connection_id,
        preset=preset,
        cfg=cfg,
        email=email,
    )

    command: list[str] = [
        "action",
        "run",
        f"--connectionId={resolved_connection_id}",
        action_id,
        "--json",
    ]

    if input_json is not None:
        try:
            json.loads(input_json)
        except json.JSONDecodeError:
            utils.error_exit(
                "invalid_input_json",
                "--input-json must be a valid JSON object/string.",
            )
        command.extend(["--input", input_json])

    payload = _run_membrane_command(command)
    utils.output(payload)


@membrane_app.command("raw")
def membrane_raw(
    args: List[str] = typer.Argument(
        ...,
        help="Arguments forwarded to membrane CLI exactly as provided.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json-output",
        help="Parse stdout as JSON and emit structured JSON.",
    ),
) -> None:
    """Pass through arbitrary membrane CLI arguments."""
    payload = _run_membrane_command(args, expect_json=json_output)
    utils.output(payload)


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
    resolved_network = network or account_cfg.get("cliq_network")

    def _cmd(*args: str, include_network: bool = False) -> str:
        parts: list[str] = ["zoho"]
        if _S.config_path:
            parts.extend(["--config", _S.config_path])
        if email:
            parts.extend(["--account", email])
        parts.extend(args)
        if include_network and resolved_network:
            parts.extend(["--network", str(resolved_network)])
        return "`" + " ".join(shlex.quote(p) for p in parts) + "`"

    def _export_next() -> list[str]:
        bundled_login = _cmd("login", "--with-cliq", "--with-cliq-export")
        explicit_scope_login = _cmd(
            "login",
            "--with-cliq",
            "--scope",
            _cliq.CLIQ_EXPORT_CHATS_SCOPE,
            "--scope",
            _cliq.CLIQ_EXPORT_MESSAGES_SCOPE,
        )
        return [
            f"re-auth with Cliq export scopes: {bundled_login} (fallback: {explicit_scope_login})",
            f"verify export scope readiness: {_cmd('cliq', 'status', '--check-auth', include_network=True)}",
            f"rerun export probes: {_cmd('cliq', 'export-chats', include_network=True)} and {_cmd('cliq', 'export-chats', '--chat-id', '<chat_id>', include_network=True)}",
        ]

    payload: dict = {
        "module": "cliq",
        "scaffold": "ready",
        "account": email or "",
        "hasAccount": bool(email),
        "hasAccountId": bool(account_cfg.get("accountId")),
        "baseUrl": _cliq.infer_cliq_base_url(
            mail_base_url=account_cfg.get("mail_base_url"),
            accounts_server=account_cfg.get("accounts_server"),
            network=resolved_network,
        ),
        "requiredScopes": _cliq.DEFAULT_CLIQ_SCOPES,
        "requiredExportScopes": _cliq.DEFAULT_CLIQ_EXPORT_SCOPES,
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
    payload["missingExportScopes"] = _cliq.missing_cliq_export_scopes(
        payload.get("grantedScopes", [])
    )
    payload["exportOauthReady"] = len(payload["missingExportScopes"]) == 0
    if not payload["exportOauthReady"]:
        payload["exportNext"] = _export_next()

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
            payload["missingExportScopes"] = _cliq.missing_cliq_export_scopes(
                live_scopes
            )
            payload["exportOauthReady"] = len(payload["missingExportScopes"]) == 0
            if payload["exportOauthReady"]:
                payload.pop("exportNext", None)
            else:
                payload["exportNext"] = _export_next()

    utils.output(payload)


@cliq_app.command("bridge-run")
def cliq_bridge_run(
    action_id: str = typer.Argument(
        ..., help="Membrane action id (for example: post-message)."
    ),
    bridge: str = typer.Option(
        "membrane",
        "--bridge",
        help="Bridge backend. Currently only 'membrane' is supported.",
    ),
    connection_id: Optional[str] = typer.Option(
        None,
        "--connection-id",
        help="Membrane connection ID. Overrides preset lookup when provided.",
    ),
    preset: Optional[str] = typer.Option(
        "zoho-cliq",
        "--preset",
        help="Connection preset alias (default: zoho-cliq).",
    ),
    input_json: Optional[str] = typer.Option(
        None,
        "--input-json",
        help="JSON string passed to membrane --input.",
    ),
) -> None:
    """Run one Cliq action through membrane bridge (explicit opt-in)."""
    if bridge.strip().lower() != "membrane":
        utils.error_exit(
            "unsupported_bridge",
            "Only --bridge membrane is supported right now.",
        )

    cfg = _cfg()
    email = _S.account or _config.default_account(cfg)
    resolved_connection_id = _resolve_membrane_connection_id(
        connection_id=connection_id,
        preset=preset,
        cfg=cfg,
        email=email,
    )

    command: list[str] = [
        "action",
        "run",
        f"--connectionId={resolved_connection_id}",
        action_id,
        "--json",
    ]

    if input_json is not None:
        try:
            json.loads(input_json)
        except json.JSONDecodeError:
            utils.error_exit(
                "invalid_input_json",
                "--input-json must be a valid JSON object/string.",
            )
        command.extend(["--input", input_json])

    result = _run_membrane_command(command)
    utils.output(
        {
            "bridge": "membrane",
            "preset": _normalize_membrane_preset(preset or "zoho-cliq"),
            "connectionId": resolved_connection_id,
            "actionId": action_id,
            "result": result,
        }
    )


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


@cliq_app.command("teams")
def cliq_teams(
    limit: int = typer.Option(50, "--limit", "-n", help="Max teams to return."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List Cliq org-admin teams (cliq-190 phase-1 slice)."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resp = client.list_teams(limit=limit)
    data = resp.get("data", resp)
    if not isinstance(data, list):
        data = []

    views: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        views.append(
            {
                "teamId": str(
                    row.get("team_id")
                    or row.get("teamId")
                    or row.get("id")
                    or row.get("zuid")
                    or ""
                ),
                "name": str(
                    row.get("name")
                    or row.get("team_name")
                    or row.get("display_name")
                    or ""
                ),
                "raw": row,
            }
        )

    utils.output(
        {
            "count": len(views),
            "teams": views,
        }
    )


@cliq_app.command("departments")
def cliq_departments(
    limit: int = typer.Option(50, "--limit", "-n", help="Max departments to return."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List Cliq org-admin departments (cliq-190 phase-1 slice)."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resp = client.list_departments(limit=limit)
    data = resp.get("data", resp)
    if not isinstance(data, list):
        data = []

    views: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        views.append(
            {
                "departmentId": str(
                    row.get("department_id")
                    or row.get("departmentId")
                    or row.get("id")
                    or row.get("zuid")
                    or ""
                ),
                "name": str(
                    row.get("name")
                    or row.get("department_name")
                    or row.get("display_name")
                    or ""
                ),
                "raw": row,
            }
        )

    utils.output(
        {
            "count": len(views),
            "departments": views,
        }
    )


@cliq_app.command("roles")
def cliq_roles(
    limit: int = typer.Option(50, "--limit", "-n", help="Max roles to return."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List Cliq org-admin roles (cliq-190 phase-1 slice)."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resp = client.list_roles(limit=limit)
    data = resp.get("data", resp)
    if not isinstance(data, list):
        data = []

    views: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        views.append(
            {
                "roleId": str(
                    row.get("role_id")
                    or row.get("roleId")
                    or row.get("id")
                    or row.get("zuid")
                    or ""
                ),
                "name": str(
                    row.get("name")
                    or row.get("role_name")
                    or row.get("display_name")
                    or ""
                ),
                "raw": row,
            }
        )

    utils.output(
        {
            "count": len(views),
            "roles": views,
        }
    )


@cliq_app.command("designations")
def cliq_designations(
    limit: int = typer.Option(50, "--limit", "-n", help="Max designations to return."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List Cliq org-admin designations (cliq-190 phase-1 slice)."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resp = client.list_designations(limit=limit)
    data = resp.get("data", resp)
    if not isinstance(data, list):
        data = []

    views: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        views.append(
            {
                "designationId": str(
                    row.get("designation_id")
                    or row.get("designationId")
                    or row.get("id")
                    or row.get("zuid")
                    or ""
                ),
                "name": str(
                    row.get("name")
                    or row.get("designation_name")
                    or row.get("display_name")
                    or ""
                ),
                "raw": row,
            }
        )

    utils.output(
        {
            "count": len(views),
            "designations": views,
        }
    )


@cliq_app.command("user-status")
def cliq_user_status(
    limit: int = typer.Option(
        50, "--limit", "-n", help="Max user-status rows to return."
    ),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List Cliq org-admin user-status values (cliq-190 phase-1 slice)."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resp = client.list_user_statuses(limit=limit)
    data = resp.get("data", resp)
    if not isinstance(data, list):
        data = []

    views: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        views.append(
            {
                "statusId": str(
                    row.get("status_id")
                    or row.get("statusId")
                    or row.get("id")
                    or row.get("zuid")
                    or ""
                ),
                "name": str(
                    row.get("name")
                    or row.get("status")
                    or row.get("label")
                    or row.get("display_name")
                    or ""
                ),
                "raw": row,
            }
        )

    utils.output(
        {
            "count": len(views),
            "statuses": views,
        }
    )


@cliq_app.command("userfields")
def cliq_userfields(
    limit: int = typer.Option(
        50, "--limit", "-n", help="Max user-field rows to return."
    ),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List Cliq org-admin userfields (cliq-190 phase-1 slice)."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resp = client.list_user_fields(limit=limit)
    data = resp.get("data", resp)
    if not isinstance(data, list):
        data = []

    views: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        views.append(
            {
                "fieldId": str(
                    row.get("field_id")
                    or row.get("fieldId")
                    or row.get("id")
                    or row.get("zuid")
                    or ""
                ),
                "label": str(
                    row.get("label")
                    or row.get("field_name")
                    or row.get("display_name")
                    or row.get("name")
                    or ""
                ),
                "type": str(
                    row.get("field_type")
                    or row.get("type")
                    or row.get("data_type")
                    or ""
                ),
                "raw": row,
            }
        )

    utils.output(
        {
            "count": len(views),
            "userFields": views,
        }
    )


@cliq_app.command("events")
def cliq_events(
    limit: int = typer.Option(50, "--limit", "-n", help="Max events to return."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List Cliq collaboration events (cliq-191 first slice)."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resp = client.list_events(limit=limit)
    data = resp.get("data", resp)
    if not isinstance(data, list):
        data = []

    views: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        views.append(
            {
                "eventId": str(
                    row.get("event_id")
                    or row.get("eventId")
                    or row.get("id")
                    or row.get("zuid")
                    or ""
                ),
                "title": str(
                    row.get("title")
                    or row.get("name")
                    or row.get("event_name")
                    or row.get("summary")
                    or ""
                ),
                "startsAt": str(
                    row.get("start_time")
                    or row.get("startTime")
                    or row.get("starts_at")
                    or row.get("startsAt")
                    or ""
                ),
                "endsAt": str(
                    row.get("end_time")
                    or row.get("endTime")
                    or row.get("ends_at")
                    or row.get("endsAt")
                    or ""
                ),
                "status": str(row.get("status") or row.get("event_status") or ""),
                "raw": row,
            }
        )

    utils.output(
        {
            "count": len(views),
            "events": views,
        }
    )


@cliq_app.command("reminders")
def cliq_reminders(
    limit: int = typer.Option(50, "--limit", "-n", help="Max reminders to return."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List Cliq collaboration reminders (cliq-191 second slice)."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resp = client.list_reminders(limit=limit)
    data = resp.get("data", resp)
    if not isinstance(data, list):
        data = []

    views: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        views.append(
            {
                "reminderId": str(
                    row.get("reminder_id")
                    or row.get("reminderId")
                    or row.get("id")
                    or row.get("zuid")
                    or ""
                ),
                "title": str(
                    row.get("title")
                    or row.get("name")
                    or row.get("message")
                    or row.get("summary")
                    or ""
                ),
                "dueAt": str(
                    row.get("remind_at")
                    or row.get("remindAt")
                    or row.get("due_at")
                    or row.get("dueAt")
                    or row.get("scheduled_time")
                    or row.get("scheduledTime")
                    or ""
                ),
                "status": str(row.get("status") or row.get("reminder_status") or ""),
                "raw": row,
            }
        )

    utils.output(
        {
            "count": len(views),
            "reminders": views,
        }
    )


@cliq_app.command("meetings")
def cliq_meetings(
    limit: int = typer.Option(50, "--limit", "-n", help="Max meetings to return."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List Cliq collaboration calls/meetings (cliq-191 third slice)."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resp = client.list_meetings(limit=limit)
    data = resp.get("data", resp)
    if not isinstance(data, list):
        data = []

    views: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        views.append(
            {
                "meetingId": str(
                    row.get("meeting_id")
                    or row.get("meetingId")
                    or row.get("call_id")
                    or row.get("callId")
                    or row.get("id")
                    or row.get("zuid")
                    or ""
                ),
                "title": str(
                    row.get("title")
                    or row.get("name")
                    or row.get("subject")
                    or row.get("meeting_title")
                    or row.get("call_title")
                    or row.get("summary")
                    or ""
                ),
                "startsAt": str(
                    row.get("start_time")
                    or row.get("startTime")
                    or row.get("starts_at")
                    or row.get("startsAt")
                    or row.get("scheduled_time")
                    or row.get("scheduledTime")
                    or ""
                ),
                "endsAt": str(
                    row.get("end_time")
                    or row.get("endTime")
                    or row.get("ends_at")
                    or row.get("endsAt")
                    or ""
                ),
                "status": str(
                    row.get("status")
                    or row.get("meeting_status")
                    or row.get("call_status")
                    or ""
                ),
                "raw": row,
            }
        )

    utils.output(
        {
            "count": len(views),
            "meetings": views,
        }
    )


@cliq_app.command("databases")
def cliq_databases(
    limit: int = typer.Option(50, "--limit", "-n", help="Max databases to return."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List Cliq platform-extension databases (cliq-192 first slice)."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resp = client.list_databases(limit=limit)
    data = resp.get("data", resp)
    if not isinstance(data, list):
        data = []

    views: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        views.append(
            {
                "databaseId": str(
                    row.get("database_id")
                    or row.get("databaseId")
                    or row.get("id")
                    or row.get("zuid")
                    or ""
                ),
                "name": str(
                    row.get("name")
                    or row.get("database_name")
                    or row.get("title")
                    or row.get("display_name")
                    or ""
                ),
                "type": str(
                    row.get("database_type")
                    or row.get("type")
                    or row.get("category")
                    or ""
                ),
                "raw": row,
            }
        )

    utils.output(
        {
            "count": len(views),
            "databases": views,
        }
    )


@cliq_app.command("widgets")
def cliq_widgets(
    limit: int = typer.Option(50, "--limit", "-n", help="Max widgets to return."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List Cliq platform-extension widgets (cliq-192 second slice)."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resp = client.list_widgets(limit=limit)
    data = resp.get("data", resp)
    if not isinstance(data, list):
        data = []

    views: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        views.append(
            {
                "widgetId": str(
                    row.get("widget_id")
                    or row.get("widgetId")
                    or row.get("id")
                    or row.get("zuid")
                    or ""
                ),
                "name": str(
                    row.get("name")
                    or row.get("widget_name")
                    or row.get("title")
                    or row.get("display_name")
                    or ""
                ),
                "type": str(
                    row.get("widget_type")
                    or row.get("type")
                    or row.get("category")
                    or ""
                ),
                "status": str(
                    row.get("status")
                    or row.get("state")
                    or row.get("widget_status")
                    or ""
                ),
                "raw": row,
            }
        )

    utils.output(
        {
            "count": len(views),
            "widgets": views,
        }
    )


@cliq_app.command("map-tickers")
def cliq_map_tickers(
    limit: int = typer.Option(50, "--limit", "-n", help="Max map tickers to return."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List Cliq platform map tickers (cliq-192 third slice)."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resp = client.list_map_tickers(limit=limit)
    data = resp.get("data", resp)
    if not isinstance(data, list):
        data = []

    views: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        views.append(
            {
                "tickerId": str(
                    row.get("ticker_id")
                    or row.get("tickerId")
                    or row.get("id")
                    or row.get("zuid")
                    or ""
                ),
                "name": str(
                    row.get("name")
                    or row.get("ticker_name")
                    or row.get("title")
                    or row.get("display_name")
                    or ""
                ),
                "symbol": str(
                    row.get("symbol")
                    or row.get("ticker_symbol")
                    or row.get("code")
                    or ""
                ),
                "status": str(
                    row.get("status")
                    or row.get("state")
                    or row.get("ticker_status")
                    or ""
                ),
                "raw": row,
            }
        )

    utils.output(
        {
            "count": len(views),
            "mapTickers": views,
        }
    )


@cliq_app.command("custom-domains")
def cliq_custom_domains(
    limit: int = typer.Option(
        50, "--limit", "-n", help="Max custom domains to return."
    ),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List Cliq platform custom domains (cliq-192 fourth slice)."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resp = client.list_custom_domains(limit=limit)
    data = resp.get("data", resp)
    if not isinstance(data, list):
        data = []

    views: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        views.append(
            {
                "domainId": str(
                    row.get("domain_id")
                    or row.get("domainId")
                    or row.get("id")
                    or row.get("zuid")
                    or ""
                ),
                "domain": str(
                    row.get("domain")
                    or row.get("name")
                    or row.get("custom_domain")
                    or ""
                ),
                "status": str(
                    row.get("status")
                    or row.get("state")
                    or row.get("domain_status")
                    or ""
                ),
                "raw": row,
            }
        )

    utils.output(
        {
            "count": len(views),
            "customDomains": views,
        }
    )


@cliq_app.command("custom-emails")
def cliq_custom_emails(
    limit: int = typer.Option(50, "--limit", "-n", help="Max custom emails to return."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List Cliq platform custom emails (cliq-192 fifth slice)."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resp = client.list_custom_emails(limit=limit)
    data = resp.get("data", resp)
    if not isinstance(data, list):
        data = []

    views: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        views.append(
            {
                "emailId": str(
                    row.get("email_id")
                    or row.get("emailId")
                    or row.get("id")
                    or row.get("zuid")
                    or ""
                ),
                "email": str(
                    row.get("email")
                    or row.get("address")
                    or row.get("custom_email")
                    or ""
                ),
                "status": str(
                    row.get("status")
                    or row.get("state")
                    or row.get("email_status")
                    or ""
                ),
                "raw": row,
            }
        )

    utils.output(
        {
            "count": len(views),
            "customEmails": views,
        }
    )


@cliq_app.command("apps")
def cliq_apps(
    limit: int = typer.Option(50, "--limit", "-n", help="Max apps to return."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List Cliq app-governance apps (cliq-193 first slice)."""

    def _unwrap_app_row(row: dict[str, Any]) -> dict[str, Any]:
        current = row
        for _ in range(16):
            for key in (
                "app",
                "apps",
                "item",
                "record",
                "records",
                "data",
                "response",
                "result",
                "payload",
            ):
                nested = current.get(key)
                if isinstance(nested, dict):
                    current = nested
                    break
            else:
                break
        return current

    def _extract_app_rows(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [_unwrap_app_row(row) for row in payload if isinstance(row, dict)]

        if not isinstance(payload, dict):
            return []

        for key in ("app", "item", "record"):
            candidate = payload.get(key)
            if isinstance(candidate, dict):
                return [_unwrap_app_row(candidate)]
            if isinstance(candidate, list):
                return [
                    _unwrap_app_row(row) for row in candidate if isinstance(row, dict)
                ]

        candidates: list[Any] = [
            payload.get("response"),
            payload.get("result"),
            payload.get("payload"),
            payload.get("data"),
            payload.get("apps"),
            payload.get("list"),
            payload.get("items"),
            payload.get("results"),
            payload.get("records"),
        ]
        nested_data = payload.get("data")
        if isinstance(nested_data, dict):
            candidates.extend(
                [
                    nested_data.get("apps"),
                    nested_data.get("list"),
                    nested_data.get("items"),
                    nested_data.get("results"),
                    nested_data.get("records"),
                    nested_data.get("data"),
                    nested_data.get("response"),
                    nested_data.get("result"),
                    nested_data.get("payload"),
                ]
            )

        for candidate in candidates:
            if isinstance(candidate, list):
                return [
                    _unwrap_app_row(row) for row in candidate if isinstance(row, dict)
                ]

            if isinstance(candidate, dict):
                nested_app = (
                    candidate.get("app")
                    or candidate.get("item")
                    or candidate.get("record")
                )
                if isinstance(nested_app, dict):
                    return [_unwrap_app_row(nested_app)]

                nested_records = candidate.get("records")
                if isinstance(nested_records, list):
                    return [
                        _unwrap_app_row(row)
                        for row in nested_records
                        if isinstance(row, dict)
                    ]
                if isinstance(nested_records, dict):
                    nested_record = (
                        nested_records.get("record")
                        or nested_records.get("item")
                        or nested_records.get("app")
                    )
                    if isinstance(nested_record, dict):
                        return [_unwrap_app_row(nested_record)]

                for key in (
                    "response",
                    "result",
                    "payload",
                    "data",
                    "apps",
                    "list",
                    "items",
                    "results",
                    "records",
                    "record",
                    "item",
                ):
                    nested_candidate = candidate.get(key)
                    if nested_candidate is None:
                        continue
                    nested_rows = _extract_app_rows(nested_candidate)
                    if nested_rows:
                        return nested_rows

                if any(
                    key in candidate
                    for key in (
                        "app_id",
                        "appId",
                        "id",
                        "zuid",
                        "name",
                        "app_name",
                        "title",
                        "status",
                        "state",
                        "app_status",
                    )
                ):
                    return [_unwrap_app_row(candidate)]

        if any(
            key in payload
            for key in (
                "app_id",
                "appId",
                "id",
                "zuid",
                "name",
                "app_name",
                "title",
            )
        ):
            return [_unwrap_app_row(payload)]

        return []

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resp = client.list_apps(limit=limit)
    data = _extract_app_rows(resp)

    views: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        views.append(
            {
                "appId": str(
                    row.get("app_id")
                    or row.get("appId")
                    or row.get("id")
                    or row.get("zuid")
                    or ""
                ),
                "name": str(
                    row.get("name") or row.get("app_name") or row.get("title") or ""
                ),
                "status": str(
                    row.get("status") or row.get("state") or row.get("app_status") or ""
                ),
                "raw": row,
            }
        )

    utils.output(
        {
            "count": len(views),
            "apps": views,
        }
    )


@cliq_app.command("app-get")
def cliq_app_get(
    app_id: str = typer.Argument(..., help="Cliq app id."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Get one Cliq app-governance app by id (cliq-193 second slice)."""

    def _unwrap_app_row(row: dict[str, Any]) -> dict[str, Any]:
        current = row
        for _ in range(16):
            for key in (
                "app",
                "apps",
                "item",
                "record",
                "records",
                "data",
                "response",
                "result",
                "payload",
            ):
                nested = current.get(key)
                if isinstance(nested, dict):
                    current = nested
                    break
                if isinstance(nested, list):
                    picked = next(
                        (entry for entry in nested if isinstance(entry, dict)),
                        None,
                    )
                    if picked:
                        current = picked
                        break
            else:
                break
        return current

    def _extract_app_row(payload: Any) -> dict[str, Any]:
        if isinstance(payload, list):
            picked = next((row for row in payload if isinstance(row, dict)), None)
            return _unwrap_app_row(picked) if picked else {}

        if not isinstance(payload, dict):
            return {}

        for key in ("app", "item", "record", "response", "result", "payload"):
            candidate = payload.get(key)
            if isinstance(candidate, dict):
                return _unwrap_app_row(candidate)
            if isinstance(candidate, list):
                picked = next((row for row in candidate if isinstance(row, dict)), None)
                if picked:
                    return _unwrap_app_row(picked)

        for key in (
            "apps",
            "list",
            "items",
            "results",
            "records",
            "response",
            "result",
            "payload",
        ):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                picked = next((row for row in candidate if isinstance(row, dict)), None)
                if picked:
                    return _unwrap_app_row(picked)
            if isinstance(candidate, dict):
                nested_candidate = (
                    candidate.get("app")
                    or candidate.get("item")
                    or candidate.get("record")
                    or candidate.get("response")
                    or candidate.get("result")
                    or candidate.get("payload")
                )
                if isinstance(nested_candidate, dict):
                    return _unwrap_app_row(nested_candidate)
                if isinstance(nested_candidate, list):
                    picked = next(
                        (row for row in nested_candidate if isinstance(row, dict)),
                        None,
                    )
                    if picked:
                        return _unwrap_app_row(picked)
                if any(
                    app_key in candidate
                    for app_key in (
                        "app_id",
                        "appId",
                        "id",
                        "zuid",
                        "name",
                        "app_name",
                        "status",
                        "state",
                        "app_status",
                    )
                ):
                    return _unwrap_app_row(candidate)

        nested_data = payload.get("data")
        if isinstance(nested_data, dict):
            for key in (
                "app",
                "item",
                "record",
                "response",
                "result",
                "payload",
            ):
                candidate = nested_data.get(key)
                if isinstance(candidate, dict):
                    return _unwrap_app_row(candidate)
                if isinstance(candidate, list):
                    picked = next(
                        (row for row in candidate if isinstance(row, dict)),
                        None,
                    )
                    if picked:
                        return _unwrap_app_row(picked)
            for key in (
                "apps",
                "list",
                "items",
                "results",
                "records",
                "data",
                "response",
                "result",
                "payload",
            ):
                candidate = nested_data.get(key)
                if isinstance(candidate, list):
                    picked = next(
                        (row for row in candidate if isinstance(row, dict)),
                        None,
                    )
                    if picked:
                        return _unwrap_app_row(picked)
                if isinstance(candidate, dict):
                    return _unwrap_app_row(candidate)
            if any(
                key in nested_data
                for key in (
                    "app_id",
                    "appId",
                    "id",
                    "zuid",
                    "name",
                    "app_name",
                    "status",
                    "state",
                    "app_status",
                )
            ):
                return _unwrap_app_row(nested_data)

        if any(
            key in payload
            for key in (
                "app_id",
                "appId",
                "id",
                "zuid",
                "name",
                "app_name",
                "status",
                "state",
                "app_status",
            )
        ):
            return _unwrap_app_row(payload)

        return {}

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_app_id = app_id.strip()
    resp = client.get_app(resolved_app_id)
    app_row = _extract_app_row(resp)

    view = {
        "appId": str(
            app_row.get("app_id")
            or app_row.get("appId")
            or app_row.get("id")
            or app_row.get("zuid")
            or resolved_app_id
        ),
        "name": str(app_row.get("name") or app_row.get("app_name") or ""),
        "status": str(
            app_row.get("status")
            or app_row.get("state")
            or app_row.get("app_status")
            or ""
        ),
        "raw": app_row,
    }

    utils.output(
        {
            "app": view,
        }
    )


@cliq_app.command("app-permissions")
def cliq_app_permissions(
    app_id: str = typer.Argument(..., help="Cliq app id."),
    limit: int = typer.Option(
        50,
        "--limit",
        "-n",
        help="Max app permissions to return.",
    ),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List one app's governance permissions/scopes (cliq-193 third slice)."""

    def _unwrap_permission_row(row: dict[str, Any]) -> dict[str, Any]:
        current = row
        for _ in range(16):
            for key in (
                "response",
                "result",
                "payload",
                "permission",
                "scope",
                "item",
                "record",
                "permissions",
                "records",
                "scopes",
                "data",
            ):
                nested = current.get(key)
                if isinstance(nested, list):
                    nested = next(
                        (entry for entry in nested if isinstance(entry, dict)),
                        None,
                    )
                if isinstance(nested, dict):
                    current = nested
                    break
            else:
                break
        return current

    def _extract_permission_rows(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [
                _unwrap_permission_row(row) for row in payload if isinstance(row, dict)
            ]

        if not isinstance(payload, dict):
            return []

        for key in ("permission", "scope", "item", "record"):
            candidate = payload.get(key)
            if isinstance(candidate, dict):
                return [_unwrap_permission_row(candidate)]
            if isinstance(candidate, list):
                return [
                    _unwrap_permission_row(row)
                    for row in candidate
                    if isinstance(row, dict)
                ]

        candidates: list[Any] = [
            payload.get("data"),
            payload.get("permissions"),
            payload.get("scopes"),
            payload.get("list"),
            payload.get("items"),
            payload.get("results"),
            payload.get("records"),
            payload.get("response"),
            payload.get("result"),
            payload.get("payload"),
        ]
        nested_data = payload.get("data")
        if isinstance(nested_data, dict):
            candidates.extend(
                [
                    nested_data.get("permissions"),
                    nested_data.get("scopes"),
                    nested_data.get("list"),
                    nested_data.get("items"),
                    nested_data.get("results"),
                    nested_data.get("records"),
                    nested_data.get("data"),
                    nested_data.get("response"),
                    nested_data.get("result"),
                    nested_data.get("payload"),
                ]
            )

        for candidate in candidates:
            if isinstance(candidate, list):
                return [
                    _unwrap_permission_row(row)
                    for row in candidate
                    if isinstance(row, dict)
                ]

            if isinstance(candidate, dict):
                nested_permission = (
                    candidate.get("permission")
                    or candidate.get("scope")
                    or candidate.get("item")
                    or candidate.get("record")
                )
                if isinstance(nested_permission, dict):
                    return [_unwrap_permission_row(nested_permission)]
                if isinstance(nested_permission, list):
                    return [
                        _unwrap_permission_row(row)
                        for row in nested_permission
                        if isinstance(row, dict)
                    ]

                nested_records = candidate.get("records")
                if isinstance(nested_records, list):
                    return [
                        _unwrap_permission_row(row)
                        for row in nested_records
                        if isinstance(row, dict)
                    ]
                if isinstance(nested_records, dict):
                    nested_record = (
                        nested_records.get("record")
                        or nested_records.get("item")
                        or nested_records.get("permission")
                    )
                    if isinstance(nested_record, dict):
                        return [_unwrap_permission_row(nested_record)]
                    if isinstance(nested_record, list):
                        return [
                            _unwrap_permission_row(row)
                            for row in nested_record
                            if isinstance(row, dict)
                        ]

                unwrapped_candidate = _unwrap_permission_row(candidate)
                if any(
                    key in unwrapped_candidate
                    for key in (
                        "permission_id",
                        "permissionId",
                        "id",
                        "zuid",
                        "scope",
                        "permission",
                        "name",
                        "value",
                        "status",
                        "state",
                        "mode",
                    )
                ):
                    return [unwrapped_candidate]

        if any(
            key in payload
            for key in (
                "permission_id",
                "permissionId",
                "id",
                "zuid",
                "scope",
                "permission",
                "name",
                "value",
            )
        ):
            return [_unwrap_permission_row(payload)]

        return []

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_app_id = app_id.strip()
    resp = client.list_app_permissions(resolved_app_id, limit=limit)
    rows = _extract_permission_rows(resp)

    views: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        views.append(
            {
                "permissionId": str(
                    row.get("permission_id")
                    or row.get("permissionId")
                    or row.get("id")
                    or row.get("zuid")
                    or ""
                ),
                "scope": str(
                    row.get("scope")
                    or row.get("permission")
                    or row.get("name")
                    or row.get("value")
                    or ""
                ),
                "status": str(
                    row.get("status") or row.get("state") or row.get("mode") or ""
                ),
                "raw": row,
            }
        )

    utils.output(
        {
            "appId": resolved_app_id,
            "count": len(views),
            "permissions": views,
        }
    )


@cliq_app.command("app-permission-get")
def cliq_app_permission_get(
    app_id: str = typer.Argument(..., help="Cliq app id."),
    permission_id: str = typer.Argument(..., help="Cliq app permission id."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Get one app-governance permission by id (cliq-193 eighth slice)."""

    def _extract_permission_row(payload: Any) -> dict[str, Any]:
        def _unwrap_permission_row(row: dict[str, Any]) -> dict[str, Any]:
            current = row
            for _ in range(16):
                for key in (
                    "response",
                    "result",
                    "payload",
                    "permission",
                    "scope",
                    "item",
                    "record",
                    "permissions",
                    "scopes",
                    "list",
                    "items",
                    "results",
                    "records",
                    "data",
                ):
                    nested = current.get(key)
                    if isinstance(nested, dict):
                        current = nested
                        break
                    if isinstance(nested, list):
                        picked = next(
                            (entry for entry in nested if isinstance(entry, dict)),
                            None,
                        )
                        if picked:
                            current = picked
                            break
                else:
                    break
            return current

        if isinstance(payload, list):
            return next(
                (
                    _unwrap_permission_row(row)
                    for row in payload
                    if isinstance(row, dict)
                ),
                {},
            )

        if not isinstance(payload, dict):
            return {}

        raw_data = payload.get("data")
        if isinstance(raw_data, list):
            candidate = next((row for row in raw_data if isinstance(row, dict)), None)
            if isinstance(candidate, dict):
                return _unwrap_permission_row(candidate)

        for key in ("permission", "scope", "item", "record"):
            candidate = payload.get(key)
            if isinstance(candidate, dict):
                return _unwrap_permission_row(candidate)
            if isinstance(candidate, list):
                picked = next((row for row in candidate if isinstance(row, dict)), None)
                if picked:
                    return _unwrap_permission_row(picked)

        for key in (
            "permissions",
            "scopes",
            "list",
            "items",
            "results",
            "records",
            "response",
            "result",
            "payload",
        ):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                picked = next((row for row in candidate if isinstance(row, dict)), None)
                if picked:
                    return _unwrap_permission_row(picked)
            if isinstance(candidate, dict):
                return _unwrap_permission_row(candidate)

        nested_data = raw_data
        if isinstance(nested_data, dict):
            for key in ("permission", "scope", "item", "record"):
                candidate = nested_data.get(key)
                if isinstance(candidate, dict):
                    return _unwrap_permission_row(candidate)
            for key in (
                "permissions",
                "scopes",
                "list",
                "items",
                "results",
                "records",
                "data",
                "response",
                "result",
                "payload",
            ):
                candidate = nested_data.get(key)
                if isinstance(candidate, list):
                    picked = next(
                        (row for row in candidate if isinstance(row, dict)),
                        None,
                    )
                    if picked:
                        return _unwrap_permission_row(picked)
                if isinstance(candidate, dict):
                    return _unwrap_permission_row(candidate)
            if any(
                key in nested_data
                for key in (
                    "permission_id",
                    "permissionId",
                    "id",
                    "zuid",
                    "scope",
                    "permission",
                    "name",
                    "value",
                    "status",
                    "state",
                    "mode",
                )
            ):
                return nested_data

        if any(
            key in payload
            for key in (
                "permission_id",
                "permissionId",
                "id",
                "zuid",
                "scope",
                "permission",
                "name",
                "value",
                "status",
                "state",
                "mode",
            )
        ):
            return payload

        return {}

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_app_id = app_id.strip()
    resolved_permission_id = permission_id.strip()
    resp = client.get_app_permission(resolved_app_id, resolved_permission_id)
    row = _extract_permission_row(resp)

    view = {
        "permissionId": str(
            row.get("permission_id")
            or row.get("permissionId")
            or row.get("id")
            or row.get("zuid")
            or resolved_permission_id
        ),
        "scope": str(
            row.get("scope")
            or row.get("permission")
            or row.get("name")
            or row.get("value")
            or ""
        ),
        "status": str(row.get("status") or row.get("state") or row.get("mode") or ""),
        "raw": row,
    }

    utils.output(
        {
            "appId": resolved_app_id,
            "permission": view,
        }
    )


@cliq_app.command("app-installs")
def cliq_app_installs(
    app_id: str = typer.Argument(..., help="Cliq app id."),
    limit: int = typer.Option(
        50,
        "--limit",
        "-n",
        help="Max app installs to return.",
    ),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List one app's governance installs (cliq-193 fourth slice)."""

    def _unwrap_install_row(row: dict[str, Any]) -> dict[str, Any]:
        current = row
        for _ in range(16):
            for key in (
                "payload",
                "install",
                "item",
                "installs",
                "installation",
                "installations",
                "record",
                "records",
                "response",
                "result",
                "data",
            ):
                nested = current.get(key)
                if isinstance(nested, dict):
                    current = nested
                    break
                if isinstance(nested, list):
                    first_dict = next(
                        (entry for entry in nested if isinstance(entry, dict)), None
                    )
                    if isinstance(first_dict, dict):
                        current = first_dict
                        break
            else:
                break
        return current

    def _extract_install_rows(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [
                _unwrap_install_row(row) for row in payload if isinstance(row, dict)
            ]

        if not isinstance(payload, dict):
            return []

        for key in ("payload", "install", "item", "record", "response", "result"):
            candidate = payload.get(key)
            if isinstance(candidate, dict):
                return [_unwrap_install_row(candidate)]
            if isinstance(candidate, list):
                return [
                    _unwrap_install_row(row)
                    for row in candidate
                    if isinstance(row, dict)
                ]

        candidates: list[Any] = [
            payload.get("payload"),
            payload.get("data"),
            payload.get("installs"),
            payload.get("installations"),
            payload.get("users"),
            payload.get("list"),
            payload.get("items"),
            payload.get("results"),
            payload.get("records"),
            payload.get("response"),
            payload.get("result"),
        ]
        nested_data = payload.get("data")
        if isinstance(nested_data, dict):
            candidates.extend(
                [
                    nested_data.get("payload"),
                    nested_data.get("installs"),
                    nested_data.get("installations"),
                    nested_data.get("users"),
                    nested_data.get("list"),
                    nested_data.get("items"),
                    nested_data.get("results"),
                    nested_data.get("records"),
                    nested_data.get("response"),
                    nested_data.get("result"),
                    nested_data.get("data"),
                ]
            )

        for candidate in candidates:
            if isinstance(candidate, list):
                return [
                    _unwrap_install_row(row)
                    for row in candidate
                    if isinstance(row, dict)
                ]

            if isinstance(candidate, dict):
                nested_install = (
                    candidate.get("payload")
                    or candidate.get("data")
                    or candidate.get("install")
                    or candidate.get("item")
                    or candidate.get("record")
                    or candidate.get("response")
                    or candidate.get("result")
                )
                if isinstance(nested_install, dict):
                    return [_unwrap_install_row(nested_install)]
                if isinstance(nested_install, list):
                    return [
                        _unwrap_install_row(row)
                        for row in nested_install
                        if isinstance(row, dict)
                    ]

                nested_records = candidate.get("records")
                if isinstance(nested_records, list):
                    return [
                        _unwrap_install_row(row)
                        for row in nested_records
                        if isinstance(row, dict)
                    ]
                if isinstance(nested_records, dict):
                    nested_record = (
                        nested_records.get("record")
                        or nested_records.get("item")
                        or nested_records.get("install")
                    )
                    if isinstance(nested_record, dict):
                        return [_unwrap_install_row(nested_record)]
                    if isinstance(nested_record, list):
                        return [
                            _unwrap_install_row(row)
                            for row in nested_record
                            if isinstance(row, dict)
                        ]

                if any(
                    key in candidate
                    for key in (
                        "install_id",
                        "installId",
                        "id",
                        "zuid",
                        "user_id",
                        "userId",
                        "member_id",
                        "memberId",
                        "target_id",
                        "targetId",
                        "chat_id",
                        "chatId",
                        "bot_id",
                        "botId",
                        "display_name",
                        "name",
                        "title",
                        "user_name",
                        "status",
                        "state",
                        "install_status",
                        "mode",
                    )
                ):
                    return [_unwrap_install_row(candidate)]

        if any(
            key in payload
            for key in (
                "install_id",
                "installId",
                "id",
                "zuid",
                "user_id",
                "userId",
                "member_id",
                "memberId",
                "target_id",
                "targetId",
                "chat_id",
                "chatId",
                "bot_id",
                "botId",
                "display_name",
                "name",
                "title",
                "user_name",
            )
        ):
            return [_unwrap_install_row(payload)]

        return []

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_app_id = app_id.strip()
    resp = client.list_app_installs(resolved_app_id, limit=limit)
    rows = _extract_install_rows(resp)

    views: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        views.append(
            {
                "installId": str(
                    row.get("install_id")
                    or row.get("installId")
                    or row.get("id")
                    or row.get("zuid")
                    or ""
                ),
                "subjectId": str(
                    row.get("subject_id")
                    or row.get("subjectId")
                    or row.get("user_id")
                    or row.get("userId")
                    or row.get("member_id")
                    or row.get("memberId")
                    or row.get("target_id")
                    or row.get("targetId")
                    or row.get("chat_id")
                    or row.get("chatId")
                    or row.get("bot_id")
                    or row.get("botId")
                    or ""
                ),
                "name": str(
                    row.get("display_name")
                    or row.get("name")
                    or row.get("title")
                    or row.get("user_name")
                    or ""
                ),
                "status": str(
                    row.get("status")
                    or row.get("state")
                    or row.get("install_status")
                    or row.get("mode")
                    or ""
                ),
                "raw": row,
            }
        )

    utils.output(
        {
            "appId": resolved_app_id,
            "count": len(views),
            "installs": views,
        }
    )


@cliq_app.command("app-install-get")
def cliq_app_install_get(
    app_id: str = typer.Argument(..., help="Cliq app id."),
    install_id: str = typer.Argument(..., help="Cliq app install id."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Get one app-governance install by id (cliq-193 seventh slice)."""

    def _extract_install_row(payload: Any) -> dict[str, Any]:
        def _unwrap_install_row(row: dict[str, Any]) -> dict[str, Any]:
            current = row
            for _ in range(16):
                for key in (
                    "payload",
                    "install",
                    "item",
                    "record",
                    "installs",
                    "installations",
                    "users",
                    "list",
                    "items",
                    "results",
                    "records",
                    "response",
                    "result",
                    "data",
                ):
                    nested = current.get(key)
                    if isinstance(nested, dict):
                        current = nested
                        break
                    if isinstance(nested, list):
                        picked = next(
                            (entry for entry in nested if isinstance(entry, dict)),
                            None,
                        )
                        if picked:
                            current = picked
                            break
                else:
                    break
            return current

        if isinstance(payload, list):
            return next(
                (_unwrap_install_row(row) for row in payload if isinstance(row, dict)),
                {},
            )

        if not isinstance(payload, dict):
            return {}

        raw_data = payload.get("data") or payload.get("payload")
        if isinstance(raw_data, list):
            candidate = next((row for row in raw_data if isinstance(row, dict)), None)
            if isinstance(candidate, dict):
                return _unwrap_install_row(candidate)

        for key in ("payload", "install", "item", "record", "response", "result"):
            candidate = payload.get(key)
            if isinstance(candidate, dict):
                return _unwrap_install_row(candidate)
            if isinstance(candidate, list):
                picked = next((row for row in candidate if isinstance(row, dict)), None)
                if picked:
                    return _unwrap_install_row(picked)

        for key in (
            "payload",
            "installs",
            "installations",
            "users",
            "list",
            "items",
            "results",
            "records",
            "response",
            "result",
        ):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                picked = next((row for row in candidate if isinstance(row, dict)), None)
                if picked:
                    return _unwrap_install_row(picked)
            if isinstance(candidate, dict):
                return _unwrap_install_row(candidate)

        nested_data = raw_data
        if isinstance(nested_data, dict):
            for key in ("payload", "install", "item", "record", "response", "result"):
                candidate = nested_data.get(key)
                if isinstance(candidate, dict):
                    return _unwrap_install_row(candidate)
            for key in (
                "payload",
                "installs",
                "installations",
                "users",
                "list",
                "items",
                "results",
                "records",
                "response",
                "result",
                "data",
            ):
                candidate = nested_data.get(key)
                if isinstance(candidate, list):
                    picked = next(
                        (row for row in candidate if isinstance(row, dict)),
                        None,
                    )
                    if picked:
                        return _unwrap_install_row(picked)
                if isinstance(candidate, dict):
                    return _unwrap_install_row(candidate)
            if any(
                key in nested_data
                for key in (
                    "install_id",
                    "installId",
                    "id",
                    "zuid",
                    "user_id",
                    "userId",
                    "member_id",
                    "memberId",
                    "target_id",
                    "targetId",
                    "chat_id",
                    "chatId",
                    "bot_id",
                    "botId",
                    "display_name",
                    "name",
                    "title",
                    "user_name",
                    "status",
                    "state",
                    "install_status",
                    "mode",
                )
            ):
                return nested_data

        if any(
            key in payload
            for key in (
                "install_id",
                "installId",
                "id",
                "zuid",
                "user_id",
                "userId",
                "member_id",
                "memberId",
                "target_id",
                "targetId",
                "chat_id",
                "chatId",
                "bot_id",
                "botId",
                "display_name",
                "name",
                "title",
                "user_name",
                "status",
                "state",
                "install_status",
                "mode",
            )
        ):
            return payload

        return {}

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_app_id = app_id.strip()
    resolved_install_id = install_id.strip()
    resp = client.get_app_install(resolved_app_id, resolved_install_id)
    row = _extract_install_row(resp)

    view = {
        "installId": str(
            row.get("install_id")
            or row.get("installId")
            or row.get("id")
            or row.get("zuid")
            or resolved_install_id
        ),
        "subjectId": str(
            row.get("subject_id")
            or row.get("subjectId")
            or row.get("user_id")
            or row.get("userId")
            or row.get("member_id")
            or row.get("memberId")
            or row.get("target_id")
            or row.get("targetId")
            or row.get("chat_id")
            or row.get("chatId")
            or row.get("bot_id")
            or row.get("botId")
            or ""
        ),
        "name": str(
            row.get("display_name")
            or row.get("name")
            or row.get("title")
            or row.get("user_name")
            or ""
        ),
        "status": str(
            row.get("status")
            or row.get("state")
            or row.get("install_status")
            or row.get("mode")
            or ""
        ),
        "raw": row,
    }

    utils.output(
        {
            "appId": resolved_app_id,
            "install": view,
        }
    )


@cliq_app.command("app-commands-bridge-run")
def cliq_app_commands_bridge_run(
    app_id: str = typer.Argument(..., help="Cliq app id."),
    action_id: Optional[str] = typer.Option(
        None,
        "--action-id",
        help="Optional membrane action id override.",
    ),
    bridge: str = typer.Option(
        "membrane",
        "--bridge",
        help="Bridge backend. Currently only 'membrane' is supported.",
    ),
    connection_id: Optional[str] = typer.Option(
        None,
        "--connection-id",
        help="Membrane connection ID. Overrides preset lookup when provided.",
    ),
    preset: Optional[str] = typer.Option(
        "zoho-cliq",
        "--preset",
        help="Connection preset alias (default: zoho-cliq).",
    ),
    input_json: Optional[str] = typer.Option(
        None,
        "--input-json",
        help="Optional JSON input passed to membrane --input (merged with appId).",
    ),
) -> None:
    """Run Cliq app-command listing through membrane bridge (explicit opt-in)."""
    if bridge.strip().lower() != "membrane":
        utils.error_exit(
            "unsupported_bridge",
            "Only --bridge membrane is supported right now.",
        )

    resolved_app_id = app_id.strip()
    if not resolved_app_id:
        utils.error_exit("invalid_app_id", "App id cannot be empty")

    resolved_action_id = (action_id or "").strip() or "app-commands"

    cfg = _cfg()
    email = _S.account or _config.default_account(cfg)
    resolved_connection_id = _resolve_membrane_connection_id(
        connection_id=connection_id,
        preset=preset,
        cfg=cfg,
        email=email,
    )

    resolved_input: Any | None = None
    if input_json is not None:
        try:
            resolved_input = json.loads(input_json)
        except json.JSONDecodeError:
            utils.error_exit(
                "invalid_input_json",
                "--input-json must be a valid JSON object/string.",
            )

    if resolved_input is None:
        resolved_input = {"appId": resolved_app_id}
    elif isinstance(resolved_input, dict):
        resolved_input = dict(resolved_input)
        resolved_input.setdefault("appId", resolved_app_id)
    else:
        utils.error_exit(
            "invalid_input_json",
            "--input-json must decode to a JSON object for app-commands bridge runs.",
        )

    command: list[str] = [
        "action",
        "run",
        f"--connectionId={resolved_connection_id}",
        resolved_action_id,
        "--json",
        "--input",
        json.dumps(resolved_input, ensure_ascii=False),
    ]

    result = _run_membrane_command(command)
    utils.output(
        {
            "bridge": "membrane",
            "preset": _normalize_membrane_preset(preset or "zoho-cliq"),
            "connectionId": resolved_connection_id,
            "actionId": resolved_action_id,
            "appId": resolved_app_id,
            "input": resolved_input,
            "result": result,
        }
    )


@cliq_app.command("app-commands")
def cliq_app_commands(
    app_id: str = typer.Argument(..., help="Cliq app id."),
    limit: int = typer.Option(
        50,
        "--limit",
        "-n",
        help="Max app commands to return.",
    ),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List one app's governance commands (cliq-193 fifth slice)."""

    def _unwrap_command_row(row: dict[str, Any]) -> dict[str, Any]:
        current = row
        for _ in range(16):
            for key in (
                "payload",
                "response",
                "result",
                "command",
                "commands",
                "Command",
                "Commands",
                "COMMAND",
                "COMMANDS",
                "action",
                "actions",
                "Action",
                "Actions",
                "ACTION",
                "ACTIONS",
                "item",
                "record",
                "records",
                "data",
            ):
                nested = current.get(key)
                if isinstance(nested, dict):
                    current = nested
                    break
                if isinstance(nested, list):
                    picked = next(
                        (
                            entry
                            for entry in nested
                            if isinstance(entry, dict)
                            and _entry_has_command_hints(entry)
                        ),
                        None,
                    )
                    if not picked:
                        picked = next(
                            (entry for entry in nested if isinstance(entry, dict)), None
                        )
                    if picked:
                        current = picked
                        break
            else:
                break
        return current

    def _has_command_payload(candidate: dict[str, Any]) -> bool:
        generic_status_hints = {
            "status",
            "state",
            "mode",
            "Status",
            "State",
            "Mode",
            "STATUS",
            "STATE",
            "MODE",
        }
        present_hints = {
            key
            for key in (
                "command_id",
                "commandId",
                "CommandId",
                "CommandID",
                "COMMANDID",
                "COMMAND_ID",
                "commandID",
                "commandid",
                "action_id",
                "actionId",
                "ACTION_ID",
                "ACTIONID",
                "id",
                "zuid",
                "name",
                "CommandName",
                "command_name",
                "commandName",
                "ActionName",
                "COMMANDNAME",
                "ACTIONNAME",
                "COMMAND_NAME",
                "ACTION_NAME",
                "commandname",
                "actionname",
                "command",
                "Command",
                "COMMAND",
                "action",
                "Action",
                "ACTION",
                "action_name",
                "actionName",
                "ActionId",
                "ActionID",
                "actionID",
                "actionid",
                "display_name",
                "DisplayName",
                "displayName",
                "DISPLAYNAME",
                "DISPLAY_NAME",
                "displayname",
                "command_display_name",
                "command_displayname",
                "command_display",
                "command_displayName",
                "command_Display",
                "command_Display_Name",
                "command_DisplayName",
                "command_Displayname",
                "Command_Display",
                "Command_Display_Name",
                "Command_DisplayName",
                "Command_Displayname",
                "commandDisplay_name",
                "commandDisplay",
                "commanddisplay",
                "commandDisplayName",
                "commandDisplayname",
                "commanddisplayName",
                "commanddisplayname",
                "CommandDisplayName",
                "CommandDisplayname",
                "CommandDisplay",
                "command-display-name",
                "command-Display-Name",
                "command-displayName",
                "command-DisplayName",
                "command-displayname",
                "command-Displayname",
                "command-display",
                "command-Display",
                "Command-Display-Name",
                "Command-DisplayName",
                "Command-Displayname",
                "Command-Display",
                "COMMAND-DISPLAY-NAME",
                "COMMAND-DISPLAYNAME",
                "COMMAND-DISPLAY",
                "COMMANDDISPLAY",
                "COMMANDDISPLAYNAME",
                "COMMAND_DISPLAY_NAME",
                "COMMAND_DISPLAYNAME",
                "COMMAND_DISPLAY",
                "action_display_name",
                "action_displayname",
                "action_display",
                "action_displayName",
                "action_Display",
                "action_Display_Name",
                "action_DisplayName",
                "action_Displayname",
                "Action_Display",
                "Action_Display_Name",
                "Action_DisplayName",
                "Action_Displayname",
                "actionDisplay_name",
                "actionDisplay",
                "actiondisplay",
                "actionDisplayName",
                "actionDisplayname",
                "actiondisplayName",
                "actiondisplayname",
                "ActionDisplayName",
                "ActionDisplayname",
                "ActionDisplay",
                "action-display-name",
                "action-Display-Name",
                "action-displayName",
                "action-DisplayName",
                "action-displayname",
                "action-Displayname",
                "action-display",
                "action-Display",
                "Action-Display-Name",
                "Action-DisplayName",
                "Action-Displayname",
                "Action-Display",
                "ACTION-DISPLAY-NAME",
                "ACTION-DISPLAYNAME",
                "ACTION-DISPLAY",
                "ACTIONDISPLAY",
                "ACTIONDISPLAYNAME",
                "ACTION_DISPLAY_NAME",
                "ACTION_DISPLAYNAME",
                "ACTION_DISPLAY",
                "title",
                "description",
                "summary",
                "Description",
                "Summary",
                "DESCRIPTION",
                "SUMMARY",
                "help_text",
                "helpText",
                "helptext",
                "HelpText",
                "help",
                "Help",
                "HELPTEXT",
                "HELP",
                "command_description",
                "commandDescription",
                "commanddescription",
                "CommandDescription",
                "COMMANDDESCRIPTION",
                "COMMAND_DESCRIPTION",
                "action_description",
                "actionDescription",
                "actiondescription",
                "ActionDescription",
                "ACTIONDESCRIPTION",
                "ACTION_DESCRIPTION",
                "command_help",
                "COMMAND_HELP",
                "commandHelp",
                "COMMANDHELP",
                "CommandHelp",
                "commandhelp",
                "command-help",
                "Command-Help",
                "COMMAND-HELP",
                "command_help_text",
                "command_helpText",
                "command_HELPTEXT",
                "command_HelpText",
                "command_Helptext",
                "command_Help_Text",
                "command_HELP_TEXT",
                "command_HELP-TEXT",
                "Command_help_text",
                "Command_helpText",
                "Command_helptext",
                "Command_help-Text",
                "Command_HelpText",
                "Command_Helptext",
                "Command_Help_Text",
                "Command_HELP_TEXT",
                "Command_HELP-TEXT",
                "Command_HELPTEXT",
                "commandHelpText",
                "CommandHelpText",
                "commandhelptext",
                "COMMANDHELPTEXT",
                "COMMAND_HELP_TEXT",
                "COMMAND_HELP-TEXT",
                "COMMAND_HELPTEXT",
                "command-help-text",
                "command-helptext",
                "command-helpText",
                "command-help_text",
                "command.help_text",
                "command-Helptext",
                "command-HelpText",
                "command-Help-Text",
                "command-HELP_TEXT",
                "command-HELP-TEXT",
                "Command-helptext",
                "Command-helpText",
                "Command-help_text",
                "Command-Helptext",
                "Command-HelpText",
                "Command-Help-Text",
                "Command-HELP_TEXT",
                "Command-HELP-TEXT",
                "COMMAND-HELPTEXT",
                "COMMAND-HELP_TEXT",
                "COMMAND-HELP-TEXT",
                "action_help",
                "ACTION_HELP",
                "actionHelp",
                "ACTIONHELP",
                "ActionHelp",
                "actionhelp",
                "action-help",
                "Action-Help",
                "ACTION-HELP",
                "action_help_text",
                "action_helpText",
                "action_HELPTEXT",
                "action_HelpText",
                "action_Helptext",
                "action_Help_Text",
                "action_HELP_TEXT",
                "action_HELP-TEXT",
                "Action_help_text",
                "Action_helpText",
                "Action_helptext",
                "Action_help-Text",
                "Action_HelpText",
                "Action_Helptext",
                "Action_Help_Text",
                "Action_HELP_TEXT",
                "Action_HELP-TEXT",
                "Action_HELPTEXT",
                "actionHelpText",
                "ActionHelpText",
                "actionhelptext",
                "ACTIONHELPTEXT",
                "ACTION_HELP_TEXT",
                "ACTION_HELP-TEXT",
                "ACTION_HELPTEXT",
                "action-help-text",
                "action-helptext",
                "action-helpText",
                "action-help_text",
                "action.help_text",
                "action-Helptext",
                "action-HelpText",
                "action-Help-Text",
                "action-HELP_TEXT",
                "action-HELP-TEXT",
                "Action-helptext",
                "Action-helpText",
                "Action-help_text",
                "Action-Helptext",
                "Action-HelpText",
                "Action-Help-Text",
                "Action-HELP_TEXT",
                "Action-HELP-TEXT",
                "ACTION-HELPTEXT",
                "ACTION-HELP_TEXT",
                "ACTION-HELP-TEXT",
                "status",
                "state",
                "mode",
                "Status",
                "State",
                "Mode",
                "STATUS",
                "STATE",
                "MODE",
                "command_status",
                "command_Status",
                "command_STATUS",
                "commandStatus",
                "commandstatus",
                "CommandStatus",
                "Command_Status",
                "Command_STATUS",
                "COMMANDSTATUS",
                "COMMAND_STATUS",
                "command-status",
                "Command-Status",
                "command-STATUS",
                "Command-STATUS",
                "COMMAND-STATUS",
                "command_mode",
                "command_Mode",
                "command_MODE",
                "commandMode",
                "commandmode",
                "CommandMode",
                "Command_Mode",
                "Command_MODE",
                "COMMANDMODE",
                "COMMAND_MODE",
                "command-mode",
                "Command-Mode",
                "command-MODE",
                "Command-MODE",
                "COMMAND-MODE",
                "action_status",
                "action_Status",
                "action_STATUS",
                "actionStatus",
                "actionstatus",
                "ActionStatus",
                "Action_Status",
                "Action_STATUS",
                "ACTIONSTATUS",
                "ACTION_STATUS",
                "action-status",
                "Action-Status",
                "action-STATUS",
                "Action-STATUS",
                "ACTION-STATUS",
                "action_mode",
                "action_Mode",
                "action_MODE",
                "actionMode",
                "actionmode",
                "ActionMode",
                "Action_Mode",
                "Action_MODE",
                "ACTIONMODE",
                "ACTION_MODE",
                "action-mode",
                "Action-Mode",
                "action-MODE",
                "Action-MODE",
                "ACTION-MODE",
            )
            if key in candidate
        }
        if not present_hints:
            return False
        return any(key not in generic_status_hints for key in present_hints)

    def _entry_has_command_hints(candidate: dict[str, Any]) -> bool:
        if _has_command_payload(candidate):
            return True
        for key in (
            "payload",
            "response",
            "result",
            "command",
            "commands",
            "Command",
            "Commands",
            "COMMAND",
            "COMMANDS",
            "action",
            "actions",
            "Action",
            "Actions",
            "ACTION",
            "ACTIONS",
            "item",
            "record",
            "records",
            "data",
        ):
            nested = candidate.get(key)
            if isinstance(nested, dict) and _has_command_payload(nested):
                return True
        return False

    def _normalize_command_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = [_unwrap_command_row(row) for row in rows if isinstance(row, dict)]
        command_rows = [row for row in normalized if _has_command_payload(row)]

        def _looks_like_command_row(candidate: dict[str, Any]) -> bool:
            if "meta" not in candidate:
                return True
            return _has_command_payload(candidate)

        filtered_rows = [row for row in command_rows if _looks_like_command_row(row)]
        if filtered_rows:
            command_rows = filtered_rows
        return command_rows or normalized

    def _has_preferred_command_rows(rows: list[dict[str, Any]]) -> bool:
        for row in rows:
            if not isinstance(row, dict):
                continue
            if "meta" not in row:
                return True
            if _has_command_payload(row):
                return True
        return False

    def _extract_command_rows(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return _normalize_command_rows(payload)

        if isinstance(payload, dict):
            metadata_fallback_rows: list[dict[str, Any]] = []

            for key in (
                "data",
                "commands",
                "command",
                "COMMANDS",
                "COMMAND",
                "actions",
                "action",
                "ACTIONS",
                "ACTION",
                "payload",
                "response",
                "result",
                "record",
                "records",
                "items",
                "list",
                "results",
            ):
                candidate = payload.get(key)
                if isinstance(candidate, dict):
                    nested_rows = _extract_command_rows(candidate)
                    if nested_rows:
                        if _has_preferred_command_rows(nested_rows):
                            return nested_rows
                        if not metadata_fallback_rows:
                            metadata_fallback_rows = nested_rows
                if isinstance(candidate, list):
                    rows = _normalize_command_rows(candidate)
                    if rows:
                        if _has_preferred_command_rows(rows):
                            return rows
                        if not metadata_fallback_rows:
                            metadata_fallback_rows = rows

            candidates = [
                payload.get("payload"),
                payload.get("response"),
                payload.get("result"),
                payload.get("data"),
                payload.get("records"),
                payload.get("record"),
                payload.get("item"),
                payload,
            ]

            for candidate in candidates:
                if isinstance(candidate, list):
                    rows = _normalize_command_rows(candidate)
                    if rows:
                        if _has_preferred_command_rows(rows):
                            return rows
                        if not metadata_fallback_rows:
                            metadata_fallback_rows = rows
                if isinstance(candidate, dict):
                    nested_command = candidate.get("command")
                    if isinstance(nested_command, dict):
                        return _normalize_command_rows([nested_command])
                    if isinstance(nested_command, list):
                        return _normalize_command_rows(nested_command)

                    nested_records = candidate.get("records")
                    if isinstance(nested_records, list):
                        rows = _normalize_command_rows(nested_records)
                        if rows:
                            return rows
                    if isinstance(nested_records, dict):
                        nested_rows = _extract_command_rows(nested_records)
                        if nested_rows:
                            return nested_rows

                    nested_record = candidate.get("record")
                    if isinstance(nested_record, list):
                        rows = _normalize_command_rows(nested_record)
                        if rows:
                            return rows
                    if isinstance(nested_record, dict):
                        nested_rows = _extract_command_rows(nested_record)
                        if nested_rows:
                            return nested_rows

                    nested_data = candidate.get("data")
                    if isinstance(nested_data, list):
                        rows = _normalize_command_rows(nested_data)
                        if rows:
                            return rows
                    if isinstance(nested_data, dict):
                        nested_rows = _extract_command_rows(nested_data)
                        if nested_rows:
                            return nested_rows

                    if _has_command_payload(candidate):
                        return [_unwrap_command_row(candidate)]

            if metadata_fallback_rows:
                return metadata_fallback_rows

            if _has_command_payload(payload):
                return [_unwrap_command_row(payload)]

        return []

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_app_id = app_id.strip()
    resp = client.list_app_commands(resolved_app_id, limit=limit)
    rows = _extract_command_rows(resp)

    views: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        views.append(
            {
                "commandId": str(
                    row.get("command_id")
                    or row.get("commandId")
                    or row.get("CommandId")
                    or row.get("CommandID")
                    or row.get("COMMANDID")
                    or row.get("COMMAND_ID")
                    or row.get("commandID")
                    or row.get("commandid")
                    or row.get("action_id")
                    or row.get("actionId")
                    or row.get("ACTION_ID")
                    or row.get("ActionId")
                    or row.get("ActionID")
                    or row.get("ACTIONID")
                    or row.get("actionID")
                    or row.get("actionid")
                    or row.get("id")
                    or row.get("zuid")
                    or ""
                ),
                "name": str(
                    row.get("name")
                    or row.get("CommandName")
                    or row.get("commandName")
                    or row.get("ActionName")
                    or row.get("actionName")
                    or row.get("COMMANDNAME")
                    or row.get("ACTIONNAME")
                    or row.get("COMMAND_NAME")
                    or row.get("ACTION_NAME")
                    or row.get("commandname")
                    or row.get("actionname")
                    or row.get("command_name")
                    or row.get("command")
                    or row.get("Command")
                    or row.get("COMMAND")
                    or row.get("action")
                    or row.get("Action")
                    or row.get("ACTION")
                    or row.get("action_name")
                    or row.get("display_name")
                    or row.get("DisplayName")
                    or row.get("displayName")
                    or row.get("DISPLAYNAME")
                    or row.get("DISPLAY_NAME")
                    or row.get("displayname")
                    or row.get("command_display_name")
                    or row.get("command_displayname")
                    or row.get("command_display")
                    or row.get("command_displayName")
                    or row.get("command_Display")
                    or row.get("command_Display_Name")
                    or row.get("command_DisplayName")
                    or row.get("command_Displayname")
                    or row.get("Command_Display")
                    or row.get("Command_Display_Name")
                    or row.get("Command_DisplayName")
                    or row.get("Command_Displayname")
                    or row.get("commandDisplay_name")
                    or row.get("commandDisplay")
                    or row.get("commanddisplay")
                    or row.get("commandDisplayName")
                    or row.get("commandDisplayname")
                    or row.get("commanddisplayName")
                    or row.get("commanddisplayname")
                    or row.get("CommandDisplayName")
                    or row.get("CommandDisplayname")
                    or row.get("CommandDisplay")
                    or row.get("command-display-name")
                    or row.get("command-Display-Name")
                    or row.get("command-displayName")
                    or row.get("command-DisplayName")
                    or row.get("command-displayname")
                    or row.get("command-Displayname")
                    or row.get("command-display")
                    or row.get("command-Display")
                    or row.get("Command-Display-Name")
                    or row.get("Command-DisplayName")
                    or row.get("Command-Displayname")
                    or row.get("Command-Display")
                    or row.get("COMMAND-DISPLAY-NAME")
                    or row.get("COMMAND-DISPLAYNAME")
                    or row.get("COMMAND-DISPLAY")
                    or row.get("COMMANDDISPLAY")
                    or row.get("COMMANDDISPLAYNAME")
                    or row.get("COMMAND_DISPLAY_NAME")
                    or row.get("COMMAND_DISPLAYNAME")
                    or row.get("COMMAND_DISPLAY")
                    or row.get("action_display_name")
                    or row.get("action_displayname")
                    or row.get("action_display")
                    or row.get("action_displayName")
                    or row.get("action_Display")
                    or row.get("action_Display_Name")
                    or row.get("action_DisplayName")
                    or row.get("action_Displayname")
                    or row.get("Action_Display")
                    or row.get("Action_Display_Name")
                    or row.get("Action_DisplayName")
                    or row.get("Action_Displayname")
                    or row.get("actionDisplay_name")
                    or row.get("actionDisplay")
                    or row.get("actiondisplay")
                    or row.get("actionDisplayName")
                    or row.get("actionDisplayname")
                    or row.get("actiondisplayName")
                    or row.get("actiondisplayname")
                    or row.get("ActionDisplayName")
                    or row.get("ActionDisplayname")
                    or row.get("ActionDisplay")
                    or row.get("action-display-name")
                    or row.get("action-Display-Name")
                    or row.get("action-displayName")
                    or row.get("action-DisplayName")
                    or row.get("action-displayname")
                    or row.get("action-Displayname")
                    or row.get("action-display")
                    or row.get("action-Display")
                    or row.get("Action-Display-Name")
                    or row.get("Action-DisplayName")
                    or row.get("Action-Displayname")
                    or row.get("Action-Display")
                    or row.get("ACTION-DISPLAY-NAME")
                    or row.get("ACTION-DISPLAYNAME")
                    or row.get("ACTION-DISPLAY")
                    or row.get("ACTIONDISPLAY")
                    or row.get("ACTIONDISPLAYNAME")
                    or row.get("ACTION_DISPLAY_NAME")
                    or row.get("ACTION_DISPLAYNAME")
                    or row.get("ACTION_DISPLAY")
                    or row.get("title")
                    or ""
                ),
                "description": str(
                    row.get("description")
                    or row.get("summary")
                    or row.get("Description")
                    or row.get("Summary")
                    or row.get("DESCRIPTION")
                    or row.get("SUMMARY")
                    or row.get("help_text")
                    or row.get("helptext")
                    or row.get("helpText")
                    or row.get("HelpText")
                    or row.get("help")
                    or row.get("Help")
                    or row.get("HELPTEXT")
                    or row.get("HELP")
                    or row.get("command_description")
                    or row.get("commandDescription")
                    or row.get("commanddescription")
                    or row.get("CommandDescription")
                    or row.get("COMMANDDESCRIPTION")
                    or row.get("COMMAND_DESCRIPTION")
                    or row.get("action_description")
                    or row.get("actionDescription")
                    or row.get("actiondescription")
                    or row.get("ActionDescription")
                    or row.get("ACTIONDESCRIPTION")
                    or row.get("ACTION_DESCRIPTION")
                    or row.get("command_help")
                    or row.get("COMMAND_HELP")
                    or row.get("commandHelp")
                    or row.get("COMMANDHELP")
                    or row.get("CommandHelp")
                    or row.get("commandhelp")
                    or row.get("command-help")
                    or row.get("Command-Help")
                    or row.get("COMMAND-HELP")
                    or row.get("command_help_text")
                    or row.get("command_helpText")
                    or row.get("command_HELPTEXT")
                    or row.get("command_HelpText")
                    or row.get("command_Helptext")
                    or row.get("command_Help_Text")
                    or row.get("command_HELP_TEXT")
                    or row.get("command_HELP-TEXT")
                    or row.get("Command_help_text")
                    or row.get("Command_helpText")
                    or row.get("Command_helptext")
                    or row.get("Command_help-Text")
                    or row.get("Command_HelpText")
                    or row.get("Command_Helptext")
                    or row.get("Command_Help_Text")
                    or row.get("Command_HELP_TEXT")
                    or row.get("Command_HELP-TEXT")
                    or row.get("Command_HELPTEXT")
                    or row.get("commandHelpText")
                    or row.get("CommandHelpText")
                    or row.get("commandhelptext")
                    or row.get("COMMANDHELPTEXT")
                    or row.get("COMMAND_HELP_TEXT")
                    or row.get("COMMAND_HELP-TEXT")
                    or row.get("COMMAND_HELPTEXT")
                    or row.get("command-help-text")
                    or row.get("command-helptext")
                    or row.get("command-helpText")
                    or row.get("command-help_text")
                    or row.get("command.help_text")
                    or row.get("command-Helptext")
                    or row.get("command-HelpText")
                    or row.get("command-Help-Text")
                    or row.get("command-HELP_TEXT")
                    or row.get("command-HELP-TEXT")
                    or row.get("Command-helptext")
                    or row.get("Command-helpText")
                    or row.get("Command-help_text")
                    or row.get("Command-Helptext")
                    or row.get("Command-HelpText")
                    or row.get("Command-Help-Text")
                    or row.get("Command-HELP_TEXT")
                    or row.get("Command-HELP-TEXT")
                    or row.get("COMMAND-HELPTEXT")
                    or row.get("COMMAND-HELP_TEXT")
                    or row.get("COMMAND-HELP-TEXT")
                    or row.get("action_help")
                    or row.get("ACTION_HELP")
                    or row.get("actionHelp")
                    or row.get("ACTIONHELP")
                    or row.get("ActionHelp")
                    or row.get("actionhelp")
                    or row.get("action-help")
                    or row.get("Action-Help")
                    or row.get("ACTION-HELP")
                    or row.get("action_help_text")
                    or row.get("action_helpText")
                    or row.get("action_HELPTEXT")
                    or row.get("action_HelpText")
                    or row.get("action_Helptext")
                    or row.get("action_Help_Text")
                    or row.get("action_HELP_TEXT")
                    or row.get("action_HELP-TEXT")
                    or row.get("Action_help_text")
                    or row.get("Action_helpText")
                    or row.get("Action_helptext")
                    or row.get("Action_help-Text")
                    or row.get("Action_HelpText")
                    or row.get("Action_Helptext")
                    or row.get("Action_Help_Text")
                    or row.get("Action_HELP_TEXT")
                    or row.get("Action_HELP-TEXT")
                    or row.get("Action_HELPTEXT")
                    or row.get("actionHelpText")
                    or row.get("ActionHelpText")
                    or row.get("actionhelptext")
                    or row.get("ACTIONHELPTEXT")
                    or row.get("ACTION_HELP_TEXT")
                    or row.get("ACTION_HELP-TEXT")
                    or row.get("ACTION_HELPTEXT")
                    or row.get("action-help-text")
                    or row.get("action-helptext")
                    or row.get("action-helpText")
                    or row.get("action-help_text")
                    or row.get("action.help_text")
                    or row.get("action-Helptext")
                    or row.get("action-HelpText")
                    or row.get("action-Help-Text")
                    or row.get("action-HELP_TEXT")
                    or row.get("action-HELP-TEXT")
                    or row.get("Action-helptext")
                    or row.get("Action-helpText")
                    or row.get("Action-help_text")
                    or row.get("Action-Helptext")
                    or row.get("Action-HelpText")
                    or row.get("Action-Help-Text")
                    or row.get("Action-HELP_TEXT")
                    or row.get("Action-HELP-TEXT")
                    or row.get("ACTION-HELPTEXT")
                    or row.get("ACTION-HELP_TEXT")
                    or row.get("ACTION-HELP-TEXT")
                    or ""
                ),
                "status": str(
                    row.get("status")
                    or row.get("state")
                    or row.get("mode")
                    or row.get("Status")
                    or row.get("State")
                    or row.get("Mode")
                    or row.get("STATUS")
                    or row.get("STATE")
                    or row.get("MODE")
                    or row.get("command_status")
                    or row.get("command_Status")
                    or row.get("command_STATUS")
                    or row.get("commandStatus")
                    or row.get("commandstatus")
                    or row.get("CommandStatus")
                    or row.get("Command_Status")
                    or row.get("Command_STATUS")
                    or row.get("COMMANDSTATUS")
                    or row.get("COMMAND_STATUS")
                    or row.get("command-status")
                    or row.get("Command-Status")
                    or row.get("command-STATUS")
                    or row.get("Command-STATUS")
                    or row.get("COMMAND-STATUS")
                    or row.get("command_mode")
                    or row.get("command_Mode")
                    or row.get("command_MODE")
                    or row.get("commandMode")
                    or row.get("commandmode")
                    or row.get("CommandMode")
                    or row.get("Command_Mode")
                    or row.get("Command_MODE")
                    or row.get("COMMANDMODE")
                    or row.get("COMMAND_MODE")
                    or row.get("command-mode")
                    or row.get("Command-Mode")
                    or row.get("command-MODE")
                    or row.get("Command-MODE")
                    or row.get("COMMAND-MODE")
                    or row.get("action_status")
                    or row.get("action_Status")
                    or row.get("action_STATUS")
                    or row.get("actionStatus")
                    or row.get("actionstatus")
                    or row.get("ActionStatus")
                    or row.get("Action_Status")
                    or row.get("Action_STATUS")
                    or row.get("ACTIONSTATUS")
                    or row.get("ACTION_STATUS")
                    or row.get("action-status")
                    or row.get("Action-Status")
                    or row.get("action-STATUS")
                    or row.get("Action-STATUS")
                    or row.get("ACTION-STATUS")
                    or row.get("action_mode")
                    or row.get("action_Mode")
                    or row.get("action_MODE")
                    or row.get("actionMode")
                    or row.get("actionmode")
                    or row.get("ActionMode")
                    or row.get("Action_Mode")
                    or row.get("Action_MODE")
                    or row.get("ACTIONMODE")
                    or row.get("ACTION_MODE")
                    or row.get("action-mode")
                    or row.get("Action-Mode")
                    or row.get("action-MODE")
                    or row.get("Action-MODE")
                    or row.get("ACTION-MODE")
                    or ""
                ),
                "raw": row,
            }
        )

    utils.output(
        {
            "appId": resolved_app_id,
            "count": len(views),
            "commands": views,
        }
    )


@cliq_app.command("app-command-get")
def cliq_app_command_get(
    app_id: str = typer.Argument(..., help="Cliq app id."),
    command_id: str = typer.Argument(..., help="Cliq app command id."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Get one app's governance command by id (cliq-193 sixth slice)."""

    def _extract_command_row(payload: Any) -> dict[str, Any]:
        command_hints = (
            "command_id",
            "commandId",
            "CommandId",
            "CommandID",
            "COMMANDID",
            "COMMAND_ID",
            "commandID",
            "commandid",
            "action_id",
            "actionId",
            "ACTION_ID",
            "ActionId",
            "ActionID",
            "ACTIONID",
            "actionID",
            "actionid",
            "id",
            "zuid",
            "name",
            "CommandName",
            "commandName",
            "ActionName",
            "actionName",
            "COMMANDNAME",
            "ACTIONNAME",
            "COMMAND_NAME",
            "ACTION_NAME",
            "commandname",
            "actionname",
            "command_name",
            "command",
            "Command",
            "COMMAND",
            "action",
            "Action",
            "ACTION",
            "action_name",
            "display_name",
            "DisplayName",
            "displayName",
            "DISPLAYNAME",
            "DISPLAY_NAME",
            "displayname",
            "command_display_name",
            "command_displayname",
            "command_display",
            "command_displayName",
            "command_Display",
            "command_Display_Name",
            "command_DisplayName",
            "command_Displayname",
            "Command_Display",
            "Command_Display_Name",
            "Command_DisplayName",
            "Command_Displayname",
            "commandDisplay_name",
            "commandDisplay",
            "commanddisplay",
            "commandDisplayName",
            "commandDisplayname",
            "commanddisplayName",
            "commanddisplayname",
            "CommandDisplayName",
            "CommandDisplayname",
            "CommandDisplay",
            "command-display-name",
            "command-Display-Name",
            "command-displayName",
            "command-DisplayName",
            "command-displayname",
            "command-Displayname",
            "command-display",
            "command-Display",
            "Command-Display-Name",
            "Command-DisplayName",
            "Command-Displayname",
            "Command-Display",
            "COMMAND-DISPLAY-NAME",
            "COMMAND-DISPLAYNAME",
            "COMMAND-DISPLAY",
            "COMMANDDISPLAY",
            "COMMANDDISPLAYNAME",
            "COMMAND_DISPLAY_NAME",
            "COMMAND_DISPLAYNAME",
            "COMMAND_DISPLAY",
            "action_display_name",
            "action_displayname",
            "action_display",
            "action_displayName",
            "action_Display",
            "action_Display_Name",
            "action_DisplayName",
            "action_Displayname",
            "Action_Display",
            "Action_Display_Name",
            "Action_DisplayName",
            "Action_Displayname",
            "actionDisplay_name",
            "actionDisplay",
            "actiondisplay",
            "actionDisplayName",
            "actionDisplayname",
            "actiondisplayName",
            "actiondisplayname",
            "ActionDisplayName",
            "ActionDisplayname",
            "ActionDisplay",
            "action-display-name",
            "action-Display-Name",
            "action-displayName",
            "action-DisplayName",
            "action-displayname",
            "action-Displayname",
            "action-display",
            "action-Display",
            "Action-Display-Name",
            "Action-DisplayName",
            "Action-Displayname",
            "Action-Display",
            "ACTION-DISPLAY-NAME",
            "ACTION-DISPLAYNAME",
            "ACTION-DISPLAY",
            "ACTIONDISPLAY",
            "ACTIONDISPLAYNAME",
            "ACTION_DISPLAY_NAME",
            "ACTION_DISPLAYNAME",
            "ACTION_DISPLAY",
            "description",
            "Description",
            "DESCRIPTION",
            "summary",
            "Summary",
            "SUMMARY",
            "title",
            "help",
            "Help",
            "HELP",
            "help_text",
            "helpText",
            "helptext",
            "HelpText",
            "HELPTEXT",
            "command_description",
            "commandDescription",
            "commanddescription",
            "CommandDescription",
            "COMMANDDESCRIPTION",
            "COMMAND_DESCRIPTION",
            "action_description",
            "actionDescription",
            "actiondescription",
            "ActionDescription",
            "ACTIONDESCRIPTION",
            "ACTION_DESCRIPTION",
            "command_status",
            "command_Status",
            "command_STATUS",
            "commandStatus",
            "commandstatus",
            "CommandStatus",
            "Command_Status",
            "Command_STATUS",
            "COMMANDSTATUS",
            "COMMAND_STATUS",
            "command-status",
            "Command-Status",
            "command-STATUS",
            "Command-STATUS",
            "COMMAND-STATUS",
            "command_mode",
            "command_Mode",
            "command_MODE",
            "commandMode",
            "commandmode",
            "CommandMode",
            "Command_Mode",
            "Command_MODE",
            "COMMANDMODE",
            "COMMAND_MODE",
            "command-mode",
            "Command-Mode",
            "command-MODE",
            "Command-MODE",
            "COMMAND-MODE",
            "action_status",
            "action_Status",
            "action_STATUS",
            "actionStatus",
            "actionstatus",
            "ActionStatus",
            "Action_Status",
            "Action_STATUS",
            "ACTIONSTATUS",
            "ACTION_STATUS",
            "action-status",
            "Action-Status",
            "action-STATUS",
            "Action-STATUS",
            "ACTION-STATUS",
            "action_mode",
            "action_Mode",
            "action_MODE",
            "actionMode",
            "actionmode",
            "ActionMode",
            "Action_Mode",
            "Action_MODE",
            "ACTIONMODE",
            "ACTION_MODE",
            "action-mode",
            "Action-Mode",
            "action-MODE",
            "Action-MODE",
            "ACTION-MODE",
            "status",
            "Status",
            "STATUS",
            "state",
            "State",
            "STATE",
            "mode",
            "Mode",
            "MODE",
            "commandHelp",
            "COMMANDHELP",
            "CommandHelp",
            "commandhelp",
            "command-help",
            "Command-Help",
            "COMMAND-HELP",
            "command_help",
            "COMMAND_HELP",
            "actionHelp",
            "ACTIONHELP",
            "ActionHelp",
            "actionhelp",
            "action-help",
            "Action-Help",
            "ACTION-HELP",
            "action_help",
            "ACTION_HELP",
            "commandHelpText",
            "CommandHelpText",
            "commandhelptext",
            "command_help_text",
            "command_helpText",
            "command_HELPTEXT",
            "command_HelpText",
            "command_Helptext",
            "command_Help_Text",
            "command_HELP_TEXT",
            "command_HELP-TEXT",
            "Command_help_text",
            "Command_helpText",
            "Command_helptext",
            "Command_help-Text",
            "Command_HelpText",
            "Command_Helptext",
            "Command_Help_Text",
            "Command_HELP_TEXT",
            "Command_HELP-TEXT",
            "Command_HELPTEXT",
            "COMMANDHELPTEXT",
            "COMMAND_HELP_TEXT",
            "COMMAND_HELP-TEXT",
            "COMMAND_HELPTEXT",
            "command-help-text",
            "command-helptext",
            "command-helpText",
            "command-help_text",
            "command.help_text",
            "command-Helptext",
            "command-HelpText",
            "command-Help-Text",
            "command-HELP_TEXT",
            "command-HELP-TEXT",
            "Command-helptext",
            "Command-helpText",
            "Command-help_text",
            "Command-Helptext",
            "Command-HelpText",
            "Command-Help-Text",
            "Command-HELP_TEXT",
            "Command-HELP-TEXT",
            "COMMAND-HELPTEXT",
            "COMMAND-HELP_TEXT",
            "COMMAND-HELP-TEXT",
            "actionHelpText",
            "ActionHelpText",
            "actionhelptext",
            "action_help_text",
            "action_helpText",
            "action_HELPTEXT",
            "action_HelpText",
            "action_Helptext",
            "action_Help_Text",
            "action_HELP_TEXT",
            "action_HELP-TEXT",
            "Action_help_text",
            "Action_helpText",
            "Action_helptext",
            "Action_help-Text",
            "Action_HelpText",
            "Action_Helptext",
            "Action_Help_Text",
            "Action_HELP_TEXT",
            "Action_HELP-TEXT",
            "Action_HELPTEXT",
            "ACTIONHELPTEXT",
            "ACTION_HELP_TEXT",
            "ACTION_HELP-TEXT",
            "ACTION_HELPTEXT",
            "action-help-text",
            "action-helptext",
            "action-helpText",
            "action-help_text",
            "action.help_text",
            "action-Helptext",
            "action-HelpText",
            "action-Help-Text",
            "action-HELP_TEXT",
            "action-HELP-TEXT",
            "Action-helptext",
            "Action-helpText",
            "Action-help_text",
            "Action-Helptext",
            "Action-HelpText",
            "Action-Help-Text",
            "Action-HELP_TEXT",
            "Action-HELP-TEXT",
            "ACTION-HELPTEXT",
            "ACTION-HELP_TEXT",
            "ACTION-HELP-TEXT",
        )

        wrapper_keys = (
            "payload",
            "response",
            "result",
            "command",
            "Command",
            "COMMAND",
            "action",
            "Action",
            "ACTION",
            "item",
            "record",
            "commands",
            "Commands",
            "COMMANDS",
            "actions",
            "Actions",
            "ACTIONS",
            "list",
            "items",
            "results",
            "records",
            "data",
        )

        def _entry_has_command_hints(candidate: dict[str, Any]) -> bool:
            if any(hint in candidate for hint in command_hints):
                return True
            for key in wrapper_keys:
                nested = candidate.get(key)
                if isinstance(nested, dict) and any(
                    hint in nested for hint in command_hints
                ):
                    return True
            return False

        def _unwrap_command_row(row: dict[str, Any]) -> dict[str, Any]:
            current = row
            for _ in range(16):
                for key in wrapper_keys:
                    nested = current.get(key)
                    if isinstance(nested, dict):
                        current = nested
                        break
                    if isinstance(nested, list):
                        picked = next(
                            (
                                entry
                                for entry in nested
                                if isinstance(entry, dict)
                                and _entry_has_command_hints(entry)
                            ),
                            None,
                        )
                        if not picked:
                            picked = next(
                                (entry for entry in nested if isinstance(entry, dict)),
                                None,
                            )
                        if picked:
                            current = picked
                            break
                else:
                    break
            return current

        def _looks_like_command_row(candidate: dict[str, Any]) -> bool:
            return _entry_has_command_hints(candidate) or _entry_has_command_hints(
                _unwrap_command_row(candidate)
            )

        def _pick_command_dict(values: list[Any]) -> dict[str, Any] | None:
            first_dict = next((row for row in values if isinstance(row, dict)), None)
            if not isinstance(first_dict, dict):
                return None
            preferred = next(
                (
                    row
                    for row in values
                    if isinstance(row, dict) and _looks_like_command_row(row)
                ),
                None,
            )
            return preferred or first_dict

        if isinstance(payload, list):
            picked = _pick_command_dict(payload)
            return _unwrap_command_row(picked) if isinstance(picked, dict) else {}

        if not isinstance(payload, dict):
            return {}

        raw_data = payload.get("data") or payload.get("payload")
        if isinstance(raw_data, list):
            candidate = _pick_command_dict(raw_data)
            if isinstance(candidate, dict):
                return _unwrap_command_row(candidate)

        for key in (
            "payload",
            "response",
            "result",
            "command",
            "Command",
            "COMMAND",
            "action",
            "Action",
            "ACTION",
            "item",
            "record",
        ):
            candidate = payload.get(key)
            if isinstance(candidate, dict):
                return _unwrap_command_row(candidate)
            if isinstance(candidate, list):
                picked = _pick_command_dict(candidate)
                if picked:
                    return _unwrap_command_row(picked)

        for key in (
            "payload",
            "response",
            "result",
            "commands",
            "Commands",
            "COMMANDS",
            "actions",
            "Actions",
            "ACTIONS",
            "list",
            "items",
            "results",
            "records",
        ):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                picked = _pick_command_dict(candidate)
                if picked:
                    return _unwrap_command_row(picked)
            if isinstance(candidate, dict):
                return _unwrap_command_row(candidate)

        nested_data = raw_data
        if isinstance(nested_data, dict):
            for key in (
                "payload",
                "response",
                "result",
                "command",
                "Command",
                "COMMAND",
                "action",
                "Action",
                "ACTION",
                "item",
                "record",
                "data",
            ):
                candidate = nested_data.get(key)
                if isinstance(candidate, dict):
                    return _unwrap_command_row(candidate)
            for key in (
                "payload",
                "response",
                "result",
                "commands",
                "Commands",
                "COMMANDS",
                "actions",
                "Actions",
                "ACTIONS",
                "list",
                "items",
                "results",
                "records",
                "data",
            ):
                candidate = nested_data.get(key)
                if isinstance(candidate, list):
                    picked = _pick_command_dict(candidate)
                    if picked:
                        return _unwrap_command_row(picked)
                if isinstance(candidate, dict):
                    return _unwrap_command_row(candidate)
            if any(hint in nested_data for hint in command_hints):
                return nested_data

        if any(hint in payload for hint in command_hints):
            return payload

        return {}

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_app_id = app_id.strip()
    resolved_command_id = command_id.strip()
    resp = client.get_app_command(resolved_app_id, resolved_command_id)
    row = _extract_command_row(resp)

    view = {
        "commandId": str(
            row.get("command_id")
            or row.get("commandId")
            or row.get("CommandId")
            or row.get("CommandID")
            or row.get("COMMANDID")
            or row.get("COMMAND_ID")
            or row.get("commandID")
            or row.get("commandid")
            or row.get("action_id")
            or row.get("actionId")
            or row.get("ACTION_ID")
            or row.get("ActionId")
            or row.get("ActionID")
            or row.get("ACTIONID")
            or row.get("actionID")
            or row.get("actionid")
            or row.get("id")
            or row.get("zuid")
            or resolved_command_id
        ),
        "name": str(
            row.get("name")
            or row.get("CommandName")
            or row.get("commandName")
            or row.get("ActionName")
            or row.get("actionName")
            or row.get("COMMANDNAME")
            or row.get("ACTIONNAME")
            or row.get("COMMAND_NAME")
            or row.get("ACTION_NAME")
            or row.get("commandname")
            or row.get("actionname")
            or row.get("command_name")
            or row.get("command")
            or row.get("Command")
            or row.get("COMMAND")
            or row.get("action")
            or row.get("Action")
            or row.get("ACTION")
            or row.get("action_name")
            or row.get("display_name")
            or row.get("DisplayName")
            or row.get("displayName")
            or row.get("DISPLAYNAME")
            or row.get("DISPLAY_NAME")
            or row.get("displayname")
            or row.get("command_display_name")
            or row.get("command_displayname")
            or row.get("command_display")
            or row.get("command_displayName")
            or row.get("command_Display")
            or row.get("command_Display_Name")
            or row.get("command_DisplayName")
            or row.get("command_Displayname")
            or row.get("Command_Display")
            or row.get("Command_Display_Name")
            or row.get("Command_DisplayName")
            or row.get("Command_Displayname")
            or row.get("commandDisplay_name")
            or row.get("commandDisplay")
            or row.get("commanddisplay")
            or row.get("commandDisplayName")
            or row.get("commandDisplayname")
            or row.get("commanddisplayName")
            or row.get("commanddisplayname")
            or row.get("CommandDisplayName")
            or row.get("CommandDisplayname")
            or row.get("CommandDisplay")
            or row.get("command-display-name")
            or row.get("command-Display-Name")
            or row.get("command-displayName")
            or row.get("command-DisplayName")
            or row.get("command-displayname")
            or row.get("command-Displayname")
            or row.get("command-display")
            or row.get("command-Display")
            or row.get("Command-Display-Name")
            or row.get("Command-DisplayName")
            or row.get("Command-Displayname")
            or row.get("Command-Display")
            or row.get("COMMAND-DISPLAY-NAME")
            or row.get("COMMAND-DISPLAYNAME")
            or row.get("COMMAND-DISPLAY")
            or row.get("COMMANDDISPLAY")
            or row.get("COMMANDDISPLAYNAME")
            or row.get("COMMAND_DISPLAY_NAME")
            or row.get("COMMAND_DISPLAYNAME")
            or row.get("COMMAND_DISPLAY")
            or row.get("action_display_name")
            or row.get("action_displayname")
            or row.get("action_display")
            or row.get("action_displayName")
            or row.get("action_Display")
            or row.get("action_Display_Name")
            or row.get("action_DisplayName")
            or row.get("action_Displayname")
            or row.get("Action_Display")
            or row.get("Action_Display_Name")
            or row.get("Action_DisplayName")
            or row.get("Action_Displayname")
            or row.get("actionDisplay_name")
            or row.get("actionDisplay")
            or row.get("actiondisplay")
            or row.get("actionDisplayName")
            or row.get("actionDisplayname")
            or row.get("actiondisplayName")
            or row.get("actiondisplayname")
            or row.get("ActionDisplayName")
            or row.get("ActionDisplayname")
            or row.get("ActionDisplay")
            or row.get("action-display-name")
            or row.get("action-Display-Name")
            or row.get("action-displayName")
            or row.get("action-DisplayName")
            or row.get("action-displayname")
            or row.get("action-Displayname")
            or row.get("action-display")
            or row.get("action-Display")
            or row.get("Action-Display-Name")
            or row.get("Action-DisplayName")
            or row.get("Action-Displayname")
            or row.get("Action-Display")
            or row.get("ACTION-DISPLAY-NAME")
            or row.get("ACTION-DISPLAYNAME")
            or row.get("ACTION-DISPLAY")
            or row.get("ACTIONDISPLAY")
            or row.get("ACTIONDISPLAYNAME")
            or row.get("ACTION_DISPLAY_NAME")
            or row.get("ACTION_DISPLAYNAME")
            or row.get("ACTION_DISPLAY")
            or row.get("title")
            or ""
        ),
        "description": str(
            row.get("description")
            or row.get("summary")
            or row.get("Description")
            or row.get("Summary")
            or row.get("DESCRIPTION")
            or row.get("SUMMARY")
            or row.get("help_text")
            or row.get("helptext")
            or row.get("helpText")
            or row.get("HelpText")
            or row.get("help")
            or row.get("Help")
            or row.get("HELPTEXT")
            or row.get("HELP")
            or row.get("command_description")
            or row.get("commandDescription")
            or row.get("commanddescription")
            or row.get("CommandDescription")
            or row.get("COMMANDDESCRIPTION")
            or row.get("COMMAND_DESCRIPTION")
            or row.get("action_description")
            or row.get("actionDescription")
            or row.get("actiondescription")
            or row.get("ActionDescription")
            or row.get("ACTIONDESCRIPTION")
            or row.get("ACTION_DESCRIPTION")
            or row.get("command_help")
            or row.get("COMMAND_HELP")
            or row.get("commandHelp")
            or row.get("COMMANDHELP")
            or row.get("CommandHelp")
            or row.get("commandhelp")
            or row.get("command-help")
            or row.get("Command-Help")
            or row.get("COMMAND-HELP")
            or row.get("command_help_text")
            or row.get("command_helpText")
            or row.get("command_HELPTEXT")
            or row.get("command_HelpText")
            or row.get("command_Helptext")
            or row.get("command_Help_Text")
            or row.get("command_HELP_TEXT")
            or row.get("command_HELP-TEXT")
            or row.get("Command_help_text")
            or row.get("Command_helpText")
            or row.get("Command_helptext")
            or row.get("Command_help-Text")
            or row.get("Command_HelpText")
            or row.get("Command_Helptext")
            or row.get("Command_Help_Text")
            or row.get("Command_HELP_TEXT")
            or row.get("Command_HELP-TEXT")
            or row.get("Command_HELPTEXT")
            or row.get("commandHelpText")
            or row.get("CommandHelpText")
            or row.get("commandhelptext")
            or row.get("COMMANDHELPTEXT")
            or row.get("COMMAND_HELP_TEXT")
            or row.get("COMMAND_HELP-TEXT")
            or row.get("COMMAND_HELPTEXT")
            or row.get("command-help-text")
            or row.get("command-helptext")
            or row.get("command-helpText")
            or row.get("command-help_text")
            or row.get("command.help_text")
            or row.get("command-Helptext")
            or row.get("command-HelpText")
            or row.get("command-Help-Text")
            or row.get("command-HELP_TEXT")
            or row.get("command-HELP-TEXT")
            or row.get("Command-helptext")
            or row.get("Command-helpText")
            or row.get("Command-help_text")
            or row.get("Command-Helptext")
            or row.get("Command-HelpText")
            or row.get("Command-Help-Text")
            or row.get("Command-HELP_TEXT")
            or row.get("Command-HELP-TEXT")
            or row.get("COMMAND-HELPTEXT")
            or row.get("COMMAND-HELP_TEXT")
            or row.get("COMMAND-HELP-TEXT")
            or row.get("action_help")
            or row.get("ACTION_HELP")
            or row.get("actionHelp")
            or row.get("ACTIONHELP")
            or row.get("ActionHelp")
            or row.get("actionhelp")
            or row.get("action-help")
            or row.get("Action-Help")
            or row.get("ACTION-HELP")
            or row.get("action_help_text")
            or row.get("action_helpText")
            or row.get("action_HELPTEXT")
            or row.get("action_HelpText")
            or row.get("action_Helptext")
            or row.get("action_Help_Text")
            or row.get("action_HELP_TEXT")
            or row.get("action_HELP-TEXT")
            or row.get("Action_help_text")
            or row.get("Action_helpText")
            or row.get("Action_helptext")
            or row.get("Action_help-Text")
            or row.get("Action_HelpText")
            or row.get("Action_Helptext")
            or row.get("Action_Help_Text")
            or row.get("Action_HELP_TEXT")
            or row.get("Action_HELP-TEXT")
            or row.get("Action_HELPTEXT")
            or row.get("actionHelpText")
            or row.get("ActionHelpText")
            or row.get("actionhelptext")
            or row.get("ACTIONHELPTEXT")
            or row.get("ACTION_HELP_TEXT")
            or row.get("ACTION_HELP-TEXT")
            or row.get("ACTION_HELPTEXT")
            or row.get("action-help-text")
            or row.get("action-helptext")
            or row.get("action-helpText")
            or row.get("action-help_text")
            or row.get("action.help_text")
            or row.get("action-Helptext")
            or row.get("action-HelpText")
            or row.get("action-Help-Text")
            or row.get("action-HELP_TEXT")
            or row.get("action-HELP-TEXT")
            or row.get("Action-helptext")
            or row.get("Action-helpText")
            or row.get("Action-help_text")
            or row.get("Action-Helptext")
            or row.get("Action-HelpText")
            or row.get("Action-Help-Text")
            or row.get("Action-HELP_TEXT")
            or row.get("Action-HELP-TEXT")
            or row.get("ACTION-HELPTEXT")
            or row.get("ACTION-HELP_TEXT")
            or row.get("ACTION-HELP-TEXT")
            or ""
        ),
        "status": str(
            row.get("status")
            or row.get("state")
            or row.get("mode")
            or row.get("Status")
            or row.get("State")
            or row.get("Mode")
            or row.get("STATUS")
            or row.get("STATE")
            or row.get("MODE")
            or row.get("command_status")
            or row.get("command_Status")
            or row.get("command_STATUS")
            or row.get("commandStatus")
            or row.get("commandstatus")
            or row.get("CommandStatus")
            or row.get("Command_Status")
            or row.get("Command_STATUS")
            or row.get("COMMANDSTATUS")
            or row.get("COMMAND_STATUS")
            or row.get("command-status")
            or row.get("Command-Status")
            or row.get("command-STATUS")
            or row.get("Command-STATUS")
            or row.get("COMMAND-STATUS")
            or row.get("command_mode")
            or row.get("command_Mode")
            or row.get("command_MODE")
            or row.get("commandMode")
            or row.get("commandmode")
            or row.get("CommandMode")
            or row.get("Command_Mode")
            or row.get("Command_MODE")
            or row.get("COMMANDMODE")
            or row.get("COMMAND_MODE")
            or row.get("command-mode")
            or row.get("Command-Mode")
            or row.get("command-MODE")
            or row.get("Command-MODE")
            or row.get("COMMAND-MODE")
            or row.get("action_status")
            or row.get("action_Status")
            or row.get("action_STATUS")
            or row.get("actionStatus")
            or row.get("actionstatus")
            or row.get("ActionStatus")
            or row.get("Action_Status")
            or row.get("Action_STATUS")
            or row.get("ACTIONSTATUS")
            or row.get("ACTION_STATUS")
            or row.get("action-status")
            or row.get("Action-Status")
            or row.get("action-STATUS")
            or row.get("Action-STATUS")
            or row.get("ACTION-STATUS")
            or row.get("action_mode")
            or row.get("action_Mode")
            or row.get("action_MODE")
            or row.get("actionMode")
            or row.get("actionmode")
            or row.get("ActionMode")
            or row.get("Action_Mode")
            or row.get("Action_MODE")
            or row.get("ACTIONMODE")
            or row.get("ACTION_MODE")
            or row.get("action-mode")
            or row.get("Action-Mode")
            or row.get("action-MODE")
            or row.get("Action-MODE")
            or row.get("ACTION-MODE")
            or ""
        ),
        "raw": row,
    }

    utils.output(
        {
            "appId": resolved_app_id,
            "command": view,
        }
    )


@cliq_app.command("app-command-get-bridge-run")
def cliq_app_command_get_bridge_run(
    app_id: str = typer.Argument(..., help="Cliq app id."),
    command_id: str = typer.Argument(..., help="Cliq app command id."),
    action_id: Optional[str] = typer.Option(
        None,
        "--action-id",
        help="Optional membrane action id override.",
    ),
    bridge: str = typer.Option(
        "membrane",
        "--bridge",
        help="Bridge backend. Currently only 'membrane' is supported.",
    ),
    connection_id: Optional[str] = typer.Option(
        None,
        "--connection-id",
        help="Membrane connection ID. Overrides preset lookup when provided.",
    ),
    preset: Optional[str] = typer.Option(
        "zoho-cliq",
        "--preset",
        help="Connection preset alias (default: zoho-cliq).",
    ),
    input_json: Optional[str] = typer.Option(
        None,
        "--input-json",
        help="Optional JSON input passed to membrane --input (merged with appId + commandId).",
    ),
) -> None:
    """Run Cliq app-command detail through membrane bridge (explicit opt-in)."""
    if bridge.strip().lower() != "membrane":
        utils.error_exit(
            "unsupported_bridge",
            "Only --bridge membrane is supported right now.",
        )

    resolved_app_id = app_id.strip()
    if not resolved_app_id:
        utils.error_exit("invalid_app_id", "App id cannot be empty")

    resolved_command_id = command_id.strip()
    if not resolved_command_id:
        utils.error_exit("invalid_command_id", "Command id cannot be empty")

    resolved_action_id = (action_id or "").strip() or "app-command-get"

    cfg = _cfg()
    email = _S.account or _config.default_account(cfg)
    resolved_connection_id = _resolve_membrane_connection_id(
        connection_id=connection_id,
        preset=preset,
        cfg=cfg,
        email=email,
    )

    resolved_input: Any | None = None
    if input_json is not None:
        try:
            resolved_input = json.loads(input_json)
        except json.JSONDecodeError:
            utils.error_exit(
                "invalid_input_json",
                "--input-json must be a valid JSON object/string.",
            )

    if resolved_input is None:
        resolved_input = {
            "appId": resolved_app_id,
            "commandId": resolved_command_id,
        }
    elif isinstance(resolved_input, dict):
        resolved_input = dict(resolved_input)
        resolved_input.setdefault("appId", resolved_app_id)
        resolved_input.setdefault("commandId", resolved_command_id)
    else:
        utils.error_exit(
            "invalid_input_json",
            "--input-json must decode to a JSON object for app-command-get bridge runs.",
        )

    command: list[str] = [
        "action",
        "run",
        f"--connectionId={resolved_connection_id}",
        resolved_action_id,
        "--json",
        "--input",
        json.dumps(resolved_input, ensure_ascii=False),
    ]

    result = _run_membrane_command(command)
    utils.output(
        {
            "bridge": "membrane",
            "preset": _normalize_membrane_preset(preset or "zoho-cliq"),
            "connectionId": resolved_connection_id,
            "actionId": resolved_action_id,
            "appId": resolved_app_id,
            "commandId": resolved_command_id,
            "input": resolved_input,
            "result": result,
        }
    )


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

    def _extract_chat_rows(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]

        if not isinstance(payload, dict):
            return []

        candidates: list[Any] = [
            payload.get("list"),
            payload.get("chats"),
            payload.get("data"),
        ]
        nested_data = payload.get("data")
        if isinstance(nested_data, dict):
            candidates.extend(
                [
                    nested_data.get("list"),
                    nested_data.get("chats"),
                    nested_data.get("data"),
                ]
            )

        for candidate in candidates:
            if isinstance(candidate, list):
                return [row for row in candidate if isinstance(row, dict)]
        return []

    def _extract_messages(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]

        if not isinstance(payload, dict):
            return []

        candidates: list[Any] = [
            payload.get("messages"),
            payload.get("data"),
            payload.get("list"),
        ]
        nested_data = payload.get("data")
        if isinstance(nested_data, dict):
            candidates.extend(
                [
                    nested_data.get("messages"),
                    nested_data.get("data"),
                    nested_data.get("list"),
                ]
            )

        for candidate in candidates:
            if isinstance(candidate, list):
                return [row for row in candidate if isinstance(row, dict)]
        return []

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    payload: dict[str, Any]
    if (chat_id or "").strip():
        resolved_chat = (chat_id or "").strip()
        resp = client.export_chat_messages(resolved_chat)
        messages = _extract_messages(resp)
        payload = {
            "chatId": resolved_chat,
            "count": len(messages),
            "messages": messages,
        }
    else:
        resp = client.export_conversations()
        rows = _extract_chat_rows(resp)

        chats: list[dict[str, Any]] = []
        for row in rows:
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


@cliq_app.command("export-chats-bridge-run")
def cliq_export_chats_bridge_run(
    chat_id: Optional[str] = typer.Option(
        None,
        "--chat-id",
        help="Optional chat id. When set, default action switches to export-chat-messages.",
    ),
    action_id: Optional[str] = typer.Option(
        None,
        "--action-id",
        help="Optional membrane action id override.",
    ),
    bridge: str = typer.Option(
        "membrane",
        "--bridge",
        help="Bridge backend. Currently only 'membrane' is supported.",
    ),
    connection_id: Optional[str] = typer.Option(
        None,
        "--connection-id",
        help="Membrane connection ID. Overrides preset lookup when provided.",
    ),
    preset: Optional[str] = typer.Option(
        "zoho-cliq",
        "--preset",
        help="Connection preset alias (default: zoho-cliq).",
    ),
    input_json: Optional[str] = typer.Option(
        None,
        "--input-json",
        help="Optional JSON input passed to membrane --input (merged with chatId when --chat-id is provided).",
    ),
) -> None:
    """Run Cliq export-chats through membrane bridge (explicit opt-in)."""
    if bridge.strip().lower() != "membrane":
        utils.error_exit(
            "unsupported_bridge",
            "Only --bridge membrane is supported right now.",
        )

    resolved_chat_id = (chat_id or "").strip()
    resolved_action_id = (action_id or "").strip() or (
        "export-chat-messages" if resolved_chat_id else "export-conversations"
    )

    cfg = _cfg()
    email = _S.account or _config.default_account(cfg)
    resolved_connection_id = _resolve_membrane_connection_id(
        connection_id=connection_id,
        preset=preset,
        cfg=cfg,
        email=email,
    )

    resolved_input: Any | None = None
    if input_json is not None:
        try:
            resolved_input = json.loads(input_json)
        except json.JSONDecodeError:
            utils.error_exit(
                "invalid_input_json",
                "--input-json must be a valid JSON object/string.",
            )

    if resolved_chat_id:
        if resolved_input is None:
            resolved_input = {"chatId": resolved_chat_id}
        elif isinstance(resolved_input, dict):
            resolved_input = dict(resolved_input)
            resolved_input.setdefault("chatId", resolved_chat_id)
        else:
            utils.error_exit(
                "invalid_input_json",
                "--input-json must decode to a JSON object when --chat-id is provided.",
            )

    command: list[str] = [
        "action",
        "run",
        f"--connectionId={resolved_connection_id}",
        resolved_action_id,
        "--json",
    ]

    if resolved_input is not None:
        command.extend(
            [
                "--input",
                json.dumps(resolved_input, ensure_ascii=False),
            ]
        )

    result = _run_membrane_command(command)
    payload: dict[str, Any] = {
        "bridge": "membrane",
        "preset": _normalize_membrane_preset(preset or "zoho-cliq"),
        "connectionId": resolved_connection_id,
        "actionId": resolved_action_id,
        "chatId": resolved_chat_id or None,
        "result": result,
    }
    if resolved_input is not None:
        payload["input"] = resolved_input
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


@cliq_app.command("thread-create")
def cliq_thread_create(
    message_id: str = typer.Argument(..., help="Parent message id to anchor thread."),
    text: str = typer.Option(..., "--text", "-t", help="Thread message text."),
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
    """Create/send a thread message anchored to one parent message."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    resp = client.create_thread(
        message_id,
        text,
        chat_id=resolved_chat,
        channel_id=channel_id,
    )
    data = resp.get("data", resp)
    utils.output_status(
        "Cliq thread message sent",
        extra={
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "parentMessageId": message_id,
            "result": data,
        },
    )


@cliq_app.command("thread-reply")
def cliq_thread_reply(
    thread_id: str = typer.Argument(..., help="Thread id."),
    text: str = typer.Option(..., "--text", "-t", help="Reply text."),
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
    """Reply to a Cliq thread."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    resp = client.reply_thread(
        thread_id,
        text,
        chat_id=resolved_chat,
        channel_id=channel_id,
    )
    data = resp.get("data", resp)
    utils.output_status(
        "Cliq thread reply sent",
        extra={
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "threadId": thread_id,
            "result": data,
        },
    )


@cliq_app.command("threads")
def cliq_threads(
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Destination channel id (resolved to chat_id)."
    ),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Chat id."),
    message_id: Optional[str] = typer.Option(
        None,
        "--message-id",
        help="Optional parent message id for one-thread family listing.",
    ),
    limit: int = typer.Option(50, "--limit", "-n", help="Max rows to return."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List threads for one chat/channel, optionally scoped to one parent message."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    resp = client.list_threads(
        chat_id=resolved_chat,
        channel_id=channel_id,
        message_id=message_id,
        limit=limit,
    )

    data = resp.get("data", resp)
    threads: list[dict[str, Any]] = []
    if isinstance(data, list):
        threads = [item for item in data if isinstance(item, dict)]
    elif isinstance(data, dict):
        for key in ("threads", "data", "list", "items", "messages"):
            candidate = data.get(key)
            if isinstance(candidate, list):
                threads = [item for item in candidate if isinstance(item, dict)]
                break

    utils.output(
        {
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "messageId": (message_id or "").strip(),
            "count": len(threads),
            "threads": threads,
        }
    )


@cliq_app.command("schedule")
def cliq_schedule(
    text: str = typer.Option(..., "--text", "-t", help="Message text."),
    when: str = typer.Option(
        ...,
        "--when",
        help="Scheduled send time (ISO-8601 or provider-accepted timestamp).",
    ),
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Destination channel id (resolved to chat_id)."
    ),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Chat id."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Schedule one message for a chat/channel."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    resp = client.schedule_message(
        text,
        when,
        chat_id=resolved_chat,
        channel_id=channel_id,
    )

    data = resp.get("data", resp)
    scheduled_id = ""
    if isinstance(data, dict):
        for key in ("scheduled_id", "scheduledId", "id", "message_id", "messageId"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                scheduled_id = value.strip()
                break

    utils.output_status(
        "Cliq message scheduled",
        extra={
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "scheduledAt": when.strip(),
            "scheduledId": scheduled_id,
            "result": data,
        },
    )


@cliq_app.command("post-to-bot")
def cliq_post_to_bot(
    bot_id: str = typer.Argument(..., help="Bot id or unique name."),
    text: str = typer.Option(..., "--text", "-t", help="Message text."),
    title: Optional[str] = typer.Option(
        None,
        "--title",
        help="Optional title/context field for bot message payloads.",
    ),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Post one message to a bot."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    target_bot = bot_id.strip()
    resp = client.post_to_bot(target_bot, text, title=title)
    data = resp.get("data", resp)

    message_id = ""
    if isinstance(data, dict):
        for key in ("message_id", "messageId", "id"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                message_id = value.strip()
                break

    utils.output_status(
        "Cliq bot message sent",
        extra={
            "botId": target_bot,
            "messageId": message_id,
            "result": data,
        },
    )


@cliq_app.command("bot-subscribers")
def cliq_bot_subscribers(
    bot_id: str = typer.Argument(..., help="Bot id or unique name."),
    limit: int = typer.Option(50, "--limit", "-n", help="Max rows to return."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List subscribers/followers for one bot."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    target_bot = bot_id.strip()
    resp = client.list_bot_subscribers(target_bot, limit=limit)
    data = resp.get("data", resp)

    subscribers: list[dict[str, Any]] = []
    if isinstance(data, list):
        subscribers = [item for item in data if isinstance(item, dict)]
    elif isinstance(data, dict):
        for key in ("subscribers", "followers", "members", "data", "list", "items"):
            candidate = data.get(key)
            if isinstance(candidate, list):
                subscribers = [item for item in candidate if isinstance(item, dict)]
                break

    utils.output(
        {
            "botId": target_bot,
            "count": len(subscribers),
            "subscribers": subscribers,
        }
    )


@cliq_app.command("trigger-bot")
def cliq_trigger_bot(
    bot_id: str = typer.Argument(..., help="Bot id or unique name."),
    call_name: str = typer.Argument(..., help="Bot call/action name."),
    inputs_json: Optional[str] = typer.Option(
        None,
        "--inputs-json",
        help="Optional JSON object payload for bot call inputs.",
    ),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Trigger one named bot call/action."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    payload_inputs: dict[str, Any] = {}
    raw_inputs = (inputs_json or "").strip()
    if raw_inputs:
        try:
            parsed = json.loads(raw_inputs)
        except ValueError as exc:
            utils.error_exit(
                "invalid_inputs_json", f"inputs-json must be valid JSON: {exc}"
            )
        if not isinstance(parsed, dict):
            utils.error_exit(
                "invalid_inputs_json",
                "inputs-json must decode to a JSON object",
            )
        payload_inputs = parsed

    target_bot = bot_id.strip()
    target_call = call_name.strip()
    resp = client.trigger_bot_call(target_bot, target_call, inputs=payload_inputs)
    data = resp.get("data", resp)

    call_id = ""
    if isinstance(data, dict):
        for key in ("call_id", "callId", "id"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                call_id = value.strip()
                break

    utils.output_status(
        "Cliq bot call triggered",
        extra={
            "botId": target_bot,
            "callName": target_call,
            "callId": call_id,
            "result": data,
        },
    )


@cliq_app.command("scheduled")
def cliq_scheduled(
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Destination channel id (resolved to chat_id)."
    ),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Chat id."),
    limit: int = typer.Option(50, "--limit", "-n", help="Max rows to return."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List scheduled messages for one chat/channel."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    resp = client.list_scheduled_messages(
        chat_id=resolved_chat,
        channel_id=channel_id,
        limit=limit,
    )

    data = resp.get("data", resp)
    scheduled: list[dict[str, Any]] = []
    if isinstance(data, list):
        scheduled = [item for item in data if isinstance(item, dict)]
    elif isinstance(data, dict):
        for key in ("scheduled", "messages", "data", "list", "items"):
            candidate = data.get(key)
            if isinstance(candidate, list):
                scheduled = [item for item in candidate if isinstance(item, dict)]
                break

    utils.output(
        {
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "count": len(scheduled),
            "scheduled": scheduled,
        }
    )


@cliq_app.command("scheduled-get")
def cliq_scheduled_get(
    scheduled_id: str = typer.Argument(..., help="Scheduled message id."),
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Destination channel id (resolved to chat_id)."
    ),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Chat id."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Get one scheduled message by id."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    resp = client.get_scheduled_message(
        scheduled_id,
        chat_id=resolved_chat,
        channel_id=channel_id,
    )

    data = resp.get("data", resp)
    scheduled: dict[str, Any] | Any = data
    if isinstance(data, dict):
        for key in ("scheduled", "message", "item", "data"):
            candidate = data.get(key)
            if isinstance(candidate, dict):
                scheduled = candidate
                break
    elif isinstance(data, list):
        scheduled = next((item for item in data if isinstance(item, dict)), {})

    utils.output(
        {
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "scheduledId": scheduled_id,
            "scheduled": scheduled,
        }
    )


@cliq_app.command("scheduled-cancel")
def cliq_scheduled_cancel(
    scheduled_id: str = typer.Argument(..., help="Scheduled message id."),
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Destination channel id (resolved to chat_id)."
    ),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Chat id."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Cancel one scheduled message by id."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    resp = client.cancel_scheduled_message(
        scheduled_id,
        chat_id=resolved_chat,
        channel_id=channel_id,
    )
    data = resp.get("data", resp)

    utils.output_status(
        "Cliq scheduled message cancelled",
        extra={
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "scheduledId": scheduled_id,
            "result": data,
        },
    )


@cliq_app.command("leave")
def cliq_leave(
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Destination channel id (resolved to chat_id)."
    ),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Chat id."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Leave one chat/channel conversation."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    resp = client.leave_chat(chat_id=resolved_chat, channel_id=channel_id)
    data = resp.get("data", resp)

    utils.output_status(
        "Cliq conversation left",
        extra={
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "result": data,
        },
    )


@cliq_app.command("mute")
def cliq_mute(
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Destination channel id (resolved to chat_id)."
    ),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Chat id."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Mute one chat/channel conversation."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    resp = client.set_chat_mute(
        chat_id=resolved_chat, channel_id=channel_id, muted=True
    )
    data = resp.get("data", resp)

    utils.output_status(
        "Cliq conversation muted",
        extra={
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "muted": True,
            "result": data,
        },
    )


@cliq_app.command("unmute")
def cliq_unmute(
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Destination channel id (resolved to chat_id)."
    ),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Chat id."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Unmute one chat/channel conversation."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    resp = client.set_chat_mute(
        chat_id=resolved_chat,
        channel_id=channel_id,
        muted=False,
    )
    data = resp.get("data", resp)

    utils.output_status(
        "Cliq conversation unmuted",
        extra={
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "muted": False,
            "result": data,
        },
    )


@cliq_app.command("pin")
def cliq_pin(
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Destination channel id (resolved to chat_id)."
    ),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Chat id."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Pin one chat/channel conversation."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    resp = client.set_chat_pin(
        chat_id=resolved_chat, channel_id=channel_id, pinned=True
    )
    data = resp.get("data", resp)

    utils.output_status(
        "Cliq conversation pinned",
        extra={
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "pinned": True,
            "result": data,
        },
    )


@cliq_app.command("unpin")
def cliq_unpin(
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Destination channel id (resolved to chat_id)."
    ),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Chat id."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Unpin one chat/channel conversation."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    resp = client.set_chat_pin(
        chat_id=resolved_chat,
        channel_id=channel_id,
        pinned=False,
    )
    data = resp.get("data", resp)

    utils.output_status(
        "Cliq conversation unpinned",
        extra={
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "pinned": False,
            "result": data,
        },
    )


@cliq_app.command("pinned")
def cliq_pinned(
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Destination channel id (resolved to chat_id)."
    ),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Chat id."),
    limit: int = typer.Option(50, "--limit", "-n", help="Max rows to return."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List pinned messages for one chat/channel conversation."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    resp = client.list_pinned_messages(
        chat_id=resolved_chat,
        channel_id=channel_id,
        limit=limit,
    )

    data = resp.get("data", resp)
    pinned_messages: list[dict[str, Any]] = []
    if isinstance(data, list):
        pinned_messages = [item for item in data if isinstance(item, dict)]
    elif isinstance(data, dict):
        for key in (
            "pinned",
            "messages",
            "items",
            "data",
            "list",
            "pins",
        ):
            candidate = data.get(key)
            if isinstance(candidate, list):
                pinned_messages = [item for item in candidate if isinstance(item, dict)]
                break

    utils.output(
        {
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "count": len(pinned_messages),
            "pinnedMessages": pinned_messages,
        }
    )


@cliq_app.command("thread-followers")
def cliq_thread_followers(
    thread_id: str = typer.Argument(..., help="Thread id."),
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Destination channel id (resolved to chat_id)."
    ),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Chat id."),
    limit: int = typer.Option(50, "--limit", "-n", help="Max rows to return."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List followers/subscribers for one thread."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    resp = client.list_thread_followers(
        thread_id,
        chat_id=resolved_chat,
        channel_id=channel_id,
        limit=limit,
    )

    data = resp.get("data", resp)
    followers: list[dict[str, Any]] = []
    if isinstance(data, list):
        followers = [item for item in data if isinstance(item, dict)]
    elif isinstance(data, dict):
        for key in ("followers", "members", "subscribers", "data", "list", "items"):
            candidate = data.get(key)
            if isinstance(candidate, list):
                followers = [item for item in candidate if isinstance(item, dict)]
                break

    utils.output(
        {
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "threadId": thread_id,
            "count": len(followers),
            "followers": followers,
        }
    )


@cliq_app.command("thread-state")
def cliq_thread_state(
    thread_id: str = typer.Argument(..., help="Thread id."),
    state: Optional[str] = typer.Option(
        None,
        "--state",
        help="Target state to set (omit to read current state payload).",
    ),
    channel_id: Optional[str] = typer.Option(
        None, "--channel-id", help="Destination channel id (resolved to chat_id)."
    ),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Chat id."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Get or set thread state."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    if (state or "").strip():
        resp = client.update_thread_state(
            thread_id,
            (state or "").strip(),
            chat_id=resolved_chat,
            channel_id=channel_id,
        )
        data = resp.get("data", resp)
        utils.output_status(
            "Cliq thread state updated",
            extra={
                "chatId": resolved_chat or "",
                "channelId": channel_id or "",
                "threadId": thread_id,
                "state": (state or "").strip(),
                "result": data,
            },
        )
        return

    resp = client.get_thread_state(
        thread_id,
        chat_id=resolved_chat,
        channel_id=channel_id,
    )
    data = resp.get("data", resp)
    state_view = ""
    if isinstance(data, dict):
        state_view = str(
            data.get("state")
            or data.get("thread_state")
            or data.get("threadState")
            or data.get("status")
            or ""
        )

    utils.output(
        {
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "threadId": thread_id,
            "state": state_view,
            "thread": data,
        }
    )


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


@crm_app.command("bridge-run")
def crm_bridge_run(
    action_id: str = typer.Argument(
        ..., help="Membrane action id (for example: list-records)."
    ),
    bridge: str = typer.Option(
        "membrane",
        "--bridge",
        help="Bridge backend. Currently only 'membrane' is supported.",
    ),
    connection_id: Optional[str] = typer.Option(
        None,
        "--connection-id",
        help="Membrane connection ID. Overrides preset lookup when provided.",
    ),
    preset: Optional[str] = typer.Option(
        "zoho-crm",
        "--preset",
        help="Connection preset alias (default: zoho-crm).",
    ),
    input_json: Optional[str] = typer.Option(
        None,
        "--input-json",
        help="JSON string passed to membrane --input.",
    ),
) -> None:
    """Run one CRM action through membrane bridge (explicit opt-in)."""
    if bridge.strip().lower() != "membrane":
        utils.error_exit(
            "unsupported_bridge",
            "Only --bridge membrane is supported right now.",
        )

    cfg = _cfg()
    email = _S.account or _config.default_account(cfg)
    resolved_connection_id = _resolve_membrane_connection_id(
        connection_id=connection_id,
        preset=preset,
        cfg=cfg,
        email=email,
    )

    command: list[str] = [
        "action",
        "run",
        f"--connectionId={resolved_connection_id}",
        action_id,
        "--json",
    ]

    if input_json is not None:
        try:
            json.loads(input_json)
        except json.JSONDecodeError:
            utils.error_exit(
                "invalid_input_json",
                "--input-json must be a valid JSON object/string.",
            )
        command.extend(["--input", input_json])

    result = _run_membrane_command(command)
    utils.output(
        {
            "bridge": "membrane",
            "preset": _normalize_membrane_preset(preset or "zoho-crm"),
            "connectionId": resolved_connection_id,
            "actionId": action_id,
            "result": result,
        }
    )


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
