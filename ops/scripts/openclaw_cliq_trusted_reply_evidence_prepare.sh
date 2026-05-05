#!/usr/bin/env bash
set -euo pipefail

JQ_BIN="${JQ_BIN:-jq}"
ROUTE_REPORT_FILE="${ZOHO_CLIQ_ROUTE_REPORT_FILE:-}"
EVIDENCE_FILE="${ZOHO_CLIQ_TRUSTED_REPLY_EVIDENCE_FILE:-}"
EXPECTED_ACCOUNT_ID="${ZOHO_CLIQ_EXPECTED_ACCOUNT_ID:-default}"
TRUSTED_SENDER_ID_HASH="${ZOHO_CLIQ_TRUSTED_SENDER_ID_HASH:-}"
TRUSTED_MESSAGE_ID_HASH="${ZOHO_CLIQ_TRUSTED_MESSAGE_ID_HASH:-}"
DELIVERY_ID_HASH="${ZOHO_CLIQ_DELIVERY_ID_HASH:-}"
TRUSTED_MENTION_SENT_AT="${ZOHO_CLIQ_TRUSTED_MENTION_SENT_AT:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
PUBLIC_CALLBACK_VERIFIED="${ZOHO_CLIQ_PUBLIC_CALLBACK_VERIFIED:-true}"
REPLY_DELIVERED="${ZOHO_CLIQ_REPLY_DELIVERED:-true}"
AGENT_TURN_COUNT="${ZOHO_CLIQ_AGENT_TURN_COUNT:-1}"
CLIQ_REPLY_COUNT="${ZOHO_CLIQ_REPLY_COUNT:-1}"
DEAD_LETTER_COUNT="${ZOHO_CLIQ_DEAD_LETTER_COUNT:-0}"
DUPLICATE_DISPATCH_COUNT="${ZOHO_CLIQ_DUPLICATE_DISPATCH_COUNT:-0}"
RUN_ID="${ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

emit_payload() {
  local payload="$1"
  printf '%s\n' "$payload"
  if [[ -n "$EVIDENCE_FILE" ]]; then
    mkdir -p "$(dirname "$EVIDENCE_FILE")"
    printf '%s\n' "$payload" > "$EVIDENCE_FILE"
  fi
}

emit_error() {
  local error="$1"
  printf '{"schemaVersion":1,"kind":"openclaw_cliq_trusted_reply_evidence_prepare","runId":"%s","checkedAt":"%s","status":"error","error":"%s"}\n' "$RUN_ID" "$CHECKED_AT" "$error"
}

is_sha256_ref() {
  [[ "$1" =~ ^sha256:[A-Za-z0-9._:-]+$ ]]
}

is_bool() {
  [[ "$1" == "true" || "$1" == "false" ]]
}

is_count() {
  [[ "$1" =~ ^(0|[1-9][0-9]*)$ ]]
}

if [[ -z "$ROUTE_REPORT_FILE" ]]; then
  emit_error "route_report_file_missing"
  exit 2
fi
if [[ ! -f "$ROUTE_REPORT_FILE" ]]; then
  emit_error "route_report_file_not_found"
  exit 2
fi
if ! command -v "$JQ_BIN" >/dev/null 2>&1; then
  emit_error "jq_required"
  exit 2
fi
if ! is_sha256_ref "$TRUSTED_SENDER_ID_HASH"; then
  emit_error "trusted_sender_hash_missing"
  exit 2
fi
if ! is_sha256_ref "$TRUSTED_MESSAGE_ID_HASH"; then
  emit_error "trusted_message_hash_missing"
  exit 2
fi
if ! is_sha256_ref "$DELIVERY_ID_HASH"; then
  emit_error "delivery_id_hash_missing"
  exit 2
fi
if ! is_bool "$PUBLIC_CALLBACK_VERIFIED"; then
  emit_error "public_callback_verified_invalid"
  exit 2
fi
if ! is_bool "$REPLY_DELIVERED"; then
  emit_error "reply_delivered_invalid"
  exit 2
fi
for count in "$AGENT_TURN_COUNT" "$CLIQ_REPLY_COUNT" "$DEAD_LETTER_COUNT" "$DUPLICATE_DISPATCH_COUNT"; do
  if ! is_count "$count"; then
    emit_error "count_invalid"
    exit 2
  fi
done

PAYLOAD="$("$JQ_BIN" -n \
  --slurpfile route "$ROUTE_REPORT_FILE" \
  --arg expectedAccountId "$EXPECTED_ACCOUNT_ID" \
  --arg trustedSenderIdHash "$TRUSTED_SENDER_ID_HASH" \
  --arg trustedMessageIdHash "$TRUSTED_MESSAGE_ID_HASH" \
  --arg deliveryIdHash "$DELIVERY_ID_HASH" \
  --arg sentAt "$TRUSTED_MENTION_SENT_AT" \
  --argjson publicCallbackVerified "$PUBLIC_CALLBACK_VERIFIED" \
  --argjson replyDelivered "$REPLY_DELIVERED" \
  --argjson agentTurnCount "$AGENT_TURN_COUNT" \
  --argjson cliqReplyCount "$CLIQ_REPLY_COUNT" \
  --argjson deadLetterCount "$DEAD_LETTER_COUNT" \
  --argjson duplicateDispatchCount "$DUPLICATE_DISPATCH_COUNT" \
  '
  ($route[0]) as $r
  | ($r.accountId // $expectedAccountId) as $accountId
  | ($r.agentId // $r.actualAgentId // $r.expectedAgentId // "") as $agentId
  | ($r.model // $r.actualModel // $r.expectedModel // null) as $agentModel
  | {
      schemaVersion: 1,
      kind: "openclaw_cliq_trusted_reply_evidence",
      channel: "cliq",
      accountId: $accountId,
      routePreflight: {
        status: ($r.status // ""),
        agentId: $agentId,
        model: $agentModel
      },
      publicCallbackVerified: $publicCallbackVerified,
      trustedMention: {
        handler: "mention",
        sentAt: $sentAt,
        trustedSenderIdHash: $trustedSenderIdHash,
        messageIdHash: $trustedMessageIdHash
      },
      nativeDispatch: {
        agentId: $agentId,
        agentModel: $agentModel,
        agentTurnCount: $agentTurnCount,
        deadLetterCount: $deadLetterCount,
        duplicateDispatchCount: $duplicateDispatchCount
      },
      delivery: {
        replyDelivered: $replyDelivered,
        cliqReplyCount: $cliqReplyCount,
        deliveryIdHash: $deliveryIdHash
      },
      redaction: {
        rawWebhookPayloadStored: false,
        rawMessageBodyStored: false,
        rawCliqReplyBodyStored: false,
        secretsStored: false
      }
    }
  ')"

emit_payload "$PAYLOAD"
