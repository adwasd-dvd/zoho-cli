.DEFAULT_GOAL := help
PYTHON := .venv/bin/python
PYTEST := .venv/bin/pytest
RUFF   := .venv/bin/ruff

.PHONY: help install test lint fmt fmt-check package-smoke release-gate ci

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "  install     Install package + dev deps in .venv"
	@echo "  test        Run tests"
	@echo "  lint        Run ruff linter on source and tests"
	@echo "  fmt         Auto-format code with ruff"
	@echo "  fmt-check   Check formatting (no changes)"
	@echo "  package-smoke Build wheel and smoke-install in isolated venv"
	@echo "  release-gate Full release gate: tests + package smoke"
	@echo "  ci          fmt-check + lint + test"

install:
	uv venv --python 3.11
	uv pip install -e ".[dev]"

test:
	$(PYTEST) tests/ -v

lint:
	$(RUFF) check zoho_cli/ tests/

fmt:
	$(RUFF) format zoho_cli/ tests/

fmt-check:
	$(RUFF) format --check zoho_cli/ tests/

package-smoke:
	./ops/scripts/release_gate.sh package-only

release-gate:
	./ops/scripts/release_gate.sh full

ci: fmt-check lint test
