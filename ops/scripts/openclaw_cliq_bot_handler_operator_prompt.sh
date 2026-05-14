#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
JQ_BIN="${JQ_BIN:-jq}"

RUN_ID="${ZOHO_CLIQ_HANDLER_OPERATOR_PROMPT_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT_DIR="${ZOHO_CLIQ_HANDLER_OPERATOR_PROMPT_REPORT_DIR:-"$ROOT/tests/auto_pilot/reports"}"
PROMPT_FILE="${ZOHO_CLIQ_HANDLER_OPERATOR_PROMPT_FILE:-"$REPORT_DIR/openclaw_cliq_bot_handler_operator_prompt_$RUN_ID.json"}"
HANDLER_PACKET_SOURCE_FILE="${ZOHO_CLIQ_HANDLER_OPERATOR_PROMPT_HANDLER_PACKET_FILE:-}"
HANDLER_PACKET_FILE="${HANDLER_PACKET_SOURCE_FILE:-"$REPORT_DIR/openclaw_cliq_handler_trigger_packet_$RUN_ID.json"}"
PUBLIC_WEBHOOK_URL="${ZOHO_CLIQ_PUBLIC_WEBHOOK_URL:-}"

emit_error() {
  local error="$1"
  printf '{"schemaVersion":1,"kind":"openclaw_cliq_bot_handler_operator_prompt","runId":"%s","checkedAt":"%s","status":"error","error":"%s"}\n' "$RUN_ID" "$CHECKED_AT" "$error"
}

json_basename() {
  local path="${1:-}"
  if [[ -z "$path" ]]; then
    "$JQ_BIN" -n 'null'
  else
    "$JQ_BIN" -n --arg value "$(basename "$path")" '$value'
  fi
}

OUTPUT_FORMAT="${ZOHO_CLIQ_HANDLER_OPERATOR_PROMPT_FORMAT:-json}"
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
Usage: ops/scripts/openclaw_cliq_bot_handler_operator_prompt.sh [--json|--md]

Emits JSON by default. Use --md to print a compact operator handoff for fixing
the Zoho Bot Message Handler trigger path. The script is read-only and never
runs a live Bot probe.
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

HANDLER_PACKET_EXIT=0
HANDLER_PACKET_RAN=false
if [[ -z "$HANDLER_PACKET_SOURCE_FILE" ]]; then
  HANDLER_PACKET_RAN=true
  ZOHO_CLIQ_HANDLER_PACKET_RUN_ID="$RUN_ID" \
  ZOHO_CLIQ_HANDLER_PACKET_REPORT_DIR="$REPORT_DIR" \
  ZOHO_CLIQ_HANDLER_PACKET_FILE="$HANDLER_PACKET_FILE" \
  ZOHO_CLIQ_HANDLER_TARGETS="${ZOHO_CLIQ_HANDLER_TARGETS:-message}" \
    "$ROOT/ops/scripts/openclaw_cliq_handler_trigger_packet.sh" \
    >"$REPORT_DIR/openclaw_cliq_bot_handler_operator_prompt_${RUN_ID}_handler.stdout" \
    2>"$REPORT_DIR/openclaw_cliq_bot_handler_operator_prompt_${RUN_ID}_handler.stderr" || HANDLER_PACKET_EXIT=$?
fi

if [[ ! -f "$HANDLER_PACKET_FILE" ]]; then
  emit_error "handler_trigger_packet_missing"
  exit 2
fi

PROMPT_BASENAME="$(json_basename "$PROMPT_FILE")"
HANDLER_PACKET_BASENAME="$(json_basename "$HANDLER_PACKET_FILE")"

PAYLOAD="$("$JQ_BIN" -n \
  --arg runId "$RUN_ID" \
  --arg checkedAt "$CHECKED_AT" \
  --argjson promptFile "$PROMPT_BASENAME" \
  --argjson handlerPacketFile "$HANDLER_PACKET_BASENAME" \
  --argjson handlerPacketExit "$HANDLER_PACKET_EXIT" \
  --argjson handlerPacketRan "$HANDLER_PACKET_RAN" \
  --arg publicWebhookUrl "$PUBLIC_WEBHOOK_URL" \
  --slurpfile packet "$HANDLER_PACKET_FILE" \
  '
  def mdline_request:
    "- `" + .id + "`: " + .summary
    + (if (.template // null) != null then " Template: `" + .template + "`." else "" end)
    + (if (.renderCommand // null) != null then " Render: `" + .renderCommand + "`." else "" end)
    + (if (.command // null) != null then " Command: `" + .command + "`." else "" end);

  ($packet[0] // {}) as $packet
  | ($packet.status // "missing") as $handlerStatus
  | ($packet.blockers // []) as $handlerBlockers
  | ($packet.handlers.directMessageRequirement // {}) as $directRequirement
  | [
      (if ($packet.kind // "") == "openclaw_cliq_handler_trigger_packet" then empty else "handler_trigger_packet_invalid" end),
      (if $handlerStatus == "error" then ($packet.error // "handler_trigger_packet_error") else empty end),
      (if $handlerStatus == "blocked" then $handlerBlockers[] else empty end)
    ] as $rawBlockers
  | ($rawBlockers | unique) as $blockers
  | ($handlerStatus == "handler_trigger_packet_ready" and ($blockers | length) == 0) as $ready
  | [
      {
        id: "verify_public_callback",
        required: true,
        summary: "Confirm the public webhook route is reachable before changing Zoho handlers.",
        command: (
          if $publicWebhookUrl == "" then
            "ZOHO_CLIQ_PUBLIC_WEBHOOK_URL=https://<your-host>/webhooks/cliq ops/scripts/openclaw_cliq_public_callback_smoke.sh"
          else
            "ZOHO_CLIQ_PUBLIC_WEBHOOK_URL=" + $publicWebhookUrl + " ops/scripts/openclaw_cliq_public_callback_smoke.sh"
          end
        ),
        expectedStatus: "public_callback_verified",
        agentMayExecute: true
      },
      {
        id: "install_message_handler",
        required: true,
        summary: "Paste and save the Message Handler so plain direct Bot DMs can trigger OpenClaw.",
        zohoVisibleSignal: ($directRequirement.botDetailsVisibleSignal // "Handlers list includes Message Handler"),
        template: "docs/releases/OPENCLAW_CLIQ_BOT_HANDLER_TEMPLATES.md#message-handler",
        renderCommand: (
          if $publicWebhookUrl == "" then
            "ops/scripts/openclaw_cliq_bot_handler_template_render.sh --md --handlers message"
          else
            "ZOHO_CLIQ_PUBLIC_WEBHOOK_URL=" + $publicWebhookUrl + " ops/scripts/openclaw_cliq_bot_handler_template_render.sh --md --handlers message"
          end
        ),
        requiredReplyMode: "deluge_response",
        requiredReturn: "normalize webhook_response into webhook_text and return the clean response map",
        agentMayExecute: false
      },
      {
        id: "send_one_fresh_direct_message",
        required: true,
        summary: "After saving Message Handler, send exactly one fresh direct message to the Bot.",
        exampleMessage: "你好123456",
        agentMayExecute: false
      },
      {
        id: "rerun_no_response_packet",
        required: true,
        summary: "Run one short-window no-response diagnostic after the fresh message.",
        command: (
          if $publicWebhookUrl == "" then
            "ZOHO_CLIQ_INGRESS_LOOKBACK_SECONDS=600 ops/scripts/openclaw_cliq_bot_no_response_packet.sh"
          else
            "ZOHO_CLIQ_PUBLIC_WEBHOOK_URL=" + $publicWebhookUrl + " ZOHO_CLIQ_INGRESS_LOOKBACK_SECONDS=600 ops/scripts/openclaw_cliq_bot_no_response_packet.sh"
          end
        ),
        expectedGoodStatus: "ingress_active",
        expectedHandlerProblemCode: "zoho_bot_handler_not_posting",
        agentMayExecuteAfterFreshOperatorMessage: true
      }
    ] as $requests
  | ([
      "### OpenClaw Cliq Bot handler handoff",
      "",
      "Status: `" + (if $ready then "handler_operator_prompt_ready" else "blocked" end) + "`.",
      "",
      "Why this matters: direct Bot DMs trigger Zoho **Message Handler**. Mention Handler alone handles @mentions/channel contexts and can make another account look ignored.",
      "",
      "Actions:"
    ] + ($requests | map(mdline_request))
      + [
          "",
          "A delayed literal `received` is only a Deluge ACK; the expected final answer is normalized from `webhook_response` into a clean `response.text` map in `reply_mode=deluge_response`.",
          "",
          "Safety: this handoff stores no raw webhook payloads, message bodies, reply bodies, local paths, or secrets."
        ]) as $markdownLines
  | {
      schemaVersion: 1,
      kind: "openclaw_cliq_bot_handler_operator_prompt",
      runId: $runId,
      checkedAt: $checkedAt,
      status: (if $ready then "handler_operator_prompt_ready" else "blocked" end),
      blockers: $blockers,
      handlerTrigger: {
        status: $handlerStatus,
        nextAction: ($packet.nextAction // null),
        reportFile: $handlerPacketFile,
        ranHandlerPacket: $handlerPacketRan,
        commandExit: $handlerPacketExit,
        directMessageRequirement: $directRequirement,
        delugeContract: ($packet.delugeContract // {})
      },
      requestCount: ($requests | length),
      requestIds: ($requests | map(.id)),
      requests: $requests,
      messageMarkdown: ($markdownLines | join("\n")),
      redaction: {
        rawWebhookPayloadStored: false,
        rawMessageBodyStored: false,
        rawCliqReplyBodyStored: false,
        responseBodyStored: false,
        secretsStored: false,
        secretValueStored: false,
        localPathsStored: false
      },
      reportFiles: {
        operatorPrompt: $promptFile,
        handlerTriggerPacket: $handlerPacketFile
      },
      nextAction: (
        if $ready then "send_handler_operator_prompt"
        elif ($blockers | index("public_webhook_url_missing")) then "set_public_webhook_url"
        elif ($blockers | length) > 0 then "fix_handler_trigger_packet_blockers"
        else "inspect_handler_trigger_packet"
        end
      )
    }
  ')"

printf '%s\n' "$PAYLOAD" >"$PROMPT_FILE"
if [[ "$OUTPUT_FORMAT" == "markdown" ]]; then
  "$JQ_BIN" -r '.messageMarkdown' "$PROMPT_FILE"
else
  printf '%s\n' "$PAYLOAD"
fi

if [[ "$("$JQ_BIN" -r '.status' "$PROMPT_FILE")" != "handler_operator_prompt_ready" ]]; then
  exit 1
fi
