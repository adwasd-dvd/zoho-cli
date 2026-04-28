# Multi-product platform plan

## Product order

This repository expands in this order:

1. Zoho Mail
2. Zoho Cliq
3. Zoho CRM
4. Zoho Books (post-v1)

## v1.0 north-star (AI employee)

`zoho-cli` v1.0 is optimized for one concrete use case:

- an AI agent acts as a virtual employee
- uses **Mail + Cliq** as primary work surfaces
- runs with configured persona, memory, and work instructions
- can close internal workflows first, then escalate to external communication channels through adapter-style integrations

## Scope split for fast v1.0

### Must ship in v1.0

1. **Agent contract**
   - persona/memory/work-profile configuration contract
   - safe defaults and explicit operator override points
2. **Mail operational baseline**
   - triage/read/search
   - draft/reply assist
   - send guardrails (safety + auditability)
3. **Cliq operational baseline**
   - inbound loop for near-realtime work intake (`cliq-194`: web-trigger default + API adaptive fallback)
   - every consumed inbound item must be read-acknowledged/marked as read, plus cursor-based dedupe, to prevent dead-loop mis-operations
   - core reply/notify/workflow actions for internal coordination
4. **Release readiness**
   - focused acceptance checks for the AI-employee workflow
   - explicit capability-gating for unsupported live endpoints

### Deferred from v1.0 (post-release)

- Cliq endpoints with stable `not_supported` / `inactive_appaccount_user` outcomes
- CRM deep operational flows (beyond current verified read baseline)
- Zoho Books command surface
- fully native multi-channel provider expansion (outside current Cliq-first channel path)

## Architecture fusion (what gets unified)

Unify product work around one operator-facing flow:

1. **Task intake layer**: Cliq inbound events/notifications + fallback polling
2. **Work execution layer**: Mail/Cliq product actions via stable command contracts
3. **Policy layer**: persona + memory + safety constraints
4. **Audit/recovery layer**: state files, capability gates, deferred-blocker logs

## Guardrails

- Do not start new CRM feature work until Cliq baseline is stable.
- Patch releases must not mix in new modules.
- All cron/agents read and write the same state files in `ops/state/`.
- Unsupported external endpoints follow 3-strike deferred policy and must not stall unrelated v1.0 slices.

## Platform-204 architecture contract (v1 cut)

This section is the lock point for `platform-204` and the handoff baseline for `platform-205`.

### Core operating contract

1. **Control contract**
   - persona, memory, and work instructions are first-class runtime inputs
   - one canonical state plane in `ops/state/*` drives automation decisions and recovery
2. **Execution contract**
   - intake starts in Cliq (`cliq-194`/`cliq-195` path), then routes to Mail/Cliq actions
   - consumed intake must always read-ack/mark-read with dedupe protection before next loop step
3. **Escalation contract**
   - internal loop closes first when possible
   - external communication is adapter-driven and capability-gated, never a blocker for internal-loop correctness

### Explicit v1 boundaries

- **In v1**: Mail + Cliq operational core, persona/memory/work contract, focused acceptance gates.
- **Post-v1**: CRM deep workflows, Books surface, unsupported Cliq endpoints, and non-critical cliq-195 tail hardening.

### Platform-205 handoff requirements

`platform-205` acceptance must validate:

1. end-to-end AI-employee happy path (Cliq intake -> decision -> Mail/Cliq action -> audit trail)
2. mandatory read-ack/dedupe behavior for consumed intake
3. capability-gated behavior when unsupported endpoints are encountered
4. reproducible operator run contract from docs + state files only
