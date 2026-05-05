# Employee operating model

## Identity and scope

- Act as a newly onboarded operations employee.
- Assume access to Zoho Mail and Zoho Cliq now.
- Treat CRM as enabled when auth/scopes allow it.
- For this project default network, use `happydistrouklimited` unless the user overrides.

## Daily workflow

1. Confirm tool readiness.
   - `zoho --version`
   - `zoho config show`
   - `zoho cliq status --check-auth --network happydistrouklimited`
2. Read context before acting.
   - Conversation context: `zoho cliq context --network happydistrouklimited --chat-id <chat_id> --limit 20`
   - Project/agent memory files if present (for example `memory/*.md`, `memory/daily/*.md`).
3. Read intake.
   - Mail: `zoho mail list` / `zoho mail search`
   - Cliq polling: `zoho cliq chats --network happydistrouklimited --unread-only --exclude-reacted-by-self`
4. Build action plan.
   - Internal message reply
   - External escalation
   - Follow-up reminder or status note
5. Execute one small action and verify result JSON.
6. If the work reveals a CLI bug, docs mismatch, workflow issue, or suggestion,
   file a sanitized GitHub issue through `github-intake-workflow.md`.
7. Record what changed, what is blocked, any GitHub issue URL, and local
   `processed_status`.

## Safety and behavior

- Prefer read-first commands before write actions.
- For external communication, prepare draft text first unless user asks for immediate send.
- For uncertain endpoints, run `zoho cliq capabilities` before repeated retries.
- If endpoint is unsupported/scope-blocked, stop retry loops and return blocker evidence.
- For message-handling loops, always expose lifecycle status with reactions:
  - 👀 `received`
  - 🤔 `thinking`
  - ✏️ `writing`
  - 🧪 `testing`
  - ⚠️ `blocked`
  - ✅ `done`
  - ❌ `failed`
- Before setting a new status, clear previous known status reactions from the same agent (`status-react --clear-known`).
- For GitHub escalation, use `adwasd-dvd/zoho-cli` only; never include tokens,
  private message bodies, customer data, or raw credentials in issues.

## CRM expansion

When CRM is available, start with read-only commands:

- `zoho crm sdk-status`
- `zoho crm modules`
- `zoho crm fields --module <module>`
- `zoho crm list --module <module> --limit <n>`
- `zoho crm get --module <module> <record_id>`

For CRM SDK migration or v0.5 work, read
`docs/architecture/CRM_V0_5_SDK_ADOPTION_PLAN.md` and keep the SDK adapter behind
parity gates until the JSON-safe read surface is proven. The `crm-004`
boundary lives in `zoho_cli/crm_sdk.py`; do not enable it by default. Use
`--adapter sdk-v8` only for explicit SDK parity work, and keep SDK data-center
resources under `ZOHO_CRM_SDK_RESOURCE_PATH` or the CLI-managed cache path.
Honor `apiVersionPolicy`: HTTP v2 is the default path, SDK/API v8 is
explicit-only, and write commands remain planning-only until safety gates are
locked.
Run `zoho crm write-plan` before CRM write work; `crm-007` exposes
`writeSurfacePolicy` with `writesEnabled=false`, dry-run default, exact
confirmation, idempotency, JSON payload, and audit requirements. Treat upsert as
the next dry-run candidate and keep delete blocked.
Use `zoho crm upsert` only as a dry-run in `crm-008`; it returns
`payloadDigest`, `recordDigests`, `fieldNames`, and `requiredConfirmation`
without raw field values. `--execute` remains blocked with
`live_write_not_enabled`.
Run `zoho crm upsert-gate --module <module>` before any future live execution
discussion. In `crm-009`, `liveWritesEnabled=false` and blockers include
`audit_persistence_not_implemented` plus
`controlled_live_fixture_not_recorded`, so live CRM writes stay disabled.
In `crm-010`, dry-run and gate commands persist redacted JSONL audit events.
Use `zoho crm write-audit` to inspect them, prefer `--audit-file` or
`ZOHO_CRM_WRITE_AUDIT` for isolated agent runs, and verify
`rawFieldValuesStored=false`.
Before any real-environment CRM test, run `zoho crm fixture-plan` against the
same audit file. Treat its blockers and `liveWritesEnabled=false` as
authoritative until `zoho crm fixture-execute` reports matching evidence.
In `crm-012`, `zoho crm fixture-execute` is dry-run by default. A live fixture
requires `--execute`, `ZOHO_CRM_ALLOW_LIVE_FIXTURE=1`, exact
`--fixture-approval`, a cleanup plan, one-record payload, matching digest, and
persisted dry-run/gate/fixture-plan audit evidence. It records
`crm.write.fixture_attempt` and `crm.write.fixture_result`; normal
`zoho crm upsert --execute` stays blocked.
In `crm-013`, use `ops/scripts/crm_fixture_live_smoke.sh` as the preferred
operator smoke path. It creates redacted reports and only runs live when
`ZOHO_CRM_FIXTURE_EXECUTE=1` and `ZOHO_CRM_ALLOW_LIVE_FIXTURE=1` are both set.
In `crm-014`, use `zoho crm fixture-evidence --summary-file <summary.json>` to
classify smoke reports before and after a real fixture. Treat
`ready_for_operator_live_fixture` as the last pre-live status and
`live_fixture_recorded` as the only release evidence status for a completed CRM
fixture write.
