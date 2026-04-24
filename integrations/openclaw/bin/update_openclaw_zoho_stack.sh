#!/usr/bin/env bash
set -euo pipefail

REPO_DIR=""
PACKAGE_SPEC="git+https://github.com/adwasd-dvd/zoho-cli"
INSTALLER="auto"
SKIP_PULL=0
SKIP_CLI=0
SKIP_SKILL=0
SKILL_NAME="zoho-cli-employee"

usage() {
  cat <<'EOF'
Usage: update_openclaw_zoho_stack.sh [options]

Options:
  --repo <path>            Repository root (default: auto-detect from script path)
  --package-spec <spec>    CLI package spec for uv/pipx (default: git+https://github.com/adwasd-dvd/zoho-cli)
  --installer <mode>       auto|uv|pipx|none (default: auto)
  --skill-name <name>      Installed skill directory name (default: zoho-cli-employee)
  --no-pull                Skip git pull
  --skip-cli               Skip CLI update
  --skip-skill             Skip skill reinstall
  -h, --help               Show help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      REPO_DIR="${2:?missing value for --repo}"
      shift 2
      ;;
    --package-spec)
      PACKAGE_SPEC="${2:?missing value for --package-spec}"
      shift 2
      ;;
    --installer)
      INSTALLER="${2:?missing value for --installer}"
      shift 2
      ;;
    --skill-name)
      SKILL_NAME="${2:?missing value for --skill-name}"
      shift 2
      ;;
    --no-pull)
      SKIP_PULL=1
      shift
      ;;
    --skip-cli)
      SKIP_CLI=1
      shift
      ;;
    --skip-skill)
      SKIP_SKILL=1
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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "${REPO_DIR}" ]]; then
  REPO_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
fi

case "${INSTALLER}" in
  auto|uv|pipx|none) ;;
  *)
    echo "Invalid --installer value: ${INSTALLER}" >&2
    exit 1
    ;;
esac

if [[ ! -d "${REPO_DIR}" ]]; then
  echo "Repo path not found: ${REPO_DIR}" >&2
  exit 1
fi

if [[ "${SKIP_PULL}" -eq 0 ]]; then
  if git -C "${REPO_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git -C "${REPO_DIR}" pull --ff-only
  else
    echo "Warning: ${REPO_DIR} is not a git repo, skipping pull" >&2
  fi
fi

if [[ "${SKIP_CLI}" -eq 0 ]]; then
  selected_installer="${INSTALLER}"
  if [[ "${selected_installer}" == "auto" ]]; then
    if command -v uv >/dev/null 2>&1; then
      selected_installer="uv"
    elif command -v pipx >/dev/null 2>&1; then
      selected_installer="pipx"
    else
      echo "Neither uv nor pipx found, cannot update CLI" >&2
      exit 1
    fi
  fi

  case "${selected_installer}" in
    uv)
      uv tool install --upgrade "${PACKAGE_SPEC}"
      ;;
    pipx)
      pipx install --force "${PACKAGE_SPEC}"
      ;;
    none)
      echo "Skipping CLI update (--installer none)"
      ;;
    *)
      echo "Unhandled installer: ${selected_installer}" >&2
      exit 1
      ;;
  esac
fi

if [[ "${SKIP_SKILL}" -eq 0 ]]; then
  "${SCRIPT_DIR}/install_openclaw_skill.sh" \
    --repo "${REPO_DIR}" \
    --skill-name "${SKILL_NAME}"
fi

echo "Update complete"
