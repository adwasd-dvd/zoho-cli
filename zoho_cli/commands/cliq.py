"""Cliq command-registration helpers for modular CLI wiring."""

from __future__ import annotations

from collections.abc import Callable

import typer


def register_cliq_app_catalog_commands(
    cliq_app: typer.Typer,
    *,
    cliq_apps_command: Callable[..., None],
    cliq_app_get_command: Callable[..., None],
) -> None:
    """Register the first Cliq app-catalog command family on ``cliq_app``."""
    cliq_app.command("apps")(cliq_apps_command)
    cliq_app.command("app-get")(cliq_app_get_command)


def register_cliq_app_catalog_bridge_commands(
    cliq_app: typer.Typer,
    *,
    cliq_apps_bridge_run_command: Callable[..., None],
    cliq_app_get_bridge_run_command: Callable[..., None],
) -> None:
    """Register the adjacent Cliq app-catalog bridge command family."""
    cliq_app.command("apps-bridge-run")(cliq_apps_bridge_run_command)
    cliq_app.command("app-get-bridge-run")(cliq_app_get_bridge_run_command)


def register_cliq_app_commands_commands(
    cliq_app: typer.Typer,
    *,
    cliq_app_commands_command: Callable[..., None],
    cliq_app_command_get_command: Callable[..., None],
) -> None:
    """Register the adjacent Cliq app-commands command family on ``cliq_app``."""
    cliq_app.command("app-commands")(cliq_app_commands_command)
    cliq_app.command("app-command-get")(cliq_app_command_get_command)


def register_cliq_app_permissions_commands(
    cliq_app: typer.Typer,
    *,
    cliq_app_permissions_command: Callable[..., None],
    cliq_app_permission_get_command: Callable[..., None],
) -> None:
    """Register the adjacent Cliq app-permissions command family on ``cliq_app``."""
    cliq_app.command("app-permissions")(cliq_app_permissions_command)
    cliq_app.command("app-permission-get")(cliq_app_permission_get_command)


def register_cliq_app_installs_commands(
    cliq_app: typer.Typer,
    *,
    cliq_app_installs_command: Callable[..., None],
    cliq_app_install_get_command: Callable[..., None],
) -> None:
    """Register the adjacent Cliq app-installs command family on ``cliq_app``."""
    cliq_app.command("app-installs")(cliq_app_installs_command)
    cliq_app.command("app-install-get")(cliq_app_install_get_command)


def register_cliq_app_permissions_bridge_commands(
    cliq_app: typer.Typer,
    *,
    cliq_app_permissions_bridge_run_command: Callable[..., None],
    cliq_app_permission_get_bridge_run_command: Callable[..., None],
) -> None:
    """Register the adjacent Cliq app-permissions bridge command family."""
    cliq_app.command("app-permissions-bridge-run")(
        cliq_app_permissions_bridge_run_command
    )
    cliq_app.command("app-permission-get-bridge-run")(
        cliq_app_permission_get_bridge_run_command
    )


def register_cliq_app_installs_bridge_commands(
    cliq_app: typer.Typer,
    *,
    cliq_app_installs_bridge_run_command: Callable[..., None],
    cliq_app_install_get_bridge_run_command: Callable[..., None],
) -> None:
    """Register the adjacent Cliq app-installs bridge command family."""
    cliq_app.command("app-install-get-bridge-run")(
        cliq_app_install_get_bridge_run_command
    )
    cliq_app.command("app-installs-bridge-run")(cliq_app_installs_bridge_run_command)


def register_cliq_app_commands_bridge_commands(
    cliq_app: typer.Typer,
    *,
    cliq_app_commands_bridge_run_command: Callable[..., None],
    cliq_app_command_get_bridge_run_command: Callable[..., None],
) -> None:
    """Register the adjacent Cliq app-commands bridge command family."""
    cliq_app.command("app-commands-bridge-run")(cliq_app_commands_bridge_run_command)
    cliq_app.command("app-command-get-bridge-run")(
        cliq_app_command_get_bridge_run_command
    )


def register_cliq_export_commands(
    cliq_app: typer.Typer,
    *,
    cliq_export_chats_command: Callable[..., None],
    cliq_export_chats_bridge_run_command: Callable[..., None],
) -> None:
    """Register adjacent Cliq export commands on ``cliq_app``."""
    cliq_app.command("export-chats")(cliq_export_chats_command)
    cliq_app.command("export-chats-bridge-run")(cliq_export_chats_bridge_run_command)


def register_cliq_identity_commands(
    cliq_app: typer.Typer,
    *,
    cliq_whoami_command: Callable[..., None],
    cliq_user_resolve_command: Callable[..., None],
) -> None:
    """Register adjacent Cliq identity commands on ``cliq_app``."""
    cliq_app.command("whoami")(cliq_whoami_command)
    cliq_app.command("user-resolve")(cliq_user_resolve_command)


def register_cliq_channel_membership_commands(
    cliq_app: typer.Typer,
    *,
    cliq_members_command: Callable[..., None],
    cliq_channel_create_command: Callable[..., None],
) -> None:
    """Register adjacent Cliq channel-membership commands on ``cliq_app``."""
    cliq_app.command("members")(cliq_members_command)
    cliq_app.command("channel-create")(cliq_channel_create_command)


def register_cliq_channel_metadata_commands(
    cliq_app: typer.Typer,
    *,
    cliq_channel_rename_command: Callable[..., None],
    cliq_channel_topic_command: Callable[..., None],
) -> None:
    """Register adjacent Cliq channel-metadata commands on ``cliq_app``."""
    cliq_app.command("channel-rename")(cliq_channel_rename_command)
    cliq_app.command("channel-topic")(cliq_channel_topic_command)


def register_cliq_channel_member_management_commands(
    cliq_app: typer.Typer,
    *,
    cliq_member_add_command: Callable[..., None],
    cliq_member_remove_command: Callable[..., None],
) -> None:
    """Register adjacent Cliq channel-member management commands on ``cliq_app``."""
    cliq_app.command("member-add")(cliq_member_add_command)
    cliq_app.command("member-remove")(cliq_member_remove_command)


def register_cliq_channel_lifecycle_commands(
    cliq_app: typer.Typer,
    *,
    cliq_channel_archive_command: Callable[..., None],
    cliq_channel_delete_command: Callable[..., None],
) -> None:
    """Register adjacent Cliq channel-lifecycle commands on ``cliq_app``."""
    cliq_app.command("channel-archive")(cliq_channel_archive_command)
    cliq_app.command("channel-delete")(cliq_channel_delete_command)


def register_cliq_thread_commands(
    cliq_app: typer.Typer,
    *,
    cliq_thread_create_command: Callable[..., None],
    cliq_thread_reply_command: Callable[..., None],
) -> None:
    """Register adjacent Cliq thread commands on ``cliq_app``."""
    cliq_app.command("thread-create")(cliq_thread_create_command)
    cliq_app.command("thread-reply")(cliq_thread_reply_command)


def register_cliq_thread_state_commands(
    cliq_app: typer.Typer,
    *,
    cliq_thread_followers_command: Callable[..., None],
    cliq_thread_state_command: Callable[..., None],
) -> None:
    """Register adjacent Cliq thread-state commands on ``cliq_app``."""
    cliq_app.command("thread-followers")(cliq_thread_followers_command)
    cliq_app.command("thread-state")(cliq_thread_state_command)


def register_cliq_message_discovery_commands(
    cliq_app: typer.Typer,
    *,
    cliq_schedule_command: Callable[..., None],
    cliq_search_command: Callable[..., None],
) -> None:
    """Register adjacent Cliq message-discovery commands on ``cliq_app``."""
    cliq_app.command("schedule")(cliq_schedule_command)
    cliq_app.command("search")(cliq_search_command)


def register_cliq_scheduled_lifecycle_commands(
    cliq_app: typer.Typer,
    *,
    cliq_scheduled_command: Callable[..., None],
    cliq_scheduled_get_command: Callable[..., None],
) -> None:
    """Register adjacent Cliq scheduled-lifecycle commands on ``cliq_app``."""
    cliq_app.command("scheduled")(cliq_scheduled_command)
    cliq_app.command("scheduled-get")(cliq_scheduled_get_command)


def register_cliq_scheduled_cancel_leave_commands(
    cliq_app: typer.Typer,
    *,
    cliq_scheduled_cancel_command: Callable[..., None],
    cliq_leave_command: Callable[..., None],
) -> None:
    """Register adjacent Cliq scheduled-cancel/leave commands on ``cliq_app``."""
    cliq_app.command("scheduled-cancel")(cliq_scheduled_cancel_command)
    cliq_app.command("leave")(cliq_leave_command)
