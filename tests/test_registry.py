from __future__ import annotations

from functools import partial
from pathlib import Path

import typer

import zoho_cli.commands as commands_pkg
from zoho_cli.cli import (
    app as cli_app,
    attachment_subapp,
    cliq_app,
    config_app,
    crm_app,
    folders_app,
    labels_app,
    mail_app,
    membrane_app,
)
from zoho_cli.commands.cliq import register_cliq_app_catalog_commands
from zoho_cli.commands.cliq import register_cliq_app_catalog_bridge_commands
from zoho_cli.commands.cliq import register_cliq_app_commands_bridge_commands
from zoho_cli.commands.cliq import register_cliq_app_commands_commands
from zoho_cli.commands.cliq import register_cliq_channel_lifecycle_commands
from zoho_cli.commands.cliq import register_cliq_channel_unarchive_commands
from zoho_cli.commands.cliq import register_cliq_channel_member_management_commands
from zoho_cli.commands.cliq import register_cliq_channel_metadata_commands
from zoho_cli.commands.cliq import register_cliq_channel_membership_commands
from zoho_cli.commands.cliq import register_cliq_message_discovery_commands
from zoho_cli.commands.cliq import register_cliq_file_voice_commands
from zoho_cli.commands.cliq import register_cliq_messages_message_commands
from zoho_cli.commands.cliq import register_cliq_context_watch_context_commands
from zoho_cli.commands.cliq import register_cliq_watch_act_commands
from zoho_cli.commands.cliq import register_cliq_voice_send_commands
from zoho_cli.commands.cliq import register_cliq_reply_edit_commands
from zoho_cli.commands.cliq import register_cliq_delete_react_commands
from zoho_cli.commands.cliq import register_cliq_mark_read_commands
from zoho_cli.commands.cliq import register_cliq_status_reaction_commands
from zoho_cli.commands.cliq import register_cliq_mute_unmute_commands
from zoho_cli.commands.cliq import register_cliq_pinned_commands
from zoho_cli.commands.cliq import register_cliq_pin_unpin_commands
from zoho_cli.commands.cliq import register_cliq_scheduled_cancel_leave_commands
from zoho_cli.commands.cliq import register_cliq_scheduled_lifecycle_commands
from zoho_cli.commands.cliq import register_cliq_bridge_run_commands
from zoho_cli.commands.cliq import register_cliq_capabilities_commands
from zoho_cli.commands.cliq import register_cliq_channels_chats_commands
from zoho_cli.commands.cliq import register_cliq_users_teams_commands
from zoho_cli.commands.cliq import register_cliq_departments_roles_commands
from zoho_cli.commands.cliq import register_cliq_designations_user_status_commands
from zoho_cli.commands.cliq import register_cliq_userfields_commands
from zoho_cli.commands.cliq import register_cliq_events_reminders_commands
from zoho_cli.commands.cliq import register_cliq_meetings_databases_commands
from zoho_cli.commands.cliq import register_cliq_widgets_map_tickers_commands
from zoho_cli.commands.cliq import register_cliq_custom_domains_emails_commands
from zoho_cli.commands.cliq import register_cliq_status_commands
from zoho_cli.commands.cliq import register_cliq_thread_commands
from zoho_cli.commands.cliq import register_cliq_threads_commands
from zoho_cli.commands.cliq import register_cliq_post_to_bot_commands
from zoho_cli.commands.cliq import register_cliq_bot_subscribers_commands
from zoho_cli.commands.cliq import register_cliq_trigger_bot_commands
from zoho_cli.commands.cliq import register_cliq_notify_mail_commands
from zoho_cli.commands.cliq import register_cliq_thread_state_commands
from zoho_cli.commands.cliq import register_cliq_export_commands
from zoho_cli.commands.cliq import register_cliq_identity_commands
from zoho_cli.commands.cliq import register_cliq_app_installs_bridge_commands
from zoho_cli.commands.cliq import register_cliq_app_installs_commands
from zoho_cli.commands.cliq import register_cliq_app_permissions_bridge_commands
from zoho_cli.commands.cliq import register_cliq_app_permissions_commands
from zoho_cli.commands.root import (
    register_builtin_root_typers,
    register_cliq_root_typers,
    register_cliq_crm_config_root_typers,
    register_cliq_crm_root_typers,
    register_config_root_typers,
    register_crm_root_typers,
    register_crm_config_root_typers,
    register_mail_primary_root_typers,
    register_mail_root_typers,
    register_mail_support_root_typers,
    register_mail_support_typers_under_mail,
    register_membrane_root_typers,
)
from zoho_cli.registry import register_root_commands


def test_register_root_commands_is_noop_scaffold() -> None:
    app = typer.Typer()
    before = len(app.registered_commands)

    register_root_commands(app)

    assert len(app.registered_commands) == before


def test_commands_package_exports_root_registrars() -> None:
    assert (
        commands_pkg.register_cliq_app_catalog_commands
        is register_cliq_app_catalog_commands
    )
    assert (
        commands_pkg.register_cliq_app_catalog_bridge_commands
        is register_cliq_app_catalog_bridge_commands
    )
    assert (
        commands_pkg.register_cliq_app_permissions_commands
        is register_cliq_app_permissions_commands
    )
    assert (
        commands_pkg.register_cliq_app_permissions_bridge_commands
        is register_cliq_app_permissions_bridge_commands
    )
    assert (
        commands_pkg.register_cliq_app_commands_commands
        is register_cliq_app_commands_commands
    )
    assert (
        commands_pkg.register_cliq_app_commands_bridge_commands
        is register_cliq_app_commands_bridge_commands
    )
    assert (
        commands_pkg.register_cliq_channel_lifecycle_commands
        is register_cliq_channel_lifecycle_commands
    )
    assert (
        commands_pkg.register_cliq_channel_unarchive_commands
        is register_cliq_channel_unarchive_commands
    )
    assert (
        commands_pkg.register_cliq_channel_member_management_commands
        is register_cliq_channel_member_management_commands
    )
    assert (
        commands_pkg.register_cliq_channel_metadata_commands
        is register_cliq_channel_metadata_commands
    )
    assert (
        commands_pkg.register_cliq_channel_membership_commands
        is register_cliq_channel_membership_commands
    )
    assert (
        commands_pkg.register_cliq_message_discovery_commands
        is register_cliq_message_discovery_commands
    )
    assert (
        commands_pkg.register_cliq_file_voice_commands
        is register_cliq_file_voice_commands
    )
    assert (
        commands_pkg.register_cliq_messages_message_commands
        is register_cliq_messages_message_commands
    )
    assert (
        commands_pkg.register_cliq_context_watch_context_commands
        is register_cliq_context_watch_context_commands
    )
    assert (
        commands_pkg.register_cliq_watch_act_commands
        is register_cliq_watch_act_commands
    )
    assert (
        commands_pkg.register_cliq_voice_send_commands
        is register_cliq_voice_send_commands
    )
    assert (
        commands_pkg.register_cliq_reply_edit_commands
        is register_cliq_reply_edit_commands
    )
    assert (
        commands_pkg.register_cliq_delete_react_commands
        is register_cliq_delete_react_commands
    )
    assert (
        commands_pkg.register_cliq_mark_read_commands
        is register_cliq_mark_read_commands
    )
    assert (
        commands_pkg.register_cliq_status_reaction_commands
        is register_cliq_status_reaction_commands
    )
    assert (
        commands_pkg.register_cliq_mute_unmute_commands
        is register_cliq_mute_unmute_commands
    )
    assert commands_pkg.register_cliq_pinned_commands is register_cliq_pinned_commands
    assert (
        commands_pkg.register_cliq_pin_unpin_commands
        is register_cliq_pin_unpin_commands
    )
    assert (
        commands_pkg.register_cliq_scheduled_lifecycle_commands
        is register_cliq_scheduled_lifecycle_commands
    )
    assert (
        commands_pkg.register_cliq_bridge_run_commands
        is register_cliq_bridge_run_commands
    )
    assert (
        commands_pkg.register_cliq_capabilities_commands
        is register_cliq_capabilities_commands
    )
    assert (
        commands_pkg.register_cliq_channels_chats_commands
        is register_cliq_channels_chats_commands
    )
    assert (
        commands_pkg.register_cliq_users_teams_commands
        is register_cliq_users_teams_commands
    )
    assert (
        commands_pkg.register_cliq_departments_roles_commands
        is register_cliq_departments_roles_commands
    )
    assert (
        commands_pkg.register_cliq_designations_user_status_commands
        is register_cliq_designations_user_status_commands
    )
    assert (
        commands_pkg.register_cliq_userfields_commands
        is register_cliq_userfields_commands
    )
    assert (
        commands_pkg.register_cliq_events_reminders_commands
        is register_cliq_events_reminders_commands
    )
    assert (
        commands_pkg.register_cliq_meetings_databases_commands
        is register_cliq_meetings_databases_commands
    )
    assert (
        commands_pkg.register_cliq_widgets_map_tickers_commands
        is register_cliq_widgets_map_tickers_commands
    )
    assert (
        commands_pkg.register_cliq_custom_domains_emails_commands
        is register_cliq_custom_domains_emails_commands
    )
    assert commands_pkg.register_cliq_status_commands is register_cliq_status_commands
    assert (
        commands_pkg.register_cliq_scheduled_cancel_leave_commands
        is register_cliq_scheduled_cancel_leave_commands
    )
    assert commands_pkg.register_cliq_thread_commands is register_cliq_thread_commands
    assert commands_pkg.register_cliq_threads_commands is register_cliq_threads_commands
    assert (
        commands_pkg.register_cliq_post_to_bot_commands
        is register_cliq_post_to_bot_commands
    )
    assert (
        commands_pkg.register_cliq_bot_subscribers_commands
        is register_cliq_bot_subscribers_commands
    )
    assert (
        commands_pkg.register_cliq_trigger_bot_commands
        is register_cliq_trigger_bot_commands
    )
    assert (
        commands_pkg.register_cliq_notify_mail_commands
        is register_cliq_notify_mail_commands
    )
    assert (
        commands_pkg.register_cliq_thread_state_commands
        is register_cliq_thread_state_commands
    )
    assert commands_pkg.register_cliq_export_commands is register_cliq_export_commands
    assert (
        commands_pkg.register_cliq_identity_commands is register_cliq_identity_commands
    )
    assert (
        commands_pkg.register_cliq_app_installs_commands
        is register_cliq_app_installs_commands
    )
    assert (
        commands_pkg.register_cliq_app_installs_bridge_commands
        is register_cliq_app_installs_bridge_commands
    )
    assert commands_pkg.register_cliq_root_typers is register_cliq_root_typers
    assert (
        commands_pkg.register_crm_config_root_typers is register_crm_config_root_typers
    )
    assert (
        commands_pkg.register_mail_support_typers_under_mail
        is register_mail_support_typers_under_mail
    )
    assert commands_pkg.register_membrane_root_typers is register_membrane_root_typers


def test_register_root_commands_runs_supplied_registrars_in_order() -> None:
    app = typer.Typer()
    seen: list[str] = []

    def first(_app: typer.Typer) -> None:
        seen.append("first")

    def second(_app: typer.Typer) -> None:
        seen.append("second")

    register_root_commands(app, registrars=(first, second))

    assert seen == ["first", "second"]


def test_register_cliq_app_catalog_commands_preserves_expected_command_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    def _apps_command() -> None:
        return None

    def _app_get_command() -> None:
        return None

    register_cliq_app_catalog_commands(
        app,
        cliq_apps_command=_apps_command,
        cliq_app_get_command=_app_get_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "apps",
        "app-get",
    ]


def test_register_cliq_app_catalog_bridge_commands_preserves_expected_command_names() -> (
    None
):
    app = typer.Typer(no_args_is_help=True)

    def _apps_bridge_run_command() -> None:
        return None

    def _app_get_bridge_run_command() -> None:
        return None

    register_cliq_app_catalog_bridge_commands(
        app,
        cliq_apps_bridge_run_command=_apps_bridge_run_command,
        cliq_app_get_bridge_run_command=_app_get_bridge_run_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "apps-bridge-run",
        "app-get-bridge-run",
    ]


def test_register_cliq_app_permissions_commands_preserves_expected_command_names() -> (
    None
):
    app = typer.Typer(no_args_is_help=True)

    def _app_permissions_command() -> None:
        return None

    def _app_permission_get_command() -> None:
        return None

    register_cliq_app_permissions_commands(
        app,
        cliq_app_permissions_command=_app_permissions_command,
        cliq_app_permission_get_command=_app_permission_get_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "app-permissions",
        "app-permission-get",
    ]


def test_register_cliq_app_commands_commands_preserves_expected_command_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    def _app_commands_command() -> None:
        return None

    def _app_command_get_command() -> None:
        return None

    register_cliq_app_commands_commands(
        app,
        cliq_app_commands_command=_app_commands_command,
        cliq_app_command_get_command=_app_command_get_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "app-commands",
        "app-command-get",
    ]


def test_register_cliq_app_installs_commands_preserves_expected_command_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    def _app_installs_command() -> None:
        return None

    def _app_install_get_command() -> None:
        return None

    register_cliq_app_installs_commands(
        app,
        cliq_app_installs_command=_app_installs_command,
        cliq_app_install_get_command=_app_install_get_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "app-installs",
        "app-install-get",
    ]


def test_register_cliq_app_permissions_bridge_commands_preserves_expected_command_names() -> (
    None
):
    app = typer.Typer(no_args_is_help=True)

    def _app_permissions_bridge_run_command() -> None:
        return None

    def _app_permission_get_bridge_run_command() -> None:
        return None

    register_cliq_app_permissions_bridge_commands(
        app,
        cliq_app_permissions_bridge_run_command=_app_permissions_bridge_run_command,
        cliq_app_permission_get_bridge_run_command=_app_permission_get_bridge_run_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "app-permissions-bridge-run",
        "app-permission-get-bridge-run",
    ]


def test_register_cliq_app_installs_bridge_commands_preserves_expected_command_names() -> (
    None
):
    app = typer.Typer(no_args_is_help=True)

    def _app_installs_bridge_run_command() -> None:
        return None

    def _app_install_get_bridge_run_command() -> None:
        return None

    register_cliq_app_installs_bridge_commands(
        app,
        cliq_app_installs_bridge_run_command=_app_installs_bridge_run_command,
        cliq_app_install_get_bridge_run_command=_app_install_get_bridge_run_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "app-install-get-bridge-run",
        "app-installs-bridge-run",
    ]


def test_register_cliq_app_commands_bridge_commands_preserves_expected_command_names() -> (
    None
):
    app = typer.Typer(no_args_is_help=True)

    def _app_commands_bridge_run_command() -> None:
        return None

    def _app_command_get_bridge_run_command() -> None:
        return None

    register_cliq_app_commands_bridge_commands(
        app,
        cliq_app_commands_bridge_run_command=_app_commands_bridge_run_command,
        cliq_app_command_get_bridge_run_command=_app_command_get_bridge_run_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "app-commands-bridge-run",
        "app-command-get-bridge-run",
    ]


def test_register_cliq_export_commands_preserves_expected_command_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    def _export_chats_command() -> None:
        return None

    def _export_chats_bridge_run_command() -> None:
        return None

    register_cliq_export_commands(
        app,
        cliq_export_chats_command=_export_chats_command,
        cliq_export_chats_bridge_run_command=_export_chats_bridge_run_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "export-chats",
        "export-chats-bridge-run",
    ]


def test_register_cliq_identity_commands_preserves_expected_command_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    def _whoami_command() -> None:
        return None

    def _user_resolve_command() -> None:
        return None

    register_cliq_identity_commands(
        app,
        cliq_whoami_command=_whoami_command,
        cliq_user_resolve_command=_user_resolve_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "whoami",
        "user-resolve",
    ]


def test_register_cliq_channel_membership_commands_preserves_expected_command_names() -> (
    None
):
    app = typer.Typer(no_args_is_help=True)

    def _members_command() -> None:
        return None

    def _channel_create_command() -> None:
        return None

    register_cliq_channel_membership_commands(
        app,
        cliq_members_command=_members_command,
        cliq_channel_create_command=_channel_create_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "members",
        "channel-create",
    ]


def test_register_cliq_channel_metadata_commands_preserves_expected_command_names() -> (
    None
):
    app = typer.Typer(no_args_is_help=True)

    def _channel_rename_command() -> None:
        return None

    def _channel_topic_command() -> None:
        return None

    register_cliq_channel_metadata_commands(
        app,
        cliq_channel_rename_command=_channel_rename_command,
        cliq_channel_topic_command=_channel_topic_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "channel-rename",
        "channel-topic",
    ]


def test_register_cliq_channel_member_management_commands_preserves_expected_command_names() -> (
    None
):
    app = typer.Typer(no_args_is_help=True)

    def _member_add_command() -> None:
        return None

    def _member_remove_command() -> None:
        return None

    register_cliq_channel_member_management_commands(
        app,
        cliq_member_add_command=_member_add_command,
        cliq_member_remove_command=_member_remove_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "member-add",
        "member-remove",
    ]


def test_register_cliq_channel_lifecycle_commands_preserves_expected_command_names() -> (
    None
):
    app = typer.Typer(no_args_is_help=True)

    def _channel_archive_command() -> None:
        return None

    def _channel_delete_command() -> None:
        return None

    register_cliq_channel_lifecycle_commands(
        app,
        cliq_channel_archive_command=_channel_archive_command,
        cliq_channel_delete_command=_channel_delete_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "channel-archive",
        "channel-delete",
    ]


def test_register_cliq_channel_unarchive_commands_preserves_expected_command_names() -> (
    None
):
    app = typer.Typer(no_args_is_help=True)

    def _channel_unarchive_command() -> None:
        return None

    register_cliq_channel_unarchive_commands(
        app,
        cliq_channel_unarchive_command=_channel_unarchive_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "channel-unarchive",
    ]


def test_register_cliq_thread_commands_preserves_expected_command_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    def _thread_create_command() -> None:
        return None

    def _thread_reply_command() -> None:
        return None

    register_cliq_thread_commands(
        app,
        cliq_thread_create_command=_thread_create_command,
        cliq_thread_reply_command=_thread_reply_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "thread-create",
        "thread-reply",
    ]


def test_register_cliq_threads_commands_preserves_expected_command_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    def _threads_command() -> None:
        return None

    register_cliq_threads_commands(
        app,
        cliq_threads_command=_threads_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "threads",
    ]


def test_register_cliq_post_to_bot_commands_preserves_expected_command_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    def _post_to_bot_command() -> None:
        return None

    register_cliq_post_to_bot_commands(
        app,
        cliq_post_to_bot_command=_post_to_bot_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "post-to-bot",
    ]


def test_register_cliq_bot_subscribers_commands_preserves_expected_command_names() -> (
    None
):
    app = typer.Typer(no_args_is_help=True)

    def _bot_subscribers_command() -> None:
        return None

    register_cliq_bot_subscribers_commands(
        app,
        cliq_bot_subscribers_command=_bot_subscribers_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "bot-subscribers",
    ]


def test_register_cliq_trigger_bot_commands_preserves_expected_command_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    def _trigger_bot_command() -> None:
        return None

    register_cliq_trigger_bot_commands(
        app,
        cliq_trigger_bot_command=_trigger_bot_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "trigger-bot",
    ]


def test_register_cliq_notify_mail_commands_preserves_expected_command_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    def _notify_mail_command() -> None:
        return None

    register_cliq_notify_mail_commands(
        app,
        cliq_notify_mail_command=_notify_mail_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "notify-mail",
    ]


def test_register_cliq_thread_state_commands_preserves_expected_command_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    def _thread_followers_command() -> None:
        return None

    def _thread_state_command() -> None:
        return None

    register_cliq_thread_state_commands(
        app,
        cliq_thread_followers_command=_thread_followers_command,
        cliq_thread_state_command=_thread_state_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "thread-followers",
        "thread-state",
    ]


def test_register_cliq_message_discovery_commands_preserves_expected_command_names() -> (
    None
):
    app = typer.Typer(no_args_is_help=True)

    def _schedule_command() -> None:
        return None

    def _search_command() -> None:
        return None

    register_cliq_message_discovery_commands(
        app,
        cliq_schedule_command=_schedule_command,
        cliq_search_command=_search_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "schedule",
        "search",
    ]


def test_register_cliq_file_voice_commands_preserves_expected_command_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    def _file_command() -> None:
        return None

    def _voice_command() -> None:
        return None

    register_cliq_file_voice_commands(
        app,
        cliq_file_command=_file_command,
        cliq_voice_command=_voice_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "file",
        "voice",
    ]


def test_register_cliq_messages_message_commands_preserves_expected_command_names() -> (
    None
):
    app = typer.Typer(no_args_is_help=True)

    def _messages_command() -> None:
        return None

    def _message_command() -> None:
        return None

    register_cliq_messages_message_commands(
        app,
        cliq_messages_command=_messages_command,
        cliq_message_command=_message_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "messages",
        "message",
    ]


def test_register_cliq_context_watch_context_commands_preserves_expected_command_names() -> (
    None
):
    app = typer.Typer(no_args_is_help=True)

    def _context_command() -> None:
        return None

    def _watch_context_command() -> None:
        return None

    register_cliq_context_watch_context_commands(
        app,
        cliq_context_command=_context_command,
        cliq_watch_context_command=_watch_context_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "context",
        "watch-context",
    ]


def test_register_cliq_watch_act_commands_preserves_expected_command_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    def _watch_act_command() -> None:
        return None

    register_cliq_watch_act_commands(
        app,
        cliq_watch_act_command=_watch_act_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "watch-act",
    ]


def test_register_cliq_voice_send_commands_preserves_expected_command_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    def _voice_send_command() -> None:
        return None

    def _send_command() -> None:
        return None

    register_cliq_voice_send_commands(
        app,
        cliq_voice_send_command=_voice_send_command,
        cliq_send_command=_send_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "voice-send",
        "send",
    ]


def test_register_cliq_reply_edit_commands_preserves_expected_command_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    def _reply_command() -> None:
        return None

    def _edit_command() -> None:
        return None

    register_cliq_reply_edit_commands(
        app,
        cliq_reply_command=_reply_command,
        cliq_edit_command=_edit_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "reply",
        "edit",
    ]


def test_register_cliq_delete_react_commands_preserves_expected_command_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    def _delete_command() -> None:
        return None

    def _react_command() -> None:
        return None

    register_cliq_delete_react_commands(
        app,
        cliq_delete_command=_delete_command,
        cliq_react_command=_react_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "delete",
        "react",
    ]


def test_register_cliq_mark_read_commands_preserves_expected_command_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    def _mark_read_command() -> None:
        return None

    register_cliq_mark_read_commands(
        app,
        cliq_mark_read_command=_mark_read_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "mark-read",
    ]


def test_register_cliq_status_reaction_commands_preserves_expected_command_names() -> (
    None
):
    app = typer.Typer(no_args_is_help=True)

    def _status_react_command() -> None:
        return None

    register_cliq_status_reaction_commands(
        app,
        cliq_status_reaction_command=_status_react_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "status-react",
    ]


def test_register_cliq_scheduled_lifecycle_commands_preserves_expected_command_names() -> (
    None
):
    app = typer.Typer(no_args_is_help=True)

    def _scheduled_command() -> None:
        return None

    def _scheduled_get_command() -> None:
        return None

    register_cliq_scheduled_lifecycle_commands(
        app,
        cliq_scheduled_command=_scheduled_command,
        cliq_scheduled_get_command=_scheduled_get_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "scheduled",
        "scheduled-get",
    ]


def test_register_cliq_scheduled_cancel_leave_commands_preserves_expected_command_names() -> (
    None
):
    app = typer.Typer(no_args_is_help=True)

    def _scheduled_cancel_command() -> None:
        return None

    def _leave_command() -> None:
        return None

    register_cliq_scheduled_cancel_leave_commands(
        app,
        cliq_scheduled_cancel_command=_scheduled_cancel_command,
        cliq_leave_command=_leave_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "scheduled-cancel",
        "leave",
    ]


def test_register_cliq_mute_unmute_commands_preserves_expected_command_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    def _mute_command() -> None:
        return None

    def _unmute_command() -> None:
        return None

    register_cliq_mute_unmute_commands(
        app,
        cliq_mute_command=_mute_command,
        cliq_unmute_command=_unmute_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "mute",
        "unmute",
    ]


def test_register_cliq_pin_unpin_commands_preserves_expected_command_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    def _pin_command() -> None:
        return None

    def _unpin_command() -> None:
        return None

    register_cliq_pin_unpin_commands(
        app,
        cliq_pin_command=_pin_command,
        cliq_unpin_command=_unpin_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "pin",
        "unpin",
    ]


def test_register_cliq_pinned_commands_preserves_expected_command_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    def _pinned_command() -> None:
        return None

    register_cliq_pinned_commands(
        app,
        cliq_pinned_command=_pinned_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "pinned",
    ]


def test_register_cliq_status_commands_preserves_expected_command_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    def _status_command() -> None:
        return None

    register_cliq_status_commands(
        app,
        cliq_status_command=_status_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "status",
    ]


def test_register_cliq_bridge_run_commands_preserves_expected_command_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    def _bridge_run_command() -> None:
        return None

    register_cliq_bridge_run_commands(
        app,
        cliq_bridge_run_command=_bridge_run_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "bridge-run",
    ]


def test_register_cliq_capabilities_commands_preserves_expected_command_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    def _capabilities_command() -> None:
        return None

    register_cliq_capabilities_commands(
        app,
        cliq_capabilities_command=_capabilities_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "capabilities",
    ]


def test_register_cliq_channels_chats_commands_preserves_expected_command_names() -> (
    None
):
    app = typer.Typer(no_args_is_help=True)

    def _channels_command() -> None:
        return None

    def _chats_command() -> None:
        return None

    register_cliq_channels_chats_commands(
        app,
        cliq_channels_command=_channels_command,
        cliq_chats_command=_chats_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "channels",
        "chats",
    ]


def test_register_cliq_users_teams_commands_preserves_expected_command_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    def _users_command() -> None:
        return None

    def _teams_command() -> None:
        return None

    register_cliq_users_teams_commands(
        app,
        cliq_users_command=_users_command,
        cliq_teams_command=_teams_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "users",
        "teams",
    ]


def test_register_cliq_departments_roles_commands_preserves_expected_command_names() -> (
    None
):
    app = typer.Typer(no_args_is_help=True)

    def _departments_command() -> None:
        return None

    def _roles_command() -> None:
        return None

    register_cliq_departments_roles_commands(
        app,
        cliq_departments_command=_departments_command,
        cliq_roles_command=_roles_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "departments",
        "roles",
    ]


def test_register_cliq_designations_user_status_commands_preserves_expected_command_names() -> (
    None
):
    app = typer.Typer(no_args_is_help=True)

    def _designations_command() -> None:
        return None

    def _user_status_command() -> None:
        return None

    register_cliq_designations_user_status_commands(
        app,
        cliq_designations_command=_designations_command,
        cliq_user_status_command=_user_status_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "designations",
        "user-status",
    ]


def test_register_cliq_userfields_commands_preserves_expected_command_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    def _userfields_command() -> None:
        return None

    register_cliq_userfields_commands(
        app,
        cliq_userfields_command=_userfields_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "userfields",
    ]


def test_register_cliq_events_reminders_commands_preserves_expected_command_names() -> (
    None
):
    app = typer.Typer(no_args_is_help=True)

    def _events_command() -> None:
        return None

    def _reminders_command() -> None:
        return None

    register_cliq_events_reminders_commands(
        app,
        cliq_events_command=_events_command,
        cliq_reminders_command=_reminders_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "events",
        "reminders",
    ]


def test_register_cliq_meetings_databases_commands_preserves_expected_command_names() -> (
    None
):
    app = typer.Typer(no_args_is_help=True)

    def _meetings_command() -> None:
        return None

    def _databases_command() -> None:
        return None

    register_cliq_meetings_databases_commands(
        app,
        cliq_meetings_command=_meetings_command,
        cliq_databases_command=_databases_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "meetings",
        "databases",
    ]


def test_register_cliq_widgets_map_tickers_commands_preserves_expected_command_names() -> (
    None
):
    app = typer.Typer(no_args_is_help=True)

    def _widgets_command() -> None:
        return None

    def _map_tickers_command() -> None:
        return None

    register_cliq_widgets_map_tickers_commands(
        app,
        cliq_widgets_command=_widgets_command,
        cliq_map_tickers_command=_map_tickers_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "widgets",
        "map-tickers",
    ]


def test_register_cliq_custom_domains_emails_commands_preserves_expected_command_names() -> (
    None
):
    app = typer.Typer(no_args_is_help=True)

    def _custom_domains_command() -> None:
        return None

    def _custom_emails_command() -> None:
        return None

    register_cliq_custom_domains_emails_commands(
        app,
        cliq_custom_domains_command=_custom_domains_command,
        cliq_custom_emails_command=_custom_emails_command,
    )

    assert [command.name for command in app.registered_commands] == [
        "custom-domains",
        "custom-emails",
    ]


def test_register_builtin_root_typers_preserves_expected_group_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    register_root_commands(
        app,
        registrars=(
            partial(
                register_builtin_root_typers,
                mail_app=mail_app,
                attachment_app=attachment_subapp,
                folders_app=folders_app,
                labels_app=labels_app,
                cliq_app=cliq_app,
                crm_app=crm_app,
                config_app=config_app,
                membrane_app=membrane_app,
            ),
        ),
    )

    assert [group.name for group in app.registered_groups] == [
        "mail",
        "attachment",
        "folders",
        "labels",
        "cliq",
        "crm",
        "config",
        "membrane",
    ]


def test_register_membrane_root_typers_preserves_expected_group_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    register_root_commands(
        app,
        registrars=(
            partial(
                register_membrane_root_typers,
                membrane_app=membrane_app,
            ),
        ),
    )

    assert [group.name for group in app.registered_groups] == ["membrane"]


def test_register_mail_root_typers_preserves_expected_group_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    register_root_commands(
        app,
        registrars=(
            partial(
                register_mail_root_typers,
                mail_app=mail_app,
                attachment_app=attachment_subapp,
                folders_app=folders_app,
                labels_app=labels_app,
            ),
        ),
    )

    assert [group.name for group in app.registered_groups] == [
        "mail",
        "attachment",
        "folders",
        "labels",
    ]


def test_register_mail_primary_root_typers_preserves_expected_group_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    register_root_commands(
        app,
        registrars=(
            partial(
                register_mail_primary_root_typers,
                mail_app=mail_app,
            ),
        ),
    )

    assert [group.name for group in app.registered_groups] == ["mail"]


def test_register_mail_support_root_typers_preserves_expected_group_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    register_root_commands(
        app,
        registrars=(
            partial(
                register_mail_support_root_typers,
                attachment_app=attachment_subapp,
                folders_app=folders_app,
                labels_app=labels_app,
            ),
        ),
    )

    assert [group.name for group in app.registered_groups] == [
        "attachment",
        "folders",
        "labels",
    ]


def test_register_mail_support_typers_under_mail_preserves_expected_group_names() -> (
    None
):
    app = typer.Typer(no_args_is_help=True)

    register_mail_support_typers_under_mail(
        app,
        attachment_app=attachment_subapp,
        folders_app=folders_app,
        labels_app=labels_app,
    )

    assert [group.name for group in app.registered_groups] == [
        "attachment",
        "folders",
        "labels",
    ]


def test_register_cliq_crm_config_root_typers_preserves_expected_group_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    register_root_commands(
        app,
        registrars=(
            partial(
                register_cliq_crm_config_root_typers,
                cliq_app=cliq_app,
                crm_app=crm_app,
                config_app=config_app,
            ),
        ),
    )

    assert [group.name for group in app.registered_groups] == [
        "cliq",
        "crm",
        "config",
    ]


def test_register_cliq_root_typers_preserves_expected_group_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    register_root_commands(
        app,
        registrars=(
            partial(
                register_cliq_root_typers,
                cliq_app=cliq_app,
            ),
        ),
    )

    assert [group.name for group in app.registered_groups] == ["cliq"]


def test_register_cliq_crm_root_typers_preserves_expected_group_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    register_root_commands(
        app,
        registrars=(
            partial(
                register_cliq_crm_root_typers,
                cliq_app=cliq_app,
                crm_app=crm_app,
            ),
        ),
    )

    assert [group.name for group in app.registered_groups] == ["cliq", "crm"]


def test_register_crm_config_root_typers_preserves_expected_group_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    register_root_commands(
        app,
        registrars=(
            partial(
                register_crm_config_root_typers,
                crm_app=crm_app,
                config_app=config_app,
            ),
        ),
    )

    assert [group.name for group in app.registered_groups] == ["crm", "config"]


def test_register_crm_root_typers_preserves_expected_group_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    register_root_commands(
        app,
        registrars=(
            partial(
                register_crm_root_typers,
                crm_app=crm_app,
            ),
        ),
    )

    assert [group.name for group in app.registered_groups] == ["crm"]


def test_register_config_root_typers_preserves_expected_group_names() -> None:
    app = typer.Typer(no_args_is_help=True)

    register_root_commands(
        app,
        registrars=(
            partial(
                register_config_root_typers,
                config_app=config_app,
            ),
        ),
    )

    assert [group.name for group in app.registered_groups] == ["config"]


def test_cli_app_root_group_names_match_expected_defaults() -> None:
    assert [group.name for group in cli_app.registered_groups] == [
        "mail",
        "attachment",
        "folders",
        "labels",
        "cliq",
        "crm",
        "config",
        "membrane",
    ]


def test_cli_module_has_no_direct_cliq_command_decorators() -> None:
    cli_module_path = Path(__file__).resolve().parents[1] / "zoho_cli" / "cli.py"
    cli_source = cli_module_path.read_text(encoding="utf-8")

    assert "@cliq_app.command" not in cli_source
