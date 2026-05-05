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
- Current slice: `cliq-channel-418` is complete; the channel now has account/network-aware session grammar, secure policy gates, native approval metadata, a JSON-safe `zoho` process adapter, native outbound send/reply/thread-reply delivery, fixture-backed inbound polling normalization/dedupe through `zoho cliq chats` + `zoho cliq context`, a Bot webhook intake route at `/webhooks/cliq` with secret verification, shared status/read lifecycle handling, a native turn ledger for duplicate/active/dead-letter loop prevention, operator-readable status/capability/routing diagnostics, AI-facing troubleshooting docs, native OpenClaw agent turn dispatch for accepted webhook/polling events, a redacted live smoke gate, a host compatibility repair runbook, and a v0.4 RC checklist.
- Setup runbook: `docs/releases/OPENCLAW_CLIQ_CHANNEL_SETUP.md`; RC checklist: `docs/releases/OPENCLAW_CLIQ_CHANNEL_V0_4_RC_CHECKLIST.md`.
- Controlled live outbound smoke, local inbound polling dry-runs, Bot webhook receive/auth/normalize smoke, status/read lifecycle smoke, turn-ledger loop-prevention smoke, status/routing diagnostics smoke, AI troubleshooting dry-runs, fake host native dispatch smoke, live smoke gate, and host compatibility revalidation are now unblocked for trusted targets; production rollout still waits for a reachable public Bot callback URL.

### 🚧 Zoho CRM (guarded fixture write path implemented)

- Implemented commands: `crm status`, `crm sdk-status`, `crm write-plan`, `crm upsert` dry-run, `crm upsert-gate`, `crm write-audit`, `crm fixture-plan`, `crm fixture-execute`, `crm modules`, `crm fields`, `crm list`, `crm get`, `crm search`
- SDK adoption: `crm-003` added `zoho crm sdk-status` plus optional `zoho-cli[crm-sdk]` packaging for official `zohocrmsdk8_0==5.0.0`; `crm-004` added the optional `zoho_cli/crm_sdk.py` SDK adapter skeleton with data-center mapping and `ZOHO_CRM_SDK_RESOURCE_PATH`; `crm-005` added explicit `--adapter sdk-v8` read-only parity gates for modules/fields/list/get/search; `crm-006` locks the API version policy: HTTP v2 remains default, SDK/API v8 stays explicit. Plan: `docs/architecture/CRM_V0_5_SDK_ADOPTION_PLAN.md`.
- Write planning: `crm-007` added `zoho crm write-plan` and `writeSurfacePolicy` diagnostics. `crm-008` added `zoho crm upsert` as dry-run-only: it accepts JSON payloads, records duplicate-check fields and idempotency key, returns field names plus payload digest, and blocks `--execute` with `live_write_not_enabled`. `crm-009` added `zoho crm upsert-gate` to keep live upsert deferred until OAuth scope, audit persistence, and controlled live fixture evidence are ready. `crm-010` added redacted JSONL audit persistence plus `zoho crm write-audit` for dry-run/gate events. `crm-011` added `zoho crm fixture-plan` to evaluate controlled live fixture readiness without writing CRM data. `crm-012` added `zoho crm fixture-execute`, which defaults to dry-run and can only perform one live fixture upsert when the environment gate, exact approval token, cleanup plan, payload digest, idempotency key, and persisted dry-run/gate/fixture-plan audit evidence all match. Contract: `docs/architecture/CRM_WRITE_SURFACE_CONTRACT.md`.
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

## Development status and roadmap (from `ops/state`, updated 2026-05-05)

### Current progress

| Module | Status | Current phase | Notes |
| --- | --- | --- | --- |
| Mail | ✅ Completed | stabilization_complete | Shipping baseline is stable. |
| Cliq | ✅ Completed for RC | workflow_packaging_complete_with_deferred_external_blockers | Mail+Cliq AI-employee core is ready for RC; endpoint-limited tail is deferred post-RC. |
| OpenClaw Cliq channel | 🚧 In progress | rc_package_ready_external_callback_deferred | `cliq-channel-401/402/416/403/414/404/405/406/407/408/413/409/410/417/415/411/412/418` added the installable package, config/setup UX, security/employee policy gates, SDK session/mention/approval seams, JSON-safe CLI process execution, native outbound delivery, normalized/deduped inbound polling, Bot webhook intake, status/read lifecycle handling, turn-ledger loop prevention, status/capability/routing diagnostics, AI troubleshooting docs, native OpenClaw agent turn dispatch, redacted observability/privacy diagnostics, the redacted fake/live smoke gate harness, host compatibility maintenance runbook, and v0.4 RC checklist. |
| CRM | 🚧 In progress | v0_5_controlled_fixture_live_smoke | Read-only scaffold is present; `crm-003/004/005/006/007/008/009/010/011/012` added SDK readiness diagnostics, optional SDK packaging, the default-disabled SDK adapter, explicit `--adapter sdk-v8` read-only gates, the HTTP v2 vs SDK/API v8 policy, machine-readable write safety gates, upsert dry-run output, the live upsert gate, redacted write audit persistence, controlled fixture readiness planning, and the guarded `fixture-execute` live fixture harness while preserving the current JSON-safe HTTP adapter as default. |

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
- Next active target: CRM v0.5 controlled fixture live smoke while public native Cliq Bot callback verification waits on a reachable tunnel/gateway URL.
- Release candidate: `false`
- Broad automated gate: final `make release-gate && make ci` is green for `0.2.1`; [v0.2.1](https://github.com/adwasd-dvd/zoho-cli/releases/tag/v0.2.1) is the current stable release.

### Deferred external blockers (do not block release)

- Native Cliq public Bot callback verification requires a reachable tunnel/gateway URL; local webhook auth/security gates pass.
- Zoho refresh throttling can recur in bursty live probe loops; treat `token_refresh_rate_limited` as `skip_deferred` and rerun after cooldown.
- Cliq-194 live read-ack endpoint is still unsupported on active network/token, but runtime continuity is capability-gated (watch-act falls back safely instead of hard-failing).
- Cliq maintenance export verification (`cliq-165`) is blocked by API-side `inactive_appaccount_user`.
- Several Cliq endpoints are still unsupported on the current org/network (`not_supported`) or require extra scopes.
- CRM broad live writes remain blocked; controlled CRM live verification now requires an operator-approved fixture payload and `ZOHO_CRM_ALLOW_LIVE_FIXTURE=1`.

### Near-term plan

1. Keep unsupported Cliq endpoints capability-gated so they do not stall AI-employee internal-loop readiness.
2. Keep remaining Cliq helper-heavy modularization opportunistic while the
   channel lane moves.
3. Continue the native OpenClaw Cliq channel in v0.4 with native agent turn dispatch next.
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
