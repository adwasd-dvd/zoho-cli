"""Cliq readiness and capability command builders."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import shlex
from typing import Any, Optional

import typer

from zoho_cli import cliq as _cliq
from zoho_cli import utils

ConfiguredCliqTargets = tuple[list[dict[str, Any]], list[str]]


@dataclass(frozen=True)
class CliqReadinessContext:
    """Runtime hooks needed by the Cliq readiness command surface."""

    load_config: Callable[[], dict[str, Any]]
    selected_account: Callable[[], str | None]
    selected_config_path: Callable[[], str | None]
    selected_network: Callable[[], str | None]
    default_account: Callable[[dict[str, Any]], str | None]
    collect_configured_targets: Callable[[dict[str, Any]], ConfiguredCliqTargets]
    require_credentials: Callable[[dict[str, Any]], tuple[str, str]]
    refresh_access_token_info: Callable[..., dict[str, Any]]
    require_account: Callable[[dict[str, Any]], str]
    get_cliq_client: Callable[..., Any]


def build_cliq_status_command(
    context: CliqReadinessContext,
) -> Callable[..., None]:
    """Build ``zoho cliq status`` with injected runtime state."""

    def cliq_status(
        check_auth: bool = typer.Option(
            False,
            "--check-auth",
            help="Verify OAuth refresh for the selected account.",
        ),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
        list_networks: bool = typer.Option(
            False,
            "--list-networks",
            help="List known Cliq network slugs from configured account defaults.",
        ),
        list_accounts: bool = typer.Option(
            False,
            "--list-accounts",
            help="List configured account options and their default Cliq network.",
        ),
    ) -> None:
        """Show Cliq auth readiness and inferred API endpoint."""
        cfg = context.load_config()
        email = context.selected_account() or context.default_account(cfg)
        account_cfg = cfg.get("accounts", {}).get(email, {}) if email else {}
        resolved_network = (
            network or context.selected_network() or account_cfg.get("cliq_network")
        )
        config_path = context.selected_config_path()

        def _cmd(*args: str, include_network: bool = False) -> str:
            parts: list[str] = ["zoho"]
            if config_path:
                parts.extend(["--config", config_path])
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

        payload: dict[str, Any] = {
            "module": "cliq",
            "scaffold": "ready",
            "account": email or "",
            "network": resolved_network or "",
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

        if list_networks or list_accounts:
            configured_accounts, configured_networks = (
                context.collect_configured_targets(cfg)
            )
            if list_accounts:
                payload["availableAccounts"] = configured_accounts
            if list_networks:
                payload["availableNetworks"] = configured_networks
            payload["targetUsage"] = {
                "network": "zoho cliq --network <network> channels",
                "account": "zoho --account <email> cliq status --check-auth",
                "combined": "zoho --account <email> cliq --network <network> channels",
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
            cid, csec = context.require_credentials(cfg)
            token_info = context.refresh_access_token_info(
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

    return cliq_status


def build_cliq_capabilities_command(
    context: CliqReadinessContext,
) -> Callable[..., None]:
    """Build ``zoho cliq capabilities`` with injected runtime state."""

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
        """Probe currently-available Cliq read capabilities for this account and network."""
        if (message_id or "").strip() and not (channel_id or "").strip():
            utils.error_exit(
                "invalid_destination",
                "Provide --channel-id when using --message-id for message/file capability probes",
            )

        cfg = context.load_config()
        email = context.require_account(cfg)
        client = context.get_cliq_client(cfg, email, network=network)

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

    return cliq_capabilities
