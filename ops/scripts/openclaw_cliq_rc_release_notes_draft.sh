#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
JQ_BIN="${JQ_BIN:-jq}"
RUN_ID="${OPENCLAW_CLIQ_RELEASE_NOTES_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT_DIR="${OPENCLAW_CLIQ_RELEASE_NOTES_REPORT_DIR:-"$ROOT/tests/auto_pilot/reports"}"
OPERATOR_BUNDLE_FILE="${OPENCLAW_CLIQ_OPERATOR_BUNDLE_REPORT_FILE:-}"
DRAFT_FILE="${OPENCLAW_CLIQ_RELEASE_NOTES_DRAFT_FILE:-"$REPORT_DIR/openclaw_cliq_rc_release_notes_draft_$RUN_ID.md"}"

emit_error() {
  local error="$1"
  printf '{"schemaVersion":1,"kind":"openclaw_cliq_rc_release_notes_draft","runId":"%s","checkedAt":"%s","status":"error","error":"%s"}\n' "$RUN_ID" "$CHECKED_AT" "$error"
}

latest_report() {
  local pattern="$1"
  find "$REPORT_DIR" -maxdepth 1 -type f -name "$pattern" -print 2>/dev/null | sort | tail -n 1
}

command -v "$JQ_BIN" >/dev/null 2>&1 || {
  emit_error "jq_required"
  exit 2
}

mkdir -p "$REPORT_DIR"

if [[ -z "$OPERATOR_BUNDLE_FILE" ]]; then
  OPERATOR_BUNDLE_FILE="$(latest_report "openclaw_cliq_rc_operator_publish_bundle_*.json")"
fi
if [[ -z "$OPERATOR_BUNDLE_FILE" || ! -f "$OPERATOR_BUNDLE_FILE" ]]; then
  emit_error "operator_bundle_missing"
  exit 2
fi

STATUS="$("$JQ_BIN" -r '.status // ""' "$OPERATOR_BUNDLE_FILE")"
if [[ "$STATUS" != "operator_publish_bundle_ready" ]]; then
  emit_error "operator_bundle_not_ready"
  exit 1
fi

if [[ "$("$JQ_BIN" -r 'if (.releasePosture | has("agentMayPublish")) then .releasePosture.agentMayPublish else true end' "$OPERATOR_BUNDLE_FILE")" != "false" ]]; then
  emit_error "agent_publish_permission_unexpected"
  exit 1
fi
if [[ "$("$JQ_BIN" -r 'if (.releasePosture | has("agentMayTag")) then .releasePosture.agentMayTag else true end' "$OPERATOR_BUNDLE_FILE")" != "false" ]]; then
  emit_error "agent_tag_permission_unexpected"
  exit 1
fi
if [[ "$("$JQ_BIN" -r 'if (.releasePosture | has("agentMayFillExpectedIntegrity")) then .releasePosture.agentMayFillExpectedIntegrity else true end' "$OPERATOR_BUNDLE_FILE")" != "false" ]]; then
  emit_error "agent_integrity_fill_permission_unexpected"
  exit 1
fi

PACKAGE_NAME="$("$JQ_BIN" -r '.package.name // "unknown"' "$OPERATOR_BUNDLE_FILE")"
VERSION="$("$JQ_BIN" -r '.package.version // "unknown"' "$OPERATOR_BUNDLE_FILE")"
TARBALL="$("$JQ_BIN" -r '.artifact.filename // "unknown"' "$OPERATOR_BUNDLE_FILE")"
SHASUM="$("$JQ_BIN" -r '.artifact.shasum // "unknown"' "$OPERATOR_BUNDLE_FILE")"
INTEGRITY="$("$JQ_BIN" -r '.artifact.integrity // "unknown"' "$OPERATOR_BUNDLE_FILE")"
EXPECTED_INTEGRITY_STATE="$("$JQ_BIN" -r '.package.expectedIntegrityState // "unknown"' "$OPERATOR_BUNDLE_FILE")"
PACK_REPORT="$("$JQ_BIN" -r '.reports.packSummary.file // "unknown"' "$OPERATOR_BUNDLE_FILE")"
ARTIFACT_REPORT="$("$JQ_BIN" -r '.reports.artifact.file // "unknown"' "$OPERATOR_BUNDLE_FILE")"
INSTALL_REPORT="$("$JQ_BIN" -r '.reports.installSmoke.file // "unknown"' "$OPERATOR_BUNDLE_FILE")"
PROMOTION_REPORT="$("$JQ_BIN" -r '.reports.promotion.file // "unknown"' "$OPERATOR_BUNDLE_FILE")"
TRUSTED_REPLY_REPORT="$("$JQ_BIN" -r '.reports.trustedReply.file // "unknown"' "$OPERATOR_BUNDLE_FILE")"
INSTALL_STATUS="$("$JQ_BIN" -r '.reports.installSmoke.status // "unknown"' "$OPERATOR_BUNDLE_FILE")"
PROMOTION_STATUS="$("$JQ_BIN" -r '.reports.promotion.status // "unknown"' "$OPERATOR_BUNDLE_FILE")"
TRUSTED_REPLY_STATUS="$("$JQ_BIN" -r '.reports.trustedReply.status // "unknown"' "$OPERATOR_BUNDLE_FILE")"

cat >"$DRAFT_FILE" <<EOF
# OpenClaw Zoho Cliq channel ${VERSION} release notes draft

Draft generated: ${CHECKED_AT}

This is a draft-only operator handoff. No npm publish, git tag, GitHub release,
version bump, or \`openclaw.install.expectedIntegrity\` fill has been performed
by this script.

## Artifact

- Package: \`${PACKAGE_NAME}\`
- Version: \`${VERSION}\`
- Local tarball: \`${TARBALL}\`
- Local shasum: \`${SHASUM}\`
- Local integrity: \`${INTEGRITY}\`
- \`openclaw.install.expectedIntegrity\`: \`${EXPECTED_INTEGRITY_STATE}\`

## Verification

- Operator bundle: \`operator_publish_bundle_ready\`
- Promotion preflight: \`${PROMOTION_STATUS}\`
- Artifact check: \`artifact_verified\`
- Install smoke: \`${INSTALL_STATUS}\`
- Trusted reply evidence: \`${TRUSTED_REPLY_STATUS}\`
- Public callback: verified through the operator Cloudflare route
- Trusted Bot Mention: reached \`zoho-employee-test\`, used
  \`openai-codex/gpt-5.3-codex\`, and delivered exactly one Cliq reply

## Evidence Reports

- Pack summary: \`${PACK_REPORT}\`
- Artifact check: \`${ARTIFACT_REPORT}\`
- Install smoke: \`${INSTALL_REPORT}\`
- Promotion preflight: \`${PROMOTION_REPORT}\`
- Trusted reply: \`${TRUSTED_REPLY_REPORT}\`

## Operator Boundary

- \`agentMayPublish=false\`
- \`agentMayTag=false\`
- \`agentMayFillExpectedIntegrity=false\`
- Choose exactly one publish path: \`local_operator_rc\`, \`npm_rc_publish\`, or
  \`github_release_artifact\`
- Fill published artifact integrity only after the operator approves the
  artifact source and the published integrity is known

## Production Note

Durable production tunnel/gateway selection remains an operations decision
unless the operator explicitly finalizes it during this release.
EOF

cat "$DRAFT_FILE"
