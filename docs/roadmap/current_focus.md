# Current Focus

## Immediate
1. **RC is published**: `v0.2.1rc1` is the fast release-candidate line for the Mail + Cliq AI-employee core.
2. **Architecture lock is complete**: `platform-204` contract is landed and drives gate execution.
3. **Release-gate lane is unblocked**: deferred external Zoho endpoint blockers are accepted as non-blocking for RC.
4. **Workflow packaging status**: `mail-010`, `cliq-195`, `platform-207`, and `platform-208` are complete for this milestone.
5. **Cliq modularization has started**: `cliq-210` has moved readiness, identity, org-directory, org-admin, and productivity list commands into smaller `zoho_cli/commands/cliq_*` modules with JSON/help parity preserved.
6. **External blockers remain deferred**: `cliq-165` (`inactive_appaccount_user`) and `cliq-193` (`not_supported`) stay capability-gated under 3-strike policy.

## Next
1. Keep the release evidence linked in state and changelog.
2. Keep cliq-194 read-ack endpoint limitation in capability-gated deferred mode.
3. Continue post-RC Cliq API-surface modularization so AI agents can read smaller files.
4. Resume CRM CLI planning after the Cliq split lane is stable.

## Delivery estimate (v1.0 first cut)
- **RC cut**: published as `v0.2.1rc1`.
- **External-unblocked full parity**: add ~1-3 weeks depending on Zoho-side availability.

## Blocker policy
- 3 consecutive `not_supported` or `inactive_appaccount_user` outcomes for the same check => mark post-release deferred.
- Deferred blockers cannot block unrelated v1.0 core slices.
- Every mergeable slice must pass focused tests and formatting checks.
