# MAIL-010 Operator Workflow Package (v1 slice)

This document defines the first executable operator workflow contract for Mail in the AI-employee v1 lane.

## Scope

- in scope: triage, search/read, reply/send, and send-safety checks
- out of scope (this slice): advanced automation orchestration and provider-specific optimizations

## Workflow contract

### 1) Intake triage

Purpose: quickly identify what needs action.

Command surfaces:
- `python -m zoho_cli mail list --folder Inbox --limit 50`
- `python -m zoho_cli mail search "<query>" --limit 50`
- `python -m zoho_cli mail get <message_id>`

Expected operator output:
- candidate message ids for action
- brief action intent (`reply`, `new-send`, `archive`, `spam`, `defer`)

### 2) Draft/reply assist

Purpose: prepare outbound content with context.

Command surfaces:
- `python -m zoho_cli mail reply <message_id> --text "<reply body>" [--quote]`
- `python -m zoho_cli mail send --to <recipient> --subject "<subject>" --text "<body>"`

Expected operator output:
- final body text that reflects task context
- explicit recipient/subject confirmation before send

### 3) Safe-send guardrails

Before any send/reply, operator must confirm:

1. recipient target is correct (`--to`, optional `--cc/--bcc`)
2. subject/body match requested intent
3. no sensitive data is leaked unintentionally
4. attachments (if any) are intended and readable

Related command surfaces:
- `python -m zoho_cli mail attachments <message_id>`
- `python -m zoho_cli mail download-attachment <message_id> <attachment_id> --output <path>`

### 4) Post-action state hygiene

Purpose: keep mailbox state auditable after action.

Command surfaces:
- `python -m zoho_cli mail mark-read <id...>`
- `python -m zoho_cli mail archive <id...>`
- `python -m zoho_cli mail tag <id...> <label>`

## Minimal runnable examples (v1)

1. triage pass:
   - list inbox
   - open one message with `mail get`
2. reply pass:
   - reply to one message with explicit text
3. safety pass:
   - execute recipient/content check before send

## Acceptance checklist (mail-010)

- [x] Workflow contract sections are documented.
- [x] Current CLI command surfaces are mapped to each workflow phase.
- [ ] Add one end-to-end operator example transcript suitable for platform-207 quickstart.
- [ ] Add focused verification notes/evidence for this workflow package in state/changelog.

## References

- `docs/releases/AI_EMPLOYEE_V1_GATE.md`
- `docs/releases/AI_EMPLOYEE_V1_OPERATOR_RUNBOOK.md`
- `ops/state/active_task.yml`
