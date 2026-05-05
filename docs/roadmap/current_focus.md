# Current Focus

## Immediate
1. **Stable release is published**: `v0.2.1` is the stable Mail + Cliq AI-employee core release promoted from `v0.2.1rc1`.
2. **Architecture lock is complete**: `platform-204` contract is landed and drives gate execution.
3. **Release-gate lane is unblocked**: deferred external Zoho endpoint blockers are accepted as non-blocking for the stable release.
4. **Workflow packaging status**: `mail-010`, `cliq-195`, `platform-207`, and `platform-208` are complete for this milestone.
5. **Cliq modularization handoff is complete for the channel lane**: `cliq-210` moved readiness, identity, org-directory, org-admin, productivity, platform-extension list, channel-management/chat-control, threading, scheduled-message, bot, and message retrieval/context commands into smaller `zoho_cli/commands/cliq_*` modules with JSON/help parity preserved.
6. **External blockers remain deferred**: `cliq-165` (`inactive_appaccount_user`) and `cliq-193` (`not_supported`) stay capability-gated under 3-strike policy.
7. **OpenClaw channel RC package is ready for local/operator testing**: `cliq-channel-401` added the installable package, `cliq-channel-402` expanded config/SecretRef setup, `cliq-channel-416` added setup wizard UX, `cliq-channel-403` added secure policy gates, `cliq-channel-414` added SDK session/mention/approval seams, `cliq-channel-404` added JSON-safe `zoho` process execution, `cliq-channel-405` wired native outbound delivery, `cliq-channel-406` added fixture-backed polling normalization/dedupe over `zoho cliq chats` + `zoho cliq context`, `cliq-channel-407` added Bot webhook receive/auth/normalize intake at `/webhooks/cliq`, `cliq-channel-408` added status/read lifecycle handling, `cliq-channel-413` added turn-ledger loop prevention, `cliq-channel-409` added status/capability/routing diagnostics, `cliq-channel-410` added AI troubleshooting guidance, `cliq-channel-417` wires accepted webhook/polling events into native OpenClaw agent turns, `cliq-channel-415` adds redacted audit/diagnostic bundles plus privacy/retention/rate-limit/release-integrity diagnostics, `cliq-channel-411` adds the redacted fake/live smoke gate with local webhook checks and `skip_deferred` handling for Zoho refresh throttling, `cliq-channel-412` adds the host compatibility matrix plus future SDK repair workflow, and `cliq-channel-418` adds the v0.4 RC checklist.

## Next
1. Begin CRM v0.5 planning while public native Cliq Bot callback verification waits on a reachable tunnel/gateway URL.
2. Keep cliq-194 read-ack endpoint limitation in capability-gated deferred mode.
3. Continue remaining Cliq helper-heavy modularization opportunistically when it directly lowers channel implementation risk.
4. Resume CRM CLI planning in v0.5 after the native channel lane is stable.

## Delivery estimate (v1.0 first cut)
- **Stable cut**: published as `v0.2.1`.
- **External-unblocked full parity**: add ~1-3 weeks depending on Zoho-side availability.
- **Native OpenClaw Cliq channel v0.4**: config/setup/security/SDK/CLI adapter/outbound smoke, local inbound polling dry-runs, Bot webhook receive/auth/normalize intake, status/read lifecycle smoke, turn-ledger loop-prevention smoke, status/routing diagnostics smoke, AI troubleshooting dry-runs, fake host native dispatch coverage, redacted observability/privacy diagnostics, the fake/live smoke harness, host compatibility repair workflow, and RC checklist are ready; public Bot callback testing remains deployment-dependent on a reachable tunnel/gateway URL.

## Blocker policy
- 3 consecutive `not_supported` or `inactive_appaccount_user` outcomes for the same check => mark post-release deferred.
- Deferred blockers cannot block unrelated v1.0 core slices.
- Every mergeable slice must pass focused tests and formatting checks.
