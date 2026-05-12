#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
JQ_BIN="${JQ_BIN:-jq}"

RUN_ID="${OPENCLAW_CLIQ_DECISION_PACKET_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT_DIR="${OPENCLAW_CLIQ_DECISION_PACKET_REPORT_DIR:-"$ROOT/tests/auto_pilot/reports"}"
PACKET_FILE="${OPENCLAW_CLIQ_DECISION_PACKET_FILE:-"$REPORT_DIR/openclaw_cliq_rc_operator_decision_packet_$RUN_ID.json"}"
PUBLISH_PLAN_FILE="${OPENCLAW_CLIQ_DECISION_PACKET_PUBLISH_PLAN_FILE:-"$REPORT_DIR/openclaw_cliq_rc_publish_plan_$RUN_ID.json"}"
SOURCE_DRIFT_FILE="${OPENCLAW_CLIQ_DECISION_PACKET_SOURCE_DRIFT_FILE:-"$REPORT_DIR/openclaw_cliq_rc_source_drift_check_$RUN_ID.json"}"
SELECTION_REVIEW_FILE="${OPENCLAW_CLIQ_DECISION_PACKET_SELECTION_REVIEW_FILE:-"$REPORT_DIR/openclaw_cliq_rc_operator_selection_review_$RUN_ID.json"}"

emit_error() {
  local error="$1"
  printf '{"schemaVersion":1,"kind":"openclaw_cliq_rc_operator_decision_packet","runId":"%s","checkedAt":"%s","status":"error","error":"%s"}\n' "$RUN_ID" "$CHECKED_AT" "$error"
}

json_basename() {
  local path="${1:-}"
  if [[ -z "$path" ]]; then
    "$JQ_BIN" -n 'null'
  else
    "$JQ_BIN" -n --arg value "$(basename "$path")" '$value'
  fi
}

command -v "$JQ_BIN" >/dev/null 2>&1 || {
  emit_error "jq_required"
  exit 2
}

mkdir -p "$REPORT_DIR"

PUBLISH_PLAN_EXIT=0
OPENCLAW_CLIQ_PUBLISH_PLAN_RUN_ID="$RUN_ID" \
OPENCLAW_CLIQ_PUBLISH_PLAN_REPORT_DIR="$REPORT_DIR" \
OPENCLAW_CLIQ_PUBLISH_PLAN_FILE="$PUBLISH_PLAN_FILE" \
  "$ROOT/ops/scripts/openclaw_cliq_rc_publish_plan.sh" \
  >"$REPORT_DIR/openclaw_cliq_rc_operator_decision_packet_${RUN_ID}_publish_plan.stdout" \
  2>"$REPORT_DIR/openclaw_cliq_rc_operator_decision_packet_${RUN_ID}_publish_plan.stderr" || PUBLISH_PLAN_EXIT=$?
[[ -f "$PUBLISH_PLAN_FILE" ]] || printf '{}\n' >"$PUBLISH_PLAN_FILE"

SOURCE_DRIFT_EXIT=0
OPENCLAW_CLIQ_SOURCE_DRIFT_RUN_ID="$RUN_ID" \
OPENCLAW_CLIQ_SOURCE_DRIFT_REPORT_FILE="$SOURCE_DRIFT_FILE" \
  "$ROOT/ops/scripts/openclaw_cliq_rc_source_drift_check.sh" \
  >"$REPORT_DIR/openclaw_cliq_rc_operator_decision_packet_${RUN_ID}_source_drift.stdout" \
  2>"$REPORT_DIR/openclaw_cliq_rc_operator_decision_packet_${RUN_ID}_source_drift.stderr" || SOURCE_DRIFT_EXIT=$?
[[ -f "$SOURCE_DRIFT_FILE" ]] || printf '{}\n' >"$SOURCE_DRIFT_FILE"

SELECTION_REVIEW_EXIT=0
OPENCLAW_CLIQ_SELECTION_REVIEW_RUN_ID="$RUN_ID" \
OPENCLAW_CLIQ_SELECTION_REVIEW_REPORT_DIR="$REPORT_DIR" \
OPENCLAW_CLIQ_PUBLISH_PLAN_FILE="$PUBLISH_PLAN_FILE" \
OPENCLAW_CLIQ_SOURCE_DRIFT_REPORT_FILE="$SOURCE_DRIFT_FILE" \
OPENCLAW_CLIQ_SELECTION_REVIEW_FILE="$SELECTION_REVIEW_FILE" \
  "$ROOT/ops/scripts/openclaw_cliq_rc_operator_selection_review.sh" \
  >"$REPORT_DIR/openclaw_cliq_rc_operator_decision_packet_${RUN_ID}_selection_review.stdout" \
  2>"$REPORT_DIR/openclaw_cliq_rc_operator_decision_packet_${RUN_ID}_selection_review.stderr" || SELECTION_REVIEW_EXIT=$?
[[ -f "$SELECTION_REVIEW_FILE" ]] || printf '{}\n' >"$SELECTION_REVIEW_FILE"

PUBLISH_PLAN_BASENAME="$(json_basename "$PUBLISH_PLAN_FILE")"
SOURCE_DRIFT_BASENAME="$(json_basename "$SOURCE_DRIFT_FILE")"
SELECTION_REVIEW_BASENAME="$(json_basename "$SELECTION_REVIEW_FILE")"

PAYLOAD="$("$JQ_BIN" -n \
  --arg runId "$RUN_ID" \
  --arg checkedAt "$CHECKED_AT" \
  --argjson publishPlanExit "$PUBLISH_PLAN_EXIT" \
  --argjson sourceDriftExit "$SOURCE_DRIFT_EXIT" \
  --argjson selectionReviewExit "$SELECTION_REVIEW_EXIT" \
  --argjson publishPlanFile "$PUBLISH_PLAN_BASENAME" \
  --argjson sourceDriftFile "$SOURCE_DRIFT_BASENAME" \
  --argjson selectionReviewFile "$SELECTION_REVIEW_BASENAME" \
  --slurpfile plan "$PUBLISH_PLAN_FILE" \
  --slurpfile drift "$SOURCE_DRIFT_FILE" \
  --slurpfile review "$SELECTION_REVIEW_FILE" \
  '
  ($plan[0] // {}) as $plan
  | ($drift[0] // {}) as $drift
  | ($review[0] // {}) as $review
  | ($plan.status // "missing") as $planStatus
  | ($drift.status // "missing") as $driftStatus
  | ($review.status // "missing") as $reviewStatus
  | (
      [(if $planStatus == "operator_publish_plan_ready" then empty else "publish_plan_not_ready" end)]
      + (if $driftStatus == "package_source_unchanged" then [] else ["source_drift_not_clean"] end)
      + (if ($drift.blockers // []) | length == 0 then [] else ($drift.blockers // []) end)
      + (if ($reviewStatus == "blocked" or $reviewStatus == "error") then ($review.blockers // [$review.error // "selection_review_not_ready"]) else [] end)
    ) as $rawBlockers
  | ($rawBlockers | unique) as $blockers
  | (
      if $planStatus != "operator_publish_plan_ready" or $driftStatus != "package_source_unchanged" then "blocked"
      elif $reviewStatus == "operator_publish_selection_ready" then "operator_publish_selection_ready"
      elif ($blockers | index("publish_path_not_selected")) then "awaiting_operator_publish_path"
      else "blocked"
      end
    ) as $status
  | {
      schemaVersion: 1,
      kind: "openclaw_cliq_rc_operator_decision_packet",
      runId: $runId,
      checkedAt: $checkedAt,
      status: $status,
      blockers: $blockers,
      selectedPublishPath: ($plan.selectedPublishPath // null),
      publishPaths: ($plan.publishPaths // []),
      selectedPublishPathReview: ($review.selectedPublishPathReview // null),
      evidenceFiles: {
        publishPlan: $publishPlanFile,
        sourceDrift: $sourceDriftFile,
        selectionReview: $selectionReviewFile,
        operatorBundle: ($plan.evidence.operatorBundle.file // null),
        releaseNotesDraft: ($plan.evidence.releaseNotesDraft.file // null),
        handoffManifest: ($drift.source.manifestFile // null)
      },
      reportFiles: {
        publishPlan: $publishPlanFile,
        sourceDrift: $sourceDriftFile,
        selectionReview: $selectionReviewFile,
        operatorBundle: ($plan.evidence.operatorBundle.file // null),
        releaseNotesDraft: ($plan.evidence.releaseNotesDraft.file // null),
        handoffManifest: ($drift.source.manifestFile // null)
      },
      reportsReady: {
        publishPlan: (($publishPlanExit == 0) and ($planStatus == "operator_publish_plan_ready")),
        sourceDrift: (($sourceDriftExit == 0) and ($driftStatus == "package_source_unchanged")),
        selectionReview: (
          (($selectionReviewExit == 0) and ($reviewStatus == "operator_publish_selection_ready"))
          or (($reviewStatus == "blocked") and ((($review.blockers // []) | index("publish_path_not_selected")) != null))
        ),
        operatorBundle: (($plan.evidence.operatorBundle.file // null) != null and ($plan.evidence.operatorBundle.status // null) == "operator_publish_bundle_ready"),
        releaseNotesDraft: (($plan.evidence.releaseNotesDraft.file // null) != null and ($plan.evidence.releaseNotesDraft.status // null) == "draft_ready"),
        handoffManifest: (($drift.source.manifestFile // null) != null)
      },
      commandExits: {
        publishPlan: $publishPlanExit,
        sourceDrift: $sourceDriftExit,
        selectionReview: $selectionReviewExit
      },
      verifiedStatuses: {
        publishPlan: $planStatus,
        sourceDrift: $driftStatus,
        selectionReview: $reviewStatus,
        promotion: ($plan.evidence.promotion.status // null),
        artifact: ($plan.evidence.artifact.status // null),
        installSmoke: ($plan.evidence.installSmoke.status // null),
        trustedReply: ($plan.evidence.trustedReply.status // null)
      },
      package: {
        name: ($plan.package.name // $drift.package.name // null),
        version: ($plan.package.version // $drift.package.version // null),
        expectedIntegrityState: ($plan.package.expectedIntegrityState // $drift.package.expectedIntegrityState // null)
      },
      artifact: {
        filename: ($plan.artifact.filename // $drift.artifact.filename // null),
        shasum: ($plan.artifact.shasum // $drift.artifact.shasum // null),
        integrity: ($plan.artifact.integrity // $drift.artifact.integrity // null),
        pathHint: ($plan.artifact.pathHint // null)
      },
      sourceDrift: {
        status: $driftStatus,
        sourceCommit: ($drift.source.sourceCommit // null),
        headCommit: ($drift.source.headCommit // null),
        repoChangedSinceManifest: (
          if ($drift.source | has("repoChangedSinceManifest"))
          then $drift.source.repoChangedSinceManifest
          else null
          end
        ),
        packageChangedSinceManifest: (
          if ($drift.packageDrift | has("packageChangedSinceManifest"))
          then $drift.packageDrift.packageChangedSinceManifest
          else null
          end
        ),
        packageDirtyFileCount: ($drift.packageDrift.dirtyFileCount // null)
      },
      safety: {
        blockedAgentActions: ($plan.blockedAgentActions // $review.safety.blockedAgentActions // []),
        agentMayPublish: false,
        agentMayTag: false,
        agentMayCreateGithubRelease: false,
        agentMayFillExpectedIntegrity: false,
        agentMayExecutePlan: false,
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
        if $status == "operator_publish_selection_ready" then "operator_review_selected_publish_path"
        elif $status == "awaiting_operator_publish_path" then "operator_select_publish_path"
        else "fix_operator_decision_packet_blockers"
        end
      )
    }
  ')"

printf '%s\n' "$PAYLOAD" >"$PACKET_FILE"
printf '%s\n' "$PAYLOAD"

if [[ "$("$JQ_BIN" -r '.status' "$PACKET_FILE")" == "blocked" ]]; then
  exit 1
fi
