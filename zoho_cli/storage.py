"""Token storage with file-first default and optional OS keyring backend."""

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import keyring
import keyring.errors

from zoho_cli import config as _config

SERVICE_NAME = "zoho-cli"
logger = logging.getLogger(__name__)
REFRESH_HEALTH_KEY = "refresh_health"
TOKEN_BACKEND_ENV = "ZOHO_TOKEN_BACKEND"
TOKEN_BACKEND_FILE = "file"
TOKEN_BACKEND_KEYCHAIN = "keychain"
TOKEN_BACKEND_AUTO = "auto"
TOKEN_BACKEND_DEFAULT = TOKEN_BACKEND_FILE


def token_backend() -> str:
    """Return selected token backend.

    Defaults to file storage to avoid macOS Keychain prompts in unattended
    OpenClaw/gateway/automation processes. Set ``ZOHO_TOKEN_BACKEND=keychain``
    to opt back into the legacy keyring path.
    """
    raw = os.environ.get(TOKEN_BACKEND_ENV, TOKEN_BACKEND_DEFAULT).strip().lower()
    if raw in {TOKEN_BACKEND_FILE, TOKEN_BACKEND_KEYCHAIN, TOKEN_BACKEND_AUTO}:
        return raw
    logger.debug("Ignoring invalid %s=%r; using file backend", TOKEN_BACKEND_ENV, raw)
    return TOKEN_BACKEND_FILE


def _keychain_allowed_for_auto() -> bool:
    return sys.stdin.isatty() and sys.stderr.isatty()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: object) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _normalize_refresh_health(raw: object) -> dict:
    if not isinstance(raw, dict):
        return {}

    health = {
        "lastAttemptAt": raw.get("lastAttemptAt") or "",
        "lastSuccessAt": raw.get("lastSuccessAt") or "",
        "lastFailureAt": raw.get("lastFailureAt") or "",
        "lastFailureType": raw.get("lastFailureType") or "",
        "lastErrorCode": raw.get("lastErrorCode") or "",
        "lastHttpStatus": raw.get("lastHttpStatus"),
        "failureCount": int(raw.get("failureCount") or 0),
        "nextAllowedRefreshAt": raw.get("nextAllowedRefreshAt") or "",
        "cooldownSeconds": int(raw.get("cooldownSeconds") or 0),
        "rawDetailsStored": False,
    }
    return health


def _mutate_token(email: str, mutator) -> Optional[dict]:
    data = load_token(email)
    if not data:
        return None
    updated = mutator(dict(data))
    if updated is None:
        return None
    _store_raw(email, json.dumps(updated))
    return updated


def store_token(
    email: str,
    refresh_token: str,
    scopes: list[str],
    accounts_server: Optional[str] = None,
) -> None:
    data = {
        "refresh_token": refresh_token,
        "scopes": scopes,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if accounts_server:
        data["accounts_server"] = accounts_server
    _store_raw(email, json.dumps(data))


def store_access_token(
    email: str,
    *,
    access_token: str,
    scopes: list[str],
    api_domain: Optional[str] = None,
    token_type: Optional[str] = None,
    expires_in: Optional[int] = None,
    accounts_server: Optional[str] = None,
) -> None:
    """Cache a short-lived access token alongside the stored refresh token."""
    data = load_token(email) or {}
    if not data.get("refresh_token"):
        logger.debug(
            "Skipping access-token cache for %s because no refresh token is stored",
            email,
        )
        return

    now = _utc_now()
    ttl = int(expires_in or 3600)
    expires_at = now + timedelta(seconds=max(ttl - 120, 60))

    data.update(
        {
            "access_token": access_token,
            "access_token_cached_at": now.isoformat(),
            "access_token_expires_at": expires_at.isoformat(),
            REFRESH_HEALTH_KEY: {
                "lastAttemptAt": (data.get(REFRESH_HEALTH_KEY) or {}).get(
                    "lastAttemptAt", ""
                )
                if isinstance(data.get(REFRESH_HEALTH_KEY), dict)
                else "",
                "lastSuccessAt": now.isoformat(),
                "lastFailureAt": "",
                "lastFailureType": "",
                "lastErrorCode": "",
                "lastHttpStatus": None,
                "failureCount": 0,
                "nextAllowedRefreshAt": "",
                "cooldownSeconds": 0,
                "rawDetailsStored": False,
            },
        }
    )
    if scopes:
        data["access_token_scopes"] = scopes
    if api_domain:
        data["api_domain"] = api_domain
    if token_type:
        data["token_type"] = token_type
    if accounts_server:
        data["accounts_server"] = accounts_server

    _store_raw(email, json.dumps(data))


def load_token_refresh_health(email: str) -> dict:
    """Return sanitized OAuth refresh health metadata for an account."""
    data = load_token(email) or {}
    health = _normalize_refresh_health(data.get(REFRESH_HEALTH_KEY))
    if not health:
        return {
            "lastAttemptAt": "",
            "lastSuccessAt": "",
            "lastFailureAt": "",
            "lastFailureType": "",
            "lastErrorCode": "",
            "lastHttpStatus": None,
            "failureCount": 0,
            "nextAllowedRefreshAt": "",
            "cooldownSeconds": 0,
            "rawDetailsStored": False,
        }
    return health


def record_token_refresh_attempt(
    email: str, *, attempted_at: Optional[datetime] = None
) -> None:
    """Persist the time of an actual OAuth refresh attempt without storing secrets."""
    now = attempted_at or _utc_now()

    def _record(data: dict) -> dict:
        health = _normalize_refresh_health(data.get(REFRESH_HEALTH_KEY))
        health["lastAttemptAt"] = now.isoformat()
        health["rawDetailsStored"] = False
        data[REFRESH_HEALTH_KEY] = health
        return data

    try:
        _mutate_token(email, _record)
    except Exception as exc:
        logger.debug("token refresh attempt health write failed for %s: %s", email, exc)


def record_token_refresh_failure(
    email: str,
    *,
    failure_type: str,
    error_code: str,
    http_status: Optional[int],
    cooldown_seconds: int,
    failed_at: Optional[datetime] = None,
) -> None:
    """Persist sanitized refresh failure metadata and the next retry window."""
    now = failed_at or _utc_now()
    normalized_type = failure_type.strip().upper()
    normalized_code = error_code.strip()[:80]
    cooldown = max(int(cooldown_seconds), 0)
    next_allowed = now + timedelta(seconds=cooldown) if cooldown else None

    def _record(data: dict) -> dict:
        previous = _normalize_refresh_health(data.get(REFRESH_HEALTH_KEY))
        same_type = previous.get("lastFailureType") == normalized_type
        failure_count = int(previous.get("failureCount") or 0) + 1 if same_type else 1
        data[REFRESH_HEALTH_KEY] = {
            "lastAttemptAt": previous.get("lastAttemptAt", ""),
            "lastSuccessAt": previous.get("lastSuccessAt", ""),
            "lastFailureAt": now.isoformat(),
            "lastFailureType": normalized_type,
            "lastErrorCode": normalized_code,
            "lastHttpStatus": http_status,
            "failureCount": failure_count,
            "nextAllowedRefreshAt": next_allowed.isoformat() if next_allowed else "",
            "cooldownSeconds": cooldown,
            "rawDetailsStored": False,
        }
        return data

    try:
        _mutate_token(email, _record)
    except Exception as exc:
        logger.debug("token refresh failure health write failed for %s: %s", email, exc)


def token_refresh_wait_seconds(email: str, *, now: Optional[datetime] = None) -> int:
    """Return seconds remaining before another refresh attempt is allowed."""
    health = load_token_refresh_health(email)
    next_allowed = _parse_datetime(health.get("nextAllowedRefreshAt"))
    if not next_allowed:
        return 0
    current = now or _utc_now()
    return max(int((next_allowed - current).total_seconds()), 0)


def cached_access_token(email: str, *, min_ttl_seconds: int = 120) -> Optional[dict]:
    """Return cached access-token metadata when it is still safely usable."""
    data = load_token(email)
    if not data or not data.get("access_token"):
        return None

    expires_at_raw = data.get("access_token_expires_at")
    if not expires_at_raw:
        return None
    try:
        expires_at = datetime.fromisoformat(str(expires_at_raw))
    except ValueError:
        return None
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at <= datetime.now(timezone.utc) + timedelta(seconds=min_ttl_seconds):
        return None

    return {
        "access_token": data["access_token"],
        "scopes": data.get("access_token_scopes") or data.get("scopes") or [],
        "api_domain": data.get("api_domain"),
        "token_type": data.get("token_type"),
        "cached": True,
        "expires_at": expires_at.isoformat(),
    }


def load_token(email: str) -> Optional[dict]:
    raw = _load_raw(email)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.debug("Corrupted token data for %s", email)
        return None


def delete_token(email: str) -> None:
    if token_backend() in {TOKEN_BACKEND_KEYCHAIN, TOKEN_BACKEND_AUTO}:
        try:
            keyring.delete_password(SERVICE_NAME, email)
        except keyring.errors.PasswordDeleteError:
            pass
        except Exception as exc:
            logger.debug("keyring delete failed (%s)", exc)
    # Also remove fallback file if present
    _fallback_path(email).unlink(missing_ok=True)


# ── internal helpers ──────────────────────────────────────────────────────────


def _fallback_path(email: str) -> Path:
    safe = email.replace("@", "_at_").replace(".", "_")
    return Path(_config.config_path().parent) / f"token_{safe}.json"


def _store_raw(email: str, value: str) -> None:
    password = os.environ.get("ZOHO_TOKEN_PASSWORD")
    backend = token_backend()
    if password or backend == TOKEN_BACKEND_FILE:
        _file_store(email, value, password)
        return
    if backend == TOKEN_BACKEND_AUTO and not _keychain_allowed_for_auto():
        _file_store(email, value, password="")
        return
    if backend in {TOKEN_BACKEND_KEYCHAIN, TOKEN_BACKEND_AUTO}:
        try:
            keyring.set_password(SERVICE_NAME, email, value)
            return
        except Exception as exc:
            logger.debug("keyring write failed (%s), falling back to file", exc)
            _file_store(email, value, password="")
            return
    _file_store(email, value, password="")


def _load_raw(email: str) -> Optional[str]:
    password = os.environ.get("ZOHO_TOKEN_PASSWORD")
    backend = token_backend()
    if password or backend == TOKEN_BACKEND_FILE:
        return _file_load(email, password)
    if backend == TOKEN_BACKEND_AUTO:
        file_value = _file_load(email, password="")
        if file_value is not None:
            return file_value
        if not _keychain_allowed_for_auto():
            return None
    if backend in {TOKEN_BACKEND_KEYCHAIN, TOKEN_BACKEND_AUTO}:
        try:
            val = keyring.get_password(SERVICE_NAME, email)
            if val is not None:
                return val
        except Exception as exc:
            logger.debug("keyring read failed (%s), trying file fallback", exc)
    return _file_load(email, password="")


def _file_store(email: str, value: str, password: str) -> None:
    path = _fallback_path(email)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Simple XOR obfuscation when a password is provided (not crypto-grade)
    if password:
        import base64

        key = (password * (len(value) // len(password) + 1))[: len(value)]
        obfuscated = bytes(a ^ b for a, b in zip(value.encode(), key.encode()))
        path.write_bytes(base64.b64encode(obfuscated))
    else:
        path.write_text(value)
    path.chmod(0o600)


def _file_load(email: str, password: str) -> Optional[str]:
    path = _fallback_path(email)
    if not path.exists():
        return None
    if password:
        import base64

        raw = base64.b64decode(path.read_bytes())
        key = (password * (len(raw) // len(password) + 1))[: len(raw)]
        return bytes(a ^ b for a, b in zip(raw, key.encode())).decode()
    return path.read_text()
