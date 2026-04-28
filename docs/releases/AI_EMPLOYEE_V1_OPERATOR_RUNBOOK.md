# AI Employee v1.0 Operator Runbook

This runbook is the operator-facing baseline for v1 release-candidate preparation (`platform-207`).

## Scope

- Internal operation: Cliq intake loop and Mail/Cliq execution actions
- External escalation: channel adapters only through the platform-206 interop contract

## Required contract references

- Release gate baseline: `docs/releases/AI_EMPLOYEE_V1_GATE.md`
- Cross-channel interop baseline: `docs/architecture/CROSS_CHANNEL_INTEROP_CONTRACT.md`
- Release state baseline: `ops/state/release_status.yml`

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
