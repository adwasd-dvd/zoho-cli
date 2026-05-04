"""Cliq organization-directory command builders."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

import typer

from zoho_cli import utils


@dataclass(frozen=True)
class CliqOrgDirectoryContext:
    """Runtime hooks needed by the Cliq organization-directory command surface."""

    load_config: Callable[[], dict[str, Any]]
    require_account: Callable[[dict[str, Any]], str]
    get_cliq_client: Callable[..., Any]


def build_cliq_users_command(
    context: CliqOrgDirectoryContext,
) -> Callable[..., None]:
    """Build ``zoho cliq users`` with injected runtime state."""

    def cliq_users(
        limit: int = typer.Option(50, "--limit", "-n", help="Max users to return."),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """List Cliq users."""
        cfg = context.load_config()
        email = context.require_account(cfg)
        client = context.get_cliq_client(cfg, email, network=network)

        resp = client.users(limit=limit)
        data = resp.get("data", resp)
        utils.output(data)

    return cliq_users


def build_cliq_teams_command(
    context: CliqOrgDirectoryContext,
) -> Callable[..., None]:
    """Build ``zoho cliq teams`` with injected runtime state."""

    def cliq_teams(
        limit: int = typer.Option(50, "--limit", "-n", help="Max teams to return."),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """List Cliq teams."""
        cfg = context.load_config()
        email = context.require_account(cfg)
        client = context.get_cliq_client(cfg, email, network=network)

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

    return cliq_teams
