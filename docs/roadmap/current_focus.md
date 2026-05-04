# Current Focus

## Immediate
1. **RC target is active**: `0.2.1rc1` is the fast release-candidate line for the Mail + Cliq AI-employee core.
2. **Architecture lock is complete**: `platform-204` contract is landed and drives gate execution.
3. **Release-gate lane is unblocked**: deferred external Zoho endpoint blockers are accepted as non-blocking for RC.
4. **Workflow packaging status**: `mail-010`, `cliq-195`, `platform-207`, and `platform-208` are complete for this milestone.
5. **External blockers remain deferred**: `cliq-165` (`inactive_appaccount_user`) and `cliq-193` (`not_supported`) stay capability-gated under 3-strike policy.

## Next
1. Tag/publish the green `v0.2.1rc1` RC from `autobot/zoho-platform`.
2. Keep the release evidence linked in state and changelog.
3. Keep cliq-194 read-ack endpoint limitation in capability-gated deferred mode.
4. Start post-RC Cliq API-surface modularization so AI agents can read smaller files.
5. Resume CRM CLI planning after the RC is cut.

## Delivery estimate (v1.0 first cut)
- **RC cut**: release gate is green; tag/publish is the remaining action.
- **External-unblocked full parity**: add ~1-3 weeks depending on Zoho-side availability.

## Blocker policy
- 3 consecutive `not_supported` or `inactive_appaccount_user` outcomes for the same check => mark post-release deferred.
- Deferred blockers cannot block unrelated v1.0 core slices.
- Every mergeable slice must pass focused tests and formatting checks.
