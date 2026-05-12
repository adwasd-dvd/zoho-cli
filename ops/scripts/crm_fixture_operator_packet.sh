#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
JQ_BIN="${JQ_BIN:-jq}"

RUN_ID="${ZOHO_CRM_FIXTURE_PACKET_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT_DIR="${ZOHO_CRM_FIXTURE_PACKET_REPORT_DIR:-"$ROOT/tests/auto_pilot/reports"}"
PACKET_FILE="${ZOHO_CRM_FIXTURE_PACKET_FILE:-"$REPORT_DIR/crm_fixture_operator_packet_$RUN_ID.json"}"
PREFLIGHT_FILE="${ZOHO_CRM_FIXTURE_PACKET_PREFLIGHT_FILE:-"$REPORT_DIR/crm_fixture_payload_preflight_$RUN_ID.json"}"
READINESS_FILE="${ZOHO_CRM_FIXTURE_PACKET_READINESS_FILE:-"$REPORT_DIR/crm_fixture_operator_readiness_bundle_$RUN_ID.json"}"
SUMMARY_FILE="${ZOHO_CRM_FIXTURE_SUMMARY_FILE:-}"

emit_error() {
  local error="$1"
  printf '{"schemaVersion":1,"kind":"crm_fixture_operator_packet","runId":"%s","checkedAt":"%s","status":"error","error":"%s"}\n' "$RUN_ID" "$CHECKED_AT" "$error"
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

PREFLIGHT_EXIT=0
ZOHO_CRM_FIXTURE_PREFLIGHT_RUN_ID="$RUN_ID" \
ZOHO_CRM_FIXTURE_PREFLIGHT_REPORT_DIR="$REPORT_DIR" \
ZOHO_CRM_FIXTURE_PREFLIGHT_FILE="$PREFLIGHT_FILE" \
  "$ROOT/ops/scripts/crm_fixture_payload_preflight.sh" \
  >"$REPORT_DIR/crm_fixture_operator_packet_${RUN_ID}_preflight.stdout" \
  2>"$REPORT_DIR/crm_fixture_operator_packet_${RUN_ID}_preflight.stderr" || PREFLIGHT_EXIT=$?

READINESS_EXIT=0
READINESS_SKIPPED=true
if [[ -n "$SUMMARY_FILE" ]]; then
  READINESS_SKIPPED=false
  ZOHO_CRM_FIXTURE_READINESS_RUN_ID="$RUN_ID" \
  ZOHO_CRM_FIXTURE_READINESS_REPORT_DIR="$REPORT_DIR" \
  ZOHO_CRM_FIXTURE_READINESS_BUNDLE_FILE="$READINESS_FILE" \
    "$ROOT/ops/scripts/crm_fixture_operator_readiness_bundle.sh" \
    >"$REPORT_DIR/crm_fixture_operator_packet_${RUN_ID}_readiness.stdout" \
    2>"$REPORT_DIR/crm_fixture_operator_packet_${RUN_ID}_readiness.stderr" || READINESS_EXIT=$?
else
  printf '{}\n' >"$READINESS_FILE"
fi

PREFLIGHT_BASENAME="$(json_basename "$PREFLIGHT_FILE")"
READINESS_BASENAME="$(json_basename "$READINESS_FILE")"
SUMMARY_BASENAME="$(json_basename "$SUMMARY_FILE")"

PAYLOAD="$("$JQ_BIN" -n \
  --arg runId "$RUN_ID" \
  --arg checkedAt "$CHECKED_AT" \
  --argjson preflightExit "$PREFLIGHT_EXIT" \
  --argjson readinessExit "$READINESS_EXIT" \
  --argjson readinessSkipped "$READINESS_SKIPPED" \
  --argjson preflightFile "$PREFLIGHT_BASENAME" \
  --argjson readinessFile "$READINESS_BASENAME" \
  --argjson summaryFile "$SUMMARY_BASENAME" \
  --slurpfile preflight "$PREFLIGHT_FILE" \
  --slurpfile readiness "$READINESS_FILE" \
  '
  ($preflight[0] // {}) as $preflightReport
  | ($readiness[0] // {}) as $readinessReport
  | ($preflightReport.status // "missing") as $preflightStatus
  | ($readinessReport.status // null) as $readinessStatus
  | (
      if ($readinessSkipped | not) and ($readinessStatus == "live_fixture_recorded") then "live_fixture_recorded"
      elif ($readinessSkipped | not) and ($readinessStatus == "ready_for_operator_live_fixture") then "ready_for_operator_live_fixture"
      elif $preflightStatus == "payload_preflight_ready" then "payload_preflight_ready"
      else "blocked"
      end
    ) as $status
  | (
      if $status == "blocked" then
        (($preflightReport.blockers // ["payload_preflight_missing"])
        + (if $readinessSkipped then [] else ($readinessReport.blockers // ["fixture_readiness_missing"]) end))
      else []
      end
    ) as $blockers
  | {
      schemaVersion: 1,
      kind: "crm_fixture_operator_packet",
      runId: $runId,
      checkedAt: $checkedAt,
      status: $status,
      blockers: ($blockers | unique),
      payloadPreflight: {
        ready: ($preflightStatus == "payload_preflight_ready"),
        file: $preflightFile,
        commandExit: $preflightExit,
        status: $preflightStatus,
        blockers: ($preflightReport.blockers // []),
        nextAction: ($preflightReport.nextAction // null),
        payload: {
          file: ($preflightReport.payload.file // null),
          module: ($preflightReport.payload.module // null),
          recordCount: ($preflightReport.payload.recordCount // null),
          missingRequiredFields: ($preflightReport.payload.missingRequiredFields // []),
          placeholderEmailCount: ($preflightReport.payload.placeholderEmailCount // null),
          dedicatedFixtureCandidate: ($preflightReport.payload.dedicatedFixtureCandidate // false)
        },
        cleanup: ($preflightReport.cleanup // null)
      },
      dryRunReadiness: {
        ready: (($readinessStatus == "ready_for_operator_live_fixture") or ($readinessStatus == "live_fixture_recorded")),
        skipped: $readinessSkipped,
        skippedReason: (if $readinessSkipped then "summary_file_not_provided" else null end),
        file: $readinessFile,
        summaryFile: $summaryFile,
        commandExit: $readinessExit,
        status: $readinessStatus,
        blockers: ($readinessReport.blockers // []),
        evidenceStatus: ($readinessReport.evidence.status // null),
        nextAction: ($readinessReport.nextAction // null)
      },
      releasePosture: {
        normalUpsertExecuteBlocked: true,
        agentMayRunNormalUpsertExecute: false,
        agentMayExecuteLiveFixture: false,
        liveFixtureRequiresOperatorApproval: true,
        zohoBackedDryRunRequiresPayloadPreflight: true
      },
      nextAction: (
        if $status == "live_fixture_recorded" then "review_live_fixture_evidence"
        elif $status == "ready_for_operator_live_fixture" then "operator_review_payload_cleanup_and_approval"
        elif $status == "payload_preflight_ready" then "run_crm_fixture_live_smoke_dry_run"
        elif ($blockers | index("payload_file_required")) or ($blockers | index("payload_file_missing")) then "provide_fixture_payload_file"
        elif ($blockers | index("cleanup_plan_missing")) then "provide_cleanup_plan"
        elif ($blockers | index("cleanup_plan_too_short")) or ($blockers | index("cleanup_plan_action_missing")) or ($blockers | index("cleanup_plan_target_missing")) or ($blockers | index("cleanup_plan_selector_missing")) then "improve_cleanup_plan"
        else "fix_blockers"
        end
      )
    }
  ')"

printf '%s\n' "$PAYLOAD" >"$PACKET_FILE"
printf '%s\n' "$PAYLOAD"

if [[ "$("$JQ_BIN" -r '.status' "$PACKET_FILE")" == "blocked" ]]; then
  exit 1
fi
