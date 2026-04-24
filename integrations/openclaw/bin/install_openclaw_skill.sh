#!/usr/bin/env bash
set -euo pipefail

REPO_DIR=""
TARGET_ROOT="${HOME}/.openclaw/skills"
SKILL_NAME="zoho-cli-employee"
SKILL_SOURCE_REL="skill"
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage: install_openclaw_skill.sh [options]

Options:
  --repo <path>          Repository root (default: auto-detect from script path)
  --target-root <path>   OpenClaw skills root (default: ~/.openclaw/skills)
  --skill-name <name>    Installed skill directory name (default: zoho-cli-employee)
  --skill-source <rel>   Skill source path relative to repo root (default: skill)
  --dry-run              Print planned actions only
  -h, --help             Show help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      REPO_DIR="${2:?missing value for --repo}"
      shift 2
      ;;
    --target-root)
      TARGET_ROOT="${2:?missing value for --target-root}"
      shift 2
      ;;
    --skill-name)
      SKILL_NAME="${2:?missing value for --skill-name}"
      shift 2
      ;;
    --skill-source)
      SKILL_SOURCE_REL="${2:?missing value for --skill-source}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
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

if [[ -z "${REPO_DIR}" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  REPO_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
fi

SOURCE_DIR="${REPO_DIR}/${SKILL_SOURCE_REL}"
DEST_DIR="${TARGET_ROOT%/}/${SKILL_NAME}"

if [[ ! -f "${SOURCE_DIR}/SKILL.md" ]]; then
  echo "Skill source missing SKILL.md: ${SOURCE_DIR}" >&2
  exit 1
fi

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "[dry-run] source: ${SOURCE_DIR}"
  echo "[dry-run] dest:   ${DEST_DIR}"
  exit 0
fi

mkdir -p "${TARGET_ROOT}"

if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete --exclude '.DS_Store' "${SOURCE_DIR}/" "${DEST_DIR}/"
else
  rm -rf "${DEST_DIR}"
  mkdir -p "${DEST_DIR}"
  (
    cd "${SOURCE_DIR}"
    tar cf - . --exclude .DS_Store
  ) | (
    cd "${DEST_DIR}"
    tar xf -
  )
fi

if git -C "${REPO_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  {
    echo "repo=$(git -C "${REPO_DIR}" remote get-url origin 2>/dev/null || echo unknown)"
    echo "revision=$(git -C "${REPO_DIR}" rev-parse HEAD)"
    echo "installed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } > "${DEST_DIR}/.source-revision"
fi

echo "Installed skill to ${DEST_DIR}"
