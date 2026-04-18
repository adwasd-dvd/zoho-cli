# Current Focus

## Immediate
1. **v1.0 target is fixed**: AI-employee-first release using Mail + Cliq as the core workspace.
2. **Framework-first remains active**: continue `platform-202` command-layer extraction (no behavior change, parity-guarded).
3. **Architecture lane is now active**: `platform-204` defines v1.0 boundaries (must-ship vs deferred) for fast release packaging.
4. **Realtime lane is queued and gated**: `cliq-194` uses web-trigger default with adaptive API polling fallback.
5. **External blockers remain deferred**: `cliq-165` (`inactive_appaccount_user`) and `cliq-193` (`not_supported`) stay capability-gated under 3-strike policy.

## Next
1. Finish next `platform-202` extraction pair with focused parity tests.
2. Finalize `platform-204` architecture brief for AI-employee flow (persona/memory/work contract + channel boundaries).
3. Start `platform-205` acceptance gate definition for v1.0 AI-employee workflow.
4. Start `mail-010` and `cliq-195` packaging slices for operator-facing workflows.
5. Prepare `platform-207` release-candidate docs/runbook once above lanes are green.

## Delivery estimate (v1.0 first cut)
- **Engineering complete for v1.0 core**: ~5-8 workdays (blockers isolated).
- **External-unblocked full parity**: add ~1-3 weeks depending on Zoho-side availability.

## Blocker policy
- 3 consecutive `not_supported` or `inactive_appaccount_user` outcomes for the same check => mark post-release deferred.
- Deferred blockers cannot block unrelated v1.0 core slices.
- Every mergeable slice must pass focused tests and formatting checks.
