from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / "skill"


def _frontmatter_fields(skill_text: str) -> dict[str, str]:
    lines = skill_text.splitlines()
    assert lines and lines[0].strip() == "---"

    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def test_skill_frontmatter_is_minimal_and_named() -> None:
    text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    fields = _frontmatter_fields(text)

    assert set(fields) == {"name", "description"}
    assert fields["name"] == "zoho-cli-employee"
    assert "OpenClaw" in fields["description"]


def test_skill_references_and_scripts_exist() -> None:
    required_paths = [
        SKILL_ROOT / "references" / "employee-operating-model.md",
        SKILL_ROOT / "references" / "command-playbook.md",
        SKILL_ROOT / "references" / "install-and-update.md",
        SKILL_ROOT / "references" / "maintenance-checklist.md",
        SKILL_ROOT / "references" / "cli-help-snapshot.md",
        SKILL_ROOT / "scripts" / "refresh_cli_help_snapshot.py",
        REPO_ROOT
        / "integrations"
        / "openclaw"
        / "bin"
        / "install_openclaw_skill.sh",
        REPO_ROOT
        / "integrations"
        / "openclaw"
        / "bin"
        / "update_openclaw_zoho_stack.sh",
    ]

    for path in required_paths:
        assert path.exists(), f"missing: {path}"


def test_command_playbook_has_no_truncated_zoho_command_prefix() -> None:
    text = (SKILL_ROOT / "references" / "command-playbook.md").read_text(
        encoding="utf-8"
    )
    assert "\noho " not in text
