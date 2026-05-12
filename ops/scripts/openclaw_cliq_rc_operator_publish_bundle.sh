#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
JQ_BIN="${JQ_BIN:-jq}"
RUN_ID="${OPENCLAW_CLIQ_OPERATOR_BUNDLE_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT_DIR="${OPENCLAW_CLIQ_OPERATOR_BUNDLE_REPORT_DIR:-"$ROOT/tests/auto_pilot/reports"}"
BUNDLE_REPORT_FILE="${OPENCLAW_CLIQ_OPERATOR_BUNDLE_REPORT_FILE:-"$REPORT_DIR/openclaw_cliq_rc_operator_publish_bundle_$RUN_ID.json"}"
EXPECTED_PACKAGE_NAME="${OPENCLAW_CLIQ_EXPECTED_PACKAGE_NAME:-@adwasd/openclaw-zoho-cliq}"
EXPECTED_VERSION="${OPENCLAW_CLIQ_EXPECTED_VERSION:-0.4.0-rc.1}"
PACK_SUMMARY_FILE="${OPENCLAW_CLIQ_PACK_SUMMARY_FILE:-}"
ARTIFACT_REPORT_FILE="${OPENCLAW_CLIQ_ARTIFACT_REPORT_FILE:-}"
INSTALL_SMOKE_FILE="${OPENCLAW_CLIQ_INSTALL_SMOKE_FILE:-}"
PROMOTION_REPORT_FILE="${OPENCLAW_CLIQ_PROMOTION_REPORT_FILE:-}"
TRUSTED_REPLY_CHECK_FILE="${OPENCLAW_CLIQ_TRUSTED_REPLY_CHECK_FILE:-}"

emit_error() {
  local error="$1"
  printf '{"schemaVersion":1,"kind":"openclaw_cliq_rc_operator_publish_bundle","runId":"%s","checkedAt":"%s","status":"error","error":"%s"}\n' "$RUN_ID" "$CHECKED_AT" "$error"
}

latest_report() {
  local pattern="$1"
  find "$REPORT_DIR" -maxdepth 1 -type f -name "$pattern" -print 2>/dev/null | sort | tail -n 1
}

basename_or_null() {
  local path="${1:-}"
  if [[ -z "$path" ]]; then
    printf 'null'
  else
    "$JQ_BIN" -n --arg value "$(basename "$path")" '$value'
  fi
}

command -v "$JQ_BIN" >/dev/null 2>&1 || {
  emit_error "jq_required"
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
if [[ -z "$PROMOTION_REPORT_FILE" ]]; then
  PROMOTION_REPORT_FILE="$(latest_report "openclaw_cliq_rc_promotion_check_*.json")"
fi
if [[ -z "$TRUSTED_REPLY_CHECK_FILE" ]]; then
  TRUSTED_REPLY_CHECK_FILE="$(latest_report "openclaw_cliq_trusted_reply_check_*.json")"
fi

PACK_SUMMARY_EXISTS=false
ARTIFACT_EXISTS=false
INSTALL_SMOKE_EXISTS=false
PROMOTION_EXISTS=false
TRUSTED_REPLY_EXISTS=false
PACK_SUMMARY_SLURP_FILE="/dev/null"
ARTIFACT_SLURP_FILE="/dev/null"
INSTALL_SMOKE_SLURP_FILE="/dev/null"
PROMOTION_SLURP_FILE="/dev/null"
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
if [[ -n "$PROMOTION_REPORT_FILE" && -f "$PROMOTION_REPORT_FILE" ]]; then
  PROMOTION_EXISTS=true
  PROMOTION_SLURP_FILE="$PROMOTION_REPORT_FILE"
fi
if [[ -n "$TRUSTED_REPLY_CHECK_FILE" && -f "$TRUSTED_REPLY_CHECK_FILE" ]]; then
  TRUSTED_REPLY_EXISTS=true
  TRUSTED_REPLY_SLURP_FILE="$TRUSTED_REPLY_CHECK_FILE"
fi

PACK_SUMMARY_BASENAME="$(basename_or_null "$PACK_SUMMARY_FILE")"
ARTIFACT_BASENAME="$(basename_or_null "$ARTIFACT_REPORT_FILE")"
INSTALL_SMOKE_BASENAME="$(basename_or_null "$INSTALL_SMOKE_FILE")"
PROMOTION_BASENAME="$(basename_or_null "$PROMOTION_REPORT_FILE")"
TRUSTED_REPLY_BASENAME="$(basename_or_null "$TRUSTED_REPLY_CHECK_FILE")"

PAYLOAD="$("$JQ_BIN" -n \
  --arg runId "$RUN_ID" \
  --arg checkedAt "$CHECKED_AT" \
  --arg expectedPackageName "$EXPECTED_PACKAGE_NAME" \
  --arg expectedVersion "$EXPECTED_VERSION" \
  --argjson packSummaryExists "$PACK_SUMMARY_EXISTS" \
  --argjson artifactExists "$ARTIFACT_EXISTS" \
  --argjson installSmokeExists "$INSTALL_SMOKE_EXISTS" \
  --argjson promotionExists "$PROMOTION_EXISTS" \
  --argjson trustedReplyExists "$TRUSTED_REPLY_EXISTS" \
  --argjson packSummaryFile "$PACK_SUMMARY_BASENAME" \
  --argjson artifactReportFile "$ARTIFACT_BASENAME" \
  --argjson installSmokeFile "$INSTALL_SMOKE_BASENAME" \
  --argjson promotionReportFile "$PROMOTION_BASENAME" \
  --argjson trustedReplyFile "$TRUSTED_REPLY_BASENAME" \
  --slurpfile pack "$PACK_SUMMARY_SLURP_FILE" \
  --slurpfile artifact "$ARTIFACT_SLURP_FILE" \
  --slurpfile install "$INSTALL_SMOKE_SLURP_FILE" \
  --slurpfile promotion "$PROMOTION_SLURP_FILE" \
  --slurpfile trusted "$TRUSTED_REPLY_SLURP_FILE" \
  '
  (if $packSummaryExists then $pack[0] else {} end) as $packReport
  | (if $artifactExists then $artifact[0] else {} end) as $artifactReport
  | (if $installSmokeExists then $install[0] else {} end) as $installReport
  | (if $promotionExists then $promotion[0] else {} end) as $promotionReport
  | (if $trustedReplyExists then $trusted[0] else {} end) as $trustedReport
  | [
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
      (if $promotionExists then empty else "promotion_report_missing" end),
      (if ($promotionReport.status // "") == "ready_for_operator_publish" then empty else "promotion_not_ready" end),
      (if (($promotionReport.blockers // []) | length) == 0 then empty else "promotion_has_blockers" end),
      (if ($promotionReport.package.expectedIntegrityState // "") == "placeholder" then empty else "promotion_expected_integrity_not_placeholder" end),
      (if ($promotionReport.releasePosture.publishPerformed // false) == false then empty else "promotion_publish_performed" end),
      (if ($promotionReport.releasePosture.tagCreated // false) == false then empty else "promotion_tag_created" end),
      (if ($promotionReport.releasePosture.npmPromotionRequiresOperatorApproval // false) == true then empty else "npm_operator_approval_flag_missing" end),
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
      kind: "openclaw_cliq_rc_operator_publish_bundle",
      runId: $runId,
      checkedAt: $checkedAt,
      status: (if ($blockers | length) == 0 then "operator_publish_bundle_ready" else "blocked" end),
      blockers: $blockers,
      package: {
        name: ($promotionReport.package.name // $artifactReport.package.name // $packReport.pack.name // null),
        version: ($promotionReport.package.version // $artifactReport.package.version // $packReport.pack.version // null),
        expectedIntegrityState: ($promotionReport.package.expectedIntegrityState // $artifactReport.package.expectedIntegrityState // null)
      },
      artifact: {
        filename: ($artifactReport.artifact.filename // $packReport.pack.filename // null),
        shasum: ($artifactReport.artifact.shasum // $packReport.pack.shasum // null),
        integrity: ($packReport.pack.integrity // null),
        shasumMatchesPackSummary: ($artifactReport.artifact.shasumMatchesPackSummary // null)
      },
      reports: {
        packSummary: {
          ready: $packSummaryExists,
          file: $packSummaryFile,
          status: ($packReport.status // null)
        },
        artifact: {
          ready: $artifactExists,
          file: $artifactReportFile,
          status: ($artifactReport.status // null)
        },
        installSmoke: {
          ready: $installSmokeExists,
          file: $installSmokeFile,
          status: ($installReport.status // null),
          commandStatuses: [($installReport.commands // [])[] | {name, status, exitCode}]
        },
        promotion: {
          ready: $promotionExists,
          file: $promotionReportFile,
          status: ($promotionReport.status // null),
          blockers: ($promotionReport.blockers // [])
        },
        trustedReply: {
          ready: $trustedReplyExists,
          file: $trustedReplyFile,
          status: ($trustedReport.status // null),
          redaction: ($trustedReport.redaction // null)
        }
      },
      releasePosture: {
        publishPerformed: false,
        tagCreated: false,
        npmPromotionRequiresOperatorApproval: true,
        agentMayPublish: false,
        agentMayTag: false,
        agentMayFillExpectedIntegrity: false,
        expectedIntegrityAction: "operator_fills_after_approved_publish_only"
      },
      allowedPublishPaths: [
        "local_operator_rc",
        "npm_rc_publish",
        "github_release_artifact"
      ],
      nextAction: (if ($blockers | length) == 0 then "operator_select_publish_path" else "fix_blockers" end)
    }
  ')"

printf '%s\n' "$PAYLOAD" > "$BUNDLE_REPORT_FILE"
printf '%s\n' "$PAYLOAD"

if [[ "$("$JQ_BIN" -r '.status' "$BUNDLE_REPORT_FILE")" != "operator_publish_bundle_ready" ]]; then
  exit 1
fi
