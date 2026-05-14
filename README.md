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
- Current slice: `cliq-channel-519` is complete after `cliq-channel-506/507/508/509/510/511/512/513/514/515/516/517/518/520/521`; the channel supports `reply_mode=deluge_response` for real Bot handlers, captures the native OpenClaw final answer into webhook JSON `text`, and Message/Mention/Participation/Context Deluge templates now copy only `webhook_response.text` into a clean `response.text` map before returning it. This keeps Zoho's native Bot response surface small enough to render while avoiding the second-hop OAuth `zoho cliq send` path. The no-response diagnostics expose `diagnosis.code` plus `handlers.directMessageRequirement` so public-callback-green/no-ingress cases point at Zoho handler save/trigger state, especially a missing saved **Message Handler** for plain direct Bot DMs. `ops/scripts/openclaw_cliq_bot_handler_operator_prompt.sh --md` renders the compact human handoff for that Zoho UI step, and `ops/scripts/openclaw_cliq_bot_handler_template_render.sh --md --handlers message` renders a minimal direct-DM Deluge block that uses only `message`, `user`, and `chat`, avoids optional Deluge variables that can be undefined before `invokeurl`, closes assigned `invokeurl [...]` tasks with `];`, and returns the clean response map. The cross-lane RC autonomy packet now surfaces `save_openclaw_cliq_bot_message_handler` as the first `operatorActionRequests` item and exposes `nextOperatorActionId=save_openclaw_cliq_bot_message_handler` plus `nextOperatorActionRequest`, so recurring agents ask for the Bot Message Handler save/recheck step before publish-path/CRM prompts without reparsing the full request list. Bot emoji support is deliberately conservative: true Zoho lifecycle/status reactions are attempted only when an inbound event has a native message id plus chat/channel route facts; synthetic Deluge ids such as `zoho-message-*` and `webhook-*` skip true reaction/read calls with `synthetic_message_id`, and Deluge-native synthetic replies get a tested visible `✅ ` prefix fallback with privacy-safe `reactionFallback` diagnostics. The source-drift guard skips newer blocked handoff drafts and defaults to the newest ready handoff manifest, keeping recurring autonomy checks from false-blocking on stale failed manifest attempts. The no-publish package chain was refreshed after the agent-binding diagnostics package-source change; the current local RC tarball still needs refresh for the reaction-fallback package-source change before it supersedes shasum `7f50359917d1e784f3ebc28e85b8303f700dbfdc`. The existing RC chain still includes the `cliq-channel-473/474` no-response handler-trigger flow, `cliq-channel-501/502/503` direct chat-id fallback plus quiet lifecycle/rate-limit diagnostics and artifact refresh, cross-lane autonomy/operator prompt tooling, read-only publish handoff, local artifact/install/promotion checks, and all publish/tag/release/integrity-fill actions remain operator-approved only.
- Agent binding: `cliq-channel-520` verifies `oldsix老六` / `cliq/default` is bound to OpenClaw agent `zoho-employee-test` through OpenClaw `bindings[]`, matching Discord's account-to-agent selection model. Deep Cliq channel status now exposes `agentBinding.agentId` plus `diagnostics.agentBinding.agentId` before live Bot traffic, and `cliq-channel-521` refreshed no-publish RC evidence for that package-source change.
- Next package slice: `cliq-channel-522` refreshes the no-publish RC artifact/install/promotion/handoff evidence after the `cliq-channel-519` reaction-fallback package-source change. True Bot reaction support remains gated on Zoho providing a native inbound message id; synthetic Message Handler ids use the documented emoji-prefixed reply fallback.
- Setup runbook: `docs/releases/OPENCLAW_CLIQ_CHANNEL_SETUP.md`; RC checklist: `docs/releases/OPENCLAW_CLIQ_CHANNEL_V0_4_RC_CHECKLIST.md`.
- Controlled live outbound smoke, local inbound polling dry-runs, Bot webhook receive/auth/normalize smoke, public callback smoke, live ingress/no-response diagnostics, status/read lifecycle smoke, turn-ledger loop-prevention smoke, status/routing diagnostics smoke, AI troubleshooting dry-runs, fake host native dispatch smoke, live smoke gate, trusted reply evidence bundle/prepare/checking with `sha256:` sender/message/reply references, RC pack/artifact/install/promotion/operator-bundle/release-note/publish-plan/manifest/source-drift/selection-review/decision-packet preflights, the cross-lane autonomy packet, and host compatibility revalidation are now unblocked for trusted targets; a public Bot callback plus one controlled trusted Mention-to-agent reply have been verified through the operator Cloudflare route, with durable tunnel/gateway selection remaining for production operations. The public callback smoke is `ops/scripts/openclaw_cliq_public_callback_smoke.sh`; it accepts any HTTPS `ZOHO_CLIQ_PUBLIC_WEBHOOK_URL`, rejects placeholder URLs, checks missing-secret `401` plus authenticated unsupported-handler `200`, and writes redacted `openclaw_cliq_public_callback_smoke` JSON evidence. For “Bot message sent but no answer”, run `ops/scripts/openclaw_cliq_bot_no_response_packet.sh`; it embeds `handlerTrigger` from `ops/scripts/openclaw_cliq_handler_trigger_packet.sh` when `no_recent_webhook_ingress` points at a Zoho Bot handler trigger/save issue, and reports `dispatch_reply_rate_limited` when the handler plus OpenClaw dispatch worked but the final Cliq send hit Zoho throttling. For a compact human handoff before editing Zoho, run `ops/scripts/openclaw_cliq_bot_handler_operator_prompt.sh --md`; it reports `handler_operator_prompt_ready` when the handoff is ready and renders the direct-DM Message Handler requirement, public callback recheck, template-render command, one-fresh-message rule, and no-response command without storing raw payloads, message text, reply text, local paths, or secrets. For the exact paste block, run `ops/scripts/openclaw_cliq_bot_handler_template_render.sh --md --handlers message`; it reports `handler_template_render_ready` and renders fenced Deluge with `reply_mode=deluge_response`, clean `response.put("text",webhook_response.get("text"));` return handling, the configured public URL, and a secret placeholder only. The one-shot trusted reply bundle supports `ZOHO_CLIQ_TRUSTED_REPLY_PLAN_ONLY=1` for a route-first checklist before delivery facts exist, writes a redacted plan report with `missingFacts`/`readyFacts`, `nextAction`, `readyForFinalBundle`, `reportFiles`, `reportsReady`, `redaction`, `collectionGuide`, and `acceptedFactSources`, can consume a hash-only `ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE`, and emits route preflight JSON only on blockers such as `agent_binding_mismatch` without creating trusted reply evidence/check reports. Template: `docs/releases/OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_TEMPLATE.json`; one-shot bundle: `ops/scripts/openclaw_cliq_trusted_reply_evidence_bundle.sh`; facts prepare script: `ops/scripts/openclaw_cliq_trusted_reply_facts_prepare.sh`; hash helper: `ops/scripts/openclaw_cliq_hash_ref.sh`; evidence prepare script: `ops/scripts/openclaw_cliq_trusted_reply_evidence_prepare.sh`; no-response packet: `ops/scripts/openclaw_cliq_bot_no_response_packet.sh`; handler trigger packet: `ops/scripts/openclaw_cliq_handler_trigger_packet.sh`; handler operator prompt: `ops/scripts/openclaw_cliq_bot_handler_operator_prompt.sh`; handler template renderer: `ops/scripts/openclaw_cliq_bot_handler_template_render.sh`; artifact check: `ops/scripts/openclaw_cliq_rc_artifact_check.sh`; install smoke: `ops/scripts/openclaw_cliq_rc_install_smoke.sh`; promotion check: `ops/scripts/openclaw_cliq_rc_promotion_check.sh`; operator bundle: `ops/scripts/openclaw_cliq_rc_operator_publish_bundle.sh`; release notes draft: `ops/scripts/openclaw_cliq_rc_release_notes_draft.sh`; publish plan: `ops/scripts/openclaw_cliq_rc_publish_plan.sh`; handoff manifest: `ops/scripts/openclaw_cliq_rc_operator_handoff_manifest.sh`; source drift check: `ops/scripts/openclaw_cliq_rc_source_drift_check.sh`; selection review: `ops/scripts/openclaw_cliq_rc_operator_selection_review.sh`; decision packet: `ops/scripts/openclaw_cliq_rc_operator_decision_packet.sh`; RC autonomy packet: `ops/scripts/zoho_cli_rc_autonomy_packet.sh` with redacted `operatorActionRequests`; operator action prompt: `ops/scripts/zoho_cli_rc_operator_action_prompt.sh` (`--md` prints the redacted human handoff); operator handoff: `docs/releases/OPENCLAW_CLIQ_CHANNEL_V0_4_OPERATOR_PUBLISH_HANDOFF.md`.

### 🚧 Zoho CRM (guarded fixture write path implemented)

- Implemented commands: `crm status`, `crm sdk-status`, `crm write-plan`, `crm upsert` dry-run, `crm upsert-gate`, `crm write-audit`, `crm fixture-plan`, `crm fixture-execute`, `crm fixture-evidence`, `crm modules`, `crm fields`, `crm list`, `crm get`, `crm search`
- SDK adoption: `crm-003` added `zoho crm sdk-status` plus optional `zoho-cli[crm-sdk]` packaging for official `zohocrmsdk8_0==5.0.0`; `crm-004` added the optional `zoho_cli/crm_sdk.py` SDK adapter skeleton with data-center mapping and `ZOHO_CRM_SDK_RESOURCE_PATH`; `crm-005` added explicit `--adapter sdk-v8` read-only parity gates for modules/fields/list/get/search; `crm-006` locks the API version policy: HTTP v2 remains default, SDK/API v8 stays explicit. Plan: `docs/architecture/CRM_V0_5_SDK_ADOPTION_PLAN.md`.
- Write planning: `crm-007` added `zoho crm write-plan` and `writeSurfacePolicy` diagnostics. `crm-008` added `zoho crm upsert` as dry-run-only: it accepts JSON payloads, records duplicate-check fields and idempotency key, returns field names plus payload digest, and blocks `--execute` with `live_write_not_enabled`. `crm-009` added `zoho crm upsert-gate` to keep live upsert deferred until OAuth scope, audit persistence, and controlled live fixture evidence are ready. `crm-010` added redacted JSONL audit persistence plus `zoho crm write-audit` for dry-run/gate events. `crm-011` added `zoho crm fixture-plan` to evaluate controlled live fixture readiness without writing CRM data. `crm-012` added `zoho crm fixture-execute`, which defaults to dry-run and can only perform one live fixture upsert when the environment gate, exact approval token, cleanup plan, payload digest, idempotency key, and persisted dry-run/gate/fixture-plan audit evidence all match. Contract: `docs/architecture/CRM_WRITE_SURFACE_CONTRACT.md`.
- Live smoke harness: `ops/scripts/crm_fixture_payload_preflight.sh` checks a copied fixture payload plus cleanup plan locally before any Zoho call and emits redacted `payload_preflight_ready` or blocker JSON; cleanup plans must now include a selector such as fixture email, record id, duplicate field, idempotency key, or payload digest, otherwise `cleanup_plan_selector_missing` blocks before any Zoho-backed smoke. The report exposes only redacted `cleanup.selectorTypes` categories, not raw selector values. `ops/scripts/crm_fixture_operator_packet.sh` combines that preflight with optional dry-run readiness evidence into one redacted status/next-action packet for agents, including `operatorReview.readyFacts`, `operatorReview.missingFacts`, redacted `operatorReview.nextCommands`, `operatorReview.actionBoundary`, `operatorReview.agentAutomation`, `operatorReview.liveApproval`, and `reportFiles`/`reportsReady` hints for AI-safe branching and artifact handoff. `ops/scripts/crm_fixture_agent_next_command.sh` wraps that packet into a compact `crm_fixture_agent_next_command` summary, classifying the next step as `operator_input_required`, `agent_next_command_ready`, `stop_before_operator_live_fixture`, or `agent_command_not_allowlisted` while preserving basename-only report handoff. It also exposes `operatorReview.agentExecutableCommandAllowlist`, `operatorReview.agentExecutableCommandAllowed`, and `safety.nextCommandAllowedForAgent`; agents may execute only `agent_next_command_ready` when the command id and script path match that built-in local/dry-run allowlist. `operatorReview.actionBoundary` exposes command id buckets such as `agentExecutableCommandIds`, `operatorOnlyCommandIds`, and `zohoWriteCommandIds`; agents may run only the agent-executable dry-run/local ids and must stop on operator-only write ids. `operatorReview.agentAutomation.nextAgentCommand` embeds the redacted placeholder-only command preview for the next runnable dry-run/local step and stays `null` at operator-only or Zoho-writing boundaries. `operatorReview.liveApproval` exposes only booleans plus `readyFacts`/`missingFacts` such as `summary_file`, `payload_digest`, `idempotency_key`, and `required_approval`, so agents know when to stop for operator approval without logging the exact approval token. `ops/scripts/crm_fixture_live_smoke.sh` runs the controlled fixture sequence and writes redacted report files; it defaults to dry-run and only executes live when `ZOHO_CRM_FIXTURE_EXECUTE=1` and `ZOHO_CRM_ALLOW_LIVE_FIXTURE=1`. `crm-014` added `zoho crm fixture-evidence` to classify those reports as `incomplete`, `ready_for_operator_live_fixture`, or `live_fixture_recorded`; `ops/scripts/crm_fixture_operator_readiness_bundle.sh` wraps an existing smoke summary plus fixture evidence into a no-write operator readiness bundle with basename-only `reportFiles`/`reportsReady` metadata, redacted `operatorReview.nextCommands`, and `operatorReview.actionBoundary` buckets that mirror the operator packet stop/go contract, and blocks placeholder payloads with `fixture_payload_placeholder_email`. `docs/releases/CRM_V0_5_FIXTURE_PAYLOAD_TEMPLATE.json` is a safe starting payload for dry-run planning and `docs/releases/CRM_V0_5_FIXTURE_CLEANUP_PLAN_TEMPLATE.md` is the matching cleanup-plan starter; operators must copy/edit both outside the repo and replace placeholders with a dedicated test address plus selector before live mode.
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
make lint          # Ruff checks source and tests
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

## Development status and roadmap (from `ops/state`, updated 2026-05-13)

### Current progress

| Module | Status | Current phase | Notes |
| --- | --- | --- | --- |
| Mail | ✅ Completed | stabilization_complete | Shipping baseline is stable. |
| Cliq | ✅ Completed for RC | workflow_packaging_complete_with_deferred_external_blockers | Mail+Cliq AI-employee core is ready for RC; endpoint-limited tail is deferred post-RC. |
| OpenClaw Cliq channel | 🚧 RC-ready locally; product follow-up pending | bot_direct_dm_normal_agent_bound_reactions_pending | `cliq-channel-401..521` plus `platform-214/215/216/217/218/221` added the installable package, config/setup UX, security/employee policy gates, native outbound/inbound dispatch, Bot webhook intake, real Bot templates, Deluge Map-string hardening, direct Bot `--chat-id` fallback, quiet lifecycle/rate-limit diagnostics, no-response/handler-trigger packets, trusted reply evidence, no-publish RC artifact/install/promotion/operator handoff checks, cross-lane autonomy/operator prompts, Deluge-native `reply_mode=deluge_response`, direct-DM diagnosis, a compact Bot handler operator prompt, a no-secret template renderer for the exact Zoho Message Handler paste block, clean response-map handling confirmed by the operator, and deep `cliq/default -> zoho-employee-test` agent-binding diagnostics. Next product slice is Bot reaction discovery/fallback (`cliq-channel-519`); publish/tag/release/integrity-fill remain operator-approved only. |
| CRM | 🚧 In progress | v0_5_cleanup_plan_template | Read-only scaffold is present; `crm-003/004/005/006/007/008/009/010/011/012/013/014/015/016/017/018/019/020/021/022/023/024/025/026/028/029/030/031/032/033` added SDK readiness diagnostics, optional SDK packaging, the default-disabled SDK adapter, explicit `--adapter sdk-v8` read-only gates, the HTTP v2 vs SDK/API v8 policy, machine-readable write safety gates, upsert dry-run output, the live upsert gate, redacted write audit persistence, controlled fixture readiness planning, the guarded `fixture-execute` live fixture harness, the CRM fixture live smoke script, the fixture evidence checker, a no-write operator readiness bundle, a no-Zoho payload preflight, a no-write operator packet wrapper, cleanup-plan quality blockers, cleanup selector blockers, redacted cleanup selector type metadata, redacted operator review facts, redacted operator command previews, basename-only report metadata, redacted `operatorReview.liveApproval` booleans, live-approval `readyFacts`/`missingFacts`, operator packet `operatorReview.actionBoundary` command id buckets, readiness-bundle `nextCommands`/`actionBoundary` buckets for operator-only fixture approval, `operatorReview.agentAutomation` summaries for AI-safe next-command branching, embedded `operatorReview.agentAutomation.nextAgentCommand` previews, a compact `crm_fixture_agent_next_command` wrapper for the next safe agent step, explicit agent-ready branch coverage, command allowlist enforcement for that wrapper, and a copy/edit cleanup-plan template now linked from RC autonomy prompts while preserving the current JSON-safe HTTP adapter as default. |

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
- Next active target: `cliq-channel-519` investigates Bot emoji reactions now that the clean-response `oldsix老六` direct Bot path is confirmed normal. It should preserve a real inbound message id for true reactions if Zoho exposes one, or ship a documented emoji-reply fallback if direct Message Handler payloads do not expose a usable id. Operator decision on the native Zoho Cliq channel RC publish/tag path and CRM fixture live run remain separately gated.
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
3. Run `ops/scripts/openclaw_cliq_bot_handler_template_render.sh --md --handlers message`, re-paste/save the rendered `oldsix老六` Message Handler template with `reply_mode=deluge_response`, then use the no-response packet to confirm fresh webhook ingress and a visible native Bot reply before choosing the RC publish path. Keep publish/tag/npm promotion and published integrity updates operator-approved only.
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
