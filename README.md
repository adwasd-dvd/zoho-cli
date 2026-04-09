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
   - Redirect URI: `http://localhost:51821/callback` (or add headless fallback)
   
2. **Authenticate**
   ```bash
   zoho login
   # For Cliq/CRM scopes:
   zoho login --with-cliq --with-crm
   ```

---

## What works now

### ✅ Zoho Mail (v0.2.0 stable)

- `zoho mail list` — List messages with filtering
- `zoho mail search "query"` — Full-text and field-based search
- `zoho mail get <id>` — Get full message content
- `zoho mail send --to ... --subject ... --text ...` — Send messages
- `zoho mail attachments <id>` / `download-attachment` — Handle attachments
- `zoho mail mark-read/unread`, `archive`, `delete`, `move` — Message operations
- Folder management: `folders list/create/rename/delete`

### ✅ Zoho Cliq (v0.4.0 in progress)

**Read plane:**
- `cliq status --check-auth` — Auth and scope verification
- `cliq capabilities` — Capability matrix for token/org/network
- `cliq channels`, `users`, `members` — List resources
- `cliq whoami` — Best-effort current-token identity diagnostic (direct endpoint first, directory fallback)
- `cliq messages <channel-id>` / `message <id>` — Read messages
- `cliq context` — Message thread context
- `cliq file <message-id>` — Fetch message attachment/file metadata
- `cliq voice <message-id>` — Filter voice/audio attachment metadata for one message

**Write plane:**
- `cliq send --text ...` — Send plain text
- `cliq send --image-url/--file-url/--audio-url/--voice-url ...` — Send rich link-style media payloads
- `cliq voice-send --voice-url ...` — Explicit voice-message send wrapper
- `cliq send --sticker :thumbsup:` — Append sticker/emoji shortcode in outbound text
- `cliq reply/edit/delete/react` — Message operations

**Admin plane (active development):**
- `cliq channel-create`, `channel-archive/unarchive`, `channel-delete --force`
- `cliq member-add/remove`
- `cliq channel-rename`, `channel-topic`

### ⏳ Zoho CRM (planned)

- Module/field listing
- Record CRUD operations
- Search and advanced queries

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

### State-driven workflow

Project state lives in `ops/state/*.yml`:
- `module_status.yml` — Module priorities and blockers
- `active_task.yml` — Current task with success criteria
- `work_queue.yml` — Backlog of tasks
- `test_status.yml`, `release_status.yml` — Verification tracking

---

## Release train

| Version | Milestone | Status |
| --- | --- | --- |
| v0.2.0 | Mail stabilized + shared core extracted | ✅ Stable |
| v0.3.0 | Cliq baseline (read/write) | ⏳ In progress |
| v0.4.0 | Cliq admin plane + Mail×Cliq integration | 🚧 Active |
| v0.5.0 | CRM read-only scaffolding | 📋 Planned |
| v0.6.0 | CRM write baseline | 📋 Planned |

---

## OpenClaw automation

This repo includes helpers for long-running development automation:

```bash
bash integrations/openclaw/bin/bootstrap_openclaw_workspace.sh --repo "$(pwd)"
```

Key files:
- `integrations/openclaw/START_HERE.md` — Quickstart guide
- `ops/prompts/` — Agent prompts for consistent workflows
- `ops/cron/README.md` — Scheduled verification setup

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
