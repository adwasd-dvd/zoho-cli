from __future__ import annotations

import os
import hashlib
import json
import stat
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPORT_RECHECK_SCRIPT = (
    REPO_ROOT / "tests" / "auto_pilot" / "run_cliq_export_scope_recheck.sh"
)
CRM_FIXTURE_SMOKE_SCRIPT = REPO_ROOT / "ops" / "scripts" / "crm_fixture_live_smoke.sh"
OPENCLAW_CLIQ_LIVE_SMOKE_SCRIPT = (
    REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_live_smoke.sh"
)
OPENCLAW_CLIQ_HASH_REF_SCRIPT = (
    REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_hash_ref.sh"
)
OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_SCRIPT = (
    REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_trusted_reply_evidence.sh"
)
OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_PREPARE_SCRIPT = (
    REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_trusted_reply_evidence_prepare.sh"
)
OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_BUNDLE_SCRIPT = (
    REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_trusted_reply_evidence_bundle.sh"
)
OPENCLAW_CLIQ_RC_PACK_SCRIPT = (
    REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_rc_pack.sh"
)


def test_export_scope_recheck_runner_propagates_probe_exit_codes(
    tmp_path: Path,
) -> None:
    fake_python = tmp_path / "fake_python.py"
    fake_python.write_text(
        """#!/usr/bin/env python3
import json
import sys

args = sys.argv[1:]
if "status" in args:
    print(json.dumps({"status": "ok"}))
    raise SystemExit(0)
if "--chat-id" in args:
    print(json.dumps({"status": "error", "error": "chat_probe_failed"}))
    raise SystemExit(4)
print(json.dumps({"status": "error", "error": "list_probe_failed"}))
raise SystemExit(3)
"""
    )
    fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)

    reports_dir = tmp_path / "reports"
    result = subprocess.run(
        [
            "bash",
            str(EXPORT_RECHECK_SCRIPT),
            str(tmp_path / "config.json"),
            "test@example.com",
            "example-network",
            "CHAT-123",
        ],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "PYTHON_BIN": str(fake_python),
            "SCAP_REPORT_DIR": str(reports_dir),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    assert "[SCAP] status exit=0 list exit=3 chat exit=4" in output
    assert "[SCAP] overall exit=1" in output

    status_reports = list(reports_dir.glob("cliq_status_export_scope_recheck_*.json"))
    list_reports = list(reports_dir.glob("cliq_export_chats_list_scope_recheck_*.json"))
    chat_reports = list(reports_dir.glob("cliq_export_chat_scope_recheck_*.json"))
    summary_reports = list(reports_dir.glob("cliq_export_scope_recheck_summary_*.json"))
    assert len(status_reports) == 1
    assert len(list_reports) == 1
    assert len(chat_reports) == 1
    assert len(summary_reports) == 1

    summary = json.loads(summary_reports[0].read_text())
    assert summary["statusExit"] == 0
    assert summary["listExit"] == 3
    assert summary["chatExit"] == 4
    assert summary["overallExit"] == 1
    assert summary["summaryVersion"] == 3
    assert summary["config"].endswith("config.json")
    assert summary["account"] == "test@example.com"
    assert summary["network"] == "example-network"
    assert summary["chatId"] == "CHAT-123"
    assert summary["scopeBlocked"] is False
    assert summary["rateLimited"] is False
    assert summary["recommendedNext"] == "rerun_scope_recheck"
    assert "--with-cliq-export" in summary["nextCommands"]["reauth"]
    assert summary["statusReport"].endswith(status_reports[0].name)
    assert summary["listReport"].endswith(list_reports[0].name)
    assert summary["chatReport"].endswith(chat_reports[0].name)


def test_export_scope_recheck_runner_marks_scope_blocked_when_detected(
    tmp_path: Path,
) -> None:
    fake_python = tmp_path / "fake_python_scope.py"
    fake_python.write_text(
        """#!/usr/bin/env python3
import json
import sys

args = sys.argv[1:]
if "status" in args:
    print(json.dumps({"status": "ok"}))
    raise SystemExit(0)
print(json.dumps({"status": "error", "error": "oauth_scope_invalid"}))
raise SystemExit(1)
"""
    )
    fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)

    reports_dir = tmp_path / "reports"
    result = subprocess.run(
        [
            "bash",
            str(EXPORT_RECHECK_SCRIPT),
            str(tmp_path / "config.json"),
            "test@example.com",
            "example-network",
            "CHAT-123",
        ],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "PYTHON_BIN": str(fake_python),
            "SCAP_REPORT_DIR": str(reports_dir),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    summary_reports = list(reports_dir.glob("cliq_export_scope_recheck_summary_*.json"))
    assert len(summary_reports) == 1

    summary = json.loads(summary_reports[0].read_text())
    assert summary["scopeBlocked"] is True
    assert summary["rateLimited"] is False
    assert summary["recommendedNext"] == "interactive_reauth_then_rerun"


def test_export_scope_recheck_runner_marks_scope_blocked_from_status_report(
    tmp_path: Path,
) -> None:
    fake_python = tmp_path / "fake_python_status_scope.py"
    fake_python.write_text(
        """#!/usr/bin/env python3
import json
import sys

args = sys.argv[1:]
if "status" in args:
    print(json.dumps({
        "status": "ok",
        "exportOauthReady": False,
        "missingExportScopes": ["ZohoCliq.OrganizationChats.READ"],
    }))
    raise SystemExit(0)
if "--chat-id" in args:
    print(json.dumps({"status": "error", "error": "chat_probe_failed"}))
    raise SystemExit(4)
print(json.dumps({"status": "error", "error": "list_probe_failed"}))
raise SystemExit(3)
"""
    )
    fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)

    reports_dir = tmp_path / "reports"
    result = subprocess.run(
        [
            "bash",
            str(EXPORT_RECHECK_SCRIPT),
            str(tmp_path / "config.json"),
            "test@example.com",
            "example-network",
            "CHAT-123",
        ],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "PYTHON_BIN": str(fake_python),
            "SCAP_REPORT_DIR": str(reports_dir),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    summary_reports = list(reports_dir.glob("cliq_export_scope_recheck_summary_*.json"))
    assert len(summary_reports) == 1

    summary = json.loads(summary_reports[0].read_text())
    assert summary["scopeBlocked"] is True
    assert summary["rateLimited"] is False
    assert summary["recommendedNext"] == "interactive_reauth_then_rerun"


def test_export_scope_recheck_runner_marks_rate_limited_when_detected(
    tmp_path: Path,
) -> None:
    fake_python = tmp_path / "fake_python_rate_limited.py"
    fake_python.write_text(
        """#!/usr/bin/env python3
import json
import sys

args = sys.argv[1:]
if "status" in args:
    print(json.dumps({"status": "error", "error": "token_refresh_rate_limited"}))
    raise SystemExit(1)
if "--chat-id" in args:
    print(json.dumps({"status": "error", "error": "chat_probe_failed"}))
    raise SystemExit(4)
print(json.dumps({"status": "error", "error": "list_probe_failed"}))
raise SystemExit(3)
"""
    )
    fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)

    reports_dir = tmp_path / "reports"
    result = subprocess.run(
        [
            "bash",
            str(EXPORT_RECHECK_SCRIPT),
            str(tmp_path / "config.json"),
            "test@example.com",
            "example-network",
            "CHAT-123",
        ],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "PYTHON_BIN": str(fake_python),
            "SCAP_REPORT_DIR": str(reports_dir),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    summary_reports = list(reports_dir.glob("cliq_export_scope_recheck_summary_*.json"))
    assert len(summary_reports) == 1

    summary = json.loads(summary_reports[0].read_text())
    assert summary["scopeBlocked"] is False
    assert summary["rateLimited"] is True
    assert summary["recommendedNext"] == "wait_for_refresh_cooldown_then_rerun"


def test_openclaw_cliq_rc_pack_script_runs_pack_from_package_dir(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / "openclaw-channel-cliq"
    package_dir.mkdir()
    (package_dir / "package.json").write_text(
        json.dumps(
            {
                "name": "@adwasd/openclaw-zoho-cliq",
                "version": "0.4.0-rc.1",
            }
        )
    )
    calls_path = tmp_path / "fake_npm_calls.jsonl"
    fake_npm = tmp_path / "fake_npm.py"
    fake_npm.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
expected_package_dir = Path(os.environ["EXPECTED_PACKAGE_DIR"])
calls_path = Path(os.environ["FAKE_NPM_CALLS"])
with calls_path.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps({"args": args, "cwd": os.getcwd()}) + "\\n")

if args == ["--prefix", str(expected_package_dir), "run", "typecheck"]:
    raise SystemExit(0)
if args == ["--prefix", str(expected_package_dir), "run", "build"]:
    raise SystemExit(0)

if args[:1] == ["pack"]:
    if Path.cwd() != expected_package_dir:
        print(json.dumps({"status": "error", "error": "wrong_cwd"}))
        raise SystemExit(8)
    destination = Path(args[args.index("--pack-destination") + 1])
    destination.mkdir(parents=True, exist_ok=True)
    filename = "adwasd-openclaw-zoho-cliq-0.4.0-rc.1.tgz"
    (destination / filename).write_bytes(b"fake-tarball")
    print(json.dumps([{
        "id": "@adwasd/openclaw-zoho-cliq@0.4.0-rc.1",
        "name": "@adwasd/openclaw-zoho-cliq",
        "version": "0.4.0-rc.1",
        "filename": filename,
        "size": 12,
        "unpackedSize": 34,
        "shasum": "abc123",
        "integrity": "sha512-test",
        "files": [{"path": "README.md"}, {"path": "dist/index.js"}],
        "bundled": []
    }]))
    raise SystemExit(0)

print(json.dumps({"status": "error", "error": "unexpected_args", "args": args}))
raise SystemExit(9)
"""
    )
    fake_npm.chmod(fake_npm.stat().st_mode | stat.S_IXUSR)

    reports_dir = tmp_path / "reports"
    pack_dir = tmp_path / "pack"
    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_RC_PACK_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "NPM_BIN": str(fake_npm),
            "FAKE_NPM_CALLS": str(calls_path),
            "EXPECTED_PACKAGE_DIR": str(package_dir),
            "OPENCLAW_CLIQ_PACKAGE_DIR": str(package_dir),
            "OPENCLAW_CLIQ_PACK_DIR": str(pack_dir),
            "OPENCLAW_CLIQ_PACK_REPORT_DIR": str(reports_dir),
            "OPENCLAW_CLIQ_PACK_RUN_ID": "unit-test",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    summary_path = reports_dir / "openclaw_cliq_rc_pack_summary_unit-test.json"
    raw_pack_path = reports_dir / "openclaw_cliq_rc_pack_unit-test.pack.json"
    assert summary_path.exists()
    assert raw_pack_path.exists()

    summary = json.loads(summary_path.read_text())
    assert summary["status"] == "passed"
    assert summary["packageDir"] == str(package_dir)
    assert summary["pack"]["name"] == "@adwasd/openclaw-zoho-cliq"
    assert summary["pack"]["version"] == "0.4.0-rc.1"
    assert summary["pack"]["entryCount"] == 2
    assert summary["releasePosture"] == {
        "publishPerformed": False,
        "versionBumped": False,
        "expectedIntegrityPlaceholder": "<filled-at-release>",
    }
    assert Path(summary["pack"]["tarballPath"]).exists()

    calls = [json.loads(line) for line in calls_path.read_text().splitlines()]
    assert {
        "args": ["--prefix", str(package_dir), "run", "typecheck"],
        "cwd": str(REPO_ROOT),
    } in calls
    assert {
        "args": ["--prefix", str(package_dir), "run", "build"],
        "cwd": str(REPO_ROOT),
    } in calls
    pack_calls = [call for call in calls if call["args"][:1] == ["pack"]]
    assert len(pack_calls) == 1
    assert pack_calls[0]["cwd"] == str(package_dir)


def _write_fake_zoho_for_crm_fixture_smoke(tmp_path: Path) -> tuple[Path, Path]:
    calls_path = tmp_path / "zoho_calls.jsonl"
    fake_zoho = tmp_path / "fake_zoho.py"
    fake_zoho.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
calls_path = Path(os.environ["FAKE_ZOHO_CALLS"])
with calls_path.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(args) + "\\n")

if args[:2] == ["crm", "upsert"]:
    print(json.dumps({"status":"planned","payloadDigest":"sha256:abc123","liveWritesEnabled":False}))
elif args[:2] == ["crm", "upsert-gate"]:
    print(json.dumps({"policyId":"crm-009-live-upsert-gate","decision":"defer_live_execution","liveWritesEnabled":False,"blockingReasons":[]}))
elif args[:2] == ["crm", "fixture-plan"]:
    print(json.dumps({"policyId":"crm-011-controlled-live-fixture-gate","decision":"defer_controlled_live_fixture","liveWritesEnabled":False,"auditEvidence":{"hasDryRunPlan":True,"hasGate":True,"hasScopeEvidence":True},"blockingReasons":[]}))
elif args[:2] == ["crm", "fixture-execute"] and "--execute" in args:
    print(json.dumps({"policyId":"crm-012-guarded-fixture-execution-harness","decision":"allow_controlled_live_fixture_execution","status":"succeeded","liveWritesEnabled":True,"responseSummary":{"recordIds":["R1"]}}))
elif args[:2] == ["crm", "fixture-execute"]:
    print(json.dumps({"policyId":"crm-012-guarded-fixture-execution-harness","decision":"defer_controlled_live_fixture_execution","requiredApproval":"crm:fixture:upsert:Leads:abc123:fixture-test","liveWritesEnabled":False,"blockingReasons":["execute_flag_required"]}))
elif args[:2] == ["crm", "write-audit"]:
    print(json.dumps({"status":"ok","count":4,"events":[]}))
else:
    print(json.dumps({"status":"error","error":"unexpected_args","args":args}))
    raise SystemExit(9)
"""
    )
    fake_zoho.chmod(fake_zoho.stat().st_mode | stat.S_IXUSR)
    return fake_zoho, calls_path


def test_crm_fixture_live_smoke_defaults_to_dry_run(tmp_path: Path) -> None:
    fake_zoho, calls_path = _write_fake_zoho_for_crm_fixture_smoke(tmp_path)
    payload_file = tmp_path / "fixture.json"
    payload_file.write_text(
        json.dumps({"Last_Name": "Wang", "Email": "wang@example.com"})
    )
    reports_dir = tmp_path / "reports"

    result = subprocess.run(
        ["bash", str(CRM_FIXTURE_SMOKE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_BIN": str(fake_zoho),
            "FAKE_ZOHO_CALLS": str(calls_path),
            "ZOHO_CRM_FIXTURE_PAYLOAD_FILE": str(payload_file),
            "ZOHO_CRM_FIXTURE_REPORT_DIR": str(reports_dir),
            "ZOHO_CRM_FIXTURE_IDEMPOTENCY_KEY": "fixture-test",
            "ZOHO_CRM_FIXTURE_RUN_ID": "unit-test",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    calls = [json.loads(line) for line in calls_path.read_text().splitlines()]
    assert not any("--execute" in call for call in calls)
    summary = json.loads(
        (reports_dir / "crm_fixture_live_smoke_summary_unit-test.json").read_text()
    )
    assert summary["executeRequested"] is False
    assert summary["liveResultRecorded"] is False
    assert summary["requiredApproval"] == "crm:fixture:upsert:Leads:abc123:fixture-test"
    assert summary["payloadTemplatePlaceholders"] == {"emailCount": 0}


def test_crm_fixture_live_smoke_requires_env_for_execute(tmp_path: Path) -> None:
    fake_zoho, calls_path = _write_fake_zoho_for_crm_fixture_smoke(tmp_path)
    payload_file = tmp_path / "fixture.json"
    payload_file.write_text(json.dumps({"Last_Name": "Wang"}))

    result = subprocess.run(
        ["bash", str(CRM_FIXTURE_SMOKE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_BIN": str(fake_zoho),
            "FAKE_ZOHO_CALLS": str(calls_path),
            "ZOHO_CRM_FIXTURE_PAYLOAD_FILE": str(payload_file),
            "ZOHO_CRM_FIXTURE_REPORT_DIR": str(tmp_path / "reports"),
            "ZOHO_CRM_FIXTURE_IDEMPOTENCY_KEY": "fixture-test",
            "ZOHO_CRM_FIXTURE_CLEANUP_PLAN": "remove fixture record after validation",
            "ZOHO_CRM_FIXTURE_EXECUTE": "1",
            "ZOHO_CRM_FIXTURE_RUN_ID": "unit-test-execute",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 2, output
    assert "ZOHO_CRM_ALLOW_LIVE_FIXTURE_not_set" in output
    calls = [json.loads(line) for line in calls_path.read_text().splitlines()]
    assert not any("--execute" in call for call in calls)


def test_crm_fixture_live_smoke_blocks_placeholder_email_for_execute(
    tmp_path: Path,
) -> None:
    fake_zoho, calls_path = _write_fake_zoho_for_crm_fixture_smoke(tmp_path)
    payload_file = tmp_path / "fixture.json"
    payload_file.write_text(
        json.dumps(
            {
                "Last_Name": "ZohoCliFixtureReplaceMe",
                "Email": "zoho-cli-fixture+replace-me@example.invalid",
            }
        )
    )

    result = subprocess.run(
        ["bash", str(CRM_FIXTURE_SMOKE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_BIN": str(fake_zoho),
            "FAKE_ZOHO_CALLS": str(calls_path),
            "ZOHO_CRM_FIXTURE_PAYLOAD_FILE": str(payload_file),
            "ZOHO_CRM_FIXTURE_REPORT_DIR": str(tmp_path / "reports"),
            "ZOHO_CRM_FIXTURE_IDEMPOTENCY_KEY": "fixture-test",
            "ZOHO_CRM_FIXTURE_CLEANUP_PLAN": "remove fixture record after validation",
            "ZOHO_CRM_FIXTURE_EXECUTE": "1",
            "ZOHO_CRM_ALLOW_LIVE_FIXTURE": "1",
            "ZOHO_CRM_FIXTURE_RUN_ID": "unit-test-placeholder",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 2, output
    assert "fixture_payload_placeholder_email" in output
    calls = [json.loads(line) for line in calls_path.read_text().splitlines()]
    assert not any("--execute" in call for call in calls)


def test_openclaw_cliq_live_smoke_route_binding_only_mode(tmp_path: Path) -> None:
    config_path = tmp_path / "openclaw.json"
    report_path = tmp_path / "reports" / "route.json"
    config_path.write_text(
        json.dumps(
            {
                "bindings": [
                    {
                        "agentId": "zoho-employee-test",
                        "match": {"channel": "cliq", "accountId": "default"},
                    }
                ],
                "agents": {
                    "list": [
                        {
                            "id": "zoho-employee-test",
                            "model": "openai-codex/gpt-5.3-codex",
                        }
                    ]
                },
            }
        )
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_LIVE_SMOKE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_CONFIG_PATH": str(config_path),
            "ZOHO_CLIQ_ROUTE_BINDING_ONLY": "1",
            "ZOHO_CLIQ_ROUTE_REPORT_FILE": str(report_path),
            "ZOHO_CLIQ_SMOKE_RUN_ID": "unit-route-ok",
            "ZOHO_CLIQ_EXPECTED_AGENT_ID": "zoho-employee-test",
            "ZOHO_CLIQ_EXPECTED_AGENT_MODEL": "openai-codex/gpt-5.3-codex",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    assert "openclaw cliq route binding gate" in output
    assert '"agentId":"zoho-employee-test"' in output
    assert "zoho auth" not in output
    assert "local webhook missing-secret gate" not in output
    report = json.loads(report_path.read_text())
    assert report["schemaVersion"] == 1
    assert report["kind"] == "openclaw_cliq_route_preflight"
    assert report["runId"] == "unit-route-ok"
    assert "checkedAt" in report
    assert report["status"] == "ok"
    assert report["expectedAgentId"] == "zoho-employee-test"
    assert report["expectedModel"] == "openai-codex/gpt-5.3-codex"
    assert report["agentId"] == "zoho-employee-test"
    assert report["model"] == "openai-codex/gpt-5.3-codex"
    assert "configPath" not in report
    script = OPENCLAW_CLIQ_LIVE_SMOKE_SCRIPT.read_text()
    assert "ZOHO_CLIQ_EXPECTED_AGENT_ID" in script
    assert "ZOHO_CLIQ_EXPECTED_AGENT_MODEL" in script
    assert "ZOHO_CLIQ_EXPECTED_ACCOUNT_ID" in script
    assert "ZOHO_CLIQ_ROUTE_BINDING_ONLY" in script
    assert "ZOHO_CLIQ_ROUTE_REPORT_FILE" in script
    assert "OPENCLAW_CONFIG_PATH" in script
    assert 'match.channel === "cliq"' in script
    assert "agent_binding_mismatch" in script


def test_openclaw_cliq_live_smoke_route_binding_only_reports_mismatch(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "openclaw.json"
    report_path = tmp_path / "route-report.json"
    config_path.write_text(
        json.dumps(
            {
                "bindings": [
                    {
                        "agentId": "main",
                        "match": {"channel": "cliq", "accountId": "default"},
                    }
                ],
                "agents": {
                    "list": [
                        {"id": "main", "model": "openai-codex/gpt-5.3-codex"},
                        {
                            "id": "zoho-employee-test",
                            "model": "openai-codex/gpt-5.3-codex",
                        },
                    ]
                },
            }
        )
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_LIVE_SMOKE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_CONFIG_PATH": str(config_path),
            "ZOHO_CLIQ_ROUTE_BINDING_ONLY": "1",
            "ZOHO_CLIQ_ROUTE_REPORT_FILE": str(report_path),
            "ZOHO_CLIQ_SMOKE_RUN_ID": "unit-route-mismatch",
            "ZOHO_CLIQ_EXPECTED_AGENT_ID": "zoho-employee-test",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    payload_lines = [
        line
        for line in result.stdout.splitlines()
        if line.startswith("{") and '"status":"error"' in line
    ]
    assert len(payload_lines) == 1, output
    payload = json.loads(payload_lines[0])
    assert payload["schemaVersion"] == 1
    assert payload["kind"] == "openclaw_cliq_route_preflight"
    assert payload["runId"] == "unit-route-mismatch"
    assert payload["error"] == "agent_binding_mismatch"
    assert payload["expectedAgentId"] == "zoho-employee-test"
    assert payload["actualAgentId"] == "main"
    assert payload["channel"] == "cliq"
    assert payload["accountId"] == "default"
    assert "configPath" not in payload
    assert json.loads(report_path.read_text()) == payload
    assert "AssertionError" not in output


def test_openclaw_cliq_live_smoke_route_binding_only_requires_expected_agent() -> None:
    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_LIVE_SMOKE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CLIQ_ROUTE_BINDING_ONLY": "1",
            "ZOHO_CLIQ_SMOKE_RUN_ID": "unit-route-missing",
            "ZOHO_CLIQ_EXPECTED_AGENT_ID": "",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    payload_lines = [
        line
        for line in result.stdout.splitlines()
        if line.startswith("{") and '"status":"error"' in line
    ]
    assert len(payload_lines) == 1, output
    payload = json.loads(payload_lines[0])
    assert payload["schemaVersion"] == 1
    assert payload["kind"] == "openclaw_cliq_route_preflight"
    assert payload["runId"] == "unit-route-missing"
    assert payload["error"] == "expected_agent_missing"
    assert payload["channel"] == "cliq"
    assert payload["accountId"] == "default"
    assert "zoho auth" not in output
    assert "local webhook missing-secret gate" not in output


def test_openclaw_cliq_hash_ref_hashes_stdin_without_echoing_raw_id() -> None:
    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_HASH_REF_SCRIPT)],
        cwd=REPO_ROOT,
        input="raw-cliq-message-id",
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    assert result.stderr == ""
    assert result.stdout.startswith("sha256:")
    assert result.stdout.strip() == (
        "sha256:29faeea9d9156bf36ace510646aea6b156047547b1db6a53ed8541e37655b45f"
    )
    assert "raw-cliq-message-id" not in output


def test_openclaw_cliq_hash_ref_rejects_empty_input_without_stdout() -> None:
    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_HASH_REF_SCRIPT)],
        cwd=REPO_ROOT,
        input="",
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert json.loads(result.stderr)["error"] == "input_missing"


def _valid_openclaw_cliq_trusted_reply_evidence() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "kind": "openclaw_cliq_trusted_reply_evidence",
        "channel": "cliq",
        "accountId": "default",
        "routePreflight": {
            "status": "ok",
            "agentId": "zoho-employee-test",
            "model": "openai-codex/gpt-5.3-codex",
        },
        "publicCallbackVerified": True,
        "trustedMention": {
            "handler": "mention",
            "sentAt": "2026-05-05T20:48:51Z",
            "trustedSenderIdHash": "sha256:sender",
            "messageIdHash": "sha256:message",
        },
        "nativeDispatch": {
            "agentId": "zoho-employee-test",
            "agentModel": "openai-codex/gpt-5.3-codex",
            "agentTurnCount": 1,
            "deadLetterCount": 0,
            "duplicateDispatchCount": 0,
        },
        "delivery": {
            "replyDelivered": True,
            "cliqReplyCount": 1,
            "deliveryIdHash": "sha256:reply",
        },
        "redaction": {
            "rawWebhookPayloadStored": False,
            "rawMessageBodyStored": False,
            "rawCliqReplyBodyStored": False,
            "secretsStored": False,
        },
    }


def test_openclaw_cliq_trusted_reply_evidence_accepts_redacted_gate(
    tmp_path: Path,
) -> None:
    evidence_path = tmp_path / "trusted-reply.json"
    report_path = tmp_path / "reports" / "trusted-reply-report.json"
    evidence_path.write_text(json.dumps(_valid_openclaw_cliq_trusted_reply_evidence()))

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CLIQ_TRUSTED_REPLY_EVIDENCE_FILE": str(evidence_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_REPORT_FILE": str(report_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID": "unit-trusted-ok",
            "ZOHO_CLIQ_EXPECTED_AGENT_ID": "zoho-employee-test",
            "ZOHO_CLIQ_EXPECTED_AGENT_MODEL": "openai-codex/gpt-5.3-codex",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    payload = json.loads(result.stdout)
    assert payload["schemaVersion"] == 1
    assert payload["kind"] == "openclaw_cliq_trusted_reply_evidence_check"
    assert payload["runId"] == "unit-trusted-ok"
    assert payload["status"] == "trusted_reply_recorded"
    assert payload["blockingReasons"] == []
    assert payload["agentId"] == "zoho-employee-test"
    assert payload["agentTurnCount"] == 1
    assert payload["cliqReplyCount"] == 1
    assert payload["trustedMention"] == {
        "handler": "mention",
        "trustedSenderIdHashPresent": True,
        "messageIdHashPresent": True,
    }
    assert payload["deliveryIdHashPresent"] is True
    assert payload["redaction"]["secretMarkerPresent"] is False
    assert "trusted-reply.json" == payload["evidenceFile"]
    assert "configPath" not in payload
    assert json.loads(report_path.read_text()) == payload


def test_openclaw_cliq_trusted_reply_evidence_reports_blockers(
    tmp_path: Path,
) -> None:
    evidence_path = tmp_path / "trusted-reply-bad.json"
    evidence_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "kind": "openclaw_cliq_trusted_reply_evidence",
                "channel": "cliq",
                "accountId": "default",
                "routePreflight": {"status": "error", "agentId": "main"},
                "publicCallbackVerified": False,
                "trustedMention": {
                    "handler": "message",
                    "trustedSenderIdHash": "sender-raw",
                    "messageIdHash": "",
                },
                "nativeDispatch": {
                    "agentId": "main",
                    "agentTurnCount": 2,
                    "deadLetterCount": 1,
                    "duplicateDispatchCount": 1,
                },
                "delivery": {
                    "replyDelivered": False,
                    "cliqReplyCount": 0,
                    "deliveryIdHash": "",
                },
                "redaction": {
                    "rawWebhookPayloadStored": False,
                    "rawMessageBodyStored": False,
                    "rawCliqReplyBodyStored": False,
                    "secretsStored": False,
                },
            }
        )
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CLIQ_TRUSTED_REPLY_EVIDENCE_FILE": str(evidence_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID": "unit-trusted-bad",
            "ZOHO_CLIQ_EXPECTED_AGENT_ID": "zoho-employee-test",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    payload = json.loads(result.stdout)
    assert payload["status"] == "incomplete"
    assert payload["blockingReasons"] == [
        "route_preflight_not_ok",
        "public_callback_not_verified",
        "trusted_mention_handler_invalid",
        "trusted_sender_hash_missing",
        "trusted_message_hash_missing",
        "agent_mismatch",
        "agent_turn_count_not_one",
        "cliq_reply_count_not_one",
        "reply_not_delivered",
        "delivery_id_hash_missing",
        "dead_letter_count_not_zero",
        "duplicate_dispatch_count_not_zero",
    ]


def test_openclaw_cliq_trusted_reply_template_cannot_pass_unchanged() -> None:
    template_path = (
        REPO_ROOT
        / "docs"
        / "releases"
        / "OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_TEMPLATE.json"
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CLIQ_TRUSTED_REPLY_EVIDENCE_FILE": str(template_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID": "unit-template-placeholder",
            "ZOHO_CLIQ_EXPECTED_AGENT_ID": "zoho-employee-test",
            "ZOHO_CLIQ_EXPECTED_AGENT_MODEL": "openai-codex/gpt-5.3-codex",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    payload = json.loads(result.stdout)
    assert payload["status"] == "incomplete"
    assert (
        payload["evidenceFile"] == "OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_TEMPLATE.json"
    )
    assert payload["blockingReasons"] == [
        "route_preflight_not_ok",
        "public_callback_not_verified",
        "trusted_sender_hash_missing",
        "trusted_message_hash_missing",
        "agent_turn_count_not_one",
        "cliq_reply_count_not_one",
        "reply_not_delivered",
        "delivery_id_hash_missing",
    ]


def test_openclaw_cliq_trusted_reply_evidence_blocks_secret_markers(
    tmp_path: Path,
) -> None:
    evidence = _valid_openclaw_cliq_trusted_reply_evidence()
    evidence["diagnostic"] = "redacted X-Cliq-Webhook-Secret header marker"
    evidence_path = tmp_path / "trusted-reply-secret-marker.json"
    evidence_path.write_text(json.dumps(evidence))

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CLIQ_TRUSTED_REPLY_EVIDENCE_FILE": str(evidence_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID": "unit-secret-marker",
            "ZOHO_CLIQ_EXPECTED_AGENT_ID": "zoho-employee-test",
            "ZOHO_CLIQ_EXPECTED_AGENT_MODEL": "openai-codex/gpt-5.3-codex",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    payload = json.loads(result.stdout)
    assert payload["status"] == "incomplete"
    assert payload["blockingReasons"] == ["secret_marker_present"]
    assert payload["redaction"]["secretMarkerPresent"] is True


def test_openclaw_cliq_trusted_reply_evidence_prepare_creates_checkable_artifact(
    tmp_path: Path,
) -> None:
    route_path = tmp_path / "route.json"
    evidence_path = tmp_path / "reports" / "trusted-reply.json"
    route_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "kind": "openclaw_cliq_route_preflight",
                "status": "ok",
                "accountId": "default",
                "agentId": "zoho-employee-test",
                "model": "openai-codex/gpt-5.3-codex",
            }
        )
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_PREPARE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CLIQ_ROUTE_REPORT_FILE": str(route_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_EVIDENCE_FILE": str(evidence_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID": "unit-prepare-ok",
            "ZOHO_CLIQ_TRUSTED_MENTION_SENT_AT": "2026-05-05T22:10:51Z",
            "ZOHO_CLIQ_TRUSTED_SENDER_ID_HASH": "sha256:sender",
            "ZOHO_CLIQ_TRUSTED_MESSAGE_ID_HASH": "sha256:message",
            "ZOHO_CLIQ_DELIVERY_ID_HASH": "sha256:reply",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    payload = json.loads(result.stdout)
    assert json.loads(evidence_path.read_text()) == payload
    assert payload["kind"] == "openclaw_cliq_trusted_reply_evidence"
    assert payload["routePreflight"] == {
        "status": "ok",
        "agentId": "zoho-employee-test",
        "model": "openai-codex/gpt-5.3-codex",
    }
    assert payload["trustedMention"]["trustedSenderIdHash"] == "sha256:sender"
    assert payload["trustedMention"]["messageIdHash"] == "sha256:message"
    assert payload["delivery"]["deliveryIdHash"] == "sha256:reply"
    assert payload["redaction"] == {
        "rawWebhookPayloadStored": False,
        "rawMessageBodyStored": False,
        "rawCliqReplyBodyStored": False,
        "secretsStored": False,
    }
    assert "configPath" not in payload

    check_result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CLIQ_TRUSTED_REPLY_EVIDENCE_FILE": str(evidence_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID": "unit-prepare-check",
            "ZOHO_CLIQ_EXPECTED_AGENT_ID": "zoho-employee-test",
            "ZOHO_CLIQ_EXPECTED_AGENT_MODEL": "openai-codex/gpt-5.3-codex",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    check_output = f"{check_result.stdout}\n{check_result.stderr}"
    assert check_result.returncode == 0, check_output
    assert json.loads(check_result.stdout)["status"] == "trusted_reply_recorded"


def test_openclaw_cliq_trusted_reply_evidence_prepare_rejects_raw_ids(
    tmp_path: Path,
) -> None:
    route_path = tmp_path / "route.json"
    evidence_path = tmp_path / "trusted-reply.json"
    route_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "kind": "openclaw_cliq_route_preflight",
                "status": "ok",
                "accountId": "default",
                "agentId": "zoho-employee-test",
                "model": "openai-codex/gpt-5.3-codex",
            }
        )
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_PREPARE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CLIQ_ROUTE_REPORT_FILE": str(route_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_EVIDENCE_FILE": str(evidence_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID": "unit-prepare-raw",
            "ZOHO_CLIQ_TRUSTED_SENDER_ID_HASH": "sender-raw",
            "ZOHO_CLIQ_TRUSTED_MESSAGE_ID_HASH": "sha256:message",
            "ZOHO_CLIQ_DELIVERY_ID_HASH": "sha256:reply",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 2, output
    payload = json.loads(result.stdout)
    assert payload["kind"] == "openclaw_cliq_trusted_reply_evidence_prepare"
    assert payload["status"] == "error"
    assert payload["error"] == "trusted_sender_hash_missing"
    assert not evidence_path.exists()


def _sha256_ref(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode()).hexdigest()}"


def test_openclaw_cliq_trusted_reply_bundle_hashes_raw_ids_and_checks(
    tmp_path: Path,
) -> None:
    route_path = tmp_path / "route.json"
    evidence_path = tmp_path / "reports" / "trusted-reply.json"
    check_path = tmp_path / "reports" / "trusted-reply-check.json"
    route_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "kind": "openclaw_cliq_route_preflight",
                "status": "ok",
                "accountId": "default",
                "agentId": "zoho-employee-test",
                "model": "openai-codex/gpt-5.3-codex",
            }
        )
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_BUNDLE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CLIQ_ROUTE_REPORT_FILE": str(route_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_EVIDENCE_FILE": str(evidence_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_REPORT_FILE": str(check_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID": "unit-bundle-ok",
            "ZOHO_CLIQ_TRUSTED_MENTION_SENT_AT": "2026-05-05T23:36:22Z",
            "ZOHO_CLIQ_TRUSTED_SENDER_ID": "sender-raw-id",
            "ZOHO_CLIQ_TRUSTED_MESSAGE_ID": "message-raw-id",
            "ZOHO_CLIQ_DELIVERY_ID": "delivery-raw-id",
            "ZOHO_CLIQ_EXPECTED_AGENT_ID": "zoho-employee-test",
            "ZOHO_CLIQ_EXPECTED_AGENT_MODEL": "openai-codex/gpt-5.3-codex",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    assert "sender-raw-id" not in output
    assert "message-raw-id" not in output
    assert "delivery-raw-id" not in output

    check_payload = json.loads(result.stdout)
    assert check_payload["status"] == "trusted_reply_recorded"
    assert json.loads(check_path.read_text()) == check_payload

    evidence = json.loads(evidence_path.read_text())
    assert evidence["trustedMention"]["trustedSenderIdHash"] == _sha256_ref(
        "sender-raw-id"
    )
    assert evidence["trustedMention"]["messageIdHash"] == _sha256_ref("message-raw-id")
    assert evidence["delivery"]["deliveryIdHash"] == _sha256_ref("delivery-raw-id")
    assert "sender-raw-id" not in evidence_path.read_text()
    assert "message-raw-id" not in evidence_path.read_text()
    assert "delivery-raw-id" not in evidence_path.read_text()


def test_openclaw_cliq_trusted_reply_bundle_auto_runs_route_preflight(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "openclaw.json"
    reports_dir = tmp_path / "reports"
    config_path.write_text(
        json.dumps(
            {
                "bindings": [
                    {
                        "agentId": "zoho-employee-test",
                        "match": {"channel": "cliq", "accountId": "default"},
                    }
                ],
                "agents": {
                    "list": [
                        {
                            "id": "zoho-employee-test",
                            "model": "openai-codex/gpt-5.3-codex",
                        }
                    ]
                },
            }
        )
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_BUNDLE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_CONFIG_PATH": str(config_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_REPORT_DIR": str(reports_dir),
            "ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID": "unit-bundle-route",
            "ZOHO_CLIQ_TRUSTED_SENDER_ID_HASH": "sha256:sender",
            "ZOHO_CLIQ_TRUSTED_MESSAGE_ID_HASH": "sha256:message",
            "ZOHO_CLIQ_DELIVERY_ID_HASH": "sha256:reply",
            "ZOHO_CLIQ_EXPECTED_AGENT_ID": "zoho-employee-test",
            "ZOHO_CLIQ_EXPECTED_AGENT_MODEL": "openai-codex/gpt-5.3-codex",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    assert "openclaw cliq route binding gate" not in output
    payload = json.loads(result.stdout)
    assert payload["status"] == "trusted_reply_recorded"

    route_report = reports_dir / "openclaw_cliq_route_preflight_unit-bundle-route.json"
    evidence_report = reports_dir / "openclaw_cliq_trusted_reply_unit-bundle-route.json"
    check_report = (
        reports_dir / "openclaw_cliq_trusted_reply_check_unit-bundle-route.json"
    )
    assert json.loads(route_report.read_text())["status"] == "ok"
    assert json.loads(evidence_report.read_text())["routePreflight"]["status"] == "ok"
    assert json.loads(check_report.read_text()) == payload


def test_openclaw_cliq_trusted_reply_bundle_plan_only_lists_missing_live_facts(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "openclaw.json"
    reports_dir = tmp_path / "reports"
    config_path.write_text(
        json.dumps(
            {
                "bindings": [
                    {
                        "agentId": "zoho-employee-test",
                        "match": {"channel": "cliq", "accountId": "default"},
                    }
                ],
                "agents": {
                    "list": [
                        {
                            "id": "zoho-employee-test",
                            "model": "openai-codex/gpt-5.3-codex",
                        }
                    ]
                },
            }
        )
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_BUNDLE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_CONFIG_PATH": str(config_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_PLAN_ONLY": "1",
            "ZOHO_CLIQ_TRUSTED_REPLY_REPORT_DIR": str(reports_dir),
            "ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID": "unit-bundle-plan",
            "ZOHO_CLIQ_EXPECTED_AGENT_ID": "zoho-employee-test",
            "ZOHO_CLIQ_EXPECTED_AGENT_MODEL": "openai-codex/gpt-5.3-codex",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["kind"] == "openclaw_cliq_trusted_reply_evidence_bundle_plan"
    assert payload["status"] == "awaiting_live_delivery_facts"
    assert payload["routeReportReady"] is True
    assert payload["facts"] == {
        "trustedSenderId": "missing",
        "trustedMessageId": "missing",
        "deliveryId": "missing",
    }
    assert payload["missingFacts"] == [
        "trustedSenderId",
        "trustedMessageId",
        "deliveryId",
    ]
    assert payload["readyFacts"] == []
    assert payload["nextAction"] == "collect_live_delivery_facts"
    assert payload["readyForFinalBundle"] is False
    assert payload["acceptedFactStates"] == ["hash", "raw"]
    assert (
        "ZOHO_CLIQ_DELIVERY_ID_HASH or ZOHO_CLIQ_DELIVERY_ID" in payload["requiredEnv"]
    )
    assert (
        payload["nextCommand"]
        == "ops/scripts/openclaw_cliq_trusted_reply_evidence_bundle.sh"
    )

    route_report = reports_dir / "openclaw_cliq_route_preflight_unit-bundle-plan.json"
    plan_report = reports_dir / "openclaw_cliq_trusted_reply_plan_unit-bundle-plan.json"
    evidence_report = reports_dir / "openclaw_cliq_trusted_reply_unit-bundle-plan.json"
    check_report = (
        reports_dir / "openclaw_cliq_trusted_reply_check_unit-bundle-plan.json"
    )
    assert json.loads(route_report.read_text())["status"] == "ok"
    assert json.loads(plan_report.read_text()) == payload
    assert not evidence_report.exists()
    assert not check_report.exists()


def test_openclaw_cliq_trusted_reply_bundle_plan_only_redacts_ready_raw_facts(
    tmp_path: Path,
) -> None:
    route_path = tmp_path / "route.json"
    reports_dir = tmp_path / "reports"
    route_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "kind": "openclaw_cliq_route_preflight",
                "status": "ok",
                "accountId": "default",
                "agentId": "zoho-employee-test",
                "model": "openai-codex/gpt-5.3-codex",
            }
        )
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_BUNDLE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CLIQ_ROUTE_REPORT_FILE": str(route_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_PLAN_ONLY": "1",
            "ZOHO_CLIQ_TRUSTED_REPLY_REPORT_DIR": str(reports_dir),
            "ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID": "unit-bundle-plan-ready",
            "ZOHO_CLIQ_TRUSTED_SENDER_ID": "sender-raw-id",
            "ZOHO_CLIQ_TRUSTED_MESSAGE_ID": "message-raw-id",
            "ZOHO_CLIQ_DELIVERY_ID": "delivery-raw-id",
            "ZOHO_CLIQ_EXPECTED_AGENT_ID": "zoho-employee-test",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    assert "sender-raw-id" not in output
    assert "message-raw-id" not in output
    assert "delivery-raw-id" not in output

    payload = json.loads(result.stdout)
    assert payload["status"] == "ready_for_bundle_check"
    assert payload["facts"] == {
        "trustedSenderId": "raw",
        "trustedMessageId": "raw",
        "deliveryId": "raw",
    }
    assert payload["missingFacts"] == []
    assert payload["readyFacts"] == [
        "trustedSenderId",
        "trustedMessageId",
        "deliveryId",
    ]
    assert payload["nextAction"] == "run_final_trusted_reply_bundle"
    assert payload["readyForFinalBundle"] is True

    plan_report = (
        reports_dir / "openclaw_cliq_trusted_reply_plan_unit-bundle-plan-ready.json"
    )
    evidence_report = (
        reports_dir / "openclaw_cliq_trusted_reply_unit-bundle-plan-ready.json"
    )
    check_report = (
        reports_dir / "openclaw_cliq_trusted_reply_check_unit-bundle-plan-ready.json"
    )
    assert json.loads(plan_report.read_text()) == payload
    assert "sender-raw-id" not in plan_report.read_text()
    assert "message-raw-id" not in plan_report.read_text()
    assert "delivery-raw-id" not in plan_report.read_text()
    assert not evidence_report.exists()
    assert not check_report.exists()


def test_openclaw_cliq_trusted_reply_bundle_reports_missing_agent(
    tmp_path: Path,
) -> None:
    route_path = tmp_path / "route.json"
    route_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "kind": "openclaw_cliq_route_preflight",
                "status": "ok",
            }
        )
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_BUNDLE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CLIQ_ROUTE_REPORT_FILE": str(route_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID": "unit-bundle-missing-agent",
            "ZOHO_CLIQ_EXPECTED_AGENT_ID": "",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["kind"] == "openclaw_cliq_trusted_reply_evidence_bundle"
    assert payload["error"] == "expected_agent_missing"


def test_openclaw_cliq_trusted_reply_bundle_stops_on_route_mismatch(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "openclaw.json"
    reports_dir = tmp_path / "reports"
    config_path.write_text(
        json.dumps(
            {
                "bindings": [
                    {
                        "agentId": "main",
                        "match": {"channel": "cliq", "accountId": "default"},
                    }
                ],
                "agents": {
                    "list": [
                        {"id": "main", "model": "openai-codex/gpt-5.3-codex"},
                        {
                            "id": "zoho-employee-test",
                            "model": "openai-codex/gpt-5.3-codex",
                        },
                    ]
                },
            }
        )
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_BUNDLE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_CONFIG_PATH": str(config_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_REPORT_DIR": str(reports_dir),
            "ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID": "unit-bundle-route-mismatch",
            "ZOHO_CLIQ_TRUSTED_SENDER_ID_HASH": "sha256:sender",
            "ZOHO_CLIQ_TRUSTED_MESSAGE_ID_HASH": "sha256:message",
            "ZOHO_CLIQ_DELIVERY_ID_HASH": "sha256:reply",
            "ZOHO_CLIQ_EXPECTED_AGENT_ID": "zoho-employee-test",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    assert "openclaw cliq route binding gate" not in output
    payload = json.loads(result.stdout)
    assert payload["kind"] == "openclaw_cliq_route_preflight"
    assert payload["error"] == "agent_binding_mismatch"
    assert payload["expectedAgentId"] == "zoho-employee-test"
    assert payload["actualAgentId"] == "main"

    route_report = (
        reports_dir / "openclaw_cliq_route_preflight_unit-bundle-route-mismatch.json"
    )
    evidence_report = (
        reports_dir / "openclaw_cliq_trusted_reply_unit-bundle-route-mismatch.json"
    )
    check_report = (
        reports_dir
        / "openclaw_cliq_trusted_reply_check_unit-bundle-route-mismatch.json"
    )
    assert json.loads(route_report.read_text()) == payload
    assert not evidence_report.exists()
    assert not check_report.exists()


def test_openclaw_cliq_trusted_reply_bundle_reports_missing_hash(
    tmp_path: Path,
) -> None:
    route_path = tmp_path / "route.json"
    route_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "kind": "openclaw_cliq_route_preflight",
                "status": "ok",
            }
        )
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_BUNDLE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CLIQ_ROUTE_REPORT_FILE": str(route_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID": "unit-bundle-missing-hash",
            "ZOHO_CLIQ_EXPECTED_AGENT_ID": "zoho-employee-test",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["kind"] == "openclaw_cliq_trusted_reply_evidence_bundle"
    assert payload["error"] == "trusted_sender_hash_missing"
