#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NPM_BIN="${NPM_BIN:-npm}"
JQ_BIN="${JQ_BIN:-jq}"
PACKAGE_DIR="${OPENCLAW_CLIQ_PACKAGE_DIR:-"$ROOT/integrations/openclaw-channel-cliq"}"
REPORT_DIR="${OPENCLAW_CLIQ_PACK_REPORT_DIR:-"$ROOT/tests/auto_pilot/reports"}"
PACK_DIR="${OPENCLAW_CLIQ_PACK_DIR:-"$ROOT/.tmp/openclaw-cliq-rc-pack"}"
RUN_ID="${OPENCLAW_CLIQ_PACK_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
GENERATED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

SUMMARY_PATH="$REPORT_DIR/openclaw_cliq_rc_pack_summary_$RUN_ID.json"
RAW_PACK_PATH="$REPORT_DIR/openclaw_cliq_rc_pack_$RUN_ID.pack.json"

abort() {
  local message="$1"
  local code="${2:-1}"
  printf 'error=%s\n' "$message" >&2
  exit "$code"
}

run_step() {
  printf '\n== %s ==\n' "$1" >&2
  shift
  "$@"
}

command -v "$NPM_BIN" >/dev/null 2>&1 || abort "npm_not_found" 2
command -v "$JQ_BIN" >/dev/null 2>&1 || abort "jq_not_found" 2
[[ -d "$PACKAGE_DIR" ]] || abort "package_dir_not_found" 2
[[ -f "$PACKAGE_DIR/package.json" ]] || abort "package_json_not_found" 2

mkdir -p "$REPORT_DIR" "$PACK_DIR"

run_step "typecheck" "$NPM_BIN" --prefix "$PACKAGE_DIR" run typecheck
run_step "build" "$NPM_BIN" --prefix "$PACKAGE_DIR" run build

printf '\n== npm pack ==\n' >&2
PACK_OUTPUT="$(cd "$PACKAGE_DIR" && "$NPM_BIN" pack --json --pack-destination "$PACK_DIR")"
printf '%s\n' "$PACK_OUTPUT" >"$RAW_PACK_PATH"

PACK_COUNT="$("$JQ_BIN" 'length' "$RAW_PACK_PATH")"
[[ "$PACK_COUNT" == "1" ]] || abort "unexpected_pack_result_count" 2

TARBALL_FILE="$("$JQ_BIN" -r '.[0].filename // empty' "$RAW_PACK_PATH")"
[[ -n "$TARBALL_FILE" ]] || abort "pack_filename_missing" 2
TARBALL_PATH="$PACK_DIR/$TARBALL_FILE"
[[ -f "$TARBALL_PATH" ]] || abort "pack_tarball_missing" 2

"$JQ_BIN" -n \
  --arg runId "$RUN_ID" \
  --arg generatedAt "$GENERATED_AT" \
  --arg packageDir "$PACKAGE_DIR" \
  --arg packDir "$PACK_DIR" \
  --arg tarballPath "$TARBALL_PATH" \
  --arg reportPath "$SUMMARY_PATH" \
  --arg rawPackReport "$RAW_PACK_PATH" \
  --slurpfile pack "$RAW_PACK_PATH" \
  '($pack[0][0]) as $pkg | {
    summaryVersion: 1,
    status: "passed",
    runId: $runId,
    generatedAt: $generatedAt,
    packageDir: $packageDir,
    packDir: $packDir,
    reportPath: $reportPath,
    rawPackReport: $rawPackReport,
    typecheck: {
      status: "passed",
      command: ["npm", "--prefix", $packageDir, "run", "typecheck"]
    },
    build: {
      status: "passed",
      command: ["npm", "--prefix", $packageDir, "run", "build"]
    },
    pack: {
      status: "passed",
      command: ["npm", "pack", "--json", "--pack-destination", $packDir],
      name: $pkg.name,
      version: $pkg.version,
      filename: $pkg.filename,
      tarballPath: $tarballPath,
      size: $pkg.size,
      unpackedSize: $pkg.unpackedSize,
      shasum: $pkg.shasum,
      integrity: $pkg.integrity,
      entryCount: (($pkg.files // []) | length),
      bundled: ($pkg.bundled // [])
    },
    releasePosture: {
      publishPerformed: false,
      versionBumped: false,
      expectedIntegrityPlaceholder: "<filled-at-release>"
    }
  }' >"$SUMMARY_PATH"

"$JQ_BIN" -c . "$SUMMARY_PATH"
