from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_make_lint_covers_source_and_tests() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert "$(RUFF) check zoho_cli/ tests/" in makefile
