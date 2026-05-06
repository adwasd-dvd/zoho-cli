#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HASH_SCRIPT="${ZOHO_CLIQ_HASH_REF_SCRIPT:-"$ROOT/ops/scripts/openclaw_cliq_hash_ref.sh"}"
ROUTE_SCRIPT="${ZOHO_CLIQ_ROUTE_PREFLIGHT_SCRIPT:-"$ROOT/ops/scripts/openclaw_cliq_live_smoke.sh"}"
PREPARE_SCRIPT="${ZOHO_CLIQ_TRUSTED_REPLY_PREPARE_SCRIPT:-"$ROOT/ops/scripts/openclaw_cliq_trusted_reply_evidence_prepare.sh"}"
CHECK_SCRIPT="${ZOHO_CLIQ_TRUSTED_REPLY_CHECK_SCRIPT:-"$ROOT/ops/scripts/openclaw_cliq_trusted_reply_evidence.sh"}"
JQ_BIN="${JQ_BIN:-jq}"
RUN_ID="${ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT_DIR="${ZOHO_CLIQ_TRUSTED_REPLY_REPORT_DIR:-"$ROOT/tests/auto_pilot/reports"}"
ROUTE_REPORT_FILE="${ZOHO_CLIQ_ROUTE_REPORT_FILE:-"$REPORT_DIR/openclaw_cliq_route_preflight_${RUN_ID}.json"}"
EVIDENCE_FILE="${ZOHO_CLIQ_TRUSTED_REPLY_EVIDENCE_FILE:-"$REPORT_DIR/openclaw_cliq_trusted_reply_${RUN_ID}.json"}"
CHECK_REPORT_FILE="${ZOHO_CLIQ_TRUSTED_REPLY_REPORT_FILE:-"$REPORT_DIR/openclaw_cliq_trusted_reply_check_${RUN_ID}.json"}"
PLAN_REPORT_FILE="${ZOHO_CLIQ_TRUSTED_REPLY_PLAN_FILE:-"$REPORT_DIR/openclaw_cliq_trusted_reply_plan_${RUN_ID}.json"}"
PLAN_ONLY="${ZOHO_CLIQ_TRUSTED_REPLY_PLAN_ONLY:-}"
FACTS_FILE="${ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE:-}"
FACTS_TRUSTED_SENDER_ID_HASH=""
FACTS_TRUSTED_MESSAGE_ID_HASH=""
FACTS_DELIVERY_ID_HASH=""

emit_error() {
  local error="$1"
  printf '{"schemaVersion":1,"kind":"openclaw_cliq_trusted_reply_evidence_bundle","runId":"%s","checkedAt":"%s","status":"error","error":"%s"}\n' "$RUN_ID" "$CHECKED_AT" "$error"
}

emit_plan() {
  local payload="$1"
  printf '%s\n' "$payload"
  if [[ -n "$PLAN_REPORT_FILE" ]]; then
    mkdir -p "$(dirname "$PLAN_REPORT_FILE")"
    printf '%s\n' "$payload" > "$PLAN_REPORT_FILE"
  fi
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
  local resolved_ref
  if [[ -n "$hash_value" ]]; then
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

fact_state() {
  local hash_value="$1"
  local raw_value="$2"
  if [[ -n "$hash_value" ]]; then
    printf 'hash'
  elif [[ -n "$raw_value" ]]; then
    printf 'raw'
  else
    printf 'missing'
  fi
}

json_string_array() {
  local first=1
  local value
  printf '['
  for value in "$@"; do
    if [[ "$first" -eq 0 ]]; then
      printf ','
    fi
    printf '"%s"' "$value"
    first=0
  done
  printf ']'
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

first_non_empty() {
  local value
  for value in "$@"; do
    if [[ -n "$value" ]]; then
      printf '%s' "$value"
      return 0
    fi
  done
}

load_facts_file() {
  if [[ -z "$FACTS_FILE" ]]; then
    return 0
  fi
  if [[ ! -f "$FACTS_FILE" ]]; then
    emit_error "facts_file_not_found"
    exit 2
  fi
  if ! command -v "$JQ_BIN" >/dev/null 2>&1; then
    emit_error "jq_required"
    exit 2
  fi
  if ! "$JQ_BIN" -e . "$FACTS_FILE" >/dev/null 2>&1; then
    emit_error "facts_file_invalid_json"
    exit 2
  fi
  if grep -Eiq 'X-Cliq-Webhook-Secret|ZOHO_CLIQ_WEBHOOK_SECRET|access_token|refresh_token|client_secret' "$FACTS_FILE"; then
    emit_error "facts_file_secret_marker_present"
    exit 2
  fi
  if ! "$JQ_BIN" -e '(.kind // "openclaw_cliq_trusted_reply_facts") == "openclaw_cliq_trusted_reply_facts"' "$FACTS_FILE" >/dev/null; then
    emit_error "facts_file_kind_invalid"
    exit 2
  fi
  if "$JQ_BIN" -e '
    has("trustedSenderId")
    or has("trustedMessageId")
    or has("deliveryId")
    or ((.trustedMention // {}) | has("trustedSenderId") or has("messageId"))
    or ((.delivery // {}) | has("deliveryId"))
  ' "$FACTS_FILE" >/dev/null; then
    emit_error "facts_file_raw_ids_present"
    exit 2
  fi

  FACTS_TRUSTED_SENDER_ID_HASH="$("$JQ_BIN" -r '.trustedSenderIdHash // .trustedMention.trustedSenderIdHash // empty' "$FACTS_FILE")"
  FACTS_TRUSTED_MESSAGE_ID_HASH="$("$JQ_BIN" -r '.trustedMessageIdHash // .messageIdHash // .trustedMention.messageIdHash // empty' "$FACTS_FILE")"
  FACTS_DELIVERY_ID_HASH="$("$JQ_BIN" -r '.deliveryIdHash // .delivery.deliveryIdHash // empty' "$FACTS_FILE")"

  if [[ -n "$FACTS_TRUSTED_SENDER_ID_HASH" ]] && ! is_sha256_ref "$FACTS_TRUSTED_SENDER_ID_HASH"; then
    emit_error "facts_file_trusted_sender_hash_invalid"
    exit 2
  fi
  if [[ -n "$FACTS_TRUSTED_MESSAGE_ID_HASH" ]] && ! is_sha256_ref "$FACTS_TRUSTED_MESSAGE_ID_HASH"; then
    emit_error "facts_file_trusted_message_hash_invalid"
    exit 2
  fi
  if [[ -n "$FACTS_DELIVERY_ID_HASH" ]] && ! is_sha256_ref "$FACTS_DELIVERY_ID_HASH"; then
    emit_error "facts_file_delivery_hash_invalid"
    exit 2
  fi
}

if [[ ! -x "$HASH_SCRIPT" ]]; then
  emit_error "hash_ref_script_missing"
  exit 2
fi
if [[ ! -x "$ROUTE_SCRIPT" ]]; then
  emit_error "route_preflight_script_missing"
  exit 2
fi
if [[ ! -x "$PREPARE_SCRIPT" ]]; then
  emit_error "prepare_script_missing"
  exit 2
fi
if [[ ! -x "$CHECK_SCRIPT" ]]; then
  emit_error "check_script_missing"
  exit 2
fi
if [[ -z "${ZOHO_CLIQ_EXPECTED_AGENT_ID:-}" ]]; then
  emit_error "expected_agent_missing"
  exit 2
fi

load_facts_file

if [[ ! -f "$ROUTE_REPORT_FILE" ]]; then
  set +e
  ROUTE_OUTPUT="$(
    env \
      ZOHO_CLIQ_ROUTE_BINDING_ONLY=1 \
      ZOHO_CLIQ_ROUTE_REPORT_FILE="$ROUTE_REPORT_FILE" \
      ZOHO_CLIQ_SMOKE_RUN_ID="$RUN_ID" \
      "$ROUTE_SCRIPT"
  )"
  ROUTE_STATUS=$?
  set -e
  if [[ "$ROUTE_STATUS" -ne 0 ]]; then
    if [[ -f "$ROUTE_REPORT_FILE" ]]; then
      cat "$ROUTE_REPORT_FILE"
    elif [[ -n "$ROUTE_OUTPUT" ]]; then
      ROUTE_PAYLOAD="$(printf '%s\n' "$ROUTE_OUTPUT" | awk '/^{/ { payload=$0 } END { if (payload != "") print payload }')"
      if [[ -n "$ROUTE_PAYLOAD" ]]; then
        printf '%s\n' "$ROUTE_PAYLOAD"
      else
        emit_error "route_preflight_failed"
      fi
    else
      emit_error "route_preflight_failed"
    fi
    exit "$ROUTE_STATUS"
  fi
fi

if [[ "$PLAN_ONLY" == "1" || "$PLAN_ONLY" == "true" ]]; then
  SENDER_HASH="$(first_non_empty "${ZOHO_CLIQ_TRUSTED_SENDER_ID_HASH:-}" "$FACTS_TRUSTED_SENDER_ID_HASH")"
  MESSAGE_HASH="$(first_non_empty "${ZOHO_CLIQ_TRUSTED_MESSAGE_ID_HASH:-}" "$FACTS_TRUSTED_MESSAGE_ID_HASH")"
  DELIVERY_HASH="$(first_non_empty "${ZOHO_CLIQ_DELIVERY_ID_HASH:-}" "$FACTS_DELIVERY_ID_HASH")"
  SENDER_FACT="$(fact_state "$SENDER_HASH" "${ZOHO_CLIQ_TRUSTED_SENDER_ID:-}")"
  MESSAGE_FACT="$(fact_state "$MESSAGE_HASH" "${ZOHO_CLIQ_TRUSTED_MESSAGE_ID:-}")"
  DELIVERY_FACT="$(fact_state "$DELIVERY_HASH" "${ZOHO_CLIQ_DELIVERY_ID:-}")"
  MISSING_FACTS=()
  READY_FACTS=()
  if [[ "$SENDER_FACT" == "missing" ]]; then
    MISSING_FACTS+=("trustedSenderId")
  else
    READY_FACTS+=("trustedSenderId")
  fi
  if [[ "$MESSAGE_FACT" == "missing" ]]; then
    MISSING_FACTS+=("trustedMessageId")
  else
    READY_FACTS+=("trustedMessageId")
  fi
  if [[ "$DELIVERY_FACT" == "missing" ]]; then
    MISSING_FACTS+=("deliveryId")
  else
    READY_FACTS+=("deliveryId")
  fi
  if [[ "${#MISSING_FACTS[@]}" -eq 0 ]]; then
    MISSING_FACTS_JSON="[]"
  else
    MISSING_FACTS_JSON="$(json_string_array "${MISSING_FACTS[@]}")"
  fi
  if [[ "${#READY_FACTS[@]}" -eq 0 ]]; then
    READY_FACTS_JSON="[]"
  else
    READY_FACTS_JSON="$(json_string_array "${READY_FACTS[@]}")"
  fi
  PLAN_STATUS="ready_for_bundle_check"
  NEXT_ACTION="run_final_trusted_reply_bundle"
  READY_FOR_FINAL_BUNDLE="true"
  if [[ "$SENDER_FACT" == "missing" || "$MESSAGE_FACT" == "missing" || "$DELIVERY_FACT" == "missing" ]]; then
    PLAN_STATUS="awaiting_live_delivery_facts"
    NEXT_ACTION="collect_live_delivery_facts"
    READY_FOR_FINAL_BUNDLE="false"
  fi
  ROUTE_REPORT_NAME="${ROUTE_REPORT_FILE##*/}"
  PLAN_REPORT_NAME="${PLAN_REPORT_FILE##*/}"
  EVIDENCE_REPORT_NAME="${EVIDENCE_FILE##*/}"
  CHECK_REPORT_NAME="${CHECK_REPORT_FILE##*/}"
  PLAN_PAYLOAD="$(
    printf '{'
    printf '"schemaVersion":1,'
    printf '"kind":"openclaw_cliq_trusted_reply_evidence_bundle_plan",'
    printf '"runId":"%s","checkedAt":"%s","status":"%s",' "$RUN_ID" "$CHECKED_AT" "$PLAN_STATUS"
    printf '"routeReportReady":true,'
    printf '"facts":{"trustedSenderId":"%s","trustedMessageId":"%s","deliveryId":"%s"},' "$SENDER_FACT" "$MESSAGE_FACT" "$DELIVERY_FACT"
    printf '"missingFacts":%s,' "$MISSING_FACTS_JSON"
    printf '"readyFacts":%s,' "$READY_FACTS_JSON"
    printf '"nextAction":"%s",' "$NEXT_ACTION"
    printf '"readyForFinalBundle":%s,' "$READY_FOR_FINAL_BUNDLE"
    printf '"reportFiles":{"routePreflight":'
    json_string "$ROUTE_REPORT_NAME"
    printf ',"plan":'
    json_string "$PLAN_REPORT_NAME"
    printf ',"evidence":'
    json_string "$EVIDENCE_REPORT_NAME"
    printf ',"check":'
    json_string "$CHECK_REPORT_NAME"
    printf '},'
    printf '"reportsReady":{"routePreflight":true,"plan":true,"evidence":false,"check":false},'
    printf '"redaction":{"rawIdsStored":false,"hashValuesStored":false,"localPathsStored":false,"secretsStored":false},'
    printf '"collectionGuide":{"sendExactlyOneTrustedMention":true,"requiredLiveFacts":["trustedSenderId","trustedMessageId","deliveryId"],"forbiddenEvidence":["rawWebhookPayload","rawMessageBody","rawCliqReplyBody","secrets"],"hashRawIdsBeforeEvidence":true,"preferredFactSource":"ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE","successStatus":"trusted_reply_recorded"},'
    printf '"acceptedFactSources":["env","hashFactsFile"],'
    printf '"acceptedFactStates":["hash","raw"],'
    printf '"requiredEnv":["ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE or ZOHO_CLIQ_TRUSTED_SENDER_ID_HASH or ZOHO_CLIQ_TRUSTED_SENDER_ID","ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE or ZOHO_CLIQ_TRUSTED_MESSAGE_ID_HASH or ZOHO_CLIQ_TRUSTED_MESSAGE_ID","ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE or ZOHO_CLIQ_DELIVERY_ID_HASH or ZOHO_CLIQ_DELIVERY_ID"],'
    printf '"nextCommand":"ops/scripts/openclaw_cliq_trusted_reply_evidence_bundle.sh"'
    printf '}'
  )"
  emit_plan "$PLAN_PAYLOAD"
  exit 0
fi

TRUSTED_SENDER_ID_HASH=""
TRUSTED_MESSAGE_ID_HASH=""
DELIVERY_ID_HASH=""
resolve_ref_into \
  TRUSTED_SENDER_ID_HASH \
  "$(first_non_empty "${ZOHO_CLIQ_TRUSTED_SENDER_ID_HASH:-}" "$FACTS_TRUSTED_SENDER_ID_HASH")" \
  "${ZOHO_CLIQ_TRUSTED_SENDER_ID:-}" \
  "trusted_sender_hash_missing" || exit $?
resolve_ref_into \
  TRUSTED_MESSAGE_ID_HASH \
  "$(first_non_empty "${ZOHO_CLIQ_TRUSTED_MESSAGE_ID_HASH:-}" "$FACTS_TRUSTED_MESSAGE_ID_HASH")" \
  "${ZOHO_CLIQ_TRUSTED_MESSAGE_ID:-}" \
  "trusted_message_hash_missing" || exit $?
resolve_ref_into \
  DELIVERY_ID_HASH \
  "$(first_non_empty "${ZOHO_CLIQ_DELIVERY_ID_HASH:-}" "$FACTS_DELIVERY_ID_HASH")" \
  "${ZOHO_CLIQ_DELIVERY_ID:-}" \
  "delivery_id_hash_missing" || exit $?

set +e
PREPARE_OUTPUT="$(
  env \
    -u ZOHO_CLIQ_TRUSTED_SENDER_ID \
    -u ZOHO_CLIQ_TRUSTED_MESSAGE_ID \
    -u ZOHO_CLIQ_DELIVERY_ID \
    ZOHO_CLIQ_ROUTE_REPORT_FILE="$ROUTE_REPORT_FILE" \
    ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID="$RUN_ID" \
    ZOHO_CLIQ_TRUSTED_REPLY_EVIDENCE_FILE="$EVIDENCE_FILE" \
    ZOHO_CLIQ_TRUSTED_SENDER_ID_HASH="$TRUSTED_SENDER_ID_HASH" \
    ZOHO_CLIQ_TRUSTED_MESSAGE_ID_HASH="$TRUSTED_MESSAGE_ID_HASH" \
    ZOHO_CLIQ_DELIVERY_ID_HASH="$DELIVERY_ID_HASH" \
    "$PREPARE_SCRIPT"
)"
PREPARE_STATUS=$?
set -e
if [[ "$PREPARE_STATUS" -ne 0 ]]; then
  printf '%s\n' "$PREPARE_OUTPUT"
  exit "$PREPARE_STATUS"
fi

exec env \
  -u ZOHO_CLIQ_TRUSTED_SENDER_ID \
  -u ZOHO_CLIQ_TRUSTED_MESSAGE_ID \
  -u ZOHO_CLIQ_DELIVERY_ID \
  ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID="$RUN_ID" \
  ZOHO_CLIQ_TRUSTED_REPLY_EVIDENCE_FILE="$EVIDENCE_FILE" \
  ZOHO_CLIQ_TRUSTED_REPLY_REPORT_FILE="$CHECK_REPORT_FILE" \
  "$CHECK_SCRIPT"
