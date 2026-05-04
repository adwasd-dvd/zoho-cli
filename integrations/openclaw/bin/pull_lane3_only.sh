#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/adwasd-dvd/zoho-cli.git"
BRANCH="autobot/zoho-platform"
WORKSPACE="$HOME/.openclaw/workspace-zoho-employee-test"
SKILL_NAME="zoho-cli-employee"
SOURCE_DIR_NAME="lane3-source"

usage() {
  cat <<'EOF'
Usage: pull_lane3_only.sh [options]

Options:
  --workspace <path>    Agent workspace (default: ~/.openclaw/workspace-zoho-employee-test)
  --branch <name>       Git branch to sync (default: autobot/zoho-platform)
  --repo-url <url>      Git repo url (default: adwasd-dvd/zoho-cli)
  --skill-name <name>   Local skill directory name (default: zoho-cli-employee)
  -h, --help            Show help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --workspace)
      WORKSPACE="${2:?missing value for --workspace}"
      shift 2
      ;;
    --branch)
      BRANCH="${2:?missing value for --branch}"
      shift 2
      ;;
    --repo-url)
      REPO_URL="${2:?missing value for --repo-url}"
      shift 2
      ;;
    --skill-name)
      SKILL_NAME="${2:?missing value for --skill-name}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

mkdir -p "$WORKSPACE"
SOURCE_DIR="$WORKSPACE/$SOURCE_DIR_NAME"

if [[ ! -d "$SOURCE_DIR/.git" ]]; then
  git clone --filter=blob:none --no-checkout "$REPO_URL" "$SOURCE_DIR"
fi

git -C "$SOURCE_DIR" fetch --prune origin

# Use non-cone mode so we can include one specific docs file path.
git -C "$SOURCE_DIR" sparse-checkout init --no-cone

git -C "$SOURCE_DIR" sparse-checkout set \
  /skill/ \
  /integrations/openclaw/ \
  /docs/DOCUMENTATION_LANES.md

git -C "$SOURCE_DIR" checkout -B "$BRANCH" "origin/$BRANCH"

TARGET_SKILL_DIR="$WORKSPACE/skills/$SKILL_NAME"
mkdir -p "$TARGET_SKILL_DIR"
rsync -a --delete --exclude '.git' "$SOURCE_DIR/skill/" "$TARGET_SKILL_DIR/"

DOCS_DIR="$WORKSPACE/lane3-docs"
mkdir -p "$DOCS_DIR"
rsync -a --delete --exclude '.git' "$SOURCE_DIR/integrations/openclaw/" "$DOCS_DIR/openclaw/"
cp "$SOURCE_DIR/docs/DOCUMENTATION_LANES.md" "$DOCS_DIR/DOCUMENTATION_LANES.md"

echo "Lane3 sync complete"
echo "workspace: $WORKSPACE"
echo "branch:    $BRANCH"
echo "skill:     $TARGET_SKILL_DIR"
echo "docs:      $DOCS_DIR"
