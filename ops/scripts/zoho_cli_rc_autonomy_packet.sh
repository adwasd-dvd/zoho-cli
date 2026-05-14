#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
JQ_BIN="${JQ_BIN:-jq}"

RUN_ID="${ZOHO_CLI_RC_AUTONOMY_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT_DIR="${ZOHO_CLI_RC_AUTONOMY_REPORT_DIR:-"$ROOT/tests/auto_pilot/reports"}"
PACKET_FILE="${ZOHO_CLI_RC_AUTONOMY_FILE:-"$REPORT_DIR/zoho_cli_rc_autonomy_packet_$RUN_ID.json"}"
CLIQ_DECISION_SOURCE_FILE="${ZOHO_CLI_RC_AUTONOMY_CLIQ_DECISION_SOURCE_FILE:-}"
CRM_AGENT_NEXT_SOURCE_FILE="${ZOHO_CLI_RC_AUTONOMY_CRM_AGENT_NEXT_SOURCE_FILE:-}"
CLIQ_DECISION_FILE="${CLIQ_DECISION_SOURCE_FILE:-"$REPORT_DIR/openclaw_cliq_rc_operator_decision_packet_$RUN_ID.json"}"
CRM_AGENT_NEXT_FILE="${CRM_AGENT_NEXT_SOURCE_FILE:-"$REPORT_DIR/crm_fixture_agent_next_command_$RUN_ID.json"}"
BOT_HANDLER_REQUEST_MODE="${ZOHO_CLI_RC_AUTONOMY_INCLUDE_BOT_HANDLER_REQUEST:-auto}"
BOT_HANDLER_REQUEST_MODE_NORMALIZED="$(printf '%s' "$BOT_HANDLER_REQUEST_MODE" | tr '[:upper:]' '[:lower:]')"
case "$BOT_HANDLER_REQUEST_MODE_NORMALIZED" in
  1|true|on|yes|force|forced|always)
    BOT_HANDLER_REQUEST_ENABLED=true
    ;;
  0|false|off|no)
    BOT_HANDLER_REQUEST_ENABLED=false
    ;;
  auto|"")
    # The real oldsix老六 Message Handler path is operator-confirmed working.
    # Keep the handler-save request available only as an explicit debug/forced
    # mode so normal RC autonomy does not keep asking for a stale Zoho UI step.
    BOT_HANDLER_REQUEST_ENABLED=false
    ;;
  *)
    BOT_HANDLER_REQUEST_ENABLED=false
    ;;
esac
BOT_HANDLER_PUBLIC_WEBHOOK_URL="${ZOHO_CLIQ_PUBLIC_WEBHOOK_URL:-}"

emit_error() {
  local error="$1"
  printf '{"schemaVersion":1,"kind":"zoho_cli_rc_autonomy_packet","runId":"%s","checkedAt":"%s","status":"error","error":"%s"}\n' "$RUN_ID" "$CHECKED_AT" "$error"
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

CLIQ_DECISION_EXIT=0
CLIQ_DECISION_RAN=false
if [[ -z "$CLIQ_DECISION_SOURCE_FILE" ]]; then
  CLIQ_DECISION_RAN=true
  ZOHO_CLI_RC_AUTONOMY_NESTED=1 \
  OPENCLAW_CLIQ_DECISION_PACKET_RUN_ID="$RUN_ID" \
  OPENCLAW_CLIQ_DECISION_PACKET_REPORT_DIR="$REPORT_DIR" \
  OPENCLAW_CLIQ_DECISION_PACKET_FILE="$CLIQ_DECISION_FILE" \
    "$ROOT/ops/scripts/openclaw_cliq_rc_operator_decision_packet.sh" \
    >"$REPORT_DIR/zoho_cli_rc_autonomy_packet_${RUN_ID}_cliq_decision.stdout" \
    2>"$REPORT_DIR/zoho_cli_rc_autonomy_packet_${RUN_ID}_cliq_decision.stderr" || CLIQ_DECISION_EXIT=$?
fi

CRM_AGENT_NEXT_EXIT=0
CRM_AGENT_NEXT_RAN=false
if [[ -z "$CRM_AGENT_NEXT_SOURCE_FILE" ]]; then
  CRM_AGENT_NEXT_RAN=true
  ZOHO_CRM_FIXTURE_AGENT_NEXT_RUN_ID="$RUN_ID" \
  ZOHO_CRM_FIXTURE_AGENT_NEXT_REPORT_DIR="$REPORT_DIR" \
  ZOHO_CRM_FIXTURE_AGENT_NEXT_FILE="$CRM_AGENT_NEXT_FILE" \
    "$ROOT/ops/scripts/crm_fixture_agent_next_command.sh" \
    >"$REPORT_DIR/zoho_cli_rc_autonomy_packet_${RUN_ID}_crm_agent_next.stdout" \
    2>"$REPORT_DIR/zoho_cli_rc_autonomy_packet_${RUN_ID}_crm_agent_next.stderr" || CRM_AGENT_NEXT_EXIT=$?
fi

if [[ ! -f "$CLIQ_DECISION_FILE" ]]; then
  emit_error "cliq_decision_packet_missing"
  exit 2
fi
if [[ ! -f "$CRM_AGENT_NEXT_FILE" ]]; then
  emit_error "crm_agent_next_command_missing"
  exit 2
fi

PACKET_BASENAME="$(json_basename "$PACKET_FILE")"
CLIQ_DECISION_BASENAME="$(json_basename "$CLIQ_DECISION_FILE")"
CRM_AGENT_NEXT_BASENAME="$(json_basename "$CRM_AGENT_NEXT_FILE")"

PAYLOAD="$("$JQ_BIN" -n \
  --arg runId "$RUN_ID" \
  --arg checkedAt "$CHECKED_AT" \
  --argjson packetFile "$PACKET_BASENAME" \
  --argjson cliqDecisionFile "$CLIQ_DECISION_BASENAME" \
  --argjson crmAgentNextFile "$CRM_AGENT_NEXT_BASENAME" \
  --argjson cliqDecisionExit "$CLIQ_DECISION_EXIT" \
  --argjson cliqDecisionRan "$CLIQ_DECISION_RAN" \
  --argjson crmAgentNextExit "$CRM_AGENT_NEXT_EXIT" \
  --argjson crmAgentNextRan "$CRM_AGENT_NEXT_RAN" \
  --argjson botHandlerRequestEnabled "$BOT_HANDLER_REQUEST_ENABLED" \
  --arg botHandlerPublicWebhookUrl "$BOT_HANDLER_PUBLIC_WEBHOOK_URL" \
  --slurpfile cliq "$CLIQ_DECISION_FILE" \
  --slurpfile crm "$CRM_AGENT_NEXT_FILE" \
  '
  ($cliq[0] // {}) as $cliq
  | ($crm[0] // {}) as $crm
  | ($cliq.status // "missing") as $cliqStatus
  | ($crm.status // "missing") as $crmStatus
  | (($crm.safety.nextCommandAllowedForAgent // false) == true) as $crmNextAllowed
  | (($crm.operatorReview.nextAgentCommand // null)) as $crmNextCommand
  | ($botHandlerRequestEnabled and $cliqStatus == "awaiting_operator_publish_path") as $botHandlerRequestNeeded
  | (
      if ($botHandlerPublicWebhookUrl // "") == ""
      then "<public-webhook-url>"
      else $botHandlerPublicWebhookUrl
      end
    ) as $botHandlerCommandWebhookUrl
  | [
      (if ($cliq.kind // "") == "openclaw_cliq_rc_operator_decision_packet" then empty else "cliq_decision_packet_invalid" end),
      (if ($crm.kind // "") == "crm_fixture_agent_next_command" then empty else "crm_agent_next_command_invalid" end),
      (if $cliqStatus == "error" then ($cliq.error // "cliq_decision_packet_error") else empty end),
      (if $crmStatus == "error" then ($crm.error // "crm_agent_next_command_error") else empty end),
      (if $cliqStatus == "blocked" then ($cliq.blockers // ["cliq_decision_packet_blocked"])[] else empty end),
      (if $crmStatus == "blocked" then ($crm.packet.blockers // ["crm_fixture_packet_blocked"])[] else empty end),
      (if $crmStatus == "agent_command_not_allowlisted" then "crm_agent_command_not_allowlisted" else empty end)
    ] as $rawBlockers
  | ($rawBlockers | unique) as $blockers
  | (
      if ($blockers | length) != 0 then "blocked"
      elif $crmStatus == "agent_next_command_ready" and $crmNextAllowed then "agent_next_command_ready"
      elif $cliqStatus == "operator_publish_selection_ready" then "stop_before_operator_publish"
      elif $crmStatus == "stop_before_operator_live_fixture" then "stop_before_operator_live_fixture"
      elif $crmStatus == "operator_input_required" or $botHandlerRequestNeeded then "operator_input_required"
      elif $cliqStatus == "awaiting_operator_publish_path" then "operator_publish_path_required"
      else "no_agent_command"
      end
    ) as $status
  | {
      schemaVersion: 1,
      kind: "zoho_cli_rc_autonomy_packet",
      runId: $runId,
      checkedAt: $checkedAt,
      status: $status,
      blockers: $blockers,
      lanes: {
        openclawCliq: {
          status: $cliqStatus,
          nextAction: ($cliq.nextAction // null),
          selectedPublishPath: ($cliq.selectedPublishPath // null),
          blockers: ($cliq.blockers // []),
          reportsReady: ($cliq.reportsReady // {}),
          verifiedStatuses: ($cliq.verifiedStatuses // {}),
          package: ($cliq.package // {}),
          artifact: ($cliq.artifact // {}),
          botHandlerOperatorActionRequired: $botHandlerRequestNeeded,
          safety: ($cliq.safety // {})
        },
        crmFixture: {
          status: $crmStatus,
          nextAction: ($crm.nextAction // null),
          packetStatus: ($crm.packet.status // null),
          readyFacts: ($crm.operatorReview.readyFacts // []),
          missingFacts: ($crm.operatorReview.missingFacts // []),
          nextAgentExecutableCommandId: ($crm.operatorReview.nextAgentExecutableCommandId // null),
          nextAgentCommand: $crmNextCommand,
          agentExecutableCommandAllowed: ($crm.operatorReview.agentExecutableCommandAllowed // false),
          safety: ($crm.safety // {})
        }
      },
      recommendedAgentCommand: (
        if $status == "agent_next_command_ready" then $crmNextCommand else null end
      ),
      operatorInputsNeeded: {
        openclawCliqPublishPath: ($cliqStatus == "awaiting_operator_publish_path"),
        openclawCliqBotMessageHandler: $botHandlerRequestNeeded,
        crmFixtureFacts: (
          if $crmStatus == "operator_input_required"
          then ($crm.operatorReview.missingFacts // [])
          else []
          end
        )
      },
      operatorActionRequests: (
        [
          (
            if $botHandlerRequestNeeded then {
              id: "save_openclaw_cliq_bot_message_handler",
              lane: "openclawCliqBot",
              required: true,
              inputKind: "zoho_bot_handler_save",
              template: "docs/releases/OPENCLAW_CLIQ_BOT_HANDLER_TEMPLATES.md#message-handler",
              guidance: "Render the no-secret Message Handler Deluge block, paste it into the oldsix老六 Bot Message Handler, save it, then send exactly one fresh direct Bot message before rerunning diagnostics.",
              commandPreview: ("ZOHO_CLIQ_PUBLIC_WEBHOOK_URL=" + $botHandlerCommandWebhookUrl + " ops/scripts/openclaw_cliq_bot_handler_template_render.sh --md --handlers message"),
              followUpCommandPreview: "ZOHO_CLIQ_INGRESS_LOOKBACK_SECONDS=600 ops/scripts/openclaw_cliq_bot_no_response_packet.sh",
              zohoVisibleSignal: "The same Bot chat should show the OpenClaw reply from the handler response, not only a delayed literal Deluge acknowledgement such as `received`.",
              unblocks: "openclaw_cliq_bot_direct_dm_recheck",
              agentMayExecute: false,
              requiresExplicitOperatorApproval: false,
              redaction: {
                rawSecretsStored: false,
                rawMessageBodyStored: false,
                rawReplyTextStored: false,
                rawLocalPathsStored: false
              }
            } else empty end
          ),
          (
            if $cliqStatus == "awaiting_operator_publish_path" then {
              id: "select_openclaw_cliq_publish_path",
              lane: "openclawCliq",
              required: true,
              inputKind: "choice",
              allowedValues: [
                "local_operator_rc",
                "npm_rc_publish",
                "github_release_artifact"
              ],
              commandPreview: "OPENCLAW_CLIQ_OPERATOR_PUBLISH_PATH=<choice> ops/scripts/openclaw_cliq_rc_operator_decision_packet.sh",
              unblocks: "openclaw_cliq_operator_publish_selection_review",
              agentMayExecute: false,
              requiresExplicitOperatorApproval: true,
              redaction: {
                rawSecretsStored: false,
                rawLocalPathsStored: false
              }
            } else empty end
          ),
          (
            if $cliqStatus == "operator_publish_selection_ready" then {
              id: "review_execute_selected_openclaw_cliq_publish_path",
              lane: "openclawCliq",
              required: true,
              inputKind: "operator_review",
              selectedPublishPath: ($cliq.selectedPublishPath // null),
              unblocks: "operator_publish_execution_review",
              agentMayExecute: false,
              requiresExplicitOperatorApproval: true,
              redaction: {
                rawSecretsStored: false,
                rawLocalPathsStored: false
              }
            } else empty end
          )
        ]
        + (
          if $crmStatus == "operator_input_required" then
            [
              ($crm.operatorReview.missingFacts // [])[]
              | if . == "fixture_payload_file" then {
                  id: "provide_crm_fixture_payload_file",
                  lane: "crmFixture",
                  required: true,
                  inputKind: "file",
                  template: "docs/releases/CRM_V0_5_FIXTURE_PAYLOAD_TEMPLATE.json",
                  guidance: "Copy the template outside the repo and replace placeholder values with a dedicated test fixture before any live gate.",
                  commandPreview: "ZOHO_CRM_FIXTURE_PAYLOAD_FILE=<copied-payload-file> ZOHO_CRM_FIXTURE_CLEANUP_PLAN=<cleanup-plan> ops/scripts/crm_fixture_agent_next_command.sh",
                  unblocks: "crm_fixture_agent_next_command_recheck",
                  agentMayExecute: false,
                  requiresExplicitOperatorApproval: false,
                  redaction: {
                    rawPayloadStored: false,
                    rawEmailStored: false,
                    rawLocalPathsStored: false
                  }
                }
                elif . == "cleanup_plan" then {
                  id: "provide_crm_fixture_cleanup_plan",
                  lane: "crmFixture",
                  required: true,
                  inputKind: "text",
                  template: "docs/releases/CRM_V0_5_FIXTURE_CLEANUP_PLAN_TEMPLATE.md",
                  guidance: "Provide a cleanup plan with an action, target, and selector category such as fixture email, record id, duplicate field, idempotency key, or payload digest.",
                  commandPreview: "ZOHO_CRM_FIXTURE_PAYLOAD_FILE=<copied-payload-file> ZOHO_CRM_FIXTURE_CLEANUP_PLAN=<cleanup-plan> ops/scripts/crm_fixture_agent_next_command.sh",
                  unblocks: "crm_fixture_agent_next_command_recheck",
                  agentMayExecute: false,
                  requiresExplicitOperatorApproval: false,
                  redaction: {
                    rawCleanupPlanStored: false,
                    rawSelectorValuesStored: false
                  }
                }
                else {
                  id: ("provide_crm_fixture_" + .),
                  lane: "crmFixture",
                  required: true,
                  inputKind: "operator_input",
                  fact: .,
                  unblocks: "crm_fixture_agent_next_command_recheck",
                  agentMayExecute: false,
                  requiresExplicitOperatorApproval: false,
                  redaction: {
                    rawValuesStored: false
                  }
                }
                end
            ]
          else []
          end
        )
      ),
      safety: {
        noPublishOrTagOrReleasePerformed: true,
        noZohoLiveWritePerformed: true,
        normalCrmUpsertExecuteBlocked: true,
        agentMayPublish: false,
        agentMayTag: false,
        agentMayCreateGithubRelease: false,
        agentMayFillExpectedIntegrity: false,
        agentMayExecuteCliqSelectedPath: false,
        agentMayRunCrmNextCommand: ($status == "agent_next_command_ready"),
        crmNextCommandAllowedForAgent: ($status == "agent_next_command_ready"),
        crmNextCommandAllowlistedDryRunLocal: $crmNextAllowed
      },
      reportFiles: {
        autonomyPacket: $packetFile,
        cliqDecisionPacket: $cliqDecisionFile,
        crmAgentNextCommand: $crmAgentNextFile
      },
      commandExits: {
        cliqDecisionPacket: $cliqDecisionExit,
        crmAgentNextCommand: $crmAgentNextExit
      },
      commandsRan: {
        cliqDecisionPacket: $cliqDecisionRan,
        crmAgentNextCommand: $crmAgentNextRan
      },
      nextAction: (
        if $status == "agent_next_command_ready" then "execute_crm_next_agent_command"
        elif $status == "stop_before_operator_publish" then "stop_for_operator_publish_execution"
        elif $status == "stop_before_operator_live_fixture" then "stop_for_operator_live_fixture_approval"
        elif $status == "operator_input_required" then "collect_operator_input_or_select_publish_path"
        elif $status == "operator_publish_path_required" then "operator_select_openclaw_cliq_publish_path"
        elif $status == "blocked" then "fix_autonomy_packet_blockers"
        else "inspect_rc_autonomy_packet"
        end
      )
    }
    | . + {
      nextOperatorActionId: ((.operatorActionRequests[0].id) // null),
      nextOperatorActionRequest: ((.operatorActionRequests[0]) // null)
    }
  ')"

printf '%s\n' "$PAYLOAD" >"$PACKET_FILE"
printf '%s\n' "$PAYLOAD"

case "$("$JQ_BIN" -r '.status' "$PACKET_FILE")" in
  blocked|error)
    exit 1
    ;;
esac
