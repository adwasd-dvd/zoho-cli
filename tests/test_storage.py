from __future__ import annotations

import json
from pathlib import Path

from zoho_cli import storage


def _token_path(config_path: Path, email: str) -> Path:
    safe = email.replace("@", "_at_").replace(".", "_")
    return config_path.parent / f"token_{safe}.json"


def test_token_backend_defaults_to_file(monkeypatch) -> None:
    monkeypatch.delenv("ZOHO_TOKEN_BACKEND", raising=False)
    assert storage.token_backend() == "file"


def test_file_backend_does_not_call_keyring_by_default(
    tmp_path: Path, monkeypatch
) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("{}")
    monkeypatch.setenv("ZOHO_CONFIG", str(cfg_path))
    monkeypatch.delenv("ZOHO_TOKEN_BACKEND", raising=False)
    monkeypatch.delenv("ZOHO_TOKEN_PASSWORD", raising=False)
    monkeypatch.setattr(
        "keyring.set_password",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("keyring should not be called by default")
        ),
    )
    monkeypatch.setattr(
        "keyring.get_password",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("keyring should not be called by default")
        ),
    )

    storage.store_token(
        "bot@example.com",
        "refresh-token",
        ["ZohoCRM.modules.ALL"],
        accounts_server="https://accounts.zoho.com",
    )

    token_path = _token_path(cfg_path, "bot@example.com")
    assert token_path.exists()
    assert json.loads(token_path.read_text())["refresh_token"] == "refresh-token"
    loaded = storage.load_token("bot@example.com")
    assert loaded is not None
    assert loaded["refresh_token"] == "refresh-token"


def test_keychain_backend_is_explicit_opt_in(monkeypatch) -> None:
    monkeypatch.setenv("ZOHO_TOKEN_BACKEND", "keychain")
    monkeypatch.delenv("ZOHO_TOKEN_PASSWORD", raising=False)
    writes: list[tuple[str, str, str]] = []
    token_data = json.dumps(
        {
            "refresh_token": "keychain-refresh-token",
            "scopes": ["ZohoMail.messages.ALL"],
        }
    )
    monkeypatch.setattr(
        "keyring.set_password",
        lambda service, username, password: writes.append(
            (service, username, password)
        ),
    )
    monkeypatch.setattr("keyring.get_password", lambda _service, _username: token_data)

    storage.store_token("bot@example.com", "keychain-refresh-token", [])
    loaded = storage.load_token("bot@example.com")

    assert writes
    assert loaded is not None
    assert loaded["refresh_token"] == "keychain-refresh-token"
