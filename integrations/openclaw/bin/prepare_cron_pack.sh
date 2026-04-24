#!/usr/bin/env bash
set -euo pipefail
REPO_PATH="$(cd "$(dirname "$0")/../../.." && pwd)"
cat <<TXT
Use these prompt files for recurring agents:

planner         $REPO_PATH/ops/prompts/planner.md
builder         $REPO_PATH/ops/prompts/builder.md
verifier        $REPO_PATH/ops/prompts/verifier.md
fixer           $REPO_PATH/ops/prompts/fixer.md
release-manager $REPO_PATH/ops/prompts/release-manager.md
nightly-smoke   $REPO_PATH/ops/prompts/nightly-smoke.md

Suggested schedule reference:
$REPO_PATH/ops/cron/README.md
TXT
