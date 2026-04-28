# Cross-channel interoperability contract (platform-206)

This document defines the v1 contract between the internal Cliq work loop and external communication adapters.

## Purpose

- keep internal AI-employee execution stable and auditable
- allow outbound escalation to external channels without coupling core loop correctness to any single provider
- provide a concrete handoff baseline for `platform-207` release-candidate docs/runbook

## Non-goals (v1)

- full feature parity across all external channels
- blocking v1 release on unsupported external-provider endpoints
- replacing Cliq as primary internal intake plane

## Interop planes

1. **Internal plane (authoritative)**
   - Cliq intake, read-ack, dedupe, decision, and internal action surfaces
2. **External adapter plane (capability-gated)**
   - provider-specific delivery adapters consuming normalized escalation envelopes
3. **State/audit plane**
   - `ops/state/*` + workflow metadata as the only operational source of truth

## Canonical escalation envelope

External adapters consume this normalized envelope shape.

```yaml
escalationEnvelope:
  target: "<provider route target>"
  to: "<human-readable recipient>"
  subject: "<optional subject>"
  body: "<required message body>"
escalationEnvelopeMetadata:
  source: "top_level_alias|nested_fallback"
  sourcePath: "<field path used>"
  fieldSources:
    target: "<path>"
    to: "<path>"
    subject: "<path>"
    body: "<path>"
```

Rules:
- adapters must read `escalationEnvelope` first, then metadata for provenance
- missing `body` is a hard validation failure
- unsupported provider features are `skip_deferred`, not implicit success

## Routing and execution contract

1. Internal loop closes first whenever possible.
2. External escalation runs only when policy/workflow signals it.
3. Adapter failures must not corrupt read-ack/dedupe state.
4. Retry policy is adapter-local and bounded; repeated unsupported outcomes follow 3-strike defer policy.

## Capability-gating contract

Each adapter must declare runtime capability status as one of:

- `pass` (supported and verified)
- `skip_deferred` (known unsupported / missing scope / external account constraint)
- `fail` (unexpected regression requiring attention)

`skip_deferred` status requires explicit evidence links in state/docs and cannot silently downgrade into `pass`.

## Audit contract

Every external escalation attempt must be traceable via:

- source intake identity (`chat_id`, message id, or equivalent)
- normalized envelope plus envelope metadata provenance
- adapter target/provider choice and capability status
- final outcome (`pass`, `skip_deferred`, `fail`) with evidence pointer

## Platform-206 acceptance checklist

- [x] Canonical external escalation envelope is documented.
- [x] Routing contract (internal-first, external-gated) is explicit.
- [x] Capability statuses and defer semantics are explicit.
- [x] Audit trace requirements are explicit and state-driven.
- [x] Platform-207 runbook references this contract directly for operator procedures (`docs/releases/AI_EMPLOYEE_V1_OPERATOR_RUNBOOK.md`).

## References

- `docs/architecture/MULTI_PRODUCT_PLAN.md`
- `docs/releases/AI_EMPLOYEE_V1_GATE.md`
- `docs/releases/AI_EMPLOYEE_V1_OPERATOR_RUNBOOK.md`
- `ops/state/release_status.yml`
- `ops/state/project.yml`
