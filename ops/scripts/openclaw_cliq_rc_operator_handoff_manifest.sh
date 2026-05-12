#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
JQ_BIN="${JQ_BIN:-jq}"
GIT_BIN="${GIT_BIN:-git}"
RUN_ID="${OPENCLAW_CLIQ_HANDOFF_MANIFEST_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT_DIR="${OPENCLAW_CLIQ_HANDOFF_MANIFEST_REPORT_DIR:-"$ROOT/tests/auto_pilot/reports"}"
OPERATOR_BUNDLE_FILE="${OPENCLAW_CLIQ_OPERATOR_BUNDLE_REPORT_FILE:-}"
RELEASE_NOTES_DRAFT_FILE="${OPENCLAW_CLIQ_RELEASE_NOTES_DRAFT_FILE:-}"
PUBLISH_PLAN_FILE="${OPENCLAW_CLIQ_PUBLISH_PLAN_FILE:-}"
MANIFEST_FILE="${OPENCLAW_CLIQ_HANDOFF_MANIFEST_FILE:-"$REPORT_DIR/openclaw_cliq_rc_operator_handoff_manifest_$RUN_ID.json"}"

emit_error() {
  local error="$1"
  printf '{"schemaVersion":1,"kind":"openclaw_cliq_rc_operator_handoff_manifest","runId":"%s","checkedAt":"%s","status":"error","error":"%s"}\n' "$RUN_ID" "$CHECKED_AT" "$error"
}

latest_report() {
  local pattern="$1"
  find "$REPORT_DIR" -maxdepth 1 -type f -name "$pattern" -print 2>/dev/null | sort | tail -n 1
}

basename_or_null() {
  local path="${1:-}"
  if [[ -z "$path" ]]; then
    printf 'null'
  else
    "$JQ_BIN" -n --arg value "$(basename "$path")" '$value'
  fi
}

git_value_or_null() {
  local args=("$@")
  if command -v "$GIT_BIN" >/dev/null 2>&1; then
    "$GIT_BIN" -C "$ROOT" "${args[@]}" 2>/dev/null || true
  fi
}

command -v "$JQ_BIN" >/dev/null 2>&1 || {
  emit_error "jq_required"
  exit 2
}

mkdir -p "$REPORT_DIR"

if [[ -z "$OPERATOR_BUNDLE_FILE" ]]; then
  OPERATOR_BUNDLE_FILE="$(latest_report "openclaw_cliq_rc_operator_publish_bundle_*.json")"
fi
if [[ -z "$RELEASE_NOTES_DRAFT_FILE" ]]; then
  RELEASE_NOTES_DRAFT_FILE="$(latest_report "openclaw_cliq_rc_release_notes_draft_*.md")"
fi
if [[ -z "$PUBLISH_PLAN_FILE" ]]; then
  PUBLISH_PLAN_FILE="$(latest_report "openclaw_cliq_rc_publish_plan_*.json")"
fi

if [[ -z "$OPERATOR_BUNDLE_FILE" || ! -f "$OPERATOR_BUNDLE_FILE" ]]; then
  emit_error "operator_bundle_missing"
  exit 2
fi
if [[ -z "$RELEASE_NOTES_DRAFT_FILE" || ! -f "$RELEASE_NOTES_DRAFT_FILE" ]]; then
  emit_error "release_notes_draft_missing"
  exit 2
fi
if [[ -z "$PUBLISH_PLAN_FILE" || ! -f "$PUBLISH_PLAN_FILE" ]]; then
  emit_error "publish_plan_missing"
  exit 2
fi

if [[ "$("$JQ_BIN" -r '.status // ""' "$OPERATOR_BUNDLE_FILE")" != "operator_publish_bundle_ready" ]]; then
  emit_error "operator_bundle_not_ready"
  exit 1
fi
if [[ "$("$JQ_BIN" -r '.status // ""' "$PUBLISH_PLAN_FILE")" != "operator_publish_plan_ready" ]]; then
  emit_error "publish_plan_not_ready"
  exit 1
fi

for marker in \
  'No npm publish, git tag, GitHub release' \
  'agentMayPublish=false' \
  'agentMayTag=false' \
  'agentMayFillExpectedIntegrity=false'
do
  if ! grep -Fq "$marker" "$RELEASE_NOTES_DRAFT_FILE"; then
    emit_error "release_notes_draft_unsafe"
    exit 1
  fi
done

for field in \
  '.releasePosture.agentMayPublish' \
  '.releasePosture.agentMayTag' \
  '.releasePosture.agentMayCreateGithubRelease' \
  '.releasePosture.agentMayFillExpectedIntegrity' \
  '.releasePosture.agentMayExecutePlan'
do
  if [[ "$("$JQ_BIN" -r "if (${field%.*} | has(\"${field##*.}\")) then $field else true end" "$PUBLISH_PLAN_FILE")" != "false" ]]; then
    emit_error "publish_plan_permission_unexpected"
    exit 1
  fi
done

OPERATOR_BUNDLE_BASENAME="$(basename_or_null "$OPERATOR_BUNDLE_FILE")"
RELEASE_NOTES_BASENAME="$(basename_or_null "$RELEASE_NOTES_DRAFT_FILE")"
PUBLISH_PLAN_BASENAME="$(basename_or_null "$PUBLISH_PLAN_FILE")"
GIT_COMMIT="$(git_value_or_null rev-parse HEAD | tr -d '\n')"
GIT_BRANCH="$(git_value_or_null branch --show-current | tr -d '\n')"

PAYLOAD="$("$JQ_BIN" -n \
  --arg runId "$RUN_ID" \
  --arg checkedAt "$CHECKED_AT" \
  --arg gitCommit "$GIT_COMMIT" \
  --arg gitBranch "$GIT_BRANCH" \
  --argjson operatorBundleFile "$OPERATOR_BUNDLE_BASENAME" \
  --argjson releaseNotesDraftFile "$RELEASE_NOTES_BASENAME" \
  --argjson publishPlanFile "$PUBLISH_PLAN_BASENAME" \
  --slurpfile bundle "$OPERATOR_BUNDLE_FILE" \
  --slurpfile plan "$PUBLISH_PLAN_FILE" \
  '
  $bundle[0] as $bundle
  | $plan[0] as $plan
  | [
      (if ($plan.evidence.operatorBundle.file // "") == $operatorBundleFile then empty else "operator_bundle_file_mismatch" end),
      (if ($plan.evidence.releaseNotesDraft.file // "") == $releaseNotesDraftFile then empty else "release_notes_draft_file_mismatch" end),
      (if ($plan.package.name // "") == ($bundle.package.name // "") then empty else "package_name_mismatch" end),
      (if ($plan.package.version // "") == ($bundle.package.version // "") then empty else "package_version_mismatch" end),
      (if ($plan.artifact.shasum // "") == ($bundle.artifact.shasum // "") then empty else "artifact_shasum_mismatch" end),
      (if ($plan.artifact.integrity // "") == ($bundle.artifact.integrity // "") then empty else "artifact_integrity_mismatch" end)
    ] as $blockers
  | {
      schemaVersion: 1,
      kind: "openclaw_cliq_rc_operator_handoff_manifest",
      runId: $runId,
      checkedAt: $checkedAt,
      status: (if ($blockers | length) == 0 then "operator_handoff_manifest_ready" else "blocked" end),
      blockers: $blockers,
      source: {
        gitCommit: (if $gitCommit == "" then null else $gitCommit end),
        gitBranch: (if $gitBranch == "" then null else $gitBranch end)
      },
      package: {
        name: ($bundle.package.name // null),
        version: ($bundle.package.version // null),
        expectedIntegrityState: ($bundle.package.expectedIntegrityState // null)
      },
      artifact: {
        filename: ($bundle.artifact.filename // null),
        shasum: ($bundle.artifact.shasum // null),
        integrity: ($bundle.artifact.integrity // null)
      },
      evidenceFiles: {
        operatorBundle: $operatorBundleFile,
        releaseNotesDraft: $releaseNotesDraftFile,
        publishPlan: $publishPlanFile,
        packSummary: ($bundle.reports.packSummary.file // null),
        artifact: ($bundle.reports.artifact.file // null),
        installSmoke: ($bundle.reports.installSmoke.file // null),
        promotion: ($bundle.reports.promotion.file // null),
        trustedReply: ($bundle.reports.trustedReply.file // null)
      },
      verifiedStatuses: {
        operatorBundle: ($bundle.status // null),
        publishPlan: ($plan.status // null),
        promotion: ($bundle.reports.promotion.status // null),
        artifact: ($bundle.reports.artifact.status // null),
        installSmoke: ($bundle.reports.installSmoke.status // null),
        trustedReply: ($bundle.reports.trustedReply.status // null)
      },
      safety: {
        blockedAgentActions: ($plan.blockedAgentActions // []),
        agentMayPublish: false,
        agentMayTag: false,
        agentMayCreateGithubRelease: false,
        agentMayFillExpectedIntegrity: false,
        agentMayExecutePlan: false
      },
      releasePosture: {
        publishPerformed: false,
        tagCreated: false,
        githubReleaseCreated: false,
        versionBumped: false,
        expectedIntegrityFilled: false,
        npmPromotionRequiresOperatorApproval: true
      },
      nextAction: (if ($blockers | length) == 0 then "operator_review_handoff_manifest" else "fix_handoff_manifest_blockers" end)
    }
  ')"

printf '%s\n' "$PAYLOAD" > "$MANIFEST_FILE"
printf '%s\n' "$PAYLOAD"

if [[ "$("$JQ_BIN" -r '.status' "$MANIFEST_FILE")" != "operator_handoff_manifest_ready" ]]; then
  exit 1
fi
