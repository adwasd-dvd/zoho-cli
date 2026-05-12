#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
JQ_BIN="${JQ_BIN:-jq}"
RUN_ID="${OPENCLAW_CLIQ_SELECTION_REVIEW_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT_DIR="${OPENCLAW_CLIQ_SELECTION_REVIEW_REPORT_DIR:-"$ROOT/tests/auto_pilot/reports"}"
PUBLISH_PLAN_FILE="${OPENCLAW_CLIQ_PUBLISH_PLAN_FILE:-}"
SOURCE_DRIFT_FILE="${OPENCLAW_CLIQ_SOURCE_DRIFT_REPORT_FILE:-}"
SELECTION_REVIEW_FILE="${OPENCLAW_CLIQ_SELECTION_REVIEW_FILE:-"$REPORT_DIR/openclaw_cliq_rc_operator_selection_review_$RUN_ID.json"}"

emit_error() {
  local error="$1"
  printf '{"schemaVersion":1,"kind":"openclaw_cliq_rc_operator_selection_review","runId":"%s","checkedAt":"%s","status":"error","error":"%s"}\n' "$RUN_ID" "$CHECKED_AT" "$error"
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

command -v "$JQ_BIN" >/dev/null 2>&1 || {
  emit_error "jq_required"
  exit 2
}

mkdir -p "$REPORT_DIR"

if [[ -z "$PUBLISH_PLAN_FILE" ]]; then
  PUBLISH_PLAN_FILE="$(latest_report "openclaw_cliq_rc_publish_plan_*.json")"
fi
if [[ -z "$SOURCE_DRIFT_FILE" ]]; then
  SOURCE_DRIFT_FILE="$(latest_report "openclaw_cliq_rc_source_drift_check_*.json")"
fi

if [[ -z "$PUBLISH_PLAN_FILE" || ! -f "$PUBLISH_PLAN_FILE" ]]; then
  emit_error "publish_plan_missing"
  exit 2
fi
if [[ -z "$SOURCE_DRIFT_FILE" || ! -f "$SOURCE_DRIFT_FILE" ]]; then
  emit_error "source_drift_report_missing"
  exit 2
fi
if [[ "$("$JQ_BIN" -r '.status // ""' "$PUBLISH_PLAN_FILE")" != "operator_publish_plan_ready" ]]; then
  emit_error "publish_plan_not_ready"
  exit 1
fi
if [[ "$("$JQ_BIN" -r '.status // ""' "$SOURCE_DRIFT_FILE")" != "package_source_unchanged" ]]; then
  emit_error "source_drift_not_clean"
  exit 1
fi

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

PUBLISH_PLAN_BASENAME="$(basename_or_null "$PUBLISH_PLAN_FILE")"
SOURCE_DRIFT_BASENAME="$(basename_or_null "$SOURCE_DRIFT_FILE")"

PAYLOAD="$("$JQ_BIN" -n \
  --arg runId "$RUN_ID" \
  --arg checkedAt "$CHECKED_AT" \
  --argjson publishPlanFile "$PUBLISH_PLAN_BASENAME" \
  --argjson sourceDriftFile "$SOURCE_DRIFT_BASENAME" \
  --slurpfile plan "$PUBLISH_PLAN_FILE" \
  --slurpfile drift "$SOURCE_DRIFT_FILE" \
  '
  $plan[0] as $plan
  | $drift[0] as $drift
  | ($plan.selectedPublishPath // null) as $selectedPath
  | (
      if $selectedPath == null then null
      else (($plan.publishPaths // []) | map(select(.id == $selectedPath)) | .[0] // null)
      end
    ) as $selectedPathSpec
  | [
      (if $selectedPath != null then empty else "publish_path_not_selected" end),
      (if $selectedPath == null or $selectedPathSpec != null then empty else "publish_path_not_in_plan" end),
      (if (
        if ($drift.packageDrift | has("packageChangedSinceManifest"))
        then $drift.packageDrift.packageChangedSinceManifest
        else true
        end
      ) == false then empty else "package_source_drift_detected" end),
      (if ($drift.packageDrift.dirtyFileCount // 1) == 0 then empty else "package_worktree_or_index_dirty" end)
    ] as $blockers
  | {
      schemaVersion: 1,
      kind: "openclaw_cliq_rc_operator_selection_review",
      runId: $runId,
      checkedAt: $checkedAt,
      status: (if ($blockers | length) == 0 then "operator_publish_selection_ready" else "blocked" end),
      blockers: $blockers,
      selectedPublishPath: $selectedPath,
      selectedPublishPathReview: (
        if $selectedPathSpec == null then null
        else {
          id: ($selectedPathSpec.id // null),
          operatorOnly: ($selectedPathSpec.operatorOnly // true),
          fillsExpectedIntegrity: ($selectedPathSpec.fillsExpectedIntegrity // false),
          fillsExpectedIntegrityAfterPublish: ($selectedPathSpec.fillsExpectedIntegrityAfterPublish // false),
          commandPreview: ($selectedPathSpec.commandPreview // null),
          agentMayExecute: false,
          requiresExplicitOperatorApproval: true
        }
        end
      ),
      evidenceFiles: {
        publishPlan: $publishPlanFile,
        sourceDrift: $sourceDriftFile,
        operatorBundle: ($plan.evidence.operatorBundle.file // null),
        releaseNotesDraft: ($plan.evidence.releaseNotesDraft.file // null)
      },
      package: {
        name: ($plan.package.name // null),
        version: ($plan.package.version // null),
        expectedIntegrityState: ($plan.package.expectedIntegrityState // null)
      },
      artifact: {
        filename: ($plan.artifact.filename // null),
        shasum: ($plan.artifact.shasum // null),
        integrity: ($plan.artifact.integrity // null),
        pathHint: ($plan.artifact.pathHint // null)
      },
      sourceDrift: {
        status: ($drift.status // null),
        sourceCommit: ($drift.source.sourceCommit // null),
        headCommit: ($drift.source.headCommit // null),
        packagePathFilter: ($drift.source.packagePathFilter // null),
        repoChangedSinceManifest: ($drift.source.repoChangedSinceManifest),
        packageChangedSinceManifest: ($drift.packageDrift.packageChangedSinceManifest),
        packageDirtyFileCount: ($drift.packageDrift.dirtyFileCount // null)
      },
      safety: {
        blockedAgentActions: ($plan.blockedAgentActions // []),
        agentMayPublish: false,
        agentMayTag: false,
        agentMayCreateGithubRelease: false,
        agentMayFillExpectedIntegrity: false,
        agentMayExecuteSelectedPath: false
      },
      releasePosture: {
        publishPerformed: false,
        tagCreated: false,
        githubReleaseCreated: false,
        versionBumped: false,
        expectedIntegrityFilled: false,
        npmPromotionRequiresOperatorApproval: true
      },
      nextAction: (
        if ($blockers | index("publish_path_not_selected")) then "operator_select_publish_path"
        elif ($blockers | length) != 0 then "fix_selection_review_blockers"
        else "operator_review_selected_publish_path"
        end
      )
    }
  ')"

printf '%s\n' "$PAYLOAD" >"$SELECTION_REVIEW_FILE"
printf '%s\n' "$PAYLOAD"

if [[ "$("$JQ_BIN" -r '.status' "$SELECTION_REVIEW_FILE")" != "operator_publish_selection_ready" ]]; then
  exit 1
fi
