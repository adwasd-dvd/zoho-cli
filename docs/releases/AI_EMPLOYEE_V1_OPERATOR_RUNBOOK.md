# AI Employee v1.0 Operator Runbook

This runbook is the operator-facing baseline for v1 release-candidate preparation (`platform-207`).

## Scope

- Internal operation: Cliq intake loop and Mail/Cliq execution actions
- External escalation: channel adapters only through the platform-206 interop contract

## Required contract references

- Release gate baseline: `docs/releases/AI_EMPLOYEE_V1_GATE.md`
- Cross-channel interop baseline: `docs/architecture/CROSS_CHANNEL_INTEROP_CONTRACT.md`
- Release state baseline: `ops/state/release_status.yml`

## Operator procedure: mail workflow contract (mail-010 thin slice)

Contract objective: package one auditable operator path for Mail triage/search/read -> draft/reply assist -> safe-send.

### Command surface mapping

- Triage/search/read:
  - `zoho mail list`
  - `zoho mail search <query>`
  - `zoho mail get <message-id> --folder-id <folder-id>`
- Draft/reply assist:
  - `zoho mail reply <message-id> --text "..." [--quote] [--folder-id <folder-id>]`
  - `zoho mail forward <message-id> --to <recipient> [--text "note"] [--folder-id <folder-id>]`
- Safe-send execution:
  - `zoho mail send --to <recipient> --subject "..." --text "..." [--cc ...] [--bcc ...] [--attach ...]`

### Safe-send guardrails

1. Confirm recipient list (`--to/--cc/--bcc`) is intentional and complete.
2. Confirm subject/body intent matches the current task and does not include stale context.
3. For reply/forward, verify the source message id and folder context before send.
4. Attachments are explicit only (`--attach` repeatable); do not infer hidden files.
5. Record command + outcome in state/memory updates for auditability.

### Minimal runnable examples

```bash
# 1) triage candidates
zoho mail list --folder inbox --limit 10

# 2) inspect one message
zoho mail get 17a4... --folder-id 3266...

# 3) send a controlled reply
zoho mail reply 17a4... --folder-id 3266... --text "Thanks, received. We will follow up by 17:00 UTC." --quote
```

## Operator procedure: cross-channel escalation

1. Confirm escalation is needed and internal-first handling is insufficient.
2. Use the canonical `escalationEnvelope` and `escalationEnvelopeMetadata` contract exactly as defined in `docs/architecture/CROSS_CHANNEL_INTEROP_CONTRACT.md`.
3. Validate required envelope fields before adapter execution (`body` is mandatory).
4. Execute provider adapter in capability-gated mode.
5. Record adapter outcome as one of:
   - `pass`
   - `skip_deferred`
   - `fail`
6. Persist evidence and provenance pointers in state/docs so outcome is auditable.

## Outcome semantics

- `skip_deferred` is valid when capability is unsupported, scope-gated, or externally blocked.
- `skip_deferred` must include explicit evidence and must never be treated as `pass`.
- Adapter failures must not break read-ack/dedupe integrity in the internal loop.

## Platform-207 handoff marker

- This runbook now consumes the platform-206 interoperability contract directly.
- Mail workflow contract thin slice is now documented for platform-207 consumption.
