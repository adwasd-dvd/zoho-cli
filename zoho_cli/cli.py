"""zoho CLI — all subcommands.

Output:
- Default → JSON to stdout (pipe-friendly, agent-friendly)
- --md    → Markdown tables/text
- stderr  → errors, debug, interactive prompts (never pollutes stdout)
"""

# ruff: noqa: E402

from __future__ import annotations

import contextlib
from datetime import datetime, timezone
from functools import partial
import io
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
from zoho_cli.commands import (
    register_cliq_app_catalog_bridge_commands,
    register_builtin_root_typers,
    register_cliq_app_catalog_commands,
    register_cliq_app_commands_bridge_commands,
    register_cliq_app_commands_commands,
    register_cliq_channel_lifecycle_commands,
    register_cliq_channel_unarchive_commands,
    register_cliq_channel_member_management_commands,
    register_cliq_channel_metadata_commands,
    register_cliq_channel_membership_commands,
    register_cliq_message_discovery_commands,
    register_cliq_file_voice_commands,
    register_cliq_messages_message_commands,
    register_cliq_context_watch_context_commands,
    register_cliq_watch_act_commands,
    register_cliq_voice_send_commands,
    register_cliq_reply_edit_commands,
    register_cliq_delete_react_commands,
    register_cliq_mark_read_commands,
    register_cliq_mute_unmute_commands,
    register_cliq_pinned_commands,
    register_cliq_pin_unpin_commands,
    register_cliq_scheduled_cancel_leave_commands,
    register_cliq_scheduled_lifecycle_commands,
    register_cliq_bridge_run_commands,
    register_cliq_capabilities_commands,
    register_cliq_channels_chats_commands,
    register_cliq_users_teams_commands,
    register_cliq_departments_roles_commands,
    register_cliq_designations_user_status_commands,
    register_cliq_userfields_commands,
    register_cliq_events_reminders_commands,
    register_cliq_meetings_databases_commands,
    register_cliq_widgets_map_tickers_commands,
    register_cliq_custom_domains_emails_commands,
    register_cliq_status_commands,
    register_cliq_thread_commands,
    register_cliq_threads_commands,
    register_cliq_post_to_bot_commands,
    register_cliq_bot_subscribers_commands,
    register_cliq_trigger_bot_commands,
    register_cliq_notify_mail_commands,
    register_cliq_thread_state_commands,
    register_cliq_export_commands,
    register_cliq_identity_commands,
    register_cliq_app_installs_bridge_commands,
    register_cliq_app_installs_commands,
    register_cliq_app_permissions_commands,
    register_cliq_app_permissions_bridge_commands,
)
from zoho_cli.commands.cliq_readiness import (
    CliqReadinessContext,
    build_cliq_capabilities_command,
    build_cliq_status_command,
)
from zoho_cli.commands.cliq_identity import (
    CliqIdentityContext,
    build_cliq_user_resolve_command,
    build_cliq_whoami_command,
)
from zoho_cli.commands.cliq_org_directory import (
    CliqOrgDirectoryContext,
    build_cliq_teams_command,
    build_cliq_users_command,
)
from zoho_cli.commands.cliq_productivity import (
    CliqProductivityContext,
    build_cliq_databases_command,
    build_cliq_events_command,
    build_cliq_meetings_command,
    build_cliq_reminders_command,
)
from zoho_cli.commands.cliq_platform_extensions import (
    CliqPlatformExtensionsContext,
    build_cliq_custom_domains_command,
    build_cliq_custom_emails_command,
    build_cliq_map_tickers_command,
    build_cliq_widgets_command,
)
from zoho_cli.commands.cliq_channel_management import (
    CliqChannelManagementContext,
    build_cliq_channel_archive_command,
    build_cliq_channel_create_command,
    build_cliq_channel_delete_command,
    build_cliq_channel_rename_command,
    build_cliq_channel_topic_command,
    build_cliq_channel_unarchive_command,
    build_cliq_leave_command,
    build_cliq_member_add_command,
    build_cliq_member_remove_command,
    build_cliq_members_command,
    build_cliq_mute_command,
    build_cliq_pin_command,
    build_cliq_pinned_command,
    build_cliq_unpin_command,
    build_cliq_unmute_command,
)
from zoho_cli.commands.cliq_threading import (
    CliqThreadingContext,
    build_cliq_thread_create_command,
    build_cliq_thread_followers_command,
    build_cliq_thread_reply_command,
    build_cliq_thread_state_command,
    build_cliq_threads_command,
)
from zoho_cli.commands.cliq_scheduling import (
    CliqSchedulingContext,
    build_cliq_schedule_command,
    build_cliq_scheduled_cancel_command,
    build_cliq_scheduled_command,
    build_cliq_scheduled_get_command,
)
from zoho_cli.commands.cliq_bots import (
    CliqBotsContext,
    build_cliq_bot_subscribers_command,
    build_cliq_post_to_bot_command,
    build_cliq_trigger_bot_command,
)
from zoho_cli.commands.cliq_message_retrieval import (
    CliqMessageRetrievalContext,
    build_cliq_context_command,
    build_cliq_message_command,
    build_cliq_messages_command,
    build_cliq_search_command,
    build_cliq_watch_context_command,
)
from zoho_cli.commands.cliq_org_admin import (
    CliqOrgAdminContext,
    build_cliq_departments_command,
    build_cliq_designations_command,
    build_cliq_roles_command,
    build_cliq_user_status_command,
    build_cliq_userfields_command,
)
from zoho_cli.crm import ZohoCrmClient
from zoho_cli.registry import register_root_commands


_CLIQ_STATUS_REACTION_MAP: dict[str, str] = {
    "received": "👀",
    "thinking": "🤔",
    "writing": "✏️",
    "testing": "🧪",
    "blocked": "⚠️",
    "done": "✅",
    "failed": "❌",
}
_CLIQ_STATUS_REACTION_ALIASES: dict[str, str] = {
    "seen": "received",
    "read": "received",
    "analyse": "thinking",
    "analyze": "thinking",
    "draft": "writing",
    "verify": "testing",
    "complete": "done",
    "completed": "done",
    "error": "failed",
}


def _cliq_status_tracker_path() -> Path:
    override = (os.environ.get("ZOHO_CLIQ_STATUS_TRACKER_PATH") or "").strip()
    if override:
        return Path(override).expanduser()
    return _config.config_path().parent / "cliq_message_status_tracker.json"


def _read_cliq_status_tracker() -> dict[str, Any]:
    path = _cliq_status_tracker_path()
    if not path.exists():
        return {"version": 1, "messages": {}}

    try:
        raw = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return {"version": 1, "messages": {}}

    if not raw:
        return {"version": 1, "messages": {}}

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {"version": 1, "messages": {}}

    if not isinstance(payload, dict):
        return {"version": 1, "messages": {}}

    messages = payload.get("messages")
    if not isinstance(messages, dict):
        messages = {}

    return {
        "version": int(payload.get("version") or 1),
        "messages": messages,
    }


def _write_cliq_status_tracker(payload: dict[str, Any]) -> None:
    path = _cliq_status_tracker_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _normalize_cliq_status_key(raw_status: str) -> str:
    key = raw_status.strip().lower()
    if not key:
        return ""
    if key in _CLIQ_STATUS_REACTION_MAP:
        return key
    return _CLIQ_STATUS_REACTION_ALIASES.get(key, "")


def _cliq_status_tracker_key(
    *, base_url: str, chat_id: str, channel_id: str, message_id: str
) -> str:
    return (
        f"{base_url.strip()}::{chat_id.strip()}::{channel_id.strip()}::"
        f"{message_id.strip()}"
    )


def _apply_cliq_status_reaction(
    client: ZohoCliqClient,
    *,
    email: str,
    message_id: str,
    status: str,
    chat_id: str,
    channel_id: str,
    clear_known: bool = True,
) -> dict[str, Any]:
    normalized_status = _normalize_cliq_status_key(status)
    if not normalized_status:
        utils.error_exit(
            "invalid_status",
            "Unsupported --status value. Use one of: received, thinking, writing, testing, blocked, done, failed.",
        )

    target_message_id = message_id.strip()
    if not target_message_id:
        utils.error_exit("invalid_message_id", "message_id cannot be empty")

    target_emoji = _CLIQ_STATUS_REACTION_MAP[normalized_status]
    tracker = _read_cliq_status_tracker()
    messages = tracker.get("messages")
    if not isinstance(messages, dict):
        messages = {}

    entry_key = _cliq_status_tracker_key(
        base_url=client.base_url,
        chat_id=chat_id,
        channel_id=channel_id,
        message_id=target_message_id,
    )
    current_entry = messages.get(entry_key)
    if not isinstance(current_entry, dict):
        current_entry = {}

    previous_status = str(current_entry.get("status") or "")
    previous_emoji = str(current_entry.get("emoji") or "")

    tracked_emojis: list[str] = []
    if previous_emoji:
        tracked_emojis.append(previous_emoji)
    if clear_known:
        for known_emoji in sorted(set(_CLIQ_STATUS_REACTION_MAP.values())):
            if known_emoji not in tracked_emojis:
                tracked_emojis.append(known_emoji)

    reaction_result = client.set_message_status_reaction(
        target_message_id,
        emoji=target_emoji,
        tracked_status_emojis=tracked_emojis,
        chat_id=chat_id,
        channel_id=channel_id,
    )
    data = reaction_result.get("result", {})

    now = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    messages[entry_key] = {
        "status": normalized_status,
        "emoji": target_emoji,
        "updatedAt": now,
        "messageId": target_message_id,
        "chatId": chat_id,
        "channelId": channel_id,
        "account": email,
    }
    tracker["messages"] = messages
    tracker["version"] = 1
    _write_cliq_status_tracker(tracker)

    return {
        "messageId": target_message_id,
        "statusKey": normalized_status,
        "emoji": target_emoji,
        "previousStatus": previous_status,
        "previousEmoji": previous_emoji,
        "removed": reaction_result.get("removed", []),
        "removeErrors": reaction_result.get("removeFailures", []),
        "result": data,
    }


def _apply_cliq_status_reaction_best_effort(
    client: ZohoCliqClient,
    *,
    email: str,
    message_id: str,
    status: str,
    chat_id: str,
    channel_id: str,
    clear_known: bool = True,
) -> dict[str, Any]:
    try:
        payload = _apply_cliq_status_reaction(
            client,
            email=email,
            message_id=message_id,
            status=status,
            chat_id=chat_id,
            channel_id=channel_id,
            clear_known=clear_known,
        )
        return {
            "applied": True,
            **payload,
        }
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 1
        return {
            "applied": False,
            "messageId": message_id,
            "statusKey": _normalize_cliq_status_key(status),
            "error": "status_reaction_failed",
            "exitCode": exit_code,
        }


def _unsupported_counter(entry: dict[str, Any]) -> int:
    try:
        return max(0, int(entry.get("unsupportedConsecutiveCount") or 0))
    except (TypeError, ValueError):
        return 0


def _should_use_mark_read_status_fallback(
    client: ZohoCliqClient,
    *,
    unsupported_entry_before: dict[str, Any],
) -> bool:
    unsupported_entry_after = client._read_operation_unsupported_entry(  # noqa: SLF001
        "message-read-ack"
    )
    if not isinstance(unsupported_entry_after, dict):
        return False

    last_signal = (
        str(unsupported_entry_after.get("lastUnsupportedSignal") or "").strip().lower()
    )
    if last_signal not in {"not_supported", "unsupported"}:
        return False

    if bool(unsupported_entry_after.get("postReleaseDeferred")):
        return True

    return _unsupported_counter(unsupported_entry_after) > _unsupported_counter(
        unsupported_entry_before
    )


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
    help=(
        f"Zoho CLI (v{_get_version()}) — unified multi-product CLI for Mail, Cliq, "
        "and CRM.\n"
        "Use module-first commands: `zoho mail ...`, `zoho cliq ...`, "
        "`zoho crm ...`."
    ),
)
mail_app = typer.Typer(
    no_args_is_help=True,
    help=(
        "Mail module commands. Includes message operations plus mail support "
        "subgroups (`zoho mail attachment`, `zoho mail folders`, "
        "`zoho mail labels`)."
    ),
)
attachment_subapp = typer.Typer(
    no_args_is_help=True,
    name="attachment",
    help="Mail attachment utilities (download and parse).",
)
folders_app = typer.Typer(
    no_args_is_help=True,
    help="Mail folder lifecycle operations.",
)
labels_app = typer.Typer(
    no_args_is_help=True,
    help="Mail label lifecycle operations.",
)
cliq_app = typer.Typer(
    no_args_is_help=True,
    help="Cliq module operations.",
)
crm_app = typer.Typer(
    no_args_is_help=True,
    help="CRM module operations.",
)
config_app = typer.Typer(no_args_is_help=True, help="Configuration helpers.")
membrane_app = typer.Typer(
    no_args_is_help=True,
    help="Membrane bridge operations.",
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


class _CliqState:
    network: Optional[str] = None


_CLIQ = _CliqState()


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


@cliq_app.callback()
def _cliq_global(
    network: Optional[str] = typer.Option(
        None,
        "--network",
        help=(
            "Default Cliq network slug for this invocation."
            " You can still override with per-command --network."
        ),
    ),
) -> None:
    """Set Cliq module-scoped defaults."""
    _CLIQ.network = network


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
    cid = (cfg.get("client_id") or os.environ.get("ZOHO_CLIENT_ID") or "").strip()
    csec = (
        cfg.get("client_secret") or os.environ.get("ZOHO_CLIENT_SECRET") or ""
    ).strip()
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
    resolved_network = network or _CLIQ.network or account_cfg.get("cliq_network")
    return ZohoCliqClient(
        access_token,
        base_url=_cliq.infer_cliq_base_url(
            mail_base_url=account_cfg.get("mail_base_url"),
            accounts_server=account_cfg.get("accounts_server"),
            network=resolved_network,
        ),
    )


def _collect_configured_cliq_targets(
    cfg: dict,
) -> tuple[list[dict[str, Any]], list[str]]:
    accounts_cfg = cfg.get("accounts", {}) or {}
    default_account = _config.default_account(cfg)
    account_rows: list[dict[str, Any]] = []
    seen_networks: set[str] = set()

    for email in sorted(accounts_cfg):
        account_cfg = accounts_cfg.get(email, {}) or {}
        network = str(account_cfg.get("cliq_network") or "").strip()
        if network:
            seen_networks.add(network)
        account_rows.append(
            {
                "email": email,
                "isDefault": email == default_account,
                "cliqNetwork": network,
                "hasCliqNetwork": bool(network),
            }
        )

    return account_rows, sorted(seen_networks)


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
        "label_not_found",
        f"Label '{name_or_id}' not found. Run: zoho mail labels list",
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
        help="Include Cliq chat export OAuth scopes in this login flow.",
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
        _stderr("  zoho mail folders list")
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


_cliq_readiness_context = CliqReadinessContext(
    load_config=_cfg,
    selected_account=lambda: _S.account,
    selected_config_path=lambda: _S.config_path,
    selected_network=lambda: _CLIQ.network,
    default_account=_config.default_account,
    collect_configured_targets=_collect_configured_cliq_targets,
    require_credentials=_require_credentials,
    refresh_access_token_info=lambda *args, **kwargs: auth.refresh_access_token_info(
        *args, **kwargs
    ),
    require_account=_require_account,
    get_cliq_client=_get_cliq_client,
)


cliq_status = build_cliq_status_command(_cliq_readiness_context)


register_cliq_status_commands(
    cliq_app,
    cliq_status_command=cliq_status,
)


def _build_action_source_metadata(source: str, source_path: str) -> dict[str, Any]:
    normalized_source = str(source or "").strip()
    normalized_source_path = str(source_path or "").strip()
    return {
        "source": normalized_source,
        "sourcePath": normalized_source_path,
        "fromWatchLoopHint": normalized_source == "watch-loop-hint",
        "fromEscalationHint": normalized_source == "escalation-hint",
        "fromExplicitOverride": normalized_source == "explicit-override",
    }


def _extract_watch_intake_with_source(
    watch_payload: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    watch_intake = watch_payload.get("watchIntake")
    if isinstance(watch_intake, dict):
        return watch_intake, "watchIntake"

    snake_watch_intake = watch_payload.get("watch_intake")
    if isinstance(snake_watch_intake, dict):
        return snake_watch_intake, "watch_intake"

    kebab_watch_intake = watch_payload.get("watch-intake")
    if isinstance(kebab_watch_intake, dict):
        return kebab_watch_intake, "watch-intake"

    return {}, ""


def _extract_operator_workflow_with_source(
    watch_payload: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    workflow = watch_payload.get("operatorWorkflow")
    if isinstance(workflow, dict):
        return workflow, "operatorWorkflow"

    snake_workflow = watch_payload.get("operator_workflow")
    if isinstance(snake_workflow, dict):
        return snake_workflow, "operator_workflow"

    kebab_workflow = watch_payload.get("operator-workflow")
    if isinstance(kebab_workflow, dict):
        return kebab_workflow, "operator-workflow"

    return {}, ""


def _extract_watch_consume_with_source(
    watch_intake: dict[str, Any],
    watch_intake_source_root: str,
) -> tuple[dict[str, Any], str]:
    for alias in ("consume", "consumePolicy", "consume_policy", "consume-policy"):
        candidate = watch_intake.get(alias)
        if isinstance(candidate, dict):
            return candidate, f"{watch_intake_source_root}.{alias}"

    buckets: dict[str, list[tuple[dict[str, Any], str]]] = {
        "consume": [],
        "consumepolicy": [],
    }
    for key, value in watch_intake.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        normalized_key = "".join(ch for ch in key.lower() if ch.isalnum())
        if normalized_key in buckets:
            buckets[normalized_key].append((value, key))

    for normalized_key in ("consume", "consumepolicy"):
        for candidate, source_key in buckets[normalized_key]:
            return candidate, f"{watch_intake_source_root}.{source_key}"

    return {}, ""


def _collect_action_id_like_candidates(
    payload: dict[str, Any],
    source_root: str,
) -> list[tuple[Any, str]]:
    if not isinstance(payload, dict) or not source_root:
        return []

    buckets: dict[str, list[tuple[Any, str]]] = {
        "bridgeactionid": [],
        "actionid": [],
        "defaultactionid": [],
    }

    for key, value in payload.items():
        if not isinstance(key, str):
            continue
        normalized = "".join(ch for ch in key.lower() if ch.isalnum())
        if normalized in buckets:
            buckets[normalized].append((value, f"{source_root}.{key}"))

    candidates: list[tuple[Any, str]] = []
    for normalized in ("bridgeactionid", "actionid", "defaultactionid"):
        candidates.extend(buckets[normalized])
    return candidates


def cliq_bridge_run(
    action_id: Optional[str] = typer.Argument(
        None,
        help=(
            "Membrane action id (for example: post-message). Optional when "
            "--watch-file includes an action hint."
        ),
    ),
    action_override: Optional[str] = typer.Option(
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
        help="JSON string passed to membrane --input.",
    ),
    watch_file: Optional[str] = typer.Option(
        None,
        "--watch-file",
        help=(
            "Optional watch-context JSON payload path (use '-' for stdin). "
            "When provided, watch payload + watchIntake metadata are forwarded "
            "to bridge input."
        ),
    ),
    escalation_action: bool = typer.Option(
        False,
        "--escalation-action",
        help=(
            "Prefer explicit escalation action hints from operatorWorkflow when "
            "resolving action id from --watch-file metadata."
        ),
    ),
    status_flow: bool = typer.Option(
        False,
        "--status-flow/--no-status-flow",
        help=(
            "Pass watch-act status-flow preference through bridge input when "
            "--watch-file is provided."
        ),
    ),
) -> None:
    """Run one Cliq action through membrane bridge (explicit opt-in)."""
    if bridge.strip().lower() != "membrane":
        utils.error_exit(
            "unsupported_bridge",
            "Only --bridge membrane is supported right now.",
        )

    watch_payload: dict[str, Any] | None = None
    if watch_file is not None:
        source = watch_file.strip()
        raw = ""
        if source == "-":
            raw = sys.stdin.read()
        else:
            payload_path = Path(source)
            if not payload_path.exists():
                utils.error_exit("file_not_found", f"Watch payload not found: {source}")
            raw = payload_path.read_text()

        try:
            decoded_watch = json.loads(raw)
        except json.JSONDecodeError as exc:
            utils.error_exit(
                "invalid_watch_payload",
                f"Invalid JSON payload: {exc}",
            )

        if not isinstance(decoded_watch, dict):
            utils.error_exit(
                "invalid_watch_payload",
                "Watch payload must be a JSON object",
            )
        watch_payload = decoded_watch

    action_hint = ""
    action_hint_source = ""
    action_hint_source_path = ""
    if watch_payload is not None:
        watch_candidates: list[tuple[Any, str]] = [
            (watch_payload.get("actionId"), "watchPayload.actionId"),
            (watch_payload.get("actionid"), "watchPayload.actionid"),
            (watch_payload.get("actionID"), "watchPayload.actionID"),
            (watch_payload.get("action_id"), "watchPayload.action_id"),
            (watch_payload.get("action"), "watchPayload.action"),
            (watch_payload.get("bridgeActionId"), "watchPayload.bridgeActionId"),
            (watch_payload.get("bridgeActionid"), "watchPayload.bridgeActionid"),
            (watch_payload.get("bridgeActionID"), "watchPayload.bridgeActionID"),
            (watch_payload.get("bridgeAction_id"), "watchPayload.bridgeAction_id"),
            (
                watch_payload.get("bridge-action-id"),
                "watchPayload.bridge-action-id",
            ),
            (
                watch_payload.get("bridge-action_id"),
                "watchPayload.bridge-action_id",
            ),
            (
                watch_payload.get("bridge-actionid"),
                "watchPayload.bridge-actionid",
            ),
            (
                watch_payload.get("bridge-actionId"),
                "watchPayload.bridge-actionId",
            ),
            (
                watch_payload.get("bridge-actionID"),
                "watchPayload.bridge-actionID",
            ),
            (watch_payload.get("bridge_actionid"), "watchPayload.bridge_actionid"),
            (watch_payload.get("bridge_actionID"), "watchPayload.bridge_actionID"),
            (
                watch_payload.get("bridge_action_id"),
                "watchPayload.bridge_action_id",
            ),
            (watch_payload.get("bridge_actionId"), "watchPayload.bridge_actionId"),
            (watch_payload.get("defaultAction"), "watchPayload.defaultAction"),
            (watch_payload.get("default_action"), "watchPayload.default_action"),
            (watch_payload.get("default-action"), "watchPayload.default-action"),
            (
                watch_payload.get("default-action-id"),
                "watchPayload.default-action-id",
            ),
            (
                watch_payload.get("default-action_id"),
                "watchPayload.default-action_id",
            ),
            (
                watch_payload.get("default-actionid"),
                "watchPayload.default-actionid",
            ),
            (
                watch_payload.get("default-actionId"),
                "watchPayload.default-actionId",
            ),
            (
                watch_payload.get("default-actionID"),
                "watchPayload.default-actionID",
            ),
            (watch_payload.get("defaultActionId"), "watchPayload.defaultActionId"),
            (watch_payload.get("defaultActionid"), "watchPayload.defaultActionid"),
            (watch_payload.get("defaultActionID"), "watchPayload.defaultActionID"),
            (watch_payload.get("defaultAction_id"), "watchPayload.defaultAction_id"),
            (
                watch_payload.get("default_action_id"),
                "watchPayload.default_action_id",
            ),
            (
                watch_payload.get("default_actionid"),
                "watchPayload.default_actionid",
            ),
            (watch_payload.get("default_actionId"), "watchPayload.default_actionId"),
            (
                watch_payload.get("default_actionID"),
                "watchPayload.default_actionID",
            ),
        ]
        intake, intake_source_root = _extract_watch_intake_with_source(watch_payload)
        if isinstance(intake, dict):
            bridge_cfg = intake.get("bridge")
            if isinstance(bridge_cfg, dict):
                watch_candidates.extend(
                    [
                        (
                            bridge_cfg.get("actionId"),
                            f"{intake_source_root}.bridge.actionId",
                        ),
                        (
                            bridge_cfg.get("action_id"),
                            f"{intake_source_root}.bridge.action_id",
                        ),
                        (
                            bridge_cfg.get("bridgeActionId"),
                            f"{intake_source_root}.bridge.bridgeActionId",
                        ),
                        (
                            bridge_cfg.get("bridgeActionid"),
                            f"{intake_source_root}.bridge.bridgeActionid",
                        ),
                        (
                            bridge_cfg.get("bridgeActionID"),
                            f"{intake_source_root}.bridge.bridgeActionID",
                        ),
                        (
                            bridge_cfg.get("bridgeAction_id"),
                            f"{intake_source_root}.bridge.bridgeAction_id",
                        ),
                        (
                            bridge_cfg.get("bridge_actionID"),
                            f"{intake_source_root}.bridge.bridge_actionID",
                        ),
                        (
                            bridge_cfg.get("bridge_action_id"),
                            f"{intake_source_root}.bridge.bridge_action_id",
                        ),
                        (
                            bridge_cfg.get("bridge_actionId"),
                            f"{intake_source_root}.bridge.bridge_actionId",
                        ),
                        (
                            bridge_cfg.get("bridge_actionid"),
                            f"{intake_source_root}.bridge.bridge_actionid",
                        ),
                        (
                            bridge_cfg.get("bridge-action-id"),
                            f"{intake_source_root}.bridge.bridge-action-id",
                        ),
                        (
                            bridge_cfg.get("bridge-action_id"),
                            f"{intake_source_root}.bridge.bridge-action_id",
                        ),
                        (
                            bridge_cfg.get("bridge-actionid"),
                            f"{intake_source_root}.bridge.bridge-actionid",
                        ),
                        (
                            bridge_cfg.get("bridge-actionId"),
                            f"{intake_source_root}.bridge.bridge-actionId",
                        ),
                        (
                            bridge_cfg.get("bridge-actionID"),
                            f"{intake_source_root}.bridge.bridge-actionID",
                        ),
                    ]
                )
            consume_cfg = intake.get("consume")
            if isinstance(consume_cfg, dict):
                watch_candidates.extend(
                    [
                        (
                            consume_cfg.get("bridgeActionId"),
                            f"{intake_source_root}.consume.bridgeActionId",
                        ),
                        (
                            consume_cfg.get("BridgeActionId"),
                            f"{intake_source_root}.consume.BridgeActionId",
                        ),
                        (
                            consume_cfg.get("BridgeActionID"),
                            f"{intake_source_root}.consume.BridgeActionID",
                        ),
                        (
                            consume_cfg.get("BridgeActionid"),
                            f"{intake_source_root}.consume.BridgeActionid",
                        ),
                        (
                            consume_cfg.get("BridgeAction_id"),
                            f"{intake_source_root}.consume.BridgeAction_id",
                        ),
                        (
                            consume_cfg.get("BridgeAction_Id"),
                            f"{intake_source_root}.consume.BridgeAction_Id",
                        ),
                        (
                            consume_cfg.get("BridgeAction_ID"),
                            f"{intake_source_root}.consume.BridgeAction_ID",
                        ),
                        (
                            consume_cfg.get("BridgeAction-id"),
                            f"{intake_source_root}.consume.BridgeAction-id",
                        ),
                        (
                            consume_cfg.get("BridgeAction-Id"),
                            f"{intake_source_root}.consume.BridgeAction-Id",
                        ),
                        (
                            consume_cfg.get("BridgeAction-ID"),
                            f"{intake_source_root}.consume.BridgeAction-ID",
                        ),
                        (
                            consume_cfg.get("Bridge_ActionId"),
                            f"{intake_source_root}.consume.Bridge_ActionId",
                        ),
                        (
                            consume_cfg.get("Bridge_ActionID"),
                            f"{intake_source_root}.consume.Bridge_ActionID",
                        ),
                        (
                            consume_cfg.get("Bridge_Action_ID"),
                            f"{intake_source_root}.consume.Bridge_Action_ID",
                        ),
                        (
                            consume_cfg.get("Bridge_Action_Id"),
                            f"{intake_source_root}.consume.Bridge_Action_Id",
                        ),
                        (
                            consume_cfg.get("Bridge_Actionid"),
                            f"{intake_source_root}.consume.Bridge_Actionid",
                        ),
                        (
                            consume_cfg.get("Bridge_Action_id"),
                            f"{intake_source_root}.consume.Bridge_Action_id",
                        ),
                        (
                            consume_cfg.get("Bridge_Action-id"),
                            f"{intake_source_root}.consume.Bridge_Action-id",
                        ),
                        (
                            consume_cfg.get("Bridge_Action-Id"),
                            f"{intake_source_root}.consume.Bridge_Action-Id",
                        ),
                        (
                            consume_cfg.get("Bridge_Action-ID"),
                            f"{intake_source_root}.consume.Bridge_Action-ID",
                        ),
                        (
                            consume_cfg.get("Bridge-ActionId"),
                            f"{intake_source_root}.consume.Bridge-ActionId",
                        ),
                        (
                            consume_cfg.get("Bridge-ActionID"),
                            f"{intake_source_root}.consume.Bridge-ActionID",
                        ),
                        (
                            consume_cfg.get("Bridge-Action-ID"),
                            f"{intake_source_root}.consume.Bridge-Action-ID",
                        ),
                        (
                            consume_cfg.get("Bridge-Action-Id"),
                            f"{intake_source_root}.consume.Bridge-Action-Id",
                        ),
                        (
                            consume_cfg.get("Bridge-Actionid"),
                            f"{intake_source_root}.consume.Bridge-Actionid",
                        ),
                        (
                            consume_cfg.get("Bridge-Action_id"),
                            f"{intake_source_root}.consume.Bridge-Action_id",
                        ),
                        (
                            consume_cfg.get("Bridge-Action_Id"),
                            f"{intake_source_root}.consume.Bridge-Action_Id",
                        ),
                        (
                            consume_cfg.get("Bridge-Action_ID"),
                            f"{intake_source_root}.consume.Bridge-Action_ID",
                        ),
                        (
                            consume_cfg.get("bridgeActionID"),
                            f"{intake_source_root}.consume.bridgeActionID",
                        ),
                        (
                            consume_cfg.get("bridgeActionid"),
                            f"{intake_source_root}.consume.bridgeActionid",
                        ),
                        (
                            consume_cfg.get("bridge-ActionId"),
                            f"{intake_source_root}.consume.bridge-ActionId",
                        ),
                        (
                            consume_cfg.get("bridge-ActionID"),
                            f"{intake_source_root}.consume.bridge-ActionID",
                        ),
                        (
                            consume_cfg.get("bridge-Action-ID"),
                            f"{intake_source_root}.consume.bridge-Action-ID",
                        ),
                        (
                            consume_cfg.get("bridge-Action-Id"),
                            f"{intake_source_root}.consume.bridge-Action-Id",
                        ),
                        (
                            consume_cfg.get("bridge-Action-id"),
                            f"{intake_source_root}.consume.bridge-Action-id",
                        ),
                        (
                            consume_cfg.get("bridge-Action-iD"),
                            f"{intake_source_root}.consume.bridge-Action-iD",
                        ),
                        (
                            consume_cfg.get("bridge-Actionid"),
                            f"{intake_source_root}.consume.bridge-Actionid",
                        ),
                        (
                            consume_cfg.get("bridge-Action_id"),
                            f"{intake_source_root}.consume.bridge-Action_id",
                        ),
                        (
                            consume_cfg.get("bridge-Action_Id"),
                            f"{intake_source_root}.consume.bridge-Action_Id",
                        ),
                        (
                            consume_cfg.get("bridge-Action_ID"),
                            f"{intake_source_root}.consume.bridge-Action_ID",
                        ),
                        (
                            consume_cfg.get("bridge_ActionId"),
                            f"{intake_source_root}.consume.bridge_ActionId",
                        ),
                        (
                            consume_cfg.get("bridge_ActionID"),
                            f"{intake_source_root}.consume.bridge_ActionID",
                        ),
                        (
                            consume_cfg.get("bridge_Actionid"),
                            f"{intake_source_root}.consume.bridge_Actionid",
                        ),
                        (
                            consume_cfg.get("bridge_Action_id"),
                            f"{intake_source_root}.consume.bridge_Action_id",
                        ),
                        (
                            consume_cfg.get("bridge_Action_Id"),
                            f"{intake_source_root}.consume.bridge_Action_Id",
                        ),
                        (
                            consume_cfg.get("bridge_Action_ID"),
                            f"{intake_source_root}.consume.bridge_Action_ID",
                        ),
                        (
                            consume_cfg.get("bridgeAction-Id"),
                            f"{intake_source_root}.consume.bridgeAction-Id",
                        ),
                        (
                            consume_cfg.get("bridgeAction-id"),
                            f"{intake_source_root}.consume.bridgeAction-id",
                        ),
                        (
                            consume_cfg.get("bridgeAction-ID"),
                            f"{intake_source_root}.consume.bridgeAction-ID",
                        ),
                        (
                            consume_cfg.get("bridgeAction_id"),
                            f"{intake_source_root}.consume.bridgeAction_id",
                        ),
                        (
                            consume_cfg.get("bridgeAction_Id"),
                            f"{intake_source_root}.consume.bridgeAction_Id",
                        ),
                        (
                            consume_cfg.get("bridgeAction_ID"),
                            f"{intake_source_root}.consume.bridgeAction_ID",
                        ),
                        (
                            consume_cfg.get("bridge_action_id"),
                            f"{intake_source_root}.consume.bridge_action_id",
                        ),
                        (
                            consume_cfg.get("bridge_action_Id"),
                            f"{intake_source_root}.consume.bridge_action_Id",
                        ),
                        (
                            consume_cfg.get("bridge_actionId"),
                            f"{intake_source_root}.consume.bridge_actionId",
                        ),
                        (
                            consume_cfg.get("bridge_actionid"),
                            f"{intake_source_root}.consume.bridge_actionid",
                        ),
                        (
                            consume_cfg.get("bridge_actionID"),
                            f"{intake_source_root}.consume.bridge_actionID",
                        ),
                        (
                            consume_cfg.get("bridge-action-id"),
                            f"{intake_source_root}.consume.bridge-action-id",
                        ),
                        (
                            consume_cfg.get("bridge-action_id"),
                            f"{intake_source_root}.consume.bridge-action_id",
                        ),
                        (
                            consume_cfg.get("bridge-action_Id"),
                            f"{intake_source_root}.consume.bridge-action_Id",
                        ),
                        (
                            consume_cfg.get("bridge-actionId"),
                            f"{intake_source_root}.consume.bridge-actionId",
                        ),
                        (
                            consume_cfg.get("bridge-actionID"),
                            f"{intake_source_root}.consume.bridge-actionID",
                        ),
                        (
                            consume_cfg.get("bridge-action-Id"),
                            f"{intake_source_root}.consume.bridge-action-Id",
                        ),
                        (
                            consume_cfg.get("bridge-action-ID"),
                            f"{intake_source_root}.consume.bridge-action-ID",
                        ),
                        (
                            consume_cfg.get("bridge-action-iD"),
                            f"{intake_source_root}.consume.bridge-action-iD",
                        ),
                        (
                            consume_cfg.get("bridge-actionid"),
                            f"{intake_source_root}.consume.bridge-actionid",
                        ),
                        (
                            consume_cfg.get("ActionId"),
                            f"{intake_source_root}.consume.ActionId",
                        ),
                        (
                            consume_cfg.get("ActionID"),
                            f"{intake_source_root}.consume.ActionID",
                        ),
                        (
                            consume_cfg.get("Action-ID"),
                            f"{intake_source_root}.consume.Action-ID",
                        ),
                        (
                            consume_cfg.get("Action-Id"),
                            f"{intake_source_root}.consume.Action-Id",
                        ),
                        (
                            consume_cfg.get("Action-id"),
                            f"{intake_source_root}.consume.Action-id",
                        ),
                        (
                            consume_cfg.get("ACTIONID"),
                            f"{intake_source_root}.consume.ACTIONID",
                        ),
                        (
                            consume_cfg.get("ACTION_ID"),
                            f"{intake_source_root}.consume.ACTION_ID",
                        ),
                        (
                            consume_cfg.get("ACTION-ID"),
                            f"{intake_source_root}.consume.ACTION-ID",
                        ),
                        (
                            consume_cfg.get("Action_id"),
                            f"{intake_source_root}.consume.Action_id",
                        ),
                        (
                            consume_cfg.get("Action_ID"),
                            f"{intake_source_root}.consume.Action_ID",
                        ),
                        (
                            consume_cfg.get("Actionid"),
                            f"{intake_source_root}.consume.Actionid",
                        ),
                        (
                            consume_cfg.get("actionId"),
                            f"{intake_source_root}.consume.actionId",
                        ),
                        (
                            consume_cfg.get("actionid"),
                            f"{intake_source_root}.consume.actionid",
                        ),
                        (
                            consume_cfg.get("action_id"),
                            f"{intake_source_root}.consume.action_id",
                        ),
                        (
                            consume_cfg.get("action-id"),
                            f"{intake_source_root}.consume.action-id",
                        ),
                        (
                            consume_cfg.get("action-Id"),
                            f"{intake_source_root}.consume.action-Id",
                        ),
                        (
                            consume_cfg.get("actionID"),
                            f"{intake_source_root}.consume.actionID",
                        ),
                    ]
                )

            consume_alias_cfg, consume_alias_source_root = (
                _extract_watch_consume_with_source(intake, intake_source_root)
            )
            watch_candidates.extend(
                _collect_action_id_like_candidates(
                    consume_alias_cfg,
                    consume_alias_source_root,
                )
            )

        escalation_candidates: list[tuple[Any, str]] = []
        workflow, workflow_source_root = _extract_operator_workflow_with_source(
            watch_payload
        )
        if workflow_source_root:
            internal_loop = workflow.get("internalLoop")
            internal_loop_source_root = f"{workflow_source_root}.internalLoop"
            if not isinstance(internal_loop, dict):
                internal_loop = workflow.get("internal_loop")
                internal_loop_source_root = f"{workflow_source_root}.internal_loop"
            if not isinstance(internal_loop, dict):
                internal_loop = workflow.get("internal-loop")
                internal_loop_source_root = f"{workflow_source_root}.internal-loop"
            if isinstance(internal_loop, dict):
                watch_candidates.extend(
                    [
                        (
                            internal_loop.get("bridgeActionId"),
                            f"{internal_loop_source_root}.bridgeActionId",
                        ),
                        (
                            internal_loop.get("bridgeActionID"),
                            f"{internal_loop_source_root}.bridgeActionID",
                        ),
                        (
                            internal_loop.get("bridgeActionid"),
                            f"{internal_loop_source_root}.bridgeActionid",
                        ),
                        (
                            internal_loop.get("bridgeAction_id"),
                            f"{internal_loop_source_root}.bridgeAction_id",
                        ),
                        (
                            internal_loop.get("bridge_actionID"),
                            f"{internal_loop_source_root}.bridge_actionID",
                        ),
                        (
                            internal_loop.get("bridge_action_id"),
                            f"{internal_loop_source_root}.bridge_action_id",
                        ),
                        (
                            internal_loop.get("bridge_actionId"),
                            f"{internal_loop_source_root}.bridge_actionId",
                        ),
                        (
                            internal_loop.get("bridge_actionid"),
                            f"{internal_loop_source_root}.bridge_actionid",
                        ),
                        (
                            internal_loop.get("bridge-action-id"),
                            f"{internal_loop_source_root}.bridge-action-id",
                        ),
                        (
                            internal_loop.get("bridge-actionid"),
                            f"{internal_loop_source_root}.bridge-actionid",
                        ),
                        (
                            internal_loop.get("bridge-actionId"),
                            f"{internal_loop_source_root}.bridge-actionId",
                        ),
                        (
                            internal_loop.get("bridge-actionID"),
                            f"{internal_loop_source_root}.bridge-actionID",
                        ),
                        (
                            internal_loop.get("bridge-action_id"),
                            f"{internal_loop_source_root}.bridge-action_id",
                        ),
                        (
                            internal_loop.get("actionId"),
                            f"{internal_loop_source_root}.actionId",
                        ),
                        (
                            internal_loop.get("actionid"),
                            f"{internal_loop_source_root}.actionid",
                        ),
                        (
                            internal_loop.get("actionID"),
                            f"{internal_loop_source_root}.actionID",
                        ),
                        (
                            internal_loop.get("action_id"),
                            f"{internal_loop_source_root}.action_id",
                        ),
                        (
                            internal_loop.get("action"),
                            f"{internal_loop_source_root}.action",
                        ),
                    ]
                )

                internal_hint = internal_loop.get("actionHint")
                internal_hint_source_root = f"{internal_loop_source_root}.actionHint"
                if not isinstance(internal_hint, dict):
                    internal_hint = internal_loop.get("action_hint")
                    internal_hint_source_root = (
                        f"{internal_loop_source_root}.action_hint"
                    )
                if not isinstance(internal_hint, dict):
                    internal_hint = internal_loop.get("action-hint")
                    internal_hint_source_root = (
                        f"{internal_loop_source_root}.action-hint"
                    )
                if isinstance(internal_hint, dict):
                    watch_candidates.extend(
                        [
                            (
                                internal_hint.get("bridgeActionId"),
                                f"{internal_hint_source_root}.bridgeActionId",
                            ),
                            (
                                internal_hint.get("bridgeActionID"),
                                f"{internal_hint_source_root}.bridgeActionID",
                            ),
                            (
                                internal_hint.get("bridgeActionid"),
                                f"{internal_hint_source_root}.bridgeActionid",
                            ),
                            (
                                internal_hint.get("bridgeAction_id"),
                                f"{internal_hint_source_root}.bridgeAction_id",
                            ),
                            (
                                internal_hint.get("bridge_actionID"),
                                f"{internal_hint_source_root}.bridge_actionID",
                            ),
                            (
                                internal_hint.get("bridge_action_id"),
                                f"{internal_hint_source_root}.bridge_action_id",
                            ),
                            (
                                internal_hint.get("bridge_actionId"),
                                f"{internal_hint_source_root}.bridge_actionId",
                            ),
                            (
                                internal_hint.get("bridge_actionid"),
                                f"{internal_hint_source_root}.bridge_actionid",
                            ),
                            (
                                internal_hint.get("bridge-action-id"),
                                f"{internal_hint_source_root}.bridge-action-id",
                            ),
                            (
                                internal_hint.get("bridge-actionid"),
                                f"{internal_hint_source_root}.bridge-actionid",
                            ),
                            (
                                internal_hint.get("bridge-actionId"),
                                f"{internal_hint_source_root}.bridge-actionId",
                            ),
                            (
                                internal_hint.get("bridge-actionID"),
                                f"{internal_hint_source_root}.bridge-actionID",
                            ),
                            (
                                internal_hint.get("bridge-action_id"),
                                f"{internal_hint_source_root}.bridge-action_id",
                            ),
                            (
                                internal_hint.get("actionId"),
                                f"{internal_hint_source_root}.actionId",
                            ),
                            (
                                internal_hint.get("actionid"),
                                f"{internal_hint_source_root}.actionid",
                            ),
                            (
                                internal_hint.get("actionID"),
                                f"{internal_hint_source_root}.actionID",
                            ),
                            (
                                internal_hint.get("action_id"),
                                f"{internal_hint_source_root}.action_id",
                            ),
                            (
                                internal_hint.get("action"),
                                f"{internal_hint_source_root}.action",
                            ),
                            (
                                internal_hint.get("defaultAction"),
                                f"{internal_hint_source_root}.defaultAction",
                            ),
                            (
                                internal_hint.get("default_action"),
                                f"{internal_hint_source_root}.default_action",
                            ),
                            (
                                internal_hint.get("defaultActionId"),
                                f"{internal_hint_source_root}.defaultActionId",
                            ),
                            (
                                internal_hint.get("defaultActionid"),
                                f"{internal_hint_source_root}.defaultActionid",
                            ),
                            (
                                internal_hint.get("defaultActionID"),
                                f"{internal_hint_source_root}.defaultActionID",
                            ),
                            (
                                internal_hint.get("defaultAction_id"),
                                f"{internal_hint_source_root}.defaultAction_id",
                            ),
                            (
                                internal_hint.get("default_action_id"),
                                f"{internal_hint_source_root}.default_action_id",
                            ),
                            (
                                internal_hint.get("default_actionId"),
                                f"{internal_hint_source_root}.default_actionId",
                            ),
                            (
                                internal_hint.get("default_actionid"),
                                f"{internal_hint_source_root}.default_actionid",
                            ),
                            (
                                internal_hint.get("default_actionID"),
                                f"{internal_hint_source_root}.default_actionID",
                            ),
                            (
                                internal_hint.get("watchActAction"),
                                f"{internal_hint_source_root}.watchActAction",
                            ),
                            (
                                internal_hint.get("watch_act_action"),
                                f"{internal_hint_source_root}.watch_act_action",
                            ),
                            (
                                internal_hint.get("watch-act-action"),
                                f"{internal_hint_source_root}.watch-act-action",
                            ),
                        ]
                    )

                watch_candidates.extend(
                    [
                        (
                            internal_loop.get("defaultAction"),
                            f"{internal_loop_source_root}.defaultAction",
                        ),
                        (
                            internal_loop.get("default_action"),
                            f"{internal_loop_source_root}.default_action",
                        ),
                        (
                            internal_loop.get("defaultActionId"),
                            f"{internal_loop_source_root}.defaultActionId",
                        ),
                        (
                            internal_loop.get("defaultActionid"),
                            f"{internal_loop_source_root}.defaultActionid",
                        ),
                        (
                            internal_loop.get("defaultActionID"),
                            f"{internal_loop_source_root}.defaultActionID",
                        ),
                        (
                            internal_loop.get("defaultAction_id"),
                            f"{internal_loop_source_root}.defaultAction_id",
                        ),
                        (
                            internal_loop.get("default_action_id"),
                            f"{internal_loop_source_root}.default_action_id",
                        ),
                        (
                            internal_loop.get("default_actionId"),
                            f"{internal_loop_source_root}.default_actionId",
                        ),
                        (
                            internal_loop.get("default_actionid"),
                            f"{internal_loop_source_root}.default_actionid",
                        ),
                        (
                            internal_loop.get("default_actionID"),
                            f"{internal_loop_source_root}.default_actionID",
                        ),
                        (
                            internal_loop.get("watchActAction"),
                            f"{internal_loop_source_root}.watchActAction",
                        ),
                        (
                            internal_loop.get("watch_act_action"),
                            f"{internal_loop_source_root}.watch_act_action",
                        ),
                        (
                            internal_loop.get("watch-act-action"),
                            f"{internal_loop_source_root}.watch-act-action",
                        ),
                    ]
                )

            escalation = workflow.get("externalEscalation")
            escalation_source_root = f"{workflow_source_root}.externalEscalation"
            if not isinstance(escalation, dict):
                escalation = workflow.get("external_escalation")
                escalation_source_root = f"{workflow_source_root}.external_escalation"
            if not isinstance(escalation, dict):
                escalation = workflow.get("external-escalation")
                escalation_source_root = f"{workflow_source_root}.external-escalation"
            if isinstance(escalation, dict):
                escalation_candidates.extend(
                    [
                        (
                            escalation.get("bridgeActionId"),
                            f"{escalation_source_root}.bridgeActionId",
                        ),
                        (
                            escalation.get("bridgeActionid"),
                            f"{escalation_source_root}.bridgeActionid",
                        ),
                        (
                            escalation.get("bridgeActionID"),
                            f"{escalation_source_root}.bridgeActionID",
                        ),
                        (
                            escalation.get("bridgeAction_id"),
                            f"{escalation_source_root}.bridgeAction_id",
                        ),
                        (
                            escalation.get("bridge_actionid"),
                            f"{escalation_source_root}.bridge_actionid",
                        ),
                        (
                            escalation.get("bridge_actionID"),
                            f"{escalation_source_root}.bridge_actionID",
                        ),
                        (
                            escalation.get("bridge_action_id"),
                            f"{escalation_source_root}.bridge_action_id",
                        ),
                        (
                            escalation.get("bridge_actionId"),
                            f"{escalation_source_root}.bridge_actionId",
                        ),
                        (
                            escalation.get("bridge-action-id"),
                            f"{escalation_source_root}.bridge-action-id",
                        ),
                        (
                            escalation.get("bridge-action_id"),
                            f"{escalation_source_root}.bridge-action_id",
                        ),
                        (
                            escalation.get("bridge-actionid"),
                            f"{escalation_source_root}.bridge-actionid",
                        ),
                        (
                            escalation.get("bridge-actionId"),
                            f"{escalation_source_root}.bridge-actionId",
                        ),
                        (
                            escalation.get("bridge-actionID"),
                            f"{escalation_source_root}.bridge-actionID",
                        ),
                        (
                            escalation.get("actionId"),
                            f"{escalation_source_root}.actionId",
                        ),
                        (
                            escalation.get("actionID"),
                            f"{escalation_source_root}.actionID",
                        ),
                        (
                            escalation.get("actionid"),
                            f"{escalation_source_root}.actionid",
                        ),
                        (
                            escalation.get("action_id"),
                            f"{escalation_source_root}.action_id",
                        ),
                        (
                            escalation.get("action"),
                            f"{escalation_source_root}.action",
                        ),
                        (
                            escalation.get("defaultActionId"),
                            f"{escalation_source_root}.defaultActionId",
                        ),
                        (
                            escalation.get("defaultActionID"),
                            f"{escalation_source_root}.defaultActionID",
                        ),
                        (
                            escalation.get("defaultAction_id"),
                            f"{escalation_source_root}.defaultAction_id",
                        ),
                        (
                            escalation.get("default_action_id"),
                            f"{escalation_source_root}.default_action_id",
                        ),
                        (
                            escalation.get("default_actionId"),
                            f"{escalation_source_root}.default_actionId",
                        ),
                        (
                            escalation.get("default_actionID"),
                            f"{escalation_source_root}.default_actionID",
                        ),
                        (
                            escalation.get("default-action-id"),
                            f"{escalation_source_root}.default-action-id",
                        ),
                        (
                            escalation.get("default-actionid"),
                            f"{escalation_source_root}.default-actionid",
                        ),
                        (
                            escalation.get("default-actionId"),
                            f"{escalation_source_root}.default-actionId",
                        ),
                        (
                            escalation.get("default-actionID"),
                            f"{escalation_source_root}.default-actionID",
                        ),
                        (
                            escalation.get("watchActAction"),
                            f"{escalation_source_root}.watchActAction",
                        ),
                        (
                            escalation.get("watch_act_action"),
                            f"{escalation_source_root}.watch_act_action",
                        ),
                        (
                            escalation.get("watch-act-action"),
                            f"{escalation_source_root}.watch-act-action",
                        ),
                    ]
                )
                escalation_hint = escalation.get("actionHint")
                escalation_hint_source_root = f"{escalation_source_root}.actionHint"
                if not isinstance(escalation_hint, dict):
                    escalation_hint = escalation.get("action_hint")
                    escalation_hint_source_root = (
                        f"{escalation_source_root}.action_hint"
                    )
                if not isinstance(escalation_hint, dict):
                    escalation_hint = escalation.get("action-hint")
                    escalation_hint_source_root = (
                        f"{escalation_source_root}.action-hint"
                    )
                if isinstance(escalation_hint, dict):
                    escalation_candidates.extend(
                        [
                            (
                                escalation_hint.get("bridgeActionId"),
                                f"{escalation_hint_source_root}.bridgeActionId",
                            ),
                            (
                                escalation_hint.get("bridgeActionid"),
                                f"{escalation_hint_source_root}.bridgeActionid",
                            ),
                            (
                                escalation_hint.get("bridgeActionID"),
                                f"{escalation_hint_source_root}.bridgeActionID",
                            ),
                            (
                                escalation_hint.get("bridgeAction_id"),
                                f"{escalation_hint_source_root}.bridgeAction_id",
                            ),
                            (
                                escalation_hint.get("bridge_actionid"),
                                f"{escalation_hint_source_root}.bridge_actionid",
                            ),
                            (
                                escalation_hint.get("bridge_actionID"),
                                f"{escalation_hint_source_root}.bridge_actionID",
                            ),
                            (
                                escalation_hint.get("bridge_action_id"),
                                f"{escalation_hint_source_root}.bridge_action_id",
                            ),
                            (
                                escalation_hint.get("bridge_actionId"),
                                f"{escalation_hint_source_root}.bridge_actionId",
                            ),
                            (
                                escalation_hint.get("bridge-action-id"),
                                f"{escalation_hint_source_root}.bridge-action-id",
                            ),
                            (
                                escalation_hint.get("bridge-action_id"),
                                f"{escalation_hint_source_root}.bridge-action_id",
                            ),
                            (
                                escalation_hint.get("bridge-actionid"),
                                f"{escalation_hint_source_root}.bridge-actionid",
                            ),
                            (
                                escalation_hint.get("bridge-actionId"),
                                f"{escalation_hint_source_root}.bridge-actionId",
                            ),
                            (
                                escalation_hint.get("bridge-actionID"),
                                f"{escalation_hint_source_root}.bridge-actionID",
                            ),
                            (
                                escalation_hint.get("actionId"),
                                f"{escalation_hint_source_root}.actionId",
                            ),
                            (
                                escalation_hint.get("actionID"),
                                f"{escalation_hint_source_root}.actionID",
                            ),
                            (
                                escalation_hint.get("actionid"),
                                f"{escalation_hint_source_root}.actionid",
                            ),
                            (
                                escalation_hint.get("action_id"),
                                f"{escalation_hint_source_root}.action_id",
                            ),
                            (
                                escalation_hint.get("action"),
                                f"{escalation_hint_source_root}.action",
                            ),
                            (
                                escalation_hint.get("watchActAction"),
                                f"{escalation_hint_source_root}.watchActAction",
                            ),
                            (
                                escalation_hint.get("watch_act_action"),
                                f"{escalation_hint_source_root}.watch_act_action",
                            ),
                            (
                                escalation_hint.get("watch-act-action"),
                                f"{escalation_hint_source_root}.watch-act-action",
                            ),
                            (
                                escalation_hint.get("defaultAction"),
                                f"{escalation_hint_source_root}.defaultAction",
                            ),
                            (
                                escalation_hint.get("default_action"),
                                f"{escalation_hint_source_root}.default_action",
                            ),
                            (
                                escalation_hint.get("default-action"),
                                f"{escalation_hint_source_root}.default-action",
                            ),
                            (
                                escalation_hint.get("defaultActionId"),
                                f"{escalation_hint_source_root}.defaultActionId",
                            ),
                            (
                                escalation_hint.get("defaultActionid"),
                                f"{escalation_hint_source_root}.defaultActionid",
                            ),
                            (
                                escalation_hint.get("defaultActionID"),
                                f"{escalation_hint_source_root}.defaultActionID",
                            ),
                            (
                                escalation_hint.get("defaultAction_id"),
                                f"{escalation_hint_source_root}.defaultAction_id",
                            ),
                            (
                                escalation_hint.get("default_action_id"),
                                f"{escalation_hint_source_root}.default_action_id",
                            ),
                            (
                                escalation_hint.get("default_actionId"),
                                f"{escalation_hint_source_root}.default_actionId",
                            ),
                            (
                                escalation_hint.get("default_actionid"),
                                f"{escalation_hint_source_root}.default_actionid",
                            ),
                            (
                                escalation_hint.get("default_actionID"),
                                f"{escalation_hint_source_root}.default_actionID",
                            ),
                            (
                                escalation_hint.get("default-action-id"),
                                f"{escalation_hint_source_root}.default-action-id",
                            ),
                            (
                                escalation_hint.get("default-actionid"),
                                f"{escalation_hint_source_root}.default-actionid",
                            ),
                            (
                                escalation_hint.get("default-actionId"),
                                f"{escalation_hint_source_root}.default-actionId",
                            ),
                            (
                                escalation_hint.get("default-actionID"),
                                f"{escalation_hint_source_root}.default-actionID",
                            ),
                        ]
                    )

                escalation_candidates.append(
                    (
                        escalation.get("defaultAction"),
                        f"{escalation_source_root}.defaultAction",
                    )
                )
                escalation_candidates.append(
                    (
                        escalation.get("default_action"),
                        f"{escalation_source_root}.default_action",
                    )
                )
                escalation_candidates.append(
                    (
                        escalation.get("default-action"),
                        f"{escalation_source_root}.default-action",
                    )
                )
                escalation_candidates.append(
                    (
                        escalation.get("defaultActionId"),
                        f"{escalation_source_root}.defaultActionId",
                    )
                )
                escalation_candidates.append(
                    (
                        escalation.get("defaultActionid"),
                        f"{escalation_source_root}.defaultActionid",
                    )
                )
                escalation_candidates.append(
                    (
                        escalation.get("defaultActionID"),
                        f"{escalation_source_root}.defaultActionID",
                    )
                )
                escalation_candidates.append(
                    (
                        escalation.get("defaultAction_id"),
                        f"{escalation_source_root}.defaultAction_id",
                    )
                )
                escalation_candidates.append(
                    (
                        escalation.get("default_action_id"),
                        f"{escalation_source_root}.default_action_id",
                    )
                )
                escalation_candidates.append(
                    (
                        escalation.get("default_actionId"),
                        f"{escalation_source_root}.default_actionId",
                    )
                )
                escalation_candidates.append(
                    (
                        escalation.get("default_actionid"),
                        f"{escalation_source_root}.default_actionid",
                    )
                )
                escalation_candidates.append(
                    (
                        escalation.get("default_actionID"),
                        f"{escalation_source_root}.default_actionID",
                    )
                )
                escalation_candidates.append(
                    (
                        escalation.get("default-action-id"),
                        f"{escalation_source_root}.default-action-id",
                    )
                )
                escalation_candidates.append(
                    (
                        escalation.get("default-actionid"),
                        f"{escalation_source_root}.default-actionid",
                    )
                )
                escalation_candidates.append(
                    (
                        escalation.get("default-actionId"),
                        f"{escalation_source_root}.default-actionId",
                    )
                )
                escalation_candidates.append(
                    (
                        escalation.get("default-actionID"),
                        f"{escalation_source_root}.default-actionID",
                    )
                )

        candidates: list[tuple[Any, str, str]] = []
        if escalation_action:
            candidates.extend(
                (candidate, "escalation-hint", path)
                for candidate, path in escalation_candidates
            )
            candidates.extend(
                (candidate, "watch-loop-hint", path)
                for candidate, path in watch_candidates
            )
        else:
            candidates.extend(
                (candidate, "watch-loop-hint", path)
                for candidate, path in watch_candidates
            )
            candidates.extend(
                (candidate, "escalation-hint", path)
                for candidate, path in escalation_candidates
            )

        for candidate, source, source_path in candidates:
            text = str(candidate or "").strip()
            if text:
                action_hint = text
                action_hint_source = source
                action_hint_source_path = source_path
                break

    explicit_action_override = (action_override or "").strip()
    positional_action_id = (action_id or "").strip()
    resolved_action_id = ""
    resolved_action_source = ""
    resolved_action_source_path = ""

    if explicit_action_override:
        resolved_action_id = explicit_action_override
        resolved_action_source = "explicit-override"
        resolved_action_source_path = "--action-id"
    elif positional_action_id:
        resolved_action_id = positional_action_id
        resolved_action_source = "explicit-override"
        resolved_action_source_path = "<action-id>"
    else:
        resolved_action_id = action_hint
        resolved_action_source = action_hint_source
        resolved_action_source_path = action_hint_source_path

    if not resolved_action_id:
        utils.error_exit(
            "invalid_action_id",
            "Provide <action-id>, --action-id, or include actionId in watch payload.",
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
        resolved_action_id,
        "--json",
    ]

    parsed_input_json: Any | None = None
    if input_json is not None:
        try:
            parsed_input_json = json.loads(input_json)
        except json.JSONDecodeError:
            utils.error_exit(
                "invalid_input_json",
                "--input-json must be a valid JSON object/string.",
            )

    resolved_input_text: Optional[str] = input_json
    if watch_payload is not None:
        watch_intake, _ = _extract_watch_intake_with_source(watch_payload)
        operator_workflow, _ = _extract_operator_workflow_with_source(watch_payload)
        escalation_envelope = _cliq.ZohoCliqClient.extract_escalation_envelope_alias(
            watch_payload
        )
        escalation_envelope_metadata = (
            _cliq.ZohoCliqClient.extract_escalation_envelope_alias_metadata(
                watch_payload
            )
        )
        resolved_watch_input: dict[str, Any] = {
            "watchPayload": watch_payload,
            "escalationEnvelope": escalation_envelope,
            "escalationEnvelopeMetadata": escalation_envelope_metadata,
            "actionSource": resolved_action_source,
            "actionSourcePath": resolved_action_source_path,
            "actionSourceMetadata": _build_action_source_metadata(
                resolved_action_source,
                resolved_action_source_path,
            ),
            "watchIntake": watch_intake if isinstance(watch_intake, dict) else {},
            "operatorWorkflow": (
                operator_workflow if isinstance(operator_workflow, dict) else {}
            ),
        }
        if status_flow:
            resolved_watch_input["statusFlow"] = {"enabled": True}

        if input_json is None:
            resolved_input_text = json.dumps(resolved_watch_input, ensure_ascii=False)
        else:
            if not isinstance(parsed_input_json, dict):
                utils.error_exit(
                    "invalid_input_json",
                    "--input-json must decode to a JSON object when --watch-file is used.",
                )
            merged_input = dict(parsed_input_json)
            merged_input.setdefault("watchPayload", watch_payload)
            merged_input.setdefault(
                "watchIntake",
                watch_intake if isinstance(watch_intake, dict) else {},
            )
            merged_input.setdefault(
                "operatorWorkflow",
                operator_workflow if isinstance(operator_workflow, dict) else {},
            )
            merged_input.setdefault("escalationEnvelope", escalation_envelope)
            merged_input.setdefault(
                "escalationEnvelopeMetadata", escalation_envelope_metadata
            )
            merged_input.setdefault("actionSource", resolved_action_source)
            merged_input.setdefault("actionSourcePath", resolved_action_source_path)
            merged_input.setdefault(
                "actionSourceMetadata",
                _build_action_source_metadata(
                    resolved_action_source,
                    resolved_action_source_path,
                ),
            )
            if status_flow:
                merged_input.setdefault("statusFlow", {"enabled": True})
            resolved_input_text = json.dumps(merged_input, ensure_ascii=False)

    if resolved_input_text is not None:
        command.extend(["--input", resolved_input_text])

    result = _run_membrane_command(command)
    output_payload: dict[str, Any] = {
        "bridge": "membrane",
        "preset": _normalize_membrane_preset(preset or "zoho-cliq"),
        "connectionId": resolved_connection_id,
        "actionId": resolved_action_id,
        "actionSource": resolved_action_source,
        "actionSourcePath": resolved_action_source_path,
        "actionSourceMetadata": _build_action_source_metadata(
            resolved_action_source,
            resolved_action_source_path,
        ),
        "result": result,
    }
    if watch_payload is not None:
        watch_intake, _ = _extract_watch_intake_with_source(watch_payload)
        operator_workflow, _ = _extract_operator_workflow_with_source(watch_payload)
        output_payload["escalationEnvelope"] = escalation_envelope
        output_payload["escalationEnvelopeMetadata"] = escalation_envelope_metadata
        output_payload["watchIntake"] = (
            watch_intake if isinstance(watch_intake, dict) else {}
        )
        output_payload["operatorWorkflow"] = (
            operator_workflow if isinstance(operator_workflow, dict) else {}
        )
        if status_flow:
            output_payload["statusFlow"] = {"enabled": True}

    utils.output(output_payload)


register_cliq_bridge_run_commands(
    cliq_app,
    cliq_bridge_run_command=cliq_bridge_run,
)


cliq_capabilities = build_cliq_capabilities_command(_cliq_readiness_context)


register_cliq_capabilities_commands(
    cliq_app,
    cliq_capabilities_command=cliq_capabilities,
)


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


def cliq_chats(
    limit: int = typer.Option(50, "--limit", "-n", help="Max chats to return."),
    unread_only: bool = typer.Option(
        False,
        "--unread-only",
        help="Only return chats with unread messages.",
    ),
    exclude_reacted_by_self: bool = typer.Option(
        False,
        "--exclude-reacted-by-self",
        help="Exclude chats whose latest message already has a reaction from the current account.",
    ),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List Cliq chats (DM/group conversation descriptors)."""
    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resp = client.chats(limit=limit)
    rows: list[Any] = []
    if isinstance(resp, dict):
        data = resp.get("data")
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            nested = data.get("chats")
            if isinstance(nested, list):
                rows = nested

        if not rows:
            top_level_chats = resp.get("chats")
            if isinstance(top_level_chats, list):
                rows = top_level_chats

    views: list[dict[str, Any]] = []

    def _unread_count(row: dict[str, Any]) -> tuple[int, bool]:
        explicit_field_found = False
        for key in (
            "unread_message_count",
            "unreadMessageCount",
            "unreadCount",
        ):
            if key not in row:
                continue

            explicit_field_found = True
            value = row.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                return max(0, int(value)), True
            if isinstance(value, str):
                parsed = value.strip()
                if parsed.isdigit():
                    return int(parsed), True
        return 0, explicit_field_found

    self_identifier_sets: tuple[set[str], set[str]] | None = None

    def _get_self_identifier_sets() -> tuple[set[str], set[str]]:
        nonlocal self_identifier_sets
        if self_identifier_sets is None:
            identity: dict[str, Any] = {}
            try:
                identity = client.whoami(account_email=email)
            except SystemExit:
                identity = {}
            self_identifier_sets = _self_identifier_sets(identity)
        return self_identifier_sets

    account_email_lc = email.strip().lower()
    account_local_lc = (
        account_email_lc.split("@", 1)[0] if "@" in account_email_lc else ""
    )

    def _looks_like_email(value: str) -> bool:
        return "@" in value

    def _has_non_email_identifier(values: set[str]) -> bool:
        return any(token and not _looks_like_email(token) for token in values)

    def _self_tokens_from_chat_row(row: dict[str, Any]) -> tuple[set[str], set[str]]:
        exact: set[str] = set()
        lowered: set[str] = set()

        def _add(value: Any) -> None:
            text = str(value or "").strip()
            if not text:
                return
            exact.add(text)
            lowered.add(text.lower())

        def _matches_account(value: Any) -> bool:
            text = str(value or "").strip().lower()
            if not text:
                return False
            if account_email_lc and text == account_email_lc:
                return True
            if account_local_lc and text == account_local_lc:
                return True
            return False

        recipients = row.get("recipients_summary")
        if isinstance(recipients, list):
            for recipient in recipients:
                if not isinstance(recipient, dict):
                    continue

                matched = any(
                    _matches_account(recipient.get(key))
                    for key in (
                        "email",
                        "email_id",
                        "emailId",
                        "user_email",
                        "userEmail",
                        "name",
                        "display_name",
                        "displayName",
                        "full_name",
                        "fullName",
                    )
                )
                if not matched:
                    continue

                for key in (
                    "user_id",
                    "userId",
                    "id",
                    "zuid",
                    "email",
                    "email_id",
                    "emailId",
                ):
                    if key in recipient:
                        _add(recipient.get(key))

        return exact, lowered

    def _extract_sender_tokens(message: Any) -> list[str]:
        tokens: list[str] = []
        seen: set[str] = set()

        def _add(value: Any) -> None:
            text = str(value or "").strip()
            if not text or text in seen:
                return
            seen.add(text)
            tokens.append(text)

        if not isinstance(message, dict):
            return tokens

        for key in (
            "sender_id",
            "senderId",
            "user_id",
            "userId",
            "zuid",
            "email",
            "email_id",
            "emailId",
        ):
            if key in message:
                _add(message.get(key))

        sender = message.get("sender")
        if isinstance(sender, dict):
            for key in (
                "id",
                "zuid",
                "user_id",
                "userId",
                "email",
                "email_id",
                "emailId",
            ):
                if key in sender:
                    _add(sender.get(key))

        return tokens

    def _infer_unread_from_latest_sender(row: dict[str, Any]) -> bool:
        last_message = row.get("last_message_info")
        sender_tokens = _extract_sender_tokens(last_message)
        if not sender_tokens:
            return False

        self_exact, self_lowered = _get_self_identifier_sets()
        row_self_exact, row_self_lowered = _self_tokens_from_chat_row(row)
        combined_exact = set(self_exact)
        combined_exact.update(row_self_exact)
        combined_lowered = set(self_lowered)
        combined_lowered.update(row_self_lowered)

        if any(
            _token_matches_self(
                token,
                self_exact=combined_exact,
                self_lowered=combined_lowered,
            )
            for token in sender_tokens
        ):
            return False

        if not _has_non_email_identifier(combined_exact):
            return False

        return True

    def _extract_reaction_rows(payload: Any) -> list[dict[str, Any]]:
        queue: list[Any] = [payload]
        visited_ids: set[int] = set()
        reaction_keys = (
            "emoji",
            "emoji_code",
            "emojiCode",
            "users",
            "user_ids",
            "userId",
            "user_id",
            "owner",
            "owners",
            "reacted_users",
            "reactedUsers",
        )
        container_keys = (
            "data",
            "reactions",
            "reaction",
            "messageactions",
            "messageActions",
            "items",
            "results",
            "records",
            "payload",
            "response",
            "result",
        )

        while queue:
            current = queue.pop(0)
            marker = id(current)
            if marker in visited_ids:
                continue
            visited_ids.add(marker)

            if isinstance(current, list):
                rows = [item for item in current if isinstance(item, dict)]
                if rows and any(
                    any(key in row for key in reaction_keys) for row in rows
                ):
                    return rows
                queue.extend(rows)
                continue

            if not isinstance(current, dict):
                continue

            if any(key in current for key in reaction_keys):
                return [current]

            for key in container_keys:
                nested = current.get(key)
                if nested is not None:
                    queue.append(nested)

        return []

    def _extract_reaction_owner_tokens(reaction: dict[str, Any]) -> list[str]:
        tokens: list[str] = []
        seen: set[str] = set()

        def _add(value: Any) -> None:
            text = str(value or "").strip()
            if not text or text in seen:
                return
            seen.add(text)
            tokens.append(text)

        def _walk(value: Any) -> None:
            if isinstance(value, dict):
                for key in (
                    "id",
                    "zuid",
                    "user_id",
                    "userId",
                    "owner_id",
                    "ownerId",
                    "email",
                    "email_id",
                    "emailId",
                ):
                    if key in value:
                        _add(value.get(key))
                for key in (
                    "users",
                    "user",
                    "owners",
                    "owner",
                    "reacted_users",
                    "reactedUsers",
                    "members",
                    "member",
                    "participants",
                    "participant",
                    "users_info",
                    "usersInfo",
                    "user_ids",
                    "userIds",
                    "owner_ids",
                    "ownerIds",
                    "zuids",
                    "emails",
                ):
                    if key in value:
                        _walk(value.get(key))
                return

            if isinstance(value, (list, tuple, set)):
                for item in value:
                    _walk(item)
                return

            if isinstance(value, (str, int, float)):
                _add(value)

        _walk(reaction)
        return tokens

    def _self_identifier_sets(identity: dict[str, Any]) -> tuple[set[str], set[str]]:
        exact: set[str] = set()
        lowered: set[str] = set()

        def _add_token(value: Any) -> None:
            text = str(value or "").strip()
            if not text:
                return
            exact.add(text)
            lowered.add(text.lower())

        user = identity.get("user") if isinstance(identity, dict) else {}
        if isinstance(user, dict):
            _add_token(user.get("userId"))
            _add_token(user.get("email"))
            raw = user.get("raw")
            if isinstance(raw, dict):
                for key in (
                    "id",
                    "zuid",
                    "user_id",
                    "userId",
                    "email",
                    "email_id",
                    "emailId",
                ):
                    if key in raw:
                        _add_token(raw.get(key))

        _add_token(email)
        return exact, lowered

    def _token_matches_self(
        token: str,
        *,
        self_exact: set[str],
        self_lowered: set[str],
    ) -> bool:
        candidate = token.strip()
        if not candidate:
            return False
        return candidate in self_exact or candidate.lower() in self_lowered

    def _latest_message_for_chat(chat_identifier: str) -> dict[str, Any]:
        if not chat_identifier:
            return {}
        response = client.list_messages(chat_id=chat_identifier, limit=1)
        data = response.get("data", response)
        if not isinstance(data, list) or not data:
            return {}
        first = data[0]
        return first if isinstance(first, dict) else {}

    inferred_unread_count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue

        unread_count, unread_field_present = _unread_count(row)
        unread_inferred = False
        if unread_only and unread_count <= 0:
            if unread_field_present:
                continue
            if not _infer_unread_from_latest_sender(row):
                continue
            unread_count = 1
            unread_inferred = True
            inferred_unread_count += 1

        item: dict[str, Any] = {
            "chatId": str(
                row.get("id") or row.get("chat_id") or row.get("chatId") or ""
            ),
            "name": str(
                row.get("name") or row.get("title") or row.get("display_name") or ""
            ),
            "type": str(
                row.get("type") or row.get("chat_type") or row.get("chatType") or ""
            ),
            "unreadCount": unread_count,
            "raw": row,
        }
        if unread_inferred:
            item["unreadInferred"] = True

        views.append(item)

    filtered_by_self_reaction = 0
    if exclude_reacted_by_self and views:
        identity = client.whoami(account_email=email)
        self_exact, self_lowered = _self_identifier_sets(identity)

        retained_views: list[dict[str, Any]] = []
        for view in views:
            chat_identifier = str(view.get("chatId") or "").strip()
            if not chat_identifier:
                retained_views.append(view)
                continue

            latest_message = _latest_message_for_chat(chat_identifier)
            message_id = _cliq.ZohoCliqClient._extract_message_id(latest_message)
            if not message_id:
                retained_views.append(view)
                continue

            reactions_payload: Any
            try:
                reactions_payload = client.get_message_reactions(
                    message_id,
                    chat_id=chat_identifier,
                )
            except SystemExit:
                reactions_payload = latest_message

            reaction_rows = _extract_reaction_rows(reactions_payload)
            if not reaction_rows:
                reaction_rows = _extract_reaction_rows(latest_message)

            reacted_by_self = False
            for reaction in reaction_rows:
                owner_tokens = _extract_reaction_owner_tokens(reaction)
                if any(
                    _token_matches_self(
                        owner,
                        self_exact=self_exact,
                        self_lowered=self_lowered,
                    )
                    for owner in owner_tokens
                ):
                    reacted_by_self = True
                    break

            if reacted_by_self:
                filtered_by_self_reaction += 1
                continue

            retained_views.append(view)

        views = retained_views

    payload: dict[str, Any] = {
        "count": len(views),
        "unreadChatsCount": len([item for item in views if item["unreadCount"] > 0]),
        "chats": views,
    }
    if unread_only and inferred_unread_count > 0:
        payload["unreadInference"] = {
            "enabled": True,
            "strategy": "latest_message_sender_not_self_when_unread_field_missing",
            "inferredChatsCount": inferred_unread_count,
        }
    if exclude_reacted_by_self:
        payload["selfReactionFilter"] = {
            "enabled": True,
            "excludedCount": filtered_by_self_reaction,
        }
    if isinstance(resp, dict):
        has_more = resp.get("has_more")
        if isinstance(has_more, bool):
            payload["hasMore"] = has_more
        next_token = resp.get("next_token")
        if isinstance(next_token, str) and next_token.strip():
            payload["nextToken"] = next_token

    utils.output(payload)


register_cliq_channels_chats_commands(
    cliq_app,
    cliq_channels_command=cliq_channels,
    cliq_chats_command=cliq_chats,
)


_cliq_org_directory_context = CliqOrgDirectoryContext(
    load_config=_cfg,
    require_account=lambda cfg: _require_account(cfg),
    get_cliq_client=lambda *args, **kwargs: _get_cliq_client(*args, **kwargs),
)


cliq_users = build_cliq_users_command(_cliq_org_directory_context)
cliq_teams = build_cliq_teams_command(_cliq_org_directory_context)


register_cliq_users_teams_commands(
    cliq_app,
    cliq_users_command=cliq_users,
    cliq_teams_command=cliq_teams,
)


_cliq_org_admin_context = CliqOrgAdminContext(
    load_config=_cfg,
    require_account=lambda cfg: _require_account(cfg),
    get_cliq_client=lambda *args, **kwargs: _get_cliq_client(*args, **kwargs),
)


cliq_departments = build_cliq_departments_command(_cliq_org_admin_context)
cliq_roles = build_cliq_roles_command(_cliq_org_admin_context)


register_cliq_departments_roles_commands(
    cliq_app,
    cliq_departments_command=cliq_departments,
    cliq_roles_command=cliq_roles,
)


cliq_designations = build_cliq_designations_command(_cliq_org_admin_context)
cliq_user_status = build_cliq_user_status_command(_cliq_org_admin_context)


register_cliq_designations_user_status_commands(
    cliq_app,
    cliq_designations_command=cliq_designations,
    cliq_user_status_command=cliq_user_status,
)


cliq_userfields = build_cliq_userfields_command(_cliq_org_admin_context)


register_cliq_userfields_commands(
    cliq_app,
    cliq_userfields_command=cliq_userfields,
)


_cliq_productivity_context = CliqProductivityContext(
    load_config=_cfg,
    require_account=lambda cfg: _require_account(cfg),
    get_cliq_client=lambda *args, **kwargs: _get_cliq_client(*args, **kwargs),
)


cliq_events = build_cliq_events_command(_cliq_productivity_context)
cliq_reminders = build_cliq_reminders_command(_cliq_productivity_context)


register_cliq_events_reminders_commands(
    cliq_app,
    cliq_events_command=cliq_events,
    cliq_reminders_command=cliq_reminders,
)


cliq_meetings = build_cliq_meetings_command(_cliq_productivity_context)
cliq_databases = build_cliq_databases_command(_cliq_productivity_context)


register_cliq_meetings_databases_commands(
    cliq_app,
    cliq_meetings_command=cliq_meetings,
    cliq_databases_command=cliq_databases,
)


_cliq_platform_extensions_context = CliqPlatformExtensionsContext(
    load_config=_cfg,
    require_account=lambda cfg: _require_account(cfg),
    get_cliq_client=lambda *args, **kwargs: _get_cliq_client(*args, **kwargs),
)


cliq_widgets = build_cliq_widgets_command(_cliq_platform_extensions_context)
cliq_map_tickers = build_cliq_map_tickers_command(_cliq_platform_extensions_context)


register_cliq_widgets_map_tickers_commands(
    cliq_app,
    cliq_widgets_command=cliq_widgets,
    cliq_map_tickers_command=cliq_map_tickers,
)


cliq_custom_domains = build_cliq_custom_domains_command(
    _cliq_platform_extensions_context
)
cliq_custom_emails = build_cliq_custom_emails_command(_cliq_platform_extensions_context)


register_cliq_custom_domains_emails_commands(
    cliq_app,
    cliq_custom_domains_command=cliq_custom_domains,
    cliq_custom_emails_command=cliq_custom_emails,
)


def cliq_apps(
    limit: int = typer.Option(50, "--limit", "-n", help="Max apps to return."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """List Cliq apps."""

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


def cliq_app_get(
    app_id: str = typer.Argument(..., help="Cliq app id."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Get one Cliq app by id."""

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


register_cliq_app_catalog_commands(
    cliq_app,
    cliq_apps_command=cliq_apps,
    cliq_app_get_command=cliq_app_get,
)


def cliq_apps_bridge_run(
    limit: int = typer.Option(
        50,
        "--limit",
        "-n",
        help="Max apps to request through membrane input.",
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
        help="Optional JSON input passed to membrane --input (merged with limit).",
    ),
) -> None:
    """Run Cliq apps listing through membrane bridge (explicit opt-in)."""
    if bridge.strip().lower() != "membrane":
        utils.error_exit(
            "unsupported_bridge",
            "Only --bridge membrane is supported right now.",
        )

    resolved_action_id = (action_id or "").strip() or "apps"

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
        resolved_input = {"limit": limit}
    elif isinstance(resolved_input, dict):
        resolved_input = dict(resolved_input)
        resolved_input.setdefault("limit", limit)
    else:
        utils.error_exit(
            "invalid_input_json",
            "--input-json must decode to a JSON object for apps bridge runs.",
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
            "input": resolved_input,
            "result": result,
        }
    )


def cliq_app_get_bridge_run(
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
    """Run Cliq app detail lookup through membrane bridge (explicit opt-in)."""
    if bridge.strip().lower() != "membrane":
        utils.error_exit(
            "unsupported_bridge",
            "Only --bridge membrane is supported right now.",
        )

    resolved_app_id = app_id.strip()
    if not resolved_app_id:
        utils.error_exit("invalid_app_id", "App id cannot be empty")

    resolved_action_id = (action_id or "").strip() or "app-get"

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
            "--input-json must decode to a JSON object for app-get bridge runs.",
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


register_cliq_app_catalog_bridge_commands(
    cliq_app,
    cliq_apps_bridge_run_command=cliq_apps_bridge_run,
    cliq_app_get_bridge_run_command=cliq_app_get_bridge_run,
)


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
    """List one app's permissions and scopes."""

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


def cliq_app_permission_get(
    app_id: str = typer.Argument(..., help="Cliq app id."),
    permission_id: str = typer.Argument(..., help="Cliq app permission id."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Get one app permission by id."""

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


register_cliq_app_permissions_commands(
    cliq_app,
    cliq_app_permissions_command=cliq_app_permissions,
    cliq_app_permission_get_command=cliq_app_permission_get,
)


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
    """List one app's installs."""

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


def cliq_app_install_get(
    app_id: str = typer.Argument(..., help="Cliq app id."),
    install_id: str = typer.Argument(..., help="Cliq app install id."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Get one app install by id."""

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


register_cliq_app_installs_commands(
    cliq_app,
    cliq_app_installs_command=cliq_app_installs,
    cliq_app_install_get_command=cliq_app_install_get,
)


def cliq_app_permissions_bridge_run(
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
    """Run Cliq app-permission listing through membrane bridge (explicit opt-in)."""
    if bridge.strip().lower() != "membrane":
        utils.error_exit(
            "unsupported_bridge",
            "Only --bridge membrane is supported right now.",
        )

    resolved_app_id = app_id.strip()
    if not resolved_app_id:
        utils.error_exit("invalid_app_id", "App id cannot be empty")

    resolved_action_id = (action_id or "").strip() or "app-permissions"

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
            "--input-json must decode to a JSON object for app-permissions bridge runs.",
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


def cliq_app_permission_get_bridge_run(
    app_id: str = typer.Argument(..., help="Cliq app id."),
    permission_id: str = typer.Argument(..., help="Cliq app permission id."),
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
        help="Optional JSON input passed to membrane --input (merged with appId + permissionId).",
    ),
) -> None:
    """Run Cliq app-permission detail through membrane bridge (explicit opt-in)."""
    if bridge.strip().lower() != "membrane":
        utils.error_exit(
            "unsupported_bridge",
            "Only --bridge membrane is supported right now.",
        )

    resolved_app_id = app_id.strip()
    if not resolved_app_id:
        utils.error_exit("invalid_app_id", "App id cannot be empty")

    resolved_permission_id = permission_id.strip()
    if not resolved_permission_id:
        utils.error_exit("invalid_permission_id", "Permission id cannot be empty")

    resolved_action_id = (action_id or "").strip() or "app-permission-get"

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
            "permissionId": resolved_permission_id,
        }
    elif isinstance(resolved_input, dict):
        resolved_input = dict(resolved_input)
        resolved_input.setdefault("appId", resolved_app_id)
        resolved_input.setdefault("permissionId", resolved_permission_id)
    else:
        utils.error_exit(
            "invalid_input_json",
            "--input-json must decode to a JSON object for app-permission-get bridge runs.",
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
            "permissionId": resolved_permission_id,
            "input": resolved_input,
            "result": result,
        }
    )


register_cliq_app_permissions_bridge_commands(
    cliq_app,
    cliq_app_permissions_bridge_run_command=cliq_app_permissions_bridge_run,
    cliq_app_permission_get_bridge_run_command=cliq_app_permission_get_bridge_run,
)


def cliq_app_install_get_bridge_run(
    app_id: str = typer.Argument(..., help="Cliq app id."),
    install_id: str = typer.Argument(..., help="Cliq app install id."),
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
        help="Optional JSON input passed to membrane --input (merged with appId + installId).",
    ),
) -> None:
    """Run Cliq app-install detail through membrane bridge (explicit opt-in)."""
    if bridge.strip().lower() != "membrane":
        utils.error_exit(
            "unsupported_bridge",
            "Only --bridge membrane is supported right now.",
        )

    resolved_app_id = app_id.strip()
    if not resolved_app_id:
        utils.error_exit("invalid_app_id", "App id cannot be empty")

    resolved_install_id = install_id.strip()
    if not resolved_install_id:
        utils.error_exit("invalid_install_id", "Install id cannot be empty")

    resolved_action_id = (action_id or "").strip() or "app-install-get"

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
            "installId": resolved_install_id,
        }
    elif isinstance(resolved_input, dict):
        resolved_input = dict(resolved_input)
        resolved_input.setdefault("appId", resolved_app_id)
        resolved_input.setdefault("installId", resolved_install_id)
    else:
        utils.error_exit(
            "invalid_input_json",
            "--input-json must decode to a JSON object for app-install-get bridge runs.",
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
            "installId": resolved_install_id,
            "input": resolved_input,
            "result": result,
        }
    )


def cliq_app_installs_bridge_run(
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
    """Run Cliq app-install listing through membrane bridge (explicit opt-in)."""
    if bridge.strip().lower() != "membrane":
        utils.error_exit(
            "unsupported_bridge",
            "Only --bridge membrane is supported right now.",
        )

    resolved_app_id = app_id.strip()
    if not resolved_app_id:
        utils.error_exit("invalid_app_id", "App id cannot be empty")

    resolved_action_id = (action_id or "").strip() or "app-installs"

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
            "--input-json must decode to a JSON object for app-installs bridge runs.",
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


register_cliq_app_installs_bridge_commands(
    cliq_app,
    cliq_app_installs_bridge_run_command=cliq_app_installs_bridge_run,
    cliq_app_install_get_bridge_run_command=cliq_app_install_get_bridge_run,
)


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
    """List one app's commands."""

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


def cliq_app_command_get(
    app_id: str = typer.Argument(..., help="Cliq app id."),
    command_id: str = typer.Argument(..., help="Cliq app command id."),
    network: Optional[str] = typer.Option(
        None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
    ),
) -> None:
    """Get one app command by id."""

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


register_cliq_app_commands_commands(
    cliq_app,
    cliq_app_commands_command=cliq_app_commands,
    cliq_app_command_get_command=cliq_app_command_get,
)


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


register_cliq_app_commands_bridge_commands(
    cliq_app,
    cliq_app_commands_bridge_run_command=cliq_app_commands_bridge_run,
    cliq_app_command_get_bridge_run_command=cliq_app_command_get_bridge_run,
)


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
    """Export Cliq chats or one chat's message history."""

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


register_cliq_export_commands(
    cliq_app,
    cliq_export_chats_command=cliq_export_chats,
    cliq_export_chats_bridge_run_command=cliq_export_chats_bridge_run,
)


_cliq_identity_context = CliqIdentityContext(
    load_config=_cfg,
    require_account=lambda cfg: _require_account(cfg),
    get_cliq_client=lambda *args, **kwargs: _get_cliq_client(*args, **kwargs),
)


cliq_whoami = build_cliq_whoami_command(_cliq_identity_context)
cliq_user_resolve = build_cliq_user_resolve_command(_cliq_identity_context)


register_cliq_identity_commands(
    cliq_app,
    cliq_whoami_command=cliq_whoami,
    cliq_user_resolve_command=cliq_user_resolve,
)


_cliq_channel_management_context = CliqChannelManagementContext(
    load_config=_cfg,
    require_account=lambda cfg: _require_account(cfg),
    get_cliq_client=lambda *args, **kwargs: _get_cliq_client(*args, **kwargs),
)


cliq_members = build_cliq_members_command(_cliq_channel_management_context)
cliq_channel_create = build_cliq_channel_create_command(
    _cliq_channel_management_context
)


register_cliq_channel_membership_commands(
    cliq_app,
    cliq_members_command=cliq_members,
    cliq_channel_create_command=cliq_channel_create,
)


cliq_channel_rename = build_cliq_channel_rename_command(
    _cliq_channel_management_context
)
cliq_channel_topic = build_cliq_channel_topic_command(_cliq_channel_management_context)


register_cliq_channel_metadata_commands(
    cliq_app,
    cliq_channel_rename_command=cliq_channel_rename,
    cliq_channel_topic_command=cliq_channel_topic,
)


cliq_member_add = build_cliq_member_add_command(_cliq_channel_management_context)
cliq_member_remove = build_cliq_member_remove_command(_cliq_channel_management_context)


register_cliq_channel_member_management_commands(
    cliq_app,
    cliq_member_add_command=cliq_member_add,
    cliq_member_remove_command=cliq_member_remove,
)


cliq_channel_archive = build_cliq_channel_archive_command(
    _cliq_channel_management_context
)
cliq_channel_delete = build_cliq_channel_delete_command(
    _cliq_channel_management_context
)


register_cliq_channel_lifecycle_commands(
    cliq_app,
    cliq_channel_archive_command=cliq_channel_archive,
    cliq_channel_delete_command=cliq_channel_delete,
)


cliq_channel_unarchive = build_cliq_channel_unarchive_command(
    _cliq_channel_management_context
)


register_cliq_channel_unarchive_commands(
    cliq_app,
    cliq_channel_unarchive_command=cliq_channel_unarchive,
)


_cliq_threading_context = CliqThreadingContext(
    load_config=_cfg,
    require_account=lambda cfg: _require_account(cfg),
    get_cliq_client=lambda *args, **kwargs: _get_cliq_client(*args, **kwargs),
)


cliq_thread_create = build_cliq_thread_create_command(_cliq_threading_context)
cliq_thread_reply = build_cliq_thread_reply_command(_cliq_threading_context)


register_cliq_thread_commands(
    cliq_app,
    cliq_thread_create_command=cliq_thread_create,
    cliq_thread_reply_command=cliq_thread_reply,
)


cliq_threads = build_cliq_threads_command(_cliq_threading_context)


register_cliq_threads_commands(
    cliq_app,
    cliq_threads_command=cliq_threads,
)


_cliq_scheduling_context = CliqSchedulingContext(
    load_config=_cfg,
    require_account=lambda cfg: _require_account(cfg),
    get_cliq_client=lambda *args, **kwargs: _get_cliq_client(*args, **kwargs),
)


cliq_schedule = build_cliq_schedule_command(_cliq_scheduling_context)


_cliq_bots_context = CliqBotsContext(
    load_config=_cfg,
    require_account=lambda cfg: _require_account(cfg),
    get_cliq_client=lambda *args, **kwargs: _get_cliq_client(*args, **kwargs),
)


cliq_post_to_bot = build_cliq_post_to_bot_command(_cliq_bots_context)


register_cliq_post_to_bot_commands(
    cliq_app,
    cliq_post_to_bot_command=cliq_post_to_bot,
)


cliq_bot_subscribers = build_cliq_bot_subscribers_command(_cliq_bots_context)


register_cliq_bot_subscribers_commands(
    cliq_app,
    cliq_bot_subscribers_command=cliq_bot_subscribers,
)


cliq_trigger_bot = build_cliq_trigger_bot_command(_cliq_bots_context)


register_cliq_trigger_bot_commands(
    cliq_app,
    cliq_trigger_bot_command=cliq_trigger_bot,
)


cliq_scheduled = build_cliq_scheduled_command(_cliq_scheduling_context)
cliq_scheduled_get = build_cliq_scheduled_get_command(_cliq_scheduling_context)


register_cliq_scheduled_lifecycle_commands(
    cliq_app,
    cliq_scheduled_command=cliq_scheduled,
    cliq_scheduled_get_command=cliq_scheduled_get,
)


cliq_scheduled_cancel = build_cliq_scheduled_cancel_command(_cliq_scheduling_context)


cliq_leave = build_cliq_leave_command(_cliq_channel_management_context)


register_cliq_scheduled_cancel_leave_commands(
    cliq_app,
    cliq_scheduled_cancel_command=cliq_scheduled_cancel,
    cliq_leave_command=cliq_leave,
)


cliq_mute = build_cliq_mute_command(_cliq_channel_management_context)
cliq_unmute = build_cliq_unmute_command(_cliq_channel_management_context)


register_cliq_mute_unmute_commands(
    cliq_app,
    cliq_mute_command=cliq_mute,
    cliq_unmute_command=cliq_unmute,
)


cliq_pin = build_cliq_pin_command(_cliq_channel_management_context)
cliq_unpin = build_cliq_unpin_command(_cliq_channel_management_context)


register_cliq_pin_unpin_commands(
    cliq_app,
    cliq_pin_command=cliq_pin,
    cliq_unpin_command=cliq_unpin,
)


cliq_pinned = build_cliq_pinned_command(_cliq_channel_management_context)


register_cliq_pinned_commands(
    cliq_app,
    cliq_pinned_command=cliq_pinned,
)


cliq_thread_followers = build_cliq_thread_followers_command(_cliq_threading_context)
cliq_thread_state = build_cliq_thread_state_command(_cliq_threading_context)


register_cliq_thread_state_commands(
    cliq_app,
    cliq_thread_followers_command=cliq_thread_followers,
    cliq_thread_state_command=cliq_thread_state,
)


_cliq_message_retrieval_context = CliqMessageRetrievalContext(
    load_config=_cfg,
    require_account=lambda cfg: _require_account(cfg),
    get_cliq_client=lambda *args, **kwargs: _get_cliq_client(*args, **kwargs),
    infer_message_types=_cliq.ZohoCliqClient.infer_message_types,
    extract_message_id=_cliq.ZohoCliqClient._extract_message_id,
    build_watch_context_seed=_cliq.ZohoCliqClient.build_watch_context_seed,
    typed_messages=_cliq_typed_messages,
)


cliq_search = build_cliq_search_command(_cliq_message_retrieval_context)


register_cliq_message_discovery_commands(
    cliq_app,
    cliq_schedule_command=cliq_schedule,
    cliq_search_command=cliq_search,
)


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


register_cliq_file_voice_commands(
    cliq_app,
    cliq_file_command=cliq_file,
    cliq_voice_command=cliq_voice,
)


cliq_messages = build_cliq_messages_command(_cliq_message_retrieval_context)
cliq_message = build_cliq_message_command(_cliq_message_retrieval_context)


register_cliq_messages_message_commands(
    cliq_app,
    cliq_messages_command=cliq_messages,
    cliq_message_command=cliq_message,
)


cliq_context = build_cliq_context_command(_cliq_message_retrieval_context)
cliq_watch_context = build_cliq_watch_context_command(_cliq_message_retrieval_context)


register_cliq_context_watch_context_commands(
    cliq_app,
    cliq_context_command=cliq_context,
    cliq_watch_context_command=cliq_watch_context,
)


def cliq_watch_act(
    watch_file: str = typer.Option(
        "-",
        "--watch-file",
        help="Path to watch-context JSON payload (use '-' to read from stdin).",
    ),
    action: Optional[str] = typer.Option(
        None,
        "--action",
        help=(
            "Action to execute from the watch payload: reply-latest or "
            "read-ack-latest (default: reply-latest)."
        ),
    ),
    escalation_action: bool = typer.Option(
        False,
        "--escalation-action",
        help=("Resolve --action from operatorWorkflow.externalEscalation.actionHint."),
    ),
    text: Optional[str] = typer.Option(
        None,
        "--text",
        "-t",
        help="Reply text to send (required for --action reply-latest).",
    ),
    message_id: Optional[str] = typer.Option(
        None,
        "--message-id",
        help="Optional explicit message id to read-ack when --action read-ack-latest.",
    ),
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
    status_flow: bool = typer.Option(
        False,
        "--status-flow/--no-status-flow",
        help=(
            "Auto-apply status reactions on the target message during watch-act "
            "lifecycle (received/thinking/writing/testing/done/failed)."
        ),
    ),
) -> None:
    """Execute one deterministic action from watch payload."""
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

    selected_action = (action or "").strip().lower()
    selected_action_source = ""
    selected_action_source_path = ""
    workflow, workflow_source_root = _extract_operator_workflow_with_source(
        watch_payload
    )
    if not workflow_source_root:
        workflow = {}

    if selected_action:
        selected_action_source = "explicit-override"
        selected_action_source_path = "--action"

    if escalation_action and not selected_action:
        escalation_action_hint = ""
        escalation_action_hint_path = ""
        if workflow_source_root:
            escalation = workflow.get("externalEscalation")
            escalation_source_root = f"{workflow_source_root}.externalEscalation"
            if not isinstance(escalation, dict):
                escalation = workflow.get("external_escalation")
                escalation_source_root = f"{workflow_source_root}.external_escalation"
            if not isinstance(escalation, dict):
                escalation = workflow.get("external-escalation")
                escalation_source_root = f"{workflow_source_root}.external-escalation"
            if isinstance(escalation, dict):
                candidates: list[tuple[Any, str]] = [
                    (
                        escalation.get("watchActAction"),
                        f"{escalation_source_root}.watchActAction",
                    ),
                    (
                        escalation.get("watch_act_action"),
                        f"{escalation_source_root}.watch_act_action",
                    ),
                    (
                        escalation.get("watch-act-action"),
                        f"{escalation_source_root}.watch-act-action",
                    ),
                    (
                        escalation.get("action"),
                        f"{escalation_source_root}.action",
                    ),
                    (
                        escalation.get("actionId"),
                        f"{escalation_source_root}.actionId",
                    ),
                    (
                        escalation.get("actionID"),
                        f"{escalation_source_root}.actionID",
                    ),
                    (
                        escalation.get("actionid"),
                        f"{escalation_source_root}.actionid",
                    ),
                    (
                        escalation.get("action_id"),
                        f"{escalation_source_root}.action_id",
                    ),
                    (
                        escalation.get("bridgeActionId"),
                        f"{escalation_source_root}.bridgeActionId",
                    ),
                    (
                        escalation.get("bridgeActionid"),
                        f"{escalation_source_root}.bridgeActionid",
                    ),
                    (
                        escalation.get("bridgeActionID"),
                        f"{escalation_source_root}.bridgeActionID",
                    ),
                    (
                        escalation.get("bridgeAction_id"),
                        f"{escalation_source_root}.bridgeAction_id",
                    ),
                    (
                        escalation.get("bridge_actionid"),
                        f"{escalation_source_root}.bridge_actionid",
                    ),
                    (
                        escalation.get("bridge_actionID"),
                        f"{escalation_source_root}.bridge_actionID",
                    ),
                    (
                        escalation.get("bridge_action_id"),
                        f"{escalation_source_root}.bridge_action_id",
                    ),
                    (
                        escalation.get("bridge_actionId"),
                        f"{escalation_source_root}.bridge_actionId",
                    ),
                    (
                        escalation.get("bridge-action-id"),
                        f"{escalation_source_root}.bridge-action-id",
                    ),
                    (
                        escalation.get("bridge-action_id"),
                        f"{escalation_source_root}.bridge-action_id",
                    ),
                    (
                        escalation.get("bridge-actionid"),
                        f"{escalation_source_root}.bridge-actionid",
                    ),
                    (
                        escalation.get("bridge-actionId"),
                        f"{escalation_source_root}.bridge-actionId",
                    ),
                    (
                        escalation.get("bridge-actionID"),
                        f"{escalation_source_root}.bridge-actionID",
                    ),
                    (
                        escalation.get("defaultActionId"),
                        f"{escalation_source_root}.defaultActionId",
                    ),
                    (
                        escalation.get("defaultActionID"),
                        f"{escalation_source_root}.defaultActionID",
                    ),
                    (
                        escalation.get("defaultAction_id"),
                        f"{escalation_source_root}.defaultAction_id",
                    ),
                    (
                        escalation.get("default_action_id"),
                        f"{escalation_source_root}.default_action_id",
                    ),
                    (
                        escalation.get("default_actionId"),
                        f"{escalation_source_root}.default_actionId",
                    ),
                    (
                        escalation.get("default_actionID"),
                        f"{escalation_source_root}.default_actionID",
                    ),
                    (
                        escalation.get("default-action-id"),
                        f"{escalation_source_root}.default-action-id",
                    ),
                    (
                        escalation.get("default-actionid"),
                        f"{escalation_source_root}.default-actionid",
                    ),
                    (
                        escalation.get("default-actionId"),
                        f"{escalation_source_root}.default-actionId",
                    ),
                    (
                        escalation.get("default-actionID"),
                        f"{escalation_source_root}.default-actionID",
                    ),
                ]
                hint = escalation.get("actionHint")
                hint_source_root = f"{escalation_source_root}.actionHint"
                if not isinstance(hint, dict):
                    hint = escalation.get("action_hint")
                    hint_source_root = f"{escalation_source_root}.action_hint"
                if not isinstance(hint, dict):
                    hint = escalation.get("action-hint")
                    hint_source_root = f"{escalation_source_root}.action-hint"
                if isinstance(hint, dict):
                    candidates.extend(
                        [
                            (
                                hint.get("watchActAction"),
                                f"{hint_source_root}.watchActAction",
                            ),
                            (
                                hint.get("watch_act_action"),
                                f"{hint_source_root}.watch_act_action",
                            ),
                            (
                                hint.get("watch-act-action"),
                                f"{hint_source_root}.watch-act-action",
                            ),
                            (
                                hint.get("action"),
                                f"{hint_source_root}.action",
                            ),
                            (
                                hint.get("actionId"),
                                f"{hint_source_root}.actionId",
                            ),
                            (
                                hint.get("actionid"),
                                f"{hint_source_root}.actionid",
                            ),
                            (
                                hint.get("actionID"),
                                f"{hint_source_root}.actionID",
                            ),
                            (
                                hint.get("action_id"),
                                f"{hint_source_root}.action_id",
                            ),
                            (
                                hint.get("bridgeActionId"),
                                f"{hint_source_root}.bridgeActionId",
                            ),
                            (
                                hint.get("bridgeActionid"),
                                f"{hint_source_root}.bridgeActionid",
                            ),
                            (
                                hint.get("bridgeActionID"),
                                f"{hint_source_root}.bridgeActionID",
                            ),
                            (
                                hint.get("bridgeAction_id"),
                                f"{hint_source_root}.bridgeAction_id",
                            ),
                            (
                                hint.get("bridge_actionid"),
                                f"{hint_source_root}.bridge_actionid",
                            ),
                            (
                                hint.get("bridge_actionID"),
                                f"{hint_source_root}.bridge_actionID",
                            ),
                            (
                                hint.get("bridge_action_id"),
                                f"{hint_source_root}.bridge_action_id",
                            ),
                            (
                                hint.get("bridge_actionId"),
                                f"{hint_source_root}.bridge_actionId",
                            ),
                            (
                                hint.get("bridge-action-id"),
                                f"{hint_source_root}.bridge-action-id",
                            ),
                            (
                                hint.get("bridge-action_id"),
                                f"{hint_source_root}.bridge-action_id",
                            ),
                            (
                                hint.get("bridge-actionid"),
                                f"{hint_source_root}.bridge-actionid",
                            ),
                            (
                                hint.get("bridge-actionId"),
                                f"{hint_source_root}.bridge-actionId",
                            ),
                            (
                                hint.get("bridge-actionID"),
                                f"{hint_source_root}.bridge-actionID",
                            ),
                            (
                                hint.get("defaultAction"),
                                f"{hint_source_root}.defaultAction",
                            ),
                            (
                                hint.get("default_action"),
                                f"{hint_source_root}.default_action",
                            ),
                            (
                                hint.get("default-action"),
                                f"{hint_source_root}.default-action",
                            ),
                            (
                                hint.get("defaultActionId"),
                                f"{hint_source_root}.defaultActionId",
                            ),
                            (
                                hint.get("defaultActionid"),
                                f"{hint_source_root}.defaultActionid",
                            ),
                            (
                                hint.get("defaultActionID"),
                                f"{hint_source_root}.defaultActionID",
                            ),
                            (
                                hint.get("defaultAction_id"),
                                f"{hint_source_root}.defaultAction_id",
                            ),
                            (
                                hint.get("default_action_id"),
                                f"{hint_source_root}.default_action_id",
                            ),
                            (
                                hint.get("default_actionId"),
                                f"{hint_source_root}.default_actionId",
                            ),
                            (
                                hint.get("default_actionid"),
                                f"{hint_source_root}.default_actionid",
                            ),
                            (
                                hint.get("default_actionID"),
                                f"{hint_source_root}.default_actionID",
                            ),
                            (
                                hint.get("default-action-id"),
                                f"{hint_source_root}.default-action-id",
                            ),
                            (
                                hint.get("default-actionid"),
                                f"{hint_source_root}.default-actionid",
                            ),
                            (
                                hint.get("default-actionId"),
                                f"{hint_source_root}.default-actionId",
                            ),
                            (
                                hint.get("default-actionID"),
                                f"{hint_source_root}.default-actionID",
                            ),
                        ]
                    )
                candidates.extend(
                    [
                        (
                            escalation.get("defaultAction"),
                            f"{escalation_source_root}.defaultAction",
                        ),
                        (
                            escalation.get("default_action"),
                            f"{escalation_source_root}.default_action",
                        ),
                        (
                            escalation.get("default-action"),
                            f"{escalation_source_root}.default-action",
                        ),
                        (
                            escalation.get("defaultActionId"),
                            f"{escalation_source_root}.defaultActionId",
                        ),
                        (
                            escalation.get("defaultActionid"),
                            f"{escalation_source_root}.defaultActionid",
                        ),
                        (
                            escalation.get("defaultActionID"),
                            f"{escalation_source_root}.defaultActionID",
                        ),
                        (
                            escalation.get("defaultAction_id"),
                            f"{escalation_source_root}.defaultAction_id",
                        ),
                        (
                            escalation.get("default_action_id"),
                            f"{escalation_source_root}.default_action_id",
                        ),
                        (
                            escalation.get("default_actionId"),
                            f"{escalation_source_root}.default_actionId",
                        ),
                        (
                            escalation.get("default_actionid"),
                            f"{escalation_source_root}.default_actionid",
                        ),
                        (
                            escalation.get("default_actionID"),
                            f"{escalation_source_root}.default_actionID",
                        ),
                        (
                            escalation.get("default-action-id"),
                            f"{escalation_source_root}.default-action-id",
                        ),
                        (
                            escalation.get("default-actionid"),
                            f"{escalation_source_root}.default-actionid",
                        ),
                        (
                            escalation.get("default-actionId"),
                            f"{escalation_source_root}.default-actionId",
                        ),
                        (
                            escalation.get("default-actionID"),
                            f"{escalation_source_root}.default-actionID",
                        ),
                    ]
                )
                for candidate, source_path in candidates:
                    value = str(candidate or "").strip().lower()
                    if value:
                        escalation_action_hint = value
                        escalation_action_hint_path = source_path
                        break

        if not escalation_action_hint:
            utils.error_exit(
                "invalid_action",
                "--escalation-action requires operatorWorkflow.externalEscalation.actionHint.watchActAction (or pass --action).",
            )
        selected_action = escalation_action_hint
        selected_action_source = "escalation-hint"
        selected_action_source_path = escalation_action_hint_path

    if not selected_action:
        watch_loop_hint = ""
        watch_loop_hint_path = ""
        if workflow_source_root:
            internal_loop = workflow.get("internalLoop")
            internal_loop_source_root = f"{workflow_source_root}.internalLoop"
            if not isinstance(internal_loop, dict):
                internal_loop = workflow.get("internal_loop")
                internal_loop_source_root = f"{workflow_source_root}.internal_loop"
            if not isinstance(internal_loop, dict):
                internal_loop = workflow.get("internal-loop")
                internal_loop_source_root = f"{workflow_source_root}.internal-loop"
            if isinstance(internal_loop, dict):
                candidates: list[tuple[Any, str]] = [
                    (
                        internal_loop.get("watchActAction"),
                        f"{internal_loop_source_root}.watchActAction",
                    ),
                    (
                        internal_loop.get("watch_act_action"),
                        f"{internal_loop_source_root}.watch_act_action",
                    ),
                    (
                        internal_loop.get("watch-act-action"),
                        f"{internal_loop_source_root}.watch-act-action",
                    ),
                    (
                        internal_loop.get("bridgeActionId"),
                        f"{internal_loop_source_root}.bridgeActionId",
                    ),
                    (
                        internal_loop.get("bridgeActionID"),
                        f"{internal_loop_source_root}.bridgeActionID",
                    ),
                    (
                        internal_loop.get("bridgeActionid"),
                        f"{internal_loop_source_root}.bridgeActionid",
                    ),
                    (
                        internal_loop.get("bridgeAction_id"),
                        f"{internal_loop_source_root}.bridgeAction_id",
                    ),
                    (
                        internal_loop.get("bridge_actionID"),
                        f"{internal_loop_source_root}.bridge_actionID",
                    ),
                    (
                        internal_loop.get("bridge_action_id"),
                        f"{internal_loop_source_root}.bridge_action_id",
                    ),
                    (
                        internal_loop.get("bridge_actionId"),
                        f"{internal_loop_source_root}.bridge_actionId",
                    ),
                    (
                        internal_loop.get("bridge_actionid"),
                        f"{internal_loop_source_root}.bridge_actionid",
                    ),
                    (
                        internal_loop.get("bridge-action-id"),
                        f"{internal_loop_source_root}.bridge-action-id",
                    ),
                    (
                        internal_loop.get("bridge-actionid"),
                        f"{internal_loop_source_root}.bridge-actionid",
                    ),
                    (
                        internal_loop.get("bridge-actionId"),
                        f"{internal_loop_source_root}.bridge-actionId",
                    ),
                    (
                        internal_loop.get("bridge-actionID"),
                        f"{internal_loop_source_root}.bridge-actionID",
                    ),
                    (
                        internal_loop.get("bridge-action_id"),
                        f"{internal_loop_source_root}.bridge-action_id",
                    ),
                    (
                        internal_loop.get("action"),
                        f"{internal_loop_source_root}.action",
                    ),
                    (
                        internal_loop.get("actionId"),
                        f"{internal_loop_source_root}.actionId",
                    ),
                    (
                        internal_loop.get("actionid"),
                        f"{internal_loop_source_root}.actionid",
                    ),
                    (
                        internal_loop.get("actionID"),
                        f"{internal_loop_source_root}.actionID",
                    ),
                    (
                        internal_loop.get("action_id"),
                        f"{internal_loop_source_root}.action_id",
                    ),
                    (
                        internal_loop.get("defaultActionId"),
                        f"{internal_loop_source_root}.defaultActionId",
                    ),
                    (
                        internal_loop.get("defaultActionID"),
                        f"{internal_loop_source_root}.defaultActionID",
                    ),
                    (
                        internal_loop.get("default_action_id"),
                        f"{internal_loop_source_root}.default_action_id",
                    ),
                ]
                hint = internal_loop.get("actionHint")
                hint_source_root = f"{internal_loop_source_root}.actionHint"
                if not isinstance(hint, dict):
                    hint = internal_loop.get("action_hint")
                    hint_source_root = f"{internal_loop_source_root}.action_hint"
                if not isinstance(hint, dict):
                    hint = internal_loop.get("action-hint")
                    hint_source_root = f"{internal_loop_source_root}.action-hint"
                if isinstance(hint, dict):
                    candidates.extend(
                        [
                            (
                                hint.get("watchActAction"),
                                f"{hint_source_root}.watchActAction",
                            ),
                            (
                                hint.get("watch_act_action"),
                                f"{hint_source_root}.watch_act_action",
                            ),
                            (
                                hint.get("watch-act-action"),
                                f"{hint_source_root}.watch-act-action",
                            ),
                            (
                                hint.get("action"),
                                f"{hint_source_root}.action",
                            ),
                            (
                                hint.get("bridgeActionId"),
                                f"{hint_source_root}.bridgeActionId",
                            ),
                            (
                                hint.get("bridgeActionID"),
                                f"{hint_source_root}.bridgeActionID",
                            ),
                            (
                                hint.get("bridgeActionid"),
                                f"{hint_source_root}.bridgeActionid",
                            ),
                            (
                                hint.get("bridgeAction_id"),
                                f"{hint_source_root}.bridgeAction_id",
                            ),
                            (
                                hint.get("bridge_actionID"),
                                f"{hint_source_root}.bridge_actionID",
                            ),
                            (
                                hint.get("bridge_action_id"),
                                f"{hint_source_root}.bridge_action_id",
                            ),
                            (
                                hint.get("bridge_actionId"),
                                f"{hint_source_root}.bridge_actionId",
                            ),
                            (
                                hint.get("bridge_actionid"),
                                f"{hint_source_root}.bridge_actionid",
                            ),
                            (
                                hint.get("bridge-action-id"),
                                f"{hint_source_root}.bridge-action-id",
                            ),
                            (
                                hint.get("bridge-actionid"),
                                f"{hint_source_root}.bridge-actionid",
                            ),
                            (
                                hint.get("bridge-actionId"),
                                f"{hint_source_root}.bridge-actionId",
                            ),
                            (
                                hint.get("bridge-actionID"),
                                f"{hint_source_root}.bridge-actionID",
                            ),
                            (
                                hint.get("bridge-action_id"),
                                f"{hint_source_root}.bridge-action_id",
                            ),
                            (
                                hint.get("actionId"),
                                f"{hint_source_root}.actionId",
                            ),
                            (
                                hint.get("actionid"),
                                f"{hint_source_root}.actionid",
                            ),
                            (
                                hint.get("actionID"),
                                f"{hint_source_root}.actionID",
                            ),
                            (
                                hint.get("action_id"),
                                f"{hint_source_root}.action_id",
                            ),
                            (
                                hint.get("defaultAction"),
                                f"{hint_source_root}.defaultAction",
                            ),
                            (
                                hint.get("default_action"),
                                f"{hint_source_root}.default_action",
                            ),
                            (
                                hint.get("defaultActionId"),
                                f"{hint_source_root}.defaultActionId",
                            ),
                            (
                                hint.get("defaultActionid"),
                                f"{hint_source_root}.defaultActionid",
                            ),
                            (
                                hint.get("defaultActionID"),
                                f"{hint_source_root}.defaultActionID",
                            ),
                            (
                                hint.get("defaultAction_id"),
                                f"{hint_source_root}.defaultAction_id",
                            ),
                            (
                                hint.get("default_action_id"),
                                f"{hint_source_root}.default_action_id",
                            ),
                            (
                                hint.get("default_actionId"),
                                f"{hint_source_root}.default_actionId",
                            ),
                            (
                                hint.get("default_actionid"),
                                f"{hint_source_root}.default_actionid",
                            ),
                            (
                                hint.get("default_actionID"),
                                f"{hint_source_root}.default_actionID",
                            ),
                        ]
                    )
                candidates.extend(
                    [
                        (
                            internal_loop.get("defaultAction"),
                            f"{internal_loop_source_root}.defaultAction",
                        ),
                        (
                            internal_loop.get("default_action"),
                            f"{internal_loop_source_root}.default_action",
                        ),
                        (
                            internal_loop.get("defaultActionId"),
                            f"{internal_loop_source_root}.defaultActionId",
                        ),
                        (
                            internal_loop.get("defaultActionid"),
                            f"{internal_loop_source_root}.defaultActionid",
                        ),
                        (
                            internal_loop.get("defaultActionID"),
                            f"{internal_loop_source_root}.defaultActionID",
                        ),
                        (
                            internal_loop.get("defaultAction_id"),
                            f"{internal_loop_source_root}.defaultAction_id",
                        ),
                        (
                            internal_loop.get("default_action_id"),
                            f"{internal_loop_source_root}.default_action_id",
                        ),
                        (
                            internal_loop.get("default_actionId"),
                            f"{internal_loop_source_root}.default_actionId",
                        ),
                        (
                            internal_loop.get("default_actionid"),
                            f"{internal_loop_source_root}.default_actionid",
                        ),
                        (
                            internal_loop.get("default_actionID"),
                            f"{internal_loop_source_root}.default_actionID",
                        ),
                    ]
                )

                for candidate, source_path in candidates:
                    value = str(candidate or "").strip().lower()
                    if value:
                        watch_loop_hint = value
                        watch_loop_hint_path = source_path
                        break

        if not watch_loop_hint:
            top_level_candidates: list[tuple[Any, str]] = [
                (watch_payload.get("actionId"), "watchPayload.actionId"),
                (watch_payload.get("actionid"), "watchPayload.actionid"),
                (watch_payload.get("actionID"), "watchPayload.actionID"),
                (watch_payload.get("action_id"), "watchPayload.action_id"),
                (watch_payload.get("action"), "watchPayload.action"),
                (watch_payload.get("bridgeActionId"), "watchPayload.bridgeActionId"),
                (watch_payload.get("bridgeActionid"), "watchPayload.bridgeActionid"),
                (watch_payload.get("bridgeActionID"), "watchPayload.bridgeActionID"),
                (
                    watch_payload.get("bridgeAction_id"),
                    "watchPayload.bridgeAction_id",
                ),
                (
                    watch_payload.get("bridge-action-id"),
                    "watchPayload.bridge-action-id",
                ),
                (
                    watch_payload.get("bridge-action_id"),
                    "watchPayload.bridge-action_id",
                ),
                (
                    watch_payload.get("bridge-actionid"),
                    "watchPayload.bridge-actionid",
                ),
                (
                    watch_payload.get("bridge-actionId"),
                    "watchPayload.bridge-actionId",
                ),
                (
                    watch_payload.get("bridge-actionID"),
                    "watchPayload.bridge-actionID",
                ),
                (
                    watch_payload.get("bridge_actionid"),
                    "watchPayload.bridge_actionid",
                ),
                (
                    watch_payload.get("bridge_actionID"),
                    "watchPayload.bridge_actionID",
                ),
                (
                    watch_payload.get("bridge_action_id"),
                    "watchPayload.bridge_action_id",
                ),
                (
                    watch_payload.get("bridge_actionId"),
                    "watchPayload.bridge_actionId",
                ),
                (watch_payload.get("defaultAction"), "watchPayload.defaultAction"),
                (watch_payload.get("default_action"), "watchPayload.default_action"),
                (watch_payload.get("default-action"), "watchPayload.default-action"),
                (
                    watch_payload.get("default-action-id"),
                    "watchPayload.default-action-id",
                ),
                (
                    watch_payload.get("default-action_id"),
                    "watchPayload.default-action_id",
                ),
                (
                    watch_payload.get("default-actionid"),
                    "watchPayload.default-actionid",
                ),
                (
                    watch_payload.get("default-actionId"),
                    "watchPayload.default-actionId",
                ),
                (
                    watch_payload.get("default-actionID"),
                    "watchPayload.default-actionID",
                ),
                (
                    watch_payload.get("defaultActionId"),
                    "watchPayload.defaultActionId",
                ),
                (
                    watch_payload.get("defaultActionid"),
                    "watchPayload.defaultActionid",
                ),
                (
                    watch_payload.get("defaultActionID"),
                    "watchPayload.defaultActionID",
                ),
                (
                    watch_payload.get("defaultAction_id"),
                    "watchPayload.defaultAction_id",
                ),
                (
                    watch_payload.get("default_action_id"),
                    "watchPayload.default_action_id",
                ),
                (
                    watch_payload.get("default_actionid"),
                    "watchPayload.default_actionid",
                ),
                (
                    watch_payload.get("default_actionId"),
                    "watchPayload.default_actionId",
                ),
                (
                    watch_payload.get("default_actionID"),
                    "watchPayload.default_actionID",
                ),
            ]
            for candidate, source_path in top_level_candidates:
                value = str(candidate or "").strip().lower()
                if value:
                    watch_loop_hint = value
                    watch_loop_hint_path = source_path
                    break

        if not watch_loop_hint:
            intake, intake_source_root = _extract_watch_intake_with_source(
                watch_payload
            )
            if isinstance(intake, dict):
                intake_candidates: list[tuple[Any, str]] = []
                bridge_cfg = intake.get("bridge")
                if isinstance(bridge_cfg, dict):
                    intake_candidates.extend(
                        [
                            (
                                bridge_cfg.get("actionId"),
                                f"{intake_source_root}.bridge.actionId",
                            ),
                            (
                                bridge_cfg.get("action_id"),
                                f"{intake_source_root}.bridge.action_id",
                            ),
                            (
                                bridge_cfg.get("bridgeActionId"),
                                f"{intake_source_root}.bridge.bridgeActionId",
                            ),
                            (
                                bridge_cfg.get("bridgeActionid"),
                                f"{intake_source_root}.bridge.bridgeActionid",
                            ),
                            (
                                bridge_cfg.get("bridgeActionID"),
                                f"{intake_source_root}.bridge.bridgeActionID",
                            ),
                            (
                                bridge_cfg.get("bridgeAction_id"),
                                f"{intake_source_root}.bridge.bridgeAction_id",
                            ),
                            (
                                bridge_cfg.get("bridge_actionID"),
                                f"{intake_source_root}.bridge.bridge_actionID",
                            ),
                            (
                                bridge_cfg.get("bridge_action_id"),
                                f"{intake_source_root}.bridge.bridge_action_id",
                            ),
                            (
                                bridge_cfg.get("bridge_actionId"),
                                f"{intake_source_root}.bridge.bridge_actionId",
                            ),
                            (
                                bridge_cfg.get("bridge_actionid"),
                                f"{intake_source_root}.bridge.bridge_actionid",
                            ),
                            (
                                bridge_cfg.get("bridge-action-id"),
                                f"{intake_source_root}.bridge.bridge-action-id",
                            ),
                            (
                                bridge_cfg.get("bridge-action_id"),
                                f"{intake_source_root}.bridge.bridge-action_id",
                            ),
                            (
                                bridge_cfg.get("bridge-actionid"),
                                f"{intake_source_root}.bridge.bridge-actionid",
                            ),
                            (
                                bridge_cfg.get("bridge-actionId"),
                                f"{intake_source_root}.bridge.bridge-actionId",
                            ),
                            (
                                bridge_cfg.get("bridge-actionID"),
                                f"{intake_source_root}.bridge.bridge-actionID",
                            ),
                        ]
                    )

                consume_cfg = intake.get("consume")
                if isinstance(consume_cfg, dict):
                    intake_candidates.extend(
                        [
                            (
                                consume_cfg.get("bridgeActionId"),
                                f"{intake_source_root}.consume.bridgeActionId",
                            ),
                            (
                                consume_cfg.get("BridgeActionId"),
                                f"{intake_source_root}.consume.BridgeActionId",
                            ),
                            (
                                consume_cfg.get("BridgeActionID"),
                                f"{intake_source_root}.consume.BridgeActionID",
                            ),
                            (
                                consume_cfg.get("BridgeActionid"),
                                f"{intake_source_root}.consume.BridgeActionid",
                            ),
                            (
                                consume_cfg.get("BridgeAction_id"),
                                f"{intake_source_root}.consume.BridgeAction_id",
                            ),
                            (
                                consume_cfg.get("BridgeAction_Id"),
                                f"{intake_source_root}.consume.BridgeAction_Id",
                            ),
                            (
                                consume_cfg.get("BridgeAction_ID"),
                                f"{intake_source_root}.consume.BridgeAction_ID",
                            ),
                            (
                                consume_cfg.get("BridgeAction-id"),
                                f"{intake_source_root}.consume.BridgeAction-id",
                            ),
                            (
                                consume_cfg.get("BridgeAction-Id"),
                                f"{intake_source_root}.consume.BridgeAction-Id",
                            ),
                            (
                                consume_cfg.get("BridgeAction-ID"),
                                f"{intake_source_root}.consume.BridgeAction-ID",
                            ),
                            (
                                consume_cfg.get("Bridge_ActionId"),
                                f"{intake_source_root}.consume.Bridge_ActionId",
                            ),
                            (
                                consume_cfg.get("Bridge_ActionID"),
                                f"{intake_source_root}.consume.Bridge_ActionID",
                            ),
                            (
                                consume_cfg.get("Bridge_Action_ID"),
                                f"{intake_source_root}.consume.Bridge_Action_ID",
                            ),
                            (
                                consume_cfg.get("Bridge_Action_Id"),
                                f"{intake_source_root}.consume.Bridge_Action_Id",
                            ),
                            (
                                consume_cfg.get("Bridge_Actionid"),
                                f"{intake_source_root}.consume.Bridge_Actionid",
                            ),
                            (
                                consume_cfg.get("Bridge_Action_id"),
                                f"{intake_source_root}.consume.Bridge_Action_id",
                            ),
                            (
                                consume_cfg.get("Bridge_Action-id"),
                                f"{intake_source_root}.consume.Bridge_Action-id",
                            ),
                            (
                                consume_cfg.get("Bridge_Action-Id"),
                                f"{intake_source_root}.consume.Bridge_Action-Id",
                            ),
                            (
                                consume_cfg.get("Bridge_Action-ID"),
                                f"{intake_source_root}.consume.Bridge_Action-ID",
                            ),
                            (
                                consume_cfg.get("Bridge-ActionId"),
                                f"{intake_source_root}.consume.Bridge-ActionId",
                            ),
                            (
                                consume_cfg.get("Bridge-ActionID"),
                                f"{intake_source_root}.consume.Bridge-ActionID",
                            ),
                            (
                                consume_cfg.get("Bridge-Action-ID"),
                                f"{intake_source_root}.consume.Bridge-Action-ID",
                            ),
                            (
                                consume_cfg.get("Bridge-Action-Id"),
                                f"{intake_source_root}.consume.Bridge-Action-Id",
                            ),
                            (
                                consume_cfg.get("Bridge-Actionid"),
                                f"{intake_source_root}.consume.Bridge-Actionid",
                            ),
                            (
                                consume_cfg.get("Bridge-Action_id"),
                                f"{intake_source_root}.consume.Bridge-Action_id",
                            ),
                            (
                                consume_cfg.get("Bridge-Action_Id"),
                                f"{intake_source_root}.consume.Bridge-Action_Id",
                            ),
                            (
                                consume_cfg.get("Bridge-Action_ID"),
                                f"{intake_source_root}.consume.Bridge-Action_ID",
                            ),
                            (
                                consume_cfg.get("bridgeActionID"),
                                f"{intake_source_root}.consume.bridgeActionID",
                            ),
                            (
                                consume_cfg.get("bridgeActionid"),
                                f"{intake_source_root}.consume.bridgeActionid",
                            ),
                            (
                                consume_cfg.get("bridge-ActionId"),
                                f"{intake_source_root}.consume.bridge-ActionId",
                            ),
                            (
                                consume_cfg.get("bridge-ActionID"),
                                f"{intake_source_root}.consume.bridge-ActionID",
                            ),
                            (
                                consume_cfg.get("bridge-Action-ID"),
                                f"{intake_source_root}.consume.bridge-Action-ID",
                            ),
                            (
                                consume_cfg.get("bridge-Action-Id"),
                                f"{intake_source_root}.consume.bridge-Action-Id",
                            ),
                            (
                                consume_cfg.get("bridge-Action-id"),
                                f"{intake_source_root}.consume.bridge-Action-id",
                            ),
                            (
                                consume_cfg.get("bridge-Action-iD"),
                                f"{intake_source_root}.consume.bridge-Action-iD",
                            ),
                            (
                                consume_cfg.get("bridge-Actionid"),
                                f"{intake_source_root}.consume.bridge-Actionid",
                            ),
                            (
                                consume_cfg.get("bridge-Action_id"),
                                f"{intake_source_root}.consume.bridge-Action_id",
                            ),
                            (
                                consume_cfg.get("bridge-Action_Id"),
                                f"{intake_source_root}.consume.bridge-Action_Id",
                            ),
                            (
                                consume_cfg.get("bridge-Action_ID"),
                                f"{intake_source_root}.consume.bridge-Action_ID",
                            ),
                            (
                                consume_cfg.get("bridge_ActionId"),
                                f"{intake_source_root}.consume.bridge_ActionId",
                            ),
                            (
                                consume_cfg.get("bridge_ActionID"),
                                f"{intake_source_root}.consume.bridge_ActionID",
                            ),
                            (
                                consume_cfg.get("bridge_Actionid"),
                                f"{intake_source_root}.consume.bridge_Actionid",
                            ),
                            (
                                consume_cfg.get("bridge_Action_id"),
                                f"{intake_source_root}.consume.bridge_Action_id",
                            ),
                            (
                                consume_cfg.get("bridge_Action_Id"),
                                f"{intake_source_root}.consume.bridge_Action_Id",
                            ),
                            (
                                consume_cfg.get("bridge_Action_ID"),
                                f"{intake_source_root}.consume.bridge_Action_ID",
                            ),
                            (
                                consume_cfg.get("bridgeAction-Id"),
                                f"{intake_source_root}.consume.bridgeAction-Id",
                            ),
                            (
                                consume_cfg.get("bridgeAction-id"),
                                f"{intake_source_root}.consume.bridgeAction-id",
                            ),
                            (
                                consume_cfg.get("bridgeAction-ID"),
                                f"{intake_source_root}.consume.bridgeAction-ID",
                            ),
                            (
                                consume_cfg.get("bridgeAction_id"),
                                f"{intake_source_root}.consume.bridgeAction_id",
                            ),
                            (
                                consume_cfg.get("bridgeAction_Id"),
                                f"{intake_source_root}.consume.bridgeAction_Id",
                            ),
                            (
                                consume_cfg.get("bridgeAction_ID"),
                                f"{intake_source_root}.consume.bridgeAction_ID",
                            ),
                            (
                                consume_cfg.get("bridge_action_id"),
                                f"{intake_source_root}.consume.bridge_action_id",
                            ),
                            (
                                consume_cfg.get("bridge_action_Id"),
                                f"{intake_source_root}.consume.bridge_action_Id",
                            ),
                            (
                                consume_cfg.get("bridge_actionId"),
                                f"{intake_source_root}.consume.bridge_actionId",
                            ),
                            (
                                consume_cfg.get("bridge_actionid"),
                                f"{intake_source_root}.consume.bridge_actionid",
                            ),
                            (
                                consume_cfg.get("bridge_actionID"),
                                f"{intake_source_root}.consume.bridge_actionID",
                            ),
                            (
                                consume_cfg.get("bridge-action-id"),
                                f"{intake_source_root}.consume.bridge-action-id",
                            ),
                            (
                                consume_cfg.get("bridge-action_id"),
                                f"{intake_source_root}.consume.bridge-action_id",
                            ),
                            (
                                consume_cfg.get("bridge-action_Id"),
                                f"{intake_source_root}.consume.bridge-action_Id",
                            ),
                            (
                                consume_cfg.get("bridge-actionId"),
                                f"{intake_source_root}.consume.bridge-actionId",
                            ),
                            (
                                consume_cfg.get("bridge-actionID"),
                                f"{intake_source_root}.consume.bridge-actionID",
                            ),
                            (
                                consume_cfg.get("bridge-action-Id"),
                                f"{intake_source_root}.consume.bridge-action-Id",
                            ),
                            (
                                consume_cfg.get("bridge-action-ID"),
                                f"{intake_source_root}.consume.bridge-action-ID",
                            ),
                            (
                                consume_cfg.get("bridge-action-iD"),
                                f"{intake_source_root}.consume.bridge-action-iD",
                            ),
                            (
                                consume_cfg.get("bridge-actionid"),
                                f"{intake_source_root}.consume.bridge-actionid",
                            ),
                            (
                                consume_cfg.get("ActionId"),
                                f"{intake_source_root}.consume.ActionId",
                            ),
                            (
                                consume_cfg.get("ActionID"),
                                f"{intake_source_root}.consume.ActionID",
                            ),
                            (
                                consume_cfg.get("Action-ID"),
                                f"{intake_source_root}.consume.Action-ID",
                            ),
                            (
                                consume_cfg.get("Action-Id"),
                                f"{intake_source_root}.consume.Action-Id",
                            ),
                            (
                                consume_cfg.get("Action-id"),
                                f"{intake_source_root}.consume.Action-id",
                            ),
                            (
                                consume_cfg.get("ACTIONID"),
                                f"{intake_source_root}.consume.ACTIONID",
                            ),
                            (
                                consume_cfg.get("ACTION_ID"),
                                f"{intake_source_root}.consume.ACTION_ID",
                            ),
                            (
                                consume_cfg.get("ACTION-ID"),
                                f"{intake_source_root}.consume.ACTION-ID",
                            ),
                            (
                                consume_cfg.get("Action_id"),
                                f"{intake_source_root}.consume.Action_id",
                            ),
                            (
                                consume_cfg.get("Action_ID"),
                                f"{intake_source_root}.consume.Action_ID",
                            ),
                            (
                                consume_cfg.get("Actionid"),
                                f"{intake_source_root}.consume.Actionid",
                            ),
                            (
                                consume_cfg.get("actionId"),
                                f"{intake_source_root}.consume.actionId",
                            ),
                            (
                                consume_cfg.get("actionid"),
                                f"{intake_source_root}.consume.actionid",
                            ),
                            (
                                consume_cfg.get("action_id"),
                                f"{intake_source_root}.consume.action_id",
                            ),
                            (
                                consume_cfg.get("action-id"),
                                f"{intake_source_root}.consume.action-id",
                            ),
                            (
                                consume_cfg.get("action-Id"),
                                f"{intake_source_root}.consume.action-Id",
                            ),
                            (
                                consume_cfg.get("actionID"),
                                f"{intake_source_root}.consume.actionID",
                            ),
                        ]
                    )

                consume_alias_cfg, consume_alias_source_root = (
                    _extract_watch_consume_with_source(intake, intake_source_root)
                )
                intake_candidates.extend(
                    _collect_action_id_like_candidates(
                        consume_alias_cfg,
                        consume_alias_source_root,
                    )
                )

                for candidate, source_path in intake_candidates:
                    value = str(candidate or "").strip().lower()
                    if value:
                        watch_loop_hint = value
                        watch_loop_hint_path = source_path
                        break

        if watch_loop_hint:
            selected_action = watch_loop_hint
            selected_action_source = "watch-loop-hint"
            selected_action_source_path = watch_loop_hint_path
        else:
            selected_action = "reply-latest"
            selected_action_source = "watch-loop-hint"
            selected_action_source_path = "default:reply-latest"

    preview_action: dict[str, Any] = {}
    if selected_action == "reply-latest":
        reply_text = (text or "").strip()
        if not reply_text:
            utils.error_exit(
                "invalid_text",
                "--text is required when --action reply-latest",
            )
        preview_action = client.build_watch_reply_action(
            watch_payload,
            text=reply_text,
            chat_id=chat_id,
            channel_id=channel_id,
        )
    elif selected_action == "read-ack-latest":
        preview_action = client.build_watch_read_ack_action(
            watch_payload,
            chat_id=chat_id,
            channel_id=channel_id,
            message_id=message_id,
        )
    else:
        utils.error_exit(
            "invalid_action",
            "--action must be one of: reply-latest, read-ack-latest",
        )

    status_flow_events: list[dict[str, Any]] = []
    status_target_message_id = str(preview_action.get("targetMessageId") or "").strip()
    status_target_chat = str(preview_action.get("chatId") or "").strip()
    status_target_channel = str(preview_action.get("channelId") or "").strip()

    def _emit_status(stage: str) -> None:
        if not status_flow:
            return
        if not status_target_message_id:
            return
        event = _apply_cliq_status_reaction_best_effort(
            client,
            email=email,
            message_id=status_target_message_id,
            status=stage,
            chat_id=status_target_chat,
            channel_id=status_target_channel,
            clear_known=False,
        )
        event["stage"] = stage
        status_flow_events.append(event)

    if status_flow and status_target_message_id:
        _emit_status("received")
        _emit_status("thinking")
        if selected_action == "reply-latest":
            _emit_status("writing")
        else:
            _emit_status("testing")

    try:
        if selected_action == "reply-latest":
            result = client.execute_watch_reply_action(
                watch_payload,
                text=reply_text,
                chat_id=chat_id,
                channel_id=channel_id,
            )
            if status_flow and status_target_message_id:
                _emit_status("testing")
        else:
            unsupported_entry_before = client._read_operation_unsupported_entry(  # noqa: SLF001
                "message-read-ack"
            )
            read_ack_stderr = io.StringIO()
            try:
                with contextlib.redirect_stderr(read_ack_stderr):
                    result = client.execute_watch_read_ack_action(
                        watch_payload,
                        chat_id=chat_id,
                        channel_id=channel_id,
                        message_id=message_id,
                    )
                if isinstance(result, dict):
                    result.setdefault("fallbackUsed", False)
                    result.setdefault("readAckSupported", True)
            except SystemExit:
                if not _should_use_mark_read_status_fallback(
                    client,
                    unsupported_entry_before=unsupported_entry_before,
                ):
                    stderr_payload = read_ack_stderr.getvalue()
                    if stderr_payload:
                        print(stderr_payload, end="", file=sys.stderr)
                    raise

                fallback_payload = _apply_cliq_status_reaction(
                    client,
                    email=email,
                    message_id=status_target_message_id,
                    status="received",
                    chat_id=status_target_chat,
                    channel_id=status_target_channel,
                    clear_known=False,
                )
                result = {
                    "status": "ok",
                    **preview_action,
                    "applied": False,
                    "reason": "read_ack_not_supported",
                    "result": {},
                    "fallbackUsed": True,
                    "readAckSupported": False,
                    "statusReaction": {
                        "statusKey": fallback_payload["statusKey"],
                        "emoji": fallback_payload["emoji"],
                        "previousStatus": fallback_payload["previousStatus"],
                        "previousEmoji": fallback_payload["previousEmoji"],
                        "removed": fallback_payload["removed"],
                        "removeErrors": fallback_payload["removeErrors"],
                        "result": fallback_payload["result"],
                    },
                }

        if status_flow and status_target_message_id:
            _emit_status("done")
    except BaseException:
        if status_flow and status_target_message_id:
            _emit_status("failed")
        raise

    if isinstance(result, dict):
        result["actionSource"] = selected_action_source
        result["actionSourcePath"] = selected_action_source_path
        result["actionSourceMetadata"] = _build_action_source_metadata(
            selected_action_source,
            selected_action_source_path,
        )
        if status_flow:
            result["statusFlow"] = {
                "enabled": True,
                "targetMessageId": status_target_message_id,
                "events": status_flow_events,
            }

    utils.output(result)


register_cliq_watch_act_commands(
    cliq_app,
    cliq_watch_act_command=cliq_watch_act,
)


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


register_cliq_reply_edit_commands(
    cliq_app,
    cliq_reply_command=cliq_reply,
    cliq_edit_command=cliq_edit,
)


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


def cliq_status_react(
    message_id: str = typer.Argument(..., help="Target message id."),
    status: str = typer.Option(
        ...,
        "--status",
        help=(
            "Status key (received, thinking, writing, testing, blocked, done, failed)."
        ),
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
    clear_known: bool = typer.Option(
        True,
        "--clear-known/--keep-existing",
        help="Clear known status emojis before setting the new one.",
    ),
) -> None:
    """Set one status reaction on a Cliq message."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")
    payload = _apply_cliq_status_reaction(
        client,
        email=email,
        message_id=message_id,
        status=status,
        chat_id=resolved_chat or "",
        channel_id=channel_id or "",
        clear_known=clear_known,
    )

    utils.output_status(
        "Cliq status reaction updated",
        extra={
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "messageId": payload["messageId"],
            "statusKey": payload["statusKey"],
            "emoji": payload["emoji"],
            "previousStatus": payload["previousStatus"],
            "previousEmoji": payload["previousEmoji"],
            "removed": payload["removed"],
            "removeErrors": payload["removeErrors"],
            "result": payload["result"],
        },
    )


def cliq_mark_read(
    message_id: Optional[str] = typer.Argument(
        None,
        help="Target message id. Optional when using --latest.",
    ),
    latest: bool = typer.Option(
        False,
        "--latest",
        help="Mark the latest fetched message in the chat/channel as read.",
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
    """Mark one Cliq message as read/acknowledged."""
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")

    target_message_id = (message_id or "").strip()
    if not target_message_id and not latest:
        utils.error_exit(
            "invalid_message_id",
            "Provide message_id or use --latest to mark the newest message as read.",
        )

    cfg = _cfg()
    email = _require_account(cfg)
    client = _get_cliq_client(cfg, email, network=network)

    resolved_chat = (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")

    resolved_via_latest = False
    if not target_message_id:
        messages_resp = client.list_messages(
            chat_id=resolved_chat,
            channel_id=channel_id,
            limit=1,
        )
        data = messages_resp.get("data", messages_resp)
        messages = data if isinstance(data, list) else []
        if not messages:
            utils.output_status(
                "No messages found to mark as read",
                extra={
                    "chatId": resolved_chat or "",
                    "channelId": channel_id or "",
                    "messageId": "",
                    "result": {"status": "noop"},
                },
            )
            return

        target_message_id = (
            _cliq.ZohoCliqClient._extract_message_id(messages[0])
            if isinstance(messages[0], dict)
            else ""
        )
        if not target_message_id:
            utils.error_exit(
                "invalid_message_id",
                "Unable to infer latest message id from chat payload.",
            )
        resolved_via_latest = True

    unsupported_entry_before = client._read_operation_unsupported_entry(  # noqa: SLF001
        "message-read-ack"
    )
    read_ack_stderr = io.StringIO()

    try:
        with contextlib.redirect_stderr(read_ack_stderr):
            resp = client.read_ack_message(
                target_message_id,
                chat_id=resolved_chat,
                channel_id=channel_id,
            )
        data = resp.get("data", resp)
        utils.output_status(
            "Cliq message marked as read",
            extra={
                "chatId": resolved_chat or "",
                "channelId": channel_id or "",
                "messageId": target_message_id,
                "viaLatest": resolved_via_latest,
                "fallbackUsed": False,
                "readAckSupported": True,
                "result": data,
            },
        )
        return
    except SystemExit:
        if not _should_use_mark_read_status_fallback(
            client,
            unsupported_entry_before=unsupported_entry_before,
        ):
            stderr_payload = read_ack_stderr.getvalue()
            if stderr_payload:
                print(stderr_payload, end="", file=sys.stderr)
            raise

    fallback_payload = _apply_cliq_status_reaction(
        client,
        email=email,
        message_id=target_message_id,
        status="received",
        chat_id=resolved_chat or "",
        channel_id=channel_id or "",
        clear_known=False,
    )
    utils.output_status(
        "Cliq read-ack unsupported, applied reaction fallback",
        extra={
            "chatId": resolved_chat or "",
            "channelId": channel_id or "",
            "messageId": target_message_id,
            "viaLatest": resolved_via_latest,
            "fallbackUsed": True,
            "readAckSupported": False,
            "statusReaction": {
                "statusKey": fallback_payload["statusKey"],
                "emoji": fallback_payload["emoji"],
                "previousStatus": fallback_payload["previousStatus"],
                "previousEmoji": fallback_payload["previousEmoji"],
                "removed": fallback_payload["removed"],
                "removeErrors": fallback_payload["removeErrors"],
                "result": fallback_payload["result"],
            },
        },
    )


register_cliq_delete_react_commands(
    cliq_app,
    cliq_delete_command=cliq_delete,
    cliq_react_command=cliq_react,
    cliq_status_react_command=cliq_status_react,
)

register_cliq_mark_read_commands(
    cliq_app,
    cliq_mark_read_command=cliq_mark_read,
)


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


register_cliq_voice_send_commands(
    cliq_app,
    cliq_voice_send_command=cliq_voice_send,
    cliq_send_command=cliq_send,
)


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


register_cliq_notify_mail_commands(
    cliq_app,
    cliq_notify_mail_command=cliq_notify_mail,
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
    """Show CRM auth readiness and inferred API endpoint."""
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


@crm_app.command("sdk-status")
def crm_sdk_status() -> None:
    """Show official Zoho CRM SDK adapter readiness."""
    utils.output(_crm.crm_sdk_status())


@crm_app.command("modules")
def crm_modules(
    limit: int = typer.Option(50, "--limit", "-n", help="Max modules to return."),
    page: int = typer.Option(1, "--page", help="Result page number."),
) -> None:
    """List CRM modules available to the account."""
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
