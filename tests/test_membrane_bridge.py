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
