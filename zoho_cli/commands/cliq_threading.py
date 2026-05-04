"""Cliq thread command builders."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

import typer

from zoho_cli import utils


@dataclass(frozen=True)
class CliqThreadingContext:
    """Runtime hooks needed by the Cliq thread command surface."""

    load_config: Callable[[], dict[str, Any]]
    require_account: Callable[[dict[str, Any]], str]
    get_cliq_client: Callable[..., Any]


def _client(context: CliqThreadingContext, network: str | None) -> Any:
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


def build_cliq_thread_create_command(
    context: CliqThreadingContext,
) -> Callable[..., None]:
    """Build ``zoho cliq thread-create`` with injected runtime state."""

    def cliq_thread_create(
        message_id: str = typer.Argument(
            ..., help="Parent message id to anchor thread."
        ),
        text: str = typer.Option(..., "--text", "-t", help="Thread message text."),
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
        """Create/send a thread message anchored to one parent message."""
        _require_destination(chat_id, channel_id)

        client = _client(context, network)
        resolved_chat = _resolved_chat(client, chat_id, channel_id)
        data = _data(
            client.create_thread(
                message_id,
                text,
                chat_id=resolved_chat,
                channel_id=channel_id,
            )
        )
        utils.output_status(
            "Cliq thread message sent",
            extra={
                "chatId": resolved_chat or "",
                "channelId": channel_id or "",
                "parentMessageId": message_id,
                "result": data,
            },
        )

    return cliq_thread_create


def build_cliq_thread_reply_command(
    context: CliqThreadingContext,
) -> Callable[..., None]:
    """Build ``zoho cliq thread-reply`` with injected runtime state."""

    def cliq_thread_reply(
        thread_id: str = typer.Argument(..., help="Thread id."),
        text: str = typer.Option(..., "--text", "-t", help="Reply text."),
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
        """Reply to a Cliq thread."""
        _require_destination(chat_id, channel_id)

        client = _client(context, network)
        resolved_chat = _resolved_chat(client, chat_id, channel_id)
        data = _data(
            client.reply_thread(
                thread_id,
                text,
                chat_id=resolved_chat,
                channel_id=channel_id,
            )
        )
        utils.output_status(
            "Cliq thread reply sent",
            extra={
                "chatId": resolved_chat or "",
                "channelId": channel_id or "",
                "threadId": thread_id,
                "result": data,
            },
        )

    return cliq_thread_reply


def build_cliq_threads_command(context: CliqThreadingContext) -> Callable[..., None]:
    """Build ``zoho cliq threads`` with injected runtime state."""

    def cliq_threads(
        channel_id: Optional[str] = typer.Option(
            None, "--channel-id", help="Destination channel id (resolved to chat_id)."
        ),
        chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Chat id."),
        message_id: Optional[str] = typer.Option(
            None,
            "--message-id",
            help="Optional parent message id for one-thread family listing.",
        ),
        limit: int = typer.Option(50, "--limit", "-n", help="Max rows to return."),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """List threads for one chat/channel, optionally scoped to one parent message."""
        _require_destination(chat_id, channel_id)

        client = _client(context, network)
        resolved_chat = _resolved_chat(client, chat_id, channel_id)
        data = _data(
            client.list_threads(
                chat_id=resolved_chat,
                channel_id=channel_id,
                message_id=message_id,
                limit=limit,
            )
        )
        threads = _dict_rows(data, ("threads", "data", "list", "items", "messages"))
        utils.output(
            {
                "chatId": resolved_chat or "",
                "channelId": channel_id or "",
                "messageId": (message_id or "").strip(),
                "count": len(threads),
                "threads": threads,
            }
        )

    return cliq_threads


def build_cliq_thread_followers_command(
    context: CliqThreadingContext,
) -> Callable[..., None]:
    """Build ``zoho cliq thread-followers`` with injected runtime state."""

    def cliq_thread_followers(
        thread_id: str = typer.Argument(..., help="Thread id."),
        channel_id: Optional[str] = typer.Option(
            None, "--channel-id", help="Destination channel id (resolved to chat_id)."
        ),
        chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Chat id."),
        limit: int = typer.Option(50, "--limit", "-n", help="Max rows to return."),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """List followers/subscribers for one thread."""
        _require_destination(chat_id, channel_id)

        client = _client(context, network)
        resolved_chat = _resolved_chat(client, chat_id, channel_id)
        data = _data(
            client.list_thread_followers(
                thread_id,
                chat_id=resolved_chat,
                channel_id=channel_id,
                limit=limit,
            )
        )
        followers = _dict_rows(
            data, ("followers", "members", "subscribers", "data", "list", "items")
        )
        utils.output(
            {
                "chatId": resolved_chat or "",
                "channelId": channel_id or "",
                "threadId": thread_id,
                "count": len(followers),
                "followers": followers,
            }
        )

    return cliq_thread_followers


def build_cliq_thread_state_command(
    context: CliqThreadingContext,
) -> Callable[..., None]:
    """Build ``zoho cliq thread-state`` with injected runtime state."""

    def cliq_thread_state(
        thread_id: str = typer.Argument(..., help="Thread id."),
        state: Optional[str] = typer.Option(
            None,
            "--state",
            help="Target state to set (omit to read current state payload).",
        ),
        channel_id: Optional[str] = typer.Option(
            None, "--channel-id", help="Destination channel id (resolved to chat_id)."
        ),
        chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Chat id."),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """Get or set thread state."""
        _require_destination(chat_id, channel_id)

        client = _client(context, network)
        resolved_chat = _resolved_chat(client, chat_id, channel_id)
        state_text = (state or "").strip()
        if state_text:
            data = _data(
                client.update_thread_state(
                    thread_id,
                    state_text,
                    chat_id=resolved_chat,
                    channel_id=channel_id,
                )
            )
            utils.output_status(
                "Cliq thread state updated",
                extra={
                    "chatId": resolved_chat or "",
                    "channelId": channel_id or "",
                    "threadId": thread_id,
                    "state": state_text,
                    "result": data,
                },
            )
            return

        data = _data(
            client.get_thread_state(
                thread_id,
                chat_id=resolved_chat,
                channel_id=channel_id,
            )
        )
        state_view = ""
        if isinstance(data, dict):
            state_view = str(
                data.get("state")
                or data.get("thread_state")
                or data.get("threadState")
                or data.get("status")
                or ""
            )

        utils.output(
            {
                "chatId": resolved_chat or "",
                "channelId": channel_id or "",
                "threadId": thread_id,
                "state": state_view,
                "thread": data,
            }
        )

    return cliq_thread_state
