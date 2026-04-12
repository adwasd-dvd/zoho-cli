from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

# Configuration
REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = REPO_ROOT / "ops" / "state"
REPORT_DIR = REPO_ROOT / "tests" / "auto_pilot" / "reports"
VALIDATOR_PATH = Path(__file__).resolve().with_name("state_validator.py")


def _escape_markdown_cell(raw: str) -> str:
    """Escape markdown table-breaking characters for report rows."""
    return (
        raw.replace("|", "\\|")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "<br>")
    )


class SCAPRunner:
    def __init__(self) -> None:
        self.results: list[dict[str, str]] = []
        self.start_time = datetime.now()

    def log_result(self, scenario_name: str, status: str, message: str = "") -> None:
        res = {
            "timestamp": datetime.now().isoformat(),
            "scenario": scenario_name,
            "status": status,  # PASS, FAIL, ERROR
            "message": message,
        }
        self.results.append(res)
        print(f"[{status}] {scenario_name}: {message}")

    def run_command(self, cmd: list[str]) -> tuple[int, str, str]:
        """Run a command in repo root and return (code, stdout, stderr)."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
                check=False,
            )
            return result.returncode, result.stdout, result.stderr
        except Exception as e:
            return 1, "", str(e)

    def validate_state(
        self, state_file: str | Path, expected_dict: dict
    ) -> tuple[bool, str]:
        """Use the validator script to check a state file."""
        path = Path(state_file)
        abs_path = path if path.is_absolute() else (REPO_ROOT / path)
        expected_json = json.dumps(expected_dict)

        cmd = [sys.executable, str(VALIDATOR_PATH), str(abs_path), expected_json]
        code, stdout, stderr = self.run_command(cmd)

        if code == 0 and "VALIDATION_SUCCESS" in stdout:
            return True, "State matches expected schema."
        return False, (stderr if stderr else stdout).strip()

    def run_scenario(self, name: str, func: Callable[[], tuple[bool, str]]) -> bool:
        print(f"\n>>> Running Scenario: {name}")
        try:
            success, msg = func()
            status = "PASS" if success else "FAIL"
            self.log_result(name, status, msg)
            return success
        except Exception as e:
            self.log_result(name, "ERROR", str(e))
            return False

    def generate_report(self) -> Path:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        report_path = (
            REPORT_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        )

        total = len(self.results)
        passed = len([r for r in self.results if r["status"] == "PASS"])
        failed = len([r for r in self.results if r["status"] == "FAIL"])
        errors = len([r for r in self.results if r["status"] == "ERROR"])

        with report_path.open("w", encoding="utf-8") as f:
            f.write("# SCAP Test Report\n")
            f.write(f"**Run at**: {self.start_time.isoformat()}\n\n")
            f.write("## Summary\n")
            f.write(f"- Total Scenarios: {total}\n")
            f.write(f"- ✅ Passed: {passed}\n")
            f.write(f"- ❌ Failed: {failed}\n")
            f.write(f"- ⚠️ Errors: {errors}\n\n")

            f.write("## Detailed Results\n")
            f.write("| Scenario | Status | Message |\n")
            f.write("| :--- | :--- | :--- |\n")
            for r in self.results:
                status_emoji = {"PASS": "✅", "FAIL": "❌", "ERROR": "⚠️"}.get(
                    r["status"], "❓"
                )
                scenario = _escape_markdown_cell(r["scenario"])
                message = _escape_markdown_cell(r["message"])
                f.write(f"| {scenario} | {status_emoji} {r['status']} | {message} |\n")

        print(f"\n[DONE] Report generated: {report_path}")
        return report_path


def main() -> None:
    runner = SCAPRunner()

    # --- Scenario 1: Baseline Check ---
    def test_baseline() -> tuple[bool, str]:
        return runner.validate_state(
            STATE_DIR / "module_status.yml",
            {"mail": {"priority": 1, "status": "completed"}},
        )

    runner.run_scenario("Baseline Module Status Check", test_baseline)

    # --- Scenario 2: Chaos - Corrupt State File ---
    def test_chaos_corruption() -> tuple[bool, str]:
        target = STATE_DIR / "project.yml"
        backup = target.read_text(encoding="utf-8") if target.exists() else ""
        existed = target.exists()

        try:
            target.write_text("!!! INVALID YAML !!! { [ ]\n", encoding="utf-8")
            success, msg = runner.validate_state(target, {"some": "key"})
        finally:
            if existed:
                target.write_text(backup, encoding="utf-8")
            elif target.exists():
                target.unlink()

        return not success, f"System correctly identified corrupted YAML (msg: {msg})"

    runner.run_scenario(
        "Resilience: Corrupted State File Detection", test_chaos_corruption
    )

    # --- Scenario 3: Command Execution Check ---
    def test_cli_version() -> tuple[bool, str]:
        code, stdout, stderr = runner.run_command(
            [sys.executable, "-m", "zoho_cli", "--version"]
        )
        if code == 0:
            return True, f"Version detected: {stdout.strip()}"
        return False, f"CLI failed to run version check: {stderr.strip()}"

    runner.run_scenario("Functional: CLI Version Check", test_cli_version)

    # Finalize
    report = runner.generate_report()
    print(f"\n[FINAL] Test suite completed. Report at {report}")


if __name__ == "__main__":
    main()
