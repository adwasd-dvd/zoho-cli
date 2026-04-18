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


def register_cliq_file_voice_commands(
    cliq_app: typer.Typer,
    *,
    cliq_file_command: Callable[..., None],
    cliq_voice_command: Callable[..., None],
) -> None:
    """Register adjacent Cliq file/voice retrieval commands on ``cliq_app``."""
    cliq_app.command("file")(cliq_file_command)
    cliq_app.command("voice")(cliq_voice_command)


def register_cliq_messages_message_commands(
    cliq_app: typer.Typer,
    *,
    cliq_messages_command: Callable[..., None],
    cliq_message_command: Callable[..., None],
) -> None:
    """Register adjacent Cliq messages/message read commands on ``cliq_app``."""
    cliq_app.command("messages")(cliq_messages_command)
    cliq_app.command("message")(cliq_message_command)


def register_cliq_context_watch_context_commands(
    cliq_app: typer.Typer,
    *,
    cliq_context_command: Callable[..., None],
    cliq_watch_context_command: Callable[..., None],
) -> None:
    """Register adjacent Cliq context/watch-context commands on ``cliq_app``."""
    cliq_app.command("context")(cliq_context_command)
    cliq_app.command("watch-context")(cliq_watch_context_command)


def register_cliq_watch_act_commands(
    cliq_app: typer.Typer,
    *,
    cliq_watch_act_command: Callable[..., None],
) -> None:
    """Register the Cliq watch-act command on ``cliq_app``."""
    cliq_app.command("watch-act")(cliq_watch_act_command)


def register_cliq_voice_send_commands(
    cliq_app: typer.Typer,
    *,
    cliq_voice_send_command: Callable[..., None],
    cliq_send_command: Callable[..., None],
) -> None:
    """Register adjacent Cliq voice-send/send commands on ``cliq_app``."""
    cliq_app.command("voice-send")(cliq_voice_send_command)
    cliq_app.command("send")(cliq_send_command)


def register_cliq_reply_edit_commands(
    cliq_app: typer.Typer,
    *,
    cliq_reply_command: Callable[..., None],
    cliq_edit_command: Callable[..., None],
) -> None:
    """Register adjacent Cliq reply/edit commands on ``cliq_app``."""
    cliq_app.command("reply")(cliq_reply_command)
    cliq_app.command("edit")(cliq_edit_command)


def register_cliq_delete_react_commands(
    cliq_app: typer.Typer,
    *,
    cliq_delete_command: Callable[..., None],
    cliq_react_command: Callable[..., None],
) -> None:
    """Register adjacent Cliq delete/react commands on ``cliq_app``."""
    cliq_app.command("delete")(cliq_delete_command)
    cliq_app.command("react")(cliq_react_command)


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


def register_cliq_mute_unmute_commands(
    cliq_app: typer.Typer,
    *,
    cliq_mute_command: Callable[..., None],
    cliq_unmute_command: Callable[..., None],
) -> None:
    """Register adjacent Cliq mute/unmute commands on ``cliq_app``."""
    cliq_app.command("mute")(cliq_mute_command)
    cliq_app.command("unmute")(cliq_unmute_command)


def register_cliq_pin_unpin_commands(
    cliq_app: typer.Typer,
    *,
    cliq_pin_command: Callable[..., None],
    cliq_unpin_command: Callable[..., None],
) -> None:
    """Register adjacent Cliq pin/unpin commands on ``cliq_app``."""
    cliq_app.command("pin")(cliq_pin_command)
    cliq_app.command("unpin")(cliq_unpin_command)


def register_cliq_pinned_commands(
    cliq_app: typer.Typer,
    *,
    cliq_pinned_command: Callable[..., None],
) -> None:
    """Register the Cliq pinned-messages listing command on ``cliq_app``."""
    cliq_app.command("pinned")(cliq_pinned_command)


def register_cliq_status_commands(
    cliq_app: typer.Typer,
    *,
    cliq_status_command: Callable[..., None],
) -> None:
    """Register the Cliq status command on ``cliq_app``."""
    cliq_app.command("status")(cliq_status_command)


def register_cliq_bridge_run_commands(
    cliq_app: typer.Typer,
    *,
    cliq_bridge_run_command: Callable[..., None],
) -> None:
    """Register the Cliq bridge-run command on ``cliq_app``."""
    cliq_app.command("bridge-run")(cliq_bridge_run_command)


def register_cliq_capabilities_commands(
    cliq_app: typer.Typer,
    *,
    cliq_capabilities_command: Callable[..., None],
) -> None:
    """Register the Cliq capabilities command on ``cliq_app``."""
    cliq_app.command("capabilities")(cliq_capabilities_command)


def register_cliq_channels_chats_commands(
    cliq_app: typer.Typer,
    *,
    cliq_channels_command: Callable[..., None],
    cliq_chats_command: Callable[..., None],
) -> None:
    """Register adjacent Cliq channels/chats commands on ``cliq_app``."""
    cliq_app.command("channels")(cliq_channels_command)
    cliq_app.command("chats")(cliq_chats_command)


def register_cliq_users_teams_commands(
    cliq_app: typer.Typer,
    *,
    cliq_users_command: Callable[..., None],
    cliq_teams_command: Callable[..., None],
) -> None:
    """Register adjacent Cliq users/teams commands on ``cliq_app``."""
    cliq_app.command("users")(cliq_users_command)
    cliq_app.command("teams")(cliq_teams_command)


def register_cliq_departments_roles_commands(
    cliq_app: typer.Typer,
    *,
    cliq_departments_command: Callable[..., None],
    cliq_roles_command: Callable[..., None],
) -> None:
    """Register adjacent Cliq departments/roles commands on ``cliq_app``."""
    cliq_app.command("departments")(cliq_departments_command)
    cliq_app.command("roles")(cliq_roles_command)


def register_cliq_designations_user_status_commands(
    cliq_app: typer.Typer,
    *,
    cliq_designations_command: Callable[..., None],
    cliq_user_status_command: Callable[..., None],
) -> None:
    """Register adjacent Cliq designations/user-status commands on ``cliq_app``."""
    cliq_app.command("designations")(cliq_designations_command)
    cliq_app.command("user-status")(cliq_user_status_command)


def register_cliq_userfields_commands(
    cliq_app: typer.Typer,
    *,
    cliq_userfields_command: Callable[..., None],
) -> None:
    """Register the Cliq userfields command on ``cliq_app``."""
    cliq_app.command("userfields")(cliq_userfields_command)


def register_cliq_events_reminders_commands(
    cliq_app: typer.Typer,
    *,
    cliq_events_command: Callable[..., None],
    cliq_reminders_command: Callable[..., None],
) -> None:
    """Register adjacent Cliq events/reminders commands on ``cliq_app``."""
    cliq_app.command("events")(cliq_events_command)
    cliq_app.command("reminders")(cliq_reminders_command)


def register_cliq_meetings_databases_commands(
    cliq_app: typer.Typer,
    *,
    cliq_meetings_command: Callable[..., None],
    cliq_databases_command: Callable[..., None],
) -> None:
    """Register adjacent Cliq meetings/databases commands on ``cliq_app``."""
    cliq_app.command("meetings")(cliq_meetings_command)
    cliq_app.command("databases")(cliq_databases_command)


def register_cliq_widgets_map_tickers_commands(
    cliq_app: typer.Typer,
    *,
    cliq_widgets_command: Callable[..., None],
    cliq_map_tickers_command: Callable[..., None],
) -> None:
    """Register adjacent Cliq widgets/map-tickers commands on ``cliq_app``."""
    cliq_app.command("widgets")(cliq_widgets_command)
    cliq_app.command("map-tickers")(cliq_map_tickers_command)


def register_cliq_custom_domains_emails_commands(
    cliq_app: typer.Typer,
    *,
    cliq_custom_domains_command: Callable[..., None],
    cliq_custom_emails_command: Callable[..., None],
) -> None:
    """Register adjacent Cliq custom-domains/custom-emails commands."""
    cliq_app.command("custom-domains")(cliq_custom_domains_command)
    cliq_app.command("custom-emails")(cliq_custom_emails_command)
