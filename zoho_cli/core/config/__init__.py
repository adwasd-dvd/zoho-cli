"""Core config handling: paths, regions, and environment overrides."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from platformdirs import user_config_dir

APP_NAME = "zoho-cli"


def config_path(override: Optional[str] = None) -> Path:
    """Get the config file path."""
    if override:
        return Path(override)
    env = os.environ.get("ZOHO_CONFIG")
    if env:
        return Path(env)
    return Path(user_config_dir(APP_NAME)) / "config.json"


def load(override: Optional[str] = None) -> dict[str, Any]:
    """Load config from file."""
    p = config_path(override)
    if not p.exists():
        return {}
    with open(p) as f:
        return json.load(f)


def save(data: dict[str, Any], override: Optional[str] = None) -> None:
    """Save config to file."""
    p = config_path(override)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        json.dump(data, f, indent=2)


def default_account(cfg: dict[str, Any]) -> Optional[str]:
    """Get the default account from config or env."""
    return os.environ.get("ZOHO_ACCOUNT") or cfg.get("default_account")


def mail_base_url() -> str:
    """Get Mail API base URL from env or default."""
    return os.environ.get("ZOHO_BASE_URL", "https://mail.zoho.com/api")


def accounts_base_url() -> str:
    """Get Accounts OAuth base URL from env or default."""
    return os.environ.get("ZOHO_ACCOUNTS_BASE_URL", "https://accounts.zoho.com")


# Region → (accounts_base_url, mail_base_url)
REGIONS: dict[str, tuple[str, str]] = {
    "com": ("https://accounts.zoho.com", "https://mail.zoho.com/api"),
    "eu": ("https://accounts.zoho.eu", "https://mail.zoho.eu/api"),
    "in": ("https://accounts.zoho.in", "https://mail.zoho.in/api"),
    "au": ("https://accounts.zoho.com.au", "https://mail.zoho.com.au/api"),
    "jp": ("https://accounts.zoho.jp", "https://mail.zoho.jp/api"),
    "ca": ("https://accounts.zohocloud.ca", "https://mail.zohocloud.ca/api"),
}


def infer_accounts_server(cfg: dict[str, Any]) -> Optional[str]:
    """Infer the regional accounts server from config."""
    env = os.environ.get("ZOHO_ACCOUNTS_BASE_URL")
    if env:
        return env
    if cfg.get("accounts_server"):
        return cfg["accounts_server"]
    for acc in cfg.get("accounts", {}).values():
        if acc.get("accounts_server"):
            return acc["accounts_server"]
    return None


__all__ = [
    "config_path",
    "load",
    "save",
    "default_account",
    "mail_base_url",
    "accounts_base_url",
    "REGIONS",
    "infer_accounts_server",
]
