# Current Focus

## Immediate
1. **Stable release is published**: `v0.2.1` is the stable Mail + Cliq AI-employee core release promoted from `v0.2.1rc1`.
2. **Architecture lock is complete**: `platform-204` contract is landed and drives gate execution.
3. **Release-gate lane is unblocked**: deferred external Zoho endpoint blockers are accepted as non-blocking for the stable release.
4. **Workflow packaging status**: `mail-010`, `cliq-195`, `platform-207`, and `platform-208` are complete for this milestone.
5. **Cliq modularization handoff is complete for the channel lane**: `cliq-210` moved readiness, identity, org-directory, org-admin, productivity, platform-extension list, channel-management/chat-control, threading, scheduled-message, bot, and message retrieval/context commands into smaller `zoho_cli/commands/cliq_*` modules with JSON/help parity preserved.
6. **External blockers remain deferred**: `cliq-165` (`inactive_appaccount_user`) and `cliq-193` (`not_supported`) stay capability-gated under 3-strike policy.
7. **OpenClaw channel inbound webhook intake is normalized and deduped**: `cliq-channel-401` added the installable package, `cliq-channel-402` expanded config/SecretRef setup, `cliq-channel-416` added setup wizard UX, `cliq-channel-403` added secure policy gates, `cliq-channel-414` added SDK session/mention/approval seams, `cliq-channel-404` added JSON-safe `zoho` process execution, `cliq-channel-405` wired native outbound delivery, `cliq-channel-406` added fixture-backed polling normalization/dedupe over `zoho cliq chats` + `zoho cliq context`, and `cliq-channel-407` added Bot webhook receive/auth/normalize intake at `/webhooks/cliq`.

## Next
1. Start `cliq-channel-408`: implement status/read lifecycle for accepted native Cliq turns.
2. Keep cliq-194 read-ack endpoint limitation in capability-gated deferred mode.
3. Continue remaining Cliq helper-heavy modularization opportunistically when it directly lowers channel implementation risk.
4. Resume CRM CLI planning in v0.5 after the native channel lane is stable.

## Delivery estimate (v1.0 first cut)
- **Stable cut**: published as `v0.2.1`.
- **External-unblocked full parity**: add ~1-3 weeks depending on Zoho-side availability.
- **Native OpenClaw Cliq channel v0.4**: config/setup/security/SDK/CLI adapter/outbound smoke, local inbound polling dry-runs, and real Bot webhook receive/auth/normalize smoke are ready; status/read lifecycle, turn ledger loop prevention, and observability remain before production bidirectional testing.

## Blocker policy
- 3 consecutive `not_supported` or `inactive_appaccount_user` outcomes for the same check => mark post-release deferred.
- Deferred blockers cannot block unrelated v1.0 core slices.
- Every mergeable slice must pass focused tests and formatting checks.
