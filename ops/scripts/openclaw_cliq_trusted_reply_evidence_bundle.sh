#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HASH_SCRIPT="${ZOHO_CLIQ_HASH_REF_SCRIPT:-"$ROOT/ops/scripts/openclaw_cliq_hash_ref.sh"}"
ROUTE_SCRIPT="${ZOHO_CLIQ_ROUTE_PREFLIGHT_SCRIPT:-"$ROOT/ops/scripts/openclaw_cliq_live_smoke.sh"}"
PREPARE_SCRIPT="${ZOHO_CLIQ_TRUSTED_REPLY_PREPARE_SCRIPT:-"$ROOT/ops/scripts/openclaw_cliq_trusted_reply_evidence_prepare.sh"}"
CHECK_SCRIPT="${ZOHO_CLIQ_TRUSTED_REPLY_CHECK_SCRIPT:-"$ROOT/ops/scripts/openclaw_cliq_trusted_reply_evidence.sh"}"
RUN_ID="${ZOHO_CLIQ_TRUSTED_REPLY_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT_DIR="${ZOHO_CLIQ_TRUSTED_REPLY_REPORT_DIR:-"$ROOT/tests/auto_pilot/reports"}"
ROUTE_REPORT_FILE="${ZOHO_CLIQ_ROUTE_REPORT_FILE:-"$REPORT_DIR/openclaw_cliq_route_preflight_${RUN_ID}.json"}"
EVIDENCE_FILE="${ZOHO_CLIQ_TRUSTED_REPLY_EVIDENCE_FILE:-"$REPORT_DIR/openclaw_cliq_trusted_reply_${RUN_ID}.json"}"
CHECK_REPORT_FILE="${ZOHO_CLIQ_TRUSTED_REPLY_REPORT_FILE:-"$REPORT_DIR/openclaw_cliq_trusted_reply_check_${RUN_ID}.json"}"

emit_error() {
  local error="$1"
  printf '{"schemaVersion":1,"kind":"openclaw_cliq_trusted_reply_evidence_bundle","runId":"%s","checkedAt":"%s","status":"error","error":"%s"}\n' "$RUN_ID" "$CHECKED_AT" "$error"
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

TRUSTED_SENDER_ID_HASH=""
TRUSTED_MESSAGE_ID_HASH=""
DELIVERY_ID_HASH=""
resolve_ref_into \
  TRUSTED_SENDER_ID_HASH \
  "${ZOHO_CLIQ_TRUSTED_SENDER_ID_HASH:-}" \
  "${ZOHO_CLIQ_TRUSTED_SENDER_ID:-}" \
  "trusted_sender_hash_missing" || exit $?
resolve_ref_into \
  TRUSTED_MESSAGE_ID_HASH \
  "${ZOHO_CLIQ_TRUSTED_MESSAGE_ID_HASH:-}" \
  "${ZOHO_CLIQ_TRUSTED_MESSAGE_ID:-}" \
  "trusted_message_hash_missing" || exit $?
resolve_ref_into \
  DELIVERY_ID_HASH \
  "${ZOHO_CLIQ_DELIVERY_ID_HASH:-}" \
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
