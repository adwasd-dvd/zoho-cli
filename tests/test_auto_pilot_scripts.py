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
    assert summary["summaryVersion"] == 2
    assert summary["config"].endswith("config.json")
    assert summary["account"] == "test@example.com"
    assert summary["network"] == "example-network"
    assert summary["chatId"] == "CHAT-123"
    assert summary["scopeBlocked"] is False
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
    assert summary["recommendedNext"] == "interactive_reauth_then_rerun"
