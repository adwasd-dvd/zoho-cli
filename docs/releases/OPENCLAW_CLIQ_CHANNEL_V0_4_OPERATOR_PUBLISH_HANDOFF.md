# OpenClaw Cliq channel v0.4 operator publish handoff

This handoff starts only after the local no-publish promotion check reports
`ready_for_operator_publish`.

Current baseline:

- Package: `@adwasd/openclaw-zoho-cliq`
- Version: `0.4.0-rc.1`
- Tarball: `adwasd-openclaw-zoho-cliq-0.4.0-rc.1.tgz`
- Local pack integrity:
  `sha512-tOZ8qARh62jh8fQKQ/f1ClihYwofq59qjJXnI9TDdMyZrjjG0V+4pzV6SqJ1a8wnoBmoLkqFhCL+gH6p/fGrfg==`
- Local pack shasum: `9fca0282ff0c6bfeec6d6158d1bb6fab3f63bcc5`
- Trusted reply evidence: `trusted_reply_recorded`
- Local artifact check: `artifact_verified`
- Local OpenClaw install smoke: `install_smoke_passed`
- Handoff manifest:
  `openclaw_cliq_rc_operator_handoff_manifest_20260512T055900Z-ingress-diagnostic-rc-restore-manifest.json`
- Latest source drift guard:
  `openclaw_cliq_rc_source_drift_check_20260512T094343Z-crm-report-metadata-postcommit-source.json`

## Non-automated approval boundary

Do not let an agent perform these actions without explicit operator approval:

1. `npm publish` or any npm promotion command.
2. Git tag creation or GitHub release creation.
3. Filling `openclaw.install.expectedIntegrity`.
4. Marking a durable production tunnel/gateway decision complete.

The placeholder `openclaw.install.expectedIntegrity=<filled-at-release>` is
correct before publish. Fill it only after the approved artifact is published
and the published integrity is known.

## Required preflight

Run these immediately before any publish/tag action:

```bash
git status --short

NPM_CONFIG_CACHE=/private/tmp/zoho-cli-npm-cache \
OPENCLAW_CLIQ_PACK_RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-operator-pack" \
  ops/scripts/openclaw_cliq_rc_pack.sh

OPENCLAW_CLIQ_ARTIFACT_RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-operator-artifact" \
  ops/scripts/openclaw_cliq_rc_artifact_check.sh

OPENCLAW_CLIQ_INSTALL_RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-operator-install" \
  ops/scripts/openclaw_cliq_rc_install_smoke.sh

OPENCLAW_CLIQ_PROMOTION_RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-operator" \
  ops/scripts/openclaw_cliq_rc_promotion_check.sh

OPENCLAW_CLIQ_OPERATOR_BUNDLE_RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-operator-bundle" \
  ops/scripts/openclaw_cliq_rc_operator_publish_bundle.sh

OPENCLAW_CLIQ_RELEASE_NOTES_RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-operator-draft" \
  ops/scripts/openclaw_cliq_rc_release_notes_draft.sh

OPENCLAW_CLIQ_PUBLISH_PLAN_RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-operator-plan" \
  ops/scripts/openclaw_cliq_rc_publish_plan.sh

OPENCLAW_CLIQ_HANDOFF_MANIFEST_RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-operator-manifest" \
  ops/scripts/openclaw_cliq_rc_operator_handoff_manifest.sh

OPENCLAW_CLIQ_SOURCE_DRIFT_RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-source-drift" \
  ops/scripts/openclaw_cliq_rc_source_drift_check.sh

# Optional after the operator chooses one publish path:
OPENCLAW_CLIQ_OPERATOR_PUBLISH_PATH=<local_operator_rc|npm_rc_publish|github_release_artifact> \
OPENCLAW_CLIQ_PUBLISH_PLAN_RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-selected-path" \
  ops/scripts/openclaw_cliq_rc_publish_plan.sh

OPENCLAW_CLIQ_SELECTION_REVIEW_RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-selection-review" \
  ops/scripts/openclaw_cliq_rc_operator_selection_review.sh

OPENCLAW_CLIQ_DECISION_PACKET_RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-decision-packet" \
  ops/scripts/openclaw_cliq_rc_operator_decision_packet.sh

./.venv/bin/python -m pytest -q \
  tests/test_auto_pilot_scripts.py::test_openclaw_cliq_rc_promotion_check_requires_ready_local_evidence \
  tests/test_auto_pilot_scripts.py::test_openclaw_cliq_rc_promotion_check_blocks_published_integrity_too_early \
  tests/test_auto_pilot_scripts.py::test_openclaw_cliq_rc_operator_publish_bundle_collects_ready_evidence \
  tests/test_auto_pilot_scripts.py::test_openclaw_cliq_rc_release_notes_draft_uses_ready_operator_bundle \
  tests/test_auto_pilot_scripts.py::test_openclaw_cliq_rc_publish_plan_uses_ready_bundle_and_draft \
  tests/test_auto_pilot_scripts.py::test_openclaw_cliq_rc_operator_handoff_manifest_indexes_ready_packet \
  tests/test_auto_pilot_scripts.py::test_openclaw_cliq_rc_source_drift_check_allows_non_package_head_drift \
  tests/test_auto_pilot_scripts.py::test_openclaw_cliq_rc_operator_selection_review_indexes_selected_path \
  tests/test_auto_pilot_scripts.py::test_openclaw_cliq_rc_operator_decision_packet_awaits_publish_path \
  tests/test_auto_pilot_scripts.py::test_openclaw_cliq_rc_artifact_check_verifies_tarball_contract \
  tests/test_auto_pilot_scripts.py::test_openclaw_cliq_rc_install_smoke_installs_verified_artifact \
  tests/test_openclaw_channel_contract.py::test_openclaw_cliq_channel_rc_checklist_has_cut_contract \
  tests/test_markdown_update.py
```

Expected local pre-publish posture:

- `status=ready_for_operator_publish`
- `blockers=[]`
- `expectedIntegrityState=placeholder`
- `pack.publishPerformed=false`
- `pack.versionBumped=false`
- `artifact.status=artifact_verified`
- `install.status=install_smoke_passed`
- `trustedReply.status=trusted_reply_recorded`
- `operatorBundle.status=operator_publish_bundle_ready`
- release notes draft says no publish/tag/release/integrity fill was performed
- publish plan reports `operator_publish_plan_ready` and
  `agentMayExecutePlan=false`
- handoff manifest reports `operator_handoff_manifest_ready`
- source drift check reports `package_source_unchanged`; it may report
  `repoChangedSinceManifest=true` after CRM/docs/state commits, but must keep
  `packageDrift.packageChangedSinceManifest=false`
- before the operator chooses a path, selection review blocks with
  `publish_path_not_selected` and `nextAction=operator_select_publish_path`
- after the operator chooses a path and reruns the publish plan, selection
  review reports `operator_publish_selection_ready`,
  `requiresExplicitOperatorApproval=true`, and `agentMayExecuteSelectedPath=false`
- decision packet reports `awaiting_operator_publish_path` before a path is
  selected, or `operator_publish_selection_ready` after a path is selected,
  while keeping `agentMayExecuteSelectedPath=false`
- `npmPromotionRequiresOperatorApproval=true`

The promotion preflight is intentionally strict: `ready_for_operator_publish`
requires the pack summary, artifact check, install smoke, trusted reply evidence,
placeholder `expectedIntegrity`, and no publish/tag/version-bump posture to all
be present at the same time.
The operator bundle is the read-only review packet for that posture; it must
keep `agentMayPublish=false`, `agentMayTag=false`, and
`agentMayFillExpectedIntegrity=false`.
The release-notes draft is also read-only; it is generated from the operator
bundle and is not a publish action.
The publish plan is read-only too; it can preview local/operator, npm RC, and
GitHub artifact paths, but it must keep publish/tag/release/integrity-fill
actions operator-only.
The handoff manifest is the final read-only packet index. It must tie the
operator bundle, release-notes draft, publish plan, artifact facts, and source
commit together before any operator publish decision.
The source drift check is the no-repack guard for later unrelated commits: it
compares the handoff manifest source commit to current `HEAD` and blocks with
`package_source_drift_detected`, `package_worktree_dirty`,
`package_index_dirty`, or `package_untracked_files` if
`integrations/openclaw-channel-cliq/` changed after the manifest. If only
CRM/docs/state files changed, it reports `package_source_unchanged` so the
operator knows the RC tarball is still current for package code.
The selected path review is also read-only. It combines the selected publish
plan plus source drift guard into one JSON packet, but it never runs the
selected command. It exists so agents can help validate the operator's chosen
path without crossing the publish/tag/release boundary.
The decision packet is the preferred one-command agent handoff. It reruns the
read-only publish plan, source drift guard, and selected path review, then
returns either `awaiting_operator_publish_path` or
`operator_publish_selection_ready` without executing publish/tag/release
commands.

## Operator publish choices

Choose exactly one path:

1. Local/operator RC only: keep the tarball under `.tmp/openclaw-cliq-rc-pack`,
   distribute it manually, and do not fill `expectedIntegrity`.
2. npm RC publish: publish `@adwasd/openclaw-zoho-cliq@0.4.0-rc.1`, capture
   the registry integrity, then fill `openclaw.install.expectedIntegrity`.
3. GitHub release artifact: attach the tarball to a release or prerelease,
   record the artifact digest, and document that install path separately from
   npm.

Do not mix paths in one release note. If npm and GitHub artifacts are both
used, record which artifact is canonical for OpenClaw install metadata.

## Post-publish checks

After the approved publish path finishes:

1. Update `openclaw.install.expectedIntegrity` only when using npm as the
   canonical install source.
2. Update `docs/releases/CHANGELOG.next.md` with the published artifact source.
3. Install the published artifact in a Temp-HOME OpenClaw profile.
4. Run `plugins inspect`, `plugins doctor`, `channels status`, and
   `channels capabilities`.
5. Re-run focused OpenClaw Cliq docs/tests and `make ci`.
6. Commit and push the post-publish metadata/evidence slice.

## Abort conditions

Abort and do not publish if any of these appear:

- `token_refresh_rate_limited` during live checks: wait for cooldown.
- `expected_integrity_not_placeholder` before publish approval.
- `pack_publish_performed` or `pack_version_bumped` in local preflight.
- `artifact_report_missing`, `artifact_not_verified`,
  `artifact_shasum_not_verified`, or `artifact_expected_integrity_not_placeholder`
  in local preflight.
- `install_smoke_missing`, `install_smoke_not_passed`,
  `install_artifact_not_verified`, `install_publish_performed`, or
  `install_version_bumped` in local preflight.
- `promotion_report_missing`, `promotion_not_ready`,
  `operator_publish_bundle_ready` absent, or any `agentMayPublish=true`,
  `agentMayTag=true`, or `agentMayFillExpectedIntegrity=true` in the operator
  bundle.
- `operator_bundle_missing`, `operator_bundle_not_ready`,
  `agent_publish_permission_unexpected`, `agent_tag_permission_unexpected`, or
  `agent_integrity_fill_permission_unexpected` in the release-notes draft step.
- `release_notes_draft_unsafe`, `expected_integrity_not_placeholder`, or
  `operator_publish_plan_ready` absent in the publish-plan step.
- `agentMayExecutePlan=false` absent from the publish plan.
- `publish_plan_permission_unexpected`, `operator_bundle_file_mismatch`,
  `release_notes_draft_file_mismatch`, `artifact_shasum_mismatch`, or
  `operator_handoff_manifest_ready` absent in the handoff manifest.
- `tarball_shasum_mismatch`, `artifact_version_mismatch`, or
  `required_entry_missing_*` in the local artifact check.
- `artifact_not_verified`, `plugin_install_failed`, `plugin_inspect_failed`,
  `plugin_id_missing`, `channel_id_missing`, or `plugin_doctor_failed` in the
  local install smoke.
- `trusted_reply_not_recorded`.
- Any raw webhook payload, raw message body, raw reply body, or secret marker in
  release evidence.

## Release-note facts

Release notes should say:

- Public callback was verified through the operator Cloudflare route.
- One trusted Cliq Bot Mention reached `zoho-employee-test`, used
  `openai-codex/gpt-5.3-codex`, and delivered exactly one Cliq reply.
- Durable production tunnel/gateway selection remains an operations decision
  unless the operator explicitly finalizes it during this release.
