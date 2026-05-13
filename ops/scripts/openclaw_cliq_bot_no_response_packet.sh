#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
JQ_BIN="${JQ_BIN:-jq}"
RUN_ID="${ZOHO_CLIQ_BOT_PACKET_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT_DIR="${ZOHO_CLIQ_BOT_PACKET_REPORT_DIR:-"$ROOT/tests/auto_pilot/reports"}"
PACKET_FILE="${ZOHO_CLIQ_BOT_PACKET_FILE:-"$REPORT_DIR/openclaw_cliq_bot_no_response_packet_$RUN_ID.json"}"
PUBLIC_CALLBACK_SCRIPT="${ZOHO_CLIQ_PUBLIC_CALLBACK_SCRIPT:-"$ROOT/ops/scripts/openclaw_cliq_public_callback_smoke.sh"}"
INGRESS_SCRIPT="${ZOHO_CLIQ_INGRESS_DIAGNOSTIC_SCRIPT:-"$ROOT/ops/scripts/openclaw_cliq_live_ingress_diagnostic.sh"}"
HANDLER_TRIGGER_SCRIPT="${ZOHO_CLIQ_HANDLER_TRIGGER_SCRIPT:-"$ROOT/ops/scripts/openclaw_cliq_handler_trigger_packet.sh"}"
REQUIRE_PUBLIC_CALLBACK="${ZOHO_CLIQ_BOT_PACKET_REQUIRE_PUBLIC_CALLBACK:-0}"

emit_error() {
  local error="$1"
  printf '{"schemaVersion":1,"kind":"openclaw_cliq_bot_no_response_packet","runId":"%s","checkedAt":"%s","status":"error","error":"%s"}\n' "$RUN_ID" "$CHECKED_AT" "$error"
}

command -v "$JQ_BIN" >/dev/null 2>&1 || {
  emit_error "jq_required"
  exit 2
}

mkdir -p "$REPORT_DIR"

PUBLIC_CALLBACK_FILE="$REPORT_DIR/openclaw_cliq_bot_no_response_packet_${RUN_ID}_public_callback.json"
PUBLIC_CALLBACK_STDOUT="$REPORT_DIR/openclaw_cliq_bot_no_response_packet_${RUN_ID}_public_callback.stdout"
PUBLIC_CALLBACK_STDERR="$REPORT_DIR/openclaw_cliq_bot_no_response_packet_${RUN_ID}_public_callback.stderr"
INGRESS_FILE="$REPORT_DIR/openclaw_cliq_bot_no_response_packet_${RUN_ID}_ingress.json"
INGRESS_STDOUT="$REPORT_DIR/openclaw_cliq_bot_no_response_packet_${RUN_ID}_ingress.stdout"
INGRESS_STDERR="$REPORT_DIR/openclaw_cliq_bot_no_response_packet_${RUN_ID}_ingress.stderr"
HANDLER_TRIGGER_FILE="$REPORT_DIR/openclaw_cliq_bot_no_response_packet_${RUN_ID}_handler_trigger.json"
HANDLER_TRIGGER_STDOUT="$REPORT_DIR/openclaw_cliq_bot_no_response_packet_${RUN_ID}_handler_trigger.stdout"
HANDLER_TRIGGER_STDERR="$REPORT_DIR/openclaw_cliq_bot_no_response_packet_${RUN_ID}_handler_trigger.stderr"

PUBLIC_CALLBACK_EXIT="null"
PUBLIC_CALLBACK_CHECKED=false

if [[ -n "${ZOHO_CLIQ_PUBLIC_WEBHOOK_URL:-}" || "$REQUIRE_PUBLIC_CALLBACK" == "1" ]]; then
  PUBLIC_CALLBACK_CHECKED=true
  PUBLIC_CALLBACK_EXIT=0
  set +e
  ZOHO_CLIQ_PUBLIC_CALLBACK_RUN_ID="${RUN_ID}-public-callback" \
  ZOHO_CLIQ_PUBLIC_CALLBACK_REPORT_FILE="$PUBLIC_CALLBACK_FILE" \
    "$PUBLIC_CALLBACK_SCRIPT" >"$PUBLIC_CALLBACK_STDOUT" 2>"$PUBLIC_CALLBACK_STDERR"
  PUBLIC_CALLBACK_EXIT=$?
  set -e
else
  "$JQ_BIN" -n \
    --arg runId "${RUN_ID}-public-callback" \
    --arg checkedAt "$CHECKED_AT" \
    '{
      schemaVersion: 1,
      kind: "openclaw_cliq_public_callback_smoke",
      runId: $runId,
      checkedAt: $checkedAt,
      status: "not_checked",
      reason: "public_webhook_url_missing",
      redaction: {
        rawWebhookPayloadStored: false,
        responseBodyStored: false,
        secretsStored: false
      }
    }' >"$PUBLIC_CALLBACK_FILE"
  : >"$PUBLIC_CALLBACK_STDOUT"
  : >"$PUBLIC_CALLBACK_STDERR"
fi

if [[ ! -f "$PUBLIC_CALLBACK_FILE" ]]; then
  cp "$PUBLIC_CALLBACK_STDOUT" "$PUBLIC_CALLBACK_FILE"
fi

INGRESS_EXIT=0
set +e
ZOHO_CLIQ_INGRESS_RUN_ID="${RUN_ID}-ingress" \
ZOHO_CLIQ_INGRESS_REPORT_FILE="$INGRESS_FILE" \
  "$INGRESS_SCRIPT" >"$INGRESS_STDOUT" 2>"$INGRESS_STDERR"
INGRESS_EXIT=$?
set -e

if [[ ! -f "$INGRESS_FILE" ]]; then
  cp "$INGRESS_STDOUT" "$INGRESS_FILE"
fi

HANDLER_TRIGGER_EXIT="null"
HANDLER_TRIGGER_CHECKED=false
HANDLER_TRIGGER_REASON="not_no_recent_webhook_ingress"
PUBLIC_CALLBACK_STATUS="$("$JQ_BIN" -r '.status // ""' "$PUBLIC_CALLBACK_FILE")"
INGRESS_HAS_NO_RECENT=false
if "$JQ_BIN" -e '((.blockers // [(.error // "")]) | index("no_recent_webhook_ingress")) != null' "$INGRESS_FILE" >/dev/null 2>&1; then
  INGRESS_HAS_NO_RECENT=true
fi

if [[ "$INGRESS_HAS_NO_RECENT" == "true" ]]; then
  if [[ "$PUBLIC_CALLBACK_CHECKED" == "true" && "$PUBLIC_CALLBACK_STATUS" != "public_callback_verified" ]]; then
    HANDLER_TRIGGER_REASON="public_callback_unverified"
  else
    HANDLER_TRIGGER_CHECKED=true
    HANDLER_TRIGGER_EXIT=0
    set +e
    ZOHO_CLIQ_HANDLER_PACKET_RUN_ID="${RUN_ID}-handler-trigger" \
    ZOHO_CLIQ_HANDLER_PACKET_FILE="$HANDLER_TRIGGER_FILE" \
      "$HANDLER_TRIGGER_SCRIPT" >"$HANDLER_TRIGGER_STDOUT" 2>"$HANDLER_TRIGGER_STDERR"
    HANDLER_TRIGGER_EXIT=$?
    set -e
  fi
fi

if [[ "$HANDLER_TRIGGER_CHECKED" != "true" ]]; then
  "$JQ_BIN" -n \
    --arg runId "${RUN_ID}-handler-trigger" \
    --arg checkedAt "$CHECKED_AT" \
    --arg reason "$HANDLER_TRIGGER_REASON" \
    '{
      schemaVersion: 1,
      kind: "openclaw_cliq_handler_trigger_packet",
      runId: $runId,
      checkedAt: $checkedAt,
      status: "not_checked",
      reason: $reason,
      redaction: {
        rawWebhookPayloadStored: false,
        rawMessageBodyStored: false,
        rawCliqReplyBodyStored: false,
        responseBodyStored: false,
        secretsStored: false,
        secretValueStored: false
      }
    }' >"$HANDLER_TRIGGER_FILE"
  : >"$HANDLER_TRIGGER_STDOUT"
  : >"$HANDLER_TRIGGER_STDERR"
elif [[ ! -f "$HANDLER_TRIGGER_FILE" ]]; then
  cp "$HANDLER_TRIGGER_STDOUT" "$HANDLER_TRIGGER_FILE"
fi

PUBLIC_CALLBACK_BASENAME="$(basename "$PUBLIC_CALLBACK_FILE")"
INGRESS_BASENAME="$(basename "$INGRESS_FILE")"
HANDLER_TRIGGER_BASENAME="$(basename "$HANDLER_TRIGGER_FILE")"

PAYLOAD="$("$JQ_BIN" -n \
  --arg runId "$RUN_ID" \
  --arg checkedAt "$CHECKED_AT" \
  --argjson publicCallbackChecked "$PUBLIC_CALLBACK_CHECKED" \
  --argjson publicCallbackExit "$PUBLIC_CALLBACK_EXIT" \
  --argjson ingressExit "$INGRESS_EXIT" \
  --argjson handlerTriggerChecked "$HANDLER_TRIGGER_CHECKED" \
  --argjson handlerTriggerExit "$HANDLER_TRIGGER_EXIT" \
  --arg publicCallbackFile "$PUBLIC_CALLBACK_BASENAME" \
  --arg ingressFile "$INGRESS_BASENAME" \
  --arg handlerTriggerFile "$HANDLER_TRIGGER_BASENAME" \
  --slurpfile publicCallback "$PUBLIC_CALLBACK_FILE" \
  --slurpfile ingress "$INGRESS_FILE" \
  --slurpfile handlerTrigger "$HANDLER_TRIGGER_FILE" \
  '
  $publicCallback[0] as $public
  | $ingress[0] as $ingressReport
  | $handlerTrigger[0] as $handlerPacket
  | [
      (if $publicCallbackChecked and (($public.status // "") != "public_callback_verified") then "public_callback_unverified" else empty end),
      (if ($ingressReport.status // "") == "live_ingress_active" then empty
       else (($ingressReport.blockers // [($ingressReport.error // "ingress_diagnostic_not_active")])[])
       end)
    ] as $blockers
  | ($publicCallbackChecked and (($public.status // "") == "public_callback_verified")) as $publicVerified
  | {
      schemaVersion: 1,
      kind: "openclaw_cliq_bot_no_response_packet",
      runId: $runId,
      checkedAt: $checkedAt,
      status: (if ($blockers | length) == 0 then "ingress_active" else "blocked" end),
      blockers: $blockers,
      commandExits: {
        publicCallback: $publicCallbackExit,
        ingressDiagnostic: $ingressExit,
        handlerTrigger: $handlerTriggerExit
      },
      evidenceFiles: {
        publicCallback: $publicCallbackFile,
        ingressDiagnostic: $ingressFile,
        handlerTrigger: $handlerTriggerFile
      },
      publicCallback: {
        checked: $publicCallbackChecked,
        status: ($public.status // null),
        error: ($public.error // null),
        reason: ($public.reason // null),
        webhook: ($public.webhook // null),
        checks: ($public.checks // null),
        redaction: ($public.redaction // null)
      },
      ingress: {
        status: ($ingressReport.status // null),
        error: ($ingressReport.error // null),
        blockers: ($ingressReport.blockers // []),
        nextAction: ($ingressReport.nextAction // null),
        window: ($ingressReport.window // null),
        counts: ($ingressReport.counts // null),
        latestWebhook: ($ingressReport.latestWebhook // null),
        latestNativeDispatch: ($ingressReport.latestNativeDispatch // null),
        redaction: ($ingressReport.redaction // null)
      },
      handlerTrigger: {
        checked: $handlerTriggerChecked,
        status: ($handlerPacket.status // null),
        reason: ($handlerPacket.reason // null),
        blockers: ($handlerPacket.blockers // []),
        nextAction: ($handlerPacket.nextAction // null),
        expectedBot: ($handlerPacket.expectedBot // null),
        publicWebhook: ($handlerPacket.publicWebhook // null),
        handlers: ($handlerPacket.handlers // null),
        delugeContract: ($handlerPacket.delugeContract // null),
        operatorChecklist: ($handlerPacket.operatorChecklist // null),
        redaction: ($handlerPacket.redaction // null)
      },
      diagnosis: (
        if ($blockers | index("public_callback_unverified")) then {
          code: "public_callback_unverified",
          likelyCause: "The public webhook did not pass the callback smoke check, so Zoho may not be able to reach OpenClaw.",
          operatorFix: "Fix the public route to /webhooks/cliq before editing Bot handlers.",
          agentSafeNextStep: "Rerun the public callback smoke after the route changes.",
          directDmRequiresMessageHandler: true,
          handlerSectionToCheck: "Message Handler for direct Bot DMs; Mention Handler for @mentions/channel contexts.",
          receivedAckMeaning: "A literal received reply only proves a fixed ACK branch ran; it is not the OpenClaw final answer."
        }
        elif ($blockers | index("no_recent_webhook_ingress")) then {
          code: (if $publicVerified then "zoho_bot_handler_not_posting" else "zoho_bot_handler_trigger_unverified" end),
          likelyCause: (
            if $publicVerified
            then "The public webhook is reachable, but no Bot handler POST reached OpenClaw during the window. For direct Bot DMs, the Zoho Bot details page must list Message Handler; Mention Handler alone will not fire for plain direct messages."
            else "No recent Bot handler POST reached OpenClaw; verify the public callback and paste/save the selected handlers."
            end
          ),
          operatorFix: "Paste and save the Deluge-native Message Handler for direct Bot DMs, paste Mention Handler for @mentions if needed, then send exactly one fresh trusted message.",
          agentSafeNextStep: "Run the handler trigger packet now, or one no-response packet after the operator confirms a fresh save/send.",
          directDmRequiresMessageHandler: true,
          handlerSectionToCheck: "Message Handler for direct Bot DMs; Mention Handler for @mentions/channel contexts.",
          receivedAckMeaning: "A literal received reply only proves a fixed ACK branch ran; it does not prove OpenClaw received the event or produced the final answer."
        }
        elif ($blockers | index("latest_webhook_not_dispatched")) then {
          code: "handler_posted_but_payload_or_policy_blocked",
          likelyCause: "Zoho posted to OpenClaw, but payload shape or OpenClaw policy blocked native dispatch.",
          operatorFix: "Re-paste the current handler template so the message map includes text, senderId, chatId, and reply_mode=deluge_response.",
          agentSafeNextStep: "Inspect the redacted ingress diagnostic latestWebhook reason.",
          directDmRequiresMessageHandler: true,
          handlerSectionToCheck: "Message Handler payload shape for direct Bot DMs.",
          receivedAckMeaning: "A literal received reply is only a handler ACK and may appear even when payload dispatch is blocked."
        }
        elif ($blockers | index("dispatch_reply_rate_limited")) then {
          code: "zoho_reply_rate_limited",
          likelyCause: "OpenClaw dispatched the turn, but Zoho reply delivery was rate-limited.",
          operatorFix: "Wait for cooldown or switch the handler to deluge_response mode so Zoho renders the webhook response directly.",
          agentSafeNextStep: "Avoid bursty live probes; rerun one packet after cooldown or handler-save confirmation.",
          directDmRequiresMessageHandler: true,
          handlerSectionToCheck: "Message Handler reply_mode=deluge_response.",
          receivedAckMeaning: "A fixed received ACK is separate from the rate-limited OpenClaw final reply."
        }
        elif ($blockers | index("dispatch_reply_not_delivered")) then {
          code: "openclaw_dispatched_but_reply_not_visible",
          likelyCause: "OpenClaw dispatched the turn, but no final reply delivery was recorded.",
          operatorFix: "Confirm the handler returns webhook_response when it contains text, not a fixed response map.",
          agentSafeNextStep: "Inspect latestNativeDispatch delivery facts and reply transport.",
          directDmRequiresMessageHandler: true,
          handlerSectionToCheck: "Message Handler return webhook_response branch.",
          receivedAckMeaning: "A literal received reply can hide that the handler returned the ACK map instead of OpenClaw text."
        }
        elif ($blockers | length) == 0 then {
          code: "ingress_and_dispatch_active",
          likelyCause: "Recent webhook ingress and native dispatch are active.",
          operatorFix: "Visually confirm the Bot chat shows the OpenClaw answer.",
          agentSafeNextStep: "Record trusted reply facts if the operator confirms visibility.",
          directDmRequiresMessageHandler: true,
          handlerSectionToCheck: "None unless the visible reply is still a fixed ACK.",
          receivedAckMeaning: "If the visible reply is only received, the handler is still returning a fixed ACK."
        }
        else {
          code: "inspect_packet_reports",
          likelyCause: "The no-response packet found blockers that need report inspection.",
          operatorFix: "Review the redacted evidence files listed in this packet.",
          agentSafeNextStep: "Inspect bot no-response packet reports.",
          directDmRequiresMessageHandler: true,
          handlerSectionToCheck: "Message Handler for direct Bot DMs first.",
          receivedAckMeaning: "A literal received reply is a handler ACK, not the OpenClaw final answer."
        }
        end
      ),
      redaction: {
        rawWebhookPayloadStored: false,
        rawMessageBodyStored: false,
        rawCliqReplyBodyStored: false,
        responseBodyStored: false,
        secretsStored: false
      },
      nextAction: (
        if ($blockers | index("public_callback_unverified")) then "fix_public_callback"
        elif ($blockers | index("no_recent_webhook_ingress")) then "fix_zoho_bot_handler_trigger"
        elif ($blockers | index("latest_webhook_not_dispatched")) then "fix_webhook_payload_or_policy"
        elif ($blockers | index("native_dispatch_missing")) then "check_openclaw_channel_dispatch"
        elif ($blockers | index("dispatch_reply_rate_limited")) then "wait_for_zoho_rate_limit_cooldown_or_retry"
        elif ($blockers | index("dispatch_reply_not_delivered")) then "check_cliq_reply_delivery"
        elif (($blockers | index("agent_mismatch")) or ($blockers | index("agent_model_mismatch"))) then "fix_openclaw_route_binding"
        elif ($blockers | length) == 0 then "collect_trusted_reply_facts_if_needed"
        else "inspect_bot_no_response_packet_reports"
        end
      )
    }
  ')"

printf '%s\n' "$PAYLOAD" >"$PACKET_FILE"
printf '%s\n' "$PAYLOAD"

if [[ "$("$JQ_BIN" -r '.status' "$PACKET_FILE")" != "ingress_active" ]]; then
  exit 1
fi
