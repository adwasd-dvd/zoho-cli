# AI Employee v1.0 Release Gate (platform-205)

This file is the executable acceptance contract for the v1 AI-employee release cut.

## Scope

- In scope: Mail + Cliq core workflow for AI-employee operation.
- Out of scope for v1 gate pass: post-v1 deferred endpoints (for example repeated `not_supported` / `inactive_appaccount_user` surfaces) when capability-gated evidence is present.

## Pass checklist

### 1) Control contract

- [ ] Persona/memory/work-instruction contract is documented and current.
- [ ] Runtime behavior is traceable via `ops/state/*` without hidden side channels.

Primary references:
- `docs/architecture/MULTI_PRODUCT_PLAN.md` (platform-204 lock section)
- `ops/state/active_task.yml`
- `ops/state/project.yml`

### 2) Execution contract

- [ ] Cliq intake -> decision -> action path is validated for the current CLI contract.
- [ ] Consumed intake requires read-ack/mark-read and cursor-based dedupe behavior.

Primary references:
- `ops/state/test_status.yml` (focused+medium gate evidence)
- `ops/state/cliq.yml`

### 3) Escalation and blocker contract

- [ ] Capability-gated deferred endpoints are explicitly listed and do not block unrelated v1 checks.
- [ ] 3-strike defer policy is applied consistently to unsupported endpoints.

Primary references:
- `WAITING_ON.md`
- `ops/state/project.yml` (primary_blockers)

### 4) Build/release baseline

- [ ] Unit/broad gate status is green or explicitly documented with bounded exceptions.
- [ ] Changelog and release-status state are in sync with current milestone.

Primary references:
- `ops/state/release_status.yml`
- `docs/releases/CHANGELOG.next.md`

## Gate decision

- Current result: **in progress**
- Owner: `coder`
- Active task: `platform-205`

