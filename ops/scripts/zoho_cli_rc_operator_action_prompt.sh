#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
JQ_BIN="${JQ_BIN:-jq}"

RUN_ID="${ZOHO_CLI_RC_OPERATOR_ACTION_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT_DIR="${ZOHO_CLI_RC_OPERATOR_ACTION_REPORT_DIR:-"$ROOT/tests/auto_pilot/reports"}"
PROMPT_FILE="${ZOHO_CLI_RC_OPERATOR_ACTION_FILE:-"$REPORT_DIR/zoho_cli_rc_operator_action_prompt_$RUN_ID.json"}"
AUTONOMY_SOURCE_FILE="${ZOHO_CLI_RC_OPERATOR_ACTION_AUTONOMY_SOURCE_FILE:-}"
AUTONOMY_FILE="${AUTONOMY_SOURCE_FILE:-"$REPORT_DIR/zoho_cli_rc_autonomy_packet_$RUN_ID.json"}"

emit_error() {
  local error="$1"
  printf '{"schemaVersion":1,"kind":"zoho_cli_rc_operator_action_prompt","runId":"%s","checkedAt":"%s","status":"error","error":"%s"}\n' "$RUN_ID" "$CHECKED_AT" "$error"
}

json_basename() {
  local path="${1:-}"
  if [[ -z "$path" ]]; then
    "$JQ_BIN" -n 'null'
  else
    "$JQ_BIN" -n --arg value "$(basename "$path")" '$value'
  fi
}

OUTPUT_FORMAT="${ZOHO_CLI_RC_OPERATOR_ACTION_FORMAT:-json}"
while (($#)); do
  case "$1" in
    --json)
      OUTPUT_FORMAT="json"
      ;;
    --md|--markdown)
      OUTPUT_FORMAT="markdown"
      ;;
    -h|--help)
      cat <<'USAGE'
Usage: ops/scripts/zoho_cli_rc_operator_action_prompt.sh [--json|--md]

Emits JSON by default. Use --md to print the redacted operator handoff
Markdown while still writing the JSON report file.
USAGE
      exit 0
      ;;
    *)
      emit_error "unknown_argument"
      exit 2
      ;;
  esac
  shift
done

case "$OUTPUT_FORMAT" in
  json|markdown)
    ;;
  *)
    emit_error "unsupported_output_format"
    exit 2
    ;;
esac

command -v "$JQ_BIN" >/dev/null 2>&1 || {
  emit_error "jq_required"
  exit 2
}

mkdir -p "$REPORT_DIR"

AUTONOMY_EXIT=0
AUTONOMY_RAN=false
if [[ -z "$AUTONOMY_SOURCE_FILE" ]]; then
  AUTONOMY_RAN=true
  ZOHO_CLI_RC_AUTONOMY_RUN_ID="$RUN_ID" \
  ZOHO_CLI_RC_AUTONOMY_REPORT_DIR="$REPORT_DIR" \
  ZOHO_CLI_RC_AUTONOMY_FILE="$AUTONOMY_FILE" \
    "$ROOT/ops/scripts/zoho_cli_rc_autonomy_packet.sh" \
    >"$REPORT_DIR/zoho_cli_rc_operator_action_prompt_${RUN_ID}_autonomy.stdout" \
    2>"$REPORT_DIR/zoho_cli_rc_operator_action_prompt_${RUN_ID}_autonomy.stderr" || AUTONOMY_EXIT=$?
fi

if [[ ! -f "$AUTONOMY_FILE" ]]; then
  emit_error "autonomy_packet_missing"
  exit 2
fi

PROMPT_BASENAME="$(json_basename "$PROMPT_FILE")"
AUTONOMY_BASENAME="$(json_basename "$AUTONOMY_FILE")"

PAYLOAD="$("$JQ_BIN" -n \
  --arg runId "$RUN_ID" \
  --arg checkedAt "$CHECKED_AT" \
  --argjson promptFile "$PROMPT_BASENAME" \
  --argjson autonomyFile "$AUTONOMY_BASENAME" \
  --argjson autonomyExit "$AUTONOMY_EXIT" \
  --argjson autonomyRan "$AUTONOMY_RAN" \
  --slurpfile autonomy "$AUTONOMY_FILE" \
  '
  def request_line:
    "- `" + (.id // "unknown_request") + "`"
    + " (" + (.lane // "unknown_lane") + ", " + (.inputKind // "unknown_input") + ")"
    + (if (.allowedValues // [] | length) > 0 then ": choose one of " + ((.allowedValues // []) | map("`" + . + "`") | join(", ")) else "" end)
    + (if (.template // null) != null then ": start from `" + .template + "`" else "" end)
    + (if (.guidance // null) != null then ": " + .guidance else "" end)
    + (if (.commandPreview // null) != null then " Recheck: `" + .commandPreview + "`." else "" end)
    + (if (.unblocks // null) != null then " Unlocks: `" + .unblocks + "`." else "" end);

  ($autonomy[0] // {}) as $packet
  | ($packet.status // "missing") as $autonomyStatus
  | ($packet.operatorActionRequests // []) as $requests
  | [
      (if ($packet.kind // "") == "zoho_cli_rc_autonomy_packet" then empty else "autonomy_packet_invalid" end),
      (if $autonomyStatus == "error" then ($packet.error // "autonomy_packet_error") else empty end),
      (if $autonomyStatus == "blocked" then ($packet.blockers // ["autonomy_packet_blocked"])[] else empty end)
    ] as $rawBlockers
  | ($rawBlockers | unique) as $blockers
  | (
      if ($blockers | length) != 0 then "blocked"
      elif ($requests | length) > 0 then "operator_action_prompt_ready"
      elif $autonomyStatus == "agent_next_command_ready" then "agent_next_command_ready"
      else "no_operator_action"
      end
    ) as $status
  | ([
      "### zoho-cli RC operator actions",
      "",
      "Status: `" + $status + "`.",
      "",
      "Needed inputs:"
    ] + ($requests | map(request_line))
      + [
          "",
          "Safety: agent execution remains disabled for publish/write boundaries; no raw secrets, payload values, cleanup text, or local paths are stored."
        ]) as $markdownLines
  | {
      schemaVersion: 1,
      kind: "zoho_cli_rc_operator_action_prompt",
      runId: $runId,
      checkedAt: $checkedAt,
      status: $status,
      blockers: $blockers,
      autonomy: {
        status: $autonomyStatus,
        nextAction: ($packet.nextAction // null),
        reportFile: $autonomyFile,
        ranAutonomyPacket: $autonomyRan,
        commandExit: $autonomyExit
      },
      requestCount: ($requests | length),
      requiredRequestCount: ($requests | map(select((.required // false) == true)) | length),
      requestIds: ($requests | map(.id // "unknown_request")),
      requests: $requests,
      messageMarkdown: (if ($requests | length) > 0 then ($markdownLines | join("\n")) else null end),
      safety: {
        noPublishOrTagOrReleasePerformed: true,
        noZohoLiveWritePerformed: true,
        normalCrmUpsertExecuteBlocked: true,
        agentMayExecutePromptRequests: false,
        agentMayPublish: false,
        agentMayTag: false,
        agentMayCreateGithubRelease: false,
        agentMayFillExpectedIntegrity: false,
        actionRequestsAgentExecutableAny: ($requests | any((.agentMayExecute // false) == true)),
        redaction: {
          rawSecretsStored: false,
          rawPayloadStored: false,
          rawCleanupPlanStored: false,
          rawLocalPathsStored: false
        }
      },
      reportFiles: {
        operatorActionPrompt: $promptFile,
        autonomyPacket: $autonomyFile
      },
      nextAction: (
        if $status == "operator_action_prompt_ready" then "send_operator_action_prompt"
        elif $status == "agent_next_command_ready" then "run_autonomy_recommended_agent_command"
        elif $status == "blocked" then "fix_autonomy_packet_blockers"
        else "inspect_rc_autonomy_packet"
        end
      )
    }
  ')"

printf '%s\n' "$PAYLOAD" >"$PROMPT_FILE"
if [[ "$OUTPUT_FORMAT" == "markdown" ]]; then
  "$JQ_BIN" -r '
    if .messageMarkdown != null then
      .messageMarkdown
    elif .status == "agent_next_command_ready" then
      "### zoho-cli RC agent command\n\nStatus: `agent_next_command_ready`.\n\nRead the JSON report before executing the recommended agent command."
    elif .status == "no_operator_action" then
      "### zoho-cli RC operator actions\n\nStatus: `no_operator_action`.\n\nNo operator action requests are present."
    else
      "### zoho-cli RC operator actions\n\nStatus: `" + (.status // "unknown") + "`.\n\nReview the JSON report for blockers."
    end
  ' "$PROMPT_FILE"
else
  printf '%s\n' "$PAYLOAD"
fi

case "$("$JQ_BIN" -r '.status' "$PROMPT_FILE")" in
  blocked|error)
    exit 1
    ;;
esac
