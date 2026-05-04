from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / "skill"


def _frontmatter_fields(text: str) -> dict[str, str]:
    lines = text.splitlines()
    assert lines and lines[0].strip() == "---"

    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def test_lane3_skill_frontmatter_is_minimal() -> None:
    text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    fields = _frontmatter_fields(text)

    assert set(fields) == {"name", "description"}
    assert fields["name"] == "zoho-cli-employee"


def test_lane3_required_paths_exist() -> None:
    required = [
        SKILL_ROOT / "references" / "employee-operating-model.md",
        SKILL_ROOT / "references" / "command-playbook.md",
        SKILL_ROOT / "references" / "install-and-update.md",
        SKILL_ROOT / "references" / "github-intake-workflow.md",
        SKILL_ROOT / "references" / "maintenance-checklist.md",
        SKILL_ROOT / "references" / "unread-status-workflow.md",
        SKILL_ROOT / "references" / "cli-help-snapshot.md",
        SKILL_ROOT / "scripts" / "refresh_cli_help_snapshot.py",
        REPO_ROOT / "integrations" / "openclaw" / "LANE3_AI_USER_GUIDE.md",
        REPO_ROOT / "integrations" / "openclaw" / "SKILL_INDEX.md",
        REPO_ROOT / "integrations" / "openclaw" / "bin" / "pull_lane3_only.sh",
        REPO_ROOT / "integrations" / "openclaw-channel-cliq" / "package.json",
        REPO_ROOT / "integrations" / "openclaw-channel-cliq" / "openclaw.plugin.json",
        REPO_ROOT / "integrations" / "openclaw-channel-cliq" / "skill" / "SKILL.md",
    ]

    for path in required:
        assert path.exists(), f"missing: {path}"


def test_lane3_docs_use_canonical_repo_url() -> None:
    lane3_files = [
        SKILL_ROOT / "SKILL.md",
        SKILL_ROOT / "references" / "install-and-update.md",
        SKILL_ROOT / "references" / "github-intake-workflow.md",
        REPO_ROOT / "integrations" / "openclaw" / "README.md",
        REPO_ROOT / "integrations" / "openclaw" / "LANE3_AI_USER_GUIDE.md",
        REPO_ROOT / "integrations" / "openclaw" / "SKILL_INDEX.md",
    ]

    canonical_refs = ("github.com/adwasd-dvd/zoho-cli", "adwasd-dvd/zoho-cli")
    outdated_refs = (
        "github.com/adwasd-dvd/zoho-mail-cli-zomacli",
        "adwasd-dvd/zoho-mail-cli-zomacli",
    )
    for path in lane3_files:
        text = path.read_text(encoding="utf-8")
        for old_ref in outdated_refs:
            assert old_ref not in text, f"outdated repo url in {path}"
        if path.name != "SKILL.md":
            assert any(ref in text for ref in canonical_refs), (
                f"missing canonical repo url in {path}"
            )


def test_lane3_reaction_status_protocol_and_unread_filter_present() -> None:
    workflow = (SKILL_ROOT / "references" / "unread-status-workflow.md").read_text(
        encoding="utf-8"
    )

    for token in [
        "received",
        "thinking",
        "writing",
        "testing",
        "blocked",
        "done",
        "failed",
        "--exclude-reacted-by-self",
        "status-react",
        "--clear-known",
    ]:
        assert token in workflow


def test_lane3_github_intake_targets_canonical_repo_and_redacts() -> None:
    workflow = (SKILL_ROOT / "references" / "github-intake-workflow.md").read_text(
        encoding="utf-8"
    )

    for token in [
        "adwasd-dvd/zoho-cli",
        "gh issue list",
        "gh issue create",
        "--repo adwasd-dvd/zoho-cli",
        "--label bug",
        "--label needs-triage",
        "agent-feedback",
        "openclaw",
        "duplicate",
        "tokens",
        "secrets",
        "customer data",
        "private message bodies",
    ]:
        assert token in workflow


def test_github_issue_templates_exist_for_employee_intake() -> None:
    template_root = REPO_ROOT / ".github" / "ISSUE_TEMPLATE"
    required = [
        template_root / "bug_report.yml",
        template_root / "suggestion.yml",
        template_root / "ai_employee_feedback.yml",
        template_root / "config.yml",
    ]

    for path in required:
        text = path.read_text(encoding="utf-8")
        assert "adwasd-dvd/zoho-mail-cli-zomacli" not in text
        assert "Privacy check" in text or path.name == "config.yml"


def test_lane3_examples_use_zoho_binary_not_legacy_command_forms() -> None:
    command_doc_files = [
        SKILL_ROOT / "SKILL.md",
        SKILL_ROOT / "references" / "employee-operating-model.md",
        SKILL_ROOT / "references" / "command-playbook.md",
        SKILL_ROOT / "references" / "install-and-update.md",
        SKILL_ROOT / "references" / "maintenance-checklist.md",
        SKILL_ROOT / "references" / "unread-status-workflow.md",
        SKILL_ROOT / "references" / "cli-help-snapshot.md",
        REPO_ROOT / "integrations" / "openclaw" / "README.md",
        REPO_ROOT / "integrations" / "openclaw" / "LANE3_AI_USER_GUIDE.md",
        REPO_ROOT / "integrations" / "openclaw" / "quick_test.sh",
    ]

    legacy_command_patterns = [
        re.compile(r"python\s+-m\s+zoho_cli"),
        re.compile(r"(?m)(?:^|[|;&`]\s*|\$\s*)zoho-cli(?:\s|$)"),
    ]

    for path in command_doc_files:
        text = path.read_text(encoding="utf-8")
        for pattern in legacy_command_patterns:
            assert not pattern.search(text), (
                f"legacy command pattern {pattern.pattern!r} found in {path}"
            )
