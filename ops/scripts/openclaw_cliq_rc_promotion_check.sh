#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
JQ_BIN="${JQ_BIN:-jq}"
RUN_ID="${OPENCLAW_CLIQ_PROMOTION_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT_DIR="${OPENCLAW_CLIQ_PROMOTION_REPORT_DIR:-"$ROOT/tests/auto_pilot/reports"}"
PROMOTION_REPORT_FILE="${OPENCLAW_CLIQ_PROMOTION_REPORT_FILE:-"$REPORT_DIR/openclaw_cliq_rc_promotion_check_$RUN_ID.json"}"
PACKAGE_JSON="${OPENCLAW_CLIQ_PACKAGE_JSON:-"$ROOT/integrations/openclaw-channel-cliq/package.json"}"
EXPECTED_PACKAGE_NAME="${OPENCLAW_CLIQ_EXPECTED_PACKAGE_NAME:-@adwasd/openclaw-zoho-cliq}"
EXPECTED_VERSION="${OPENCLAW_CLIQ_EXPECTED_VERSION:-0.4.0-rc.1}"
EXPECTED_INTEGRITY_PLACEHOLDER="${OPENCLAW_CLIQ_EXPECTED_INTEGRITY_PLACEHOLDER:-<filled-at-release>}"
PACK_SUMMARY_FILE="${OPENCLAW_CLIQ_PACK_SUMMARY_FILE:-}"
ARTIFACT_REPORT_FILE="${OPENCLAW_CLIQ_ARTIFACT_REPORT_FILE:-}"
INSTALL_SMOKE_FILE="${OPENCLAW_CLIQ_INSTALL_SMOKE_FILE:-}"
TRUSTED_REPLY_CHECK_FILE="${OPENCLAW_CLIQ_TRUSTED_REPLY_CHECK_FILE:-}"

emit_error() {
  local error="$1"
  printf '{"schemaVersion":1,"kind":"openclaw_cliq_rc_promotion_check","runId":"%s","checkedAt":"%s","status":"error","error":"%s"}\n' "$RUN_ID" "$CHECKED_AT" "$error"
}

latest_report() {
  local pattern="$1"
  find "$REPORT_DIR" -maxdepth 1 -type f -name "$pattern" -print 2>/dev/null | sort | tail -n 1
}

command -v "$JQ_BIN" >/dev/null 2>&1 || {
  emit_error "jq_required"
  exit 2
}
[[ -f "$PACKAGE_JSON" ]] || {
  emit_error "package_json_not_found"
  exit 2
}

mkdir -p "$REPORT_DIR"

if [[ -z "$PACK_SUMMARY_FILE" ]]; then
  PACK_SUMMARY_FILE="$(latest_report "openclaw_cliq_rc_pack_summary_*.json")"
fi
if [[ -z "$ARTIFACT_REPORT_FILE" ]]; then
  ARTIFACT_REPORT_FILE="$(latest_report "openclaw_cliq_rc_artifact_check_*.json")"
fi
if [[ -z "$INSTALL_SMOKE_FILE" ]]; then
  INSTALL_SMOKE_FILE="$(latest_report "openclaw_cliq_rc_install_smoke_*.json")"
fi
if [[ -z "$TRUSTED_REPLY_CHECK_FILE" ]]; then
  TRUSTED_REPLY_CHECK_FILE="$(latest_report "openclaw_cliq_trusted_reply_check_*.json")"
fi

PACK_SUMMARY_EXISTS=false
ARTIFACT_EXISTS=false
INSTALL_SMOKE_EXISTS=false
TRUSTED_REPLY_EXISTS=false
PACK_SUMMARY_SLURP_FILE="/dev/null"
ARTIFACT_SLURP_FILE="/dev/null"
INSTALL_SMOKE_SLURP_FILE="/dev/null"
TRUSTED_REPLY_SLURP_FILE="/dev/null"
if [[ -n "$PACK_SUMMARY_FILE" && -f "$PACK_SUMMARY_FILE" ]]; then
  PACK_SUMMARY_EXISTS=true
  PACK_SUMMARY_SLURP_FILE="$PACK_SUMMARY_FILE"
fi
if [[ -n "$ARTIFACT_REPORT_FILE" && -f "$ARTIFACT_REPORT_FILE" ]]; then
  ARTIFACT_EXISTS=true
  ARTIFACT_SLURP_FILE="$ARTIFACT_REPORT_FILE"
fi
if [[ -n "$INSTALL_SMOKE_FILE" && -f "$INSTALL_SMOKE_FILE" ]]; then
  INSTALL_SMOKE_EXISTS=true
  INSTALL_SMOKE_SLURP_FILE="$INSTALL_SMOKE_FILE"
fi
if [[ -n "$TRUSTED_REPLY_CHECK_FILE" && -f "$TRUSTED_REPLY_CHECK_FILE" ]]; then
  TRUSTED_REPLY_EXISTS=true
  TRUSTED_REPLY_SLURP_FILE="$TRUSTED_REPLY_CHECK_FILE"
fi

PAYLOAD="$("$JQ_BIN" -n \
  --arg runId "$RUN_ID" \
  --arg checkedAt "$CHECKED_AT" \
  --arg expectedPackageName "$EXPECTED_PACKAGE_NAME" \
  --arg expectedVersion "$EXPECTED_VERSION" \
  --arg expectedIntegrityPlaceholder "$EXPECTED_INTEGRITY_PLACEHOLDER" \
  --argjson packSummaryExists "$PACK_SUMMARY_EXISTS" \
  --argjson artifactExists "$ARTIFACT_EXISTS" \
  --argjson installSmokeExists "$INSTALL_SMOKE_EXISTS" \
  --argjson trustedReplyExists "$TRUSTED_REPLY_EXISTS" \
  --slurpfile package "$PACKAGE_JSON" \
  --slurpfile pack "$PACK_SUMMARY_SLURP_FILE" \
  --slurpfile artifact "$ARTIFACT_SLURP_FILE" \
  --slurpfile install "$INSTALL_SMOKE_SLURP_FILE" \
  --slurpfile trusted "$TRUSTED_REPLY_SLURP_FILE" \
  '
  ($package[0]) as $pkg
  | (if $packSummaryExists then $pack[0] else {} end) as $packReport
  | (if $artifactExists then $artifact[0] else {} end) as $artifactReport
  | (if $installSmokeExists then $install[0] else {} end) as $installReport
  | (if $trustedReplyExists then $trusted[0] else {} end) as $trustedReport
  | ($pkg.openclaw.install.expectedIntegrity // "") as $expectedIntegrity
  | [
      (if ($pkg.name // "") == $expectedPackageName then empty else "package_name_mismatch" end),
      (if ($pkg.version // "") == $expectedVersion then empty else "package_version_mismatch" end),
      (if $expectedIntegrity == $expectedIntegrityPlaceholder then empty else "expected_integrity_not_placeholder" end),
      (if $packSummaryExists then empty else "pack_summary_missing" end),
      (if ($packReport.status // "") == "passed" then empty else "pack_summary_not_passed" end),
      (if ($packReport.pack.name // "") == $expectedPackageName then empty else "pack_name_mismatch" end),
      (if ($packReport.pack.version // "") == $expectedVersion then empty else "pack_version_mismatch" end),
      (if ($packReport.releasePosture.publishPerformed // false) == false then empty else "pack_publish_performed" end),
      (if ($packReport.releasePosture.versionBumped // false) == false then empty else "pack_version_bumped" end),
      (if $artifactExists then empty else "artifact_report_missing" end),
      (if ($artifactReport.status // "") == "artifact_verified" then empty else "artifact_not_verified" end),
      (if ($artifactReport.artifact.shasumMatchesPackSummary // false) == true then empty else "artifact_shasum_not_verified" end),
      (if ($artifactReport.package.name // "") == $expectedPackageName then empty else "artifact_package_name_mismatch" end),
      (if ($artifactReport.package.version // "") == $expectedVersion then empty else "artifact_version_mismatch" end),
      (if ($artifactReport.package.expectedIntegrityState // "") == "placeholder" then empty else "artifact_expected_integrity_not_placeholder" end),
      (if $installSmokeExists then empty else "install_smoke_missing" end),
      (if ($installReport.status // "") == "install_smoke_passed" then empty else "install_smoke_not_passed" end),
      (if ($installReport.artifact.status // "") == "artifact_verified" then empty else "install_artifact_not_verified" end),
      (if ($installReport.releasePosture.publishPerformed // false) == false then empty else "install_publish_performed" end),
      (if ($installReport.releasePosture.versionBumped // false) == false then empty else "install_version_bumped" end),
      (if $trustedReplyExists then empty else "trusted_reply_check_missing" end),
      (if ($trustedReport.status // "") == "trusted_reply_recorded" then empty else "trusted_reply_not_recorded" end),
      (if ($trustedReport.redaction.rawWebhookPayloadStored // false) == false then empty else "raw_webhook_payload_stored" end),
      (if ($trustedReport.redaction.rawMessageBodyStored // false) == false then empty else "raw_message_body_stored" end),
      (if ($trustedReport.redaction.rawCliqReplyBodyStored // false) == false then empty else "raw_cliq_reply_body_stored" end),
      (if ($trustedReport.redaction.secretsStored // false) == false then empty else "secrets_stored" end),
      (if ($trustedReport.redaction.secretMarkerPresent // false) == false then empty else "secret_marker_present" end)
    ] as $blockers
  | {
      schemaVersion: 1,
      kind: "openclaw_cliq_rc_promotion_check",
      runId: $runId,
      checkedAt: $checkedAt,
      status: (if ($blockers | length) == 0 then "ready_for_operator_publish" else "blocked" end),
      blockers: $blockers,
      package: {
        name: ($pkg.name // null),
        version: ($pkg.version // null),
        expectedIntegrityState: (if $expectedIntegrity == $expectedIntegrityPlaceholder then "placeholder" else "filled_or_unexpected" end)
      },
      pack: {
        reportReady: $packSummaryExists,
        status: ($packReport.status // null),
        filename: ($packReport.pack.filename // null),
        integrity: ($packReport.pack.integrity // null),
        shasum: ($packReport.pack.shasum // null),
        publishPerformed: (
          if $packSummaryExists and (($packReport.releasePosture // {}) | has("publishPerformed"))
          then $packReport.releasePosture.publishPerformed
          else null
          end
        ),
        versionBumped: (
          if $packSummaryExists and (($packReport.releasePosture // {}) | has("versionBumped"))
          then $packReport.releasePosture.versionBumped
          else null
          end
        )
      },
      artifact: {
        reportReady: $artifactExists,
        status: ($artifactReport.status // null),
        filename: ($artifactReport.artifact.filename // null),
        shasum: ($artifactReport.artifact.shasum // null),
        shasumMatchesPackSummary: (
          if $artifactExists and (($artifactReport.artifact // {}) | has("shasumMatchesPackSummary"))
          then $artifactReport.artifact.shasumMatchesPackSummary
          else null
          end
        )
      },
      installSmoke: {
        reportReady: $installSmokeExists,
        status: ($installReport.status // null),
        source: ($installReport.source // null),
        commandStatuses: (
          if $installSmokeExists then [($installReport.commands // [])[] | {name, status, exitCode}] else [] end
        )
      },
      trustedReply: {
        reportReady: $trustedReplyExists,
        status: ($trustedReport.status // null),
        redaction: ($trustedReport.redaction // null)
      },
      releasePosture: {
        publishPerformed: false,
        tagCreated: false,
        npmPromotionRequiresOperatorApproval: true,
        expectedIntegrityAction: "fill_after_publish"
      }
    }
  ')"

printf '%s\n' "$PAYLOAD" > "$PROMOTION_REPORT_FILE"
printf '%s\n' "$PAYLOAD"

if [[ "$("$JQ_BIN" -r '.status' "$PROMOTION_REPORT_FILE")" != "ready_for_operator_publish" ]]; then
  exit 1
fi
