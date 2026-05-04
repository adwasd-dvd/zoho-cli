# Current Focus

## Immediate
1. **Stable release is published**: `v0.2.1` is the stable Mail + Cliq AI-employee core release promoted from `v0.2.1rc1`.
2. **Architecture lock is complete**: `platform-204` contract is landed and drives gate execution.
3. **Release-gate lane is unblocked**: deferred external Zoho endpoint blockers are accepted as non-blocking for the stable release.
4. **Workflow packaging status**: `mail-010`, `cliq-195`, `platform-207`, and `platform-208` are complete for this milestone.
5. **Cliq modularization has started**: `cliq-210` has moved readiness, identity, org-directory, org-admin, productivity, platform-extension list, channel-management/chat-control, threading, scheduled-message, bot, and message retrieval/context commands into smaller `zoho_cli/commands/cliq_*` modules with JSON/help parity preserved.
6. **External blockers remain deferred**: `cliq-165` (`inactive_appaccount_user`) and `cliq-193` (`not_supported`) stay capability-gated under 3-strike policy.
7. **Version order updated**: v0.4 is reserved for the native OpenClaw Cliq channel; CRM expansion moves to v0.5.

## Next
1. Keep the `v0.2.1` release evidence linked in state and changelog.
2. Keep cliq-194 read-ack endpoint limitation in capability-gated deferred mode.
3. Continue post-RC Cliq API-surface modularization so AI agents can read smaller files.
4. Start `cliq-channel-400` after the current Mail+Cliq release line and `cliq-210` modularization handoff are stable.
5. Resume CRM CLI planning in v0.5 after the native channel lane is stable.

## Delivery estimate (v1.0 first cut)
- **Stable cut**: published as `v0.2.1`.
- **External-unblocked full parity**: add ~1-3 weeks depending on Zoho-side availability.
- **Native OpenClaw Cliq channel v0.4**: staged after the current Mail+Cliq release line; MVP target is about one focused week, full native channel hardening is about two focused weeks.

## Blocker policy
- 3 consecutive `not_supported` or `inactive_appaccount_user` outcomes for the same check => mark post-release deferred.
- Deferred blockers cannot block unrelated v1.0 core slices.
- Every mergeable slice must pass focused tests and formatting checks.
