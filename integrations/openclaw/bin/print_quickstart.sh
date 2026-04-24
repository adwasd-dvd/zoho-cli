#!/usr/bin/env bash
set -euo pipefail
REPO_PATH="$(cd "$(dirname "$0")/../../.." && pwd)"
cat <<TXT
Copy these commands:

cd "$REPO_PATH"
bash integrations/openclaw/bin/bootstrap_openclaw_workspace.sh --repo "$(pwd)"
openclaw gateway restart
openclaw tui

Then paste the kickoff prompt from:
$REPO_PATH/integrations/openclaw/templates/KICKOFF_PROMPT.md
TXT
