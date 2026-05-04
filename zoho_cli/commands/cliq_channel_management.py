"""Cliq channel-management command builders."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

import typer

from zoho_cli import utils


@dataclass(frozen=True)
class CliqChannelManagementContext:
    """Runtime hooks needed by the Cliq channel-management command surface."""

    load_config: Callable[[], dict[str, Any]]
    require_account: Callable[[dict[str, Any]], str]
    get_cliq_client: Callable[..., Any]


def _client(context: CliqChannelManagementContext, network: str | None) -> Any:
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


def _archive_channel(
    context: CliqChannelManagementContext,
    channel_id: str,
    *,
    unarchive: bool,
    network: str | None,
) -> None:
    client = _client(context, network)
    data = _data(client.archive_channel(channel_id, unarchive=unarchive))
    utils.output_status(
        "Cliq channel unarchived" if unarchive else "Cliq channel archived",
        extra={"channelId": channel_id, "unarchive": unarchive, "result": data},
    )


def build_cliq_members_command(
    context: CliqChannelManagementContext,
) -> Callable[..., None]:
    """Build ``zoho cliq members`` with injected runtime state."""

    def cliq_members(
        channel_id: Optional[str] = typer.Option(
            None, "--channel-id", help="Channel id (preferred for member listing)."
        ),
        chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Chat id."),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """List members for a channel/chat."""
        _require_destination(chat_id, channel_id)

        client = _client(context, network)
        resolved_chat = (chat_id or "").strip()
        resp = client.list_members(chat_id=resolved_chat, channel_id=channel_id)
        members = resp.get("members", resp.get("data", resp))
        if not isinstance(members, list):
            members = []

        utils.output(
            {
                "chatId": resolved_chat or "",
                "channelId": channel_id or "",
                "count": len(members),
                "members": members,
            }
        )

    return cliq_members


def build_cliq_channel_create_command(
    context: CliqChannelManagementContext,
) -> Callable[..., None]:
    """Build ``zoho cliq channel-create`` with injected runtime state."""

    def cliq_channel_create(
        name: str = typer.Option(..., "--name", help="Channel display name."),
        level: str = typer.Option(
            "organization",
            "--level",
            help="Channel level (for example: organization/team).",
        ),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """Create a Cliq channel."""
        client = _client(context, network)
        data = _data(client.create_channel(name, level=level))
        utils.output_status(
            "Cliq channel created",
            extra={
                "name": name,
                "level": level,
                "result": data,
            },
        )

    return cliq_channel_create


def build_cliq_channel_rename_command(
    context: CliqChannelManagementContext,
) -> Callable[..., None]:
    """Build ``zoho cliq channel-rename`` with injected runtime state."""

    def cliq_channel_rename(
        channel_id: str = typer.Argument(..., help="Target channel id."),
        name: str = typer.Option(..., "--name", help="New channel display name."),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """Rename a Cliq channel."""
        client = _client(context, network)
        data = _data(client.rename_channel(channel_id, name))
        utils.output_status(
            "Cliq channel renamed",
            extra={
                "channelId": channel_id,
                "name": name,
                "result": data,
            },
        )

    return cliq_channel_rename


def build_cliq_channel_topic_command(
    context: CliqChannelManagementContext,
) -> Callable[..., None]:
    """Build ``zoho cliq channel-topic`` with injected runtime state."""

    def cliq_channel_topic(
        channel_id: str = typer.Argument(..., help="Target channel id."),
        topic: str = typer.Option(..., "--topic", help="Channel topic/description."),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """Update a Cliq channel topic."""
        client = _client(context, network)
        data = _data(client.update_channel_topic(channel_id, topic))
        utils.output_status(
            "Cliq channel topic updated",
            extra={
                "channelId": channel_id,
                "topic": topic,
                "result": data,
            },
        )

    return cliq_channel_topic


def build_cliq_member_add_command(
    context: CliqChannelManagementContext,
) -> Callable[..., None]:
    """Build ``zoho cliq member-add`` with injected runtime state."""

    def cliq_member_add(
        member_id: str = typer.Argument(..., help="Member/user id to add."),
        channel_id: Optional[str] = typer.Option(
            None, "--channel-id", help="Target channel id."
        ),
        chat_id: Optional[str] = typer.Option(
            None, "--chat-id", help="Target chat id."
        ),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """Add a member to a channel/chat."""
        _require_destination(chat_id, channel_id)

        client = _client(context, network)
        resolved_chat = _resolved_chat(client, chat_id, channel_id)
        data = _data(
            client.add_member(
                member_id,
                chat_id=resolved_chat,
                channel_id=channel_id,
            )
        )
        utils.output_status(
            "Cliq member added",
            extra={
                "memberId": member_id,
                "chatId": resolved_chat,
                "channelId": channel_id or "",
                "result": data,
            },
        )

    return cliq_member_add


def build_cliq_member_remove_command(
    context: CliqChannelManagementContext,
) -> Callable[..., None]:
    """Build ``zoho cliq member-remove`` with injected runtime state."""

    def cliq_member_remove(
        member_id: str = typer.Argument(..., help="Member/user id to remove."),
        channel_id: Optional[str] = typer.Option(
            None, "--channel-id", help="Target channel id."
        ),
        chat_id: Optional[str] = typer.Option(
            None, "--chat-id", help="Target chat id."
        ),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """Remove a member from a channel/chat."""
        _require_destination(chat_id, channel_id)

        client = _client(context, network)
        resolved_chat = _resolved_chat(client, chat_id, channel_id)
        data = _data(
            client.remove_member(
                member_id,
                chat_id=resolved_chat,
                channel_id=channel_id,
            )
        )
        utils.output_status(
            "Cliq member removed",
            extra={
                "memberId": member_id,
                "chatId": resolved_chat,
                "channelId": channel_id or "",
                "result": data,
            },
        )

    return cliq_member_remove


def build_cliq_channel_archive_command(
    context: CliqChannelManagementContext,
) -> Callable[..., None]:
    """Build ``zoho cliq channel-archive`` with injected runtime state."""

    def cliq_channel_archive(
        channel_id: str = typer.Argument(..., help="Target channel id."),
        unarchive: bool = typer.Option(
            False, "--unarchive", help="Unarchive instead of archiving."
        ),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """Archive or unarchive a Cliq channel."""
        _archive_channel(context, channel_id, unarchive=unarchive, network=network)

    return cliq_channel_archive


def build_cliq_channel_delete_command(
    context: CliqChannelManagementContext,
) -> Callable[..., None]:
    """Build ``zoho cliq channel-delete`` with injected runtime state."""

    def cliq_channel_delete(
        channel_id: str = typer.Argument(..., help="Target channel id."),
        force: bool = typer.Option(False, "--force", help="Confirm channel deletion."),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """Delete a Cliq channel."""
        if not force:
            utils.error_exit("confirm_required", "Add --force to delete a channel")

        client = _client(context, network)
        data = _data(client.delete_channel(channel_id))
        utils.output_status(
            "Cliq channel deleted",
            extra={"channelId": channel_id, "result": data},
        )

    return cliq_channel_delete


def build_cliq_channel_unarchive_command(
    context: CliqChannelManagementContext,
) -> Callable[..., None]:
    """Build ``zoho cliq channel-unarchive`` with injected runtime state."""

    def cliq_channel_unarchive(
        channel_id: str = typer.Argument(..., help="Target channel id."),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """Unarchive a Cliq channel."""
        _archive_channel(context, channel_id, unarchive=True, network=network)

    return cliq_channel_unarchive


def build_cliq_leave_command(
    context: CliqChannelManagementContext,
) -> Callable[..., None]:
    """Build ``zoho cliq leave`` with injected runtime state."""

    def cliq_leave(
        channel_id: Optional[str] = typer.Option(
            None, "--channel-id", help="Destination channel id (resolved to chat_id)."
        ),
        chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Chat id."),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """Leave one chat/channel conversation."""
        _require_destination(chat_id, channel_id)

        client = _client(context, network)
        resolved_chat = _resolved_chat(client, chat_id, channel_id)
        data = _data(client.leave_chat(chat_id=resolved_chat, channel_id=channel_id))
        utils.output_status(
            "Cliq conversation left",
            extra={
                "chatId": resolved_chat or "",
                "channelId": channel_id or "",
                "result": data,
            },
        )

    return cliq_leave


def build_cliq_mute_command(
    context: CliqChannelManagementContext,
) -> Callable[..., None]:
    """Build ``zoho cliq mute`` with injected runtime state."""

    def cliq_mute(
        channel_id: Optional[str] = typer.Option(
            None, "--channel-id", help="Destination channel id (resolved to chat_id)."
        ),
        chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Chat id."),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """Mute one chat/channel conversation."""
        _require_destination(chat_id, channel_id)

        client = _client(context, network)
        resolved_chat = _resolved_chat(client, chat_id, channel_id)
        data = _data(
            client.set_chat_mute(
                chat_id=resolved_chat,
                channel_id=channel_id,
                muted=True,
            )
        )
        utils.output_status(
            "Cliq conversation muted",
            extra={
                "chatId": resolved_chat or "",
                "channelId": channel_id or "",
                "muted": True,
                "result": data,
            },
        )

    return cliq_mute


def build_cliq_unmute_command(
    context: CliqChannelManagementContext,
) -> Callable[..., None]:
    """Build ``zoho cliq unmute`` with injected runtime state."""

    def cliq_unmute(
        channel_id: Optional[str] = typer.Option(
            None, "--channel-id", help="Destination channel id (resolved to chat_id)."
        ),
        chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Chat id."),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """Unmute one chat/channel conversation."""
        _require_destination(chat_id, channel_id)

        client = _client(context, network)
        resolved_chat = _resolved_chat(client, chat_id, channel_id)
        data = _data(
            client.set_chat_mute(
                chat_id=resolved_chat,
                channel_id=channel_id,
                muted=False,
            )
        )
        utils.output_status(
            "Cliq conversation unmuted",
            extra={
                "chatId": resolved_chat or "",
                "channelId": channel_id or "",
                "muted": False,
                "result": data,
            },
        )

    return cliq_unmute
