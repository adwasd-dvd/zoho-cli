#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
JQ_BIN="${JQ_BIN:-jq}"
GIT_BIN="${GIT_BIN:-git}"
RUN_ID="${OPENCLAW_CLIQ_SOURCE_DRIFT_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT_DIR="${OPENCLAW_CLIQ_SOURCE_DRIFT_REPORT_DIR:-"$ROOT/tests/auto_pilot/reports"}"
MANIFEST_FILE="${OPENCLAW_CLIQ_HANDOFF_MANIFEST_FILE:-}"
PACKAGE_PATH_FILTER="${OPENCLAW_CLIQ_PACKAGE_PATH_FILTER:-integrations/openclaw-channel-cliq}"
DRIFT_REPORT_FILE="${OPENCLAW_CLIQ_SOURCE_DRIFT_REPORT_FILE:-"$REPORT_DIR/openclaw_cliq_rc_source_drift_check_$RUN_ID.json"}"

emit_error() {
  local error="$1"
  printf '{"schemaVersion":1,"kind":"openclaw_cliq_rc_source_drift_check","runId":"%s","checkedAt":"%s","status":"error","error":"%s"}\n' "$RUN_ID" "$CHECKED_AT" "$error"
}

latest_report() {
  local pattern="$1"
  find "$REPORT_DIR" -maxdepth 1 -type f -name "$pattern" -print 2>/dev/null | sort | tail -n 1
}

latest_ready_json_report() {
  local pattern="$1"
  local expected_status="$2"
  local candidate
  while IFS= read -r candidate; do
    if [[ "$("$JQ_BIN" -r '.status // ""' "$candidate" 2>/dev/null || true)" == "$expected_status" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done < <(find "$REPORT_DIR" -maxdepth 1 -type f -name "$pattern" -print 2>/dev/null | sort -r)
  return 1
}

basename_or_null() {
  local path="${1:-}"
  if [[ -z "$path" ]]; then
    printf 'null'
  else
    "$JQ_BIN" -n --arg value "$(basename "$path")" '$value'
  fi
}

git_text() {
  local args=("$@")
  if command -v "$GIT_BIN" >/dev/null 2>&1; then
    "$GIT_BIN" -C "$ROOT" "${args[@]}" 2>/dev/null || true
  fi
}

json_lines() {
  "$JQ_BIN" -R -s 'split("\n") | map(select(length > 0))'
}

command -v "$JQ_BIN" >/dev/null 2>&1 || {
  emit_error "jq_required"
  exit 2
}
command -v "$GIT_BIN" >/dev/null 2>&1 || {
  emit_error "git_required"
  exit 2
}

mkdir -p "$REPORT_DIR"

if [[ -z "$MANIFEST_FILE" ]]; then
  MANIFEST_FILE="$(
    latest_ready_json_report \
      "openclaw_cliq_rc_operator_handoff_manifest_*.json" \
      "operator_handoff_manifest_ready" \
      || true
  )"
fi
if [[ -z "$MANIFEST_FILE" ]]; then
  MANIFEST_FILE="$(latest_report "openclaw_cliq_rc_operator_handoff_manifest_*.json")"
fi
if [[ -z "$MANIFEST_FILE" || ! -f "$MANIFEST_FILE" ]]; then
  emit_error "handoff_manifest_missing"
  exit 2
fi
if [[ "$("$JQ_BIN" -r '.status // ""' "$MANIFEST_FILE")" != "operator_handoff_manifest_ready" ]]; then
  emit_error "handoff_manifest_not_ready"
  exit 1
fi

SOURCE_COMMIT="$("$JQ_BIN" -r '.source.gitCommit // ""' "$MANIFEST_FILE")"
if [[ -z "$SOURCE_COMMIT" || "$SOURCE_COMMIT" == "null" ]]; then
  emit_error "source_commit_missing"
  exit 2
fi

HEAD_COMMIT="$(git_text rev-parse HEAD | tr -d '\n')"
GIT_BRANCH="$(git_text branch --show-current | tr -d '\n')"
PACKAGE_CHANGED_FILES="$(git_text diff --name-only "$SOURCE_COMMIT..HEAD" -- "$PACKAGE_PATH_FILTER")"
PACKAGE_WORKTREE_FILES="$(git_text diff --name-only -- "$PACKAGE_PATH_FILTER")"
PACKAGE_INDEX_FILES="$(git_text diff --cached --name-only -- "$PACKAGE_PATH_FILTER")"
PACKAGE_UNTRACKED_FILES="$(git_text ls-files --others --exclude-standard -- "$PACKAGE_PATH_FILTER")"
REPO_CHANGED_FILES="$(git_text diff --name-only "$SOURCE_COMMIT..HEAD")"

PACKAGE_CHANGED_JSON="$(printf '%s\n' "$PACKAGE_CHANGED_FILES" | json_lines)"
PACKAGE_WORKTREE_JSON="$(printf '%s\n' "$PACKAGE_WORKTREE_FILES" | json_lines)"
PACKAGE_INDEX_JSON="$(printf '%s\n' "$PACKAGE_INDEX_FILES" | json_lines)"
PACKAGE_UNTRACKED_JSON="$(printf '%s\n' "$PACKAGE_UNTRACKED_FILES" | json_lines)"
REPO_CHANGED_JSON="$(printf '%s\n' "$REPO_CHANGED_FILES" | json_lines)"
MANIFEST_BASENAME="$(basename_or_null "$MANIFEST_FILE")"

PAYLOAD="$("$JQ_BIN" -n \
  --arg runId "$RUN_ID" \
  --arg checkedAt "$CHECKED_AT" \
  --arg sourceCommit "$SOURCE_COMMIT" \
  --arg headCommit "$HEAD_COMMIT" \
  --arg gitBranch "$GIT_BRANCH" \
  --arg packagePathFilter "$PACKAGE_PATH_FILTER" \
  --argjson manifestFile "$MANIFEST_BASENAME" \
  --argjson packageChangedFiles "$PACKAGE_CHANGED_JSON" \
  --argjson packageWorktreeFiles "$PACKAGE_WORKTREE_JSON" \
  --argjson packageIndexFiles "$PACKAGE_INDEX_JSON" \
  --argjson packageUntrackedFiles "$PACKAGE_UNTRACKED_JSON" \
  --argjson repoChangedFiles "$REPO_CHANGED_JSON" \
  --slurpfile manifest "$MANIFEST_FILE" \
  '
  $manifest[0] as $manifest
  | [
      (if ($packageChangedFiles | length) == 0 then empty else "package_source_drift_detected" end),
      (if ($packageWorktreeFiles | length) == 0 then empty else "package_worktree_dirty" end),
      (if ($packageIndexFiles | length) == 0 then empty else "package_index_dirty" end),
      (if ($packageUntrackedFiles | length) == 0 then empty else "package_untracked_files" end)
    ] as $blockers
  | {
      schemaVersion: 1,
      kind: "openclaw_cliq_rc_source_drift_check",
      runId: $runId,
      checkedAt: $checkedAt,
      status: (if ($blockers | length) == 0 then "package_source_unchanged" else "blocked" end),
      blockers: $blockers,
      source: {
        manifestFile: $manifestFile,
        manifestStatus: ($manifest.status // null),
        sourceCommit: $sourceCommit,
        headCommit: (if $headCommit == "" then null else $headCommit end),
        gitBranch: (if $gitBranch == "" then null else $gitBranch end),
        packagePathFilter: $packagePathFilter,
        headMatchesManifestSource: ($headCommit == $sourceCommit),
        repoChangedSinceManifest: (($repoChangedFiles | length) > 0),
        repoChangedFileCount: ($repoChangedFiles | length)
      },
      packageDrift: {
        packageChangedSinceManifest: (($packageChangedFiles | length) > 0),
        changedFileCount: ($packageChangedFiles | length),
        changedFiles: $packageChangedFiles,
        dirtyFileCount: (($packageWorktreeFiles | length) + ($packageIndexFiles | length) + ($packageUntrackedFiles | length)),
        worktreeFiles: $packageWorktreeFiles,
        indexFiles: $packageIndexFiles,
        untrackedFiles: $packageUntrackedFiles
      },
      artifact: {
        filename: ($manifest.artifact.filename // null),
        shasum: ($manifest.artifact.shasum // null),
        integrity: ($manifest.artifact.integrity // null)
      },
      package: {
        name: ($manifest.package.name // null),
        version: ($manifest.package.version // null),
        expectedIntegrityState: ($manifest.package.expectedIntegrityState // null)
      },
      releasePosture: {
        publishPerformed: false,
        tagCreated: false,
        githubReleaseCreated: false,
        versionBumped: false,
        expectedIntegrityFilled: false,
        agentMayPublish: false,
        agentMayTag: false,
        agentMayCreateGithubRelease: false,
        agentMayFillExpectedIntegrity: false
      },
      nextAction: (
        if ($blockers | length) == 0 then "operator_handoff_still_current_for_package"
        else "repack_current_head_before_operator_publish"
        end
      )
    }
  ')"

printf '%s\n' "$PAYLOAD" >"$DRIFT_REPORT_FILE"
printf '%s\n' "$PAYLOAD"

if [[ "$("$JQ_BIN" -r '.status' "$DRIFT_REPORT_FILE")" != "package_source_unchanged" ]]; then
  exit 1
fi
