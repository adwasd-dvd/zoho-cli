#!/usr/bin/env bash
# Patch an installed pipx copy with the current repository files.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PY_SITE=$(python3 - <<'PY'
import sysconfig
print(sysconfig.get_paths().get("purelib",""))
PY
)

if [[ -z "$PY_SITE" || ! -d "$PY_SITE/zoho_cli" ]]; then
  echo "Could not find an installed zoho_cli package in the current Python environment."
  echo "Activate the target pipx/venv Python first, then rerun this script."
  exit 1
fi

cp "$REPO_ROOT/zoho_cli/cli.py" "$PY_SITE/zoho_cli/cli.py"
cp "$REPO_ROOT/zoho_cli/mail.py" "$PY_SITE/zoho_cli/mail.py"
if [[ -f "$REPO_ROOT/zoho_cli/parse.py" ]]; then
  cp "$REPO_ROOT/zoho_cli/parse.py" "$PY_SITE/zoho_cli/parse.py"
fi

echo "Patched installed zoho_cli package at: $PY_SITE/zoho_cli"
