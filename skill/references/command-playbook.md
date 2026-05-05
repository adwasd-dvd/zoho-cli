# Command playbook

## Mail

```bash
# Inbox triage
zoho mail list --folder Inbox --limit 20

# Search and inspect one message
zoho mail search "invoice" --limit 5
zoho mail get <message_id>

# Reply and mark read
zoho mail reply <message_id> --text "Received. I will follow up shortly."
zoho mail mark-read <message_id>
```

## Cliq (network-scoped)

```bash
# Basic health and capability check
zoho cliq status --check-auth --network happydistrouklimited
zoho cliq capabilities --network happydistrouklimited

# Unread intake loop (exclude messages already reacted by this account)
zoho cliq chats --network happydistrouklimited --unread-only --exclude-reacted-by-self

# Context + reply
zoho cliq context --network happydistrouklimited --chat-id <chat_id> --limit 20
zoho cliq reply --network happydistrouklimited --chat-id <chat_id> --message-id <msg_id> --text "On it."

# Acknowledge after handling
zoho cliq mark-read --network happydistrouklimited --chat-id <chat_id> --latest
```

## Cliq reaction status lifecycle

```bash
# received
zoho cliq status-react <msg_id> --status received --chat-id <chat_id> --network happydistrouklimited --clear-known

# thinking
zoho cliq status-react <msg_id> --status thinking --chat-id <chat_id> --network happydistrouklimited --clear-known

# writing
zoho cliq status-react <msg_id> --status writing --chat-id <chat_id> --network happydistrouklimited --clear-known

# testing
zoho cliq status-react <msg_id> --status testing --chat-id <chat_id> --network happydistrouklimited --clear-known

# blocked / done / failed
zoho cliq status-react <msg_id> --status blocked --chat-id <chat_id> --network happydistrouklimited --clear-known
zoho cliq status-react <msg_id> --status done    --chat-id <chat_id> --network happydistrouklimited --clear-known
zoho cliq status-react <msg_id> --status failed  --chat-id <chat_id> --network happydistrouklimited --clear-known
```

## CRM (read-first)

```bash
zoho crm status --check-auth
zoho crm sdk-status
zoho crm modules
zoho crm fields --module Leads
zoho crm list --module Leads --limit 5
```

For SDK migration work, inspect `zoho crm sdk-status` and
`docs/architecture/CRM_V0_5_SDK_ADOPTION_PLAN.md` first. `crm-004` keeps the
`zoho_cli/crm_sdk.py` data-center adapter skeleton default-disabled; SDK
resources must stay under `ZOHO_CRM_SDK_RESOURCE_PATH` or the CLI-managed cache.
Use explicit `--adapter sdk-v8` only for SDK parity checks:

```bash
zoho crm modules --adapter sdk-v8
zoho crm list --module Leads --adapter sdk-v8 --limit 5
```

`zoho crm status` and `zoho crm sdk-status` expose `apiVersionPolicy`; keep
HTTP v2 as default and SDK/API v8 explicit-only unless a later compatibility
slice records live shape parity.

Before any CRM write work, inspect the write contract:

```bash
zoho crm write-plan
zoho crm write-plan --operation upsert
```

`crm-007` exposes `writeSurfacePolicy` with `writesEnabled=false`, dry-run
default, exact confirmation, idempotency-key, JSON-payload, and audit-envelope
requirements. Do not invent live write commands while `writesEnabled=false`;
the next candidate is `zoho crm upsert` dry-run, and delete remains blocked.

`crm-008` implements that first dry-run command:

```bash
zoho crm upsert \
  --module Leads \
  --data-json '{"Last_Name":"Example","Email":"example@example.com"}' \
  --duplicate-check-field Email \
  --idempotency-key crm-leads-upsert-$(date +%F)
```

Use the returned `payloadDigest`, `fieldNames`, `recordCount`, and
`requiredConfirmation` for review. The command does not echo raw field values.
`--execute` is intentionally blocked with `live_write_not_enabled`.

Before any future live upsert decision, inspect the gate:

```bash
zoho crm upsert-gate --module Leads
zoho crm upsert-gate --module Leads --check-auth
```

`crm-009` keeps `liveWritesEnabled=false` and `decision=defer_live_execution`.
Use `scopeGate.matchingScopes` only as readiness evidence; blockers such as
`audit_persistence_not_implemented` and `controlled_live_fixture_not_recorded`
mean live writes remain disabled.

`crm-010` persists redacted JSONL audit events for dry-run and gate commands.
Use `--audit-file` or `ZOHO_CRM_WRITE_AUDIT` to isolate an agent run:

```bash
zoho crm upsert \
  --module Leads \
  --data-json '{"Last_Name":"Example","Email":"example@example.com"}' \
  --duplicate-check-field Email \
  --idempotency-key crm-leads-upsert-$(date +%F) \
  --audit-file /tmp/zoho-crm-audit.jsonl

zoho crm write-audit \
  --audit-file /tmp/zoho-crm-audit.jsonl \
  --operation upsert \
  --module Leads \
  --limit 10
```

Audit events should show `rawFieldValuesStored=false`; do not paste raw field
values, tokens, or secrets into audit reports.

## Bridge fallback (explicit)

```bash
zoho cliq bridge-run --bridge membrane --action-id <action_id> --input-json '{"limit":5}'
zoho crm bridge-run --bridge membrane --action-id <action_id> --input-json '{"module":"Leads","limit":5}'
```
