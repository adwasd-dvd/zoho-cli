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
  | (
      if ($blockers | length) != 0 then "blocked"
      elif $evidenceStatus == "live_fixture_recorded" then "live_fixture_recorded"
      else "ready_for_operator_live_fixture"
      end
    ) as $status
  | (
      if $status == "live_fixture_recorded" then [
        {
          id: "review_live_fixture_evidence",
          command: "ZOHO_CRM_FIXTURE_SUMMARY_FILE=<smoke-summary.json> ops/scripts/crm_fixture_operator_readiness_bundle.sh",
          purpose: "review the redacted recorded live fixture readiness bundle",
          writesZohoData: false,
          dryRunOnly: true,
          agentMayExecute: true,
          requiresOperatorInput: true,
          requiresExplicitOperatorApproval: false,
          operatorOnly: false
        }
      ]
      elif $status == "ready_for_operator_live_fixture" then [
        {
          id: "operator_review_live_fixture_approval",
          command: "ZOHO_CRM_FIXTURE_EXECUTE=1 ZOHO_CRM_ALLOW_LIVE_FIXTURE=1 ZOHO_CRM_FIXTURE_PAYLOAD_FILE=<copied-fixture-payload.json> ZOHO_CRM_FIXTURE_CLEANUP_PLAN=<cleanup-plan> ops/scripts/crm_fixture_live_smoke.sh",
          purpose: "operator-only live fixture approval after reviewing the readiness bundle",
          writesZohoData: true,
          dryRunOnly: false,
          agentMayExecute: false,
          requiresOperatorInput: true,
          requiresExplicitOperatorApproval: true,
          operatorOnly: true
        }
      ]
      else [
        {
          id: "fix_readiness_blockers",
          command: "ZOHO_CRM_FIXTURE_SUMMARY_FILE=<smoke-summary.json> ops/scripts/crm_fixture_operator_readiness_bundle.sh",
          purpose: "fix the readiness blockers and rerun the no-write readiness bundle",
          writesZohoData: false,
          dryRunOnly: true,
          agentMayExecute: true,
          requiresOperatorInput: true,
          requiresExplicitOperatorApproval: false,
          operatorOnly: false
        }
      ]
      end
    ) as $nextCommands
  | ($nextCommands | map(select(.agentMayExecute == true) | .id)) as $agentExecutableCommandIds
  | ($nextCommands | map(select(.operatorOnly == true) | .id)) as $operatorOnlyCommandIds
  | ($nextCommands | map(select(.writesZohoData == true) | .id)) as $zohoWriteCommandIds
  | ($nextCommands | map(select(.dryRunOnly == true) | .id)) as $dryRunOnlyCommandIds
  | ($nextCommands | map(select(.requiresExplicitOperatorApproval == true) | .id)) as $approvalCommandIds
  | {
      schemaVersion: 1,
      kind: "crm_fixture_operator_readiness_bundle",
      runId: $runId,
      checkedAt: $checkedAt,
      status: $status,
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
        payloadDigestPresent: (($summaryReport.payloadDigest // "") != ""),
        idempotencyKeyPresent: (($summaryReport.idempotencyKey // "") != ""),
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
      operatorReview: {
        nextCommands: $nextCommands,
        actionBoundary: {
          nextCommandCount: ($nextCommands | length),
          agentExecutableCommandIds: $agentExecutableCommandIds,
          operatorOnlyCommandIds: $operatorOnlyCommandIds,
          zohoWriteCommandIds: $zohoWriteCommandIds,
          dryRunOnlyCommandIds: $dryRunOnlyCommandIds,
          requiresExplicitOperatorApprovalCommandIds: $approvalCommandIds,
          agentMayExecuteAny: (($agentExecutableCommandIds | length) > 0),
          operatorOnlyAny: (($operatorOnlyCommandIds | length) > 0),
          writesZohoDataAny: (($zohoWriteCommandIds | length) > 0),
          requiresExplicitOperatorApprovalAny: (($approvalCommandIds | length) > 0),
          normalUpsertExecuteBlocked: true,
          liveFixtureExecutionBoundary: (if (($zohoWriteCommandIds | length) > 0) then "operator_only" else "not_ready_or_dry_run_only" end)
        },
        agentAutomation: {
          policyId: "crm-fixture-agent-command-boundary-v1",
          guidance: "execute only dry-run/local command ids listed in nextAgentExecutableCommandId or agentExecutableCommandIds; stop on any operator-only, Zoho-writing, or explicit-approval id",
          nextAgentExecutableCommandId: ($agentExecutableCommandIds[0] // null),
          agentMayExecuteNextCommand: (
            (($agentExecutableCommandIds | length) > 0)
            and (($zohoWriteCommandIds | length) == 0)
            and (($approvalCommandIds | length) == 0)
          ),
          agentExecutableCommandIds: $agentExecutableCommandIds,
          dryRunOnlyCommandIds: $dryRunOnlyCommandIds,
          stopCommandIds: (($operatorOnlyCommandIds + $zohoWriteCommandIds + $approvalCommandIds) | unique),
          stopReason: (
            if (($operatorOnlyCommandIds + $zohoWriteCommandIds + $approvalCommandIds) | unique | length) > 0 then "operator_only_zoho_write_or_approval_required"
            elif ($agentExecutableCommandIds | length) == 0 then "no_agent_executable_command"
            else null
            end
          ),
          normalUpsertExecuteBlocked: true,
          liveFixtureExecutionBlockedForAgent: true
        },
        liveApproval: {
          readyFacts: ([
            (if $summaryExists then "summary_file_ready" else empty end),
            (if ($evidenceExists and ($evidenceStatus == "ready_for_operator_live_fixture" or $evidenceStatus == "live_fixture_recorded")) then "dry_run_readiness_ready" else empty end),
            (if ($evidenceExists and ($evidenceStatus == "ready_for_operator_live_fixture" or $evidenceStatus == "live_fixture_recorded")) then "fixture_evidence_ready" else empty end),
            (if (($summaryReport.payloadDigest // "") != "") then "payload_digest_present" else empty end),
            (if (($summaryReport.idempotencyKey // "") != "") then "idempotency_key_present" else empty end),
            (if (($summaryReport.requiredApproval // "") != "") then "required_approval_present" else empty end),
            (if ($emailPlaceholders == 0) then "placeholder_email_count_zero" else empty end),
            "command_preview_uses_placeholders",
            "agent_execution_blocked"
          ] | unique),
          missingFacts: ([
            (if $summaryExists then empty else "summary_file" end),
            (if ($evidenceExists and ($evidenceStatus == "ready_for_operator_live_fixture" or $evidenceStatus == "live_fixture_recorded")) then empty else "dry_run_readiness" end),
            (if ($evidenceExists and ($evidenceStatus == "ready_for_operator_live_fixture" or $evidenceStatus == "live_fixture_recorded")) then empty else "fixture_evidence" end),
            (if (($summaryReport.payloadDigest // "") != "") then empty else "payload_digest" end),
            (if (($summaryReport.idempotencyKey // "") != "") then empty else "idempotency_key" end),
            (if (($summaryReport.requiredApproval // "") != "") then empty else "required_approval" end),
            (if ($emailPlaceholders == 0) then empty else "placeholder_email_count_zero" end)
          ] | unique),
          summaryFileReady: $summaryExists,
          dryRunReadinessReady: ($evidenceExists and ($evidenceStatus == "ready_for_operator_live_fixture" or $evidenceStatus == "live_fixture_recorded")),
          fixtureEvidenceReady: ($evidenceExists and ($evidenceStatus == "ready_for_operator_live_fixture" or $evidenceStatus == "live_fixture_recorded")),
          payloadDigestPresent: (($summaryReport.payloadDigest // "") != ""),
          idempotencyKeyPresent: (($summaryReport.idempotencyKey // "") != ""),
          requiredApprovalPresent: (($summaryReport.requiredApproval // "") != ""),
          placeholderEmailCountZero: ($emailPlaceholders == 0),
          commandPreviewUsesPlaceholders: true,
          writesZohoData: ($evidenceStatus == "ready_for_operator_live_fixture"),
          agentMayExecute: false,
          agentMayExecuteLiveFixture: false,
          agentMayRunNormalUpsertExecute: false,
          operatorOnly: true,
          requiresExplicitOperatorApproval: true
        },
        redaction: {
          rawRequiredApprovalStored: false,
          rawIdempotencyKeyStored: false,
          rawPayloadValuesStored: false,
          rawCleanupPlanStored: false
        }
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
