#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HASH_SCRIPT="${ZOHO_CLIQ_HASH_REF_SCRIPT:-"$ROOT/ops/scripts/openclaw_cliq_hash_ref.sh"}"
RUN_ID="${ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT_DIR="${ZOHO_CLIQ_TRUSTED_REPLY_REPORT_DIR:-"$ROOT/tests/auto_pilot/reports"}"
FACTS_FILE="${ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE:-"$REPORT_DIR/openclaw_cliq_trusted_reply_facts_${RUN_ID}.json"}"

emit_error() {
  local error="$1"
  printf '{"schemaVersion":1,"kind":"openclaw_cliq_trusted_reply_facts_prepare","runId":"%s","checkedAt":"%s","status":"error","error":"%s"}\n' "$RUN_ID" "$CHECKED_AT" "$error"
}

json_string() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  printf '"%s"' "$value"
}

is_sha256_ref() {
  [[ "$1" =~ ^sha256:[A-Za-z0-9._:-]+$ ]]
}

hash_raw_ref() {
  local raw_value="$1"
  printf '%s' "$raw_value" | "$HASH_SCRIPT"
}

resolve_ref_into() {
  local output_var="$1"
  local hash_value="$2"
  local raw_value="$3"
  local missing_error="$4"
  local invalid_error="$5"
  local resolved_ref
  if [[ -n "$hash_value" ]]; then
    if ! is_sha256_ref "$hash_value"; then
      emit_error "$invalid_error"
      return 2
    fi
    printf -v "$output_var" '%s' "$hash_value"
    return 0
  fi
  if [[ -n "$raw_value" ]]; then
    if ! resolved_ref="$(hash_raw_ref "$raw_value")"; then
      emit_error "hash_ref_failed"
      return 2
    fi
    printf -v "$output_var" '%s' "$resolved_ref"
    return 0
  fi
  emit_error "$missing_error"
  return 2
}

if [[ ! -x "$HASH_SCRIPT" ]]; then
  emit_error "hash_ref_script_missing"
  exit 2
fi

TRUSTED_SENDER_ID_HASH=""
TRUSTED_MESSAGE_ID_HASH=""
DELIVERY_ID_HASH=""
resolve_ref_into \
  TRUSTED_SENDER_ID_HASH \
  "${ZOHO_CLIQ_TRUSTED_SENDER_ID_HASH:-}" \
  "${ZOHO_CLIQ_TRUSTED_SENDER_ID:-}" \
  "trusted_sender_hash_missing" \
  "trusted_sender_hash_invalid" || exit $?
resolve_ref_into \
  TRUSTED_MESSAGE_ID_HASH \
  "${ZOHO_CLIQ_TRUSTED_MESSAGE_ID_HASH:-}" \
  "${ZOHO_CLIQ_TRUSTED_MESSAGE_ID:-}" \
  "trusted_message_hash_missing" \
  "trusted_message_hash_invalid" || exit $?
resolve_ref_into \
  DELIVERY_ID_HASH \
  "${ZOHO_CLIQ_DELIVERY_ID_HASH:-}" \
  "${ZOHO_CLIQ_DELIVERY_ID:-}" \
  "delivery_id_hash_missing" \
  "delivery_id_hash_invalid" || exit $?

mkdir -p "$(dirname "$FACTS_FILE")"
FACTS_PAYLOAD="$(
  printf '{'
  printf '"schemaVersion":1,'
  printf '"kind":"openclaw_cliq_trusted_reply_facts",'
  printf '"runId":"%s","checkedAt":"%s",' "$RUN_ID" "$CHECKED_AT"
  printf '"trustedSenderIdHash":'
  json_string "$TRUSTED_SENDER_ID_HASH"
  printf ',"trustedMessageIdHash":'
  json_string "$TRUSTED_MESSAGE_ID_HASH"
  printf ',"deliveryIdHash":'
  json_string "$DELIVERY_ID_HASH"
  printf ',"redaction":{"rawIdsStored":false,"secretsStored":false}'
  printf '}'
)"
printf '%s\n' "$FACTS_PAYLOAD" > "$FACTS_FILE"

FACTS_FILE_NAME="${FACTS_FILE##*/}"
printf '{"schemaVersion":1,"kind":"openclaw_cliq_trusted_reply_facts_prepare","runId":"%s","checkedAt":"%s","status":"facts_file_ready","factsFile":' "$RUN_ID" "$CHECKED_AT"
json_string "$FACTS_FILE_NAME"
printf ',"facts":{"trustedSenderId":"hash","trustedMessageId":"hash","deliveryId":"hash"},"redaction":{"rawIdsStored":false,"hashValuesStored":true,"localPathsStored":false,"secretsStored":false},"nextCommand":"ops/scripts/openclaw_cliq_trusted_reply_evidence_bundle.sh"}\n'
