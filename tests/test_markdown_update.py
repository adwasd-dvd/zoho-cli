from __future__ import annotations

from pathlib import Path


def test_markdown_status_updates_can_replace_sections(tmp_path: Path) -> None:
    path = tmp_path / "status.md"
    path.write_text("# Test\n\n## Status\nold\n", encoding="utf-8")

    content = path.read_text(encoding="utf-8")
    assert "## Status\nold" in content

    updated = content.replace("## Status\nold", "## Status\nnew")
    path.write_text(updated, encoding="utf-8")

    assert path.read_text(encoding="utf-8") == "# Test\n\n## Status\nnew\n"
