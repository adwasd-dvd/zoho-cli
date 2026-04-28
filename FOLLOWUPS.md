# FOLLOWUPS

## v1.0 fast-release lane (AI employee)

- [ ] Close `platform-202` next extraction slice (no behavior change, parity tests green).
- [x] Land `platform-204` architecture brief (Mail+Cliq core, persona/memory/work contract, post-v1 CRM/Books boundary).
- [x] Land `platform-205` v1.0 acceptance gate for AI-employee workflow.
- [x] Deliver `mail-010` operator workflow package (triage/draft/reply/safe-send guardrails).
  - [x] Draft contract slice landed (`docs/releases/MAIL_010_OPERATOR_WORKFLOW.md`).
  - [x] End-to-end operator example transcript + verification evidence landed.
- [ ] Deliver `cliq-194` realtime intake baseline (web-trigger default + adaptive API polling fallback) with mandatory mark-as-read/read-ack after consume to prevent looped re-processing.
- [x] Deliver `cliq-195` operator workflow package (internal loop + external-contact escalation path), then defer non-critical tail hardening to post-v1 backlog.
- [x] Land `platform-206` cross-channel interoperability contract (Cliq internal + external comm adapters).
- [x] Wire `platform-206` contract into `platform-207` operator runbook references.
- [x] Land `platform-207` release-candidate docs + quickstart + runbook.
  - [x] Docs package consolidated (`AI_EMPLOYEE_V1_OPERATOR_RUNBOOK.md`, `AI_EMPLOYEE_V1_QUICKSTART.md`, `AI_EMPLOYEE_V1_RC_CHECKLIST.md`).
  - [x] Execute and record RC/version decision checkpoint in `ops/state/release_status.yml` (decision: defer).
- [ ] Queue `platform-208` full CLI information-architecture cleanup (module-first hierarchy hardening, remove legacy root mail aliases after deprecation window, and normalize level-2/level-3 help taxonomy for human + AI operators).

## Blocker handling (do not stall release)

- [ ] Keep `cliq-165` under capability-gated deferred status until app-account activation is available.
- [ ] Keep `cliq-193` under capability-gated deferred status after repeated `not_supported` evidence.
- [ ] Apply 3-strike unsupported policy consistently for all focused live checks.

## Hygiene

- [ ] Confirm coder startup path always lands on canonical workspace.
- [ ] Keep markdown status updates section-based (avoid brittle exact-text edits).
- [ ] Keep coding slices small enough to finish inside run timeout.

## Throughput policy (turbo)

- [ ] Run all in-progress tasks in parallel lanes where dependency-safe (`cliq-194`, `platform-203`, then `platform-208`).
- [ ] Apply adaptive backoff: only reduce scope after 3 consecutive failed attempts, and cut current batch size by 30% each time.
- [ ] Keep medium-scope regression gate every 2 lane boundaries (not after every tiny change).
