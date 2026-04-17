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
from zoho_cli.commands.cliq import register_cliq_app_commands_commands
from zoho_cli.commands.cliq import register_cliq_app_installs_commands
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
        commands_pkg.register_cliq_app_permissions_commands
        is register_cliq_app_permissions_commands
    )
    assert (
        commands_pkg.register_cliq_app_commands_commands
        is register_cliq_app_commands_commands
    )
    assert (
        commands_pkg.register_cliq_app_installs_commands
        is register_cliq_app_installs_commands
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
