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
