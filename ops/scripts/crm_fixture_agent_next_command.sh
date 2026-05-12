#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
JQ_BIN="${JQ_BIN:-jq}"

RUN_ID="${ZOHO_CRM_FIXTURE_AGENT_NEXT_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT_DIR="${ZOHO_CRM_FIXTURE_AGENT_NEXT_REPORT_DIR:-"$ROOT/tests/auto_pilot/reports"}"
AGENT_NEXT_FILE="${ZOHO_CRM_FIXTURE_AGENT_NEXT_FILE:-"$REPORT_DIR/crm_fixture_agent_next_command_$RUN_ID.json"}"
PACKET_SOURCE_FILE="${ZOHO_CRM_FIXTURE_PACKET_SOURCE_FILE:-}"
PACKET_FILE="${PACKET_SOURCE_FILE:-"$REPORT_DIR/crm_fixture_operator_packet_$RUN_ID.json"}"

emit_error() {
  local error="$1"
  printf '{"schemaVersion":1,"kind":"crm_fixture_agent_next_command","runId":"%s","checkedAt":"%s","status":"error","error":"%s"}\n' "$RUN_ID" "$CHECKED_AT" "$error"
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

PACKET_EXIT=0
PACKET_RAN=false
if [[ -z "$PACKET_SOURCE_FILE" ]]; then
  PACKET_RAN=true
  ZOHO_CRM_FIXTURE_PACKET_RUN_ID="$RUN_ID" \
  ZOHO_CRM_FIXTURE_PACKET_REPORT_DIR="$REPORT_DIR" \
  ZOHO_CRM_FIXTURE_PACKET_FILE="$PACKET_FILE" \
    "$ROOT/ops/scripts/crm_fixture_operator_packet.sh" \
    >"$REPORT_DIR/crm_fixture_agent_next_command_${RUN_ID}_packet.stdout" \
    2>"$REPORT_DIR/crm_fixture_agent_next_command_${RUN_ID}_packet.stderr" || PACKET_EXIT=$?
fi

if [[ ! -f "$PACKET_FILE" ]]; then
  emit_error "crm_fixture_operator_packet_missing"
  exit 2
fi

PACKET_BASENAME="$(json_basename "$PACKET_FILE")"
AGENT_NEXT_BASENAME="$(json_basename "$AGENT_NEXT_FILE")"

PAYLOAD="$("$JQ_BIN" -n \
  --arg runId "$RUN_ID" \
  --arg checkedAt "$CHECKED_AT" \
  --argjson packetExit "$PACKET_EXIT" \
  --argjson packetRan "$PACKET_RAN" \
  --argjson packetFile "$PACKET_BASENAME" \
  --argjson agentNextFile "$AGENT_NEXT_BASENAME" \
  --slurpfile packet "$PACKET_FILE" \
  '
  ($packet[0] // {}) as $packet
  | ($packet.status // "missing") as $packetStatus
  | ($packet.operatorReview.agentAutomation // {}) as $automation
  | ($packet.operatorReview.actionBoundary // {}) as $boundary
  | ($automation.nextAgentCommand // null) as $nextAgentCommand
  | (($automation.agentMayExecuteNextCommand // false) == true) as $agentMayExecuteNextCommand
  | (($nextAgentCommand != null) and (($nextAgentCommand.requiresOperatorInput // false) == true)) as $operatorInputRequired
  | (($nextAgentCommand != null) and (($nextAgentCommand.writesZohoData // false) == true)) as $nextCommandWritesZoho
  | (($nextAgentCommand != null) and (($nextAgentCommand.requiresExplicitOperatorApproval // false) == true)) as $nextCommandRequiresApproval
  | (($boundary.writesZohoDataAny // false) == true) as $writesZohoDataAny
  | (($boundary.requiresExplicitOperatorApprovalAny // false) == true) as $requiresExplicitOperatorApprovalAny
  | (($boundary.operatorOnlyAny // false) == true) as $operatorOnlyAny
  | (($automation.stopCommandIds // []) | length) as $stopCommandCount
  | (
      if ($packet.kind // "") != "crm_fixture_operator_packet" then "error"
      elif ($packetStatus == "ready_for_operator_live_fixture")
        or $writesZohoDataAny
        or $requiresExplicitOperatorApprovalAny
        or $operatorOnlyAny
        or ($stopCommandCount > 0)
        or $nextCommandWritesZoho
        or $nextCommandRequiresApproval
      then "stop_before_operator_live_fixture"
      elif $agentMayExecuteNextCommand and ($nextAgentCommand != null) and $operatorInputRequired then "operator_input_required"
      elif $agentMayExecuteNextCommand and ($nextAgentCommand != null) then "agent_next_command_ready"
      elif $packetStatus == "blocked" then "blocked"
      else "no_agent_command"
      end
    ) as $status
  | {
      schemaVersion: 1,
      kind: "crm_fixture_agent_next_command",
      runId: $runId,
      checkedAt: $checkedAt,
      status: $status,
      packet: {
        file: $packetFile,
        ranPacket: $packetRan,
        commandExit: $packetExit,
        status: $packetStatus,
        nextAction: ($packet.nextAction // null),
        blockers: ($packet.blockers // []),
        reportFiles: ($packet.reportFiles // {}),
        reportsReady: ($packet.reportsReady // {})
      },
      operatorReview: {
        readyFacts: ($packet.operatorReview.readyFacts // []),
        missingFacts: ($packet.operatorReview.missingFacts // []),
        nextAgentExecutableCommandId: ($automation.nextAgentExecutableCommandId // null),
        nextAgentCommand: $nextAgentCommand,
        operatorInputRequiredForNextAgentCommand: $operatorInputRequired,
        agentMayExecuteNextCommand: ($status == "agent_next_command_ready"),
        agentMayExecuteAfterOperatorInput: ($status == "operator_input_required"),
        stopCommandIds: ($automation.stopCommandIds // []),
        stopReason: ($automation.stopReason // null)
      },
      safety: {
        normalUpsertExecuteBlocked: true,
        agentMayRunNormalUpsertExecute: false,
        liveFixtureExecutionBlockedForAgent: true,
        writesZohoDataAny: $writesZohoDataAny,
        requiresExplicitOperatorApprovalAny: $requiresExplicitOperatorApprovalAny,
        operatorOnlyAny: $operatorOnlyAny,
        nextCommandWritesZohoData: $nextCommandWritesZoho,
        nextCommandRequiresExplicitOperatorApproval: $nextCommandRequiresApproval,
        redaction: {
          rawPayloadStored: false,
          rawFieldValuesStored: false,
          rawEmailStored: false,
          rawCleanupPlanStored: false,
          rawSelectorValuesStored: false,
          rawRequiredApprovalStored: false,
          rawIdempotencyKeyStored: false,
          localPathsStored: false
        }
      },
      reportFiles: {
        agentNextCommand: $agentNextFile,
        operatorPacket: $packetFile
      },
      nextAction: (
        if $status == "agent_next_command_ready" then "execute_next_agent_command"
        elif $status == "operator_input_required" then "collect_operator_input_for_next_agent_command"
        elif $status == "stop_before_operator_live_fixture" then "stop_for_operator_live_fixture_approval"
        elif $status == "blocked" then ($packet.nextAction // "fix_crm_fixture_packet_blockers")
        else "inspect_crm_fixture_operator_packet"
        end
      )
    }
  ')"

printf '%s\n' "$PAYLOAD" >"$AGENT_NEXT_FILE"
printf '%s\n' "$PAYLOAD"

if [[ "$("$JQ_BIN" -r '.status' "$AGENT_NEXT_FILE")" == "error" ]]; then
  exit 2
fi
