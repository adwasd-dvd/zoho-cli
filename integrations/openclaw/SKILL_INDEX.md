# Lane3 AI-skill index

## Scope

Lane3 = AI-user-facing skill/docs/scripts for this repository.

Primary paths:
- `skill/SKILL.md`
- `skill/references/*`
- `skill/scripts/*`
- `integrations/openclaw/*`

Native channel planning:
- `docs/architecture/OPENCLAW_CLIQ_CHANNEL_0_4_PLAN.md`
- `integrations/openclaw/CLIQ_CHANNEL_DEVELOPMENT_GUIDE.md`
- `integrations/openclaw-channel-cliq/`
- `docs/releases/OPENCLAW_CLIQ_CHANNEL_SETUP.md`
- `docs/releases/OPENCLAW_CLIQ_BOT_HANDLER_TEMPLATES.md`
- `ops/scripts/openclaw_cliq_rc_pack.sh`
- `ops/scripts/openclaw_cliq_trusted_reply_evidence_prepare.sh`
- `ops/scripts/openclaw_cliq_trusted_reply_evidence.sh`
- `skill/references/openclaw-cliq-channel.md`

CRM SDK planning:
- `docs/architecture/CRM_V0_5_SDK_ADOPTION_PLAN.md`
- `zoho crm sdk-status`
- `zoho_cli/crm_sdk.py` (`crm-004` data-center/cache-path adapter skeleton,
  default-disabled; `ZOHO_CRM_SDK_RESOURCE_PATH` override)
- `crm modules|fields|list|get|search --adapter sdk-v8` (`crm-005` explicit
  SDK read gates; default remains `http-v2`)
- `apiVersionPolicy` from `zoho crm status` / `zoho crm sdk-status` (`crm-006`:
  HTTP v2 default, SDK/API v8 explicit-only)
- `zoho crm write-plan` / `writeSurfacePolicy` (`crm-007`: `writesEnabled=false`,
  dry-run default, exact confirmation, idempotency, JSON payload, audit envelope;
  upsert next, delete blocked)
- `zoho crm upsert` (`crm-008`: dry-run-only, `--data-json` / `--data-file`,
  `--duplicate-check-field`, `--idempotency-key`, `payloadDigest`,
  `recordDigests`, `requiredConfirmation`; `--execute` returns
  `live_write_not_enabled`)
- `zoho crm upsert-gate` (`crm-009`: guarded live-upsert decision,
  `liveWritesEnabled=false`, scope matching, `decision=defer_live_execution`,
  blockers include `audit_persistence_not_implemented` and
  `controlled_live_fixture_not_recorded`)
- `zoho crm write-audit` (`crm-010`: redacted JSONL audit inspection for
  `crm.write.plan` and `crm.write.gate`; use `--audit-file` or
  `ZOHO_CRM_WRITE_AUDIT`; events must report `rawFieldValuesStored=false`)
- `zoho crm fixture-plan` (`crm-011`: controlled live fixture readiness gate,
  `policyId=crm-011-controlled-live-fixture-gate`, no CRM writes,
  `liveWritesEnabled=false`)
- `zoho crm fixture-execute` (`crm-012`: guarded fixture-only live upsert
  harness, `policyId=crm-012-guarded-fixture-execution-harness`, dry-run by
  default, requires `ZOHO_CRM_ALLOW_LIVE_FIXTURE=1`, exact approval, cleanup,
  digest, idempotency, and persisted audit evidence for `--execute`)
- `ops/scripts/crm_fixture_live_smoke.sh` (`crm-013`: repeatable controlled CRM
  fixture smoke reports; skips live execution unless `ZOHO_CRM_FIXTURE_EXECUTE=1`
  and `ZOHO_CRM_ALLOW_LIVE_FIXTURE=1`)
- `zoho crm fixture-evidence` (`crm-014`: smoke summary/audit checker,
  `policyId=crm-014-operator-fixture-evidence`, reports `incomplete`,
  `ready_for_operator_live_fixture`, or `live_fixture_recorded`)
- `docs/releases/CRM_V0_5_FIXTURE_PAYLOAD_TEMPLATE.json` (`crm-015`: safe
  one-record `Leads` template with `.example.invalid` placeholder data; copy and
  edit outside the repo before live fixture mode; smoke reports
  `payloadTemplatePlaceholders.emailCount` and blocks
  `fixture_payload_placeholder_email` for live placeholder emails)
- `docs/architecture/CRM_WRITE_SURFACE_CONTRACT.md`

GitHub intake:
- `skill/references/github-intake-workflow.md`
- `.github/ISSUE_TEMPLATE/*`

## Update contract for every CLI change

1. Update lane2 human docs (`README.md`, `docs/releases/CHANGELOG.next.md`) when user-visible behavior changes.
2. Update lane3 skill/docs/scripts for AI usage changes.
3. Verify command examples still match current CLI surface.
4. Keep install/update flows approval-gated for high-impact operations.

## AI-user pull alignment (GitHub)

Before local update, compare:
1. code delta (`git log --oneline <old>..HEAD`)
2. human docs delta (`README.md`, `docs/releases/CHANGELOG.next.md`)
3. lane3 delta (`skill/*`, `integrations/openclaw/*`)

Then summarize command/skill changes and apply local lane3 sync.

## Safety checks

- no secrets/tokens in committed lane3 docs/scripts
- no machine-specific absolute paths unless explicitly template/example-scoped
- repo/package URLs must target `adwasd-dvd/zoho-cli`
- GitHub bugs, suggestions, docs mismatches, and AI employee observations must
  target `adwasd-dvd/zoho-cli`, use existing labels, search duplicates first,
  and redact private data before issue creation
- AI employee observations use `agent-feedback`, `openclaw`, and `needs-triage`
- native OpenClaw channel docs must default to pairing/allowlist access, scoped
  employee mode, SecretRef credentials, loop prevention, native approval
  surfaces, session grammar alignment, human install/onboarding UX, native
  status/capability/routing diagnostics, redacted diagnostics, and `zoho`
  CLI-backed Zoho API operations
