from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from zoho_cli import cliq as cliq_client
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


def test_cliq_bridge_run_preserves_watch_intake_input_json(mock_config: Path) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "triggerMode": "web-notification-first",
            "pollFallback": {"mode": "adaptive", "transport": "api-poll"},
            "consume": {"ackAction": "read-ack-latest", "ackRequired": True},
        },
    }

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
                "watch-loop",
                "--input-json",
                json.dumps(watch_payload),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][6] == "--input"
    assert json.loads(seen["command"][7]) == watch_payload


def test_cliq_bridge_run_watch_file_forwards_watch_payload_and_action_hint(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "triggerMode": "web-notification-first",
            "consume": {
                "ackAction": "read-ack-latest",
                "ackRequired": True,
                "actionId": "watch-loop",
            },
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "defaultAction": "notify-mail",
                "handoff": {
                    "contractId": "cliq-195-escalation-handoff-v1",
                    "payloadTemplate": {
                        "target": {
                            "kind": "external-contact",
                            "channel": "mail",
                            "defaultAction": "notify-mail",
                        },
                        "recipient": "",
                        "summary": "",
                        "reason": "",
                    },
                    "envelopeHints": {
                        "templateRoot": "payloadTemplate",
                        "targetPath": "payloadTemplate.target",
                        "fieldMap": {
                            "to": "payloadTemplate.recipient",
                            "subject": "payloadTemplate.summary",
                            "body": "payloadTemplate.reason",
                        },
                    },
                    "envelopeDefaults": {
                        "target": {
                            "kind": "external-contact",
                            "channel": "mail",
                            "defaultAction": "notify-mail",
                        },
                        "to": "",
                        "subject": "",
                        "body": "",
                    },
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop"
    assert seen["command"][6] == "--input"
    assert json.loads(seen["command"][7]) == {
        "watchPayload": watch_payload,
        "escalationEnvelope": {
            "target": {
                "kind": "external-contact",
                "channel": "mail",
                "defaultAction": "notify-mail",
            },
            "to": "",
            "subject": "",
            "body": "",
        },
        "escalationEnvelopeMetadata": {
            "source": "nested-fallback",
            "sourcePath": "operatorWorkflow.externalEscalation.handoff",
            "fromTopLevelAlias": False,
            "fromNestedFallback": True,
            "usedFieldFallback": True,
            "fieldSources": {
                "target": {
                    "source": "nested-envelope-defaults",
                    "sourcePath": (
                        "operatorWorkflow.externalEscalation.handoff."
                        "envelopeDefaults.target"
                    ),
                    "fromTopLevelAlias": False,
                    "fromNestedFallback": True,
                    "usedFallback": True,
                },
                "to": {
                    "source": "nested-envelope-defaults",
                    "sourcePath": (
                        "operatorWorkflow.externalEscalation.handoff."
                        "envelopeDefaults.to"
                    ),
                    "fromTopLevelAlias": False,
                    "fromNestedFallback": True,
                    "usedFallback": True,
                },
                "subject": {
                    "source": "nested-envelope-defaults",
                    "sourcePath": (
                        "operatorWorkflow.externalEscalation.handoff."
                        "envelopeDefaults.subject"
                    ),
                    "fromTopLevelAlias": False,
                    "fromNestedFallback": True,
                    "usedFallback": True,
                },
                "body": {
                    "source": "nested-envelope-defaults",
                    "sourcePath": (
                        "operatorWorkflow.externalEscalation.handoff."
                        "envelopeDefaults.body"
                    ),
                    "fromTopLevelAlias": False,
                    "fromNestedFallback": True,
                    "usedFallback": True,
                },
            },
        },
        "actionSource": "watch-loop-hint",
        "actionSourcePath": "watchIntake.consume.actionId",
        "actionSourceMetadata": {
            "source": "watch-loop-hint",
            "sourcePath": "watchIntake.consume.actionId",
            "fromWatchLoopHint": True,
            "fromEscalationHint": False,
            "fromExplicitOverride": False,
        },
        "watchIntake": watch_payload["watchIntake"],
        "operatorWorkflow": watch_payload["operatorWorkflow"],
    }
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.actionId"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }
    assert payload["watchIntake"]["consume"]["ackAction"] == "read-ack-latest"
    assert payload["operatorWorkflow"]["packageId"] == "cliq-195"
    assert payload["operatorWorkflow"]["externalEscalation"]["handoff"][
        "payloadTemplate"
    ] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "recipient": "",
        "summary": "",
        "reason": "",
    }
    assert payload["operatorWorkflow"]["externalEscalation"]["handoff"][
        "envelopeHints"
    ] == {
        "templateRoot": "payloadTemplate",
        "targetPath": "payloadTemplate.target",
        "fieldMap": {
            "to": "payloadTemplate.recipient",
            "subject": "payloadTemplate.summary",
            "body": "payloadTemplate.reason",
        },
    }
    assert payload["operatorWorkflow"]["externalEscalation"]["handoff"][
        "envelopeDefaults"
    ] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "to": "",
        "subject": "",
        "body": "",
    }
    assert payload["escalationEnvelope"] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "to": "",
        "subject": "",
        "body": "",
    }


def test_cliq_bridge_run_watch_file_status_flow_passthrough_enabled(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--status-flow",
            ],
        )

    assert result.exit_code == 0, result.output
    forwarded_input = json.loads(seen["command"][7])
    assert forwarded_input["statusFlow"] == {"enabled": True}

    payload = json.loads(result.output)
    assert payload["statusFlow"] == {"enabled": True}


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_action_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionID": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.actionID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_action_pascal_head_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "ActionId": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.ActionId"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.ActionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_action_pascal_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "ActionID": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.ActionID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.ActionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_action_pascal_snake_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "Action_id": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.Action_id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.Action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_action_pascal_upper_snake_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "Action_ID": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.Action_ID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.Action_ID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_action_pascal_kebab_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "Action-ID": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.Action-ID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.Action-ID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_action_pascal_kebab_mixed_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "Action-Id": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.Action-Id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.Action-Id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_action_pascal_kebab_lower_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "Action-id": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.Action-id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.Action-id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_action_pascal_lowercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "Actionid": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.Actionid"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.Actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_action_uppercase_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "ACTIONID": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.ACTIONID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.ACTIONID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_action_uppercase_snake_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "ACTION_ID": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.ACTION_ID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.ACTION_ID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_action_uppercase_kebab_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "ACTION-ID": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.ACTION-ID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.ACTION-ID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_action_lowercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionid": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.actionid"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_action_camel_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.actionId"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_action_snake_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "action_id": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.action_id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_action_kebab_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "action-id": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.action-id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.action-id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_action_kebab_mixed_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "action-Id": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.action-Id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.action-Id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_bridge_action_kebab_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "bridge": {
                "bridge-action-id": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.bridge.bridge-action-id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.bridge.bridge-action-id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_bridge_action_kebab_snake_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "bridge": {
                "bridge-action_id": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.bridge.bridge-action_id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.bridge.bridge-action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_bridge_action_kebab_compact_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "bridge": {
                "bridge-actionid": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.bridge.bridge-actionid"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.bridge.bridge-actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_bridge_action_kebab_mixed_case_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "bridge": {
                "bridge-actionId": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.bridge.bridge-actionId"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.bridge.bridge-actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_bridge_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "bridge": {
                "bridge-actionID": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.bridge.bridge-actionID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.bridge.bridge-actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_bridge_action_uppercase_tail_camel_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "bridge": {
                "bridgeActionID": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.bridge.bridgeActionID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.bridge.bridgeActionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_bridge_action_lowercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "bridge": {
                "bridgeActionid": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.bridge.bridgeActionid"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.bridge.bridgeActionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_bridge_action_snake_compact_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "bridge": {
                "bridge_actionid": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.bridge.bridge_actionid"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.bridge.bridge_actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_bridge_action_snake_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "bridge": {
                "bridge_actionID": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.bridge.bridge_actionID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.bridge.bridge_actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "bridgeActionId": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.bridgeActionId"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.bridgeActionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "bridgeActionID": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.bridgeActionID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.bridgeActionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_camel_snake_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "bridgeAction_id": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.bridgeAction_id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.bridgeAction_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_camel_snake_upper_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "bridgeAction_Id": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.bridgeAction_Id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.bridgeAction_Id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_pascal_head_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "BridgeActionId": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.BridgeActionId"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.BridgeActionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_pascal_head_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "BridgeActionID": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.BridgeActionID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.BridgeActionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_pascal_head_lowercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "BridgeActionid": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.BridgeActionid"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.BridgeActionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_pascal_head_snake_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "BridgeAction_id": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.BridgeAction_id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.BridgeAction_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_pascal_head_snake_upper_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "BridgeAction_Id": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.BridgeAction_Id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.BridgeAction_Id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_pascal_head_snake_mid_upper_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "BridgeAction_ID": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.BridgeAction_ID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.BridgeAction_ID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_pascal_head_kebab_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "BridgeAction-id": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.BridgeAction-id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.BridgeAction-id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_pascal_head_kebab_tail_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "BridgeAction-ID": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.BridgeAction-ID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.BridgeAction-ID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_pascal_head_kebab_tail_upper_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "BridgeAction-Id": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.BridgeAction-Id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.BridgeAction-Id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_pascal_head_snake_mid_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "Bridge_ActionId": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.Bridge_ActionId"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.Bridge_ActionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_pascal_head_snake_mid_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "Bridge_ActionID": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.Bridge_ActionID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.Bridge_ActionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_pascal_head_snake_mid_upper_snake_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "Bridge_Action_ID": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.Bridge_Action_ID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.Bridge_Action_ID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_pascal_head_snake_mid_snake_title_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "Bridge_Action_Id": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.Bridge_Action_Id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.Bridge_Action_Id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_pascal_head_snake_mid_lowercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "Bridge_Actionid": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.Bridge_Actionid"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.Bridge_Actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_pascal_head_snake_mid_snake_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "Bridge_Action_id": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.Bridge_Action_id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.Bridge_Action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_pascal_head_snake_mid_kebab_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "Bridge_Action-id": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.Bridge_Action-id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.Bridge_Action-id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_pascal_head_snake_mid_kebab_tail_upper_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "Bridge_Action-Id": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.Bridge_Action-Id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.Bridge_Action-Id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_pascal_head_snake_mid_kebab_tail_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "Bridge_Action-ID": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.Bridge_Action-ID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.Bridge_Action-ID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_kebab_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "bridge-action-id": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.bridge-action-id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.bridge-action-id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_lowercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "bridgeActionid": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.bridgeActionid"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.bridgeActionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_kebab_snake_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "bridge-action_id": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.bridge-action_id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.bridge-action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_kebab_compact_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "bridge-actionid": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.bridge-actionid"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.bridge-actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_snake_compact_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "bridge_actionid": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.bridge_actionid"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.bridge_actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_snake_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "bridge_actionID": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.bridge_actionID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.bridge_actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_kebab_mixed_case_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "bridge-actionId": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.bridge-actionId"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.bridge-actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_camel_kebab_mixed_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "bridgeAction-Id": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.bridgeAction-Id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.bridgeAction-Id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_camel_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "bridgeAction-ID": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.bridgeAction-ID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.bridgeAction-ID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_camel_kebab_lower_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "bridgeAction-id": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.bridgeAction-id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.bridgeAction-id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_kebab_pascal_camel_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "bridge-ActionId": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.bridge-ActionId"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.bridge-ActionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_kebab_pascal_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "bridge-ActionID": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.bridge-ActionID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.bridge-ActionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_kebab_pascal_lowercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "bridge-Actionid": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.bridge-Actionid"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.bridge-Actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_kebab_pascal_snake_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "bridge-Action_id": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.bridge-Action_id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.bridge-Action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_kebab_pascal_snake_upper_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "bridge-Action_Id": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.bridge-Action_Id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.bridge-Action_Id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "bridge-actionID": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.bridge-actionID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.bridge-actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_pascal_kebab_camel_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "Bridge-ActionId": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.Bridge-ActionId"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.Bridge-ActionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_pascal_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "Bridge-ActionID": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.Bridge-ActionID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.Bridge-ActionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_pascal_kebab_lowercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "Bridge-Actionid": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.Bridge-Actionid"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.Bridge-Actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_pascal_kebab_snake_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "Bridge-Action_id": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.Bridge-Action_id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.Bridge-Action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_watch_intake_consume_bridge_action_pascal_kebab_snake_upper_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "Bridge-Action_Id": "watch-loop-route",
            }
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchIntake.consume.Bridge-Action_Id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchIntake.consume.Bridge-Action_Id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_watch_payload_bridge_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "bridgeActionId": "watch-loop-route",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.bridgeActionId"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.bridgeActionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_watch_payload_bridge_action_kebab_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "bridge-action-id": "watch-loop-route",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.bridge-action-id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.bridge-action-id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_watch_payload_bridge_action_kebab_snake_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "bridge-action_id": "watch-loop-route",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.bridge-action_id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.bridge-action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_watch_payload_bridge_action_kebab_lowercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "bridge-actionid": "watch-loop-route",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.bridge-actionid"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.bridge-actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_watch_payload_bridge_action_kebab_mixed_case_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "bridge-actionId": "watch-loop-route",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.bridge-actionId"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.bridge-actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_watch_payload_bridge_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "bridge-actionID": "watch-loop-route",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.bridge-actionID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.bridge-actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_watch_payload_bridge_action_snake_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "bridge_action_id": "watch-loop-route",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.bridge_action_id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.bridge_action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_watch_payload_bridge_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "bridgeAction_id": "watch-loop-route",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.bridgeAction_id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.bridgeAction_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_watch_payload_bridge_action_snake_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "bridge_actionId": "watch-loop-route",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.bridge_actionId"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.bridge_actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_watch_payload_bridge_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "bridgeActionid": "watch-loop-route",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.bridgeActionid"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.bridgeActionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_watch_payload_bridge_action_snake_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "bridge_actionid": "watch-loop-route",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.bridge_actionid"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.bridge_actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_watch_payload_bridge_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "bridgeActionID": "watch-loop-route",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.bridgeActionID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.bridgeActionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_watch_payload_bridge_action_snake_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "bridge_actionID": "watch-loop-route",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.bridge_actionID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.bridge_actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_accepts_snake_case_watch_intake_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watch_intake": {
            "triggerMode": "web-notification-first",
            "consume": {
                "ackAction": "read-ack-latest",
                "ackRequired": True,
                "action_id": "watch-loop",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop"
    assert seen["command"][6] == "--input"
    assert (
        json.loads(seen["command"][7])["watchIntake"] == watch_payload["watch_intake"]
    )
    assert json.loads(seen["command"][7])["actionSourcePath"] == (
        "watch_intake.consume.action_id"
    )

    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watch_intake.consume.action_id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watch_intake.consume.action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }
    assert payload["watchIntake"] == watch_payload["watch_intake"]


def test_cliq_bridge_run_watch_file_prefers_top_level_escalation_envelope(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "escalationEnvelope": {
            "to": "ops@happy-distro.co.uk",
        },
        "watchIntake": {"consume": {"actionId": "watch-loop"}},
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "handoff": {
                    "envelopeDefaults": {
                        "target": {
                            "kind": "external-contact",
                            "channel": "mail",
                            "defaultAction": "notify-mail",
                        },
                        "to": "fallback@happy-distro.co.uk",
                        "subject": "Fallback subject",
                        "body": "Fallback body",
                    }
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop"
    payload = json.loads(result.output)
    expected_envelope = {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "to": "ops@happy-distro.co.uk",
        "subject": "Fallback subject",
        "body": "Fallback body",
    }
    assert json.loads(seen["command"][7])["escalationEnvelope"] == expected_envelope
    assert payload["escalationEnvelope"] == expected_envelope
    assert payload["escalationEnvelopeMetadata"] == {
        "source": "mixed",
        "sourcePath": "mixed",
        "fromTopLevelAlias": True,
        "fromNestedFallback": True,
        "usedFieldFallback": True,
        "fieldSources": {
            "target": {
                "source": "nested-envelope-defaults",
                "sourcePath": (
                    "operatorWorkflow.externalEscalation.handoff."
                    "envelopeDefaults.target"
                ),
                "fromTopLevelAlias": False,
                "fromNestedFallback": True,
                "usedFallback": True,
            },
            "to": {
                "source": "top-level-alias",
                "sourcePath": "escalationEnvelope.to",
                "fromTopLevelAlias": True,
                "fromNestedFallback": False,
                "usedFallback": False,
            },
            "subject": {
                "source": "nested-envelope-defaults",
                "sourcePath": (
                    "operatorWorkflow.externalEscalation.handoff."
                    "envelopeDefaults.subject"
                ),
                "fromTopLevelAlias": False,
                "fromNestedFallback": True,
                "usedFallback": True,
            },
            "body": {
                "source": "nested-envelope-defaults",
                "sourcePath": (
                    "operatorWorkflow.externalEscalation.handoff.envelopeDefaults.body"
                ),
                "fromTopLevelAlias": False,
                "fromNestedFallback": True,
                "usedFallback": True,
            },
        },
    }


def test_cliq_bridge_run_watch_file_accepts_snake_case_escalation_envelope_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "escalation_envelope": {
            "to": "ops@happy-distro.co.uk",
        },
        "watchIntake": {"consume": {"actionId": "watch-loop"}},
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "handoff": {
                    "envelopeDefaults": {
                        "target": {
                            "kind": "external-contact",
                            "channel": "mail",
                            "defaultAction": "notify-mail",
                        },
                        "to": "fallback@happy-distro.co.uk",
                        "subject": "Fallback subject",
                        "body": "Fallback body",
                    }
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop"
    payload = json.loads(result.output)
    assert payload["escalationEnvelope"]["to"] == "ops@happy-distro.co.uk"
    assert payload["escalationEnvelopeMetadata"]["fieldSources"]["to"] == {
        "source": "top-level-alias",
        "sourcePath": "escalation_envelope.to",
        "fromTopLevelAlias": True,
        "fromNestedFallback": False,
        "usedFallback": False,
    }


def test_cliq_bridge_run_watch_file_accepts_payload_template_field_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "escalation_envelope": {
            "recipient": "ops@happy-distro.co.uk",
            "summary": "Escalation subject",
            "reason": "Escalation body",
        },
        "watchIntake": {"consume": {"actionId": "watch-loop"}},
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "handoff": {
                    "envelopeDefaults": {
                        "target": {
                            "kind": "external-contact",
                            "channel": "mail",
                            "defaultAction": "notify-mail",
                        },
                        "to": "fallback@happy-distro.co.uk",
                        "subject": "Fallback subject",
                        "body": "Fallback body",
                    }
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert json.loads(seen["command"][7])["escalationEnvelope"] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "to": "ops@happy-distro.co.uk",
        "subject": "Escalation subject",
        "body": "Escalation body",
    }
    assert payload["escalationEnvelopeMetadata"]["fieldSources"] == {
        "target": {
            "source": "nested-envelope-defaults",
            "sourcePath": (
                "operatorWorkflow.externalEscalation.handoff.envelopeDefaults.target"
            ),
            "fromTopLevelAlias": False,
            "fromNestedFallback": True,
            "usedFallback": True,
        },
        "to": {
            "source": "top-level-alias",
            "sourcePath": "escalation_envelope.recipient",
            "fromTopLevelAlias": True,
            "fromNestedFallback": False,
            "usedFallback": False,
        },
        "subject": {
            "source": "top-level-alias",
            "sourcePath": "escalation_envelope.summary",
            "fromTopLevelAlias": True,
            "fromNestedFallback": False,
            "usedFallback": False,
        },
        "body": {
            "source": "top-level-alias",
            "sourcePath": "escalation_envelope.reason",
            "fromTopLevelAlias": True,
            "fromNestedFallback": False,
            "usedFallback": False,
        },
    }


def test_cliq_bridge_run_watch_file_accepts_snake_case_nested_envelope_defaults_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "escalation_envelope": {
            "to": "ops@happy-distro.co.uk",
        },
        "watchIntake": {"consume": {"actionId": "watch-loop"}},
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "handoff": {
                    "envelope_defaults": {
                        "target": {
                            "kind": "external-contact",
                            "channel": "mail",
                            "defaultAction": "notify-mail",
                        },
                        "to": "fallback@happy-distro.co.uk",
                        "subject": "Fallback subject",
                        "body": "Fallback body",
                    }
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["escalationEnvelope"]["subject"] == "Fallback subject"
    assert payload["escalationEnvelopeMetadata"]["fieldSources"]["target"] == {
        "source": "nested-envelope-defaults",
        "sourcePath": (
            "operatorWorkflow.external_escalation.handoff.envelope_defaults.target"
        ),
        "fromTopLevelAlias": False,
        "fromNestedFallback": True,
        "usedFallback": True,
    }


def test_cliq_bridge_run_watch_file_accepts_snake_case_operator_workflow_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "escalation_envelope": {
            "to": "ops@happy-distro.co.uk",
        },
        "watchIntake": {"consume": {"actionId": "watch-loop"}},
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "handoff": {
                    "envelope_defaults": {
                        "target": {
                            "kind": "external-contact",
                            "channel": "mail",
                            "defaultAction": "notify-mail",
                        },
                        "to": "fallback@happy-distro.co.uk",
                        "subject": "Fallback subject",
                        "body": "Fallback body",
                    }
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["operatorWorkflow"] == watch_payload["operator_workflow"]
    assert payload["escalationEnvelopeMetadata"]["fieldSources"]["target"] == {
        "source": "nested-envelope-defaults",
        "sourcePath": (
            "operator_workflow.external_escalation.handoff.envelope_defaults.target"
        ),
        "fromTopLevelAlias": False,
        "fromNestedFallback": True,
        "usedFallback": True,
    }


def test_cliq_bridge_run_watch_file_preserves_nested_envelope_defaults_alias_source_paths(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {"consume": {"actionId": "watch-loop"}},
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "handoff": {
                    "envelope_defaults": {
                        "target": {
                            "kind": "external-contact",
                            "channel": "mail",
                            "defaultAction": "notify-mail",
                        },
                        "recipient": "fallback@happy-distro.co.uk",
                        "summary": "Fallback subject",
                        "reason": "Fallback body",
                    }
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["escalationEnvelope"] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "to": "fallback@happy-distro.co.uk",
        "subject": "Fallback subject",
        "body": "Fallback body",
    }
    assert (
        payload["escalationEnvelopeMetadata"]["fieldSources"]["to"]["sourcePath"]
        == "operator_workflow.external_escalation.handoff.envelope_defaults.recipient"
    )
    assert (
        payload["escalationEnvelopeMetadata"]["fieldSources"]["subject"]["sourcePath"]
        == "operator_workflow.external_escalation.handoff.envelope_defaults.summary"
    )
    assert (
        payload["escalationEnvelopeMetadata"]["fieldSources"]["body"]["sourcePath"]
        == "operator_workflow.external_escalation.handoff.envelope_defaults.reason"
    )


def test_cliq_bridge_run_watch_file_infers_action_from_watch_context_seed(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = cliq_client.ZohoCliqClient.build_watch_context_seed(
        [
            {"id": "M2", "text": "latest"},
            {"id": "M1", "text": "older"},
        ],
        since_message_id="M1",
        max_messages=5,
    )
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop"
    assert payload["operatorWorkflow"]["externalEscalation"]["handoff"][
        "payloadTemplate"
    ] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "recipient": "",
        "summary": "",
        "reason": "",
    }
    assert payload["operatorWorkflow"]["externalEscalation"]["handoff"][
        "envelopeHints"
    ] == {
        "templateRoot": "payloadTemplate",
        "targetPath": "payloadTemplate.target",
        "fieldMap": {
            "to": "payloadTemplate.recipient",
            "subject": "payloadTemplate.summary",
            "body": "payloadTemplate.reason",
        },
    }
    assert payload["operatorWorkflow"]["externalEscalation"]["handoff"][
        "envelopeDefaults"
    ] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "to": "",
        "subject": "",
        "body": "",
    }
    assert payload["escalationEnvelope"] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "to": "",
        "subject": "",
        "body": "",
    }


def test_cliq_bridge_run_watch_file_infers_action_from_escalation_hint(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "defaultAction": "notify-mail",
                "actionHint": {
                    "watchActAction": "read-ack-latest",
                    "bridgeActionId": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.bridgeActionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.bridgeActionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_escalation_hint(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "action_hint": {
                    "bridge_action_id": "notify-mail",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.bridge_action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.bridge_action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_escalation_hint_default_action(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "action_hint": {
                    "default_action": "notify-mail",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.default_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.default_action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_escalation_hint_top_level_action(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "action_hint": {
                    "action": "notify-mail",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_escalation_hint_top_level_action(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "actionHint": {
                    "action": "notify-mail",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_action_fallback(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert payload["actionSourcePath"] == "operatorWorkflow.externalEscalation.action"
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_watch_payload_action_fallback(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "action": "notify-mail",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.action"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_default_action_fallback(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "defaultAction": "notify-mail",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.defaultAction"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.defaultAction",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_default_action_snake_fallback(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "default_action": "notify-mail",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.default_action"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.default_action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_default_action_kebab_fallback(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "default-action": "notify-mail",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.default-action"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.default-action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_default_action_kebab_id_fallback(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "default-action-id": "notify-mail",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.default-action-id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.default-action-id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_default_action_kebab_snake_id_fallback(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "default-action_id": "notify-mail",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.default-action_id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.default-action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_default_action_id_fallback(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "defaultActionId": "notify-mail",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.defaultActionId"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.defaultActionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_default_action_snake_id_fallback(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "default_action_id": "notify-mail",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.default_action_id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.default_action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_default_action_uppercase_tail_id_fallback(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "defaultActionID": "notify-mail",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.defaultActionID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.defaultActionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_default_action_mixed_case_id_fallback(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "defaultAction_id": "notify-mail",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.defaultAction_id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.defaultAction_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_default_action_snake_mixed_case_id_fallback(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "default_actionId": "notify-mail",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.default_actionId"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.default_actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_default_action_snake_uppercase_tail_id_fallback(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "default_actionID": "notify-mail",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.default_actionID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.default_actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_default_action_lowercase_tail_id_fallback(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "defaultActionid": "notify-mail",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.defaultActionid"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.defaultActionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_default_action_snake_lowercase_tail_id_fallback(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "default_actionid": "notify-mail",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.default_actionid"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.default_actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_action_id_fallback(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "actionId": "notify-mail",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.actionId"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_action_snake_id_fallback(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "action_id": "notify-mail",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.action_id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_action_uppercase_tail_id_fallback(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "actionID": "notify-mail",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.actionID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_top_level_action_lowercase_tail_id_fallback(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "actionid": "notify-mail",
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "watchPayload.actionid"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "watchPayload.actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_top_level_action_fallback(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "action": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert payload["actionSourcePath"] == "operator_workflow.external_escalation.action"
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_internal_loop_hint(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "action_hint": {
                    "bridge_action_id": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internal_loop.action_hint.bridge_action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internal_loop.action_hint.bridge_action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_internal_loop_hint_action_id(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "action_hint": {
                    "action_id": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internal_loop.action_hint.action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internal_loop.action_hint.action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_internal_loop_hint_top_level_action(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "action_hint": {
                    "action": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internal_loop.action_hint.action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internal_loop.action_hint.action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_internal_loop_hint_top_level_action(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "actionHint": {
                    "action": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.internalLoop.actionHint.action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internalLoop.actionHint.action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_internal_loop_hint_action_id(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "actionHint": {
                    "actionId": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internalLoop.actionHint.actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internalLoop.actionHint.actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_internal_loop_hint_bridge_action_id(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "actionHint": {
                    "bridgeActionId": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internalLoop.actionHint.bridgeActionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internalLoop.actionHint.bridgeActionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_internal_loop_top_level_bridge_action_id(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "bridgeActionId": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operatorWorkflow.internalLoop.bridgeActionId"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internalLoop.bridgeActionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_internal_loop_top_level_action_id(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "actionId": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operatorWorkflow.internalLoop.actionId"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internalLoop.actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_internal_loop_top_level_bridge_action_id(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "bridge_action_id": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internal_loop.bridge_action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internal_loop.bridge_action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_internal_loop_top_level_action_id(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "action_id": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operator_workflow.internal_loop.action_id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internal_loop.action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_top_level_bridge_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "bridgeActionID": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.internal_loop.bridgeActionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.bridgeActionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_top_level_bridge_action_snake_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "bridge_actionID": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.internalLoop.bridge_actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.bridge_actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_top_level_bridge_action_snake_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "bridge_actionID": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.internal_loop.bridge_actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.bridge_actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_top_level_bridge_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "bridgeActionID": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.internalLoop.bridgeActionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.bridgeActionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_top_level_bridge_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "bridgeAction_id": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.internal_loop.bridgeAction_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.bridgeAction_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_top_level_bridge_action_snake_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "bridge_actionId": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.internalLoop.bridge_actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.bridge_actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_top_level_bridge_action_snake_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "bridge_actionId": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.internal_loop.bridge_actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.bridge_actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_top_level_bridge_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "bridgeAction_id": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.internalLoop.bridgeAction_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.bridgeAction_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_internal_loop_top_level_default_action(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "defaultAction": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operatorWorkflow.internalLoop.defaultAction"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internalLoop.defaultAction",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_internal_loop_top_level_default_action(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "default_action": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.internal_loop.default_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internal_loop.default_action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_top_level_default_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "defaultAction": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operatorWorkflow.internal_loop.defaultAction"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.defaultAction",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_top_level_default_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "default_action": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.internalLoop.default_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.default_action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_top_level_default_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "defaultAction_id": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.internal_loop.defaultAction_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.defaultAction_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_top_level_default_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "default_actionId": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.internalLoop.default_actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.default_actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_top_level_default_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "defaultActionID": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.internal_loop.defaultActionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.defaultActionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_top_level_default_action_snake_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "default_actionID": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.internalLoop.default_actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.default_actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_top_level_default_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "defaultActionid": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.internal_loop.defaultActionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.defaultActionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_top_level_default_action_snake_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "default_actionid": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.internalLoop.default_actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.default_actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_top_level_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "action": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operatorWorkflow.internal_loop.action"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_top_level_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "action": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operator_workflow.internalLoop.action"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_top_level_bridge_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "bridgeActionId": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.internal_loop.bridgeActionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.bridgeActionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_top_level_bridge_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "bridge_action_id": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.internalLoop.bridge_action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.bridge_action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_top_level_bridge_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "bridge-action-id": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.internal_loop.bridge-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.bridge-action-id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_top_level_bridge_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "bridge-action-id": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.internalLoop.bridge-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.bridge-action-id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_top_level_bridge_action_id_snake_case_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "bridge_action_id": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.internal_loop.bridge_action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.bridge_action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_top_level_bridge_action_id_camel_case_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "bridgeActionId": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.internalLoop.bridgeActionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.bridgeActionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_top_level_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "actionId": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operatorWorkflow.internal_loop.actionId"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_top_level_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "action_id": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operator_workflow.internalLoop.action_id"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_top_level_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "actionID": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operatorWorkflow.internal_loop.actionID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_top_level_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "actionID": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operator_workflow.internalLoop.actionID"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_top_level_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "actionid": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operatorWorkflow.internal_loop.actionid"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_top_level_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "actionid": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert payload["actionSourcePath"] == "operator_workflow.internalLoop.actionid"
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_top_level_watch_act_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "watchActAction": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.internal_loop.watchActAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.watchActAction",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_top_level_watch_act_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "watch_act_action": "watch-loop-route",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.internalLoop.watch_act_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.watch_act_action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_internal_loop_hint_default_action(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "action_hint": {
                    "default_action": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internal_loop.action_hint.default_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internal_loop.action_hint.default_action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_internal_loop_hint_default_action(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "actionHint": {
                    "defaultAction": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internalLoop.actionHint.defaultAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internalLoop.actionHint.defaultAction",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_hint_default_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "action_hint": {
                    "defaultAction": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internalLoop.action_hint.defaultAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internalLoop.action_hint.defaultAction",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_hint_default_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "actionHint": {
                    "default_action": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internal_loop.actionHint.default_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internal_loop.actionHint.default_action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_hint_default_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "actionHint": {
                    "defaultAction_id": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internal_loop.actionHint.defaultAction_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionHint.defaultAction_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_hint_default_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "action_hint": {
                    "default_actionId": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.default_actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.default_actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_hint_default_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "actionHint": {
                    "defaultActionID": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internal_loop.actionHint.defaultActionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionHint.defaultActionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_hint_default_action_snake_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "action_hint": {
                    "default_actionID": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.default_actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.default_actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_hint_default_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "actionHint": {
                    "defaultActionid": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internal_loop.actionHint.defaultActionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionHint.defaultActionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_hint_default_action_snake_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "action_hint": {
                    "default_actionid": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.default_actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.default_actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_camel_case_internal_loop_hint_snake_default_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "action_hint": {
                    "defaultActionid": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internalLoop.action_hint.defaultActionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internalLoop.action_hint.defaultActionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_snake_case_internal_loop_hint_camel_default_action_snake_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "actionHint": {
                    "default_actionid": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internal_loop.actionHint.default_actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internal_loop.actionHint.default_actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_hint_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "actionHint": {
                    "action": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internal_loop.actionHint.action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionHint.action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_hint_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "action_hint": {
                    "action": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_hint_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "actionHint": {
                    "action_id": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internal_loop.actionHint.action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionHint.action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_hint_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "actionHint": {
                    "actionid": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internal_loop.actionHint.actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionHint.actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_hint_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "actionHint": {
                    "actionID": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internal_loop.actionHint.actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionHint.actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_hint_bridge_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "actionHint": {
                    "bridge_action_id": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internal_loop.actionHint.bridge_action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionHint.bridge_action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_hint_bridge_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "actionHint": {
                    "bridgeActionID": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internal_loop.actionHint.bridgeActionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionHint.bridgeActionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_hint_bridge_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "actionHint": {
                    "bridgeAction_id": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internal_loop.actionHint.bridgeAction_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionHint.bridgeAction_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_hint_bridge_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "actionHint": {
                    "bridge-action-id": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internal_loop.actionHint.bridge-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionHint.bridge-action-id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_hint_bridge_action_kebab_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "actionHint": {
                    "bridge-actionid": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internal_loop.actionHint.bridge-actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionHint.bridge-actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_hint_bridge_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "action_hint": {
                    "bridgeActionId": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.bridgeActionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.bridgeActionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_hint_bridge_action_snake_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "action_hint": {
                    "bridge_action_id": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.bridge_action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.bridge_action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_hint_bridge_action_snake_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "action_hint": {
                    "bridge_actionID": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.bridge_actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.bridge_actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_hint_bridge_action_snake_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "action_hint": {
                    "bridge_actionId": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.bridge_actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.bridge_actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_hint_bridge_action_snake_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "action_hint": {
                    "bridge_actionid": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.bridge_actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.bridge_actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_hint_bridge_action_kebab_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "action_hint": {
                    "bridge-actionId": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.bridge-actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.bridge-actionId",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_hint_bridge_action_kebab_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "action_hint": {
                    "bridge-actionID": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.bridge-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.bridge-actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_hint_bridge_action_kebab_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "action_hint": {
                    "bridge-actionid": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.bridge-actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.bridge-actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_hint_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "action_hint": {
                    "action_id": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.action_id",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_hint_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "action_hint": {
                    "actionid": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.actionid",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_hint_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "action_hint": {
                    "actionID": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.actionID",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_camel_case_workflow_snake_case_internal_loop_hint_watch_act_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "internal_loop": {
                "actionHint": {
                    "watchActAction": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.internal_loop.actionHint.watchActAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operatorWorkflow.internal_loop.actionHint.watchActAction",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_infers_action_from_snake_case_workflow_camel_case_internal_loop_hint_watch_act_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "operator_workflow": {
            "packageId": "cliq-195",
            "internalLoop": {
                "action_hint": {
                    "watch_act_action": "watch-loop-route",
                }
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "watch-loop-route"
    payload = json.loads(result.output)
    assert payload["actionId"] == "watch-loop-route"
    assert payload["actionSource"] == "watch-loop-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.internalLoop.action_hint.watch_act_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "watch-loop-hint",
        "sourcePath": "operator_workflow.internalLoop.action_hint.watch_act_action",
        "fromWatchLoopHint": True,
        "fromEscalationHint": False,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "defaultAction": "notify-mail",
                "actionHint": {
                    "bridgeActionId": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.bridgeActionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.bridgeActionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_top_level_bridge_action_id(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "bridgeActionId": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.bridgeActionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.bridgeActionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_top_level_bridge_action_id(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "bridge_action_id": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.bridge_action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.bridge_action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_top_level_bridge_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "bridge_action_id": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.bridge_action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.bridge_action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_top_level_bridge_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "bridgeActionId": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.bridgeActionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.bridgeActionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_top_level_bridge_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "bridge-action-id": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.bridge-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.bridge-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_top_level_bridge_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "bridge-action-id": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.bridge-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.bridge-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_camel_case_escalation_alias_top_level_bridge_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "bridge-action-id": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.bridge-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.bridge-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_top_level_bridge_action_kebab_compact_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "bridge-actionid": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.bridge-actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.bridge-actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_top_level_bridge_action_kebab_snake_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "bridge-action_id": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.bridge-action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.bridge-action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_top_level_bridge_action_kebab_snake_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "bridge-action_id": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.bridge-action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.bridge-action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_camel_case_escalation_alias_top_level_bridge_action_kebab_snake_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "bridge-action_id": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.bridge-action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.bridge-action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_snake_case_escalation_alias_top_level_bridge_action_kebab_snake_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "bridge-action_id": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.bridge-action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.bridge-action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_camel_case_escalation_alias_top_level_bridge_action_kebab_mixed_case_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "bridge-actionId": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.bridge-actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.bridge-actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_camel_case_escalation_alias_top_level_bridge_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "bridge-actionID": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.bridge-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.bridge-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_top_level_bridge_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "bridge-actionID": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.bridge-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.bridge-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_top_level_bridge_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "bridge-actionID": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.bridge-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.bridge-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_snake_case_escalation_alias_top_level_bridge_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "bridge-action-id": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.bridge-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.bridge-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_top_level_bridge_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "bridgeActionID": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.bridgeActionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.bridgeActionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_camel_case_escalation_alias_top_level_bridge_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "bridgeActionID": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.bridgeActionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.bridgeActionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_camel_case_escalation_alias_top_level_bridge_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "bridgeAction_id": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.bridgeAction_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.bridgeAction_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_top_level_bridge_action_snake_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "bridge_actionID": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.bridge_actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.bridge_actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_top_level_bridge_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "bridgeAction_id": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.bridgeAction_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.bridgeAction_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_top_level_bridge_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "bridge_actionId": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.bridge_actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.bridge_actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_top_level_bridge_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "bridgeActionid": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.bridgeActionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.bridgeActionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_top_level_bridge_action_snake_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "bridge_actionid": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.bridge_actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.bridge_actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_camel_case_escalation_alias_top_level_bridge_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "bridgeActionid": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.bridgeActionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.bridgeActionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_snake_case_escalation_alias_top_level_bridge_action_snake_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "bridge_actionid": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.bridge_actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.bridge_actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_top_level_watch_act_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "watch_act_action": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.watch_act_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.watch_act_action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_top_level_watch_act_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "watchActAction": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.watchActAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.watchActAction",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_top_level_watch_act_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "watchActAction": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.watchActAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.watchActAction",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_top_level_watch_act_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "watch_act_action": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.watch_act_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.watch_act_action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_action_hint_top_level_watch_act_action(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "actionHint": {
                    "watchActAction": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.watchActAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.watchActAction",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_action_hint_top_level_watch_act_action(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "action_hint": {
                    "watch_act_action": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.watch_act_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.watch_act_action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_action_hint_watch_act_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "watchActAction": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.watchActAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.watchActAction",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_action_hint_watch_act_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "watch_act_action": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.watch_act_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.watch_act_action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_action_hint_watch_act_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "watch_act_action": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.watch_act_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.watch_act_action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_action_hint_watch_act_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "watchActAction": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.watchActAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.watchActAction",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_top_level_default_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "defaultAction": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.defaultAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.defaultAction",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_top_level_default_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "default_action": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.default_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.default_action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_top_level_default_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "defaultAction": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.defaultAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.defaultAction",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_top_level_default_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "default_action": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.default_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.default_action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_top_level_default_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "defaultAction_id": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.defaultAction_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.defaultAction_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_top_level_default_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "default_actionId": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.default_actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.default_actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_top_level_default_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "defaultActionId": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.defaultActionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.defaultActionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_top_level_default_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "default-action-id": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.default-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.default-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_top_level_default_action_kebab_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "default-action": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.default-action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.default-action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_top_level_default_action_kebab_compact_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "default-actionid": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.default-actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.default-actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_top_level_default_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "default-actionID": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.default-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.default-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_top_level_default_action_kebab_mixed_case_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "default-actionId": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.default-actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.default-actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_top_level_default_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "default-actionID": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.default-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.default-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_top_level_default_action_kebab_mixed_case_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "default-actionId": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.default-actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.default-actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_top_level_default_action_kebab_compact_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "default-actionid": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.default-actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.default-actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_top_level_default_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "default_action_id": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.default_action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.default_action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_top_level_default_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "defaultActionID": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.defaultActionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.defaultActionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_top_level_default_action_snake_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "default_actionID": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.default_actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.default_actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_top_level_default_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "defaultActionid": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.defaultActionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.defaultActionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_top_level_default_action_snake_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "default_actionid": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.default_actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.default_actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_camel_case_escalation_alias_top_level_default_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "default-action-id": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.default-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.default-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_camel_case_escalation_alias_top_level_default_action_kebab_compact_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "default-actionid": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.default-actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.default-actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_camel_case_escalation_alias_top_level_default_action_kebab_mixed_case_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "default-actionId": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.default-actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.default-actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_camel_case_escalation_alias_top_level_default_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "default-actionID": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.default-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.default-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_camel_case_escalation_alias_top_level_default_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "defaultActionid": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.defaultActionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.defaultActionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_snake_case_escalation_alias_top_level_default_action_snake_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "default_actionid": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.default_actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.default_actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_snake_case_escalation_alias_top_level_default_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "default-action-id": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.default-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.default-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_snake_case_escalation_alias_top_level_default_action_kebab_mixed_case_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "default-actionId": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.default-actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.default-actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_snake_case_escalation_alias_top_level_default_action_kebab_compact_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "default-actionid": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.default-actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.default-actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_snake_case_escalation_alias_top_level_default_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "default-actionID": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.default-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.default-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_top_level_action_id(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "actionId": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert payload["actionSourcePath"] == "operatorWorkflow.externalEscalation.actionId"
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_top_level_action_id(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "action_id": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.external_escalation.action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_top_level_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionId": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.external_escalation.actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_top_level_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_id": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.externalEscalation.action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_top_level_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionID": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.external_escalation.actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_top_level_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "actionID": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.externalEscalation.actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_top_level_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionid": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"] == "operatorWorkflow.external_escalation.actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_top_level_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "actionid": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.externalEscalation.actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_camel_case_escalation_alias_top_level_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "actionid": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert payload["actionSourcePath"] == "operatorWorkflow.externalEscalation.actionid"
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_snake_case_escalation_alias_top_level_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionid": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"] == "operator_workflow.external_escalation.actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_action_hint_top_level_action_id(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "actionHint": {
                    "actionId": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_action_hint_top_level_action_id(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "action_hint": {
                    "action_id": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_action_hint_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "actionId": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_action_hint_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "action_id": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_action_hint_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "actionId": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_action_hint_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "action_id": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_camel_case_escalation_alias_action_hint_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "actionId": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_snake_case_escalation_alias_action_hint_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "action_id": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_action_hint_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "actionID": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_action_hint_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "actionID": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_action_hint_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "actionID": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_action_hint_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "actionID": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_camel_case_escalation_alias_action_hint_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "actionID": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_snake_case_escalation_alias_action_hint_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "actionID": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_action_hint_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "actionid": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_action_hint_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "actionid": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_camel_case_escalation_alias_action_hint_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "actionid": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_snake_case_escalation_alias_action_hint_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "actionid": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_action_hint_top_level_action(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "actionHint": {
                    "action": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_action_hint_top_level_action(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "action_hint": {
                    "action": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_top_level_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "action": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert payload["actionSourcePath"] == "operatorWorkflow.external_escalation.action"
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_top_level_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action": "notify-mail",
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert payload["actionSourcePath"] == "operator_workflow.externalEscalation.action"
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_action_hint_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "action": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_action_hint_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "action": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_action_hint_top_level_default_action(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "actionHint": {
                    "defaultAction": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.defaultAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.defaultAction",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_action_hint_top_level_default_action(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "action_hint": {
                    "default_action": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.default_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.default_action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_action_hint_default_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "defaultAction": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.defaultAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.defaultAction",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_action_hint_default_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "default_action": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.default_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.default_action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_action_hint_default_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "default_action_id": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.default_action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.default_action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_action_hint_default_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "defaultActionId": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.defaultActionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.defaultActionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_action_hint_default_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "defaultActionID": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.defaultActionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.defaultActionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_action_hint_default_action_snake_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "default_actionID": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.default_actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.default_actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_action_hint_default_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "defaultActionID": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.defaultActionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.defaultActionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_action_hint_default_action_snake_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "default_actionID": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.default_actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.default_actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_action_hint_default_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "defaultAction_id": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.defaultAction_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.defaultAction_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_action_hint_default_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "default_actionId": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.default_actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.default_actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_action_hint_default_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "defaultAction_id": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.defaultAction_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.defaultAction_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_action_hint_default_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "default_actionId": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.default_actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.default_actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_action_hint_default_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "default_action": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.default_action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.default_action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_action_hint_default_action_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "defaultAction": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.defaultAction"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.defaultAction",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_bridge_action_id(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "action_hint": {
                    "bridge_action_id": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.bridge_action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.bridge_action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_action_hint_top_level_bridge_action_id_camel_case_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "action_hint": {
                    "bridgeActionId": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.bridgeActionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.bridgeActionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_action_hint_top_level_bridge_action_id_snake_case_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "actionHint": {
                    "bridge_action_id": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.bridge_action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.bridge_action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_action_hint_bridge_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "bridgeActionId": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.bridgeActionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.bridgeActionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_action_hint_bridge_action_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "bridge_action_id": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.bridge_action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.bridge_action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_action_hint_bridge_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "bridgeAction_id": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.bridgeAction_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.bridgeAction_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_action_hint_bridge_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "bridge_actionId": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.bridge_actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.bridge_actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_action_hint_bridge_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "bridgeAction_id": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.bridgeAction_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.bridgeAction_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_action_hint_bridge_action_mixed_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "bridge_actionId": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.bridge_actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.bridge_actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_action_hint_bridge_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "bridge-action-id": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.bridge-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.bridge-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_action_hint_bridge_action_kebab_snake_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "bridge-action_id": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.bridge-action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.bridge-action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_action_hint_bridge_action_kebab_snake_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "bridge-action_id": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.bridge-action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.bridge-action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_action_hint_bridge_action_kebab_compact_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "bridge-actionid": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.bridge-actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.bridge-actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_action_hint_bridge_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "bridge-action-id": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.bridge-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.bridge-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_action_hint_bridge_action_kebab_compact_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "bridge-actionid": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.bridge-actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.bridge-actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_action_hint_bridge_action_kebab_mixed_case_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "bridge-actionId": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.bridge-actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.bridge-actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_action_hint_bridge_action_kebab_mixed_case_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "bridge-actionId": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.bridge-actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.bridge-actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_camel_case_escalation_alias_action_hint_bridge_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "actionHint": {
                    "bridge-action-id": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.bridge-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.bridge-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_camel_case_escalation_alias_action_hint_bridge_action_kebab_mixed_case_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "actionHint": {
                    "bridge-actionId": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.bridge-actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.bridge-actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_camel_case_escalation_alias_action_hint_bridge_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "actionHint": {
                    "bridge-actionID": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.bridge-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.bridge-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_snake_case_escalation_alias_action_hint_bridge_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "action_hint": {
                    "bridge-action-id": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.bridge-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.bridge-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_snake_case_escalation_alias_action_hint_bridge_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "action_hint": {
                    "bridge-actionID": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.bridge-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.bridge-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_action_hint_bridge_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "bridge-actionID": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.bridge-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.bridge-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_action_hint_bridge_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "bridge-actionID": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.bridge-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.bridge-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_action_hint_bridge_action_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "bridgeActionID": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.bridgeActionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.bridgeActionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_action_hint_bridge_action_snake_uppercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "bridge_actionID": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.bridge_actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.bridge_actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_action_hint_bridge_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "bridgeActionid": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.bridgeActionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.bridgeActionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_action_hint_bridge_action_snake_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "bridge_actionid": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.bridge_actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.bridge_actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_camel_case_escalation_alias_action_hint_bridge_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "actionHint": {
                    "bridgeActionid": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.bridgeActionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.bridgeActionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_snake_case_escalation_alias_action_hint_bridge_action_snake_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "action_hint": {
                    "bridge_actionid": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.bridge_actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.bridge_actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_action_hint_default_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "defaultActionid": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.defaultActionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.defaultActionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_action_hint_default_action_snake_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "default_actionid": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.default_actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.default_actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_camel_case_escalation_alias_action_hint_default_action_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "defaultActionid": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.defaultActionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.defaultActionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_snake_case_escalation_alias_action_hint_default_action_snake_lowercase_tail_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "default_actionid": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.default_actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.default_actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_action_hint_default_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "default-action-id": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.default-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.default-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_action_hint_default_action_kebab_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "default-action": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.default-action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.default-action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_action_hint_default_action_kebab_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "default-action": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.default-action"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.default-action",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_action_hint_default_action_kebab_compact_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "default-actionid": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.default-actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.default-actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_action_hint_default_action_kebab_mixed_case_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "default-actionId": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.default-actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.default-actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_escalation_alias_action_hint_default_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "default-actionID": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.external_escalation.actionHint.default-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.external_escalation.actionHint.default-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_camel_case_escalation_alias_action_hint_default_action_kebab_mixed_case_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "actionHint": {
                    "default-actionId": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.default-actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.default-actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_camel_case_escalation_alias_action_hint_default_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "actionHint": {
                    "default-actionID": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.default-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.default-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_action_hint_default_action_kebab_compact_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "default-actionid": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.default-actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.default-actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_camel_case_escalation_alias_action_hint_default_action_kebab_compact_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "actionHint": {
                    "default-actionid": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.default-actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.default-actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_snake_case_escalation_alias_action_hint_default_action_kebab_compact_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "action_hint": {
                    "default-actionid": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.default-actionid"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.default-actionid",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_snake_case_escalation_alias_action_hint_default_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "action_hint": {
                    "default-actionID": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.default-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.default-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_snake_case_escalation_alias_action_hint_default_action_kebab_mixed_case_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "action_hint": {
                    "default-actionId": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.default-actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.default-actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_action_hint_default_action_kebab_mixed_case_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "default-actionId": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.default-actionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.default-actionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_action_hint_default_action_kebab_uppercase_tail_id_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "default-actionID": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.default-actionID"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.default-actionID",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_escalation_alias_action_hint_default_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "default-action-id": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.externalEscalation.action_hint.default-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.externalEscalation.action_hint.default-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_camel_case_escalation_alias_action_hint_default_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "actionHint": {
                    "default-action-id": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.actionHint.default-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.actionHint.default-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_snake_case_escalation_alias_action_hint_default_action_kebab_case_id_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "action_hint": {
                    "default-action-id": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.action_hint.default-action-id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.action_hint.default-action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_snake_case_workflow_camel_case_action_hint_bridge_action_id_camel_case_alias(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operator_workflow": {
            "packageId": "cliq-195",
            "external_escalation": {
                "actionHint": {
                    "bridgeActionId": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operator_workflow.external_escalation.actionHint.bridgeActionId"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operator_workflow.external_escalation.actionHint.bridgeActionId",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_escalation_action_overrides_watch_loop_hint_with_camel_case_workflow_snake_case_action_hint_bridge_action_id_snake_case_aliases(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "chatId": "CT_1",
        "watchIntake": {
            "consume": {
                "actionId": "watch-loop",
            }
        },
        "operatorWorkflow": {
            "packageId": "cliq-195",
            "externalEscalation": {
                "action_hint": {
                    "bridge_action_id": "notify-mail",
                },
            },
        },
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "--watch-file",
                str(watch_file),
                "--escalation-action",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "notify-mail"
    payload = json.loads(result.output)
    assert payload["actionId"] == "notify-mail"
    assert payload["actionSource"] == "escalation-hint"
    assert (
        payload["actionSourcePath"]
        == "operatorWorkflow.externalEscalation.action_hint.bridge_action_id"
    )
    assert payload["actionSourceMetadata"] == {
        "source": "escalation-hint",
        "sourcePath": "operatorWorkflow.externalEscalation.action_hint.bridge_action_id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": True,
        "fromExplicitOverride": False,
    }


def test_cliq_bridge_run_watch_file_preserves_explicit_action_override(
    tmp_path: Path,
    mock_config: Path,
) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(*a, **kw):
        seen["command"] = a[0]
        return subprocess.CompletedProcess(
            args=a[0],
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    watch_payload = {
        "watchIntake": {
            "consume": {
                "actionId": "hinted-action",
            }
        }
    }
    watch_file = tmp_path / "watch-context.json"
    watch_file.write_text(json.dumps(watch_payload))

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
                "positional-action",
                "--action-id",
                "explicit-action",
                "--watch-file",
                str(watch_file),
                "--input-json",
                json.dumps({"batch": "B1"}),
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "explicit-action"
    assert seen["command"][6] == "--input"
    assert json.loads(seen["command"][7]) == {
        "batch": "B1",
        "watchPayload": watch_payload,
        "watchIntake": watch_payload["watchIntake"],
        "operatorWorkflow": {},
        "escalationEnvelope": {},
        "escalationEnvelopeMetadata": {
            "source": "",
            "sourcePath": "",
            "fromTopLevelAlias": False,
            "fromNestedFallback": False,
            "usedFieldFallback": False,
            "fieldSources": {},
        },
        "actionSource": "explicit-override",
        "actionSourcePath": "--action-id",
        "actionSourceMetadata": {
            "source": "explicit-override",
            "sourcePath": "--action-id",
            "fromWatchLoopHint": False,
            "fromEscalationHint": False,
            "fromExplicitOverride": True,
        },
    }
    payload = json.loads(result.output)
    assert payload["actionId"] == "explicit-action"
    assert payload["actionSource"] == "explicit-override"
    assert payload["actionSourcePath"] == "--action-id"
    assert payload["actionSourceMetadata"] == {
        "source": "explicit-override",
        "sourcePath": "--action-id",
        "fromWatchLoopHint": False,
        "fromEscalationHint": False,
        "fromExplicitOverride": True,
    }
    assert payload["escalationEnvelopeMetadata"] == {
        "source": "",
        "sourcePath": "",
        "fromTopLevelAlias": False,
        "fromNestedFallback": False,
        "usedFieldFallback": False,
        "fieldSources": {},
    }


def test_cliq_apps_bridge_run_defaults_action_and_input(
    mock_config: Path,
) -> None:
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
                "apps-bridge-run",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][:6] == [
        "/usr/local/bin/membrane",
        "action",
        "run",
        "--connectionId=CONN_CLIQ_FROM_CONFIG",
        "apps",
        "--json",
    ]
    assert seen["command"][6] == "--input"
    assert json.loads(seen["command"][7]) == {"limit": 50}

    payload = json.loads(result.output)
    assert payload["actionId"] == "apps"
    assert payload["input"] == {"limit": 50}


def test_cliq_apps_bridge_run_merges_input_json_with_limit(
    mock_config: Path,
) -> None:
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
                "apps-bridge-run",
                "--limit",
                "25",
                "--action-id",
                "custom-apps-action",
                "--input-json",
                '{"cursor": "abc"}',
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "custom-apps-action"
    assert seen["command"][6] == "--input"
    assert json.loads(seen["command"][7]) == {"cursor": "abc", "limit": 25}

    payload = json.loads(result.output)
    assert payload["actionId"] == "custom-apps-action"
    assert payload["input"] == {"cursor": "abc", "limit": 25}


def test_cliq_app_get_bridge_run_defaults_action_and_input(
    mock_config: Path,
) -> None:
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
                "app-get-bridge-run",
                "APP_123",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][:6] == [
        "/usr/local/bin/membrane",
        "action",
        "run",
        "--connectionId=CONN_CLIQ_FROM_CONFIG",
        "app-get",
        "--json",
    ]
    assert seen["command"][6] == "--input"
    assert json.loads(seen["command"][7]) == {"appId": "APP_123"}

    payload = json.loads(result.output)
    assert payload["actionId"] == "app-get"
    assert payload["appId"] == "APP_123"
    assert payload["input"] == {"appId": "APP_123"}


def test_cliq_app_get_bridge_run_merges_input_json_with_app_id(
    mock_config: Path,
) -> None:
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
                "app-get-bridge-run",
                "APP_123",
                "--action-id",
                "custom-app-get",
                "--input-json",
                '{"verbose": true}',
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "custom-app-get"
    assert seen["command"][6] == "--input"
    assert json.loads(seen["command"][7]) == {
        "verbose": True,
        "appId": "APP_123",
    }

    payload = json.loads(result.output)
    assert payload["actionId"] == "custom-app-get"
    assert payload["input"] == {
        "verbose": True,
        "appId": "APP_123",
    }


def test_cliq_app_commands_bridge_run_defaults_action_and_input(
    mock_config: Path,
) -> None:
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
                "app-commands-bridge-run",
                "APP_123",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][:6] == [
        "/usr/local/bin/membrane",
        "action",
        "run",
        "--connectionId=CONN_CLIQ_FROM_CONFIG",
        "app-commands",
        "--json",
    ]
    assert seen["command"][6] == "--input"
    assert json.loads(seen["command"][7]) == {"appId": "APP_123"}

    payload = json.loads(result.output)
    assert payload["actionId"] == "app-commands"
    assert payload["appId"] == "APP_123"
    assert payload["input"] == {"appId": "APP_123"}


def test_cliq_app_commands_bridge_run_merges_input_json_with_app_id(
    mock_config: Path,
) -> None:
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
                "app-commands-bridge-run",
                "APP_123",
                "--action-id",
                "custom-action",
                "--input-json",
                '{"limit": 5}',
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "custom-action"
    assert seen["command"][6] == "--input"
    assert json.loads(seen["command"][7]) == {"limit": 5, "appId": "APP_123"}

    payload = json.loads(result.output)
    assert payload["actionId"] == "custom-action"
    assert payload["input"] == {"limit": 5, "appId": "APP_123"}


def test_cliq_app_permissions_bridge_run_defaults_action_and_input(
    mock_config: Path,
) -> None:
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
                "app-permissions-bridge-run",
                "APP_123",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][:6] == [
        "/usr/local/bin/membrane",
        "action",
        "run",
        "--connectionId=CONN_CLIQ_FROM_CONFIG",
        "app-permissions",
        "--json",
    ]
    assert seen["command"][6] == "--input"
    assert json.loads(seen["command"][7]) == {"appId": "APP_123"}

    payload = json.loads(result.output)
    assert payload["actionId"] == "app-permissions"
    assert payload["appId"] == "APP_123"
    assert payload["input"] == {"appId": "APP_123"}


def test_cliq_app_permissions_bridge_run_merges_input_json_with_app_id(
    mock_config: Path,
) -> None:
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
                "app-permissions-bridge-run",
                "APP_123",
                "--action-id",
                "custom-action",
                "--input-json",
                '{"limit": 3}',
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "custom-action"
    assert seen["command"][6] == "--input"
    assert json.loads(seen["command"][7]) == {"limit": 3, "appId": "APP_123"}

    payload = json.loads(result.output)
    assert payload["actionId"] == "custom-action"
    assert payload["input"] == {"limit": 3, "appId": "APP_123"}


def test_cliq_app_command_get_bridge_run_defaults_action_and_input(
    mock_config: Path,
) -> None:
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
                "app-command-get-bridge-run",
                "APP_123",
                "CMD_456",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][:6] == [
        "/usr/local/bin/membrane",
        "action",
        "run",
        "--connectionId=CONN_CLIQ_FROM_CONFIG",
        "app-command-get",
        "--json",
    ]
    assert seen["command"][6] == "--input"
    assert json.loads(seen["command"][7]) == {
        "appId": "APP_123",
        "commandId": "CMD_456",
    }

    payload = json.loads(result.output)
    assert payload["actionId"] == "app-command-get"
    assert payload["appId"] == "APP_123"
    assert payload["commandId"] == "CMD_456"
    assert payload["input"] == {"appId": "APP_123", "commandId": "CMD_456"}


def test_cliq_app_command_get_bridge_run_merges_input_json_with_ids(
    mock_config: Path,
) -> None:
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
                "app-command-get-bridge-run",
                "APP_123",
                "CMD_456",
                "--action-id",
                "custom-action",
                "--input-json",
                '{"limit": 1}',
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "custom-action"
    assert seen["command"][6] == "--input"
    assert json.loads(seen["command"][7]) == {
        "limit": 1,
        "appId": "APP_123",
        "commandId": "CMD_456",
    }

    payload = json.loads(result.output)
    assert payload["actionId"] == "custom-action"
    assert payload["input"] == {
        "limit": 1,
        "appId": "APP_123",
        "commandId": "CMD_456",
    }


def test_cliq_app_installs_bridge_run_defaults_action_and_input(
    mock_config: Path,
) -> None:
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
                "app-installs-bridge-run",
                "APP_123",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][:6] == [
        "/usr/local/bin/membrane",
        "action",
        "run",
        "--connectionId=CONN_CLIQ_FROM_CONFIG",
        "app-installs",
        "--json",
    ]
    assert seen["command"][6] == "--input"
    assert json.loads(seen["command"][7]) == {"appId": "APP_123"}

    payload = json.loads(result.output)
    assert payload["actionId"] == "app-installs"
    assert payload["appId"] == "APP_123"
    assert payload["input"] == {"appId": "APP_123"}


def test_cliq_app_installs_bridge_run_merges_input_json_with_app_id(
    mock_config: Path,
) -> None:
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
                "app-installs-bridge-run",
                "APP_123",
                "--action-id",
                "custom-action",
                "--input-json",
                '{"limit": 7}',
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "custom-action"
    assert seen["command"][6] == "--input"
    assert json.loads(seen["command"][7]) == {"limit": 7, "appId": "APP_123"}

    payload = json.loads(result.output)
    assert payload["actionId"] == "custom-action"
    assert payload["input"] == {"limit": 7, "appId": "APP_123"}


def test_cliq_app_install_get_bridge_run_defaults_action_and_input(
    mock_config: Path,
) -> None:
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
                "app-install-get-bridge-run",
                "APP_123",
                "INSTALL_456",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][:6] == [
        "/usr/local/bin/membrane",
        "action",
        "run",
        "--connectionId=CONN_CLIQ_FROM_CONFIG",
        "app-install-get",
        "--json",
    ]
    assert seen["command"][6] == "--input"
    assert json.loads(seen["command"][7]) == {
        "appId": "APP_123",
        "installId": "INSTALL_456",
    }

    payload = json.loads(result.output)
    assert payload["actionId"] == "app-install-get"
    assert payload["appId"] == "APP_123"
    assert payload["installId"] == "INSTALL_456"
    assert payload["input"] == {"appId": "APP_123", "installId": "INSTALL_456"}


def test_cliq_app_install_get_bridge_run_merges_input_json_with_ids(
    mock_config: Path,
) -> None:
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
                "app-install-get-bridge-run",
                "APP_123",
                "INSTALL_456",
                "--action-id",
                "custom-action",
                "--input-json",
                '{"limit": 1}',
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "custom-action"
    assert seen["command"][6] == "--input"
    assert json.loads(seen["command"][7]) == {
        "limit": 1,
        "appId": "APP_123",
        "installId": "INSTALL_456",
    }

    payload = json.loads(result.output)
    assert payload["actionId"] == "custom-action"
    assert payload["input"] == {
        "limit": 1,
        "appId": "APP_123",
        "installId": "INSTALL_456",
    }


def test_cliq_app_permission_get_bridge_run_defaults_action_and_input(
    mock_config: Path,
) -> None:
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
                "app-permission-get-bridge-run",
                "APP_123",
                "PERMISSION_456",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][:6] == [
        "/usr/local/bin/membrane",
        "action",
        "run",
        "--connectionId=CONN_CLIQ_FROM_CONFIG",
        "app-permission-get",
        "--json",
    ]
    assert seen["command"][6] == "--input"
    assert json.loads(seen["command"][7]) == {
        "appId": "APP_123",
        "permissionId": "PERMISSION_456",
    }

    payload = json.loads(result.output)
    assert payload["actionId"] == "app-permission-get"
    assert payload["appId"] == "APP_123"
    assert payload["permissionId"] == "PERMISSION_456"
    assert payload["input"] == {
        "appId": "APP_123",
        "permissionId": "PERMISSION_456",
    }


def test_cliq_app_permission_get_bridge_run_merges_input_json_with_ids(
    mock_config: Path,
) -> None:
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
                "app-permission-get-bridge-run",
                "APP_123",
                "PERMISSION_456",
                "--action-id",
                "custom-action",
                "--input-json",
                '{"limit": 1}',
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][4] == "custom-action"
    assert seen["command"][6] == "--input"
    assert json.loads(seen["command"][7]) == {
        "limit": 1,
        "appId": "APP_123",
        "permissionId": "PERMISSION_456",
    }

    payload = json.loads(result.output)
    assert payload["actionId"] == "custom-action"
    assert payload["input"] == {
        "limit": 1,
        "appId": "APP_123",
        "permissionId": "PERMISSION_456",
    }


def test_cliq_export_chats_bridge_run_defaults_to_export_conversations(
    mock_config: Path,
) -> None:
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
                "export-chats-bridge-run",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"] == [
        "/usr/local/bin/membrane",
        "action",
        "run",
        "--connectionId=CONN_CLIQ_FROM_CONFIG",
        "export-conversations",
        "--json",
    ]
    payload = json.loads(result.output)
    assert payload["actionId"] == "export-conversations"
    assert payload["chatId"] is None


def test_cliq_export_chats_bridge_run_with_chat_id_sets_action_and_input(
    mock_config: Path,
) -> None:
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
                "export-chats-bridge-run",
                "--chat-id",
                "CT_123",
            ],
        )

    assert result.exit_code == 0, result.output
    assert seen["command"][:6] == [
        "/usr/local/bin/membrane",
        "action",
        "run",
        "--connectionId=CONN_CLIQ_FROM_CONFIG",
        "export-chat-messages",
        "--json",
    ]
    assert seen["command"][6] == "--input"
    assert json.loads(seen["command"][7]) == {"chatId": "CT_123"}

    payload = json.loads(result.output)
    assert payload["actionId"] == "export-chat-messages"
    assert payload["chatId"] == "CT_123"
    assert payload["input"] == {"chatId": "CT_123"}


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
