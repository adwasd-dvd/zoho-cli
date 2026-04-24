#!/usr/bin/env bash
set -euo pipefail

REPO_PATH=""
WORKSPACE_ROOT="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}"
PROJECT_NAME="zoho-cli-project"
COPY_MODE="symlink"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      REPO_PATH="$2"
      shift 2
      ;;
    --workspace-root)
      WORKSPACE_ROOT="$2"
      shift 2
      ;;
    --project-name)
      PROJECT_NAME="$2"
      shift 2
      ;;
    --copy)
      COPY_MODE="copy"
      shift
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "$REPO_PATH" ]]; then
  echo "Usage: $0 --repo /absolute/path/to/repo [--workspace-root PATH] [--project-name NAME] [--copy]" >&2
  exit 1
fi

REPO_PATH="$(cd "$REPO_PATH" && pwd)"
TEMPLATE_DIR="$(cd "$(dirname "$0")/.." && pwd)/workspace-template"
TARGET_DIR="$WORKSPACE_ROOT/$PROJECT_NAME"

mkdir -p "$WORKSPACE_ROOT"
rm -rf "$TARGET_DIR"
mkdir -p "$TARGET_DIR"
cp -R "$TEMPLATE_DIR"/. "$TARGET_DIR"/

if [[ "$COPY_MODE" == "copy" ]]; then
  cp -R "$REPO_PATH" "$TARGET_DIR/repo"
else
  ln -s "$REPO_PATH" "$TARGET_DIR/repo"
fi

cat > "$TARGET_DIR/OPEN_ME_FIRST.md" <<TXT
OpenClaw workspace created.

Workspace: $TARGET_DIR
Repo: $REPO_PATH
Mode: $COPY_MODE

Read order:
1. repo/AGENTS.md
2. repo/integrations/openclaw/START_HERE.md
3. repo/integrations/openclaw/templates/KICKOFF_PROMPT.md
4. repo/ops/state/active_task.yml
TXT

printf '\n✅ OpenClaw workspace ready: %s\n' "$TARGET_DIR"
printf '\nNext commands to copy:\n\n'
printf 'cd %q\n' "$REPO_PATH"
printf 'openclaw gateway restart\n'
printf 'openclaw tui\n\n'
printf 'Then point the agent at this workspace path:\n  %s\n\n' "$TARGET_DIR"
printf 'Kickoff prompt file:\n  %s\n\n' "$REPO_PATH/integrations/openclaw/templates/KICKOFF_PROMPT.md"
