#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
JQ_BIN="${JQ_BIN:-jq}"

MODULE="${ZOHO_CRM_FIXTURE_MODULE:-Leads}"
DUPLICATE_FIELD="${ZOHO_CRM_FIXTURE_DUPLICATE_FIELD:-Email}"
PAYLOAD_FILE="${ZOHO_CRM_FIXTURE_PAYLOAD_FILE:-}"
CLEANUP_PLAN="${ZOHO_CRM_FIXTURE_CLEANUP_PLAN:-}"
RUN_ID="${ZOHO_CRM_FIXTURE_PREFLIGHT_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT_DIR="${ZOHO_CRM_FIXTURE_PREFLIGHT_REPORT_DIR:-$ROOT/tests/auto_pilot/reports}"
PREFLIGHT_FILE="${ZOHO_CRM_FIXTURE_PREFLIGHT_FILE:-$REPORT_DIR/crm_fixture_payload_preflight_$RUN_ID.json}"

case "${ZOHO_CRM_FIXTURE_REQUIRE_CLEANUP:-1}" in
  1|true|TRUE|yes|YES)
    REQUIRE_CLEANUP=true
    ;;
  *)
    REQUIRE_CLEANUP=false
    ;;
esac

emit_error() {
  local error="$1"
  printf '{"schemaVersion":1,"kind":"crm_fixture_payload_preflight","runId":"%s","checkedAt":"%s","status":"error","error":"%s"}\n' "$RUN_ID" "$CHECKED_AT" "$error"
}

json_basename() {
  local path="${1:-}"
  if [[ -z "$path" ]]; then
    "$JQ_BIN" -n 'null'
  else
    "$JQ_BIN" -n --arg value "$(basename "$path")" '$value'
  fi
}

command -v "$JQ_BIN" >/dev/null 2>&1 || {
  emit_error "jq_required"
  exit 2
}

mkdir -p "$REPORT_DIR"

PAYLOAD_EXISTS=false
PAYLOAD_JSON_VALID=false
PAYLOAD_SUMMARY='{}'

if [[ -n "$PAYLOAD_FILE" && -f "$PAYLOAD_FILE" ]]; then
  PAYLOAD_EXISTS=true
  if "$JQ_BIN" -e . "$PAYLOAD_FILE" >/dev/null 2>&1; then
    PAYLOAD_JSON_VALID=true
    PAYLOAD_SUMMARY="$("$JQ_BIN" -c --arg module "$MODULE" '
      def records:
        if type == "object" and (.data? | type) == "array" then .data
        elif type == "array" then .
        elif type == "object" then [.]
        else []
        end;
      def shape:
        if type == "object" and (.data? | type) == "array" then "zoho_data_object"
        elif type == "array" then "record_array"
        elif type == "object" then "single_record"
        else "unsupported"
        end;
      def required_fields:
        if $module == "Leads" then ["Last_Name", "Company", "Email"]
        else []
        end;
      records as $records
      | ($records[0] // {}) as $first
      | required_fields as $required
      | {
          shape: shape,
          recordCount: ($records | length),
          requiredFields: $required,
          missingRequiredFields: [
            $required[]
            | select((($first[.] // "") | tostring | length) == 0)
          ],
          placeholderEmailCount: ([
            $records[]?
            | .Email? // empty
            | tostring
            | ascii_downcase
            | select((contains("example.invalid")) or (contains("replace-me")))
          ] | length)
        }
    ' "$PAYLOAD_FILE")"
  fi
fi

PAYLOAD_BASENAME="$(json_basename "$PAYLOAD_FILE")"
if [[ -n "$CLEANUP_PLAN" ]]; then
  CLEANUP_PLAN_PRESENT=true
else
  CLEANUP_PLAN_PRESENT=false
fi
CLEANUP_PLAN_LENGTH="${#CLEANUP_PLAN}"
CLEANUP_PLAN_LOWER="$(printf '%s' "$CLEANUP_PLAN" | tr '[:upper:]' '[:lower:]')"
CLEANUP_ACTION_PRESENT=false
CLEANUP_TARGET_PRESENT=false
if [[ -n "$CLEANUP_PLAN_LOWER" ]]; then
  case "$CLEANUP_PLAN_LOWER" in
    *delete*|*remove*|*archive*|*cleanup*|*"clean up"*|*update*)
      CLEANUP_ACTION_PRESENT=true
      ;;
  esac
  case "$CLEANUP_PLAN_LOWER" in
    *record*|*lead*|*fixture*|*email*|*duplicate*|*id*)
      CLEANUP_TARGET_PRESENT=true
      ;;
  esac
fi

PAYLOAD="$("$JQ_BIN" -n \
  --arg runId "$RUN_ID" \
  --arg checkedAt "$CHECKED_AT" \
  --arg module "$MODULE" \
  --arg duplicateField "$DUPLICATE_FIELD" \
  --arg payloadPath "$PAYLOAD_FILE" \
  --argjson payloadFile "$PAYLOAD_BASENAME" \
  --argjson payloadExists "$PAYLOAD_EXISTS" \
  --argjson payloadJsonValid "$PAYLOAD_JSON_VALID" \
  --argjson payloadSummary "$PAYLOAD_SUMMARY" \
  --argjson cleanupPlanPresent "$CLEANUP_PLAN_PRESENT" \
  --argjson cleanupPlanLength "$CLEANUP_PLAN_LENGTH" \
  --argjson cleanupActionPresent "$CLEANUP_ACTION_PRESENT" \
  --argjson cleanupTargetPresent "$CLEANUP_TARGET_PRESENT" \
  --argjson requireCleanup "$REQUIRE_CLEANUP" \
  '
  ($payloadSummary.recordCount // null) as $recordCount
  | ($payloadSummary.missingRequiredFields // []) as $missingRequiredFields
  | ($payloadSummary.placeholderEmailCount // null) as $placeholderEmailCount
  | [
      (if $payloadPath != "" then empty else "payload_file_required" end),
      (if $payloadPath == "" or $payloadExists then empty else "payload_file_missing" end),
      (if $payloadPath == "" or ($payloadExists | not) or $payloadJsonValid then empty else "payload_json_invalid" end),
      (if $module == "Leads" then empty else "fixture_module_not_supported_by_preflight" end),
      (if ($payloadJsonValid | not) then empty elif $recordCount == 1 then empty else "payload_record_count_not_one" end),
      (if ($payloadJsonValid | not) then empty elif ($missingRequiredFields | length) == 0 then empty else "required_fields_missing" end),
      (if ($payloadJsonValid | not) then empty elif ($placeholderEmailCount // 0) == 0 then empty else "fixture_payload_placeholder_email" end),
      (if $requireCleanup and ($cleanupPlanPresent | not) then "cleanup_plan_missing" else empty end),
      (if $cleanupPlanPresent and $cleanupPlanLength < 20 then "cleanup_plan_too_short" else empty end),
      (if $cleanupPlanPresent and ($cleanupActionPresent | not) then "cleanup_plan_action_missing" else empty end),
      (if $cleanupPlanPresent and ($cleanupTargetPresent | not) then "cleanup_plan_target_missing" else empty end)
    ] as $blockers
  | {
      schemaVersion: 1,
      kind: "crm_fixture_payload_preflight",
      runId: $runId,
      checkedAt: $checkedAt,
      status: (if ($blockers | length) == 0 then "payload_preflight_ready" else "blocked" end),
      blockers: $blockers,
      payload: {
        file: $payloadFile,
        pathProvided: ($payloadPath != ""),
        exists: $payloadExists,
        jsonValid: $payloadJsonValid,
        module: $module,
        duplicateField: $duplicateField,
        supportedModule: ($module == "Leads"),
        shape: ($payloadSummary.shape // null),
        recordCount: $recordCount,
        requiredFields: ($payloadSummary.requiredFields // []),
        missingRequiredFields: $missingRequiredFields,
        placeholderEmailCount: $placeholderEmailCount,
        placeholderFree: (($placeholderEmailCount // 1) == 0),
        dedicatedFixtureCandidate: (
          $payloadJsonValid
          and $recordCount == 1
          and ($module == "Leads")
          and (($missingRequiredFields | length) == 0)
          and (($placeholderEmailCount // 1) == 0)
        )
      },
      cleanup: {
        required: $requireCleanup,
        present: $cleanupPlanPresent,
        lengthBucket: (
          if ($cleanupPlanPresent | not) then "missing"
          elif $cleanupPlanLength < 20 then "too_short"
          else "sufficient"
          end
        ),
        actionPresent: $cleanupActionPresent,
        targetPresent: $cleanupTargetPresent,
        qualityReady: (
          $cleanupPlanPresent
          and ($cleanupPlanLength >= 20)
          and $cleanupActionPresent
          and $cleanupTargetPresent
        ),
        rawCleanupPlanStored: false
      },
      redactionContract: {
        rawPayloadStored: false,
        rawFieldValuesStored: false,
        rawEmailStored: false,
        rawCleanupPlanStored: false
      },
      releasePosture: {
        normalUpsertExecuteBlocked: true,
        agentMayRunNormalUpsertExecute: false,
        agentMayRunLiveFixture: false,
        requiresOperatorApprovalBeforeLive: true
      },
      nextAction: (
        if ($blockers | index("payload_file_required")) or ($blockers | index("payload_file_missing")) then "provide_fixture_payload_file"
        elif ($blockers | index("payload_json_invalid")) then "fix_fixture_payload_json"
        elif ($blockers | index("cleanup_plan_missing")) then "provide_cleanup_plan"
        elif ($blockers | index("cleanup_plan_too_short")) or ($blockers | index("cleanup_plan_action_missing")) or ($blockers | index("cleanup_plan_target_missing")) then "improve_cleanup_plan"
        elif ($blockers | length) != 0 then "fix_fixture_payload"
        else "run_crm_fixture_live_smoke_dry_run"
        end
      )
    }
  ')"

printf '%s\n' "$PAYLOAD" >"$PREFLIGHT_FILE"
printf '%s\n' "$PAYLOAD"

if [[ "$("$JQ_BIN" -r '.status' "$PREFLIGHT_FILE")" == "blocked" ]]; then
  exit 1
fi
