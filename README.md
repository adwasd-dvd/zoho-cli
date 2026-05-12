# zoho-cli — Zoho Mail, Cliq, and CRM in your terminal

Fast, script-friendly CLI for Zoho Mail, Cliq, and CRM. JSON output by default, Markdown tables with `--md`. Pipe to `jq`, use in scripts, or feed directly to AI agents.

[![GitHub release](https://img.shields.io/github/v/release/adwasd-dvd/zoho-cli)](https://github.com/adwasd-dvd/zoho-cli/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## Quick start

```bash
# Install via uv (recommended)
uv tool install git+https://github.com/adwasd-dvd/zoho-cli

# Or pipx
pipx install git+https://github.com/adwasd-dvd/zoho-cli

# From source
git clone https://github.com/adwasd-dvd/zoho-cli
cd zoho-cli
uv tool install .
```

### Setup

1. **Create an OAuth client** in [Zoho API Console](https://api-console.zoho.com) → Server-based Application
   - Redirect URI: `http://localhost:51821/callback` (used by both browser and `--no-browser` flows by default)
   
2. **Authenticate**
   ```bash
   zoho login
   # For Cliq/CRM scopes:
   zoho login --with-cliq --with-crm
   ```

---

## What works now

### ✅ Zoho Mail (stable)

- Message read/search: `mail list`, `mail search`, `mail get`
- Message write/actions: `mail send`, `reply`, `forward`, `mark-read/unread`, `archive/unarchive`, `move`, `delete`, `spam/not-spam`
- Attachment + metadata: `mail attachments`, `download-attachment`, `flag`, `tag`, `untag`, `untag-all`
- Folder + label management: `folders ...`, `labels ...`

### ✅ Zoho Cliq (broad command surface, active hardening)

- Read plane: `status`, `capabilities`, `channels/chats/users/members`, `messages/message/context`, `file`, `voice`, `search`, `whoami`
- Write plane: `send`, `voice-send`, `reply/edit/delete/react`, `notify-mail`
- Admin/ops planes: channel lifecycle + membership, thread/schedule/chat-control, bot operations, org-admin slices, platform-extension slices, app-governance slices
- Export plane: `export-chats` implemented with explicit scope/status diagnostics

> Note: some live Cliq endpoints are org/token/network dependent. On `happydistrouklimited`, several endpoints currently return `not_supported`/scope errors and are tracked as external blockers.

### 🚧 OpenClaw Zoho Cliq native channel (v0.4 lane)

- Package: `integrations/openclaw-channel-cliq/` (`@adwasd/openclaw-zoho-cliq`, plugin id `zoho-cliq`, channel id `cliq`)
- Host target: OpenClaw `>=2026.5.3-1`; the upgraded global host is verified at `OpenClaw 2026.5.3-1`, npm latest `2026.5.4` and beta `2026.5.4-beta.3` pass Temp-HOME compatibility checks, and package-local validation remains available for isolated checks.
- Current slice: `cliq-channel-488` is complete; the channel docs/status now sync the `cliq-channel-473/474` no-response handler-trigger flow plus post-doc-sync, post-CRM-selector-metadata, post-CRM-command-preview, post-CRM-report-metadata, post-CRM-readiness-report-metadata, post-CRM-live-approval-fact-categories, post-CRM-action-boundary, post-CRM-readiness-action-boundary, post-CRM-state-sync, all three operator publish selected-path evidence packets, post-operator-paths source-drift/decision evidence, and the latest post-CRM state-sync source-drift/decision evidence at commit `0319d9b8`, and the channel has account/network-aware session grammar, secure policy gates, native approval metadata, a JSON-safe `zoho` process adapter, native outbound send/reply/thread-reply delivery, fixture-backed inbound polling normalization/dedupe through `zoho cliq chats` + `zoho cliq context`, a Bot webhook intake route at `/webhooks/cliq` with secret verification, shared status/read lifecycle handling, a native turn ledger for duplicate/active/dead-letter loop prevention, operator-readable status/capability/routing diagnostics, AI-facing troubleshooting docs, native OpenClaw agent turn dispatch for accepted webhook/polling events, a redacted live smoke gate, a host compatibility repair runbook, a v0.4 RC checklist, repeatable RC package preflight, real Bot handler templates, Deluge Map-string Message Handler hardening, direct Bot reply fallback through real `chatId` for synthetic `webhook-*` / `zoho-message-*` ids, controlled direct fallback smoke with `deliveryCount=1`, post-hardening RC artifact/handoff evidence refresh, handler runtime contract coverage, trusted reply evidence preparation/checking, RC package metadata, an auto-route evidence bundle that stops on route mismatch before writing trusted reply evidence/check reports, a tunnel-agnostic public callback smoke for any HTTPS ingress URL, a native dispatch identity fix so accepted Cliq turns keep `Provider`/`Surface` as channel id `cliq` while preserving webhook/polling source facts separately, controlled live Bot Mention-to-agent reply evidence recorded as `trusted_reply_recorded`, redacted live ingress diagnostics, a combined Bot no-response packet, an embedded handler trigger packet for Zoho Bot handler paste/check triage, a strict local RC promotion preflight that requires `artifact_verified`, `install_smoke_passed`, and `trusted_reply_recorded` before reporting `ready_for_operator_publish`, a no-publish operator review bundle that reports `operator_publish_bundle_ready`, a read-only release-notes draft generator, a read-only operator publish plan that reports `operator_publish_plan_ready` with `agentMayExecutePlan=false`, a read-only operator handoff manifest that reports `operator_handoff_manifest_ready`, a read-only package source drift check that reports `package_source_unchanged`, read-only operator publish selection reviews that report `operator_publish_selection_ready` for `local_operator_rc`, `npm_rc_publish`, and `github_release_artifact` while keeping `agentMayExecuteSelectedPath=false`, a final operator decision packet with basename-only `reportFiles`/`reportsReady`, an operator publish handoff that defines the approval boundary, a local RC artifact check that reports `artifact_verified`, and a Temp-HOME OpenClaw install smoke that reports `install_smoke_passed`.
- Setup runbook: `docs/releases/OPENCLAW_CLIQ_CHANNEL_SETUP.md`; RC checklist: `docs/releases/OPENCLAW_CLIQ_CHANNEL_V0_4_RC_CHECKLIST.md`.
- Controlled live outbound smoke, local inbound polling dry-runs, Bot webhook receive/auth/normalize smoke, public callback smoke, live ingress/no-response diagnostics, status/read lifecycle smoke, turn-ledger loop-prevention smoke, status/routing diagnostics smoke, AI troubleshooting dry-runs, fake host native dispatch smoke, live smoke gate, trusted reply evidence bundle/prepare/checking with `sha256:` sender/message/reply references, RC pack/artifact/install/promotion/operator-bundle/release-note/publish-plan/manifest/source-drift/selection-review preflights, and host compatibility revalidation are now unblocked for trusted targets; a public Bot callback plus one controlled trusted Mention-to-agent reply have been verified through the operator Cloudflare route, with durable tunnel/gateway selection remaining for production operations. The public callback smoke is `ops/scripts/openclaw_cliq_public_callback_smoke.sh`; it accepts any HTTPS `ZOHO_CLIQ_PUBLIC_WEBHOOK_URL`, rejects placeholder URLs, checks missing-secret `401` plus authenticated unsupported-handler `200`, and writes redacted `openclaw_cliq_public_callback_smoke` JSON evidence. For “Bot message sent but no answer”, run `ops/scripts/openclaw_cliq_bot_no_response_packet.sh`; it embeds `handlerTrigger` from `ops/scripts/openclaw_cliq_handler_trigger_packet.sh` when `no_recent_webhook_ingress` points at a Zoho Bot handler trigger/save issue. The one-shot trusted reply bundle supports `ZOHO_CLIQ_TRUSTED_REPLY_PLAN_ONLY=1` for a route-first checklist before delivery facts exist, writes a redacted plan report with `missingFacts`/`readyFacts`, `nextAction`, `readyForFinalBundle`, `reportFiles`, `reportsReady`, `redaction`, `collectionGuide`, and `acceptedFactSources`, can consume a hash-only `ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE`, and emits route preflight JSON only on blockers such as `agent_binding_mismatch` without creating trusted reply evidence/check reports. Template: `docs/releases/OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_TEMPLATE.json`; one-shot bundle: `ops/scripts/openclaw_cliq_trusted_reply_evidence_bundle.sh`; facts prepare script: `ops/scripts/openclaw_cliq_trusted_reply_facts_prepare.sh`; hash helper: `ops/scripts/openclaw_cliq_hash_ref.sh`; evidence prepare script: `ops/scripts/openclaw_cliq_trusted_reply_evidence_prepare.sh`; no-response packet: `ops/scripts/openclaw_cliq_bot_no_response_packet.sh`; handler trigger packet: `ops/scripts/openclaw_cliq_handler_trigger_packet.sh`; artifact check: `ops/scripts/openclaw_cliq_rc_artifact_check.sh`; install smoke: `ops/scripts/openclaw_cliq_rc_install_smoke.sh`; promotion check: `ops/scripts/openclaw_cliq_rc_promotion_check.sh`; operator bundle: `ops/scripts/openclaw_cliq_rc_operator_publish_bundle.sh`; release notes draft: `ops/scripts/openclaw_cliq_rc_release_notes_draft.sh`; publish plan: `ops/scripts/openclaw_cliq_rc_publish_plan.sh`; handoff manifest: `ops/scripts/openclaw_cliq_rc_operator_handoff_manifest.sh`; source drift check: `ops/scripts/openclaw_cliq_rc_source_drift_check.sh`; selection review: `ops/scripts/openclaw_cliq_rc_operator_selection_review.sh`; operator handoff: `docs/releases/OPENCLAW_CLIQ_CHANNEL_V0_4_OPERATOR_PUBLISH_HANDOFF.md`.

### 🚧 Zoho CRM (guarded fixture write path implemented)

- Implemented commands: `crm status`, `crm sdk-status`, `crm write-plan`, `crm upsert` dry-run, `crm upsert-gate`, `crm write-audit`, `crm fixture-plan`, `crm fixture-execute`, `crm fixture-evidence`, `crm modules`, `crm fields`, `crm list`, `crm get`, `crm search`
- SDK adoption: `crm-003` added `zoho crm sdk-status` plus optional `zoho-cli[crm-sdk]` packaging for official `zohocrmsdk8_0==5.0.0`; `crm-004` added the optional `zoho_cli/crm_sdk.py` SDK adapter skeleton with data-center mapping and `ZOHO_CRM_SDK_RESOURCE_PATH`; `crm-005` added explicit `--adapter sdk-v8` read-only parity gates for modules/fields/list/get/search; `crm-006` locks the API version policy: HTTP v2 remains default, SDK/API v8 stays explicit. Plan: `docs/architecture/CRM_V0_5_SDK_ADOPTION_PLAN.md`.
- Write planning: `crm-007` added `zoho crm write-plan` and `writeSurfacePolicy` diagnostics. `crm-008` added `zoho crm upsert` as dry-run-only: it accepts JSON payloads, records duplicate-check fields and idempotency key, returns field names plus payload digest, and blocks `--execute` with `live_write_not_enabled`. `crm-009` added `zoho crm upsert-gate` to keep live upsert deferred until OAuth scope, audit persistence, and controlled live fixture evidence are ready. `crm-010` added redacted JSONL audit persistence plus `zoho crm write-audit` for dry-run/gate events. `crm-011` added `zoho crm fixture-plan` to evaluate controlled live fixture readiness without writing CRM data. `crm-012` added `zoho crm fixture-execute`, which defaults to dry-run and can only perform one live fixture upsert when the environment gate, exact approval token, cleanup plan, payload digest, idempotency key, and persisted dry-run/gate/fixture-plan audit evidence all match. Contract: `docs/architecture/CRM_WRITE_SURFACE_CONTRACT.md`.
- Live smoke harness: `ops/scripts/crm_fixture_payload_preflight.sh` checks a copied fixture payload plus cleanup plan locally before any Zoho call and emits redacted `payload_preflight_ready` or blocker JSON; cleanup plans must now include a selector such as fixture email, record id, duplicate field, idempotency key, or payload digest, otherwise `cleanup_plan_selector_missing` blocks before any Zoho-backed smoke. The report exposes only redacted `cleanup.selectorTypes` categories, not raw selector values. `ops/scripts/crm_fixture_operator_packet.sh` combines that preflight with optional dry-run readiness evidence into one redacted status/next-action packet for agents, including `operatorReview.readyFacts`, `operatorReview.missingFacts`, redacted `operatorReview.nextCommands`, `operatorReview.actionBoundary`, `operatorReview.agentAutomation`, `operatorReview.liveApproval`, and `reportFiles`/`reportsReady` hints for AI-safe branching and artifact handoff. `operatorReview.actionBoundary` exposes command id buckets such as `agentExecutableCommandIds`, `operatorOnlyCommandIds`, and `zohoWriteCommandIds`; agents may run only the agent-executable dry-run/local ids and must stop on operator-only write ids. `operatorReview.agentAutomation.nextAgentCommand` embeds the redacted placeholder-only command preview for the next runnable dry-run/local step and stays `null` at operator-only or Zoho-writing boundaries. `operatorReview.liveApproval` exposes only booleans plus `readyFacts`/`missingFacts` such as `summary_file`, `payload_digest`, `idempotency_key`, and `required_approval`, so agents know when to stop for operator approval without logging the exact approval token. `ops/scripts/crm_fixture_live_smoke.sh` runs the controlled fixture sequence and writes redacted report files; it defaults to dry-run and only executes live when `ZOHO_CRM_FIXTURE_EXECUTE=1` and `ZOHO_CRM_ALLOW_LIVE_FIXTURE=1`. `crm-014` added `zoho crm fixture-evidence` to classify those reports as `incomplete`, `ready_for_operator_live_fixture`, or `live_fixture_recorded`; `ops/scripts/crm_fixture_operator_readiness_bundle.sh` wraps an existing smoke summary plus fixture evidence into a no-write operator readiness bundle with basename-only `reportFiles`/`reportsReady` metadata, redacted `operatorReview.nextCommands`, and `operatorReview.actionBoundary` buckets that mirror the operator packet stop/go contract, and blocks placeholder payloads with `fixture_payload_placeholder_email`. `docs/releases/CRM_V0_5_FIXTURE_PAYLOAD_TEMPLATE.json` is a safe starting payload for dry-run planning; operators must copy/edit it outside the repo and replace the `.example.invalid` address with a dedicated test address before live mode.
- Current limitation: normal `zoho crm upsert --execute` remains blocked; real CRM writes are limited to the explicit controlled fixture harness.

### 🧪 Membrane bridge (experimental fast-fallback)

- Bridge commands: `membrane doctor`, `membrane discover`, `membrane connections`, `membrane actions`, `membrane run`, `membrane raw`
- Preset lookup: `--preset zoho-cliq|zoho-crm` resolves connection IDs from config/env to reduce manual setup friction
- Thin CRM wrapper: `crm bridge-run <action-id> --bridge membrane` delegates one call through Membrane while keeping `zoho-cli` entrypoints stable
- Purpose: quickly reuse Membrane-hosted Zoho connectors while preserving `zoho-cli` as the stable front door
- Requirement: `membrane` binary installed (`npm install -g @membranehq/cli`)

---

## Output formats

```bash
# JSON (default, script-friendly)
zoho mail list | jq '.[].subject'

# Markdown tables (--md flag)
zoho --md mail list
zoho --md folders list

# Errors go to stderr, data to stdout
zoho mail list 2>/dev/null
```

---

## Global flags

| Flag | Env var | Description |
| --- | --- | --- |
| `--account EMAIL` | `ZOHO_ACCOUNT` | Account to use |
| `--config PATH` | `ZOHO_CONFIG` | Config file path |
| `--md` | — | Markdown table output |
| `--debug` | — | HTTP + debug logs to stderr |

---

## Project structure

```text
zoho_cli/
├── core/              # Shared platform layers
│   ├── auth/          # OAuth flow, token refresh
│   ├── config/        # Config loading, regions
│   ├── http/          # HTTP client with error handling
│   ├── output/        # JSON/Markdown formatters
│   ├── errors/        # Error types and exit handling
│   └── pagination/    # Pagination helpers
├── products/          # Product modules (mail/cliq/crm)
├── commands/          # Typer registrars + extracted command-family builders
│   ├── cliq_channel_management.py  # Cliq channel/member/chat-control command bodies
│   ├── cliq_identity.py   # Cliq whoami/user-resolve command bodies
│   ├── cliq_org_admin.py  # Cliq org-admin list command bodies
│   ├── cliq_org_directory.py  # Cliq users/teams command bodies
│   ├── cliq_platform_extensions.py  # Cliq widgets/domains/emails command bodies
│   ├── cliq_productivity.py  # Cliq events/reminders/meetings/databases command bodies
│   └── cliq_readiness.py  # Cliq status/capabilities command bodies
├── cli.py             # CLI entry point (Typer)
└── registry.py        # Command registration

ops/state/             # Project state files (source of truth)
docs/roadmap/          # Release plans and milestones
integrations/openclaw/ # OpenClaw automation helpers
```

---

## Development

```bash
uv venv && uv pip install -e ".[dev]"
pytest
make release-gate   # Packaging + lint checks
```

Live probe helpers under `tests/auto_pilot/` now default to the global Zoho config path (`zoho config path`) and only need `--config` when you want an override.

### State-driven workflow

Project state lives in `ops/state/*.yml`:
- `module_status.yml` — Module priorities and blockers
- `active_task.yml` — Current task with success criteria
- `work_queue.yml` — Backlog of tasks
- `test_status.yml`, `release_status.yml` — Verification tracking

---

## Development status and roadmap (from `ops/state`, updated 2026-05-12)

### Current progress

| Module | Status | Current phase | Notes |
| --- | --- | --- | --- |
| Mail | ✅ Completed | stabilization_complete | Shipping baseline is stable. |
| Cliq | ✅ Completed for RC | workflow_packaging_complete_with_deferred_external_blockers | Mail+Cliq AI-employee core is ready for RC; endpoint-limited tail is deferred post-RC. |
| OpenClaw Cliq channel | ✅ Completed for RC | operator_publish_post_crm_state_sync_decision_ready | `cliq-channel-401..488` added the installable package, config/setup UX, security/employee policy gates, SDK session/mention/approval seams, JSON-safe CLI process execution, native outbound delivery, normalized/deduped inbound polling, Bot webhook intake, status/read lifecycle handling, turn-ledger loop prevention, status/capability/routing diagnostics, AI troubleshooting docs, native OpenClaw agent turn dispatch, redacted observability/privacy diagnostics, the redacted fake/live smoke gate harness, host compatibility maintenance runbook, v0.4 RC checklist, repeatable RC package preflight, real Bot handler templates, Deluge Map-string Message Handler hardening, direct Bot reply fallback through real `chatId` for synthetic `webhook-*` / `zoho-message-*` ids, controlled direct fallback smoke with `deliveryCount=1`, post-hardening RC artifact/handoff evidence refresh, handler runtime contract coverage, RC package metadata, trusted reply evidence preparation/checking, a tunnel-agnostic public callback smoke, a native dispatch identity fix that keeps accepted Cliq turns on `Provider`/`Surface=cliq` for automatic direct reply delivery, controlled live Bot Mention-to-agent reply evidence with `deliveryCount=1` and `trusted_reply_recorded`, redacted live ingress diagnostics, a combined Bot no-response packet with embedded handler trigger diagnostics, synchronized RC/Lane 3 docs for that handler-trigger flow, post-doc-sync/post-CRM selector metadata/post-CRM command-preview/post-CRM report-metadata/post-CRM readiness-report-metadata/post-CRM live-approval-fact-categories/post-CRM action-boundary/post-CRM readiness-action-boundary/post-CRM state-sync/post-operator-paths source-drift/decision evidence showing `package_source_unchanged` despite repo docs/state changes after the handoff manifest, an operator publish handoff, a no-publish local RC artifact check that reports `artifact_verified`, a Temp-HOME OpenClaw install smoke that reports `install_smoke_passed`, a strict no-publish RC promotion preflight that requires both before reporting `ready_for_operator_publish`, a no-publish operator review bundle that reports `operator_publish_bundle_ready`, a read-only release-notes draft generator, a read-only publish plan that reports `operator_publish_plan_ready`, a read-only handoff manifest that reports `operator_handoff_manifest_ready`, a read-only source drift check that reports `package_source_unchanged`, read-only selected path reviews that report `operator_publish_selection_ready` for local/operator, npm RC, and GitHub artifact paths, and final decision packet `reportFiles`/`reportsReady` metadata for AI-safe evidence handoff. |
| CRM | 🚧 In progress | v0_5_agent_next_command_preview | Read-only scaffold is present; `crm-003/004/005/006/007/008/009/010/011/012/013/014/015/016/017/018/019/020/021/022/023/024/025/026/028/029` added SDK readiness diagnostics, optional SDK packaging, the default-disabled SDK adapter, explicit `--adapter sdk-v8` read-only gates, the HTTP v2 vs SDK/API v8 policy, machine-readable write safety gates, upsert dry-run output, the live upsert gate, redacted write audit persistence, controlled fixture readiness planning, the guarded `fixture-execute` live fixture harness, the CRM fixture live smoke script, the fixture evidence checker, a no-write operator readiness bundle, a no-Zoho payload preflight, a no-write operator packet wrapper, cleanup-plan quality blockers, cleanup selector blockers, redacted cleanup selector type metadata, redacted operator review facts, redacted operator command previews, basename-only report metadata, redacted `operatorReview.liveApproval` booleans, live-approval `readyFacts`/`missingFacts`, operator packet `operatorReview.actionBoundary` command id buckets, readiness-bundle `nextCommands`/`actionBoundary` buckets for operator-only fixture approval, `operatorReview.agentAutomation` summaries for AI-safe next-command branching, and embedded `operatorReview.agentAutomation.nextAgentCommand` previews for the next agent-executable dry-run/local step while preserving the current JSON-safe HTTP adapter as default. |

### Current platform lane (AI-employee v1)

| Task | Status | Notes |
| --- | --- | --- |
| `platform-204` architecture contract | ✅ Completed | Mail+Cliq core, control/execution/escalation boundaries locked in docs. |
| `platform-205` release gate | ✅ Completed | Gate checklist executed, integration pass/skip mapping recorded, deferred external blockers accepted as non-blocking for RC. |
| `platform-206` interop contract | ✅ Completed | Contract locked and now consumed by operator runbook docs for platform-207 handoff. |
| `mail-010` workflow package | ✅ Completed | Workflow contract now includes end-to-end operator transcript and focused verification evidence for platform-207 consumption. |
| `platform-207` RC package | ✅ Completed | Docs package consolidated and RC/version checkpoint refreshed for RC approval. |
| `platform-208` CLI information architecture | ✅ Completed | Module-first help taxonomy cleanup is complete; remaining endpoint limitations are capability-gated. |

### Current release posture

- Current version: `0.2.1`
- Next active target: operator decision on the native Zoho Cliq channel RC publish/tag path now that local promotion preflight reports `ready_for_operator_publish`; fresh Bot no-response triage starts with `ops/scripts/openclaw_cliq_bot_no_response_packet.sh` and its embedded `handlerTrigger`; CRM fixture live run remains gated on a dedicated payload and cleanup plan.
- Release candidate: `false`
- Broad automated gate: final `make release-gate && make ci` is green for `0.2.1`; [v0.2.1](https://github.com/adwasd-dvd/zoho-cli/releases/tag/v0.2.1) is the current stable release.

### Deferred external blockers (do not block release)

- Native Cliq public Bot callback reachability and one controlled trusted agent reply have been verified through the operator Cloudflare route; durable production tunnel/gateway selection remains an operations decision.
- Zoho refresh throttling can recur in bursty live probe loops; treat `token_refresh_rate_limited` as `skip_deferred` and rerun after cooldown.
- Cliq-194 live read-ack endpoint is still unsupported on active network/token, but runtime continuity is capability-gated (watch-act falls back safely instead of hard-failing).
- Cliq maintenance export verification (`cliq-165`) is blocked by API-side `inactive_appaccount_user`.
- Several Cliq endpoints are still unsupported on the current org/network (`not_supported`) or require extra scopes.
- CRM broad live writes remain blocked; controlled CRM live verification now requires an operator-approved fixture payload and `ZOHO_CRM_ALLOW_LIVE_FIXTURE=1`.

### Near-term plan

1. Keep unsupported Cliq endpoints capability-gated so they do not stall AI-employee internal-loop readiness.
2. Keep remaining Cliq helper-heavy modularization opportunistic while the
   channel lane moves.
3. Use the native OpenClaw Cliq operator publish handoff to choose the RC artifact path; keep publish/tag/npm promotion and published integrity updates operator-approved only. For Bot no-response reports, inspect the no-response packet's embedded `handlerTrigger` before editing Zoho handlers.
4. Run the guarded CRM fixture harness only with a dedicated test record; keep normal live writes disabled while the fixture path records redacted attempt/result audit evidence.

---

## Release train

| Version | Milestone | Status |
| --- | --- | --- |
| v0.2.0 | Mail stabilized + shared core extracted | ✅ Released |
| v0.2.1rc1 | Mail+Cliq AI-employee RC with deferred external blockers | ✅ Published prerelease |
| v0.2.1 | Mail+Cliq AI-employee stable release | ✅ Released |
| v0.3.x | Cliq live parity and export unblock closure | ⏳ Pending external unblock |
| v0.4.x | Native OpenClaw Zoho Cliq channel | 📋 Next active product lane |
| v0.5.x | CRM SDK adapter, live validation, and follow-on CRM work | 🚧 Active |

---

## OpenClaw automation

This repo includes OpenClaw-facing skill and helper docs/scripts:

- `skill/SKILL.md` — canonical AI skill file
- `integrations/openclaw/SKILL.md` — integration copy for OpenClaw workflows
- `integrations/openclaw/SKILL_INDEX.md` — maintainer checklist/index
- `integrations/openclaw/LANE3_AI_USER_GUIDE.md` — AI-user lane3 sync/update guide
- `integrations/openclaw/CLIQ_CHANNEL_DEVELOPMENT_GUIDE.md` — v0.4 native Cliq channel development guide
- `integrations/openclaw/bin/pull_lane3_only.sh` — lane3-only pull/sync script
- `integrations/openclaw/bin/run-scan.example.sh` — long-running scan example
- `integrations/openclaw/quick_test.sh` — lightweight attachment smoke test

---

## Documentation lanes (required maintenance)

This project maintains three documentation lanes:

1. coder development/operations docs (state, progress, memory)
2. human user/project docs (README + docs)
3. AI-user skill/docs/scripts (skill + OpenClaw integration files)

See `docs/DOCUMENTATION_LANES.md` for the full contract and update workflow.

---

## Contributing

This project is forked from [robsannaa/zoho-cli](https://github.com/robsannaa/zoho-cli).

**Current maintainers:**
- @adwasd-dvd (primary development, OpenClaw integration)

**Original author:**
- @robsannaa (initial Zoho Mail implementation)

**Ways to contribute:**
- Report bugs or request features via GitHub issues
- Submit PRs for bug fixes or new commands
- Help with documentation and examples

---

## License

MIT License — see [LICENSE](LICENSE) for details.
