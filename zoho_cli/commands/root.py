"""Root command-registration helpers for modular CLI wiring."""

from __future__ import annotations

import typer


def register_mail_root_typers(
    root_app: typer.Typer,
    *,
    mail_app: typer.Typer,
    attachment_app: typer.Typer,
    folders_app: typer.Typer,
    labels_app: typer.Typer,
) -> None:
    """Register mail-family root command groups on ``root_app``."""
    root_app.add_typer(mail_app, name="mail")
    root_app.add_typer(attachment_app, name="attachment")
    root_app.add_typer(folders_app, name="folders")
    root_app.add_typer(labels_app, name="labels")


def register_builtin_root_typers(
    root_app: typer.Typer,
    *,
    mail_app: typer.Typer,
    attachment_app: typer.Typer,
    folders_app: typer.Typer,
    labels_app: typer.Typer,
    cliq_app: typer.Typer,
    crm_app: typer.Typer,
    config_app: typer.Typer,
) -> None:
    """Register the current built-in root command groups on ``root_app``."""
    register_mail_root_typers(
        root_app,
        mail_app=mail_app,
        attachment_app=attachment_app,
        folders_app=folders_app,
        labels_app=labels_app,
    )
    root_app.add_typer(cliq_app, name="cliq")
    root_app.add_typer(crm_app, name="crm")
    root_app.add_typer(config_app, name="config")
