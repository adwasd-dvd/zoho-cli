# Lane3 AI user guide (skill/docs/scripts)

This guide is for AI users who already have a working local `zoho` CLI and only need lane3 updates.

## What is lane3

- skill: `skill/SKILL.md`
- skill references: `skill/references/*`
- skill scripts: `skill/scripts/*`
- OpenClaw lane3 docs/scripts: `integrations/openclaw/*`
- native channel planning docs: `docs/architecture/OPENCLAW_CLIQ_CHANNEL_0_4_PLAN.md`, `skill/references/openclaw-cliq-channel.md`, and `integrations/openclaw/CLIQ_CHANNEL_DEVELOPMENT_GUIDE.md`

## Skill-only update (no CLI upgrade)

Use this when local CLI runtime is already working and aligned. This is the default for `zoho-employee-test` in your current setup.

```bash
bash integrations/openclaw/bin/pull_lane3_only.sh \
  --workspace "$HOME/.openclaw/workspace-zoho-employee-test" \
  --branch autobot/zoho-platform
```

## Repository rename alignment

The active GitHub repository is now `adwasd-dvd/zoho-cli`. If the employee
agent already has a local checkout, align the remote before syncing lane3:

```bash
git -C ~/zoho-cli remote set-url origin https://github.com/adwasd-dvd/zoho-cli.git
git -C ~/zoho-cli fetch --prune origin
```

Use `/Users/adwasd/.openclaw/workspace-zoho-employee-test` for the current local
employee-agent workspace unless the user provides another workspace.

What it does:
1. sparse-pulls lane3 paths from GitHub
2. syncs `skill/` into `<workspace>/skills/zoho-cli-employee/`
3. saves lane3 docs snapshot under `<workspace>/lane3-docs/`
4. keeps CLI binary/runtime untouched

## Full update (CLI + skill)

Only use this when user explicitly approves CLI upgrade.

```bash
git -C ~/zoho-cli pull --ff-only
uv tool install --upgrade git+https://github.com/adwasd-dvd/zoho-cli
bash integrations/openclaw/bin/pull_lane3_only.sh --workspace "$HOME/.openclaw/workspace-zoho-employee-test"
```

## Alignment checklist before sync

1. inspect code delta
2. inspect docs delta
3. inspect lane3 delta
4. inspect native channel docs when `cliq-channel-*` or v0.4 planning changed
5. summarize command/flag/output, channel, security, and skill-usage changes
6. sync lane3 locally

Current implementation-only delta:
- `cliq-210` moved `zoho cliq status` and `zoho cliq capabilities` command bodies into `zoho_cli/commands/cliq_readiness.py`; AI-user command patterns are unchanged.
- `cliq-210` also moved `zoho cliq whoami` and `zoho cliq user-resolve` command bodies into `zoho_cli/commands/cliq_identity.py`; AI-user command patterns are unchanged.
- `cliq-210` also moved `zoho cliq users` and `zoho cliq teams` command bodies into `zoho_cli/commands/cliq_org_directory.py`; AI-user command patterns are unchanged.
- `cliq-210` also moved org-admin list command bodies (`departments`, `roles`, `designations`, `user-status`, `userfields`) into `zoho_cli/commands/cliq_org_admin.py`; AI-user command patterns are unchanged.
- `cliq-210` also moved productivity/platform list command bodies (`events`, `reminders`, `meetings`, `databases`) into `zoho_cli/commands/cliq_productivity.py`; AI-user command patterns are unchanged.
- `cliq-210` also moved platform-extension list command bodies (`widgets`, `map-tickers`, `custom-domains`, `custom-emails`) into `zoho_cli/commands/cliq_platform_extensions.py`; AI-user command patterns are unchanged.
- `cliq-210` also moved channel/member/chat-control command bodies (`members`, channel lifecycle/member commands, `leave`, `mute`, `unmute`, `pin`, `unpin`, `pinned`) into `zoho_cli/commands/cliq_channel_management.py`; AI-user command patterns are unchanged.
- v0.4 native OpenClaw Cliq channel now has config/setup/security/session/CLI-adapter/outbound delivery, fixture-backed inbound polling normalization/dedupe, Bot webhook receive/auth/normalize intake at `/webhooks/cliq`, status/read lifecycle handling, turn-ledger loop prevention, native status/capability/routing diagnostics, AI-facing troubleshooting guidance, native dispatch, redacted observability/privacy diagnostics, real Bot Deluge templates in `docs/releases/OPENCLAW_CLIQ_BOT_HANDLER_TEMPLATES.md`, the exact Bot handler template renderer `ops/scripts/openclaw_cliq_bot_handler_template_render.sh`, the `ops/scripts/openclaw_cliq_live_smoke.sh` gate, tunnel-agnostic public callback verification through `ops/scripts/openclaw_cliq_public_callback_smoke.sh`, live ingress triage through `ops/scripts/openclaw_cliq_live_ingress_diagnostic.sh`, the combined no-response wrapper `ops/scripts/openclaw_cliq_bot_no_response_packet.sh`, the `ops/scripts/openclaw_cliq_rc_pack.sh` preflight, no-publish tarball verification through `ops/scripts/openclaw_cliq_rc_artifact_check.sh`, Temp-HOME install smoke through `ops/scripts/openclaw_cliq_rc_install_smoke.sh`, strict promotion preflight through `ops/scripts/openclaw_cliq_rc_promotion_check.sh`, operator review bundle through `ops/scripts/openclaw_cliq_rc_operator_publish_bundle.sh`, release-notes draft through `ops/scripts/openclaw_cliq_rc_release_notes_draft.sh`, read-only publish plan through `ops/scripts/openclaw_cliq_rc_publish_plan.sh`, read-only handoff manifest through `ops/scripts/openclaw_cliq_rc_operator_handoff_manifest.sh`, `ops/scripts/openclaw_cliq_trusted_reply_evidence.sh`, `docs/releases/OPENCLAW_CLIQ_CHANNEL_COMPATIBILITY.md`, and `docs/releases/OPENCLAW_CLIQ_CHANNEL_V0_4_RC_CHECKLIST.md`; public Bot callback verification requires a reachable HTTPS tunnel/gateway URL, but it is not Cloudflare-specific. Registered Bot webhook routes default to quiet lifecycle mode so direct Bot DMs do not spend Zoho API quota on visible status/read-ack calls; current real Bot templates use `reply_mode=deluge_response` so Zoho renders the OpenClaw final answer from the handler response instead of requiring a second OAuth send. Explicit smoke/polling paths can still exercise the lifecycle wrapper.
- CRM v0.5 SDK adoption has started. Run `zoho crm sdk-status` before SDK work, treat `zohocrmsdk8_0==5.0.0` as optional `zoho-cli[crm-sdk]` readiness, and follow `docs/architecture/CRM_V0_5_SDK_ADOPTION_PLAN.md` before changing CRM command output shapes. `crm-004/005` add the default-disabled `zoho_cli/crm_sdk.py` data-center adapter and explicit `--adapter sdk-v8` read gates; `crm-006` locks `apiVersionPolicy` so HTTP v2 is default and SDK/API v8 is explicit-only; `crm-007` adds `zoho crm write-plan` / `writeSurfacePolicy` with `writesEnabled=false`, dry-run default, exact confirmation, idempotency, JSON payload, and audit requirements; `crm-008` adds `zoho crm upsert` dry-run with `payloadDigest`, `recordDigests`, `requiredConfirmation`, and `live_write_not_enabled` for `--execute`; `crm-009` adds `zoho crm upsert-gate` with `liveWritesEnabled=false`, `decision=defer_live_execution`, scope matching, and blockers including `audit_persistence_not_implemented` plus `controlled_live_fixture_not_recorded`; `crm-010` adds redacted JSONL `auditPersistence` plus `zoho crm write-audit`, `--audit-file`, and `ZOHO_CRM_WRITE_AUDIT`; `crm-011` adds `zoho crm fixture-plan` with `policyId=crm-011-controlled-live-fixture-gate` to inspect dry-run/gate/scope audit evidence without writing CRM data; `crm-012` adds `zoho crm fixture-execute` with `policyId=crm-012-guarded-fixture-execution-harness`, dry-run default, exact approval, cleanup, env, digest, idempotency, and audit gates for one controlled live fixture; `crm-013` adds `ops/scripts/crm_fixture_live_smoke.sh` for repeatable redacted fixture smoke reports; `crm-014` adds `zoho crm fixture-evidence` with `policyId=crm-014-operator-fixture-evidence` and statuses `incomplete`, `ready_for_operator_live_fixture`, and `live_fixture_recorded`; SDK resources must stay under `ZOHO_CRM_SDK_RESOURCE_PATH` or the CLI-managed cache path.
- `crm-015` adds `ops/scripts/crm_fixture_operator_readiness_bundle.sh` as the no-write operator readiness bundle for an existing dry-run smoke summary.
- `crm-015` also adds `ops/scripts/crm_fixture_operator_packet.sh` as the preferred autonomous handoff wrapper: it reports missing payload/cleanup, payload preflight readiness, dry-run readiness, or recorded live fixture evidence without granting live CRM write permission.
- `crm-039` adds StorePilot CRM v8 read/query commands: `zoho crm users`, `zoho crm user-get`, `zoho crm org`, and `zoho crm coql --query "<SELECT ...>"`. Use `zoho login --with-storepilot-crm` plus `zoho crm status --scope-profile storepilot --check-auth` for scope readiness and live org identity; the StorePilot preset intentionally excludes the invalid `ZohoCRM.apis.READ` scope, and ready status output reports `orgId` plus `orgSource=crm_org_api`. These commands do not unlock live CRM writes; bulk and notifications remain guarded surfaces.
- `crm-041` adds StorePilot bootstrap metadata reads and local diff helpers: `zoho crm profiles`, `zoho crm roles`, `zoho crm layouts --module <Module>`, `zoho crm snapshot --crm-modules-seed <crm-modules.seed.json>`, and `zoho crm seed-diff --snapshot-file <snapshot.json> --crm-modules-seed ...`. Treat the diff as dry-run/manual-step reporting only; it never creates modules, fields, layouts, notifications, or seed records.
- `crm-042` adds StorePilot production org-id/readiness checks and type mapping refinements: pass `--expected-org-id` or set `ZOHO_ORG_ID` on `snapshot` / `seed-diff`; inspect `orgVerification`, `readiness.blockingReasons`, `field_mapping_contracts`, per-field `zohoType`, and `fields_with_property_gaps` before handing output to a schema initializer.
- `crm-043` adds StorePilot `zoho crm bulk-plan` and `zoho crm notification-plan` dry-run contracts. Use them to count seed import batches, list future bulk exports, and enumerate webhook subscriptions plus guarded apply requirements; they do not call Zoho bulk or notification write APIs.
- `crm-044` adds `zoho crm init-plan` as the combined StorePilot dry-run handoff for seed diff, bulk plan, notification plan, and legacy cleanup review. Cleanup entries are candidates only; do not treat them as permission to delete or disable anything.
- `crm-046` adds `zoho crm automation <resource>` and `zoho crm snapshot --include-automation` for read-only workflow rule, webhook, automation task, cadence, connected workflow, and assignment-threshold cleanup review. `init-plan.cleanupPlan.legacy_automation_to_review` and `zoho_only_manual_steps` are manual review signals only.
- `crm-047` adds `snapshotSummary` to `zoho crm snapshot`; use it for coverage/count checks before parsing raw modules, fields, layouts, or automation blocks.
- `crm-048` adds `init-plan.manualSetupPlan`; inspect it for seed manual steps, relationship/related-list checks, layout coverage, automation cleanup review, and notification setup review before any guarded apply planning. It remains dry-run-only.
- `crm-049` adds `zoho crm settings related_lists --module <Module>` and `zoho crm settings custom_views --module <Module>`, plus `zoho crm snapshot --include-settings`, for read-only StorePilot related-list and custom-view metadata. Treat this as review evidence only, not permission to edit layouts or settings.
- `crm-050` adds `zoho crm apply-plan --init-plan-file <init-plan.json>` as guarded apply scaffolding. It reports planned phases, org readiness, exact approval requirements, and blockers, but keeps `executionBlocked=true` and performs no Zoho writes.
- `crm-019` adds `operatorReview.readyFacts` and `operatorReview.missingFacts` to that packet so AI agents can branch on redacted fact categories instead of raw payload, email, cleanup, or selector values.
- `crm-020` adds redacted `operatorReview.nextCommands` command previews with `agentMayExecute`, `dryRunOnly`, `writesZohoData`, and `requiresExplicitOperatorApproval` gates; agents may run local/dry-run entries only and must stop at operator-only live approval entries.
- `crm-021` adds `reportFiles` and `reportsReady` to the packet so agents can hand off generated packet/preflight/readiness/smoke-summary basenames without logging local paths.
- `crm-022` adds the same basename-only `reportFiles` and `reportsReady` handoff metadata to `ops/scripts/crm_fixture_operator_readiness_bundle.sh` for `readinessBundle`, `smokeSummary`, and `fixtureEvidence`.
- `crm-023` adds redacted `operatorReview.liveApproval` to CRM fixture operator packets and readiness bundles; inspect these booleans for summary/evidence readiness, payload digest, idempotency key, required approval presence, placeholder status, and `agentMayExecute=false` before asking the operator for a live fixture approval.
- `crm-024` adds `operatorReview.liveApproval.readyFacts` and `operatorReview.liveApproval.missingFacts`; prefer those category lists when explaining what approval facts remain missing.
- `crm-025` adds `operatorReview.actionBoundary`; run only ids in `agentExecutableCommandIds` and stop on `operatorOnlyCommandIds`, `zohoWriteCommandIds`, or `requiresExplicitOperatorApprovalCommandIds`.
- `crm-026` adds the same redacted `operatorReview.nextCommands` and `operatorReview.actionBoundary` stop/go contract to readiness bundles; blocked bundles expose dry-run fixer ids only, while ready bundles expose the live approval id as operator-only and Zoho-writing.
- `crm-028` adds `operatorReview.agentAutomation` to packets and readiness bundles; prefer `nextAgentExecutableCommandId` plus `agentMayExecuteNextCommand` for autonomous branching, and stop on any `stopCommandIds`.
- `crm-029` adds `operatorReview.agentAutomation.nextAgentCommand`, a redacted placeholder-only command preview for the next agent-executable dry-run/local step; use it when present and treat `null` as a stop boundary.

## Required behavior support after lane3 sync

After sync, ensure the AI user follows:

- unread polling with self-reaction exclusion:
  - `zoho cliq chats --unread-only --exclude-reacted-by-self`
- reaction status lifecycle updates via:
  - `zoho cliq status-react --status received|thinking|writing|testing|blocked|done|failed --clear-known`
- context-before-reply in loops:
  - `zoho cliq context ...` before `zoho cliq reply ...`
- native channel inbound polling dry-runs:
  - normalize `zoho cliq chats --unread-only --exclude-reacted-by-self` + `zoho cliq context`
  - skip self-authored messages and dedupe by account/network/chat/message before dispatch
- native channel Bot webhook smoke:
  - read `docs/releases/OPENCLAW_CLIQ_BOT_HANDLER_TEMPLATES.md` before editing a real Zoho Bot
  - run `ops/scripts/openclaw_cliq_bot_handler_template_render.sh --md --handlers message` when you need the exact direct-DM Message Handler Deluge block; require `handler_template_render_ready`
  - configure Message, Mention, Participation, or Context handlers to POST to `/webhooks/cliq`
  - send `X-Cliq-Webhook-Secret` from `ZOHO_CLIQ_WEBHOOK_SECRET`
- native channel live smoke gate:
  - run `ops/scripts/openclaw_cliq_live_smoke.sh` from the repo root
  - record `token_refresh_rate_limited` and repeated endpoint availability failures as `skip_deferred`
  - if diagnostics report `dispatch_reply_rate_limited`, wait for Zoho cooldown,
    avoid bursty probes, and rerun one message after the quiet webhook lifecycle
    build is installed
  - do not claim public Bot callback success until `ZOHO_CLIQ_PUBLIC_WEBHOOK_URL` reaches the running gateway and
    `ops/scripts/openclaw_cliq_public_callback_smoke.sh` reports
    `kind=openclaw_cliq_public_callback_smoke` with
    `status=public_callback_verified`; set
    `ZOHO_CLIQ_PUBLIC_CALLBACK_REPORT_FILE` for the redacted report, require
    missing-secret `401` plus authenticated unsupported-handler `200`, reject
    placeholders, treat `public_webhook_url_requires_https` as a public-ingress
    config blocker, and never store webhook bodies, response bodies, or secrets
  - for Cloudflare Zero Trust Tunnels, choose Published application and forward
    the public hostname to `HTTP` service `127.0.0.1:18789`; if the tunnel has
    zero routes, fix Cloudflare routing before changing Zoho or OpenClaw config
  - after a controlled trusted Mention, run
    `ops/scripts/openclaw_cliq_trusted_reply_evidence_bundle.sh` with expected
    agent/model and either raw ids or `sha256:` references; the bundle
    auto-runs route preflight if no route report is provided; require
    `trusted_reply_recorded`; sender/message/reply ids must be `sha256:`
    references only; prefer `ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE` with
    `kind=openclaw_cliq_trusted_reply_facts`, `trustedSenderIdHash`,
    `trustedMessageIdHash`, and `deliveryIdHash` when passing hash facts from
    one agent/operator step to the final bundle; raw facts fields are rejected
    with `facts_file_raw_ids_present`, and secret markers with
    `facts_file_secret_marker_present`; use
    `ops/scripts/openclaw_cliq_trusted_reply_facts_prepare.sh` to create that
    hash-only facts file and require `openclaw_cliq_trusted_reply_facts_prepare`
    with `facts_file_ready`; it can also read an untracked local
    `openclaw_cliq_trusted_reply_raw_facts` JSON file through
    `ZOHO_CLIQ_TRUSTED_REPLY_RAW_FACTS_FILE`, but that file must contain ids
    only, not raw webhook payloads, message/reply bodies, secrets, or
    placeholder raw ids such as `<trusted_cliq_user_id>` / `replace-me`; the final
    bundle can take `ZOHO_CLIQ_TRUSTED_REPLY_RAW_FACTS_FILE` directly and
    auto-run facts prepare when no hash facts file is set; if route
    preflight fails with
    `agent_binding_mismatch`,
    keep only the route JSON and do not claim evidence/check reports; start from
    `docs/releases/OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_TEMPLATE.json`
  - before asking for the trusted Mention, set
    `ZOHO_CLIQ_TRUSTED_REPLY_PLAN_ONLY=1` on that bundle and require
    `kind=openclaw_cliq_trusted_reply_evidence_bundle_plan`; the
    `awaiting_live_delivery_facts` state means the remaining work is to capture
    sender/message/reply delivery facts after the real Bot turn; archive the
    `ZOHO_CLIQ_TRUSTED_REPLY_PLAN_FILE` report or the default plan report under
    the trusted reply report directory; branch on `nextAction` and
    `readyForFinalBundle`, using `missingFacts` / `readyFacts` for detail and
    `reportFiles` / `reportsReady` for artifact handoff; require plan
    `collectionGuide` to limit the live step to exactly one trusted Mention,
    `trustedSenderId`, `trustedMessageId`, and `deliveryId`, with
    `rawWebhookPayload`, `rawMessageBody`, `rawCliqReplyBody`, and `secrets`
    forbidden; use `acceptedFactSources` containing `rawFactsFile` and
    `preferredFactSource=ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE` when a hash facts
    file is available; follow `factPrepareCommand`,
    `collectionGuide.factsFileKind`,
    `collectionGuide.factsPrepareReadyStatus`,
    `collectionGuide.rawFactsPrepareEnv`, and
    `collectionGuide.rawFactsFileKind` for the facts-file handoff;
    require plan `redaction` booleans to keep raw ids, hash values, local
    paths, and secrets out of the report
  - when a user says they sent a Bot message but no reply appears, first run
    `ops/scripts/openclaw_cliq_bot_no_response_packet.sh`; it runs the public
    callback smoke when `ZOHO_CLIQ_PUBLIC_WEBHOOK_URL` is set, then runs the
    live ingress diagnostic and returns one `nextAction`. Set
    `ZOHO_CLIQ_INGRESS_LOOKBACK_SECONDS` to the expected send window and
    optional `ZOHO_CLIQ_EXPECTED_AGENT_ID` / `ZOHO_CLIQ_EXPECTED_AGENT_MODEL`;
    self-generated public callback smoke records are ignored by the ingress
    diagnostic so the packet does not classify its own smoke as the latest Bot
    message;
    `no_recent_webhook_ingress` means the Zoho Bot handler did not POST to the
    gateway during that window; if public callback smoke is verified,
    `diagnosis.code=zoho_bot_handler_not_posting` means the public route is past
    the first gate and Zoho handler save/trigger state is the likely blocker,
    with direct Bot DMs requiring a saved **Message Handler**. `latest_webhook_not_dispatched` means payload or
    policy blocked dispatch, `dispatch_reply_not_delivered` means the agent turn
    ran but no Cliq reply was delivered, and `live_ingress_active` means the
    latest observed turn dispatched and delivered at least one reply. The
    packet and diagnostic keep raw webhook payloads, message bodies, reply
    bodies, callback response bodies, and secrets out of output/report JSON.
  - when `openclaw_cliq_bot_no_response_packet` returns
    `nextAction=fix_zoho_bot_handler_trigger`, inspect its embedded
    `handlerTrigger` object first. When public callback is not the blocker, the
    wrapper auto-runs `ops/scripts/openclaw_cliq_handler_trigger_packet.sh` and
    stores the redacted handler trigger evidence filename. You may also run the
    handler trigger script directly with `ZOHO_CLIQ_PUBLIC_WEBHOOK_URL` and
    optional `ZOHO_CLIQ_HANDLER_TARGETS`; require
    `status=handler_trigger_packet_ready` before using its
    `handlers.saveTargets`, `handlers.directMessageRequirement`,
    `delugeContract`, and `operatorChecklist` to guide Zoho
    Message/Mention/Participation/Context handler edits. Direct Bot DMs require
    the Bot details **Handlers** list to include **Message Handler**; Mention
    Handler alone only handles @mentions/channel contexts. Current packets
    should require `delugeContract.replyMode=deluge_response` and
    `operatorChecklist` should say to return `webhook_response` when it has a
    `text` key; a fixed `received` ACK means the handler is still in smoke-test
    mode. The packet must
    keep `redaction.secretsStored=false` and
    `delugeContract.secretValueStored=false`.
- native channel RC pack preflight:
  - run `ops/scripts/openclaw_cliq_rc_pack.sh` from the repo root before cutting a local/operator or npm/GitHub RC artifact
  - keep generated tarballs under ignored `.tmp/openclaw-cliq-rc-pack`
  - archive only the redacted summary JSON from `tests/auto_pilot/reports/`
  - do not treat the preflight as an npm publish or version bump
- native channel RC artifact check:
  - run `ops/scripts/openclaw_cliq_rc_artifact_check.sh` after pack and before promotion handoff
  - require `artifact_verified`, matching shasum, expected package/channel/manifest identity, and required `dist/`, `README.md`, and `skill/SKILL.md` tarball entries
  - treat `tarball_shasum_mismatch`, `artifact_version_mismatch`, or `required_entry_missing_*` as stop-and-fix blockers
  - do not treat the artifact check as an npm publish, tag, version bump, or published integrity fill
- native channel RC install smoke:
  - run `ops/scripts/openclaw_cliq_rc_install_smoke.sh` after `artifact_verified`
  - require `install_smoke_passed` from a Temp-HOME local `plugins install`, `plugins inspect zoho-cliq --json`, and `plugins doctor`
  - treat `artifact_not_verified`, `plugin_install_failed`, `plugin_inspect_failed`, `plugin_id_missing`, `channel_id_missing`, or `plugin_doctor_failed` as stop-and-fix blockers
  - do not treat the install smoke as an npm publish, tag, version bump, or published integrity fill
- native channel RC promotion preflight:
  - run `ops/scripts/openclaw_cliq_rc_promotion_check.sh` only after pack, artifact check, install smoke, and trusted reply evidence exist
  - require `ready_for_operator_publish`, `artifact_verified`, `install_smoke_passed`, `trusted_reply_recorded`, and `expectedIntegrityState=placeholder`
  - treat `artifact_report_missing`, `artifact_not_verified`, `install_smoke_missing`, and `install_smoke_not_passed` as stop-and-fix blockers
  - do not treat the promotion preflight as operator approval to publish, tag, npm-promote, or fill published artifact integrity
- native channel RC operator review bundle:
  - run `ops/scripts/openclaw_cliq_rc_operator_publish_bundle.sh` after strict promotion preflight
  - require `operator_publish_bundle_ready`, `nextAction=operator_select_publish_path`, and report filenames for pack, artifact, install smoke, promotion, and trusted reply evidence
  - require `agentMayPublish=false`, `agentMayTag=false`, and `agentMayFillExpectedIntegrity=false`
  - treat `promotion_report_missing` or `promotion_not_ready` as stop-and-fix blockers, not as permission to rerun publish steps
- native channel RC release-notes draft:
  - run `ops/scripts/openclaw_cliq_rc_release_notes_draft.sh` after the operator bundle is ready
  - require draft text to include no-publish/no-tag/no-release/no-integrity-fill language plus `operator_publish_bundle_ready`, `ready_for_operator_publish`, `artifact_verified`, `install_smoke_passed`, and `trusted_reply_recorded`
  - treat `operator_bundle_missing`, `operator_bundle_not_ready`, `agent_publish_permission_unexpected`, `agent_tag_permission_unexpected`, and `agent_integrity_fill_permission_unexpected` as stop-and-fix blockers
- native channel RC publish plan:
  - run `ops/scripts/openclaw_cliq_rc_publish_plan.sh` after the release-notes draft is safe
  - require `operator_publish_plan_ready`, `agentMayExecutePlan=false`, and operator-only local/operator, npm RC, or GitHub artifact choices
  - treat `release_notes_draft_unsafe`, `expected_integrity_not_placeholder`, or missing false agent permission flags as stop-before-publish blockers
- native channel RC handoff manifest:
  - run `ops/scripts/openclaw_cliq_rc_operator_handoff_manifest.sh` after the publish plan is ready
  - require `operator_handoff_manifest_ready`, `nextAction=operator_review_handoff_manifest`, no blockers, indexed report filenames, `operator_publish_plan_ready`, and `trusted_reply_recorded`
  - treat `publish_plan_permission_unexpected`, `operator_bundle_file_mismatch`, and `release_notes_draft_file_mismatch` as stop-before-publish blockers
- native channel RC source drift:
  - run `ops/scripts/openclaw_cliq_rc_source_drift_check.sh` before relying on an older operator handoff
  - when no explicit manifest path is set, it selects the newest ready handoff manifest and skips blocked drafts
  - require `package_source_unchanged`; rebuild the RC artifact if package files changed or are dirty
- native Cliq Bot handler operator handoff:
  - run `ops/scripts/openclaw_cliq_bot_handler_operator_prompt.sh --md` when `no_recent_webhook_ingress` or `diagnosis.code=zoho_bot_handler_not_posting` points at Zoho handler save/trigger state
  - run `ops/scripts/openclaw_cliq_bot_handler_template_render.sh --md --handlers message` to render the no-secret Deluge Message Handler paste block; require `handler_template_render_ready`
  - ask for the Bot details Handlers list to include **Message Handler** before testing direct Bot DMs
  - after the operator saves the handler, run at most one short-window no-response packet for the fresh message
- native channel compatibility maintenance:
  - read `docs/releases/OPENCLAW_CLIQ_CHANNEL_COMPATIBILITY.md` before changing host/plugin API floors
  - keep `>=2026.5.3-1` as the v0.4 floor unless a newer OpenClaw SDK is genuinely required
  - patch plugin adapter/setup metadata before changing Zoho CLI command contracts
- native channel RC decisions:
  - read `docs/releases/OPENCLAW_CLIQ_CHANNEL_V0_4_RC_CHECKLIST.md`
  - keep local/operator RC package readiness separate from production rollout readiness
  - prefer `ops/scripts/openclaw_cliq_rc_operator_decision_packet.sh` for the
    current publish handoff; `awaiting_operator_publish_path` is the normal
    waiting state, `operator_publish_selection_ready` still requires operator
    review/execution, and `agentMayExecuteSelectedPath=false` must stay false
  - parse decision-packet `reportFiles` and `reportsReady` to hand off publish
    plan, source drift, selection review, operator bundle, release notes draft,
    and handoff manifest evidence by basename without logging local paths
  - for recurring autonomous sweeps that must consider both native Cliq RC
    publish state and CRM fixture state, run
    `ops/scripts/zoho_cli_rc_autonomy_packet.sh`; execute only when it returns
    `status=agent_next_command_ready` and
    `safety.crmNextCommandAllowedForAgent=true`, use
    `recommendedAgentCommand`, and treat `operator_input_required`,
    `operator_publish_path_required`, `stop_before_operator_publish`, and
    `stop_before_operator_live_fixture` as handoff states. A true
    `safety.crmNextCommandAllowlistedDryRunLocal` only confirms the CRM command
    shape is recognized; it does not override a non-ready top-level status.
    Use `operatorActionRequests` to generate the exact human ask without
    exposing raw values. `commandPreview` values are placeholder-only recheck
    hints, optional `followUpCommandPreview` values name the next diagnostic
    command, and `unblocks` names the next gate the operator input should unlock.
    Read `nextOperatorActionId` / `nextOperatorActionRequest` first when present;
    while the real Bot direct-message blocker is active, that id should be
    `save_openclaw_cliq_bot_message_handler`.
    Expected ids include
    `save_openclaw_cliq_bot_message_handler`,
    `select_openclaw_cliq_publish_path`,
    `provide_crm_fixture_cleanup_plan`, and
    `provide_crm_fixture_payload_file`; the Bot handler id should be treated as
    the first ask while direct Bot replies are still the leading blocker
  - when you need to hand those asks back to a human, prefer
    `ops/scripts/zoho_cli_rc_operator_action_prompt.sh`; it runs or reads the
    autonomy packet, returns `operator_action_prompt_ready` with
    `nextAction=send_operator_action_prompt`, and emits `messageMarkdown`
    without raw payload paths, cleanup text, secrets, publish/write execution,
    or local report paths. Use `--md` when you need direct human-readable
    stdout; default stdout stays JSON for scripts and agents
  - `OPENCLAW_CLIQ_OPERATOR_PUBLISH_PATH=local_operator_rc` may be rehearsed
    read-only; require `operator_publish_selection_ready` plus
    `selectedPublishPathReview.agentMayExecute=false` before handing the choice
    back to the operator
  - `OPENCLAW_CLIQ_OPERATOR_PUBLISH_PATH=npm_rc_publish` and
    `OPENCLAW_CLIQ_OPERATOR_PUBLISH_PATH=github_release_artifact` are also
    read-only rehearsals; command previews are for operator review only and
    must keep `agentMayExecuteSelectedPath=false`
  - after docs/state-only commits, rerun the source drift check and decision
    packet; `20260512T174215Z-platform214-postcommit-decision`
    is the current evidence that commit `a03de9e5` keeps
    `packageChangedSinceManifest=false` while returning
    `awaiting_operator_publish_path`
  - require `openclaw_cliq_public_callback_smoke` /
    `public_callback_verified` for a reachable public Bot callback URL before
    claiming production incident readiness
- native channel lifecycle smoke:
  - accepted webhook/polling events should produce lifecycle metadata and visible status reactions
  - read-ack/status failures are diagnostics and must not dispatch new inbound work
- native channel turn-ledger smoke:
  - duplicate completed events, active same-conversation bursts, and dead-lettered replays must not dispatch another agent turn
  - failed turns should expose dead-letter metadata without leaking message bodies or secrets
  - rotate any exposed secret before live use
- native channel status/capability/routing diagnostics:
  - inspect native channel summaries before falling back to ad hoc `zoho cliq ...` probes
  - use setup states, readiness blockers, and normalized route/session facts to decide the next operator action
  - do not copy webhook secrets, token passwords, raw stderr, webhook signatures, or message bodies into reports
  - treat `webhook_secret_missing` as a SecretRef/env blocker and use `ZOHO_CLIQ_WEBHOOK_SECRET`
  - native dispatch is implemented for accepted webhook/polling events; use redacted diagnostic bundles and keep public Bot callback reachability as the remaining production prerequisite when no HTTPS tunnel/gateway URL is configured
  - report repeated Zoho-side `not_supported` or `inactive_appaccount_user` results as `skip_deferred` instead of blocking unrelated channel work
  - prefer explicit routing targets such as `channel:<id>`, `user:<id>`, or `cliq:channel:<id>:thread:<thread_id>`
- native channel development/operation docs when relevant:
  - read `skill/references/openclaw-cliq-channel.md`
  - read `integrations/openclaw/CLIQ_CHANNEL_DEVELOPMENT_GUIDE.md`
- CRM write planning:
  - run `zoho crm write-plan` and `zoho crm upsert-gate --module <module>`
  - inspect persisted events with `zoho crm write-audit`
  - run `zoho crm fixture-plan` before any real-environment CRM fixture test
  - run `zoho crm fixture-execute` without `--execute` to obtain
    `requiredApproval` and inspect blockers
  - use `ZOHO_CRM_ALLOW_LIVE_FIXTURE=1` plus exact `--fixture-approval` and
    `--cleanup-plan` only for an explicitly approved dedicated fixture record
  - prefer `ops/scripts/crm_fixture_live_smoke.sh` for operator smoke reports;
    it skips live execution unless `ZOHO_CRM_FIXTURE_EXECUTE=1` and
    `ZOHO_CRM_ALLOW_LIVE_FIXTURE=1` are both set
  - use `docs/releases/CRM_V0_5_FIXTURE_PAYLOAD_TEMPLATE.json` only as a
    copy/edit starting point; use
    `docs/releases/CRM_V0_5_FIXTURE_CLEANUP_PLAN_TEMPLATE.md` only as the
    matching cleanup-plan starter; replace all placeholders with a dedicated
    operator-owned CRM test address plus selector-specific cleanup text before
    live mode
  - use `docs/releases/CRM_V0_5_FIXTURE_LOCAL_PRECHECK_EXAMPLES.md` as the
    no-write copy/edit walkthrough for cleanup-plan shape, local rechecks, and
    common blocker fixes
  - verify `payloadTemplatePlaceholders.emailCount=0`; live smoke blocks with
    `fixture_payload_placeholder_email` if template email markers remain
  - run `zoho crm fixture-evidence --summary-file <summary.json>` after smoke
    runs; require `ready_for_operator_live_fixture` before live mode and
    `live_fixture_recorded` for completed evidence
  - run `ops/scripts/crm_fixture_operator_readiness_bundle.sh` with
    `ZOHO_CRM_FIXTURE_SUMMARY_FILE=<summary.json>` before live mode; require
    `ready_for_operator_live_fixture`, `normalUpsertExecuteBlocked=true`,
    `agentMayExecuteLiveFixture=false`, and
    `payloadTemplatePlaceholders.emailCount=0`
  - run `ops/scripts/crm_fixture_payload_preflight.sh` before any Zoho-backed
    smoke; require `cleanup.qualityReady=true`, and treat
    `cleanup_plan_too_short`, `cleanup_plan_action_missing`, and
    `cleanup_plan_target_missing`, and `cleanup_plan_selector_missing` as
    stop-and-fix blockers; accepted cleanup plans must name a selector such as
    fixture email, record id, duplicate field, idempotency key, or payload digest,
    and `cleanup.selectorTypes` reports only redacted selector categories
  - inspect `operatorReview.readyFacts` and `operatorReview.missingFacts` for
    redacted handoff categories before asking for another operator action
  - inspect `operatorReview.liveApproval` before live fixture handoff; require
    `summaryFileReady=true`, `dryRunReadinessReady=true`,
    `fixtureEvidenceReady=true`, `payloadDigestPresent=true`,
    `idempotencyKeyPresent=true`, `requiredApprovalPresent=true`,
    `placeholderEmailCountZero=true`, `commandPreviewUsesPlaceholders=true`,
    and `agentMayExecute=false`
  - use `operatorReview.liveApproval.readyFacts` /
    `operatorReview.liveApproval.missingFacts` to decide whether the missing
    facts are `summary_file`, `dry_run_readiness`, `fixture_evidence`,
    `payload_digest`, `idempotency_key`, `required_approval`, or
    `placeholder_email_count_zero`
  - inspect `operatorReview.actionBoundary`; only ids in
    `agentExecutableCommandIds` may be automated, and any id in
    `operatorOnlyCommandIds`, `zohoWriteCommandIds`, or
    `requiresExplicitOperatorApprovalCommandIds` requires a human operator
  - prefer `operatorReview.agentAutomation.nextAgentExecutableCommandId` when
    `agentMayExecuteNextCommand=true`, and use
    `operatorReview.agentAutomation.nextAgentCommand` as the command preview
    when present; otherwise stop and explain
    `operatorReview.agentAutomation.stopReason`
  - prefer `ops/scripts/crm_fixture_agent_next_command.sh` when you only need a
    compact go/stop answer; execute only on `agent_next_command_ready` with
    `safety.nextCommandAllowedForAgent=true`, collect operator input on
    `operator_input_required`, fix the packet or allowlist on
    `agent_command_not_allowlisted`, and stop on
    `stop_before_operator_live_fixture`
  - treat `summary_file_missing`, `fixture_evidence_not_ready`,
    `payload_placeholder_count_missing`, and
    `fixture_payload_placeholder_email` as stop-and-fix blockers
  - use `--audit-file` or `ZOHO_CRM_WRITE_AUDIT` for isolated agent runs
  - treat normal `zoho crm upsert --execute` as blocked even after fixture
    execution exists
  - verify CRM write audit events report `rawFieldValuesStored=false`
  - verify fixture execution records `crm.write.fixture_attempt` and
    `crm.write.fixture_result` without raw field values
- GitHub issue intake for bugs/suggestions:
  - read `skill/references/github-intake-workflow.md`
  - file sanitized issues in `adwasd-dvd/zoho-cli` only
  - search duplicates before creating issues
  - ask before including private context or changing GitHub settings/labels/code
