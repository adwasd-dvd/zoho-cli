#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
JQ_BIN="${JQ_BIN:-jq}"
OPENCLAW_BIN="${OPENCLAW_BIN:-openclaw}"
RUN_ID="${OPENCLAW_CLIQ_INSTALL_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT_DIR="${OPENCLAW_CLIQ_INSTALL_REPORT_DIR:-"$ROOT/tests/auto_pilot/reports"}"
REPORT_FILE="${OPENCLAW_CLIQ_INSTALL_REPORT_FILE:-"$REPORT_DIR/openclaw_cliq_rc_install_smoke_$RUN_ID.json"}"
HOME_DIR="${OPENCLAW_CLIQ_INSTALL_HOME:-"$ROOT/.tmp/openclaw-cliq-rc-install-$RUN_ID"}"
PACK_SUMMARY_FILE="${OPENCLAW_CLIQ_PACK_SUMMARY_FILE:-}"
ARTIFACT_REPORT_FILE="${OPENCLAW_CLIQ_ARTIFACT_REPORT_FILE:-}"
INSTALL_SOURCE="${OPENCLAW_CLIQ_INSTALL_SOURCE:-}"
INSTALL_MODE="${OPENCLAW_CLIQ_INSTALL_MODE:-artifact}"
EXPECTED_PLUGIN_ID="${OPENCLAW_CLIQ_EXPECTED_PLUGIN_ID:-zoho-cliq}"
EXPECTED_CHANNEL_ID="${OPENCLAW_CLIQ_EXPECTED_CHANNEL_ID:-cliq}"

emit_tool_error() {
  local error="$1"
  printf '{"schemaVersion":1,"kind":"openclaw_cliq_rc_install_smoke","runId":"%s","checkedAt":"%s","status":"error","error":"%s"}\n' "$RUN_ID" "$CHECKED_AT" "$error"
}

latest_report() {
  local pattern="$1"
  find "$REPORT_DIR" -maxdepth 1 -type f -name "$pattern" -print 2>/dev/null | sort | tail -n 1
}

command -v "$JQ_BIN" >/dev/null 2>&1 || {
  emit_tool_error "jq_required"
  exit 2
}

mkdir -p "$REPORT_DIR"

if [[ -z "$PACK_SUMMARY_FILE" ]]; then
  PACK_SUMMARY_FILE="$(latest_report "openclaw_cliq_rc_pack_summary_*.json")"
fi
if [[ -z "$ARTIFACT_REPORT_FILE" ]]; then
  ARTIFACT_REPORT_FILE="$(latest_report "openclaw_cliq_rc_artifact_check_*.json")"
fi

BLOCKERS=()
add_blocker() {
  BLOCKERS+=("$1")
}

PACK_SUMMARY_READY=false
ARTIFACT_READY=false
PACK_SLURP="/dev/null"
ARTIFACT_SLURP="/dev/null"
ARTIFACT_STATUS=null
TARBALL_PATH=null

if [[ -n "$PACK_SUMMARY_FILE" && -f "$PACK_SUMMARY_FILE" ]]; then
  PACK_SUMMARY_READY=true
  PACK_SLURP="$PACK_SUMMARY_FILE"
  TARBALL_PATH="$("$JQ_BIN" -r '.pack.tarballPath // "null"' "$PACK_SUMMARY_FILE")"
else
  add_blocker "pack_summary_missing"
fi

if [[ -n "$ARTIFACT_REPORT_FILE" && -f "$ARTIFACT_REPORT_FILE" ]]; then
  ARTIFACT_READY=true
  ARTIFACT_SLURP="$ARTIFACT_REPORT_FILE"
  ARTIFACT_STATUS="$("$JQ_BIN" -r '.status // "null"' "$ARTIFACT_REPORT_FILE")"
  [[ "$ARTIFACT_STATUS" == "artifact_verified" ]] || add_blocker "artifact_not_verified"
else
  add_blocker "artifact_report_missing"
fi

SOURCE_TYPE="$INSTALL_MODE"
if [[ -z "$INSTALL_SOURCE" ]]; then
  if [[ "$INSTALL_MODE" == "link" ]]; then
    INSTALL_SOURCE="$ROOT/integrations/openclaw-channel-cliq"
  elif [[ "$TARBALL_PATH" != "null" ]]; then
    INSTALL_SOURCE="$TARBALL_PATH"
  fi
fi

if [[ -z "$INSTALL_SOURCE" || ! -e "$INSTALL_SOURCE" ]]; then
  add_blocker "install_source_missing"
fi

COMMANDS_FILE="$REPORT_DIR/openclaw_cliq_rc_install_smoke_commands_$RUN_ID.jsonl"
: >"$COMMANDS_FILE"

append_command_result() {
  local name="$1"
  local exit_code="$2"
  local stdout_file="$3"
  local stderr_file="$4"
  shift 4
  local command_text="$*"
  command_text="${command_text//$ROOT/\$ROOT}"
  command_text="${command_text//$HOME_DIR/\$OPENCLAW_CLIQ_INSTALL_HOME}"
  "$JQ_BIN" -n \
    --arg name "$name" \
    --argjson exitCode "$exit_code" \
    --arg status "$(if [[ "$exit_code" == "0" ]]; then printf passed; else printf failed; fi)" \
    --arg stdoutFile "$(basename "$stdout_file")" \
    --arg stderrFile "$(basename "$stderr_file")" \
    --arg command "$command_text" \
    '{
      name: $name,
      status: $status,
      exitCode: $exitCode,
      command: $command,
      stdoutFile: $stdoutFile,
      stderrFile: $stderrFile
    }' >>"$COMMANDS_FILE"
}

run_openclaw_step() {
  local name="$1"
  shift
  local stdout_file="$REPORT_DIR/openclaw_cliq_rc_install_smoke_${RUN_ID}_${name}.stdout"
  local stderr_file="$REPORT_DIR/openclaw_cliq_rc_install_smoke_${RUN_ID}_${name}.stderr"
  set +e
  HOME="$HOME_DIR" "$@" >"$stdout_file" 2>"$stderr_file"
  local exit_code=$?
  set -e
  append_command_result "$name" "$exit_code" "$stdout_file" "$stderr_file" "$@"
  return "$exit_code"
}

INSPECT_STDOUT="$REPORT_DIR/openclaw_cliq_rc_install_smoke_${RUN_ID}_inspect.stdout"
INSPECT_EXIT=1

if [[ "${#BLOCKERS[@]}" -eq 0 ]]; then
  mkdir -p "$HOME_DIR"
  if ! command -v "$OPENCLAW_BIN" >/dev/null 2>&1; then
    add_blocker "openclaw_not_found"
  fi
fi

if [[ "${#BLOCKERS[@]}" -eq 0 ]]; then
  run_openclaw_step version "$OPENCLAW_BIN" --version || add_blocker "openclaw_version_failed"

  INSTALL_ARGS=("$OPENCLAW_BIN" plugins install "$INSTALL_SOURCE")
  if [[ "$INSTALL_MODE" == "link" ]]; then
    INSTALL_ARGS+=("--link")
  fi
  run_openclaw_step install "${INSTALL_ARGS[@]}" || add_blocker "plugin_install_failed"

  if run_openclaw_step inspect "$OPENCLAW_BIN" plugins inspect "$EXPECTED_PLUGIN_ID" --json; then
    INSPECT_EXIT=0
  else
    INSPECT_EXIT=$?
  fi
  if [[ "$INSPECT_EXIT" != "0" ]]; then
    add_blocker "plugin_inspect_failed"
  elif ! "$JQ_BIN" empty "$INSPECT_STDOUT" >/dev/null 2>&1; then
    add_blocker "plugin_inspect_invalid_json"
  else
    if [[ "$("$JQ_BIN" -r --arg id "$EXPECTED_PLUGIN_ID" '[.. | strings] | index($id) != null' "$INSPECT_STDOUT")" != "true" ]]; then
      add_blocker "plugin_id_missing"
    fi
    if [[ "$("$JQ_BIN" -r --arg channel "$EXPECTED_CHANNEL_ID" '[.. | strings] | index($channel) != null' "$INSPECT_STDOUT")" != "true" ]]; then
      add_blocker "channel_id_missing"
    fi
  fi

  run_openclaw_step doctor "$OPENCLAW_BIN" plugins doctor || add_blocker "plugin_doctor_failed"
fi

if [[ "${#BLOCKERS[@]}" -eq 0 ]]; then
  BLOCKERS_JSON="[]"
else
  BLOCKERS_JSON="$("$JQ_BIN" -n '$ARGS.positional' --args "${BLOCKERS[@]}")"
fi
COMMANDS_JSON="$("$JQ_BIN" -s . "$COMMANDS_FILE")"
STATUS="install_smoke_passed"
if [[ "$("$JQ_BIN" -r 'length' <<<"$BLOCKERS_JSON")" != "0" ]]; then
  STATUS="blocked"
fi

"$JQ_BIN" -n \
  --arg runId "$RUN_ID" \
  --arg checkedAt "$CHECKED_AT" \
  --arg status "$STATUS" \
  --argjson blockers "$BLOCKERS_JSON" \
  --argjson commands "$COMMANDS_JSON" \
  --argjson packSummaryReady "$PACK_SUMMARY_READY" \
  --argjson artifactReady "$ARTIFACT_READY" \
  --arg packSummaryFile "$(basename "${PACK_SUMMARY_FILE:-}")" \
  --arg artifactReportFile "$(basename "${ARTIFACT_REPORT_FILE:-}")" \
  --arg artifactStatus "$ARTIFACT_STATUS" \
  --arg sourceType "$SOURCE_TYPE" \
  --arg sourceFilename "$(basename "${INSTALL_SOURCE:-}")" \
  --arg homeName "$(basename "$HOME_DIR")" \
  --slurpfile pack "$PACK_SLURP" \
  --slurpfile artifact "$ARTIFACT_SLURP" \
  '{
    schemaVersion: 1,
    kind: "openclaw_cliq_rc_install_smoke",
    runId: $runId,
    checkedAt: $checkedAt,
    status: $status,
    blockers: $blockers,
    source: {
      type: $sourceType,
      filename: $sourceFilename,
      homeName: $homeName
    },
    pack: {
      summaryReady: $packSummaryReady,
      summaryFile: $packSummaryFile,
      filename: (if $packSummaryReady then ($pack[0].pack.filename // null) else null end),
      shasum: (if $packSummaryReady then ($pack[0].pack.shasum // null) else null end),
      integrity: (if $packSummaryReady then ($pack[0].pack.integrity // null) else null end)
    },
    artifact: {
      reportReady: $artifactReady,
      reportFile: $artifactReportFile,
      status: (if $artifactStatus == "null" then null else $artifactStatus end),
      shasumMatchesPackSummary: (
        if $artifactReady then ($artifact[0].artifact.shasumMatchesPackSummary // null) else null end
      )
    },
    commands: $commands,
    releasePosture: {
      publishPerformed: false,
      tagCreated: false,
      versionBumped: false,
      expectedIntegrityAction: "fill_after_publish",
      localInstallSmokeOnly: true
    }
  }' >"$REPORT_FILE"

"$JQ_BIN" -c . "$REPORT_FILE"

if [[ "$STATUS" != "install_smoke_passed" ]]; then
  exit 1
fi
