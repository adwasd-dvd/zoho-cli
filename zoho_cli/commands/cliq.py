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
