from __future__ import annotations

from functools import partial

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
from zoho_cli.commands.cliq import register_cliq_channel_member_management_commands
from zoho_cli.commands.cliq import register_cliq_channel_metadata_commands
from zoho_cli.commands.cliq import register_cliq_channel_membership_commands
from zoho_cli.commands.cliq import register_cliq_message_discovery_commands
from zoho_cli.commands.cliq import register_cliq_mute_unmute_commands
from zoho_cli.commands.cliq import register_cliq_pinned_commands
from zoho_cli.commands.cliq import register_cliq_pin_unpin_commands
from zoho_cli.commands.cliq import register_cliq_scheduled_cancel_leave_commands
from zoho_cli.commands.cliq import register_cliq_scheduled_lifecycle_commands
from zoho_cli.commands.cliq import register_cliq_bridge_run_commands
from zoho_cli.commands.cliq import register_cliq_capabilities_commands
from zoho_cli.commands.cliq import register_cliq_status_commands
from zoho_cli.commands.cliq import register_cliq_thread_commands
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
    assert commands_pkg.register_cliq_status_commands is register_cliq_status_commands
    assert (
        commands_pkg.register_cliq_scheduled_cancel_leave_commands
        is register_cliq_scheduled_cancel_leave_commands
    )
    assert commands_pkg.register_cliq_thread_commands is register_cliq_thread_commands
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
