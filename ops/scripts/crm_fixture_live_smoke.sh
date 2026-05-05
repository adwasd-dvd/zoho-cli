#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEFAULT_ZOHO_BIN="$ROOT/.venv/bin/zoho"
if [[ -x "$DEFAULT_ZOHO_BIN" ]]; then
  ZOHO_BIN="${ZOHO_BIN:-$DEFAULT_ZOHO_BIN}"
else
  ZOHO_BIN="${ZOHO_BIN:-zoho}"
fi
JQ_BIN="${JQ_BIN:-jq}"

MODULE="${ZOHO_CRM_FIXTURE_MODULE:-Leads}"
DUPLICATE_FIELD="${ZOHO_CRM_FIXTURE_DUPLICATE_FIELD:-Email}"
PAYLOAD_FILE="${ZOHO_CRM_FIXTURE_PAYLOAD_FILE:-}"
SMOKE_RUN_ID="${ZOHO_CRM_FIXTURE_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
SMOKE_RUN_ID="$(printf '%s' "$SMOKE_RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
IDEMPOTENCY_KEY="${ZOHO_CRM_FIXTURE_IDEMPOTENCY_KEY:-crm-fixture-$SMOKE_RUN_ID}"
REPORT_DIR="${ZOHO_CRM_FIXTURE_REPORT_DIR:-$ROOT/tests/auto_pilot/reports}"
AUDIT_FILE="${ZOHO_CRM_FIXTURE_AUDIT_FILE:-$REPORT_DIR/crm_fixture_audit_$SMOKE_RUN_ID.jsonl}"
CLEANUP_PLAN="${ZOHO_CRM_FIXTURE_CLEANUP_PLAN:-}"
EXECUTE="${ZOHO_CRM_FIXTURE_EXECUTE:-0}"

if [[ -z "$PAYLOAD_FILE" ]]; then
  printf 'error=ZOHO_CRM_FIXTURE_PAYLOAD_FILE_required\n' >&2
  exit 2
fi
if [[ ! -f "$PAYLOAD_FILE" ]]; then
  printf 'error=payload_file_not_found path=%s\n' "$PAYLOAD_FILE" >&2
  exit 2
fi
if ! command -v "$JQ_BIN" >/dev/null 2>&1; then
  printf 'error=jq_required\n' >&2
  exit 2
fi

PAYLOAD_PLACEHOLDER_EMAIL_COUNT="$("$JQ_BIN" -r '
  def records:
    if type == "object" and (.data? | type) == "array" then .data[]
    elif type == "array" then .[]
    else .
    end;
  [
    records
    | .Email? // empty
    | tostring
    | ascii_downcase
    | select((contains("example.invalid")) or (contains("replace-me")))
  ]
  | length
' "$PAYLOAD_FILE")"

mkdir -p "$REPORT_DIR"

PLAN_JSON="$REPORT_DIR/crm_fixture_upsert_plan_$SMOKE_RUN_ID.json"
GATE_JSON="$REPORT_DIR/crm_fixture_upsert_gate_$SMOKE_RUN_ID.json"
FIXTURE_PLAN_JSON="$REPORT_DIR/crm_fixture_plan_$SMOKE_RUN_ID.json"
EXECUTE_PLAN_JSON="$REPORT_DIR/crm_fixture_execute_plan_$SMOKE_RUN_ID.json"
EXECUTE_RESULT_JSON="$REPORT_DIR/crm_fixture_execute_result_$SMOKE_RUN_ID.json"
AUDIT_SUMMARY_JSON="$REPORT_DIR/crm_fixture_audit_summary_$SMOKE_RUN_ID.json"
SUMMARY_JSON="$REPORT_DIR/crm_fixture_live_smoke_summary_$SMOKE_RUN_ID.json"

run_json() {
  local label="$1"
  local output="$2"
  shift 2
  printf '\n== %s ==\n' "$label"
  "$@" >"$output"
  "$JQ_BIN" -c '{status: (.status // .decision // "ok"), policyId: (.policyId // ""), liveWritesEnabled: (.liveWritesEnabled // null), blockingReasons: (.blockingReasons // [])}' "$output"
}

run_json "crm upsert dry-run" "$PLAN_JSON" "$ZOHO_BIN" crm upsert \
  --module "$MODULE" \
  --data-file "$PAYLOAD_FILE" \
  --duplicate-check-field "$DUPLICATE_FIELD" \
  --idempotency-key "$IDEMPOTENCY_KEY" \
  --audit-file "$AUDIT_FILE"

PAYLOAD_DIGEST="$("$JQ_BIN" -r '.payloadDigest' "$PLAN_JSON")"

run_json "crm upsert gate" "$GATE_JSON" "$ZOHO_BIN" crm upsert-gate \
  --module "$MODULE" \
  --check-auth \
  --audit-file "$AUDIT_FILE"

run_json "crm fixture plan" "$FIXTURE_PLAN_JSON" "$ZOHO_BIN" crm fixture-plan \
  --module "$MODULE" \
  --duplicate-check-field "$DUPLICATE_FIELD" \
  --idempotency-key "$IDEMPOTENCY_KEY" \
  --payload-digest "$PAYLOAD_DIGEST" \
  --audit-file "$AUDIT_FILE"

EXECUTE_PLAN_ARGS=(
  "$ZOHO_BIN" crm fixture-execute
  --module "$MODULE"
  --data-file "$PAYLOAD_FILE"
  --duplicate-check-field "$DUPLICATE_FIELD"
  --idempotency-key "$IDEMPOTENCY_KEY"
  --payload-digest "$PAYLOAD_DIGEST"
  --audit-file "$AUDIT_FILE"
)
if [[ -n "$CLEANUP_PLAN" ]]; then
  EXECUTE_PLAN_ARGS+=(--cleanup-plan "$CLEANUP_PLAN")
fi
run_json "crm fixture execute dry-run" "$EXECUTE_PLAN_JSON" "${EXECUTE_PLAN_ARGS[@]}"

REQUIRED_APPROVAL="$("$JQ_BIN" -r '.requiredApproval' "$EXECUTE_PLAN_JSON")"
LIVE_RESULT_RECORDED=false

if [[ "$EXECUTE" == "1" ]]; then
  if [[ "${ZOHO_CRM_ALLOW_LIVE_FIXTURE:-}" != "1" ]]; then
    printf '\n== crm fixture live execution blocked ==\n'
    printf 'reason=ZOHO_CRM_ALLOW_LIVE_FIXTURE_not_set\n' >&2
    exit 2
  fi
  if [[ "$PAYLOAD_PLACEHOLDER_EMAIL_COUNT" != "0" ]]; then
    printf '\n== crm fixture live execution blocked ==\n'
    printf 'reason=fixture_payload_placeholder_email\n' >&2
    exit 2
  fi
  if [[ -z "$CLEANUP_PLAN" ]]; then
    printf '\n== crm fixture live execution blocked ==\n'
    printf 'reason=ZOHO_CRM_FIXTURE_CLEANUP_PLAN_required\n' >&2
    exit 2
  fi

  run_json "crm fixture execute live" "$EXECUTE_RESULT_JSON" "$ZOHO_BIN" crm fixture-execute \
    --module "$MODULE" \
    --data-file "$PAYLOAD_FILE" \
    --duplicate-check-field "$DUPLICATE_FIELD" \
    --idempotency-key "$IDEMPOTENCY_KEY" \
    --payload-digest "$PAYLOAD_DIGEST" \
    --fixture-approval "$REQUIRED_APPROVAL" \
    --cleanup-plan "$CLEANUP_PLAN" \
    --execute \
    --audit-file "$AUDIT_FILE"
  LIVE_RESULT_RECORDED=true
else
  printf '\n== crm fixture live execution skipped ==\n'
  printf 'reason=ZOHO_CRM_FIXTURE_EXECUTE_not_1\n'
fi

run_json "crm write audit summary" "$AUDIT_SUMMARY_JSON" "$ZOHO_BIN" crm write-audit \
  --audit-file "$AUDIT_FILE" \
  --operation upsert \
  --module "$MODULE" \
  --limit 50

"$JQ_BIN" -n \
  --arg runId "$SMOKE_RUN_ID" \
  --arg module "$MODULE" \
  --arg duplicateField "$DUPLICATE_FIELD" \
  --arg idempotencyKey "$IDEMPOTENCY_KEY" \
  --arg payloadDigest "$PAYLOAD_DIGEST" \
  --arg requiredApproval "$REQUIRED_APPROVAL" \
  --arg auditFile "$AUDIT_FILE" \
  --arg planReport "$PLAN_JSON" \
  --arg gateReport "$GATE_JSON" \
  --arg fixturePlanReport "$FIXTURE_PLAN_JSON" \
  --arg executePlanReport "$EXECUTE_PLAN_JSON" \
  --arg executeResultReport "$EXECUTE_RESULT_JSON" \
  --arg auditSummaryReport "$AUDIT_SUMMARY_JSON" \
  --argjson payloadPlaceholderEmailCount "$PAYLOAD_PLACEHOLDER_EMAIL_COUNT" \
  --argjson executeRequested "$([[ "$EXECUTE" == "1" ]] && echo true || echo false)" \
  --argjson liveResultRecorded "$LIVE_RESULT_RECORDED" \
  '{
    summaryVersion: 1,
    runId: $runId,
    module: $module,
    duplicateField: $duplicateField,
    idempotencyKey: $idempotencyKey,
    payloadDigest: $payloadDigest,
    requiredApproval: $requiredApproval,
    auditFile: $auditFile,
    payloadTemplatePlaceholders: {
      emailCount: $payloadPlaceholderEmailCount
    },
    executeRequested: $executeRequested,
    liveResultRecorded: $liveResultRecorded,
    reports: {
      upsertPlan: $planReport,
      upsertGate: $gateReport,
      fixturePlan: $fixturePlanReport,
      fixtureExecutePlan: $executePlanReport,
      fixtureExecuteResult: $executeResultReport,
      auditSummary: $auditSummaryReport
    },
    redactionContract: {
      rawFieldValuesStored: false,
      rawApprovalStored: false,
      rawCleanupPlanStored: false,
      rawApiResponseStored: false
    }
  }' >"$SUMMARY_JSON"

printf '\n== crm fixture smoke summary ==\n'
"$JQ_BIN" -c . "$SUMMARY_JSON"
