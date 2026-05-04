"""Cliq scheduled-message command builders."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

import typer

from zoho_cli import utils


@dataclass(frozen=True)
class CliqSchedulingContext:
    """Runtime hooks needed by the Cliq scheduled-message command surface."""

    load_config: Callable[[], dict[str, Any]]
    require_account: Callable[[dict[str, Any]], str]
    get_cliq_client: Callable[..., Any]


def _client(context: CliqSchedulingContext, network: str | None) -> Any:
    cfg = context.load_config()
    email = context.require_account(cfg)
    return context.get_cliq_client(cfg, email, network=network)


def _require_destination(chat_id: str | None, channel_id: str | None) -> None:
    if not chat_id and not channel_id:
        utils.error_exit("invalid_destination", "Provide --chat-id or --channel-id")


def _resolved_chat(client: Any, chat_id: str | None, channel_id: str | None) -> str:
    return (chat_id or "").strip() or client.resolve_chat_id(channel_id or "")


def _data(resp: Any) -> Any:
    return resp.get("data", resp) if isinstance(resp, dict) else resp


def _dict_rows(data: Any, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in keys:
            candidate = data.get(key)
            if isinstance(candidate, list):
                return [item for item in candidate if isinstance(item, dict)]
    return []


def build_cliq_schedule_command(
    context: CliqSchedulingContext,
) -> Callable[..., None]:
    """Build ``zoho cliq schedule`` with injected runtime state."""

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
        _require_destination(chat_id, channel_id)

        client = _client(context, network)
        resolved_chat = _resolved_chat(client, chat_id, channel_id)
        data = _data(
            client.schedule_message(
                text,
                when,
                chat_id=resolved_chat,
                channel_id=channel_id,
            )
        )

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

    return cliq_schedule


def build_cliq_scheduled_command(
    context: CliqSchedulingContext,
) -> Callable[..., None]:
    """Build ``zoho cliq scheduled`` with injected runtime state."""

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
        _require_destination(chat_id, channel_id)

        client = _client(context, network)
        resolved_chat = _resolved_chat(client, chat_id, channel_id)
        data = _data(
            client.list_scheduled_messages(
                chat_id=resolved_chat,
                channel_id=channel_id,
                limit=limit,
            )
        )
        scheduled = _dict_rows(data, ("scheduled", "messages", "data", "list", "items"))
        utils.output(
            {
                "chatId": resolved_chat or "",
                "channelId": channel_id or "",
                "count": len(scheduled),
                "scheduled": scheduled,
            }
        )

    return cliq_scheduled


def build_cliq_scheduled_get_command(
    context: CliqSchedulingContext,
) -> Callable[..., None]:
    """Build ``zoho cliq scheduled-get`` with injected runtime state."""

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
        _require_destination(chat_id, channel_id)

        client = _client(context, network)
        resolved_chat = _resolved_chat(client, chat_id, channel_id)
        data = _data(
            client.get_scheduled_message(
                scheduled_id,
                chat_id=resolved_chat,
                channel_id=channel_id,
            )
        )

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

    return cliq_scheduled_get


def build_cliq_scheduled_cancel_command(
    context: CliqSchedulingContext,
) -> Callable[..., None]:
    """Build ``zoho cliq scheduled-cancel`` with injected runtime state."""

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
        _require_destination(chat_id, channel_id)

        client = _client(context, network)
        resolved_chat = _resolved_chat(client, chat_id, channel_id)
        data = _data(
            client.cancel_scheduled_message(
                scheduled_id,
                chat_id=resolved_chat,
                channel_id=channel_id,
            )
        )
        utils.output_status(
            "Cliq scheduled message cancelled",
            extra={
                "chatId": resolved_chat or "",
                "channelId": channel_id or "",
                "scheduledId": scheduled_id,
                "result": data,
            },
        )

    return cliq_scheduled_cancel
