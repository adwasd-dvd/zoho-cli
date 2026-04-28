# zoho-cli — Zoho Mail, Cliq, and CRM in your terminal

Fast, script-friendly CLI for Zoho Mail, Cliq, and CRM. JSON output by default, Markdown tables with `--md`. Pipe to `jq`, use in scripts, or feed directly to AI agents.

[![GitHub release](https://img.shields.io/github/v/release/adwasd-dvd/zoho-mail-cli-zomacli)](https://github.com/adwasd-dvd/zoho-mail-cli-zomacli/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## Quick start

```bash
# Install via uv (recommended)
uv tool install git+https://github.com/adwasd-dvd/zoho-mail-cli-zomacli

# Or pipx
pipx install git+https://github.com/adwasd-dvd/zoho-mail-cli-zomacli

# From source
git clone https://github.com/adwasd-dvd/zoho-mail-cli-zomacli
cd zoho-mail-cli-zomacli
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

### 🚧 Zoho CRM (read-only scaffold implemented)

- Implemented commands: `crm status`, `crm modules`, `crm fields`, `crm list`, `crm get`, `crm search`
- Current limitation: live verification is blocked because the test account is not in a CRM org.

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

## Development status and roadmap (from `ops/state`, updated 2026-04-28)

### Current progress

| Module | Status | Current phase | Notes |
| --- | --- | --- | --- |
| Mail | ✅ Completed | stabilization_complete | Shipping baseline is stable. |
| Cliq | 🚧 In progress | cliq-expansion-phase | `cliq-195` core package is closed for this milestone; non-critical tail is deferred post-v1. |
| CRM | ⛔ Blocked | phase_1_read_only_commands_implemented | Live org access is missing for the test account. |

### Current platform lane (AI-employee v1)

| Task | Status | Notes |
| --- | --- | --- |
| `platform-204` architecture contract | ✅ Completed | Mail+Cliq core, control/execution/escalation boundaries locked in docs. |
| `platform-205` release gate | ✅ Completed | Gate checklist executed, integration pass/skip mapping recorded, RC/version bump intentionally deferred until one more green development slice. |
| `platform-206` interop contract | ✅ Completed | Contract locked and now consumed by operator runbook docs for platform-207 handoff. |
| `mail-010` workflow package | 🚧 In progress | First contract slice landed in `docs/releases/MAIL_010_OPERATOR_WORKFLOW.md`; next is end-to-end example + verification notes. |

### Current release posture

- Current version: `0.2.0`
- Next version target: `0.2.1`
- Release candidate: `false`
- Broad automated gate: latest `make release-gate && make ci` is green, but release is still blocked by unresolved live integration blockers and pending integration gate closure.

### Active blockers (highest impact)

- Cliq maintenance export verification (`cliq-165`) is blocked by API-side `inactive_appaccount_user`.
- Several Cliq endpoints are still unsupported on the current org/network (`not_supported`) or require extra scopes.
- CRM live verification remains blocked until CRM org access is granted to the test account.

### Near-term plan

1. Extend `mail-010` from contract draft to end-to-end operator example + verification notes.
2. Consolidate `platform-207` release-candidate docs/quickstart/runbook around platform-205 + platform-206 contracts.
3. Keep unsupported Cliq endpoints capability-gated so they do not stall v1 internal-loop readiness.
4. Resume CRM live verification when CRM org access is available.

---

## Release train

| Version | Milestone | Status |
| --- | --- | --- |
| v0.2.0 | Mail stabilized + shared core extracted | ✅ Released |
| v0.2.1 | Cliq expansion hardening + blocker burn-down | 🚧 Active |
| v0.3.x | Cliq live parity and export unblock closure | ⏳ Pending external unblock |
| v0.4.x | CRM live validation and follow-on CRM work | 📋 Planned |

---

## OpenClaw automation

This repo includes OpenClaw-facing skill and helper docs/scripts:

- `skill/SKILL.md` — canonical AI skill file
- `integrations/openclaw/SKILL.md` — integration copy for OpenClaw workflows
- `integrations/openclaw/SKILL_INDEX.md` — maintainer checklist/index
- `integrations/openclaw/LANE3_AI_USER_GUIDE.md` — AI-user lane3 sync/update guide
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
