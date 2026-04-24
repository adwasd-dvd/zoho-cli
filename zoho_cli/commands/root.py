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
    register_mail_primary_root_typers(
        root_app,
        mail_app=mail_app,
    )
    register_mail_support_typers_under_mail(
        mail_app,
        attachment_app=attachment_app,
        folders_app=folders_app,
        labels_app=labels_app,
    )
    register_mail_support_root_typers(
        root_app,
        attachment_app=attachment_app,
        folders_app=folders_app,
        labels_app=labels_app,
    )


def register_mail_primary_root_typers(
    root_app: typer.Typer,
    *,
    mail_app: typer.Typer,
) -> None:
    """Register the primary mail root command group on ``root_app``."""
    root_app.add_typer(mail_app, name="mail")


def register_mail_support_root_typers(
    root_app: typer.Typer,
    *,
    attachment_app: typer.Typer,
    folders_app: typer.Typer,
    labels_app: typer.Typer,
) -> None:
    """Register legacy mail support aliases at root level on ``root_app``."""
    root_app.add_typer(
        attachment_app,
        name="attachment",
        hidden=True,
    )
    root_app.add_typer(
        folders_app,
        name="folders",
        hidden=True,
    )
    root_app.add_typer(
        labels_app,
        name="labels",
        hidden=True,
    )


def register_mail_support_typers_under_mail(
    mail_app: typer.Typer,
    *,
    attachment_app: typer.Typer,
    folders_app: typer.Typer,
    labels_app: typer.Typer,
) -> None:
    """Register mail support groups under the ``mail`` module namespace."""
    mail_app.add_typer(attachment_app, name="attachment")
    mail_app.add_typer(folders_app, name="folders")
    mail_app.add_typer(labels_app, name="labels")


def register_cliq_crm_config_root_typers(
    root_app: typer.Typer,
    *,
    cliq_app: typer.Typer,
    crm_app: typer.Typer,
    config_app: typer.Typer,
) -> None:
    """Register cliq/crm/config root command groups on ``root_app``."""
    register_cliq_crm_root_typers(
        root_app,
        cliq_app=cliq_app,
        crm_app=crm_app,
    )
    register_config_root_typers(
        root_app,
        config_app=config_app,
    )


def register_cliq_root_typers(
    root_app: typer.Typer,
    *,
    cliq_app: typer.Typer,
) -> None:
    """Register cliq root command group on ``root_app``."""
    root_app.add_typer(cliq_app, name="cliq")


def register_cliq_crm_root_typers(
    root_app: typer.Typer,
    *,
    cliq_app: typer.Typer,
    crm_app: typer.Typer,
) -> None:
    """Register cliq/crm root command groups on ``root_app``."""
    register_cliq_root_typers(root_app, cliq_app=cliq_app)
    register_crm_root_typers(
        root_app,
        crm_app=crm_app,
    )


def register_crm_config_root_typers(
    root_app: typer.Typer,
    *,
    crm_app: typer.Typer,
    config_app: typer.Typer,
) -> None:
    """Register crm/config root command groups on ``root_app``."""
    register_crm_root_typers(
        root_app,
        crm_app=crm_app,
    )
    register_config_root_typers(
        root_app,
        config_app=config_app,
    )


def register_crm_root_typers(
    root_app: typer.Typer,
    *,
    crm_app: typer.Typer,
) -> None:
    """Register crm root command group on ``root_app``."""
    root_app.add_typer(crm_app, name="crm")


def register_config_root_typers(
    root_app: typer.Typer,
    *,
    config_app: typer.Typer,
) -> None:
    """Register config root command group on ``root_app``."""
    root_app.add_typer(config_app, name="config")


def register_membrane_root_typers(
    root_app: typer.Typer,
    *,
    membrane_app: typer.Typer,
) -> None:
    """Register membrane bridge root command group on ``root_app``."""
    root_app.add_typer(membrane_app, name="membrane")


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
    membrane_app: typer.Typer,
) -> None:
    """Register the current built-in root command groups on ``root_app``."""
    register_mail_root_typers(
        root_app,
        mail_app=mail_app,
        attachment_app=attachment_app,
        folders_app=folders_app,
        labels_app=labels_app,
    )
    register_cliq_crm_root_typers(
        root_app,
        cliq_app=cliq_app,
        crm_app=crm_app,
    )
    register_config_root_typers(
        root_app,
        config_app=config_app,
    )
    register_membrane_root_typers(
        root_app,
        membrane_app=membrane_app,
    )
