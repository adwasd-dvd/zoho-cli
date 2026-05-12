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

PUBLIC_CALLBACK_BASENAME="$(basename "$PUBLIC_CALLBACK_FILE")"
INGRESS_BASENAME="$(basename "$INGRESS_FILE")"

PAYLOAD="$("$JQ_BIN" -n \
  --arg runId "$RUN_ID" \
  --arg checkedAt "$CHECKED_AT" \
  --argjson publicCallbackChecked "$PUBLIC_CALLBACK_CHECKED" \
  --argjson publicCallbackExit "$PUBLIC_CALLBACK_EXIT" \
  --argjson ingressExit "$INGRESS_EXIT" \
  --arg publicCallbackFile "$PUBLIC_CALLBACK_BASENAME" \
  --arg ingressFile "$INGRESS_BASENAME" \
  --slurpfile publicCallback "$PUBLIC_CALLBACK_FILE" \
  --slurpfile ingress "$INGRESS_FILE" \
  '
  $publicCallback[0] as $public
  | $ingress[0] as $ingressReport
  | [
      (if $publicCallbackChecked and (($public.status // "") != "public_callback_verified") then "public_callback_unverified" else empty end),
      (if ($ingressReport.status // "") == "live_ingress_active" then empty
       else (($ingressReport.blockers // [($ingressReport.error // "ingress_diagnostic_not_active")])[])
       end)
    ] as $blockers
  | {
      schemaVersion: 1,
      kind: "openclaw_cliq_bot_no_response_packet",
      runId: $runId,
      checkedAt: $checkedAt,
      status: (if ($blockers | length) == 0 then "ingress_active" else "blocked" end),
      blockers: $blockers,
      commandExits: {
        publicCallback: $publicCallbackExit,
        ingressDiagnostic: $ingressExit
      },
      evidenceFiles: {
        publicCallback: $publicCallbackFile,
        ingressDiagnostic: $ingressFile
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
