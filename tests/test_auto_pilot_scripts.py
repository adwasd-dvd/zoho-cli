from __future__ import annotations

import os
import hashlib
import io
import json
import stat
import subprocess
import tarfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPORT_RECHECK_SCRIPT = (
    REPO_ROOT / "tests" / "auto_pilot" / "run_cliq_export_scope_recheck.sh"
)
CRM_FIXTURE_SMOKE_SCRIPT = REPO_ROOT / "ops" / "scripts" / "crm_fixture_live_smoke.sh"
CRM_FIXTURE_PAYLOAD_PREFLIGHT_SCRIPT = (
    REPO_ROOT / "ops" / "scripts" / "crm_fixture_payload_preflight.sh"
)
CRM_FIXTURE_READINESS_BUNDLE_SCRIPT = (
    REPO_ROOT / "ops" / "scripts" / "crm_fixture_operator_readiness_bundle.sh"
)
CRM_FIXTURE_OPERATOR_PACKET_SCRIPT = (
    REPO_ROOT / "ops" / "scripts" / "crm_fixture_operator_packet.sh"
)
OPENCLAW_CLIQ_LIVE_SMOKE_SCRIPT = (
    REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_live_smoke.sh"
)
OPENCLAW_CLIQ_PUBLIC_CALLBACK_SMOKE_SCRIPT = (
    REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_public_callback_smoke.sh"
)
OPENCLAW_CLIQ_LIVE_INGRESS_DIAGNOSTIC_SCRIPT = (
    REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_live_ingress_diagnostic.sh"
)
OPENCLAW_CLIQ_BOT_NO_RESPONSE_PACKET_SCRIPT = (
    REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_bot_no_response_packet.sh"
)
OPENCLAW_CLIQ_HANDLER_TRIGGER_PACKET_SCRIPT = (
    REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_handler_trigger_packet.sh"
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
OPENCLAW_CLIQ_TRUSTED_REPLY_FACTS_PREPARE_SCRIPT = (
    REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_trusted_reply_facts_prepare.sh"
)
OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_BUNDLE_SCRIPT = (
    REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_trusted_reply_evidence_bundle.sh"
)
OPENCLAW_CLIQ_RC_PACK_SCRIPT = (
    REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_rc_pack.sh"
)
OPENCLAW_CLIQ_RC_PROMOTION_CHECK_SCRIPT = (
    REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_rc_promotion_check.sh"
)
OPENCLAW_CLIQ_RC_ARTIFACT_CHECK_SCRIPT = (
    REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_rc_artifact_check.sh"
)
OPENCLAW_CLIQ_RC_INSTALL_SMOKE_SCRIPT = (
    REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_rc_install_smoke.sh"
)
OPENCLAW_CLIQ_RC_OPERATOR_PUBLISH_BUNDLE_SCRIPT = (
    REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_rc_operator_publish_bundle.sh"
)
OPENCLAW_CLIQ_RC_RELEASE_NOTES_DRAFT_SCRIPT = (
    REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_rc_release_notes_draft.sh"
)
OPENCLAW_CLIQ_RC_PUBLISH_PLAN_SCRIPT = (
    REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_rc_publish_plan.sh"
)
OPENCLAW_CLIQ_RC_HANDOFF_MANIFEST_SCRIPT = (
    REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_rc_operator_handoff_manifest.sh"
)
OPENCLAW_CLIQ_RC_SOURCE_DRIFT_CHECK_SCRIPT = (
    REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_rc_source_drift_check.sh"
)
OPENCLAW_CLIQ_RC_SELECTION_REVIEW_SCRIPT = (
    REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_rc_operator_selection_review.sh"
)
OPENCLAW_CLIQ_RC_DECISION_PACKET_SCRIPT = (
    REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_rc_operator_decision_packet.sh"
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


def test_openclaw_cliq_rc_promotion_check_requires_ready_local_evidence(
    tmp_path: Path,
) -> None:
    package_json = tmp_path / "package.json"
    package_json.write_text(
        json.dumps(
            {
                "name": "@adwasd/openclaw-zoho-cliq",
                "version": "0.4.0-rc.1",
                "openclaw": {
                    "install": {
                        "expectedIntegrity": "<filled-at-release>",
                    }
                },
            }
        )
    )
    pack_summary = tmp_path / "pack-summary.json"
    pack_summary.write_text(
        json.dumps(
            {
                "status": "passed",
                "pack": {
                    "name": "@adwasd/openclaw-zoho-cliq",
                    "version": "0.4.0-rc.1",
                    "filename": "adwasd-openclaw-zoho-cliq-0.4.0-rc.1.tgz",
                    "integrity": "sha512-test",
                    "shasum": "abc123",
                },
                "releasePosture": {
                    "publishPerformed": False,
                    "versionBumped": False,
                },
            }
        )
    )
    trusted_reply = tmp_path / "trusted-reply-check.json"
    trusted_reply.write_text(
        json.dumps(
            {
                "status": "trusted_reply_recorded",
                "redaction": {
                    "rawWebhookPayloadStored": False,
                    "rawMessageBodyStored": False,
                    "rawCliqReplyBodyStored": False,
                    "secretsStored": False,
                    "secretMarkerPresent": False,
                },
            }
        )
    )
    artifact_report = tmp_path / "artifact-check.json"
    artifact_report.write_text(
        json.dumps(
            {
                "status": "artifact_verified",
                "artifact": {
                    "filename": "adwasd-openclaw-zoho-cliq-0.4.0-rc.1.tgz",
                    "shasum": "abc123",
                    "shasumMatchesPackSummary": True,
                },
                "package": {
                    "name": "@adwasd/openclaw-zoho-cliq",
                    "version": "0.4.0-rc.1",
                    "expectedIntegrityState": "placeholder",
                },
            }
        )
    )
    install_smoke = tmp_path / "install-smoke.json"
    install_smoke.write_text(
        json.dumps(
            {
                "status": "install_smoke_passed",
                "artifact": {
                    "status": "artifact_verified",
                },
                "source": {
                    "type": "artifact",
                    "filename": "adwasd-openclaw-zoho-cliq-0.4.0-rc.1.tgz",
                },
                "commands": [
                    {"name": "install", "status": "passed", "exitCode": 0},
                    {"name": "inspect", "status": "passed", "exitCode": 0},
                    {"name": "doctor", "status": "passed", "exitCode": 0},
                ],
                "releasePosture": {
                    "publishPerformed": False,
                    "versionBumped": False,
                },
            }
        )
    )
    report_file = tmp_path / "promotion-check.json"

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_RC_PROMOTION_CHECK_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_CLIQ_PACKAGE_JSON": str(package_json),
            "OPENCLAW_CLIQ_PACK_SUMMARY_FILE": str(pack_summary),
            "OPENCLAW_CLIQ_ARTIFACT_REPORT_FILE": str(artifact_report),
            "OPENCLAW_CLIQ_INSTALL_SMOKE_FILE": str(install_smoke),
            "OPENCLAW_CLIQ_TRUSTED_REPLY_CHECK_FILE": str(trusted_reply),
            "OPENCLAW_CLIQ_PROMOTION_REPORT_FILE": str(report_file),
            "OPENCLAW_CLIQ_PROMOTION_RUN_ID": "unit-test",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    payload = json.loads(result.stdout)
    assert payload["status"] == "ready_for_operator_publish"
    assert payload["blockers"] == []
    assert payload["package"]["expectedIntegrityState"] == "placeholder"
    assert payload["pack"]["publishPerformed"] is False
    assert payload["pack"]["versionBumped"] is False
    assert payload["artifact"]["status"] == "artifact_verified"
    assert payload["artifact"]["shasumMatchesPackSummary"] is True
    assert payload["installSmoke"]["status"] == "install_smoke_passed"
    assert [command["status"] for command in payload["installSmoke"]["commandStatuses"]]
    assert payload["releasePosture"] == {
        "publishPerformed": False,
        "tagCreated": False,
        "npmPromotionRequiresOperatorApproval": True,
        "expectedIntegrityAction": "fill_after_publish",
    }
    assert json.loads(report_file.read_text()) == payload


def test_openclaw_cliq_rc_promotion_check_blocks_published_integrity_too_early(
    tmp_path: Path,
) -> None:
    package_json = tmp_path / "package.json"
    package_json.write_text(
        json.dumps(
            {
                "name": "@adwasd/openclaw-zoho-cliq",
                "version": "0.4.0-rc.1",
                "openclaw": {
                    "install": {
                        "expectedIntegrity": "sha512-already-filled",
                    }
                },
            }
        )
    )
    pack_summary = tmp_path / "pack-summary.json"
    pack_summary.write_text(
        json.dumps(
            {
                "status": "passed",
                "pack": {
                    "name": "@adwasd/openclaw-zoho-cliq",
                    "version": "0.4.0-rc.1",
                },
                "releasePosture": {
                    "publishPerformed": False,
                    "versionBumped": False,
                },
            }
        )
    )
    trusted_reply = tmp_path / "trusted-reply-check.json"
    trusted_reply.write_text(
        json.dumps(
            {
                "status": "trusted_reply_recorded",
                "redaction": {
                    "rawWebhookPayloadStored": False,
                    "rawMessageBodyStored": False,
                    "rawCliqReplyBodyStored": False,
                    "secretsStored": False,
                    "secretMarkerPresent": False,
                },
            }
        )
    )
    artifact_report = tmp_path / "artifact-check.json"
    artifact_report.write_text(
        json.dumps(
            {
                "status": "artifact_verified",
                "artifact": {"shasumMatchesPackSummary": True},
                "package": {
                    "name": "@adwasd/openclaw-zoho-cliq",
                    "version": "0.4.0-rc.1",
                    "expectedIntegrityState": "placeholder",
                },
            }
        )
    )
    install_smoke = tmp_path / "install-smoke.json"
    install_smoke.write_text(
        json.dumps(
            {
                "status": "install_smoke_passed",
                "artifact": {"status": "artifact_verified"},
                "releasePosture": {
                    "publishPerformed": False,
                    "versionBumped": False,
                },
            }
        )
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_RC_PROMOTION_CHECK_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_CLIQ_PACKAGE_JSON": str(package_json),
            "OPENCLAW_CLIQ_PACK_SUMMARY_FILE": str(pack_summary),
            "OPENCLAW_CLIQ_ARTIFACT_REPORT_FILE": str(artifact_report),
            "OPENCLAW_CLIQ_INSTALL_SMOKE_FILE": str(install_smoke),
            "OPENCLAW_CLIQ_TRUSTED_REPLY_CHECK_FILE": str(trusted_reply),
            "OPENCLAW_CLIQ_PROMOTION_REPORT_FILE": str(tmp_path / "report.json"),
            "OPENCLAW_CLIQ_PROMOTION_RUN_ID": "unit-test-blocked",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert "expected_integrity_not_placeholder" in payload["blockers"]


def test_openclaw_cliq_rc_promotion_check_requires_install_smoke(
    tmp_path: Path,
) -> None:
    package_json = tmp_path / "package.json"
    package_json.write_text(
        json.dumps(
            {
                "name": "@adwasd/openclaw-zoho-cliq",
                "version": "0.4.0-rc.1",
                "openclaw": {"install": {"expectedIntegrity": "<filled-at-release>"}},
            }
        )
    )
    pack_summary = tmp_path / "pack-summary.json"
    pack_summary.write_text(
        json.dumps(
            {
                "status": "passed",
                "pack": {
                    "name": "@adwasd/openclaw-zoho-cliq",
                    "version": "0.4.0-rc.1",
                },
                "releasePosture": {
                    "publishPerformed": False,
                    "versionBumped": False,
                },
            }
        )
    )
    artifact_report = tmp_path / "artifact-check.json"
    artifact_report.write_text(
        json.dumps(
            {
                "status": "artifact_verified",
                "artifact": {"shasumMatchesPackSummary": True},
                "package": {
                    "name": "@adwasd/openclaw-zoho-cliq",
                    "version": "0.4.0-rc.1",
                    "expectedIntegrityState": "placeholder",
                },
            }
        )
    )
    trusted_reply = tmp_path / "trusted-reply-check.json"
    trusted_reply.write_text(
        json.dumps(
            {
                "status": "trusted_reply_recorded",
                "redaction": {
                    "rawWebhookPayloadStored": False,
                    "rawMessageBodyStored": False,
                    "rawCliqReplyBodyStored": False,
                    "secretsStored": False,
                    "secretMarkerPresent": False,
                },
            }
        )
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_RC_PROMOTION_CHECK_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_CLIQ_PACKAGE_JSON": str(package_json),
            "OPENCLAW_CLIQ_PACK_SUMMARY_FILE": str(pack_summary),
            "OPENCLAW_CLIQ_ARTIFACT_REPORT_FILE": str(artifact_report),
            "OPENCLAW_CLIQ_INSTALL_SMOKE_FILE": str(tmp_path / "missing-install.json"),
            "OPENCLAW_CLIQ_TRUSTED_REPLY_CHECK_FILE": str(trusted_reply),
            "OPENCLAW_CLIQ_PROMOTION_REPORT_FILE": str(tmp_path / "report.json"),
            "OPENCLAW_CLIQ_PROMOTION_RUN_ID": "unit-test-missing-install",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert "install_smoke_missing" in payload["blockers"]
    assert "install_smoke_not_passed" in payload["blockers"]


def test_openclaw_cliq_rc_operator_publish_bundle_collects_ready_evidence(
    tmp_path: Path,
) -> None:
    pack_summary = tmp_path / "pack-summary.json"
    pack_summary.write_text(
        json.dumps(
            {
                "status": "passed",
                "pack": {
                    "name": "@adwasd/openclaw-zoho-cliq",
                    "version": "0.4.0-rc.1",
                    "filename": "adwasd-openclaw-zoho-cliq-0.4.0-rc.1.tgz",
                    "integrity": "sha512-test",
                    "shasum": "abc123",
                    "tarballPath": str(tmp_path / "private" / "artifact.tgz"),
                },
                "releasePosture": {
                    "publishPerformed": False,
                    "versionBumped": False,
                },
            }
        )
    )
    artifact_report = tmp_path / "artifact-check.json"
    artifact_report.write_text(
        json.dumps(
            {
                "status": "artifact_verified",
                "artifact": {
                    "filename": "adwasd-openclaw-zoho-cliq-0.4.0-rc.1.tgz",
                    "shasum": "abc123",
                    "shasumMatchesPackSummary": True,
                },
                "package": {
                    "name": "@adwasd/openclaw-zoho-cliq",
                    "version": "0.4.0-rc.1",
                    "expectedIntegrityState": "placeholder",
                },
            }
        )
    )
    install_smoke = tmp_path / "install-smoke.json"
    install_smoke.write_text(
        json.dumps(
            {
                "status": "install_smoke_passed",
                "artifact": {"status": "artifact_verified"},
                "commands": [
                    {"name": "install", "status": "passed", "exitCode": 0},
                    {"name": "inspect", "status": "passed", "exitCode": 0},
                    {"name": "doctor", "status": "passed", "exitCode": 0},
                ],
                "releasePosture": {
                    "publishPerformed": False,
                    "versionBumped": False,
                },
            }
        )
    )
    promotion = tmp_path / "promotion-check.json"
    promotion.write_text(
        json.dumps(
            {
                "status": "ready_for_operator_publish",
                "blockers": [],
                "package": {
                    "name": "@adwasd/openclaw-zoho-cliq",
                    "version": "0.4.0-rc.1",
                    "expectedIntegrityState": "placeholder",
                },
                "releasePosture": {
                    "publishPerformed": False,
                    "tagCreated": False,
                    "npmPromotionRequiresOperatorApproval": True,
                },
            }
        )
    )
    trusted_reply = tmp_path / "trusted-reply-check.json"
    trusted_reply.write_text(
        json.dumps(
            {
                "status": "trusted_reply_recorded",
                "redaction": {
                    "rawWebhookPayloadStored": False,
                    "rawMessageBodyStored": False,
                    "rawCliqReplyBodyStored": False,
                    "secretsStored": False,
                    "secretMarkerPresent": False,
                },
            }
        )
    )
    report_file = tmp_path / "operator-bundle.json"

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_RC_OPERATOR_PUBLISH_BUNDLE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_CLIQ_PACK_SUMMARY_FILE": str(pack_summary),
            "OPENCLAW_CLIQ_ARTIFACT_REPORT_FILE": str(artifact_report),
            "OPENCLAW_CLIQ_INSTALL_SMOKE_FILE": str(install_smoke),
            "OPENCLAW_CLIQ_PROMOTION_REPORT_FILE": str(promotion),
            "OPENCLAW_CLIQ_TRUSTED_REPLY_CHECK_FILE": str(trusted_reply),
            "OPENCLAW_CLIQ_OPERATOR_BUNDLE_REPORT_FILE": str(report_file),
            "OPENCLAW_CLIQ_OPERATOR_BUNDLE_RUN_ID": "unit-test",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    assert str(tmp_path) not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "operator_publish_bundle_ready"
    assert payload["blockers"] == []
    assert payload["artifact"]["filename"] == "adwasd-openclaw-zoho-cliq-0.4.0-rc.1.tgz"
    assert payload["artifact"]["shasum"] == "abc123"
    assert payload["reports"]["promotion"]["file"] == promotion.name
    assert payload["reports"]["installSmoke"]["status"] == "install_smoke_passed"
    assert payload["releasePosture"] == {
        "publishPerformed": False,
        "tagCreated": False,
        "npmPromotionRequiresOperatorApproval": True,
        "agentMayPublish": False,
        "agentMayTag": False,
        "agentMayFillExpectedIntegrity": False,
        "expectedIntegrityAction": "operator_fills_after_approved_publish_only",
    }
    assert payload["nextAction"] == "operator_select_publish_path"
    assert json.loads(report_file.read_text()) == payload


def test_openclaw_cliq_rc_operator_publish_bundle_requires_ready_promotion(
    tmp_path: Path,
) -> None:
    pack_summary = tmp_path / "pack-summary.json"
    pack_summary.write_text(
        json.dumps(
            {
                "status": "passed",
                "pack": {
                    "name": "@adwasd/openclaw-zoho-cliq",
                    "version": "0.4.0-rc.1",
                },
                "releasePosture": {
                    "publishPerformed": False,
                    "versionBumped": False,
                },
            }
        )
    )
    artifact_report = tmp_path / "artifact-check.json"
    artifact_report.write_text(
        json.dumps(
            {
                "status": "artifact_verified",
                "artifact": {"shasumMatchesPackSummary": True},
                "package": {
                    "name": "@adwasd/openclaw-zoho-cliq",
                    "version": "0.4.0-rc.1",
                    "expectedIntegrityState": "placeholder",
                },
            }
        )
    )
    install_smoke = tmp_path / "install-smoke.json"
    install_smoke.write_text(
        json.dumps(
            {
                "status": "install_smoke_passed",
                "artifact": {"status": "artifact_verified"},
                "releasePosture": {
                    "publishPerformed": False,
                    "versionBumped": False,
                },
            }
        )
    )
    trusted_reply = tmp_path / "trusted-reply-check.json"
    trusted_reply.write_text(
        json.dumps(
            {
                "status": "trusted_reply_recorded",
                "redaction": {
                    "rawWebhookPayloadStored": False,
                    "rawMessageBodyStored": False,
                    "rawCliqReplyBodyStored": False,
                    "secretsStored": False,
                    "secretMarkerPresent": False,
                },
            }
        )
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_RC_OPERATOR_PUBLISH_BUNDLE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_CLIQ_PACK_SUMMARY_FILE": str(pack_summary),
            "OPENCLAW_CLIQ_ARTIFACT_REPORT_FILE": str(artifact_report),
            "OPENCLAW_CLIQ_INSTALL_SMOKE_FILE": str(install_smoke),
            "OPENCLAW_CLIQ_PROMOTION_REPORT_FILE": str(tmp_path / "missing.json"),
            "OPENCLAW_CLIQ_TRUSTED_REPLY_CHECK_FILE": str(trusted_reply),
            "OPENCLAW_CLIQ_OPERATOR_BUNDLE_REPORT_FILE": str(
                tmp_path / "operator-bundle.json"
            ),
            "OPENCLAW_CLIQ_OPERATOR_BUNDLE_RUN_ID": "unit-test-missing-promotion",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert "promotion_report_missing" in payload["blockers"]
    assert "promotion_not_ready" in payload["blockers"]
    assert payload["nextAction"] == "fix_blockers"


def test_openclaw_cliq_rc_release_notes_draft_uses_ready_operator_bundle(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "operator-bundle.json"
    bundle.write_text(
        json.dumps(
            {
                "status": "operator_publish_bundle_ready",
                "package": {
                    "name": "@adwasd/openclaw-zoho-cliq",
                    "version": "0.4.0-rc.1",
                    "expectedIntegrityState": "placeholder",
                },
                "artifact": {
                    "filename": "adwasd-openclaw-zoho-cliq-0.4.0-rc.1.tgz",
                    "shasum": "abc123",
                    "integrity": "sha512-test",
                },
                "reports": {
                    "packSummary": {"file": "pack.json", "status": "passed"},
                    "artifact": {
                        "file": "artifact.json",
                        "status": "artifact_verified",
                    },
                    "installSmoke": {
                        "file": "install.json",
                        "status": "install_smoke_passed",
                    },
                    "promotion": {
                        "file": "promotion.json",
                        "status": "ready_for_operator_publish",
                    },
                    "trustedReply": {
                        "file": "trusted.json",
                        "status": "trusted_reply_recorded",
                    },
                },
                "releasePosture": {
                    "agentMayPublish": False,
                    "agentMayTag": False,
                    "agentMayFillExpectedIntegrity": False,
                },
            }
        )
    )
    draft_file = tmp_path / "release-notes.md"

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_RC_RELEASE_NOTES_DRAFT_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_CLIQ_OPERATOR_BUNDLE_REPORT_FILE": str(bundle),
            "OPENCLAW_CLIQ_RELEASE_NOTES_DRAFT_FILE": str(draft_file),
            "OPENCLAW_CLIQ_RELEASE_NOTES_RUN_ID": "unit-test",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    assert result.stdout == draft_file.read_text()
    for marker in [
        "Draft generated",
        "No npm publish, git tag, GitHub release",
        "@adwasd/openclaw-zoho-cliq",
        "0.4.0-rc.1",
        "operator_publish_bundle_ready",
        "ready_for_operator_publish",
        "artifact_verified",
        "install_smoke_passed",
        "trusted_reply_recorded",
        "agentMayPublish=false",
        "agentMayTag=false",
        "agentMayFillExpectedIntegrity=false",
        "local_operator_rc",
        "npm_rc_publish",
        "github_release_artifact",
    ]:
        assert marker in result.stdout
    assert str(tmp_path) not in result.stdout


def test_openclaw_cliq_rc_release_notes_draft_requires_ready_operator_bundle(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "operator-bundle.json"
    bundle.write_text(
        json.dumps(
            {
                "status": "blocked",
                "releasePosture": {
                    "agentMayPublish": False,
                    "agentMayTag": False,
                    "agentMayFillExpectedIntegrity": False,
                },
            }
        )
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_RC_RELEASE_NOTES_DRAFT_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_CLIQ_OPERATOR_BUNDLE_REPORT_FILE": str(bundle),
            "OPENCLAW_CLIQ_RELEASE_NOTES_DRAFT_FILE": str(tmp_path / "draft.md"),
            "OPENCLAW_CLIQ_RELEASE_NOTES_RUN_ID": "unit-test-blocked",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    payload = json.loads(result.stdout)
    assert payload["kind"] == "openclaw_cliq_rc_release_notes_draft"
    assert payload["status"] == "error"
    assert payload["error"] == "operator_bundle_not_ready"


def test_openclaw_cliq_rc_publish_plan_uses_ready_bundle_and_draft(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "operator-bundle.json"
    bundle.write_text(
        json.dumps(
            {
                "status": "operator_publish_bundle_ready",
                "package": {
                    "name": "@adwasd/openclaw-zoho-cliq",
                    "version": "0.4.0-rc.1",
                    "expectedIntegrityState": "placeholder",
                },
                "artifact": {
                    "filename": "adwasd-openclaw-zoho-cliq-0.4.0-rc.1.tgz",
                    "shasum": "abc123",
                    "integrity": "sha512-test",
                },
                "reports": {
                    "artifact": {
                        "file": "artifact.json",
                        "status": "artifact_verified",
                    },
                    "installSmoke": {
                        "file": "install.json",
                        "status": "install_smoke_passed",
                    },
                    "promotion": {
                        "file": "promotion.json",
                        "status": "ready_for_operator_publish",
                    },
                    "trustedReply": {
                        "file": "trusted.json",
                        "status": "trusted_reply_recorded",
                    },
                },
                "releasePosture": {
                    "agentMayPublish": False,
                    "agentMayTag": False,
                    "agentMayFillExpectedIntegrity": False,
                },
            }
        )
    )
    release_notes = tmp_path / "release-notes.md"
    release_notes.write_text(
        "\n".join(
            [
                "# Draft",
                "No npm publish, git tag, GitHub release, version bump, or",
                "`openclaw.install.expectedIntegrity` fill has been performed.",
                "`agentMayPublish=false`",
                "`agentMayTag=false`",
                "`agentMayFillExpectedIntegrity=false`",
            ]
        )
    )
    plan_file = tmp_path / "publish-plan.json"

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_RC_PUBLISH_PLAN_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_CLIQ_OPERATOR_BUNDLE_REPORT_FILE": str(bundle),
            "OPENCLAW_CLIQ_RELEASE_NOTES_DRAFT_FILE": str(release_notes),
            "OPENCLAW_CLIQ_PUBLISH_PLAN_FILE": str(plan_file),
            "OPENCLAW_CLIQ_PUBLISH_PLAN_RUN_ID": "unit-test",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    assert str(tmp_path) not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "operator_publish_plan_ready"
    assert payload["nextAction"] == "operator_select_publish_path"
    assert payload["selectedPublishPath"] is None
    assert payload["artifact"]["pathHint"].endswith(
        "adwasd-openclaw-zoho-cliq-0.4.0-rc.1.tgz"
    )
    assert payload["evidence"]["operatorBundle"]["file"] == bundle.name
    assert payload["evidence"]["releaseNotesDraft"]["file"] == release_notes.name
    assert {path["id"] for path in payload["publishPaths"]} == {
        "local_operator_rc",
        "npm_rc_publish",
        "github_release_artifact",
    }
    assert "npm_publish" in payload["blockedAgentActions"]
    assert "expectedIntegrity_fill" in payload["blockedAgentActions"]
    assert payload["releasePosture"] == {
        "publishPerformed": False,
        "tagCreated": False,
        "githubReleaseCreated": False,
        "npmPromotionRequiresOperatorApproval": True,
        "agentMayPublish": False,
        "agentMayTag": False,
        "agentMayCreateGithubRelease": False,
        "agentMayFillExpectedIntegrity": False,
        "agentMayExecutePlan": False,
        "expectedIntegrityAction": "operator_fills_after_approved_publish_only",
    }
    assert json.loads(plan_file.read_text()) == payload


def test_openclaw_cliq_rc_publish_plan_requires_safe_release_notes(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "operator-bundle.json"
    bundle.write_text(
        json.dumps(
            {
                "status": "operator_publish_bundle_ready",
                "package": {
                    "expectedIntegrityState": "placeholder",
                },
                "releasePosture": {
                    "agentMayPublish": False,
                    "agentMayTag": False,
                    "agentMayFillExpectedIntegrity": False,
                },
            }
        )
    )
    release_notes = tmp_path / "unsafe-release-notes.md"
    release_notes.write_text("# Draft\nReady to publish.\n")

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_RC_PUBLISH_PLAN_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_CLIQ_OPERATOR_BUNDLE_REPORT_FILE": str(bundle),
            "OPENCLAW_CLIQ_RELEASE_NOTES_DRAFT_FILE": str(release_notes),
            "OPENCLAW_CLIQ_PUBLISH_PLAN_FILE": str(tmp_path / "publish-plan.json"),
            "OPENCLAW_CLIQ_PUBLISH_PLAN_RUN_ID": "unit-test-unsafe",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    payload = json.loads(result.stdout)
    assert payload["kind"] == "openclaw_cliq_rc_publish_plan"
    assert payload["status"] == "error"
    assert payload["error"] == "release_notes_draft_unsafe"


def test_openclaw_cliq_rc_operator_handoff_manifest_indexes_ready_packet(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "operator-bundle.json"
    bundle.write_text(
        json.dumps(
            {
                "status": "operator_publish_bundle_ready",
                "package": {
                    "name": "@adwasd/openclaw-zoho-cliq",
                    "version": "0.4.0-rc.1",
                    "expectedIntegrityState": "placeholder",
                },
                "artifact": {
                    "filename": "adwasd-openclaw-zoho-cliq-0.4.0-rc.1.tgz",
                    "shasum": "abc123",
                    "integrity": "sha512-test",
                },
                "reports": {
                    "packSummary": {"file": "pack.json", "status": "passed"},
                    "artifact": {
                        "file": "artifact.json",
                        "status": "artifact_verified",
                    },
                    "installSmoke": {
                        "file": "install.json",
                        "status": "install_smoke_passed",
                    },
                    "promotion": {
                        "file": "promotion.json",
                        "status": "ready_for_operator_publish",
                    },
                    "trustedReply": {
                        "file": "trusted.json",
                        "status": "trusted_reply_recorded",
                    },
                },
            }
        )
    )
    release_notes = tmp_path / "release-notes.md"
    release_notes.write_text(
        "\n".join(
            [
                "# Draft",
                "No npm publish, git tag, GitHub release, version bump, or",
                "`openclaw.install.expectedIntegrity` fill has been performed.",
                "`agentMayPublish=false`",
                "`agentMayTag=false`",
                "`agentMayFillExpectedIntegrity=false`",
            ]
        )
    )
    publish_plan = tmp_path / "publish-plan.json"
    publish_plan.write_text(
        json.dumps(
            {
                "status": "operator_publish_plan_ready",
                "package": {
                    "name": "@adwasd/openclaw-zoho-cliq",
                    "version": "0.4.0-rc.1",
                },
                "artifact": {
                    "shasum": "abc123",
                    "integrity": "sha512-test",
                },
                "evidence": {
                    "operatorBundle": {"file": bundle.name},
                    "releaseNotesDraft": {"file": release_notes.name},
                },
                "blockedAgentActions": [
                    "npm_publish",
                    "git_tag",
                    "github_release_create",
                    "expectedIntegrity_fill",
                ],
                "releasePosture": {
                    "agentMayPublish": False,
                    "agentMayTag": False,
                    "agentMayCreateGithubRelease": False,
                    "agentMayFillExpectedIntegrity": False,
                    "agentMayExecutePlan": False,
                },
            }
        )
    )
    manifest_file = tmp_path / "handoff-manifest.json"

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_RC_HANDOFF_MANIFEST_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_CLIQ_OPERATOR_BUNDLE_REPORT_FILE": str(bundle),
            "OPENCLAW_CLIQ_RELEASE_NOTES_DRAFT_FILE": str(release_notes),
            "OPENCLAW_CLIQ_PUBLISH_PLAN_FILE": str(publish_plan),
            "OPENCLAW_CLIQ_HANDOFF_MANIFEST_FILE": str(manifest_file),
            "OPENCLAW_CLIQ_HANDOFF_MANIFEST_RUN_ID": "unit-test",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    assert str(tmp_path) not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "operator_handoff_manifest_ready"
    assert payload["blockers"] == []
    assert payload["nextAction"] == "operator_review_handoff_manifest"
    assert payload["evidenceFiles"]["operatorBundle"] == bundle.name
    assert payload["evidenceFiles"]["releaseNotesDraft"] == release_notes.name
    assert payload["evidenceFiles"]["publishPlan"] == publish_plan.name
    assert payload["verifiedStatuses"] == {
        "operatorBundle": "operator_publish_bundle_ready",
        "publishPlan": "operator_publish_plan_ready",
        "promotion": "ready_for_operator_publish",
        "artifact": "artifact_verified",
        "installSmoke": "install_smoke_passed",
        "trustedReply": "trusted_reply_recorded",
    }
    assert "npm_publish" in payload["safety"]["blockedAgentActions"]
    assert payload["safety"]["agentMayExecutePlan"] is False
    assert payload["releasePosture"] == {
        "publishPerformed": False,
        "tagCreated": False,
        "githubReleaseCreated": False,
        "versionBumped": False,
        "expectedIntegrityFilled": False,
        "npmPromotionRequiresOperatorApproval": True,
    }
    assert json.loads(manifest_file.read_text()) == payload


def test_openclaw_cliq_rc_operator_handoff_manifest_blocks_unsafe_plan(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "operator-bundle.json"
    bundle.write_text(json.dumps({"status": "operator_publish_bundle_ready"}))
    release_notes = tmp_path / "release-notes.md"
    release_notes.write_text(
        "\n".join(
            [
                "No npm publish, git tag, GitHub release",
                "`agentMayPublish=false`",
                "`agentMayTag=false`",
                "`agentMayFillExpectedIntegrity=false`",
            ]
        )
    )
    publish_plan = tmp_path / "publish-plan.json"
    publish_plan.write_text(
        json.dumps(
            {
                "status": "operator_publish_plan_ready",
                "releasePosture": {
                    "agentMayPublish": False,
                    "agentMayTag": False,
                    "agentMayCreateGithubRelease": False,
                    "agentMayFillExpectedIntegrity": False,
                    "agentMayExecutePlan": True,
                },
            }
        )
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_RC_HANDOFF_MANIFEST_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_CLIQ_OPERATOR_BUNDLE_REPORT_FILE": str(bundle),
            "OPENCLAW_CLIQ_RELEASE_NOTES_DRAFT_FILE": str(release_notes),
            "OPENCLAW_CLIQ_PUBLISH_PLAN_FILE": str(publish_plan),
            "OPENCLAW_CLIQ_HANDOFF_MANIFEST_FILE": str(tmp_path / "manifest.json"),
            "OPENCLAW_CLIQ_HANDOFF_MANIFEST_RUN_ID": "unit-test-unsafe",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    payload = json.loads(result.stdout)
    assert payload["kind"] == "openclaw_cliq_rc_operator_handoff_manifest"
    assert payload["status"] == "error"
    assert payload["error"] == "publish_plan_permission_unexpected"


def _write_fake_git_for_openclaw_cliq_source_drift(tmp_path: Path) -> Path:
    fake_git = tmp_path / "fake_git.py"
    fake_git.write_text(
        """#!/usr/bin/env python3
import os
import sys

args = sys.argv[1:]
if args[:1] == ["-C"]:
    args = args[2:]

package_filter = "integrations/openclaw-channel-cliq"

if args == ["rev-parse", "HEAD"]:
    print("HEAD123")
elif args == ["branch", "--show-current"]:
    print("autobot/source-drift")
elif args[:3] == ["diff", "--name-only", "SRC..HEAD"] and args[3:] == ["--", package_filter]:
    print(os.environ.get("FAKE_PACKAGE_DRIFT", ""))
elif args == ["diff", "--name-only", "--", package_filter]:
    print(os.environ.get("FAKE_PACKAGE_WORKTREE", ""))
elif args == ["diff", "--cached", "--name-only", "--", package_filter]:
    print(os.environ.get("FAKE_PACKAGE_INDEX", ""))
elif args == ["ls-files", "--others", "--exclude-standard", "--", package_filter]:
    print(os.environ.get("FAKE_PACKAGE_UNTRACKED", ""))
elif args == ["diff", "--name-only", "SRC..HEAD"]:
    print("README.md")
    print("ops/state/project.yml")
else:
    print(f"unexpected git args: {args}", file=sys.stderr)
    raise SystemExit(9)
"""
    )
    fake_git.chmod(fake_git.stat().st_mode | stat.S_IXUSR)
    return fake_git


def _write_openclaw_cliq_handoff_manifest_for_source_drift(tmp_path: Path) -> Path:
    manifest = tmp_path / "handoff-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "status": "operator_handoff_manifest_ready",
                "source": {
                    "gitCommit": "SRC",
                    "gitBranch": "autobot/zoho-platform",
                },
                "package": {
                    "name": "@adwasd/openclaw-zoho-cliq",
                    "version": "0.4.0-rc.1",
                    "expectedIntegrityState": "placeholder",
                },
                "artifact": {
                    "filename": "adwasd-openclaw-zoho-cliq-0.4.0-rc.1.tgz",
                    "shasum": "abc123",
                    "integrity": "sha512-test",
                },
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_openclaw_cliq_rc_source_drift_check_allows_non_package_head_drift(
    tmp_path: Path,
) -> None:
    fake_git = _write_fake_git_for_openclaw_cliq_source_drift(tmp_path)
    manifest = _write_openclaw_cliq_handoff_manifest_for_source_drift(tmp_path)
    report_file = tmp_path / "source-drift.json"

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_RC_SOURCE_DRIFT_CHECK_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "GIT_BIN": str(fake_git),
            "OPENCLAW_CLIQ_HANDOFF_MANIFEST_FILE": str(manifest),
            "OPENCLAW_CLIQ_SOURCE_DRIFT_REPORT_FILE": str(report_file),
            "OPENCLAW_CLIQ_SOURCE_DRIFT_RUN_ID": "unit-source-drift-ok",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    assert str(tmp_path) not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "package_source_unchanged"
    assert payload["blockers"] == []
    assert payload["source"]["manifestFile"] == manifest.name
    assert payload["source"]["sourceCommit"] == "SRC"
    assert payload["source"]["headCommit"] == "HEAD123"
    assert payload["source"]["repoChangedSinceManifest"] is True
    assert payload["source"]["repoChangedFileCount"] == 2
    assert payload["packageDrift"]["packageChangedSinceManifest"] is False
    assert payload["packageDrift"]["changedFiles"] == []
    assert payload["nextAction"] == "operator_handoff_still_current_for_package"
    assert payload["releasePosture"]["agentMayPublish"] is False
    assert json.loads(report_file.read_text()) == payload


def test_openclaw_cliq_rc_source_drift_check_blocks_package_drift(
    tmp_path: Path,
) -> None:
    fake_git = _write_fake_git_for_openclaw_cliq_source_drift(tmp_path)
    manifest = _write_openclaw_cliq_handoff_manifest_for_source_drift(tmp_path)

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_RC_SOURCE_DRIFT_CHECK_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "GIT_BIN": str(fake_git),
            "FAKE_PACKAGE_DRIFT": "integrations/openclaw-channel-cliq/src/runtime.ts",
            "OPENCLAW_CLIQ_HANDOFF_MANIFEST_FILE": str(manifest),
            "OPENCLAW_CLIQ_SOURCE_DRIFT_REPORT_FILE": str(tmp_path / "drift.json"),
            "OPENCLAW_CLIQ_SOURCE_DRIFT_RUN_ID": "unit-source-drift-blocked",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert payload["blockers"] == ["package_source_drift_detected"]
    assert payload["packageDrift"]["changedFileCount"] == 1
    assert payload["packageDrift"]["changedFiles"] == [
        "integrations/openclaw-channel-cliq/src/runtime.ts"
    ]
    assert payload["nextAction"] == "repack_current_head_before_operator_publish"


def _write_openclaw_cliq_publish_plan_for_selection_review(
    tmp_path: Path,
    *,
    selected_path: str | None,
) -> Path:
    publish_plan = tmp_path / "publish-plan.json"
    publish_plan.write_text(
        json.dumps(
            {
                "status": "operator_publish_plan_ready",
                "selectedPublishPath": selected_path,
                "package": {
                    "name": "@adwasd/openclaw-zoho-cliq",
                    "version": "0.4.0-rc.1",
                    "expectedIntegrityState": "placeholder",
                },
                "artifact": {
                    "filename": "adwasd-openclaw-zoho-cliq-0.4.0-rc.1.tgz",
                    "shasum": "abc123",
                    "integrity": "sha512-test",
                    "pathHint": ".tmp/openclaw-cliq-rc-pack/test.tgz",
                },
                "evidence": {
                    "operatorBundle": {"file": "operator-bundle.json"},
                    "releaseNotesDraft": {"file": "release-notes.md"},
                },
                "publishPaths": [
                    {
                        "id": "local_operator_rc",
                        "operatorOnly": True,
                        "fillsExpectedIntegrity": False,
                    },
                    {
                        "id": "npm_rc_publish",
                        "operatorOnly": True,
                        "fillsExpectedIntegrityAfterPublish": True,
                        "commandPreview": [
                            "npm",
                            "publish",
                            ".tmp/openclaw-cliq-rc-pack/test.tgz",
                            "--tag",
                            "rc",
                            "--access",
                            "public",
                        ],
                    },
                ],
                "blockedAgentActions": [
                    "npm_publish",
                    "git_tag",
                    "github_release_create",
                    "expectedIntegrity_fill",
                ],
                "releasePosture": {
                    "agentMayPublish": False,
                    "agentMayTag": False,
                    "agentMayCreateGithubRelease": False,
                    "agentMayFillExpectedIntegrity": False,
                    "agentMayExecutePlan": False,
                },
            }
        ),
        encoding="utf-8",
    )
    return publish_plan


def _write_openclaw_cliq_source_drift_for_selection_review(tmp_path: Path) -> Path:
    source_drift = tmp_path / "source-drift.json"
    source_drift.write_text(
        json.dumps(
            {
                "status": "package_source_unchanged",
                "source": {
                    "sourceCommit": "SRC",
                    "headCommit": "HEAD",
                    "packagePathFilter": "integrations/openclaw-channel-cliq",
                    "repoChangedSinceManifest": True,
                },
                "packageDrift": {
                    "packageChangedSinceManifest": False,
                    "dirtyFileCount": 0,
                },
            }
        ),
        encoding="utf-8",
    )
    return source_drift


def test_openclaw_cliq_rc_operator_selection_review_indexes_selected_path(
    tmp_path: Path,
) -> None:
    publish_plan = _write_openclaw_cliq_publish_plan_for_selection_review(
        tmp_path,
        selected_path="npm_rc_publish",
    )
    source_drift = _write_openclaw_cliq_source_drift_for_selection_review(tmp_path)
    review_file = tmp_path / "selection-review.json"

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_RC_SELECTION_REVIEW_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_CLIQ_PUBLISH_PLAN_FILE": str(publish_plan),
            "OPENCLAW_CLIQ_SOURCE_DRIFT_REPORT_FILE": str(source_drift),
            "OPENCLAW_CLIQ_SELECTION_REVIEW_FILE": str(review_file),
            "OPENCLAW_CLIQ_SELECTION_REVIEW_RUN_ID": "unit-selection-ready",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    assert str(tmp_path) not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "operator_publish_selection_ready"
    assert payload["blockers"] == []
    assert payload["selectedPublishPath"] == "npm_rc_publish"
    assert payload["selectedPublishPathReview"] == {
        "id": "npm_rc_publish",
        "operatorOnly": True,
        "fillsExpectedIntegrity": False,
        "fillsExpectedIntegrityAfterPublish": True,
        "commandPreview": [
            "npm",
            "publish",
            ".tmp/openclaw-cliq-rc-pack/test.tgz",
            "--tag",
            "rc",
            "--access",
            "public",
        ],
        "agentMayExecute": False,
        "requiresExplicitOperatorApproval": True,
    }
    assert payload["evidenceFiles"]["publishPlan"] == publish_plan.name
    assert payload["evidenceFiles"]["sourceDrift"] == source_drift.name
    assert payload["sourceDrift"]["packageChangedSinceManifest"] is False
    assert "npm_publish" in payload["safety"]["blockedAgentActions"]
    assert payload["safety"]["agentMayExecuteSelectedPath"] is False
    assert payload["nextAction"] == "operator_review_selected_publish_path"
    assert json.loads(review_file.read_text()) == payload


def test_openclaw_cliq_rc_operator_selection_review_requires_selected_path(
    tmp_path: Path,
) -> None:
    publish_plan = _write_openclaw_cliq_publish_plan_for_selection_review(
        tmp_path,
        selected_path=None,
    )
    source_drift = _write_openclaw_cliq_source_drift_for_selection_review(tmp_path)

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_RC_SELECTION_REVIEW_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_CLIQ_PUBLISH_PLAN_FILE": str(publish_plan),
            "OPENCLAW_CLIQ_SOURCE_DRIFT_REPORT_FILE": str(source_drift),
            "OPENCLAW_CLIQ_SELECTION_REVIEW_FILE": str(tmp_path / "review.json"),
            "OPENCLAW_CLIQ_SELECTION_REVIEW_RUN_ID": "unit-selection-missing",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert payload["blockers"] == ["publish_path_not_selected"]
    assert payload["selectedPublishPath"] is None
    assert payload["selectedPublishPathReview"] is None
    assert payload["nextAction"] == "operator_select_publish_path"


def _write_openclaw_cliq_decision_packet_inputs(
    tmp_path: Path,
) -> tuple[Path, Path, Path]:
    bundle = tmp_path / "operator-bundle.json"
    bundle.write_text(
        json.dumps(
            {
                "status": "operator_publish_bundle_ready",
                "package": {
                    "name": "@adwasd/openclaw-zoho-cliq",
                    "version": "0.4.0-rc.1",
                    "expectedIntegrityState": "placeholder",
                },
                "artifact": {
                    "filename": "adwasd-openclaw-zoho-cliq-0.4.0-rc.1.tgz",
                    "shasum": "abc123",
                    "integrity": "sha512-test",
                },
                "reports": {
                    "promotion": {
                        "file": "promotion.json",
                        "status": "ready_for_operator_publish",
                    },
                    "artifact": {
                        "file": "artifact.json",
                        "status": "artifact_verified",
                    },
                    "installSmoke": {
                        "file": "install.json",
                        "status": "install_smoke_passed",
                    },
                    "trustedReply": {
                        "file": "trusted.json",
                        "status": "trusted_reply_recorded",
                    },
                },
                "releasePosture": {
                    "agentMayPublish": False,
                    "agentMayTag": False,
                    "agentMayFillExpectedIntegrity": False,
                },
            }
        ),
        encoding="utf-8",
    )
    release_notes = tmp_path / "release-notes.md"
    release_notes.write_text(
        "\n".join(
            [
                "# Draft",
                "No npm publish, git tag, GitHub release, version bump, or",
                "`openclaw.install.expectedIntegrity` fill has been performed.",
                "`agentMayPublish=false`",
                "`agentMayTag=false`",
                "`agentMayFillExpectedIntegrity=false`",
            ]
        ),
        encoding="utf-8",
    )
    manifest = _write_openclaw_cliq_handoff_manifest_for_source_drift(tmp_path)
    return bundle, release_notes, manifest


def test_openclaw_cliq_rc_operator_decision_packet_awaits_publish_path(
    tmp_path: Path,
) -> None:
    fake_git = _write_fake_git_for_openclaw_cliq_source_drift(tmp_path)
    bundle, release_notes, manifest = _write_openclaw_cliq_decision_packet_inputs(
        tmp_path
    )
    packet_file = tmp_path / "decision-packet.json"

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_RC_DECISION_PACKET_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "GIT_BIN": str(fake_git),
            "OPENCLAW_CLIQ_OPERATOR_BUNDLE_REPORT_FILE": str(bundle),
            "OPENCLAW_CLIQ_RELEASE_NOTES_DRAFT_FILE": str(release_notes),
            "OPENCLAW_CLIQ_HANDOFF_MANIFEST_FILE": str(manifest),
            "OPENCLAW_CLIQ_DECISION_PACKET_REPORT_DIR": str(tmp_path),
            "OPENCLAW_CLIQ_DECISION_PACKET_FILE": str(packet_file),
            "OPENCLAW_CLIQ_DECISION_PACKET_RUN_ID": "unit-decision-awaiting",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    assert str(tmp_path) not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "awaiting_operator_publish_path"
    assert payload["blockers"] == ["publish_path_not_selected"]
    assert payload["selectedPublishPath"] is None
    assert payload["verifiedStatuses"]["publishPlan"] == "operator_publish_plan_ready"
    assert payload["verifiedStatuses"]["sourceDrift"] == "package_source_unchanged"
    assert payload["verifiedStatuses"]["selectionReview"] == "blocked"
    assert payload["sourceDrift"]["packageChangedSinceManifest"] is False
    assert payload["nextAction"] == "operator_select_publish_path"
    assert payload["safety"]["agentMayExecuteSelectedPath"] is False
    assert "npm_rc_publish" in {path["id"] for path in payload["publishPaths"]}
    assert json.loads(packet_file.read_text()) == payload


def test_openclaw_cliq_rc_operator_decision_packet_indexes_selected_path(
    tmp_path: Path,
) -> None:
    fake_git = _write_fake_git_for_openclaw_cliq_source_drift(tmp_path)
    bundle, release_notes, manifest = _write_openclaw_cliq_decision_packet_inputs(
        tmp_path
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_RC_DECISION_PACKET_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "GIT_BIN": str(fake_git),
            "OPENCLAW_CLIQ_OPERATOR_BUNDLE_REPORT_FILE": str(bundle),
            "OPENCLAW_CLIQ_RELEASE_NOTES_DRAFT_FILE": str(release_notes),
            "OPENCLAW_CLIQ_HANDOFF_MANIFEST_FILE": str(manifest),
            "OPENCLAW_CLIQ_OPERATOR_PUBLISH_PATH": "npm_rc_publish",
            "OPENCLAW_CLIQ_DECISION_PACKET_REPORT_DIR": str(tmp_path),
            "OPENCLAW_CLIQ_DECISION_PACKET_FILE": str(tmp_path / "packet.json"),
            "OPENCLAW_CLIQ_DECISION_PACKET_RUN_ID": "unit-decision-selected",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    payload = json.loads(result.stdout)
    assert payload["status"] == "operator_publish_selection_ready"
    assert payload["blockers"] == []
    assert payload["selectedPublishPath"] == "npm_rc_publish"
    assert payload["selectedPublishPathReview"]["id"] == "npm_rc_publish"
    assert payload["selectedPublishPathReview"]["agentMayExecute"] is False
    assert (
        payload["selectedPublishPathReview"]["requiresExplicitOperatorApproval"] is True
    )
    assert payload["nextAction"] == "operator_review_selected_publish_path"


def test_openclaw_cliq_rc_operator_decision_packet_blocks_package_drift(
    tmp_path: Path,
) -> None:
    fake_git = _write_fake_git_for_openclaw_cliq_source_drift(tmp_path)
    bundle, release_notes, manifest = _write_openclaw_cliq_decision_packet_inputs(
        tmp_path
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_RC_DECISION_PACKET_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "GIT_BIN": str(fake_git),
            "FAKE_PACKAGE_DRIFT": "integrations/openclaw-channel-cliq/src/runtime.ts",
            "OPENCLAW_CLIQ_OPERATOR_BUNDLE_REPORT_FILE": str(bundle),
            "OPENCLAW_CLIQ_RELEASE_NOTES_DRAFT_FILE": str(release_notes),
            "OPENCLAW_CLIQ_HANDOFF_MANIFEST_FILE": str(manifest),
            "OPENCLAW_CLIQ_DECISION_PACKET_REPORT_DIR": str(tmp_path),
            "OPENCLAW_CLIQ_DECISION_PACKET_FILE": str(tmp_path / "packet.json"),
            "OPENCLAW_CLIQ_DECISION_PACKET_RUN_ID": "unit-decision-drift",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert "package_source_drift_detected" in payload["blockers"]
    assert payload["nextAction"] == "fix_operator_decision_packet_blockers"


def _write_openclaw_cliq_test_tarball(
    tarball_path: Path,
    *,
    omit_entries: set[str] | None = None,
) -> None:
    omit_entries = omit_entries or set()
    package_json = {
        "name": "@adwasd/openclaw-zoho-cliq",
        "version": "0.4.0-rc.1",
        "openclaw": {
            "extensions": ["./dist/index.js"],
            "setupEntry": "./dist/setup-entry.js",
            "channel": {"id": "cliq"},
            "install": {"expectedIntegrity": "<filled-at-release>"},
        },
    }
    manifest_json = {
        "id": "zoho-cliq",
        "channels": ["cliq"],
    }
    entries = {
        "package/package.json": json.dumps(package_json).encode(),
        "package/openclaw.plugin.json": json.dumps(manifest_json).encode(),
        "package/README.md": b"# test package\n",
        "package/skill/SKILL.md": b"# test skill\n",
        "package/dist/index.js": b"export {};\n",
        "package/dist/setup-entry.js": b"export {};\n",
        "package/dist/src/channel.js": b"export {};\n",
        "package/dist/src/native-dispatch.js": b"export {};\n",
        "package/dist/src/webhook.js": b"export {};\n",
        "package/dist/src/zoho-cli.js": b"export {};\n",
    }

    with tarfile.open(tarball_path, "w:gz") as tar:
        for name, data in entries.items():
            if name in omit_entries:
                continue
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 0
            tar.addfile(info, fileobj=io.BytesIO(data))


def test_openclaw_cliq_rc_artifact_check_verifies_tarball_contract(
    tmp_path: Path,
) -> None:
    tarball_path = tmp_path / "adwasd-openclaw-zoho-cliq-0.4.0-rc.1.tgz"
    _write_openclaw_cliq_test_tarball(tarball_path)
    shasum = hashlib.sha1(tarball_path.read_bytes()).hexdigest()
    pack_summary = tmp_path / "pack-summary.json"
    pack_summary.write_text(
        json.dumps(
            {
                "status": "passed",
                "pack": {
                    "name": "@adwasd/openclaw-zoho-cliq",
                    "version": "0.4.0-rc.1",
                    "filename": tarball_path.name,
                    "tarballPath": str(tarball_path),
                    "shasum": shasum,
                    "integrity": "sha512-test",
                },
                "releasePosture": {
                    "publishPerformed": False,
                    "versionBumped": False,
                },
            }
        )
    )
    report_file = tmp_path / "artifact-check.json"

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_RC_ARTIFACT_CHECK_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_CLIQ_PACK_SUMMARY_FILE": str(pack_summary),
            "OPENCLAW_CLIQ_ARTIFACT_REPORT_DIR": str(tmp_path),
            "OPENCLAW_CLIQ_ARTIFACT_REPORT_FILE": str(report_file),
            "OPENCLAW_CLIQ_ARTIFACT_RUN_ID": "unit-artifact",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    payload = json.loads(result.stdout)
    assert payload["status"] == "artifact_verified"
    assert payload["blockers"] == []
    assert payload["artifact"]["shasumMatchesPackSummary"] is True
    assert payload["package"]["expectedIntegrityState"] == "placeholder"
    assert payload["manifest"]["id"] == "zoho-cliq"
    assert payload["releasePosture"] == {
        "publishPerformed": False,
        "tagCreated": False,
        "versionBumped": False,
        "expectedIntegrityAction": "fill_after_publish",
        "installVerifiedWithoutPublish": True,
    }
    assert json.loads(report_file.read_text()) == payload


def test_openclaw_cliq_rc_artifact_check_blocks_missing_required_entry(
    tmp_path: Path,
) -> None:
    tarball_path = tmp_path / "adwasd-openclaw-zoho-cliq-0.4.0-rc.1.tgz"
    _write_openclaw_cliq_test_tarball(
        tarball_path,
        omit_entries={"package/dist/src/native-dispatch.js"},
    )
    shasum = hashlib.sha1(tarball_path.read_bytes()).hexdigest()
    pack_summary = tmp_path / "pack-summary.json"
    pack_summary.write_text(
        json.dumps(
            {
                "status": "passed",
                "pack": {
                    "name": "@adwasd/openclaw-zoho-cliq",
                    "version": "0.4.0-rc.1",
                    "filename": tarball_path.name,
                    "tarballPath": str(tarball_path),
                    "shasum": shasum,
                    "integrity": "sha512-test",
                },
                "releasePosture": {
                    "publishPerformed": False,
                    "versionBumped": False,
                },
            }
        )
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_RC_ARTIFACT_CHECK_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_CLIQ_PACK_SUMMARY_FILE": str(pack_summary),
            "OPENCLAW_CLIQ_ARTIFACT_REPORT_DIR": str(tmp_path),
            "OPENCLAW_CLIQ_ARTIFACT_REPORT_FILE": str(tmp_path / "report.json"),
            "OPENCLAW_CLIQ_ARTIFACT_RUN_ID": "unit-artifact-blocked",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert (
        "required_entry_missing_package_dist_src_native_dispatch_js"
        in payload["blockers"]
    )


def _write_fake_openclaw_for_install_smoke(tmp_path: Path) -> tuple[Path, Path]:
    calls_path = tmp_path / "openclaw_calls.jsonl"
    fake_openclaw = tmp_path / "fake_openclaw.py"
    fake_openclaw.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]
with open(os.environ["FAKE_OPENCLAW_CALLS"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"args": args, "home": os.environ.get("HOME")}) + "\\n")

if args == ["--version"]:
    print("OpenClaw 2026.5.3-1")
    raise SystemExit(0)
if args[:2] == ["plugins", "install"]:
    if not args[2].endswith(".tgz"):
        print("expected tgz install source", file=sys.stderr)
        raise SystemExit(3)
    print("installed")
    raise SystemExit(0)
if args == ["plugins", "inspect", "zoho-cliq", "--json"]:
    print(json.dumps({
        "id": "zoho-cliq",
        "status": "loaded",
        "channelIds": ["cliq"],
        "diagnostics": []
    }))
    raise SystemExit(0)
if args == ["plugins", "doctor"]:
    print("No plugin issues detected.")
    raise SystemExit(0)

print(json.dumps({"status": "error", "error": "unexpected_args", "args": args}))
raise SystemExit(9)
"""
    )
    fake_openclaw.chmod(fake_openclaw.stat().st_mode | stat.S_IXUSR)
    return fake_openclaw, calls_path


def test_openclaw_cliq_rc_install_smoke_installs_verified_artifact(
    tmp_path: Path,
) -> None:
    tarball_path = tmp_path / "adwasd-openclaw-zoho-cliq-0.4.0-rc.1.tgz"
    tarball_path.write_bytes(b"fake tarball")
    shasum = hashlib.sha1(tarball_path.read_bytes()).hexdigest()
    pack_summary = tmp_path / "pack-summary.json"
    pack_summary.write_text(
        json.dumps(
            {
                "status": "passed",
                "pack": {
                    "filename": tarball_path.name,
                    "tarballPath": str(tarball_path),
                    "shasum": shasum,
                    "integrity": "sha512-test",
                },
                "releasePosture": {
                    "publishPerformed": False,
                    "versionBumped": False,
                },
            }
        )
    )
    artifact_report = tmp_path / "artifact.json"
    artifact_report.write_text(
        json.dumps(
            {
                "status": "artifact_verified",
                "artifact": {
                    "shasumMatchesPackSummary": True,
                },
            }
        )
    )
    fake_openclaw, calls_path = _write_fake_openclaw_for_install_smoke(tmp_path)
    report_file = tmp_path / "install-smoke.json"

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_RC_INSTALL_SMOKE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_BIN": str(fake_openclaw),
            "FAKE_OPENCLAW_CALLS": str(calls_path),
            "OPENCLAW_CLIQ_PACK_SUMMARY_FILE": str(pack_summary),
            "OPENCLAW_CLIQ_ARTIFACT_REPORT_FILE": str(artifact_report),
            "OPENCLAW_CLIQ_INSTALL_REPORT_DIR": str(tmp_path),
            "OPENCLAW_CLIQ_INSTALL_REPORT_FILE": str(report_file),
            "OPENCLAW_CLIQ_INSTALL_HOME": str(tmp_path / "home"),
            "OPENCLAW_CLIQ_INSTALL_RUN_ID": "unit-install",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    payload = json.loads(result.stdout)
    assert payload["status"] == "install_smoke_passed"
    assert payload["blockers"] == []
    assert payload["source"]["type"] == "artifact"
    assert payload["artifact"]["status"] == "artifact_verified"
    assert payload["artifact"]["shasumMatchesPackSummary"] is True
    assert [command["name"] for command in payload["commands"]] == [
        "version",
        "install",
        "inspect",
        "doctor",
    ]
    assert all(command["status"] == "passed" for command in payload["commands"])
    assert payload["releasePosture"] == {
        "publishPerformed": False,
        "tagCreated": False,
        "versionBumped": False,
        "expectedIntegrityAction": "fill_after_publish",
        "localInstallSmokeOnly": True,
    }
    calls = [json.loads(line) for line in calls_path.read_text().splitlines()]
    assert calls[1]["args"] == ["plugins", "install", str(tarball_path)]


def test_openclaw_cliq_rc_install_smoke_requires_verified_artifact(
    tmp_path: Path,
) -> None:
    tarball_path = tmp_path / "adwasd-openclaw-zoho-cliq-0.4.0-rc.1.tgz"
    tarball_path.write_bytes(b"fake tarball")
    pack_summary = tmp_path / "pack-summary.json"
    pack_summary.write_text(
        json.dumps(
            {
                "status": "passed",
                "pack": {
                    "filename": tarball_path.name,
                    "tarballPath": str(tarball_path),
                },
            }
        )
    )
    artifact_report = tmp_path / "artifact.json"
    artifact_report.write_text(json.dumps({"status": "blocked"}))
    fake_openclaw, calls_path = _write_fake_openclaw_for_install_smoke(tmp_path)

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_RC_INSTALL_SMOKE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_BIN": str(fake_openclaw),
            "FAKE_OPENCLAW_CALLS": str(calls_path),
            "OPENCLAW_CLIQ_PACK_SUMMARY_FILE": str(pack_summary),
            "OPENCLAW_CLIQ_ARTIFACT_REPORT_FILE": str(artifact_report),
            "OPENCLAW_CLIQ_INSTALL_REPORT_DIR": str(tmp_path),
            "OPENCLAW_CLIQ_INSTALL_REPORT_FILE": str(tmp_path / "report.json"),
            "OPENCLAW_CLIQ_INSTALL_HOME": str(tmp_path / "home"),
            "OPENCLAW_CLIQ_INSTALL_RUN_ID": "unit-install-blocked",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert "artifact_not_verified" in payload["blockers"]
    assert payload["commands"] == []
    assert not calls_path.exists()


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


def test_crm_fixture_payload_preflight_blocks_template_payload(
    tmp_path: Path,
) -> None:
    raw_email = "zoho-cli-fixture+replace-me@example.invalid"
    payload_file = tmp_path / "fixture-template.json"
    payload_file.write_text(
        json.dumps(
            {
                "Last_Name": "ZohoCliFixtureReplaceMe",
                "Company": "Zoho CLI Fixture",
                "Email": raw_email,
            }
        ),
        encoding="utf-8",
    )
    reports_dir = tmp_path / "reports"

    result = subprocess.run(
        ["bash", str(CRM_FIXTURE_PAYLOAD_PREFLIGHT_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CRM_FIXTURE_PAYLOAD_FILE": str(payload_file),
            "ZOHO_CRM_FIXTURE_CLEANUP_PLAN": "delete the fixture record after validation",
            "ZOHO_CRM_FIXTURE_PREFLIGHT_REPORT_DIR": str(reports_dir),
            "ZOHO_CRM_FIXTURE_PREFLIGHT_RUN_ID": "unit-template",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    assert raw_email not in output
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert payload["blockers"] == ["fixture_payload_placeholder_email"]
    assert payload["payload"]["file"] == payload_file.name
    assert payload["payload"]["recordCount"] == 1
    assert payload["payload"]["missingRequiredFields"] == []
    assert payload["payload"]["placeholderEmailCount"] == 1
    assert payload["payload"]["dedicatedFixtureCandidate"] is False
    assert payload["cleanup"] == {
        "required": True,
        "present": True,
        "lengthBucket": "sufficient",
        "actionPresent": True,
        "targetPresent": True,
        "qualityReady": True,
        "rawCleanupPlanStored": False,
    }
    assert payload["redactionContract"]["rawEmailStored"] is False
    assert payload["nextAction"] == "fix_fixture_payload"
    assert (
        json.loads(
            (
                reports_dir / "crm_fixture_payload_preflight_unit-template.json"
            ).read_text()
        )
        == payload
    )


def test_crm_fixture_payload_preflight_accepts_dedicated_payload(
    tmp_path: Path,
) -> None:
    raw_email = "fixture-ready@operator.test"
    raw_cleanup = "delete record with this dedicated fixture email after validation"
    payload_file = tmp_path / "fixture-ready.json"
    payload_file.write_text(
        json.dumps(
            {
                "Last_Name": "ZohoCliFixtureReady",
                "Company": "Zoho CLI Fixture",
                "Email": raw_email,
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(CRM_FIXTURE_PAYLOAD_PREFLIGHT_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CRM_FIXTURE_PAYLOAD_FILE": str(payload_file),
            "ZOHO_CRM_FIXTURE_CLEANUP_PLAN": raw_cleanup,
            "ZOHO_CRM_FIXTURE_PREFLIGHT_REPORT_DIR": str(tmp_path / "reports"),
            "ZOHO_CRM_FIXTURE_PREFLIGHT_RUN_ID": "unit-ready",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    assert raw_email not in output
    assert raw_cleanup not in output
    payload = json.loads(result.stdout)
    assert payload["status"] == "payload_preflight_ready"
    assert payload["blockers"] == []
    assert payload["payload"]["dedicatedFixtureCandidate"] is True
    assert payload["payload"]["requiredFields"] == ["Last_Name", "Company", "Email"]
    assert payload["payload"]["missingRequiredFields"] == []
    assert payload["payload"]["placeholderEmailCount"] == 0
    assert payload["cleanup"]["present"] is True
    assert payload["cleanup"]["qualityReady"] is True
    assert payload["cleanup"]["lengthBucket"] == "sufficient"
    assert payload["releasePosture"]["normalUpsertExecuteBlocked"] is True
    assert payload["releasePosture"]["agentMayRunLiveFixture"] is False
    assert payload["nextAction"] == "run_crm_fixture_live_smoke_dry_run"


def test_crm_fixture_payload_preflight_requires_cleanup_plan(
    tmp_path: Path,
) -> None:
    payload_file = tmp_path / "fixture-ready.json"
    payload_file.write_text(
        json.dumps(
            {
                "Last_Name": "ZohoCliFixtureReady",
                "Company": "Zoho CLI Fixture",
                "Email": "fixture-ready@operator.test",
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(CRM_FIXTURE_PAYLOAD_PREFLIGHT_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CRM_FIXTURE_PAYLOAD_FILE": str(payload_file),
            "ZOHO_CRM_FIXTURE_PREFLIGHT_REPORT_DIR": str(tmp_path / "reports"),
            "ZOHO_CRM_FIXTURE_PREFLIGHT_RUN_ID": "unit-cleanup-missing",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert payload["blockers"] == ["cleanup_plan_missing"]
    assert payload["cleanup"] == {
        "required": True,
        "present": False,
        "lengthBucket": "missing",
        "actionPresent": False,
        "targetPresent": False,
        "qualityReady": False,
        "rawCleanupPlanStored": False,
    }
    assert payload["nextAction"] == "provide_cleanup_plan"


def test_crm_fixture_payload_preflight_blocks_vague_cleanup_plan(
    tmp_path: Path,
) -> None:
    payload_file = tmp_path / "fixture-ready.json"
    payload_file.write_text(
        json.dumps(
            {
                "Last_Name": "ZohoCliFixtureReady",
                "Company": "Zoho CLI Fixture",
                "Email": "fixture-ready@operator.test",
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(CRM_FIXTURE_PAYLOAD_PREFLIGHT_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CRM_FIXTURE_PAYLOAD_FILE": str(payload_file),
            "ZOHO_CRM_FIXTURE_CLEANUP_PLAN": "handle later",
            "ZOHO_CRM_FIXTURE_PREFLIGHT_REPORT_DIR": str(tmp_path / "reports"),
            "ZOHO_CRM_FIXTURE_PREFLIGHT_RUN_ID": "unit-cleanup-vague",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    assert "handle later" not in output
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert payload["blockers"] == [
        "cleanup_plan_too_short",
        "cleanup_plan_action_missing",
        "cleanup_plan_target_missing",
    ]
    assert payload["cleanup"] == {
        "required": True,
        "present": True,
        "lengthBucket": "too_short",
        "actionPresent": False,
        "targetPresent": False,
        "qualityReady": False,
        "rawCleanupPlanStored": False,
    }
    assert payload["nextAction"] == "improve_cleanup_plan"


def test_crm_fixture_operator_packet_reports_missing_payload(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    packet_file = reports_dir / "packet.json"

    result = subprocess.run(
        ["bash", str(CRM_FIXTURE_OPERATOR_PACKET_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CRM_FIXTURE_PACKET_REPORT_DIR": str(reports_dir),
            "ZOHO_CRM_FIXTURE_PACKET_FILE": str(packet_file),
            "ZOHO_CRM_FIXTURE_PACKET_RUN_ID": "unit-missing-payload",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    assert str(tmp_path) not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert payload["blockers"] == ["cleanup_plan_missing", "payload_file_required"]
    assert payload["payloadPreflight"]["status"] == "blocked"
    assert payload["payloadPreflight"]["blockers"] == [
        "payload_file_required",
        "cleanup_plan_missing",
    ]
    assert payload["dryRunReadiness"]["skipped"] is True
    assert payload["dryRunReadiness"]["skippedReason"] == "summary_file_not_provided"
    assert payload["releasePosture"]["normalUpsertExecuteBlocked"] is True
    assert payload["releasePosture"]["agentMayExecuteLiveFixture"] is False
    assert payload["nextAction"] == "provide_fixture_payload_file"
    assert json.loads(packet_file.read_text()) == payload


def test_crm_fixture_operator_packet_accepts_payload_preflight(
    tmp_path: Path,
) -> None:
    raw_email = "fixture-ready@operator.test"
    raw_cleanup = "delete fixture after validation"
    payload_file = tmp_path / "fixture-ready.json"
    payload_file.write_text(
        json.dumps(
            {
                "Last_Name": "ZohoCliFixtureReady",
                "Company": "Zoho CLI Fixture",
                "Email": raw_email,
            }
        ),
        encoding="utf-8",
    )
    reports_dir = tmp_path / "reports"

    result = subprocess.run(
        ["bash", str(CRM_FIXTURE_OPERATOR_PACKET_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CRM_FIXTURE_PAYLOAD_FILE": str(payload_file),
            "ZOHO_CRM_FIXTURE_CLEANUP_PLAN": raw_cleanup,
            "ZOHO_CRM_FIXTURE_PACKET_REPORT_DIR": str(reports_dir),
            "ZOHO_CRM_FIXTURE_PACKET_RUN_ID": "unit-ready-payload",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    assert raw_email not in result.stdout
    assert raw_cleanup not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "payload_preflight_ready"
    assert payload["blockers"] == []
    assert payload["payloadPreflight"]["ready"] is True
    assert payload["payloadPreflight"]["payload"]["dedicatedFixtureCandidate"] is True
    assert payload["payloadPreflight"]["payload"]["placeholderEmailCount"] == 0
    assert payload["dryRunReadiness"]["ready"] is False
    assert payload["dryRunReadiness"]["skipped"] is True
    assert payload["nextAction"] == "run_crm_fixture_live_smoke_dry_run"


def test_crm_fixture_operator_packet_blocks_vague_cleanup_plan(
    tmp_path: Path,
) -> None:
    payload_file = tmp_path / "fixture-ready.json"
    payload_file.write_text(
        json.dumps(
            {
                "Last_Name": "ZohoCliFixtureReady",
                "Company": "Zoho CLI Fixture",
                "Email": "fixture-ready@operator.test",
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(CRM_FIXTURE_OPERATOR_PACKET_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CRM_FIXTURE_PAYLOAD_FILE": str(payload_file),
            "ZOHO_CRM_FIXTURE_CLEANUP_PLAN": "later",
            "ZOHO_CRM_FIXTURE_PACKET_REPORT_DIR": str(tmp_path / "reports"),
            "ZOHO_CRM_FIXTURE_PACKET_RUN_ID": "unit-vague-cleanup",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    assert "later" not in output
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert payload["blockers"] == [
        "cleanup_plan_action_missing",
        "cleanup_plan_target_missing",
        "cleanup_plan_too_short",
    ]
    assert payload["payloadPreflight"]["cleanup"]["qualityReady"] is False
    assert payload["nextAction"] == "improve_cleanup_plan"


def test_crm_fixture_operator_packet_wraps_dry_run_readiness(
    tmp_path: Path,
) -> None:
    evidence = {
        "policyId": "crm-014-operator-fixture-evidence",
        "status": "ready_for_operator_live_fixture",
        "decision": "await_operator_live_fixture",
        "blockingReasons": ["live_fixture_not_recorded"],
        "operatorReadiness": {"readyForLiveFixture": True},
        "redaction": {"ok": True},
    }
    fake_zoho, calls_path = _write_fake_zoho_for_crm_fixture_readiness(
        tmp_path,
        evidence,
    )
    payload_file = tmp_path / "fixture-ready.json"
    payload_file.write_text(
        json.dumps(
            {
                "Last_Name": "ZohoCliFixtureReady",
                "Company": "Zoho CLI Fixture",
                "Email": "fixture-ready@operator.test",
            }
        ),
        encoding="utf-8",
    )
    summary_path = tmp_path / "crm_fixture_live_smoke_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "summaryVersion": 1,
                "runId": "fixture-run",
                "module": "Leads",
                "duplicateField": "Email",
                "idempotencyKey": "fixture-test",
                "payloadDigest": "sha256:abc123",
                "requiredApproval": "crm:fixture:upsert:Leads:abc123:fixture-test",
                "payloadTemplatePlaceholders": {"emailCount": 0},
                "executeRequested": False,
                "liveResultRecorded": False,
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(CRM_FIXTURE_OPERATOR_PACKET_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_BIN": str(fake_zoho),
            "FAKE_ZOHO_READINESS_CALLS": str(calls_path),
            "FAKE_CRM_FIXTURE_EVIDENCE_JSON": str(tmp_path / "evidence.json"),
            "ZOHO_CRM_FIXTURE_PAYLOAD_FILE": str(payload_file),
            "ZOHO_CRM_FIXTURE_CLEANUP_PLAN": "delete fixture after validation",
            "ZOHO_CRM_FIXTURE_SUMMARY_FILE": str(summary_path),
            "ZOHO_CRM_FIXTURE_PACKET_REPORT_DIR": str(tmp_path / "reports"),
            "ZOHO_CRM_FIXTURE_PACKET_RUN_ID": "unit-ready-evidence",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    payload = json.loads(result.stdout)
    assert payload["status"] == "ready_for_operator_live_fixture"
    assert payload["payloadPreflight"]["ready"] is True
    assert payload["dryRunReadiness"]["ready"] is True
    assert payload["dryRunReadiness"]["status"] == "ready_for_operator_live_fixture"
    assert payload["dryRunReadiness"]["evidenceStatus"] == (
        "ready_for_operator_live_fixture"
    )
    assert payload["nextAction"] == "operator_review_payload_cleanup_and_approval"
    calls = [json.loads(line) for line in calls_path.read_text().splitlines()]
    assert calls == [["crm", "fixture-evidence", "--summary-file", str(summary_path)]]


def _write_fake_zoho_for_crm_fixture_readiness(
    tmp_path: Path,
    evidence: dict,
) -> tuple[Path, Path]:
    calls_path = tmp_path / "zoho_readiness_calls.jsonl"
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    fake_zoho = tmp_path / "fake_zoho_readiness.py"
    fake_zoho.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
calls_path = Path(os.environ["FAKE_ZOHO_READINESS_CALLS"])
with calls_path.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(args) + "\\n")

if args[:2] == ["crm", "fixture-evidence"]:
    print(Path(os.environ["FAKE_CRM_FIXTURE_EVIDENCE_JSON"]).read_text())
else:
    print(json.dumps({"status":"error","error":"unexpected_args","args":args}))
    raise SystemExit(9)
"""
    )
    fake_zoho.chmod(fake_zoho.stat().st_mode | stat.S_IXUSR)
    return fake_zoho, calls_path


def test_crm_fixture_operator_readiness_bundle_requires_dry_run_evidence(
    tmp_path: Path,
) -> None:
    evidence = {
        "policyId": "crm-014-operator-fixture-evidence",
        "status": "ready_for_operator_live_fixture",
        "decision": "await_operator_live_fixture",
        "blockingReasons": ["live_fixture_not_recorded"],
        "operatorReadiness": {"readyForLiveFixture": True},
        "redaction": {"ok": True},
    }
    fake_zoho, calls_path = _write_fake_zoho_for_crm_fixture_readiness(
        tmp_path,
        evidence,
    )
    summary_path = tmp_path / "crm_fixture_live_smoke_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "summaryVersion": 1,
                "runId": "fixture-run",
                "module": "Leads",
                "duplicateField": "Email",
                "idempotencyKey": "fixture-test",
                "payloadDigest": "sha256:abc123",
                "requiredApproval": "crm:fixture:upsert:Leads:abc123:fixture-test",
                "payloadTemplatePlaceholders": {"emailCount": 0},
                "executeRequested": False,
                "liveResultRecorded": False,
            }
        ),
        encoding="utf-8",
    )
    reports_dir = tmp_path / "reports"
    bundle_file = reports_dir / "bundle.json"

    result = subprocess.run(
        ["bash", str(CRM_FIXTURE_READINESS_BUNDLE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_BIN": str(fake_zoho),
            "FAKE_ZOHO_READINESS_CALLS": str(calls_path),
            "FAKE_CRM_FIXTURE_EVIDENCE_JSON": str(tmp_path / "evidence.json"),
            "ZOHO_CRM_FIXTURE_SUMMARY_FILE": str(summary_path),
            "ZOHO_CRM_FIXTURE_READINESS_REPORT_DIR": str(reports_dir),
            "ZOHO_CRM_FIXTURE_READINESS_BUNDLE_FILE": str(bundle_file),
            "ZOHO_CRM_FIXTURE_READINESS_RUN_ID": "unit-test",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    assert str(tmp_path) not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "ready_for_operator_live_fixture"
    assert payload["blockers"] == []
    assert payload["summary"]["file"] == summary_path.name
    assert payload["summary"]["payloadTemplatePlaceholders"] == {"emailCount": 0}
    assert payload["evidence"]["status"] == "ready_for_operator_live_fixture"
    assert payload["releasePosture"] == {
        "normalUpsertExecuteBlocked": True,
        "agentMayExecuteLiveFixture": False,
        "agentMayRunNormalUpsertExecute": False,
        "liveFixtureRequiresOperatorApproval": True,
        "requiredLiveEnv": [
            "ZOHO_CRM_FIXTURE_EXECUTE=1",
            "ZOHO_CRM_ALLOW_LIVE_FIXTURE=1",
        ],
    }
    assert payload["nextAction"] == "operator_review_payload_cleanup_and_approval"
    assert json.loads(bundle_file.read_text()) == payload
    calls = [json.loads(line) for line in calls_path.read_text().splitlines()]
    assert calls == [["crm", "fixture-evidence", "--summary-file", str(summary_path)]]


def test_crm_fixture_operator_readiness_bundle_blocks_placeholder_payload(
    tmp_path: Path,
) -> None:
    evidence = {
        "policyId": "crm-014-operator-fixture-evidence",
        "status": "ready_for_operator_live_fixture",
        "decision": "await_operator_live_fixture",
        "blockingReasons": ["live_fixture_not_recorded"],
        "operatorReadiness": {"readyForLiveFixture": True},
        "redaction": {"ok": True},
    }
    fake_zoho, calls_path = _write_fake_zoho_for_crm_fixture_readiness(
        tmp_path,
        evidence,
    )
    summary_path = tmp_path / "crm_fixture_live_smoke_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "summaryVersion": 1,
                "runId": "fixture-run",
                "module": "Leads",
                "duplicateField": "Email",
                "payloadDigest": "sha256:abc123",
                "requiredApproval": "crm:fixture:upsert:Leads:abc123:fixture-test",
                "payloadTemplatePlaceholders": {"emailCount": 1},
                "executeRequested": False,
                "liveResultRecorded": False,
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(CRM_FIXTURE_READINESS_BUNDLE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_BIN": str(fake_zoho),
            "FAKE_ZOHO_READINESS_CALLS": str(calls_path),
            "FAKE_CRM_FIXTURE_EVIDENCE_JSON": str(tmp_path / "evidence.json"),
            "ZOHO_CRM_FIXTURE_SUMMARY_FILE": str(summary_path),
            "ZOHO_CRM_FIXTURE_READINESS_REPORT_DIR": str(tmp_path / "reports"),
            "ZOHO_CRM_FIXTURE_READINESS_RUN_ID": "unit-test-placeholder",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert "fixture_payload_placeholder_email" in payload["blockers"]
    assert payload["nextAction"] == "fix_blockers"


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
    assert "ZOHO_CLIQ_PUBLIC_CALLBACK_SCRIPT" in script
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


def test_openclaw_cliq_public_callback_smoke_verifies_statuses_without_leaking_secret(
    tmp_path: Path,
) -> None:
    calls_path = tmp_path / "curl_calls.jsonl"
    report_path = tmp_path / "reports" / "public-callback.json"
    fake_curl = tmp_path / "fake_curl.py"
    fake_curl.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]
with open(os.environ["FAKE_CURL_CALLS"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(args) + "\\n")
has_secret = any(
    arg.lower().startswith("x-cliq-webhook-secret:")
    or (
        index > 0
        and args[index - 1] == "-H"
        and arg.lower().startswith("x-cliq-webhook-secret:")
    )
    for index, arg in enumerate(args)
)
print("200" if has_secret else "401", end="")
"""
    )
    fake_curl.chmod(fake_curl.stat().st_mode | stat.S_IXUSR)

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_PUBLIC_CALLBACK_SMOKE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "CURL_BIN": str(fake_curl),
            "FAKE_CURL_CALLS": str(calls_path),
            "ZOHO_CLIQ_PUBLIC_WEBHOOK_URL": "https://public.example.test/webhooks/cliq",
            "ZOHO_CLIQ_WEBHOOK_SECRET": "unit-public-secret",
            "ZOHO_CLIQ_PUBLIC_CALLBACK_REPORT_FILE": str(report_path),
            "ZOHO_CLIQ_PUBLIC_CALLBACK_RUN_ID": "unit-public-callback",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    assert "unit-public-secret" not in output
    assert "M-PUBLIC-CALLBACK" not in output

    payload = json.loads(result.stdout)
    assert payload["schemaVersion"] == 1
    assert payload["kind"] == "openclaw_cliq_public_callback_smoke"
    assert payload["runId"] == "unit-public-callback"
    assert payload["status"] == "public_callback_verified"
    assert payload["webhook"] == {
        "scheme": "https",
        "host": "public.example.test",
        "path": "/webhooks/cliq",
    }
    assert payload["checks"]["missingSecret"] == {
        "expectedStatus": 401,
        "actualStatus": "401",
    }
    assert payload["checks"]["authenticatedUnsupportedHandler"] == {
        "expectedStatus": 200,
        "actualStatus": "200",
    }
    assert payload["redaction"] == {
        "rawWebhookPayloadStored": False,
        "responseBodyStored": False,
        "secretsStored": False,
    }
    assert json.loads(report_path.read_text()) == payload
    assert "unit-public-secret" not in report_path.read_text()
    calls = [json.loads(line) for line in calls_path.read_text().splitlines()]
    assert len(calls) == 2


def test_openclaw_cliq_public_callback_smoke_rejects_placeholder_url() -> None:
    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_PUBLIC_CALLBACK_SMOKE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CLIQ_PUBLIC_WEBHOOK_URL": "https://<your-tunnel-or-gateway>/webhooks/cliq",
            "ZOHO_CLIQ_WEBHOOK_SECRET": "unit-public-secret",
            "ZOHO_CLIQ_PUBLIC_CALLBACK_RUN_ID": "unit-public-placeholder",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 2, output
    assert "unit-public-secret" not in output
    payload = json.loads(result.stdout)
    assert payload["kind"] == "openclaw_cliq_public_callback_smoke"
    assert payload["runId"] == "unit-public-placeholder"
    assert payload["status"] == "error"
    assert payload["error"] == "public_webhook_url_placeholder"


def test_openclaw_cliq_live_ingress_diagnostic_reports_no_recent_webhook(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "openclaw.log"
    log_path.write_text(
        '[zoho-cliq-audit] {"kind":"webhook_ingress","outcome":"dispatched",'
        '"correlationId":"old","handlerKind":"mention",'
        '"createdAt":"2026-05-12T04:00:00Z"}\n'
        '[zoho-cliq-audit] {"kind":"webhook_ingress","outcome":"ignored",'
        '"correlationId":"smoke","handlerKind":"welcome",'
        '"reason":"unsupported_handler","createdAt":"2026-05-12T04:59:00Z"}\n'
    )
    report_path = tmp_path / "reports" / "ingress.json"

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_LIVE_INGRESS_DIAGNOSTIC_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_LOG_FILE": str(log_path),
            "ZOHO_CLIQ_INGRESS_NOW_ISO": "2026-05-12T05:00:00Z",
            "ZOHO_CLIQ_INGRESS_LOOKBACK_SECONDS": "900",
            "ZOHO_CLIQ_INGRESS_RUN_ID": "unit-no-ingress",
            "ZOHO_CLIQ_INGRESS_REPORT_FILE": str(report_path),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    payload = json.loads(result.stdout)
    assert payload["kind"] == "openclaw_cliq_live_ingress_diagnostic"
    assert payload["runId"] == "unit-no-ingress"
    assert payload["status"] == "blocked"
    assert payload["error"] == "no_recent_webhook_ingress"
    assert payload["blockers"] == ["no_recent_webhook_ingress"]
    assert payload["nextAction"] == "send_or_fix_zoho_bot_handler"
    assert payload["counts"]["webhookIngress"] == 0
    assert payload["counts"]["ignoredDiagnosticSmokeRecords"] == 1
    assert payload["redaction"]["rawMessageBodyStored"] is False
    assert json.loads(report_path.read_text()) == payload


def test_openclaw_cliq_live_ingress_diagnostic_reports_active_delivery(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "openclaw.log"
    log_path.write_text(
        "\n".join(
            [
                (
                    '[zoho-cliq-audit] {"kind":"native_dispatch",'
                    '"outcome":"dispatched","correlationId":"c-live",'
                    '"accountId":"default","network":"happydistrouklimited",'
                    '"handlerKind":"mention","createdAt":"2026-05-12T05:00:20Z",'
                    '"event":{"chatType":"direct","mentioned":true,"textLength":29},'
                    '"nativeDispatch":{"agentId":"zoho-employee-test",'
                    '"agentModel":"openai-codex/gpt-5.3-codex",'
                    '"deliveryCount":1,"messageIds":["cliq-redacted"]}}'
                ),
                (
                    '{"message":"[zoho-cliq-audit] {\\"kind\\":\\"webhook_ingress\\",'
                    '\\"outcome\\":\\"dispatched\\",\\"correlationId\\":\\"c-live\\",'
                    '\\"accountId\\":\\"default\\",\\"network\\":\\"happydistrouklimited\\",'
                    '\\"handlerKind\\":\\"mention\\",'
                    '\\"createdAt\\":\\"2026-05-12T05:00:30Z\\",'
                    '\\"event\\":{\\"chatType\\":\\"direct\\",'
                    '\\"mentioned\\":true,\\"textLength\\":29}}"}'
                ),
                (
                    '[zoho-cliq-audit] {"kind":"native_dispatch",'
                    '"outcome":"dispatched","correlationId":"c-live",'
                    '"accountId":"default","network":"happydistrouklimited",'
                    '"handlerKind":"mention","createdAt":"2026-05-12T05:00:40Z",'
                    '"event":{"chatType":"direct","mentioned":true,"textLength":29},'
                    '"nativeDispatch":{"agentId":"zoho-employee-test",'
                    '"agentModel":"openai-codex/gpt-5.3-codex",'
                    '"deliveryCount":1,"messageIds":["cliq-redacted"]}}'
                ),
            ]
        )
        + "\n"
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_LIVE_INGRESS_DIAGNOSTIC_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_LOG_FILE": str(log_path),
            "ZOHO_CLIQ_INGRESS_NOW_ISO": "2026-05-12T05:01:00Z",
            "ZOHO_CLIQ_INGRESS_LOOKBACK_SECONDS": "900",
            "ZOHO_CLIQ_INGRESS_RUN_ID": "unit-active-ingress",
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
    assert payload["status"] == "live_ingress_active"
    assert payload["blockers"] == []
    assert payload["nextAction"] == "collect_trusted_reply_facts_if_needed"
    assert payload["counts"]["webhookIngress"] == 1
    assert payload["counts"]["nativeDispatch"] == 2
    assert payload["latestWebhook"]["handlerKind"] == "mention"
    assert payload["latestWebhook"]["textLength"] == 29
    assert payload["latestNativeDispatch"]["agentId"] == "zoho-employee-test"
    assert payload["latestNativeDispatch"]["agentModel"] == "openai-codex/gpt-5.3-codex"
    assert payload["latestNativeDispatch"]["deliveryCount"] == 1
    assert payload["latestNativeDispatch"]["messageIdCount"] == 1
    assert payload["redaction"] == {
        "rawWebhookPayloadStored": False,
        "rawMessageBodyStored": False,
        "rawCliqReplyBodyStored": False,
        "secretsStored": False,
    }
    assert "hello from user" not in output
    assert "unit-secret" not in output


def test_openclaw_cliq_bot_no_response_packet_reports_handler_not_posting(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "openclaw.log"
    log_path.write_text(
        '[zoho-cliq-audit] {"kind":"webhook_ingress","outcome":"dispatched",'
        '"correlationId":"old","handlerKind":"mention",'
        '"createdAt":"2026-05-12T04:00:00Z"}\n'
    )
    report_dir = tmp_path / "reports"

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_BOT_NO_RESPONSE_PACKET_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_LOG_FILE": str(log_path),
            "ZOHO_CLIQ_INGRESS_NOW_ISO": "2026-05-12T05:00:00Z",
            "ZOHO_CLIQ_INGRESS_LOOKBACK_SECONDS": "900",
            "ZOHO_CLIQ_BOT_PACKET_RUN_ID": "unit-no-response",
            "ZOHO_CLIQ_BOT_PACKET_REPORT_DIR": str(report_dir),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    payload = json.loads(result.stdout)
    assert payload["kind"] == "openclaw_cliq_bot_no_response_packet"
    assert payload["status"] == "blocked"
    assert payload["blockers"] == ["no_recent_webhook_ingress"]
    assert payload["nextAction"] == "fix_zoho_bot_handler_trigger"
    assert payload["publicCallback"]["checked"] is False
    assert payload["publicCallback"]["status"] == "not_checked"
    assert payload["ingress"]["error"] == "no_recent_webhook_ingress"
    assert payload["handlerTrigger"]["checked"] is True
    assert payload["handlerTrigger"]["status"] == "blocked"
    assert payload["handlerTrigger"]["nextAction"] == "set_public_webhook_url"
    assert payload["redaction"]["secretsStored"] is False
    assert (report_dir / payload["evidenceFiles"]["ingressDiagnostic"]).exists()
    assert (report_dir / payload["evidenceFiles"]["publicCallback"]).exists()
    assert (report_dir / payload["evidenceFiles"]["handlerTrigger"]).exists()


def test_openclaw_cliq_bot_no_response_packet_embeds_handler_trigger_packet(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "openclaw.log"
    log_path.write_text(
        '[zoho-cliq-audit] {"kind":"webhook_ingress","outcome":"dispatched",'
        '"correlationId":"old","handlerKind":"mention",'
        '"createdAt":"2026-05-12T04:00:00Z"}\n'
    )
    callback_script = tmp_path / "public_callback.sh"
    callback_script.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' "
        '\'{"schemaVersion":1,"kind":"openclaw_cliq_public_callback_smoke",'
        '"status":"public_callback_verified",'
        '"webhook":{"scheme":"https","host":"cliq.example.test","path":"/webhooks/cliq"},'
        '"checks":{"missingSecret":{"expectedStatus":401,"actualStatus":"401"},'
        '"authenticatedUnsupportedHandler":{"expectedStatus":200,"actualStatus":"200"}},'
        '"redaction":{"rawWebhookPayloadStored":false,'
        '"responseBodyStored":false,"secretsStored":false}}\' '
        '> "$ZOHO_CLIQ_PUBLIC_CALLBACK_REPORT_FILE"\n'
        'cat "$ZOHO_CLIQ_PUBLIC_CALLBACK_REPORT_FILE"\n'
    )
    callback_script.chmod(0o755)
    report_dir = tmp_path / "reports"

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_BOT_NO_RESPONSE_PACKET_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_LOG_FILE": str(log_path),
            "ZOHO_CLIQ_INGRESS_NOW_ISO": "2026-05-12T05:00:00Z",
            "ZOHO_CLIQ_INGRESS_LOOKBACK_SECONDS": "900",
            "ZOHO_CLIQ_PUBLIC_WEBHOOK_URL": "https://cliq.example.test/webhooks/cliq",
            "ZOHO_CLIQ_PUBLIC_CALLBACK_SCRIPT": str(callback_script),
            "ZOHO_CLIQ_HANDLER_TARGETS": "mention,message",
            "ZOHO_CLIQ_EXPECTED_BOT_NAME": "oldsix",
            "ZOHO_CLIQ_BOT_PACKET_RUN_ID": "unit-no-response-handler-trigger",
            "ZOHO_CLIQ_BOT_PACKET_REPORT_DIR": str(report_dir),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert payload["blockers"] == ["no_recent_webhook_ingress"]
    assert payload["nextAction"] == "fix_zoho_bot_handler_trigger"
    assert payload["commandExits"]["handlerTrigger"] == 0
    assert payload["evidenceFiles"]["handlerTrigger"].endswith("_handler_trigger.json")
    assert payload["handlerTrigger"]["checked"] is True
    assert payload["handlerTrigger"]["status"] == "handler_trigger_packet_ready"
    assert (
        payload["handlerTrigger"]["nextAction"] == "paste_or_recheck_zoho_bot_handlers"
    )
    assert payload["handlerTrigger"]["expectedBot"]["name"] == "oldsix"
    assert payload["handlerTrigger"]["handlers"]["selected"] == ["mention", "message"]
    assert (
        payload["handlerTrigger"]["publicWebhook"]["url"]
        == "https://cliq.example.test/webhooks/cliq"
    )
    assert payload["handlerTrigger"]["delugeContract"]["secretValueStored"] is False
    assert payload["handlerTrigger"]["redaction"]["secretsStored"] is False
    assert (report_dir / payload["evidenceFiles"]["handlerTrigger"]).exists()


def test_openclaw_cliq_bot_no_response_packet_reports_active_ingress(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "openclaw.log"
    log_path.write_text(
        "\n".join(
            [
                (
                    '[zoho-cliq-audit] {"kind":"webhook_ingress",'
                    '"outcome":"dispatched","correlationId":"c-live",'
                    '"handlerKind":"mention","createdAt":"2026-05-12T05:00:00Z",'
                    '"event":{"chatType":"direct","mentioned":true,"textLength":11}}'
                ),
                (
                    '[zoho-cliq-audit] {"kind":"native_dispatch",'
                    '"outcome":"dispatched","correlationId":"c-live",'
                    '"handlerKind":"mention","createdAt":"2026-05-12T05:00:02Z",'
                    '"event":{"chatType":"direct","mentioned":true,"textLength":11},'
                    '"nativeDispatch":{"agentId":"zoho-employee-test",'
                    '"agentModel":"openai-codex/gpt-5.3-codex",'
                    '"deliveryCount":1,"messageIds":["cliq-redacted"]}}'
                ),
            ]
        )
        + "\n"
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_BOT_NO_RESPONSE_PACKET_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_LOG_FILE": str(log_path),
            "ZOHO_CLIQ_INGRESS_NOW_ISO": "2026-05-12T05:00:10Z",
            "ZOHO_CLIQ_INGRESS_LOOKBACK_SECONDS": "900",
            "ZOHO_CLIQ_EXPECTED_AGENT_ID": "zoho-employee-test",
            "ZOHO_CLIQ_EXPECTED_AGENT_MODEL": "openai-codex/gpt-5.3-codex",
            "ZOHO_CLIQ_BOT_PACKET_RUN_ID": "unit-active-response",
            "ZOHO_CLIQ_BOT_PACKET_REPORT_DIR": str(tmp_path / "reports"),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    payload = json.loads(result.stdout)
    assert payload["status"] == "ingress_active"
    assert payload["blockers"] == []
    assert payload["nextAction"] == "collect_trusted_reply_facts_if_needed"
    assert payload["ingress"]["status"] == "live_ingress_active"
    assert payload["ingress"]["latestNativeDispatch"]["deliveryCount"] == 1
    assert payload["publicCallback"]["status"] == "not_checked"
    assert payload["handlerTrigger"]["checked"] is False
    assert payload["handlerTrigger"]["reason"] == "not_no_recent_webhook_ingress"


def test_openclaw_cliq_bot_no_response_packet_prioritizes_callback_failure(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "openclaw.log"
    log_path.write_text(
        '[zoho-cliq-audit] {"kind":"webhook_ingress","outcome":"dispatched",'
        '"correlationId":"c-live","handlerKind":"mention",'
        '"createdAt":"2026-05-12T05:00:00Z"}\n'
        '[zoho-cliq-audit] {"kind":"native_dispatch","outcome":"dispatched",'
        '"correlationId":"c-live","handlerKind":"mention",'
        '"createdAt":"2026-05-12T05:00:01Z",'
        '"nativeDispatch":{"agentId":"zoho-employee-test","deliveryCount":1,'
        '"messageIds":["cliq-redacted"]}}\n'
    )
    callback_script = tmp_path / "public_callback.sh"
    callback_script.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' "
        '\'{"schemaVersion":1,"kind":"openclaw_cliq_public_callback_smoke",'
        '"status":"error","error":"authenticated_status_mismatch",'
        '"redaction":{"rawWebhookPayloadStored":false,'
        '"responseBodyStored":false,"secretsStored":false}}\' '
        '> "$ZOHO_CLIQ_PUBLIC_CALLBACK_REPORT_FILE"\n'
        'cat "$ZOHO_CLIQ_PUBLIC_CALLBACK_REPORT_FILE"\n'
        "exit 1\n"
    )
    callback_script.chmod(0o755)

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_BOT_NO_RESPONSE_PACKET_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "OPENCLAW_LOG_FILE": str(log_path),
            "ZOHO_CLIQ_INGRESS_NOW_ISO": "2026-05-12T05:00:10Z",
            "ZOHO_CLIQ_INGRESS_LOOKBACK_SECONDS": "900",
            "ZOHO_CLIQ_PUBLIC_WEBHOOK_URL": "https://cliq.example.test/webhooks/cliq",
            "ZOHO_CLIQ_PUBLIC_CALLBACK_SCRIPT": str(callback_script),
            "ZOHO_CLIQ_BOT_PACKET_RUN_ID": "unit-callback-failure",
            "ZOHO_CLIQ_BOT_PACKET_REPORT_DIR": str(tmp_path / "reports"),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert payload["blockers"] == ["public_callback_unverified"]
    assert payload["nextAction"] == "fix_public_callback"
    assert payload["commandExits"]["publicCallback"] == 1
    assert payload["commandExits"]["handlerTrigger"] is None
    assert payload["publicCallback"]["error"] == "authenticated_status_mismatch"
    assert payload["ingress"]["status"] == "live_ingress_active"
    assert payload["handlerTrigger"]["checked"] is False
    assert payload["handlerTrigger"]["reason"] == "not_no_recent_webhook_ingress"


def test_openclaw_cliq_handler_trigger_packet_is_ready_without_leaking_secret(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "reports" / "handler-packet.json"

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_HANDLER_TRIGGER_PACKET_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CLIQ_PUBLIC_WEBHOOK_URL": "https://cliq.example.test/webhooks/cliq",
            "ZOHO_CLIQ_WEBHOOK_SECRET": "unit-handler-secret",
            "ZOHO_CLIQ_HANDLER_TARGETS": "mention,message",
            "ZOHO_CLIQ_EXPECTED_BOT_NAME": "oldsix",
            "ZOHO_CLIQ_HANDLER_PACKET_FILE": str(report_path),
            "ZOHO_CLIQ_HANDLER_PACKET_RUN_ID": "unit-handler-ready",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    assert "unit-handler-secret" not in output
    payload = json.loads(result.stdout)
    assert payload["kind"] == "openclaw_cliq_handler_trigger_packet"
    assert payload["runId"] == "unit-handler-ready"
    assert payload["status"] == "handler_trigger_packet_ready"
    assert payload["blockers"] == []
    assert payload["expectedBot"] == {
        "name": "oldsix",
        "configuredByOperator": True,
    }
    assert payload["publicWebhook"] == {
        "provided": True,
        "readyForPaste": True,
        "scheme": "https",
        "host": "cliq.example.test",
        "path": "/webhooks/cliq",
        "expectedPath": "/webhooks/cliq",
        "urlStored": True,
        "url": "https://cliq.example.test/webhooks/cliq",
    }
    assert payload["handlers"]["selected"] == ["mention", "message"]
    assert payload["handlers"]["invalid"] == []
    assert payload["handlers"]["recommendedFirst"] == ["mention", "message"]
    assert payload["handlers"]["saveTargets"][0]["handler"] == "mention"
    assert (
        payload["handlers"]["saveTargets"][0]["zohoScreen"]
        == "Bot > Edit Handlers > Mention Handler > Edit Code > Save"
    )
    assert payload["delugeContract"]["bodyField"] == "body:payload.toString()"
    assert payload["delugeContract"]["secretPresentInCurrentEnv"] is True
    assert payload["delugeContract"]["secretValueStored"] is False
    assert (
        payload["operatorChecklist"][0]["expectedStatus"] == "public_callback_verified"
    )
    assert payload["redaction"]["secretsStored"] is False
    assert payload["nextAction"] == "paste_or_recheck_zoho_bot_handlers"
    assert json.loads(report_path.read_text()) == payload
    assert "unit-handler-secret" not in report_path.read_text()


def test_openclaw_cliq_handler_trigger_packet_blocks_bad_inputs(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_HANDLER_TRIGGER_PACKET_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CLIQ_PUBLIC_WEBHOOK_URL": "https://cliq.example.test/not-webhook",
            "ZOHO_CLIQ_HANDLER_TARGETS": "mention,call",
            "ZOHO_CLIQ_HANDLER_PACKET_REPORT_DIR": str(tmp_path / "reports"),
            "ZOHO_CLIQ_HANDLER_PACKET_RUN_ID": "unit-handler-blocked",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 1, output
    payload = json.loads(result.stdout)
    assert payload["kind"] == "openclaw_cliq_handler_trigger_packet"
    assert payload["status"] == "blocked"
    assert payload["blockers"] == [
        "public_webhook_path_mismatch",
        "handler_targets_invalid",
    ]
    assert payload["handlers"]["invalid"] == ["call"]
    assert payload["publicWebhook"]["path"] == "/not-webhook"
    assert payload["nextAction"] == "fix_public_webhook_url"


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


def test_openclaw_cliq_trusted_reply_facts_prepare_hashes_raw_ids(
    tmp_path: Path,
) -> None:
    facts_path = tmp_path / "reports" / "trusted-reply-facts.json"

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_TRUSTED_REPLY_FACTS_PREPARE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE": str(facts_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID": "unit-facts-prepare",
            "ZOHO_CLIQ_TRUSTED_SENDER_ID": "sender-raw-id",
            "ZOHO_CLIQ_TRUSTED_MESSAGE_ID": "message-raw-id",
            "ZOHO_CLIQ_DELIVERY_ID": "delivery-raw-id",
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
    assert str(facts_path) not in output

    payload = json.loads(result.stdout)
    assert payload["kind"] == "openclaw_cliq_trusted_reply_facts_prepare"
    assert payload["status"] == "facts_file_ready"
    assert payload["factsFile"] == "trusted-reply-facts.json"
    assert payload["facts"] == {
        "trustedSenderId": "hash",
        "trustedMessageId": "hash",
        "deliveryId": "hash",
    }
    assert payload["redaction"] == {
        "rawIdsStored": False,
        "hashValuesStored": True,
        "localPathsStored": False,
        "secretsStored": False,
    }

    facts = json.loads(facts_path.read_text())
    assert facts["kind"] == "openclaw_cliq_trusted_reply_facts"
    assert facts["trustedSenderIdHash"] == _sha256_ref("sender-raw-id")
    assert facts["trustedMessageIdHash"] == _sha256_ref("message-raw-id")
    assert facts["deliveryIdHash"] == _sha256_ref("delivery-raw-id")
    assert "sender-raw-id" not in facts_path.read_text()
    assert "message-raw-id" not in facts_path.read_text()
    assert "delivery-raw-id" not in facts_path.read_text()


def test_openclaw_cliq_trusted_reply_facts_prepare_reads_raw_facts_file(
    tmp_path: Path,
) -> None:
    raw_facts_path = tmp_path / "trusted-reply-raw-facts.json"
    facts_path = tmp_path / "reports" / "trusted-reply-facts.json"
    raw_facts_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "kind": "openclaw_cliq_trusted_reply_raw_facts",
                "trustedMention": {
                    "trustedSenderId": "sender-raw-id",
                    "messageId": "message-raw-id",
                },
                "delivery": {"messageId": "delivery-raw-id"},
            }
        )
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_TRUSTED_REPLY_FACTS_PREPARE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CLIQ_TRUSTED_REPLY_RAW_FACTS_FILE": str(raw_facts_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE": str(facts_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID": "unit-facts-raw-file",
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
    assert str(raw_facts_path) not in output
    assert str(facts_path) not in output

    payload = json.loads(result.stdout)
    assert payload["kind"] == "openclaw_cliq_trusted_reply_facts_prepare"
    assert payload["status"] == "facts_file_ready"
    assert payload["factsFile"] == "trusted-reply-facts.json"

    facts = json.loads(facts_path.read_text())
    assert facts["trustedSenderIdHash"] == _sha256_ref("sender-raw-id")
    assert facts["trustedMessageIdHash"] == _sha256_ref("message-raw-id")
    assert facts["deliveryIdHash"] == _sha256_ref("delivery-raw-id")
    assert "sender-raw-id" not in facts_path.read_text()
    assert "message-raw-id" not in facts_path.read_text()
    assert "delivery-raw-id" not in facts_path.read_text()


def test_openclaw_cliq_trusted_reply_facts_prepare_rejects_raw_body_file(
    tmp_path: Path,
) -> None:
    raw_facts_path = tmp_path / "trusted-reply-raw-facts.json"
    facts_path = tmp_path / "reports" / "trusted-reply-facts.json"
    raw_facts_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "kind": "openclaw_cliq_trusted_reply_raw_facts",
                "trustedSenderId": "sender-raw-id",
                "trustedMessageId": "message-raw-id",
                "deliveryId": "delivery-raw-id",
                "rawMessageBody": "@oldsix run the thing",
            }
        )
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_TRUSTED_REPLY_FACTS_PREPARE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CLIQ_TRUSTED_REPLY_RAW_FACTS_FILE": str(raw_facts_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE": str(facts_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID": "unit-facts-raw-body",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 2, output
    assert "sender-raw-id" not in output
    payload = json.loads(result.stdout)
    assert payload["kind"] == "openclaw_cliq_trusted_reply_facts_prepare"
    assert payload["error"] == "raw_facts_file_forbidden_body_present"
    assert not facts_path.exists()


def test_openclaw_cliq_trusted_reply_facts_prepare_rejects_placeholder_raw_id(
    tmp_path: Path,
) -> None:
    facts_path = tmp_path / "reports" / "trusted-reply-facts.json"

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_TRUSTED_REPLY_FACTS_PREPARE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE": str(facts_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID": "unit-facts-placeholder",
            "ZOHO_CLIQ_TRUSTED_SENDER_ID": "<trusted_cliq_user_id>",
            "ZOHO_CLIQ_TRUSTED_MESSAGE_ID": "message-raw-id",
            "ZOHO_CLIQ_DELIVERY_ID": "delivery-raw-id",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 2, output
    assert "<trusted_cliq_user_id>" not in output
    payload = json.loads(result.stdout)
    assert payload["kind"] == "openclaw_cliq_trusted_reply_facts_prepare"
    assert payload["error"] == "trusted_sender_raw_placeholder"
    assert not facts_path.exists()


def test_openclaw_cliq_trusted_reply_facts_prepare_reports_missing_fact(
    tmp_path: Path,
) -> None:
    facts_path = tmp_path / "reports" / "trusted-reply-facts.json"

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_TRUSTED_REPLY_FACTS_PREPARE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE": str(facts_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID": "unit-facts-missing",
            "ZOHO_CLIQ_TRUSTED_MESSAGE_ID_HASH": "sha256:message",
            "ZOHO_CLIQ_DELIVERY_ID_HASH": "sha256:reply",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["kind"] == "openclaw_cliq_trusted_reply_facts_prepare"
    assert payload["error"] == "trusted_sender_hash_missing"
    assert not facts_path.exists()


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


def test_openclaw_cliq_trusted_reply_bundle_accepts_hash_facts_file(
    tmp_path: Path,
) -> None:
    route_path = tmp_path / "route.json"
    facts_path = tmp_path / "trusted-reply-facts.json"
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
    facts_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "kind": "openclaw_cliq_trusted_reply_facts",
                "trustedSenderIdHash": _sha256_ref("sender-raw-id"),
                "trustedMessageIdHash": _sha256_ref("message-raw-id"),
                "deliveryIdHash": _sha256_ref("delivery-raw-id"),
            }
        )
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_BUNDLE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CLIQ_ROUTE_REPORT_FILE": str(route_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE": str(facts_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_EVIDENCE_FILE": str(evidence_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_REPORT_FILE": str(check_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID": "unit-bundle-facts-file",
            "ZOHO_CLIQ_EXPECTED_AGENT_ID": "zoho-employee-test",
            "ZOHO_CLIQ_EXPECTED_AGENT_MODEL": "openai-codex/gpt-5.3-codex",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    assert str(facts_path) not in output
    check_payload = json.loads(result.stdout)
    assert check_payload["status"] == "trusted_reply_recorded"

    evidence = json.loads(evidence_path.read_text())
    assert evidence["trustedMention"]["trustedSenderIdHash"] == _sha256_ref(
        "sender-raw-id"
    )
    assert evidence["trustedMention"]["messageIdHash"] == _sha256_ref("message-raw-id")
    assert evidence["delivery"]["deliveryIdHash"] == _sha256_ref("delivery-raw-id")


def test_openclaw_cliq_trusted_reply_bundle_accepts_raw_facts_file(
    tmp_path: Path,
) -> None:
    route_path = tmp_path / "route.json"
    raw_facts_path = tmp_path / "trusted-reply-raw-facts.json"
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
    raw_facts_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "kind": "openclaw_cliq_trusted_reply_raw_facts",
                "trustedMention": {
                    "trustedSenderId": "sender-raw-id",
                    "messageId": "message-raw-id",
                },
                "delivery": {"messageId": "delivery-raw-id"},
            }
        )
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_BUNDLE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CLIQ_ROUTE_REPORT_FILE": str(route_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_RAW_FACTS_FILE": str(raw_facts_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_REPORT_DIR": str(reports_dir),
            "ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID": "unit-bundle-raw-facts-file",
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
    assert str(raw_facts_path) not in output

    check_payload = json.loads(result.stdout)
    assert check_payload["status"] == "trusted_reply_recorded"

    facts_path = (
        reports_dir
        / "openclaw_cliq_trusted_reply_facts_unit-bundle-raw-facts-file.json"
    )
    evidence_path = (
        reports_dir / "openclaw_cliq_trusted_reply_unit-bundle-raw-facts-file.json"
    )
    assert facts_path.exists()
    assert evidence_path.exists()
    facts = json.loads(facts_path.read_text())
    evidence = json.loads(evidence_path.read_text())
    assert facts["trustedSenderIdHash"] == _sha256_ref("sender-raw-id")
    assert facts["trustedMessageIdHash"] == _sha256_ref("message-raw-id")
    assert facts["deliveryIdHash"] == _sha256_ref("delivery-raw-id")
    assert evidence["trustedMention"]["trustedSenderIdHash"] == _sha256_ref(
        "sender-raw-id"
    )
    assert evidence["trustedMention"]["messageIdHash"] == _sha256_ref("message-raw-id")
    assert evidence["delivery"]["deliveryIdHash"] == _sha256_ref("delivery-raw-id")
    assert "sender-raw-id" not in facts_path.read_text()
    assert "message-raw-id" not in evidence_path.read_text()
    assert "delivery-raw-id" not in evidence_path.read_text()


def test_openclaw_cliq_trusted_reply_bundle_rejects_placeholder_raw_facts_file(
    tmp_path: Path,
) -> None:
    route_path = tmp_path / "route.json"
    raw_facts_path = tmp_path / "trusted-reply-raw-facts.json"
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
    raw_facts_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "kind": "openclaw_cliq_trusted_reply_raw_facts",
                "trustedMention": {
                    "trustedSenderId": "replace-me",
                    "messageId": "message-raw-id",
                },
                "delivery": {"messageId": "delivery-raw-id"},
            }
        )
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_BUNDLE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CLIQ_ROUTE_REPORT_FILE": str(route_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_RAW_FACTS_FILE": str(raw_facts_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_REPORT_DIR": str(reports_dir),
            "ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID": "unit-bundle-placeholder-raw-facts",
            "ZOHO_CLIQ_EXPECTED_AGENT_ID": "zoho-employee-test",
            "ZOHO_CLIQ_EXPECTED_AGENT_MODEL": "openai-codex/gpt-5.3-codex",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 2, output
    assert "replace-me" not in output
    payload = json.loads(result.stdout)
    assert payload["kind"] == "openclaw_cliq_trusted_reply_facts_prepare"
    assert payload["error"] == "trusted_sender_raw_placeholder"
    assert not (
        reports_dir
        / "openclaw_cliq_trusted_reply_facts_unit-bundle-placeholder-raw-facts.json"
    ).exists()
    assert not (
        reports_dir
        / "openclaw_cliq_trusted_reply_unit-bundle-placeholder-raw-facts.json"
    ).exists()


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
    assert payload["reportFiles"] == {
        "routePreflight": "openclaw_cliq_route_preflight_unit-bundle-plan.json",
        "plan": "openclaw_cliq_trusted_reply_plan_unit-bundle-plan.json",
        "evidence": "openclaw_cliq_trusted_reply_unit-bundle-plan.json",
        "check": "openclaw_cliq_trusted_reply_check_unit-bundle-plan.json",
    }
    assert payload["reportsReady"] == {
        "routePreflight": True,
        "plan": True,
        "evidence": False,
        "check": False,
    }
    assert payload["redaction"] == {
        "rawIdsStored": False,
        "hashValuesStored": False,
        "localPathsStored": False,
        "secretsStored": False,
    }
    assert payload["collectionGuide"] == {
        "sendExactlyOneTrustedMention": True,
        "requiredLiveFacts": [
            "trustedSenderId",
            "trustedMessageId",
            "deliveryId",
        ],
        "forbiddenEvidence": [
            "rawWebhookPayload",
            "rawMessageBody",
            "rawCliqReplyBody",
            "secrets",
        ],
        "hashRawIdsBeforeEvidence": True,
        "preferredFactSource": "ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE",
        "factsFileKind": "openclaw_cliq_trusted_reply_facts",
        "rawFactsPrepareEnv": "ZOHO_CLIQ_TRUSTED_REPLY_RAW_FACTS_FILE",
        "rawFactsFileKind": "openclaw_cliq_trusted_reply_raw_facts",
        "factsPrepareReadyStatus": "facts_file_ready",
        "successStatus": "trusted_reply_recorded",
    }
    assert (
        payload["factPrepareCommand"]
        == "ops/scripts/openclaw_cliq_trusted_reply_facts_prepare.sh"
    )
    assert payload["acceptedFactSources"] == ["env", "hashFactsFile", "rawFactsFile"]
    assert str(reports_dir) not in result.stdout
    assert str(config_path) not in result.stdout
    assert payload["acceptedFactStates"] == ["hash", "raw"]
    assert (
        "ZOHO_CLIQ_TRUSTED_REPLY_RAW_FACTS_FILE or ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE or ZOHO_CLIQ_DELIVERY_ID_HASH or ZOHO_CLIQ_DELIVERY_ID"
        in payload["requiredEnv"]
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
    assert payload["reportsReady"] == {
        "routePreflight": True,
        "plan": True,
        "evidence": False,
        "check": False,
    }
    assert payload["redaction"]["rawIdsStored"] is False

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


def test_openclaw_cliq_trusted_reply_bundle_plan_only_redacts_hash_values(
    tmp_path: Path,
) -> None:
    route_path = tmp_path / "route.json"
    reports_dir = tmp_path / "reports"
    sender_hash = _sha256_ref("sender-raw-id")
    message_hash = _sha256_ref("message-raw-id")
    delivery_hash = _sha256_ref("delivery-raw-id")
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
            "ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID": "unit-bundle-plan-hash",
            "ZOHO_CLIQ_TRUSTED_SENDER_ID_HASH": sender_hash,
            "ZOHO_CLIQ_TRUSTED_MESSAGE_ID_HASH": message_hash,
            "ZOHO_CLIQ_DELIVERY_ID_HASH": delivery_hash,
            "ZOHO_CLIQ_EXPECTED_AGENT_ID": "zoho-employee-test",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    assert sender_hash not in output
    assert message_hash not in output
    assert delivery_hash not in output

    payload = json.loads(result.stdout)
    assert payload["status"] == "ready_for_bundle_check"
    assert payload["facts"] == {
        "trustedSenderId": "hash",
        "trustedMessageId": "hash",
        "deliveryId": "hash",
    }
    assert payload["redaction"] == {
        "rawIdsStored": False,
        "hashValuesStored": False,
        "localPathsStored": False,
        "secretsStored": False,
    }

    plan_report = (
        reports_dir / "openclaw_cliq_trusted_reply_plan_unit-bundle-plan-hash.json"
    )
    plan_text = plan_report.read_text()
    assert json.loads(plan_text) == payload
    assert sender_hash not in plan_text
    assert message_hash not in plan_text
    assert delivery_hash not in plan_text


def test_openclaw_cliq_trusted_reply_bundle_plan_only_reads_hash_facts_file(
    tmp_path: Path,
) -> None:
    route_path = tmp_path / "route.json"
    facts_path = tmp_path / "trusted-reply-facts.json"
    reports_dir = tmp_path / "reports"
    sender_hash = _sha256_ref("sender-raw-id")
    message_hash = _sha256_ref("message-raw-id")
    delivery_hash = _sha256_ref("delivery-raw-id")
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
    facts_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "kind": "openclaw_cliq_trusted_reply_facts",
                "trustedMention": {
                    "trustedSenderIdHash": sender_hash,
                    "messageIdHash": message_hash,
                },
                "delivery": {"deliveryIdHash": delivery_hash},
            }
        )
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_BUNDLE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CLIQ_ROUTE_REPORT_FILE": str(route_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE": str(facts_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_PLAN_ONLY": "1",
            "ZOHO_CLIQ_TRUSTED_REPLY_REPORT_DIR": str(reports_dir),
            "ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID": "unit-bundle-plan-facts-file",
            "ZOHO_CLIQ_EXPECTED_AGENT_ID": "zoho-employee-test",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    assert str(facts_path) not in output
    assert sender_hash not in output
    assert message_hash not in output
    assert delivery_hash not in output

    payload = json.loads(result.stdout)
    assert payload["status"] == "ready_for_bundle_check"
    assert payload["facts"] == {
        "trustedSenderId": "hash",
        "trustedMessageId": "hash",
        "deliveryId": "hash",
    }
    assert payload["readyFacts"] == [
        "trustedSenderId",
        "trustedMessageId",
        "deliveryId",
    ]
    assert payload["acceptedFactSources"] == ["env", "hashFactsFile", "rawFactsFile"]
    assert (
        payload["collectionGuide"]["preferredFactSource"]
        == "ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE"
    )


def test_openclaw_cliq_trusted_reply_bundle_rejects_raw_facts_file(
    tmp_path: Path,
) -> None:
    route_path = tmp_path / "route.json"
    facts_path = tmp_path / "trusted-reply-facts.json"
    route_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "kind": "openclaw_cliq_route_preflight",
                "status": "ok",
            }
        )
    )
    facts_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "kind": "openclaw_cliq_trusted_reply_facts",
                "trustedSenderId": "sender-raw-id",
                "trustedMessageIdHash": "sha256:message",
                "deliveryIdHash": "sha256:reply",
            }
        )
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_BUNDLE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CLIQ_ROUTE_REPORT_FILE": str(route_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE": str(facts_path),
            "ZOHO_CLIQ_EXPECTED_AGENT_ID": "zoho-employee-test",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 2, output
    assert "sender-raw-id" not in output
    payload = json.loads(result.stdout)
    assert payload["kind"] == "openclaw_cliq_trusted_reply_evidence_bundle"
    assert payload["error"] == "facts_file_raw_ids_present"


def test_openclaw_cliq_trusted_reply_bundle_rejects_secret_facts_file(
    tmp_path: Path,
) -> None:
    route_path = tmp_path / "route.json"
    facts_path = tmp_path / "trusted-reply-facts.json"
    route_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "kind": "openclaw_cliq_route_preflight",
                "status": "ok",
            }
        )
    )
    facts_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "kind": "openclaw_cliq_trusted_reply_facts",
                "trustedSenderIdHash": "sha256:sender",
                "trustedMessageIdHash": "sha256:message",
                "deliveryIdHash": "sha256:reply",
                "note": "X-Cliq-Webhook-Secret",
            }
        )
    )

    result = subprocess.run(
        ["bash", str(OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_BUNDLE_SCRIPT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "ZOHO_CLIQ_ROUTE_REPORT_FILE": str(route_path),
            "ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE": str(facts_path),
            "ZOHO_CLIQ_EXPECTED_AGENT_ID": "zoho-employee-test",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["kind"] == "openclaw_cliq_trusted_reply_evidence_bundle"
    assert payload["error"] == "facts_file_secret_marker_present"


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
    raw_facts_path = tmp_path / "trusted-reply-raw-facts.json"
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
    raw_facts_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "kind": "openclaw_cliq_trusted_reply_raw_facts",
                "trustedMention": {
                    "trustedSenderId": "sender-raw-id",
                    "messageId": "message-raw-id",
                },
                "delivery": {"messageId": "delivery-raw-id"},
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
            "ZOHO_CLIQ_TRUSTED_REPLY_RAW_FACTS_FILE": str(raw_facts_path),
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
    facts_report = (
        reports_dir
        / "openclaw_cliq_trusted_reply_facts_unit-bundle-route-mismatch.json"
    )
    evidence_report = (
        reports_dir / "openclaw_cliq_trusted_reply_unit-bundle-route-mismatch.json"
    )
    check_report = (
        reports_dir
        / "openclaw_cliq_trusted_reply_check_unit-bundle-route-mismatch.json"
    )
    assert json.loads(route_report.read_text()) == payload
    assert not facts_report.exists()
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
