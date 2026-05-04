"""Cliq message retrieval and context command builders."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

import typer

from zoho_cli import utils


@dataclass(frozen=True)
class CliqMessageRetrievalContext:
    """Runtime hooks needed by the Cliq message retrieval command surface."""

    load_config: Callable[[], dict[str, Any]]
    require_account: Callable[[dict[str, Any]], str]
    get_cliq_client: Callable[..., Any]
    infer_message_types: Callable[[dict[str, Any]], list[str]]
    extract_message_id: Callable[[dict[str, Any]], str]
    build_watch_context_seed: Callable[..., dict[str, Any]]
    typed_messages: Callable[[list[dict[str, Any]]], list[dict[str, Any]]]


def _client(context: CliqMessageRetrievalContext, network: str | None) -> Any:
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


def build_cliq_search_command(
    context: CliqMessageRetrievalContext,
) -> Callable[..., None]:
    """Build ``zoho cliq search`` with injected runtime state."""

    def cliq_search(
        query: str = typer.Argument(..., help="Search query text."),
        channel_id: Optional[str] = typer.Option(
            None, "--channel-id", help="Source channel id (resolved to chat_id)."
        ),
        chat_id: Optional[str] = typer.Option(
            None, "--chat-id", help="Source chat id."
        ),
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
        _require_destination(chat_id, channel_id)

        client = _client(context, network)
        resolved_chat = _resolved_chat(client, chat_id, channel_id)
        data = _data(
            client.search_messages(
                query,
                chat_id=resolved_chat,
                channel_id=channel_id,
                limit=limit,
                from_time=from_time,
                to_time=to_time,
            )
        )
        messages = _dict_rows(data, ("messages", "results", "items", "data"))
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

    return cliq_search


def build_cliq_messages_command(
    context: CliqMessageRetrievalContext,
) -> Callable[..., None]:
    """Build ``zoho cliq messages`` with injected runtime state."""

    def cliq_messages(
        channel_id: Optional[str] = typer.Option(
            None, "--channel-id", help="Source channel id (resolved to chat_id)."
        ),
        chat_id: Optional[str] = typer.Option(
            None, "--chat-id", help="Source chat id."
        ),
        limit: int = typer.Option(50, "--limit", "-n", help="Max messages to return."),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """List messages for a channel/chat."""
        _require_destination(chat_id, channel_id)

        client = _client(context, network)
        resolved_chat = _resolved_chat(client, chat_id, channel_id)
        messages = _data(
            client.list_messages(
                chat_id=resolved_chat, channel_id=channel_id, limit=limit
            )
        )
        if not isinstance(messages, list):
            messages = []

        utils.output(
            {
                "chatId": resolved_chat or "",
                "channelId": channel_id or "",
                "count": len(messages),
                "messages": messages,
                "typedMessages": context.typed_messages(messages),
            }
        )

    return cliq_messages


def build_cliq_message_command(
    context: CliqMessageRetrievalContext,
) -> Callable[..., None]:
    """Build ``zoho cliq message`` with injected runtime state."""

    def cliq_message(
        message_id: str = typer.Argument(..., help="Cliq message id."),
        channel_id: Optional[str] = typer.Option(
            None, "--channel-id", help="Source channel id (resolved to chat_id)."
        ),
        chat_id: Optional[str] = typer.Option(
            None, "--chat-id", help="Source chat id."
        ),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """Get one message by id from a channel/chat."""
        _require_destination(chat_id, channel_id)

        client = _client(context, network)
        resolved_chat = _resolved_chat(client, chat_id, channel_id)
        message = _data(
            client.get_message(message_id, chat_id=resolved_chat, channel_id=channel_id)
        )
        if isinstance(message, list):
            message = message[0] if message else {}
        utils.output(
            {
                "chatId": resolved_chat or "",
                "channelId": channel_id or "",
                "message": message,
                "messageTypes": context.infer_message_types(
                    message if isinstance(message, dict) else {}
                ),
            }
        )

    return cliq_message


def build_cliq_context_command(
    context: CliqMessageRetrievalContext,
) -> Callable[..., None]:
    """Build ``zoho cliq context`` with injected runtime state."""

    def cliq_context(
        channel_id: Optional[str] = typer.Option(
            None, "--channel-id", help="Source channel id (resolved to chat_id)."
        ),
        chat_id: Optional[str] = typer.Option(
            None, "--chat-id", help="Source chat id."
        ),
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
        _require_destination(chat_id, channel_id)
        if before < 0 or after < 0:
            utils.error_exit("invalid_window", "--before/--after must be >= 0")

        client = _client(context, network)
        resolved_chat = _resolved_chat(client, chat_id, channel_id)
        messages = _data(
            client.list_messages(
                chat_id=resolved_chat, channel_id=channel_id, limit=limit
            )
        )
        if not isinstance(messages, list):
            messages = []

        anchor: dict[str, Any] | None = None
        anchor_idx: int | None = None
        if message_id:
            anchor_data = _data(
                client.get_message(
                    message_id, chat_id=resolved_chat, channel_id=channel_id
                )
            )
            if isinstance(anchor_data, list):
                anchor = anchor_data[0] if anchor_data else None
            elif isinstance(anchor_data, dict):
                anchor = anchor_data

            for idx, item in enumerate(messages):
                if not isinstance(item, dict):
                    continue
                if context.extract_message_id(item) == message_id:
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
                "anchorTypes": context.infer_message_types(
                    anchor if isinstance(anchor, dict) else {}
                ),
                "messages": context_messages,
                "typedMessages": context.typed_messages(
                    [item for item in context_messages if isinstance(item, dict)]
                ),
            }
        )

    return cliq_context


def build_cliq_watch_context_command(
    context: CliqMessageRetrievalContext,
) -> Callable[..., None]:
    """Build ``zoho cliq watch-context`` with injected runtime state."""

    def cliq_watch_context(
        channel_id: Optional[str] = typer.Option(
            None, "--channel-id", help="Source channel id (resolved to chat_id)."
        ),
        chat_id: Optional[str] = typer.Option(
            None, "--chat-id", help="Source chat id."
        ),
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
        """Emit a stable incremental context payload for watch loops."""
        _require_destination(chat_id, channel_id)
        if limit < 1 or max_messages < 1:
            utils.error_exit("invalid_limit", "--limit/--max-messages must be >= 1")

        client = _client(context, network)
        fetch_limit = max(limit, max_messages)
        resolved_chat = _resolved_chat(client, chat_id, channel_id)
        data = _data(
            client.list_messages(
                chat_id=resolved_chat,
                channel_id=channel_id,
                limit=fetch_limit,
            )
        )
        messages = (
            [item for item in data if isinstance(item, dict)]
            if isinstance(data, list)
            else []
        )

        watch = context.build_watch_context_seed(
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
                "escalationEnvelope": watch["escalationEnvelope"],
                "escalationEnvelopeMetadata": watch["escalationEnvelopeMetadata"],
                "watchIntake": watch["watchIntake"],
                "operatorWorkflow": watch["operatorWorkflow"],
                "messages": watch["messages"],
            }
        )

    return cliq_watch_context
