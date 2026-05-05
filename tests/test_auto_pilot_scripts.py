from __future__ import annotations

import os
import json
import stat
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPORT_RECHECK_SCRIPT = (
    REPO_ROOT / "tests" / "auto_pilot" / "run_cliq_export_scope_recheck.sh"
)
CRM_FIXTURE_SMOKE_SCRIPT = REPO_ROOT / "ops" / "scripts" / "crm_fixture_live_smoke.sh"


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
