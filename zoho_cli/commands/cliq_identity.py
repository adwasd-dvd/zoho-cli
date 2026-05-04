"""Cliq identity command builders."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

import typer

from zoho_cli import utils


@dataclass(frozen=True)
class CliqIdentityContext:
    """Runtime hooks needed by the Cliq identity command surface."""

    load_config: Callable[[], dict[str, Any]]
    require_account: Callable[[dict[str, Any]], str]
    get_cliq_client: Callable[..., Any]


def build_cliq_whoami_command(
    context: CliqIdentityContext,
) -> Callable[..., None]:
    """Build ``zoho cliq whoami`` with injected runtime state."""

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
        cfg = context.load_config()
        email = context.require_account(cfg)
        client = context.get_cliq_client(cfg, email, network=network)

        result = client.whoami(account_email=email, limit=limit)
        utils.output(
            {
                "account": email,
                "baseUrl": client.base_url,
                **result,
            }
        )

    return cliq_whoami


def build_cliq_user_resolve_command(
    context: CliqIdentityContext,
) -> Callable[..., None]:
    """Build ``zoho cliq user-resolve`` with injected runtime state."""

    def cliq_user_resolve(
        query: str = typer.Argument(
            ..., help="User lookup query (email or display name)."
        ),
        by: str = typer.Option("auto", "--by", help="Match mode: auto|email|name."),
        limit: int = typer.Option(500, "--limit", "-n", help="Max users to scan."),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """Resolve user ids by email or display name."""
        cfg = context.load_config()
        email = context.require_account(cfg)
        client = context.get_cliq_client(cfg, email, network=network)

        result = client.resolve_users(query, by=by, limit=limit)
        utils.output(result)

    return cliq_user_resolve
