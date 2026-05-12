#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
JQ_BIN="${JQ_BIN:-jq}"
RUN_ID="${OPENCLAW_CLIQ_PUBLISH_PLAN_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT_DIR="${OPENCLAW_CLIQ_PUBLISH_PLAN_REPORT_DIR:-"$ROOT/tests/auto_pilot/reports"}"
OPERATOR_BUNDLE_FILE="${OPENCLAW_CLIQ_OPERATOR_BUNDLE_REPORT_FILE:-}"
RELEASE_NOTES_DRAFT_FILE="${OPENCLAW_CLIQ_RELEASE_NOTES_DRAFT_FILE:-}"
PLAN_FILE="${OPENCLAW_CLIQ_PUBLISH_PLAN_FILE:-"$REPORT_DIR/openclaw_cliq_rc_publish_plan_$RUN_ID.json"}"
SELECTED_PATH="${OPENCLAW_CLIQ_OPERATOR_PUBLISH_PATH:-undecided}"

emit_error() {
  local error="$1"
  printf '{"schemaVersion":1,"kind":"openclaw_cliq_rc_publish_plan","runId":"%s","checkedAt":"%s","status":"error","error":"%s"}\n' "$RUN_ID" "$CHECKED_AT" "$error"
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

if [[ -z "$OPERATOR_BUNDLE_FILE" ]]; then
  OPERATOR_BUNDLE_FILE="$(latest_report "openclaw_cliq_rc_operator_publish_bundle_*.json")"
fi
if [[ -z "$RELEASE_NOTES_DRAFT_FILE" ]]; then
  RELEASE_NOTES_DRAFT_FILE="$(latest_report "openclaw_cliq_rc_release_notes_draft_*.md")"
fi

if [[ -z "$OPERATOR_BUNDLE_FILE" || ! -f "$OPERATOR_BUNDLE_FILE" ]]; then
  emit_error "operator_bundle_missing"
  exit 2
fi
if [[ -z "$RELEASE_NOTES_DRAFT_FILE" || ! -f "$RELEASE_NOTES_DRAFT_FILE" ]]; then
  emit_error "release_notes_draft_missing"
  exit 2
fi

case "$SELECTED_PATH" in
  undecided|local_operator_rc|npm_rc_publish|github_release_artifact) ;;
  *)
    emit_error "invalid_publish_path"
    exit 1
    ;;
esac

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

EXPECTED_INTEGRITY_STATE="$("$JQ_BIN" -r '.package.expectedIntegrityState // ""' "$OPERATOR_BUNDLE_FILE")"
if [[ "$EXPECTED_INTEGRITY_STATE" != "placeholder" ]]; then
  emit_error "expected_integrity_not_placeholder"
  exit 1
fi

if ! grep -Fq "No npm publish, git tag, GitHub release" "$RELEASE_NOTES_DRAFT_FILE"; then
  emit_error "release_notes_draft_unsafe"
  exit 1
fi
for marker in \
  'agentMayPublish=false' \
  'agentMayTag=false' \
  'agentMayFillExpectedIntegrity=false'
do
  if ! grep -Fq "$marker" "$RELEASE_NOTES_DRAFT_FILE"; then
    emit_error "release_notes_draft_missing_permission_marker"
    exit 1
  fi
done

OPERATOR_BUNDLE_BASENAME="$(basename_or_null "$OPERATOR_BUNDLE_FILE")"
RELEASE_NOTES_BASENAME="$(basename_or_null "$RELEASE_NOTES_DRAFT_FILE")"

PAYLOAD="$("$JQ_BIN" -n \
  --arg runId "$RUN_ID" \
  --arg checkedAt "$CHECKED_AT" \
  --arg selectedPath "$SELECTED_PATH" \
  --argjson operatorBundleFile "$OPERATOR_BUNDLE_BASENAME" \
  --argjson releaseNotesDraftFile "$RELEASE_NOTES_BASENAME" \
  --slurpfile bundle "$OPERATOR_BUNDLE_FILE" \
  '
  $bundle[0] as $bundle
  | ($bundle.package.version // "0.4.0-rc.1") as $version
  | ($bundle.package.name // "@adwasd/openclaw-zoho-cliq") as $packageName
  | ($bundle.artifact.filename // "adwasd-openclaw-zoho-cliq-0.4.0-rc.1.tgz") as $artifactFile
  | {
      schemaVersion: 1,
      kind: "openclaw_cliq_rc_publish_plan",
      runId: $runId,
      checkedAt: $checkedAt,
      status: "operator_publish_plan_ready",
      package: {
        name: $packageName,
        version: $version,
        expectedIntegrityState: ($bundle.package.expectedIntegrityState // null)
      },
      artifact: {
        filename: $artifactFile,
        shasum: ($bundle.artifact.shasum // null),
        integrity: ($bundle.artifact.integrity // null),
        pathHint: (".tmp/openclaw-cliq-rc-pack/" + $artifactFile)
      },
      evidence: {
        operatorBundle: {
          file: $operatorBundleFile,
          status: ($bundle.status // null)
        },
        releaseNotesDraft: {
          file: $releaseNotesDraftFile,
          status: "draft_ready"
        },
        promotion: {
          file: ($bundle.reports.promotion.file // null),
          status: ($bundle.reports.promotion.status // null)
        },
        artifact: {
          file: ($bundle.reports.artifact.file // null),
          status: ($bundle.reports.artifact.status // null)
        },
        installSmoke: {
          file: ($bundle.reports.installSmoke.file // null),
          status: ($bundle.reports.installSmoke.status // null)
        },
        trustedReply: {
          file: ($bundle.reports.trustedReply.file // null),
          status: ($bundle.reports.trustedReply.status // null)
        }
      },
      selectedPublishPath: (if $selectedPath == "undecided" then null else $selectedPath end),
      publishPaths: [
        {
          id: "local_operator_rc",
          operatorOnly: true,
          fillsExpectedIntegrity: false,
          description: "Keep the verified tarball as a local/operator RC artifact."
        },
        {
          id: "npm_rc_publish",
          operatorOnly: true,
          fillsExpectedIntegrityAfterPublish: true,
          commandPreview: ["npm", "publish", (".tmp/openclaw-cliq-rc-pack/" + $artifactFile), "--tag", "rc", "--access", "public"]
        },
        {
          id: "github_release_artifact",
          operatorOnly: true,
          fillsExpectedIntegrity: false,
          commandPreview: ["gh", "release", "create", "<operator-approved-rc-tag>", (".tmp/openclaw-cliq-rc-pack/" + $artifactFile), "--prerelease", "--notes-file", "<release-notes-draft-path>"]
        }
      ],
      blockedAgentActions: [
        "npm_publish",
        "npm_dist_tag",
        "git_tag",
        "github_release_create",
        "expectedIntegrity_fill"
      ],
      postPublishChecklist: [
        "capture_published_artifact_source",
        "capture_published_integrity_if_npm_is_canonical",
        "fill_expectedIntegrity_only_after_operator_approval",
        "rerun_temp_home_openclaw_install_smoke",
        "rerun_focused_openclaw_cliq_tests",
        "commit_post_publish_metadata"
      ],
      releasePosture: {
        publishPerformed: false,
        tagCreated: false,
        githubReleaseCreated: false,
        npmPromotionRequiresOperatorApproval: true,
        agentMayPublish: false,
        agentMayTag: false,
        agentMayCreateGithubRelease: false,
        agentMayFillExpectedIntegrity: false,
        agentMayExecutePlan: false,
        expectedIntegrityAction: "operator_fills_after_approved_publish_only"
      },
      nextAction: (if $selectedPath == "undecided" then "operator_select_publish_path" else "operator_review_selected_publish_path" end)
    }
  ')"

printf '%s\n' "$PAYLOAD" > "$PLAN_FILE"
printf '%s\n' "$PAYLOAD"
