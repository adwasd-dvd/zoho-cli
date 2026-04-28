# AI Employee v1.0 Quickstart (RC package)

This quickstart is the minimal operator path for the v1 AI-employee release-candidate package.

## 1) Preconditions

- Repo state is current (`ops/state/*` reflects active lane).
- OAuth is configured for the target account.
- Use module-first commands (`zoho mail ...`, `zoho cliq ...`, `zoho crm ...`).

## 2) Sanity checks

```bash
zoho --help
zoho mail --help
zoho cliq --help
```

## 3) Core internal loop (Mail + Cliq)

1. Run Mail triage/search/read flow from `docs/releases/MAIL_010_OPERATOR_WORKFLOW.md`.
2. Apply send guardrails before any outbound message.
3. Keep internal-first handling as default.

## 4) External escalation (only when required)

- Follow `docs/architecture/CROSS_CHANNEL_INTEROP_CONTRACT.md` exactly.
- Use canonical `escalationEnvelope` + provenance metadata.
- Record outcome as `pass`, `skip_deferred`, or `fail` with evidence pointers.

## 5) Release-gate references

- Acceptance baseline: `docs/releases/AI_EMPLOYEE_V1_GATE.md`
- Operator runbook: `docs/releases/AI_EMPLOYEE_V1_OPERATOR_RUNBOOK.md`
- Release status: `ops/state/release_status.yml`

## 6) RC decision checkpoint

Use `docs/releases/AI_EMPLOYEE_V1_RC_CHECKLIST.md` to decide:

- whether to flip `release_candidate=true`
- whether to proceed with version bump execution
