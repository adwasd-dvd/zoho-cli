"""CLI command wiring modules."""

from .cliq import (
    register_cliq_app_catalog_commands,
    register_cliq_app_catalog_bridge_commands,
    register_cliq_app_commands_bridge_commands,
    register_cliq_app_commands_commands,
    register_cliq_export_commands,
    register_cliq_app_installs_bridge_commands,
    register_cliq_app_installs_commands,
    register_cliq_app_permissions_bridge_commands,
    register_cliq_app_permissions_commands,
)
from .root import (
    register_builtin_root_typers,
    register_cliq_crm_config_root_typers,
    register_cliq_crm_root_typers,
    register_cliq_root_typers,
    register_config_root_typers,
    register_crm_config_root_typers,
    register_crm_root_typers,
    register_mail_primary_root_typers,
    register_mail_root_typers,
    register_mail_support_root_typers,
    register_membrane_root_typers,
)

__all__ = [
    "register_builtin_root_typers",
    "register_cliq_app_catalog_commands",
    "register_cliq_app_catalog_bridge_commands",
    "register_cliq_app_commands_bridge_commands",
    "register_cliq_app_commands_commands",
    "register_cliq_export_commands",
    "register_cliq_app_installs_bridge_commands",
    "register_cliq_app_installs_commands",
    "register_cliq_app_permissions_bridge_commands",
    "register_cliq_app_permissions_commands",
    "register_cliq_crm_config_root_typers",
    "register_cliq_crm_root_typers",
    "register_cliq_root_typers",
    "register_config_root_typers",
    "register_crm_config_root_typers",
    "register_crm_root_typers",
    "register_mail_primary_root_typers",
    "register_mail_root_typers",
    "register_mail_support_root_typers",
    "register_membrane_root_typers",
]
