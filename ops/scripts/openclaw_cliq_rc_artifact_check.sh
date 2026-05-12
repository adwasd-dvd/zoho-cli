#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
JQ_BIN="${JQ_BIN:-jq}"
TAR_BIN="${TAR_BIN:-tar}"
SHASUM_BIN="${SHASUM_BIN:-shasum}"
RUN_ID="${OPENCLAW_CLIQ_ARTIFACT_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT_DIR="${OPENCLAW_CLIQ_ARTIFACT_REPORT_DIR:-"$ROOT/tests/auto_pilot/reports"}"
REPORT_FILE="${OPENCLAW_CLIQ_ARTIFACT_REPORT_FILE:-"$REPORT_DIR/openclaw_cliq_rc_artifact_check_$RUN_ID.json"}"
PACK_SUMMARY_FILE="${OPENCLAW_CLIQ_PACK_SUMMARY_FILE:-}"
TARBALL_PATH_OVERRIDE="${OPENCLAW_CLIQ_TARBALL_PATH:-}"
EXPECTED_PACKAGE_NAME="${OPENCLAW_CLIQ_EXPECTED_PACKAGE_NAME:-@adwasd/openclaw-zoho-cliq}"
EXPECTED_VERSION="${OPENCLAW_CLIQ_EXPECTED_VERSION:-0.4.0-rc.1}"
EXPECTED_PLUGIN_ID="${OPENCLAW_CLIQ_EXPECTED_PLUGIN_ID:-zoho-cliq}"
EXPECTED_CHANNEL_ID="${OPENCLAW_CLIQ_EXPECTED_CHANNEL_ID:-cliq}"
EXPECTED_INTEGRITY_PLACEHOLDER="${OPENCLAW_CLIQ_EXPECTED_INTEGRITY_PLACEHOLDER:-<filled-at-release>}"

emit_tool_error() {
  local error="$1"
  printf '{"schemaVersion":1,"kind":"openclaw_cliq_rc_artifact_check","runId":"%s","checkedAt":"%s","status":"error","error":"%s"}\n' "$RUN_ID" "$CHECKED_AT" "$error"
}

latest_report() {
  local pattern="$1"
  find "$REPORT_DIR" -maxdepth 1 -type f -name "$pattern" -print 2>/dev/null | sort | tail -n 1
}

sanitize_blocker_suffix() {
  printf '%s' "$1" | tr -c 'A-Za-z0-9' '_'
}

command -v "$JQ_BIN" >/dev/null 2>&1 || {
  emit_tool_error "jq_required"
  exit 2
}
command -v "$TAR_BIN" >/dev/null 2>&1 || {
  emit_tool_error "tar_required"
  exit 2
}
command -v "$SHASUM_BIN" >/dev/null 2>&1 || {
  emit_tool_error "shasum_required"
  exit 2
}

mkdir -p "$REPORT_DIR"

if [[ -z "$PACK_SUMMARY_FILE" ]]; then
  PACK_SUMMARY_FILE="$(latest_report "openclaw_cliq_rc_pack_summary_*.json")"
fi

BLOCKERS=()
add_blocker() {
  BLOCKERS+=("$1")
}

SUMMARY_READY=false
SUMMARY_SLURP="/dev/null"
if [[ -n "$PACK_SUMMARY_FILE" && -f "$PACK_SUMMARY_FILE" ]]; then
  SUMMARY_READY=true
  SUMMARY_SLURP="$PACK_SUMMARY_FILE"
else
  add_blocker "pack_summary_missing"
fi

SUMMARY_STATUS=null
SUMMARY_PACKAGE_NAME=null
SUMMARY_VERSION=null
SUMMARY_FILENAME=null
SUMMARY_TARBALL_PATH=null
SUMMARY_SHASUM=null
SUMMARY_INTEGRITY=null
SUMMARY_PUBLISH_PERFORMED=null
SUMMARY_VERSION_BUMPED=null

if [[ "$SUMMARY_READY" == true ]]; then
  SUMMARY_STATUS="$("$JQ_BIN" -r '.status // "null"' "$PACK_SUMMARY_FILE")"
  SUMMARY_PACKAGE_NAME="$("$JQ_BIN" -r '.pack.name // "null"' "$PACK_SUMMARY_FILE")"
  SUMMARY_VERSION="$("$JQ_BIN" -r '.pack.version // "null"' "$PACK_SUMMARY_FILE")"
  SUMMARY_FILENAME="$("$JQ_BIN" -r '.pack.filename // "null"' "$PACK_SUMMARY_FILE")"
  SUMMARY_TARBALL_PATH="$("$JQ_BIN" -r '.pack.tarballPath // "null"' "$PACK_SUMMARY_FILE")"
  SUMMARY_SHASUM="$("$JQ_BIN" -r '.pack.shasum // "null"' "$PACK_SUMMARY_FILE")"
  SUMMARY_INTEGRITY="$("$JQ_BIN" -r '.pack.integrity // "null"' "$PACK_SUMMARY_FILE")"
  SUMMARY_PUBLISH_PERFORMED="$("$JQ_BIN" -r 'if ((.releasePosture // {}) | has("publishPerformed")) then .releasePosture.publishPerformed else "null" end' "$PACK_SUMMARY_FILE")"
  SUMMARY_VERSION_BUMPED="$("$JQ_BIN" -r 'if ((.releasePosture // {}) | has("versionBumped")) then .releasePosture.versionBumped else "null" end' "$PACK_SUMMARY_FILE")"

  [[ "$SUMMARY_STATUS" == "passed" ]] || add_blocker "pack_summary_not_passed"
  [[ "$SUMMARY_PACKAGE_NAME" == "$EXPECTED_PACKAGE_NAME" ]] || add_blocker "pack_name_mismatch"
  [[ "$SUMMARY_VERSION" == "$EXPECTED_VERSION" ]] || add_blocker "pack_version_mismatch"
  [[ "$SUMMARY_PUBLISH_PERFORMED" == "false" ]] || add_blocker "pack_publish_performed"
  [[ "$SUMMARY_VERSION_BUMPED" == "false" ]] || add_blocker "pack_version_bumped"
fi

TARBALL_PATH="$TARBALL_PATH_OVERRIDE"
if [[ -z "$TARBALL_PATH" && "$SUMMARY_TARBALL_PATH" != "null" ]]; then
  TARBALL_PATH="$SUMMARY_TARBALL_PATH"
fi

if [[ -z "$TARBALL_PATH" || ! -f "$TARBALL_PATH" ]]; then
  add_blocker "tarball_missing"
fi

ENTRY_LIST_FILE="$REPORT_DIR/openclaw_cliq_rc_artifact_entries_$RUN_ID.txt"
PACKAGE_JSON_FILE="$REPORT_DIR/openclaw_cliq_rc_artifact_package_$RUN_ID.json"
MANIFEST_JSON_FILE="$REPORT_DIR/openclaw_cliq_rc_artifact_manifest_$RUN_ID.json"
ACTUAL_SHASUM=null
ACTUAL_SIZE=0
ENTRY_COUNT=0
PACKAGE_JSON_READY=false
MANIFEST_JSON_READY=false

REQUIRED_ENTRIES=(
  "package/package.json"
  "package/openclaw.plugin.json"
  "package/README.md"
  "package/skill/SKILL.md"
  "package/dist/index.js"
  "package/dist/setup-entry.js"
  "package/dist/src/channel.js"
  "package/dist/src/native-dispatch.js"
  "package/dist/src/webhook.js"
  "package/dist/src/zoho-cli.js"
)

if [[ -n "$TARBALL_PATH" && -f "$TARBALL_PATH" ]]; then
  ACTUAL_SHASUM="$("$SHASUM_BIN" -a 1 "$TARBALL_PATH" | awk '{print $1}')"
  ACTUAL_SIZE="$(wc -c <"$TARBALL_PATH" | tr -d ' ')"
  if [[ "$SUMMARY_SHASUM" != "null" && "$ACTUAL_SHASUM" != "$SUMMARY_SHASUM" ]]; then
    add_blocker "tarball_shasum_mismatch"
  fi

  if "$TAR_BIN" -tzf "$TARBALL_PATH" >"$ENTRY_LIST_FILE"; then
    ENTRY_COUNT="$(wc -l <"$ENTRY_LIST_FILE" | tr -d ' ')"
    for entry in "${REQUIRED_ENTRIES[@]}"; do
      if ! grep -Fxq "$entry" "$ENTRY_LIST_FILE"; then
        add_blocker "required_entry_missing_$(sanitize_blocker_suffix "$entry")"
      fi
    done
  else
    : >"$ENTRY_LIST_FILE"
    add_blocker "tarball_list_failed"
  fi

  if "$TAR_BIN" -xOf "$TARBALL_PATH" package/package.json >"$PACKAGE_JSON_FILE" 2>/dev/null; then
    PACKAGE_JSON_READY=true
  else
    printf '{}\n' >"$PACKAGE_JSON_FILE"
    add_blocker "package_json_missing_in_tar"
  fi

  if "$TAR_BIN" -xOf "$TARBALL_PATH" package/openclaw.plugin.json >"$MANIFEST_JSON_FILE" 2>/dev/null; then
    MANIFEST_JSON_READY=true
  else
    printf '{}\n' >"$MANIFEST_JSON_FILE"
    add_blocker "manifest_json_missing_in_tar"
  fi
else
  : >"$ENTRY_LIST_FILE"
  printf '{}\n' >"$PACKAGE_JSON_FILE"
  printf '{}\n' >"$MANIFEST_JSON_FILE"
fi

if [[ "$PACKAGE_JSON_READY" == true ]]; then
  ARTIFACT_PACKAGE_NAME="$("$JQ_BIN" -r '.name // "null"' "$PACKAGE_JSON_FILE")"
  ARTIFACT_VERSION="$("$JQ_BIN" -r '.version // "null"' "$PACKAGE_JSON_FILE")"
  ARTIFACT_CHANNEL_ID="$("$JQ_BIN" -r '.openclaw.channel.id // "null"' "$PACKAGE_JSON_FILE")"
  ARTIFACT_EXPECTED_INTEGRITY="$("$JQ_BIN" -r '.openclaw.install.expectedIntegrity // "null"' "$PACKAGE_JSON_FILE")"
  [[ "$ARTIFACT_PACKAGE_NAME" == "$EXPECTED_PACKAGE_NAME" ]] || add_blocker "artifact_package_name_mismatch"
  [[ "$ARTIFACT_VERSION" == "$EXPECTED_VERSION" ]] || add_blocker "artifact_version_mismatch"
  [[ "$ARTIFACT_CHANNEL_ID" == "$EXPECTED_CHANNEL_ID" ]] || add_blocker "artifact_channel_id_mismatch"
  [[ "$ARTIFACT_EXPECTED_INTEGRITY" == "$EXPECTED_INTEGRITY_PLACEHOLDER" ]] || add_blocker "expected_integrity_not_placeholder"
fi

if [[ "$MANIFEST_JSON_READY" == true ]]; then
  MANIFEST_PLUGIN_ID="$("$JQ_BIN" -r '.id // "null"' "$MANIFEST_JSON_FILE")"
  MANIFEST_CHANNEL_PRESENT="$("$JQ_BIN" -r --arg channel "$EXPECTED_CHANNEL_ID" '(.channels // []) | index($channel) != null' "$MANIFEST_JSON_FILE")"
  [[ "$MANIFEST_PLUGIN_ID" == "$EXPECTED_PLUGIN_ID" ]] || add_blocker "manifest_plugin_id_mismatch"
  [[ "$MANIFEST_CHANNEL_PRESENT" == "true" ]] || add_blocker "manifest_channel_missing"
fi

if [[ "${#BLOCKERS[@]}" -eq 0 ]]; then
  BLOCKERS_JSON="[]"
else
  BLOCKERS_JSON="$("$JQ_BIN" -n '$ARGS.positional' --args "${BLOCKERS[@]}")"
fi
STATUS="artifact_verified"
if [[ "$("$JQ_BIN" -r 'length' <<<"$BLOCKERS_JSON")" != "0" ]]; then
  STATUS="blocked"
fi

"$JQ_BIN" -n \
  --arg runId "$RUN_ID" \
  --arg checkedAt "$CHECKED_AT" \
  --arg status "$STATUS" \
  --argjson blockers "$BLOCKERS_JSON" \
  --argjson packSummaryReady "$SUMMARY_READY" \
  --arg packSummaryFile "$(basename "${PACK_SUMMARY_FILE:-}")" \
  --arg summaryStatus "$SUMMARY_STATUS" \
  --arg summaryPackageName "$SUMMARY_PACKAGE_NAME" \
  --arg summaryVersion "$SUMMARY_VERSION" \
  --arg summaryFilename "$SUMMARY_FILENAME" \
  --arg summaryShasum "$SUMMARY_SHASUM" \
  --arg summaryIntegrity "$SUMMARY_INTEGRITY" \
  --arg summaryPublishPerformed "$SUMMARY_PUBLISH_PERFORMED" \
  --arg summaryVersionBumped "$SUMMARY_VERSION_BUMPED" \
  --arg tarballFilename "$(basename "${TARBALL_PATH:-}")" \
  --arg actualShasum "$ACTUAL_SHASUM" \
  --argjson actualSize "$ACTUAL_SIZE" \
  --argjson entryCount "$ENTRY_COUNT" \
  --arg expectedIntegrityPlaceholder "$EXPECTED_INTEGRITY_PLACEHOLDER" \
  --slurpfile package "$PACKAGE_JSON_FILE" \
  --slurpfile manifest "$MANIFEST_JSON_FILE" \
  --rawfile entries "$ENTRY_LIST_FILE" \
  '($package[0]) as $pkg
  | ($manifest[0]) as $manifest
  | {
      schemaVersion: 1,
      kind: "openclaw_cliq_rc_artifact_check",
      runId: $runId,
      checkedAt: $checkedAt,
      status: $status,
      blockers: $blockers,
      pack: {
        summaryReady: $packSummaryReady,
        summaryFile: $packSummaryFile,
        status: (if $summaryStatus == "null" then null else $summaryStatus end),
        packageName: (if $summaryPackageName == "null" then null else $summaryPackageName end),
        version: (if $summaryVersion == "null" then null else $summaryVersion end),
        filename: (if $summaryFilename == "null" then null else $summaryFilename end),
        shasum: (if $summaryShasum == "null" then null else $summaryShasum end),
        integrity: (if $summaryIntegrity == "null" then null else $summaryIntegrity end),
        publishPerformed: (
          if $summaryPublishPerformed == "true" then true
          elif $summaryPublishPerformed == "false" then false
          else null end
        ),
        versionBumped: (
          if $summaryVersionBumped == "true" then true
          elif $summaryVersionBumped == "false" then false
          else null end
        )
      },
      artifact: {
        filename: $tarballFilename,
        size: $actualSize,
        shasum: (if $actualShasum == "null" then null else $actualShasum end),
        shasumMatchesPackSummary: (
          if $summaryShasum == "null" or $actualShasum == "null" then null
          else $summaryShasum == $actualShasum end
        ),
        entryCount: $entryCount,
        requiredEntries: [
          "package/package.json",
          "package/openclaw.plugin.json",
          "package/README.md",
          "package/skill/SKILL.md",
          "package/dist/index.js",
          "package/dist/setup-entry.js",
          "package/dist/src/channel.js",
          "package/dist/src/native-dispatch.js",
          "package/dist/src/webhook.js",
          "package/dist/src/zoho-cli.js"
        ],
        entries: (($entries | split("\n")) | map(select(length > 0)))
      },
      package: {
        name: ($pkg.name // null),
        version: ($pkg.version // null),
        channelId: ($pkg.openclaw.channel.id // null),
        expectedIntegrityState: (
          if ($pkg.openclaw.install.expectedIntegrity // null) == $expectedIntegrityPlaceholder
          then "placeholder"
          else "filled_or_unexpected"
          end
        )
      },
      manifest: {
        id: ($manifest.id // null),
        channels: ($manifest.channels // [])
      },
      releasePosture: {
        publishPerformed: false,
        tagCreated: false,
        versionBumped: false,
        expectedIntegrityAction: "fill_after_publish",
        installVerifiedWithoutPublish: true
      }
    }' >"$REPORT_FILE"

"$JQ_BIN" -c . "$REPORT_FILE"

if [[ "$STATUS" != "artifact_verified" ]]; then
  exit 1
fi
