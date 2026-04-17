from __future__ import annotations

from functools import partial

import typer

from zoho_cli.cli import (
    app as cli_app,
    attachment_subapp,
    cliq_app,
    config_app,
    crm_app,
    folders_app,
    labels_app,
    mail_app,
)
from zoho_cli.commands.root import (
    register_builtin_root_typers,
    register_cliq_root_typers,
    register_cliq_crm_config_root_typers,
    register_crm_config_root_typers,
    register_mail_root_typers,
)
from zoho_cli.registry import register_root_commands


def test_register_root_commands_is_noop_scaffold() -> None:
    app = typer.Typer()
    before = len(app.registered_commands)

    register_root_commands(app)

    assert len(app.registered_commands) == before


def test_register_root_commands_runs_supplied_registrars_in_order() -> None:
    app = typer.Typer()
    seen: list[str] = []

    def first(_app: typer.Typer) -> None:
        seen.append("first")

    def second(_app: typer.Typer) -> None:
        seen.append("second")

    register_root_commands(app, registrars=(first, second))

    assert seen == ["first", "second"]


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
    ]


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


def test_cli_app_root_group_names_match_expected_defaults() -> None:
    assert [group.name for group in cli_app.registered_groups] == [
        "mail",
        "attachment",
        "folders",
        "labels",
        "cliq",
        "crm",
        "config",
    ]
