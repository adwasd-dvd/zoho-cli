# Current Focus

## Immediate
1. **v1.0 target is fixed**: AI-employee-first release using Mail + Cliq as the core workspace.
2. **Architecture lock is complete**: `platform-204` contract is landed and now drives gate execution.
3. **Release-gate lane is closed**: `platform-205` signoff is complete, with explicit release-candidate defer decision recorded.
4. **Workflow packaging status**: `cliq-195` is closed for this milestone; non-critical tail is deferred post-v1.
5. **External blockers remain deferred**: `cliq-165` (`inactive_appaccount_user`) and `cliq-193` (`not_supported`) stay capability-gated under 3-strike policy.

## Next
1. Execute `platform-208` CLI information-architecture cleanup (module-first help taxonomy normalization).
2. Keep cliq-194 read-ack endpoint limitation in capability-gated deferred mode (non-blocking for forward platform work).
3. Revisit RC/version checkpoint after platform-208 first cleanup slice lands green.
4. Keep platform-207 runbook/quickstart tied directly to platform-206 interop + platform-205 gate contracts.
5. Keep deferred blocker evidence current without letting it stall core v1 flow.

## Delivery estimate (v1.0 first cut)
- **Engineering complete for v1.0 core**: ~5-8 workdays (blockers isolated).
- **External-unblocked full parity**: add ~1-3 weeks depending on Zoho-side availability.

## Blocker policy
- 3 consecutive `not_supported` or `inactive_appaccount_user` outcomes for the same check => mark post-release deferred.
- Deferred blockers cannot block unrelated v1.0 core slices.
- Every mergeable slice must pass focused tests and formatting checks.
