#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
CURL_BIN="${CURL_BIN:-curl}"
PUBLIC_WEBHOOK_URL="${ZOHO_CLIQ_PUBLIC_WEBHOOK_URL:-}"
REPORT_FILE="${ZOHO_CLIQ_PUBLIC_CALLBACK_REPORT_FILE:-}"
RUN_ID="${ZOHO_CLIQ_PUBLIC_CALLBACK_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
ALLOW_INSECURE="${ZOHO_CLIQ_ALLOW_INSECURE_PUBLIC_WEBHOOK:-0}"

secret_from_env="${ZOHO_CLIQ_WEBHOOK_SECRET:-}"
if [[ -z "$secret_from_env" ]] && command -v launchctl >/dev/null 2>&1; then
  secret_from_env="$(launchctl getenv ZOHO_CLIQ_WEBHOOK_SECRET || true)"
fi

json_string() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  printf '"%s"' "$value"
}

emit_payload() {
  local payload="$1"
  printf '%s\n' "$payload"
  if [[ -n "$REPORT_FILE" ]]; then
    mkdir -p "$(dirname "$REPORT_FILE")"
    printf '%s\n' "$payload" > "$REPORT_FILE"
  fi
}

emit_error() {
  local error="$1"
  local payload
  payload="$(
    printf '{'
    printf '"schemaVersion":1,'
    printf '"kind":"openclaw_cliq_public_callback_smoke",'
    printf '"runId":'
    json_string "$RUN_ID"
    printf ',"checkedAt":'
    json_string "$CHECKED_AT"
    printf ',"status":"error","error":'
    json_string "$error"
    printf '}'
  )"
  emit_payload "$payload"
}

is_placeholder_value() {
  local value="$1"
  local lowered
  lowered="$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]')"
  [[ "$value" == *"<"* ]] && return 0
  [[ "$value" == *">"* ]] && return 0
  [[ "$lowered" == *"replace-me"* ]] && return 0
  [[ "$lowered" == *"replace_with"* ]] && return 0
  [[ "$lowered" == *"replace-with"* ]] && return 0
  [[ "$lowered" == *"placeholder"* ]] && return 0
  [[ "$lowered" == *"example.invalid"* ]] && return 0
  return 1
}

post_status() {
  "$CURL_BIN" -sS -o /dev/null -w '%{http_code}' \
    -X POST "$PUBLIC_WEBHOOK_URL" \
    -H 'Content-Type: application/json' \
    "$@"
}

if [[ -z "$PUBLIC_WEBHOOK_URL" ]]; then
  emit_error "public_webhook_url_missing"
  exit 2
fi
if is_placeholder_value "$PUBLIC_WEBHOOK_URL"; then
  emit_error "public_webhook_url_placeholder"
  exit 2
fi
if ! command -v "$CURL_BIN" >/dev/null 2>&1; then
  emit_error "curl_missing"
  exit 2
fi
if [[ -z "$secret_from_env" ]]; then
  emit_error "webhook_secret_missing"
  exit 2
fi

scheme="${PUBLIC_WEBHOOK_URL%%:*}"
url_without_scheme="${PUBLIC_WEBHOOK_URL#*://}"
host="$url_without_scheme"
path="/"
if [[ "$url_without_scheme" == */* ]]; then
  host="${url_without_scheme%%/*}"
  path="/${url_without_scheme#*/}"
fi
if [[ "$scheme" != "https" ]]; then
  if [[ "$scheme" == "http" && "$ALLOW_INSECURE" == "1" ]]; then
    :
  else
    emit_error "public_webhook_url_requires_https"
    exit 2
  fi
fi
if [[ -z "$host" || "$host" == "$PUBLIC_WEBHOOK_URL" ]]; then
  emit_error "public_webhook_url_invalid"
  exit 2
fi

missing_payload='{"handler":"welcome","message":{"id":"M-PUBLIC-CALLBACK-MISSING","text":"safe smoke"},"user":{"id":"smoke"},"chat":{"chatId":"smoke","chatType":"dm"}}'
auth_payload='{"handler":"welcome","message":{"id":"M-PUBLIC-CALLBACK-AUTH","text":"safe smoke"},"user":{"id":"smoke"},"chat":{"chatId":"smoke","chatType":"dm"}}'

set +e
missing_status="$(post_status --data "$missing_payload")"
missing_exit=$?
auth_status="$(post_status -H "X-Cliq-Webhook-Secret: $secret_from_env" --data "$auth_payload")"
auth_exit=$?
set -e

overall_status="public_callback_verified"
error=""
if [[ "$missing_exit" -ne 0 ]]; then
  overall_status="error"
  error="missing_secret_request_failed"
elif [[ "$auth_exit" -ne 0 ]]; then
  overall_status="error"
  error="authenticated_request_failed"
elif [[ "$missing_status" != "401" ]]; then
  overall_status="error"
  error="missing_secret_status_mismatch"
elif [[ "$auth_status" != "200" ]]; then
  overall_status="error"
  error="authenticated_status_mismatch"
fi

payload="$(
  printf '{'
  printf '"schemaVersion":1,'
  printf '"kind":"openclaw_cliq_public_callback_smoke",'
  printf '"runId":'
  json_string "$RUN_ID"
  printf ',"checkedAt":'
  json_string "$CHECKED_AT"
  printf ',"status":'
  json_string "$overall_status"
  if [[ -n "$error" ]]; then
    printf ',"error":'
    json_string "$error"
  fi
  printf ',"webhook":{"scheme":'
  json_string "$scheme"
  printf ',"host":'
  json_string "$host"
  printf ',"path":'
  json_string "$path"
  printf '},'
  printf '"checks":{"missingSecret":{"expectedStatus":401,"actualStatus":'
  json_string "$missing_status"
  printf '},"authenticatedUnsupportedHandler":{"expectedStatus":200,"actualStatus":'
  json_string "$auth_status"
  printf '}},'
  printf '"redaction":{"rawWebhookPayloadStored":false,"responseBodyStored":false,"secretsStored":false}'
  printf '}'
)"
emit_payload "$payload"

if [[ "$overall_status" != "public_callback_verified" ]]; then
  exit 1
fi
