"""Cliq platform-extension command builders."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

import typer

from zoho_cli import utils


@dataclass(frozen=True)
class CliqPlatformExtensionsContext:
    """Runtime hooks needed by the Cliq platform-extension command surface."""

    load_config: Callable[[], dict[str, Any]]
    require_account: Callable[[dict[str, Any]], str]
    get_cliq_client: Callable[..., Any]


def _data_rows(resp: Any) -> list[Any]:
    if isinstance(resp, dict):
        data = resp.get("data", resp)
    else:
        data = resp
    return data if isinstance(data, list) else []


def build_cliq_widgets_command(
    context: CliqPlatformExtensionsContext,
) -> Callable[..., None]:
    """Build ``zoho cliq widgets`` with injected runtime state."""

    def cliq_widgets(
        limit: int = typer.Option(50, "--limit", "-n", help="Max widgets to return."),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """List Cliq widgets."""
        cfg = context.load_config()
        email = context.require_account(cfg)
        client = context.get_cliq_client(cfg, email, network=network)

        views: list[dict[str, Any]] = []
        for row in _data_rows(client.list_widgets(limit=limit)):
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

        utils.output({"count": len(views), "widgets": views})

    return cliq_widgets


def build_cliq_map_tickers_command(
    context: CliqPlatformExtensionsContext,
) -> Callable[..., None]:
    """Build ``zoho cliq map-tickers`` with injected runtime state."""

    def cliq_map_tickers(
        limit: int = typer.Option(
            50, "--limit", "-n", help="Max map tickers to return."
        ),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """List Cliq map tickers."""
        cfg = context.load_config()
        email = context.require_account(cfg)
        client = context.get_cliq_client(cfg, email, network=network)

        views: list[dict[str, Any]] = []
        for row in _data_rows(client.list_map_tickers(limit=limit)):
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

        utils.output({"count": len(views), "mapTickers": views})

    return cliq_map_tickers


def build_cliq_custom_domains_command(
    context: CliqPlatformExtensionsContext,
) -> Callable[..., None]:
    """Build ``zoho cliq custom-domains`` with injected runtime state."""

    def cliq_custom_domains(
        limit: int = typer.Option(
            50, "--limit", "-n", help="Max custom domains to return."
        ),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """List Cliq custom domains."""
        cfg = context.load_config()
        email = context.require_account(cfg)
        client = context.get_cliq_client(cfg, email, network=network)

        views: list[dict[str, Any]] = []
        for row in _data_rows(client.list_custom_domains(limit=limit)):
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

        utils.output({"count": len(views), "customDomains": views})

    return cliq_custom_domains


def build_cliq_custom_emails_command(
    context: CliqPlatformExtensionsContext,
) -> Callable[..., None]:
    """Build ``zoho cliq custom-emails`` with injected runtime state."""

    def cliq_custom_emails(
        limit: int = typer.Option(
            50, "--limit", "-n", help="Max custom emails to return."
        ),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """List Cliq custom emails."""
        cfg = context.load_config()
        email = context.require_account(cfg)
        client = context.get_cliq_client(cfg, email, network=network)

        views: list[dict[str, Any]] = []
        for row in _data_rows(client.list_custom_emails(limit=limit)):
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

        utils.output({"count": len(views), "customEmails": views})

    return cliq_custom_emails
