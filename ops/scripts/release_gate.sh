#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"
PYTEST="$VENV_DIR/bin/pytest"

if [[ ! -x "$PYTHON" ]]; then
  echo "error: missing virtualenv python at $PYTHON" >&2
  exit 1
fi

ensure_tool() {
  local tool_path="$1"
  local package_name="$2"
  if [[ ! -x "$tool_path" ]]; then
    echo "[release-gate] installing missing tool: $package_name"
    "$PIP" install --quiet "$package_name"
  fi
}

TMP_DIR="$(mktemp -d /tmp/zoho-release-gate.XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

MODE="${1:-full}"
if [[ "$MODE" != "full" && "$MODE" != "package-only" ]]; then
  echo "usage: $0 [full|package-only]" >&2
  exit 2
fi

DIST_DIR="$TMP_DIR/dist"
SMOKE_VENV="$TMP_DIR/smoke-venv"

cd "$ROOT_DIR"

if [[ "$MODE" == "full" ]]; then
  ensure_tool "$PYTEST" pytest

  echo "[release-gate] unit test suite"
  "$PYTEST" -q tests
fi

echo "[release-gate] build wheel"
mkdir -p "$DIST_DIR"
"$PIP" wheel "$ROOT_DIR" --no-deps -w "$DIST_DIR" >/dev/null
WHEEL_PATH="$(ls "$DIST_DIR"/zoho_cli-*.whl | head -n 1)"

if [[ -z "$WHEEL_PATH" ]]; then
  echo "error: wheel build did not produce a zoho_cli wheel" >&2
  exit 1
fi

echo "[release-gate] install wheel in isolated venv"
"$PYTHON" -m venv "$SMOKE_VENV"
"$SMOKE_VENV/bin/pip" install --quiet "$WHEEL_PATH"

VERSION_OUT="$($SMOKE_VENV/bin/zoho --version)"
"$SMOKE_VENV/bin/zoho" mail --help >/dev/null

echo "[release-gate] ok: wheel smoke passed ($VERSION_OUT)"
