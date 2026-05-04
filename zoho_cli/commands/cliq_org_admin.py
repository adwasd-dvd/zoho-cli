"""Cliq organization-admin command builders."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

import typer

from zoho_cli import utils


@dataclass(frozen=True)
class CliqOrgAdminContext:
    """Runtime hooks needed by the Cliq organization-admin command surface."""

    load_config: Callable[[], dict[str, Any]]
    require_account: Callable[[dict[str, Any]], str]
    get_cliq_client: Callable[..., Any]


def build_cliq_departments_command(
    context: CliqOrgAdminContext,
) -> Callable[..., None]:
    """Build ``zoho cliq departments`` with injected runtime state."""

    def cliq_departments(
        limit: int = typer.Option(50, "--limit", "-n", help="Max departments to return."),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """List Cliq departments."""
        cfg = context.load_config()
        email = context.require_account(cfg)
        client = context.get_cliq_client(cfg, email, network=network)

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

    return cliq_departments


def build_cliq_roles_command(context: CliqOrgAdminContext) -> Callable[..., None]:
    """Build ``zoho cliq roles`` with injected runtime state."""

    def cliq_roles(
        limit: int = typer.Option(50, "--limit", "-n", help="Max roles to return."),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """List Cliq roles."""
        cfg = context.load_config()
        email = context.require_account(cfg)
        client = context.get_cliq_client(cfg, email, network=network)

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

    return cliq_roles
