#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEFAULT_ZOHO_BIN="$ROOT/.venv/bin/zoho"
if [[ -x "$DEFAULT_ZOHO_BIN" ]]; then
  ZOHO_BIN="${ZOHO_BIN:-$DEFAULT_ZOHO_BIN}"
else
  ZOHO_BIN="${ZOHO_BIN:-zoho}"
fi
JQ_BIN="${JQ_BIN:-jq}"
RUN_ID="${ZOHO_CRM_FIXTURE_READINESS_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT_DIR="${ZOHO_CRM_FIXTURE_READINESS_REPORT_DIR:-"$ROOT/tests/auto_pilot/reports"}"
SUMMARY_FILE="${ZOHO_CRM_FIXTURE_SUMMARY_FILE:-}"
EVIDENCE_FILE="${ZOHO_CRM_FIXTURE_EVIDENCE_FILE:-"$REPORT_DIR/crm_fixture_operator_evidence_$RUN_ID.json"}"
BUNDLE_FILE="${ZOHO_CRM_FIXTURE_READINESS_BUNDLE_FILE:-"$REPORT_DIR/crm_fixture_operator_readiness_bundle_$RUN_ID.json"}"

emit_error() {
  local error="$1"
  printf '{"schemaVersion":1,"kind":"crm_fixture_operator_readiness_bundle","runId":"%s","checkedAt":"%s","status":"error","error":"%s"}\n' "$RUN_ID" "$CHECKED_AT" "$error"
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
command -v "$ZOHO_BIN" >/dev/null 2>&1 || {
  emit_error "zoho_bin_required"
  exit 2
}

mkdir -p "$REPORT_DIR"

SUMMARY_EXISTS=false
EVIDENCE_COMMAND_EXIT=0
if [[ -n "$SUMMARY_FILE" && -f "$SUMMARY_FILE" ]]; then
  SUMMARY_EXISTS=true
  if "$ZOHO_BIN" crm fixture-evidence --summary-file "$SUMMARY_FILE" >"$EVIDENCE_FILE"; then
    EVIDENCE_COMMAND_EXIT=0
  else
    EVIDENCE_COMMAND_EXIT=$?
    printf '{}\n' >"$EVIDENCE_FILE"
  fi
else
  EVIDENCE_COMMAND_EXIT=0
fi

EVIDENCE_EXISTS=false
if [[ "$SUMMARY_EXISTS" == true && -f "$EVIDENCE_FILE" ]]; then
  EVIDENCE_EXISTS=true
fi

SUMMARY_SLURP="/dev/null"
EVIDENCE_SLURP="/dev/null"
if [[ "$SUMMARY_EXISTS" == true ]]; then
  SUMMARY_SLURP="$SUMMARY_FILE"
fi
if [[ "$EVIDENCE_EXISTS" == true ]]; then
  EVIDENCE_SLURP="$EVIDENCE_FILE"
fi

SUMMARY_BASENAME="$(json_basename "$SUMMARY_FILE")"
EVIDENCE_BASENAME="$(json_basename "$EVIDENCE_FILE")"
BUNDLE_BASENAME="$(json_basename "$BUNDLE_FILE")"

PAYLOAD="$("$JQ_BIN" -n \
  --arg runId "$RUN_ID" \
  --arg checkedAt "$CHECKED_AT" \
  --argjson summaryExists "$SUMMARY_EXISTS" \
  --argjson evidenceExists "$EVIDENCE_EXISTS" \
  --argjson evidenceCommandExit "$EVIDENCE_COMMAND_EXIT" \
  --argjson bundleFile "$BUNDLE_BASENAME" \
  --argjson summaryFile "$SUMMARY_BASENAME" \
  --argjson evidenceFile "$EVIDENCE_BASENAME" \
  --slurpfile summary "$SUMMARY_SLURP" \
  --slurpfile evidence "$EVIDENCE_SLURP" \
  '
  (if $summaryExists then $summary[0] else {} end) as $summaryReport
  | (if $evidenceExists then $evidence[0] else {} end) as $evidenceReport
  | ($summaryReport.payloadTemplatePlaceholders.emailCount // null) as $emailPlaceholders
  | ($evidenceReport.status // "") as $evidenceStatus
  | [
      (if $summaryExists then empty else "summary_file_missing" end),
      (if $evidenceCommandExit == 0 then empty else "fixture_evidence_command_failed" end),
      (if $evidenceExists then empty else "fixture_evidence_report_missing" end),
      (if $evidenceStatus == "ready_for_operator_live_fixture" or $evidenceStatus == "live_fixture_recorded" then empty else "fixture_evidence_not_ready" end),
      (if $emailPlaceholders != null then empty else "payload_placeholder_count_missing" end),
      (if $emailPlaceholders == null or $emailPlaceholders == 0 then empty else "fixture_payload_placeholder_email" end),
      (if ($evidenceReport.redaction.ok // false) == true then empty else "redaction_not_ok" end),
      (if ($evidenceStatus == "live_fixture_recorded") or (($summaryReport.executeRequested // false) == false) then empty else "unexpected_live_execute_requested" end),
      (if ($evidenceStatus == "live_fixture_recorded") or (($summaryReport.liveResultRecorded // false) == false) then empty else "unexpected_live_result_recorded" end)
    ] as $blockers
  | {
      schemaVersion: 1,
      kind: "crm_fixture_operator_readiness_bundle",
      runId: $runId,
      checkedAt: $checkedAt,
      status: (
        if ($blockers | length) != 0 then "blocked"
        elif $evidenceStatus == "live_fixture_recorded" then "live_fixture_recorded"
        else "ready_for_operator_live_fixture"
        end
      ),
      blockers: $blockers,
      reportFiles: {
        readinessBundle: $bundleFile,
        smokeSummary: (if $summaryExists then $summaryFile else null end),
        fixtureEvidence: (if $evidenceExists then $evidenceFile else null end)
      },
      reportsReady: {
        readinessBundle: true,
        smokeSummary: $summaryExists,
        fixtureEvidence: $evidenceExists
      },
      summary: {
        ready: $summaryExists,
        file: $summaryFile,
        runId: ($summaryReport.runId // null),
        module: ($summaryReport.module // null),
        duplicateField: ($summaryReport.duplicateField // null),
        payloadDigest: ($summaryReport.payloadDigest // null),
        requiredApprovalPresent: (($summaryReport.requiredApproval // "") != ""),
        payloadTemplatePlaceholders: {
          emailCount: $emailPlaceholders
        },
        executeRequested: ($summaryReport.executeRequested // null),
        liveResultRecorded: ($summaryReport.liveResultRecorded // null)
      },
      evidence: {
        ready: $evidenceExists,
        file: $evidenceFile,
        commandExit: $evidenceCommandExit,
        policyId: ($evidenceReport.policyId // null),
        status: ($evidenceReport.status // null),
        decision: ($evidenceReport.decision // null),
        blockingReasons: ($evidenceReport.blockingReasons // []),
        operatorReadiness: ($evidenceReport.operatorReadiness // null),
        redaction: ($evidenceReport.redaction // null)
      },
      releasePosture: {
        normalUpsertExecuteBlocked: true,
        agentMayExecuteLiveFixture: false,
        agentMayRunNormalUpsertExecute: false,
        liveFixtureRequiresOperatorApproval: true,
        requiredLiveEnv: [
          "ZOHO_CRM_FIXTURE_EXECUTE=1",
          "ZOHO_CRM_ALLOW_LIVE_FIXTURE=1"
        ]
      },
      nextAction: (
        if ($blockers | length) != 0 then "fix_blockers"
        elif $evidenceStatus == "live_fixture_recorded" then "review_live_fixture_evidence"
        else "operator_review_payload_cleanup_and_approval"
        end
      )
    }
  ')"

printf '%s\n' "$PAYLOAD" >"$BUNDLE_FILE"
printf '%s\n' "$PAYLOAD"

if [[ "$("$JQ_BIN" -r '.status' "$BUNDLE_FILE")" == "blocked" ]]; then
  exit 1
fi
