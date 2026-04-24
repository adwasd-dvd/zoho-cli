from __future__ import annotations

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
        SKILL_ROOT / "references" / "maintenance-checklist.md",
        SKILL_ROOT / "references" / "unread-status-workflow.md",
        SKILL_ROOT / "references" / "cli-help-snapshot.md",
        SKILL_ROOT / "scripts" / "refresh_cli_help_snapshot.py",
        REPO_ROOT / "integrations" / "openclaw" / "LANE3_AI_USER_GUIDE.md",
        REPO_ROOT / "integrations" / "openclaw" / "SKILL_INDEX.md",
        REPO_ROOT / "integrations" / "openclaw" / "bin" / "pull_lane3_only.sh",
    ]

    for path in required:
        assert path.exists(), f"missing: {path}"


def test_lane3_docs_use_canonical_repo_url() -> None:
    lane3_files = [
        SKILL_ROOT / "SKILL.md",
        SKILL_ROOT / "references" / "install-and-update.md",
        REPO_ROOT / "integrations" / "openclaw" / "README.md",
        REPO_ROOT / "integrations" / "openclaw" / "LANE3_AI_USER_GUIDE.md",
        REPO_ROOT / "integrations" / "openclaw" / "SKILL_INDEX.md",
    ]

    old_url = "github.com/adwasd-dvd/zoho-cli"
    for path in lane3_files:
        text = path.read_text(encoding="utf-8")
        assert old_url not in text, f"outdated repo url in {path}"


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
