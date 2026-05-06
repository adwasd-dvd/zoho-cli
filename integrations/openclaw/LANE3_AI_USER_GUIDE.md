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
- v0.4 native OpenClaw Cliq channel now has config/setup/security/session/CLI-adapter/outbound delivery, fixture-backed inbound polling normalization/dedupe, Bot webhook receive/auth/normalize intake at `/webhooks/cliq`, status/read lifecycle handling, turn-ledger loop prevention, native status/capability/routing diagnostics, AI-facing troubleshooting guidance, native dispatch, redacted observability/privacy diagnostics, real Bot Deluge templates in `docs/releases/OPENCLAW_CLIQ_BOT_HANDLER_TEMPLATES.md`, the `ops/scripts/openclaw_cliq_live_smoke.sh` gate, the `ops/scripts/openclaw_cliq_rc_pack.sh` preflight, `ops/scripts/openclaw_cliq_trusted_reply_evidence.sh`, `docs/releases/OPENCLAW_CLIQ_CHANNEL_COMPATIBILITY.md`, and `docs/releases/OPENCLAW_CLIQ_CHANNEL_V0_4_RC_CHECKLIST.md`; public Bot callback verification still requires a reachable tunnel/gateway URL.
- CRM v0.5 SDK adoption has started. Run `zoho crm sdk-status` before SDK work, treat `zohocrmsdk8_0==5.0.0` as optional `zoho-cli[crm-sdk]` readiness, and follow `docs/architecture/CRM_V0_5_SDK_ADOPTION_PLAN.md` before changing CRM command output shapes. `crm-004/005` add the default-disabled `zoho_cli/crm_sdk.py` data-center adapter and explicit `--adapter sdk-v8` read gates; `crm-006` locks `apiVersionPolicy` so HTTP v2 is default and SDK/API v8 is explicit-only; `crm-007` adds `zoho crm write-plan` / `writeSurfacePolicy` with `writesEnabled=false`, dry-run default, exact confirmation, idempotency, JSON payload, and audit requirements; `crm-008` adds `zoho crm upsert` dry-run with `payloadDigest`, `recordDigests`, `requiredConfirmation`, and `live_write_not_enabled` for `--execute`; `crm-009` adds `zoho crm upsert-gate` with `liveWritesEnabled=false`, `decision=defer_live_execution`, scope matching, and blockers including `audit_persistence_not_implemented` plus `controlled_live_fixture_not_recorded`; `crm-010` adds redacted JSONL `auditPersistence` plus `zoho crm write-audit`, `--audit-file`, and `ZOHO_CRM_WRITE_AUDIT`; `crm-011` adds `zoho crm fixture-plan` with `policyId=crm-011-controlled-live-fixture-gate` to inspect dry-run/gate/scope audit evidence without writing CRM data; `crm-012` adds `zoho crm fixture-execute` with `policyId=crm-012-guarded-fixture-execution-harness`, dry-run default, exact approval, cleanup, env, digest, idempotency, and audit gates for one controlled live fixture; `crm-013` adds `ops/scripts/crm_fixture_live_smoke.sh` for repeatable redacted fixture smoke reports; `crm-014` adds `zoho crm fixture-evidence` with `policyId=crm-014-operator-fixture-evidence` and statuses `incomplete`, `ready_for_operator_live_fixture`, and `live_fixture_recorded`; SDK resources must stay under `ZOHO_CRM_SDK_RESOURCE_PATH` or the CLI-managed cache path.

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
  - configure Message, Mention, Participation, or Context handlers to POST to `/webhooks/cliq`
  - send `X-Cliq-Webhook-Secret` from `ZOHO_CLIQ_WEBHOOK_SECRET`
- native channel live smoke gate:
  - run `ops/scripts/openclaw_cliq_live_smoke.sh` from the repo root
  - record `token_refresh_rate_limited` and repeated endpoint availability failures as `skip_deferred`
  - do not claim public Bot callback success until `ZOHO_CLIQ_PUBLIC_WEBHOOK_URL` reaches the running gateway
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
    with `facts_file_ready`; if route preflight fails with
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
    forbidden; use `acceptedFactSources` and
    `preferredFactSource=ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE` when a hash facts
    file is available; follow `factPrepareCommand`,
    `collectionGuide.factsFileKind`, and
    `collectionGuide.factsPrepareReadyStatus` for the facts-file handoff;
    require plan `redaction` booleans to keep raw ids, hash values, local
    paths, and secrets out of the report
- native channel RC pack preflight:
  - run `ops/scripts/openclaw_cliq_rc_pack.sh` from the repo root before cutting a local/operator or npm/GitHub RC artifact
  - keep generated tarballs under ignored `.tmp/openclaw-cliq-rc-pack`
  - archive only the redacted summary JSON from `tests/auto_pilot/reports/`
  - do not treat the preflight as an npm publish or version bump
- native channel compatibility maintenance:
  - read `docs/releases/OPENCLAW_CLIQ_CHANNEL_COMPATIBILITY.md` before changing host/plugin API floors
  - keep `>=2026.5.3-1` as the v0.4 floor unless a newer OpenClaw SDK is genuinely required
  - patch plugin adapter/setup metadata before changing Zoho CLI command contracts
- native channel RC decisions:
  - read `docs/releases/OPENCLAW_CLIQ_CHANNEL_V0_4_RC_CHECKLIST.md`
  - keep local/operator RC package readiness separate from production rollout readiness
  - require a reachable public Bot callback URL before claiming production incident readiness
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
  - native dispatch is implemented for accepted webhook/polling events; use redacted diagnostic bundles and keep public Bot callback reachability as the remaining production prerequisite when no tunnel/gateway URL is configured
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
    copy/edit starting point; replace the `.example.invalid` email with a
    dedicated operator-owned CRM test address before live mode
  - verify `payloadTemplatePlaceholders.emailCount=0`; live smoke blocks with
    `fixture_payload_placeholder_email` if template email markers remain
  - run `zoho crm fixture-evidence --summary-file <summary.json>` after smoke
    runs; require `ready_for_operator_live_fixture` before live mode and
    `live_fixture_recorded` for completed evidence
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
