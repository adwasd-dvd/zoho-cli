# AI Employee v1.0 RC Checklist (platform-207)

Use this checklist to complete the platform-207 package and run the RC/version decision checkpoint.

## Package completeness

- [x] Release gate contract is finalized: `docs/releases/AI_EMPLOYEE_V1_GATE.md`
- [x] Interop contract is finalized: `docs/architecture/CROSS_CHANNEL_INTEROP_CONTRACT.md`
- [x] Mail workflow package is finalized: `docs/releases/MAIL_010_OPERATOR_WORKFLOW.md`
- [x] Operator runbook is aligned: `docs/releases/AI_EMPLOYEE_V1_OPERATOR_RUNBOOK.md`
- [x] Quickstart is present: `docs/releases/AI_EMPLOYEE_V1_QUICKSTART.md`

## State alignment

- [x] `ops/state/release_status.yml` reflects current milestone `platform-208-cli-information-architecture`
- [x] `ops/state/active_task.yml` is set to `platform-208`
- [x] RC checkpoint refresh evidence is linked (`docs/releases/AI_EMPLOYEE_V1_RC_CHECKPOINT_2026-05-04.md`)
- [x] Changelog includes platform-208 progress (`docs/releases/CHANGELOG.next.md`)

## RC/version decision checkpoint

- [x] Decide `release_candidate` flip (`true` or keep `false`) with explicit reason (current decision: `true`, approve `0.2.1rc1` with deferred external blockers).
- [x] If flip approved, execute version bump workflow and mark `release_gate.version_bumped=true`.
- [x] If flip deferred, record concrete unblock condition and next checkpoint owner/time. Not applicable for the current approved RC posture.
- [x] Run post-flip `make release-gate && make ci` before tag/publish.
- [ ] Tag/publish `v0.2.1rc1`.

## Decision rule

- Do not flip RC based on docs alone.
- RC flip needs one clear decision record in `ops/state/release_status.yml` tied to current blockers and latest gate evidence.
