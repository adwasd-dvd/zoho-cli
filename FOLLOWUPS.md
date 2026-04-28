# FOLLOWUPS

## v1.0 fast-release lane (AI employee)

- [ ] Close `platform-202` next extraction slice (no behavior change, parity tests green).
- [ ] Land `platform-204` architecture brief (Mail+Cliq core, persona/memory/work contract, post-v1 CRM/Books boundary).
- [ ] Land `platform-205` v1.0 acceptance gate for AI-employee workflow.
- [ ] Deliver `mail-010` operator workflow package (triage/draft/reply/safe-send guardrails).
- [ ] Deliver `cliq-194` realtime intake baseline (web-trigger default + adaptive API polling fallback) with mandatory mark-as-read/read-ack after consume to prevent looped re-processing.
- [ ] Deliver `cliq-195` operator workflow package (internal loop + external-contact escalation path).
- [ ] Land `platform-206` cross-channel interoperability contract (Cliq internal + external comm adapters).
- [ ] Land `platform-207` release-candidate docs + quickstart + runbook.
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

- [ ] Run `cliq-195` in 20x batch mode (larger coherent slices, fewer micro-commits).
- [ ] Run all in-progress tasks in parallel lanes where dependency-safe (`cliq-195`, `platform-204`, `platform-203`).
- [ ] Apply adaptive backoff: only reduce scope after 3 consecutive failed attempts, and cut current batch size by 30% each time.
- [ ] Keep medium-scope regression gate every 2 lane boundaries (not after every tiny change).
