#!/usr/bin/env bash
set -euo pipefail

JQ_BIN="${JQ_BIN:-jq}"
EVIDENCE_FILE="${ZOHO_CLIQ_TRUSTED_REPLY_EVIDENCE_FILE:-${1:-}}"
REPORT_FILE="${ZOHO_CLIQ_TRUSTED_REPLY_REPORT_FILE:-}"
EXPECTED_AGENT_ID="${ZOHO_CLIQ_EXPECTED_AGENT_ID:-}"
EXPECTED_AGENT_MODEL="${ZOHO_CLIQ_EXPECTED_AGENT_MODEL:-}"
EXPECTED_ACCOUNT_ID="${ZOHO_CLIQ_EXPECTED_ACCOUNT_ID:-default}"
RUN_ID="${ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

emit_result() {
  local payload="$1"
  printf '%s\n' "$payload"
  if [[ -n "$REPORT_FILE" ]]; then
    mkdir -p "$(dirname "$REPORT_FILE")"
    printf '%s\n' "$payload" > "$REPORT_FILE"
  fi
}

if [[ -z "$EVIDENCE_FILE" ]]; then
  emit_result "$(printf '{"schemaVersion":1,"kind":"openclaw_cliq_trusted_reply_evidence_check","runId":"%s","checkedAt":"%s","status":"error","error":"evidence_file_missing"}' "$RUN_ID" "$CHECKED_AT")"
  exit 2
fi
if [[ ! -f "$EVIDENCE_FILE" ]]; then
  emit_result "$(printf '{"schemaVersion":1,"kind":"openclaw_cliq_trusted_reply_evidence_check","runId":"%s","checkedAt":"%s","status":"error","error":"evidence_file_not_found"}' "$RUN_ID" "$CHECKED_AT")"
  exit 2
fi
if [[ -z "$EXPECTED_AGENT_ID" ]]; then
  emit_result "$(printf '{"schemaVersion":1,"kind":"openclaw_cliq_trusted_reply_evidence_check","runId":"%s","checkedAt":"%s","status":"error","error":"expected_agent_missing","accountId":"%s"}' "$RUN_ID" "$CHECKED_AT" "$EXPECTED_ACCOUNT_ID")"
  exit 2
fi
if ! command -v "$JQ_BIN" >/dev/null 2>&1; then
  emit_result "$(printf '{"schemaVersion":1,"kind":"openclaw_cliq_trusted_reply_evidence_check","runId":"%s","checkedAt":"%s","status":"error","error":"jq_required"}' "$RUN_ID" "$CHECKED_AT")"
  exit 2
fi

SECRET_MARKER_PRESENT=false
if grep -Eiq 'X-Cliq-Webhook-Secret|ZOHO_CLIQ_WEBHOOK_SECRET|access_token|refresh_token|client_secret' "$EVIDENCE_FILE"; then
  SECRET_MARKER_PRESENT=true
fi

EVIDENCE_BASENAME="$(basename "$EVIDENCE_FILE")"
RESULT="$("$JQ_BIN" -n \
  --slurpfile evidence "$EVIDENCE_FILE" \
  --arg runId "$RUN_ID" \
  --arg checkedAt "$CHECKED_AT" \
  --arg evidenceFile "$EVIDENCE_BASENAME" \
  --arg expectedAgentId "$EXPECTED_AGENT_ID" \
  --arg expectedAgentModel "$EXPECTED_AGENT_MODEL" \
  --arg expectedAccountId "$EXPECTED_ACCOUNT_ID" \
  --argjson secretMarkerPresent "$SECRET_MARKER_PRESENT" \
  '
  def redaction_value($redaction; $key): (($redaction // {}) as $r | if ($r | has($key)) then $r[$key] else null end);
  def redaction_false($redaction; $key): (redaction_value($redaction; $key) == false);

  ($evidence[0]) as $e
  | ($e.routePreflight.status // $e.routePreflightStatus // "") as $routeStatus
  | ($e.routePreflight.agentId // $e.nativeDispatch.agentId // $e.agentId // "") as $agentId
  | ($e.routePreflight.model // $e.nativeDispatch.agentModel // $e.agentModel // "") as $agentModel
  | ($e.accountId // $expectedAccountId) as $accountId
  | ($e.nativeDispatch.agentTurnCount // $e.agentTurnCount // -1 | tonumber? // -1) as $agentTurnCount
  | ($e.delivery.cliqReplyCount // $e.cliqReplyCount // -1 | tonumber? // -1) as $cliqReplyCount
  | ($e.nativeDispatch.deadLetterCount // $e.deadLetterCount // -1 | tonumber? // -1) as $deadLetterCount
  | ($e.nativeDispatch.duplicateDispatchCount // $e.duplicateDispatchCount // -1 | tonumber? // -1) as $duplicateDispatchCount
  | (if (($e.delivery // {}) | has("replyDelivered")) then $e.delivery.replyDelivered elif ($e | has("replyDelivered")) then $e.replyDelivered else false end) as $replyDelivered
  | [
      (if $e.schemaVersion != 1 then "schema_version_invalid" else empty end),
      (if $e.kind != "openclaw_cliq_trusted_reply_evidence" then "kind_invalid" else empty end),
      (if ($e.channel // "") != "cliq" then "channel_not_cliq" else empty end),
      (if $accountId != $expectedAccountId then "account_mismatch" else empty end),
      (if $routeStatus != "ok" then "route_preflight_not_ok" else empty end),
      (if ($e.publicCallbackVerified // false) != true then "public_callback_not_verified" else empty end),
      (if $agentId != $expectedAgentId then "agent_mismatch" else empty end),
      (if ($expectedAgentModel != "" and $agentModel != $expectedAgentModel) then "agent_model_mismatch" else empty end),
      (if $agentTurnCount != 1 then "agent_turn_count_not_one" else empty end),
      (if $cliqReplyCount != 1 then "cliq_reply_count_not_one" else empty end),
      (if $replyDelivered != true then "reply_not_delivered" else empty end),
      (if $deadLetterCount != 0 then "dead_letter_count_not_zero" else empty end),
      (if $duplicateDispatchCount != 0 then "duplicate_dispatch_count_not_zero" else empty end),
      (if redaction_false($e.redaction; "rawWebhookPayloadStored") | not then "raw_webhook_payload_stored" else empty end),
      (if redaction_false($e.redaction; "rawMessageBodyStored") | not then "raw_message_body_stored" else empty end),
      (if redaction_false($e.redaction; "rawCliqReplyBodyStored") | not then "raw_cliq_reply_body_stored" else empty end),
      (if redaction_false($e.redaction; "secretsStored") | not then "secrets_stored" else empty end),
      (if $secretMarkerPresent then "secret_marker_present" else empty end)
    ] as $blockingReasons
  | {
      schemaVersion: 1,
      kind: "openclaw_cliq_trusted_reply_evidence_check",
      runId: $runId,
      checkedAt: $checkedAt,
      status: (if ($blockingReasons | length) == 0 then "trusted_reply_recorded" else "incomplete" end),
      evidenceFile: $evidenceFile,
      channel: "cliq",
      accountId: $accountId,
      expectedAgentId: $expectedAgentId,
      expectedAgentModel: (if $expectedAgentModel == "" then null else $expectedAgentModel end),
      agentId: (if $agentId == "" then null else $agentId end),
      agentModel: (if $agentModel == "" then null else $agentModel end),
      publicCallbackVerified: ($e.publicCallbackVerified // false),
      routePreflightStatus: $routeStatus,
      agentTurnCount: $agentTurnCount,
      cliqReplyCount: $cliqReplyCount,
      replyDelivered: $replyDelivered,
      deadLetterCount: $deadLetterCount,
      duplicateDispatchCount: $duplicateDispatchCount,
      redaction: {
        rawWebhookPayloadStored: redaction_value($e.redaction; "rawWebhookPayloadStored"),
        rawMessageBodyStored: redaction_value($e.redaction; "rawMessageBodyStored"),
        rawCliqReplyBodyStored: redaction_value($e.redaction; "rawCliqReplyBodyStored"),
        secretsStored: redaction_value($e.redaction; "secretsStored"),
        secretMarkerPresent: $secretMarkerPresent
      },
      blockingReasons: $blockingReasons
    }
  ')"

emit_result "$RESULT"

STATUS="$("$JQ_BIN" -r '.status' <<<"$RESULT")"
if [[ "$STATUS" == "trusted_reply_recorded" ]]; then
  exit 0
fi
exit 1
