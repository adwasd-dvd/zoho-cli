# AI Employee v1.0 Release Gate (platform-205)

This file is the executable acceptance contract for the v1 AI-employee release cut.

## Scope

- In scope: Mail + Cliq core workflow for AI-employee operation.
- Out of scope for v1 gate pass: post-v1 deferred endpoints (for example repeated `not_supported` / `inactive_appaccount_user` surfaces) when capability-gated evidence is present.

## Pass checklist

### 1) Control contract

- [x] Persona/memory/work-instruction contract is documented and current.
- [x] Runtime behavior is traceable via `ops/state/*` without hidden side channels.

Primary references:
- `docs/architecture/MULTI_PRODUCT_PLAN.md` (platform-204 lock section)
- `ops/state/active_task.yml`
- `ops/state/project.yml`

### 2) Execution contract

- [x] Cliq intake -> decision -> action path is validated for the current CLI contract.
- [x] Consumed intake requires read-ack/mark-read and cursor-based dedupe behavior.

Primary references:
- `ops/state/test_status.yml` (focused+medium gate evidence)
- `ops/state/cliq.yml`

### 3) Escalation and blocker contract

- [x] Capability-gated deferred endpoints are explicitly listed and do not block unrelated v1 checks.
- [x] 3-strike defer policy is applied consistently to unsupported endpoints.

Primary references:
- `WAITING_ON.md`
- `ops/state/project.yml` (primary_blockers)

### 4) Build/release baseline

- [x] Unit/broad gate status is green or explicitly documented with bounded exceptions.
- [x] Changelog and release-status state are in sync with current milestone.

Primary references:
- `ops/state/release_status.yml`
- `docs/releases/CHANGELOG.next.md`

## Gate decision

- Current result: **complete (with release-candidate defer decision recorded)**
- Owner: `coder`
- Signoff task: `platform-205` (closed)

## Remaining signoff items

- [x] Finalize integration pass/skip mapping for externally blocked capabilities into `ops/state/release_status.yml`.
- [x] Decide `release_candidate` flip + version bump timing after gate signoff (decision: defer flip until one more green development slice, then revisit).
