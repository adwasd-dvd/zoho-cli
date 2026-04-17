"""CLI command wiring modules."""

from .root import (
    register_builtin_root_typers,
    register_cliq_crm_config_root_typers,
    register_mail_root_typers,
)

__all__ = [
    "register_builtin_root_typers",
    "register_cliq_crm_config_root_typers",
    "register_mail_root_typers",
]
