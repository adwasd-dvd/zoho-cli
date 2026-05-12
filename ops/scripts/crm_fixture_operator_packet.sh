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
PACKET_BASENAME="$(json_basename "$PACKET_FILE")"

PAYLOAD="$("$JQ_BIN" -n \
  --arg runId "$RUN_ID" \
  --arg checkedAt "$CHECKED_AT" \
  --argjson preflightExit "$PREFLIGHT_EXIT" \
  --argjson readinessExit "$READINESS_EXIT" \
  --argjson readinessSkipped "$READINESS_SKIPPED" \
  --argjson packetFile "$PACKET_BASENAME" \
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
  | (
      [
        (if ($preflightReport.payload.dedicatedFixtureCandidate // false) then "dedicated_fixture_payload" else empty end),
        (if (($preflightReport.payload.placeholderEmailCount // null) == 0) then "placeholder_email_absent" else empty end),
        (if ($preflightReport.cleanup.qualityReady // false) then "cleanup_quality_ready" else empty end),
        (if (($preflightReport.cleanup.selectorTypes // []) | length) > 0 then "cleanup_selector_types_present" else empty end),
        (if $preflightStatus == "payload_preflight_ready" then "payload_preflight_ready" else empty end),
        (if (($readinessStatus == "ready_for_operator_live_fixture") or ($readinessStatus == "live_fixture_recorded")) then "dry_run_readiness_ready" else empty end)
      ] | unique
    ) as $readyFacts
  | (
      [
        (if ($blockers | index("payload_file_required")) or ($blockers | index("payload_file_missing")) then "fixture_payload_file" else empty end),
        (if ($blockers | index("payload_json_invalid")) then "fixture_payload_json" else empty end),
        (if ($blockers | index("payload_record_count_not_one")) then "single_record_payload" else empty end),
        (if ($blockers | index("required_fields_missing")) then "required_fields" else empty end),
        (if ($blockers | index("fixture_payload_placeholder_email")) then "dedicated_fixture_email" else empty end),
        (if ($blockers | index("cleanup_plan_missing")) then "cleanup_plan" else empty end),
        (if ($blockers | index("cleanup_plan_too_short")) or ($blockers | index("cleanup_plan_action_missing")) or ($blockers | index("cleanup_plan_target_missing")) then "cleanup_plan_quality" else empty end),
        (if ($blockers | index("cleanup_plan_selector_missing")) then "cleanup_selector" else empty end),
        (if ($preflightStatus == "payload_preflight_ready") and $readinessSkipped then "dry_run_smoke_summary" else empty end),
        (if (($readinessSkipped | not) and ((($readinessStatus == "ready_for_operator_live_fixture") or ($readinessStatus == "live_fixture_recorded")) | not)) then "dry_run_readiness_evidence" else empty end)
      ] | unique
    ) as $missingFacts
  | (
      if $status == "live_fixture_recorded" then [
        {
          id: "review_live_fixture_evidence",
          command: "ZOHO_CRM_FIXTURE_SUMMARY_FILE=<smoke-summary.json> ops/scripts/crm_fixture_operator_packet.sh",
          purpose: "review the redacted recorded live fixture evidence packet",
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
          purpose: "operator-only live fixture approval after reviewing payload, cleanup, and dry-run evidence",
          writesZohoData: true,
          dryRunOnly: false,
          agentMayExecute: false,
          requiresOperatorInput: true,
          requiresExplicitOperatorApproval: true,
          operatorOnly: true
        }
      ]
      elif $status == "payload_preflight_ready" then [
        {
          id: "run_crm_fixture_live_smoke_dry_run",
          command: "ZOHO_CRM_FIXTURE_PAYLOAD_FILE=<copied-fixture-payload.json> ZOHO_CRM_FIXTURE_CLEANUP_PLAN=<cleanup-plan> ops/scripts/crm_fixture_live_smoke.sh",
          purpose: "run the CRM fixture smoke in dry-run mode and collect a redacted summary",
          writesZohoData: false,
          dryRunOnly: true,
          agentMayExecute: true,
          requiresOperatorInput: true,
          requiresExplicitOperatorApproval: false,
          operatorOnly: false
        }
      ]
      elif ($blockers | index("payload_file_required")) or ($blockers | index("payload_file_missing")) then [
        {
          id: "provide_fixture_payload_file",
          command: "ZOHO_CRM_FIXTURE_PAYLOAD_FILE=<copied-fixture-payload.json> ZOHO_CRM_FIXTURE_CLEANUP_PLAN=<cleanup-plan> ops/scripts/crm_fixture_operator_packet.sh",
          purpose: "rerun the no-write packet after providing a copied dedicated fixture payload",
          writesZohoData: false,
          dryRunOnly: true,
          agentMayExecute: true,
          requiresOperatorInput: true,
          requiresExplicitOperatorApproval: false,
          operatorOnly: false
        }
      ]
      elif ($blockers | index("cleanup_plan_missing")) then [
        {
          id: "provide_cleanup_plan",
          command: "ZOHO_CRM_FIXTURE_PAYLOAD_FILE=<copied-fixture-payload.json> ZOHO_CRM_FIXTURE_CLEANUP_PLAN=<cleanup-plan> ops/scripts/crm_fixture_operator_packet.sh",
          purpose: "rerun the no-write packet after adding a cleanup plan with a selector",
          writesZohoData: false,
          dryRunOnly: true,
          agentMayExecute: true,
          requiresOperatorInput: true,
          requiresExplicitOperatorApproval: false,
          operatorOnly: false
        }
      ]
      elif ($blockers | index("cleanup_plan_too_short")) or ($blockers | index("cleanup_plan_action_missing")) or ($blockers | index("cleanup_plan_target_missing")) or ($blockers | index("cleanup_plan_selector_missing")) then [
        {
          id: "improve_cleanup_plan",
          command: "ZOHO_CRM_FIXTURE_PAYLOAD_FILE=<copied-fixture-payload.json> ZOHO_CRM_FIXTURE_CLEANUP_PLAN=<cleanup-plan-with-fixture-selector> ops/scripts/crm_fixture_operator_packet.sh",
          purpose: "rerun the no-write packet after improving cleanup action, target, and selector specificity",
          writesZohoData: false,
          dryRunOnly: true,
          agentMayExecute: true,
          requiresOperatorInput: true,
          requiresExplicitOperatorApproval: false,
          operatorOnly: false
        }
      ]
      else [
        {
          id: "fix_blockers",
          command: "ZOHO_CRM_FIXTURE_PAYLOAD_FILE=<copied-fixture-payload.json> ZOHO_CRM_FIXTURE_CLEANUP_PLAN=<cleanup-plan> ops/scripts/crm_fixture_operator_packet.sh",
          purpose: "fix the reported blockers and rerun the no-write packet",
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
  | {
      schemaVersion: 1,
      kind: "crm_fixture_operator_packet",
      runId: $runId,
      checkedAt: $checkedAt,
      status: $status,
      blockers: ($blockers | unique),
      reportFiles: {
        packet: $packetFile,
        payloadPreflight: $preflightFile,
        dryRunReadiness: (if $readinessSkipped then null else $readinessFile end),
        smokeSummary: $summaryFile
      },
      reportsReady: {
        packet: true,
        payloadPreflight: true,
        dryRunReadiness: ($readinessSkipped | not),
        smokeSummary: ($summaryFile != null)
      },
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
      operatorReview: {
        readyFacts: $readyFacts,
        missingFacts: $missingFacts,
        nextCommands: $nextCommands,
        cleanupSelectorTypes: ($preflightReport.cleanup.selectorTypes // []),
        cleanupSelectorTypeCount: (($preflightReport.cleanup.selectorTypes // []) | length),
        liveApproval: {
          summaryFileReady: (($summaryFile != null) and ($readinessSkipped | not)),
          dryRunReadinessReady: (($readinessStatus == "ready_for_operator_live_fixture") or ($readinessStatus == "live_fixture_recorded")),
          fixtureEvidenceReady: ($readinessReport.operatorReview.liveApproval.fixtureEvidenceReady // false),
          payloadDigestPresent: ($readinessReport.summary.payloadDigestPresent // (($readinessReport.summary.payloadDigest // null) != null)),
          idempotencyKeyPresent: ($readinessReport.summary.idempotencyKeyPresent // false),
          requiredApprovalPresent: ($readinessReport.summary.requiredApprovalPresent // false),
          placeholderEmailCountZero: (($readinessReport.summary.payloadTemplatePlaceholders.emailCount // null) == 0),
          commandPreviewUsesPlaceholders: true,
          writesZohoData: ($status == "ready_for_operator_live_fixture"),
          agentMayExecute: false,
          agentMayExecuteLiveFixture: false,
          agentMayRunNormalUpsertExecute: false,
          operatorOnly: ($status == "ready_for_operator_live_fixture"),
          requiresExplicitOperatorApproval: ($status == "ready_for_operator_live_fixture")
        },
        redaction: {
          rawPayloadStored: false,
          rawFieldValuesStored: false,
          rawEmailStored: false,
          rawCleanupPlanStored: false,
          rawSelectorValuesStored: false,
          rawRequiredApprovalStored: false,
          rawIdempotencyKeyStored: false
        }
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
