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
        limit: int = typer.Option(
            50, "--limit", "-n", help="Max departments to return."
        ),
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


def build_cliq_designations_command(
    context: CliqOrgAdminContext,
) -> Callable[..., None]:
    """Build ``zoho cliq designations`` with injected runtime state."""

    def cliq_designations(
        limit: int = typer.Option(
            50, "--limit", "-n", help="Max designations to return."
        ),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """List Cliq designations."""
        cfg = context.load_config()
        email = context.require_account(cfg)
        client = context.get_cliq_client(cfg, email, network=network)

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

    return cliq_designations


def build_cliq_user_status_command(
    context: CliqOrgAdminContext,
) -> Callable[..., None]:
    """Build ``zoho cliq user-status`` with injected runtime state."""

    def cliq_user_status(
        limit: int = typer.Option(
            50, "--limit", "-n", help="Max user-status rows to return."
        ),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """List Cliq user-status values."""
        cfg = context.load_config()
        email = context.require_account(cfg)
        client = context.get_cliq_client(cfg, email, network=network)

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

    return cliq_user_status


def build_cliq_userfields_command(
    context: CliqOrgAdminContext,
) -> Callable[..., None]:
    """Build ``zoho cliq userfields`` with injected runtime state."""

    def cliq_userfields(
        limit: int = typer.Option(
            50, "--limit", "-n", help="Max user-field rows to return."
        ),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """List Cliq user fields."""
        cfg = context.load_config()
        email = context.require_account(cfg)
        client = context.get_cliq_client(cfg, email, network=network)

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

    return cliq_userfields
