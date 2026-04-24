from __future__ import annotations

import pytest

from zoho_cli.cli import _require_credentials


def test_require_credentials_uses_config_values_over_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ZOHO_CLIENT_ID", "env_id")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", "env_secret")

    cid, csec = _require_credentials(
        {"client_id": "config_id", "client_secret": "config_secret"}
    )

    assert cid == "config_id"
    assert csec == "config_secret"


def test_require_credentials_falls_back_to_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZOHO_CLIENT_ID", "env_id")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", "env_secret")

    cid, csec = _require_credentials({})

    assert cid == "env_id"
    assert csec == "env_secret"


def test_require_credentials_errors_when_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("ZOHO_CLIENT_ID", raising=False)
    monkeypatch.delenv("ZOHO_CLIENT_SECRET", raising=False)

    with pytest.raises(SystemExit) as exc:
        _require_credentials({})

    assert exc.value.code == 1
    stderr = capsys.readouterr().err
    assert '"error": "missing_credentials"' in stderr
    assert (
        '"details": "client_id and client_secret must be set. Run: zoho config init"'
        in stderr
    )
