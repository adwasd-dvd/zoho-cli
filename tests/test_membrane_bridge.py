from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from zoho_cli.cli import app

runner = CliRunner()


@pytest.fixture
def mock_config(tmp_path: Path) -> Path:
    cfg = {
        "client_id": "test_id",
        "client_secret": "test_secret",
        "default_account": "test@example.com",
        "accounts": {
            "test@example.com": {
                "accountId": "ACC123",
                "membrane_connections": {
                    "zoho-cliq": "CONN_CLIQ_FROM_CONFIG",
                    "zoho-crm": "CONN_CRM_FROM_CONFIG",
                },
            }
        },
        "membrane_connections": {
            "zoho-cliq": "CONN_CLIQ_GLOBAL",
            "zoho-crm": "CONN_CRM_GLOBAL",
        },
    }
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg))
    return cfg_path


def test_membrane_doctor_reports_missing_binary(mock_config: Path) -> None:
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("zoho_cli.cli.shutil.which", lambda _name: None)

        result = runner.invoke(
            app,
            ["--config", str(mock_config), "membrane", "doctor"],
        )

    assert result.exit_code == 1
    assert "membrane_cli_missing" in result.output


def test_membrane_doctor_reports_version(mock_config: Path) -> None:
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "zoho_cli.cli.shutil.which", lambda _name: "/usr/local/bin/membrane"
        )
        monkeypatch.setattr(
            "zoho_cli.cli.subprocess.run",
            lambda *a, **kw: subprocess.CompletedProcess(
                args=a[0],
                returncode=0,
                stdout="1.2.3\n",
                stderr="",
            ),
        )

        result = runner.invoke(
            app,
            ["--config", str(mock_config), "membrane", "doctor"],
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["version"] == "1.2.3"


def test_membrane_actions_forwards_connection_and_intent(mock_config: Path) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"items": []}),
            stderr="",
        )

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "zoho_cli.cli.shutil.which", lambda _name: "/usr/local/bin/membrane"
        )
        monkeypatch.setattr("zoho_cli.cli.subprocess.run", _fake_run)

        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "membrane",
                "actions",
                "--connection-id",
                "CONN_123",
                "--intent",
                "WRITE",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"] == [
        "/usr/local/bin/membrane",
        "action",
        "list",
        "--intent=WRITE",
        "--connectionId=CONN_123",
        "--json",
    ]


def test_membrane_actions_resolves_connection_from_preset(mock_config: Path) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"items": []}),
            stderr="",
        )

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "zoho_cli.cli.shutil.which", lambda _name: "/usr/local/bin/membrane"
        )
        monkeypatch.setattr("zoho_cli.cli.subprocess.run", _fake_run)

        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "membrane",
                "actions",
                "--preset",
                "zoho-crm",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"] == [
        "/usr/local/bin/membrane",
        "action",
        "list",
        "--intent=QUERY",
        "--connectionId=CONN_CRM_FROM_CONFIG",
        "--json",
    ]


def test_membrane_run_rejects_invalid_input_json(mock_config: Path) -> None:
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "zoho_cli.cli.shutil.which", lambda _name: "/usr/local/bin/membrane"
        )

        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "membrane",
                "run",
                "list-records",
                "--connection-id",
                "CONN_123",
                "--input-json",
                "{bad-json}",
            ],
        )

    assert result.exit_code == 1
    assert "invalid_input_json" in result.output


def test_membrane_actions_requires_connection_or_preset(mock_config: Path) -> None:
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "zoho_cli.cli.shutil.which", lambda _name: "/usr/local/bin/membrane"
        )

        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "membrane",
                "actions",
                "--preset",
                "unknown-product",
            ],
        )

    assert result.exit_code == 1
    assert "missing_membrane_preset_connection" in result.output


def test_cliq_bridge_run_uses_default_preset(mock_config: Path) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "zoho_cli.cli.shutil.which", lambda _name: "/usr/local/bin/membrane"
        )
        monkeypatch.setattr("zoho_cli.cli.subprocess.run", _fake_run)

        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "cliq",
                "bridge-run",
                "post-message",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"] == [
        "/usr/local/bin/membrane",
        "action",
        "run",
        "--connectionId=CONN_CLIQ_FROM_CONFIG",
        "post-message",
        "--json",
    ]
    payload = json.loads(result.output)
    assert payload["bridge"] == "membrane"
    assert payload["preset"] == "zoho-cliq"


def test_cliq_bridge_run_rejects_unsupported_bridge(mock_config: Path) -> None:
    result = runner.invoke(
        app,
        [
            "--config",
            str(mock_config),
            "cliq",
            "bridge-run",
            "post-message",
            "--bridge",
            "native",
        ],
    )

    assert result.exit_code == 1
    assert "unsupported_bridge" in result.output


def test_crm_bridge_run_uses_default_preset(mock_config: Path) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"data": [{"id": "1"}]}),
            stderr="",
        )

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "zoho_cli.cli.shutil.which", lambda _name: "/usr/local/bin/membrane"
        )
        monkeypatch.setattr("zoho_cli.cli.subprocess.run", _fake_run)

        result = runner.invoke(
            app,
            [
                "--config",
                str(mock_config),
                "crm",
                "bridge-run",
                "list-records",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"] == [
        "/usr/local/bin/membrane",
        "action",
        "run",
        "--connectionId=CONN_CRM_FROM_CONFIG",
        "list-records",
        "--json",
    ]
    payload = json.loads(result.output)
    assert payload["bridge"] == "membrane"
    assert payload["preset"] == "zoho-crm"


def test_crm_bridge_run_rejects_unsupported_bridge(mock_config: Path) -> None:
    result = runner.invoke(
        app,
        [
            "--config",
            str(mock_config),
            "crm",
            "bridge-run",
            "list-records",
            "--bridge",
            "native",
        ],
    )

    assert result.exit_code == 1
    assert "unsupported_bridge" in result.output
