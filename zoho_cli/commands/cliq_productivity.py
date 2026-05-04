"""Cliq productivity command builders."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

import typer

from zoho_cli import utils


@dataclass(frozen=True)
class CliqProductivityContext:
    """Runtime hooks needed by the Cliq productivity command surface."""

    load_config: Callable[[], dict[str, Any]]
    require_account: Callable[[dict[str, Any]], str]
    get_cliq_client: Callable[..., Any]


def _data_rows(resp: Any) -> list[Any]:
    if isinstance(resp, dict):
        data = resp.get("data", resp)
    else:
        data = resp
    return data if isinstance(data, list) else []


def build_cliq_events_command(
    context: CliqProductivityContext,
) -> Callable[..., None]:
    """Build ``zoho cliq events`` with injected runtime state."""

    def cliq_events(
        limit: int = typer.Option(50, "--limit", "-n", help="Max events to return."),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """List Cliq collaboration events."""
        cfg = context.load_config()
        email = context.require_account(cfg)
        client = context.get_cliq_client(cfg, email, network=network)

        views: list[dict[str, Any]] = []
        for row in _data_rows(client.list_events(limit=limit)):
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

        utils.output({"count": len(views), "events": views})

    return cliq_events


def build_cliq_reminders_command(
    context: CliqProductivityContext,
) -> Callable[..., None]:
    """Build ``zoho cliq reminders`` with injected runtime state."""

    def cliq_reminders(
        limit: int = typer.Option(50, "--limit", "-n", help="Max reminders to return."),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """List Cliq collaboration reminders."""
        cfg = context.load_config()
        email = context.require_account(cfg)
        client = context.get_cliq_client(cfg, email, network=network)

        views: list[dict[str, Any]] = []
        for row in _data_rows(client.list_reminders(limit=limit)):
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
                    "status": str(
                        row.get("status") or row.get("reminder_status") or ""
                    ),
                    "raw": row,
                }
            )

        utils.output({"count": len(views), "reminders": views})

    return cliq_reminders


def build_cliq_meetings_command(
    context: CliqProductivityContext,
) -> Callable[..., None]:
    """Build ``zoho cliq meetings`` with injected runtime state."""

    def cliq_meetings(
        limit: int = typer.Option(50, "--limit", "-n", help="Max meetings to return."),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """List Cliq collaboration calls and meetings."""
        cfg = context.load_config()
        email = context.require_account(cfg)
        client = context.get_cliq_client(cfg, email, network=network)

        views: list[dict[str, Any]] = []
        for row in _data_rows(client.list_meetings(limit=limit)):
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

        utils.output({"count": len(views), "meetings": views})

    return cliq_meetings


def build_cliq_databases_command(
    context: CliqProductivityContext,
) -> Callable[..., None]:
    """Build ``zoho cliq databases`` with injected runtime state."""

    def cliq_databases(
        limit: int = typer.Option(50, "--limit", "-n", help="Max databases to return."),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """List Cliq databases."""
        cfg = context.load_config()
        email = context.require_account(cfg)
        client = context.get_cliq_client(cfg, email, network=network)

        views: list[dict[str, Any]] = []
        for row in _data_rows(client.list_databases(limit=limit)):
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

        utils.output({"count": len(views), "databases": views})

    return cliq_databases
