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
- `ops/scripts/openclaw_cliq_hash_ref.sh`
- `ops/scripts/openclaw_cliq_rc_pack.sh`
- `ops/scripts/openclaw_cliq_trusted_reply_evidence_bundle.sh`
- `ops/scripts/openclaw_cliq_trusted_reply_facts_prepare.sh`
- `ops/scripts/openclaw_cliq_trusted_reply_evidence_prepare.sh`
- `ops/scripts/openclaw_cliq_trusted_reply_evidence.sh`
- `ops/scripts/openclaw_cliq_live_ingress_diagnostic.sh`
- `ops/scripts/openclaw_cliq_bot_no_response_packet.sh`
- `ops/scripts/openclaw_cliq_handler_trigger_packet.sh`
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
- `ops/scripts/openclaw_cliq_rc_operator_decision_packet.sh`
  (`cliq-channel-468`: one-command read-only native Cliq RC publish handoff;
  returns `awaiting_operator_publish_path` until the operator selects
  `local_operator_rc`, `npm_rc_publish`, or `github_release_artifact`; keeps
  `agentMayExecuteSelectedPath=false`; after repo-only docs/state commits,
  `sourceDrift.repoChangedSinceManifest=true` is acceptable only when
  `sourceDrift.packageChangedSinceManifest=false` and
  `package_source_unchanged` is still reported; `cliq-channel-477` records the
  post-CRM selector metadata check at `ae9424e7`, and `cliq-channel-478`
  records the post-CRM command-preview check at `df683f7e`; `cliq-channel-479`
  records the post-CRM report-metadata check at `a926639e`; `cliq-channel-480`
  records the post-CRM readiness-report-metadata check at `0789a734`;
  `cliq-channel-481` adds decision-packet `reportFiles` and `reportsReady`
  evidence handoff metadata; `cliq-channel-482` records read-only
  `local_operator_rc` selected-path readiness with
  `operator_publish_selection_ready` and agent execution still disabled;
  `cliq-channel-483` records read-only `npm_rc_publish` and
  `github_release_artifact` selected-path readiness with command previews still
  non-executable by agents; `cliq-channel-484` records the post-selected-path
  source-drift/decision evidence showing commit `8695726a` changed only
  docs/state relative to the handoff manifest package source;
  `cliq-channel-485` records the post-CRM live-approval-fact-categories
  source-drift/decision evidence showing commit `39642ae7` still keeps
  `packageChangedSinceManifest=false`; `cliq-channel-486` records the
  post-CRM operator-action-boundary source-drift/decision evidence showing
  commit `8a67bbb3` still keeps `packageChangedSinceManifest=false`;
  `cliq-channel-487` records the post-CRM readiness-action-boundary
  source-drift/decision evidence showing commit `25eb507d` still keeps
  `packageChangedSinceManifest=false`; `cliq-channel-488` records the
  post-CRM state-sync source-drift/decision evidence showing commit `0319d9b8`
  still keeps `packageChangedSinceManifest=false`; `cliq-channel-489` records
  the post-CRM next-command-preview source-drift/decision evidence showing
  commit `3f1773c7` still keeps `packageChangedSinceManifest=false`;
  `cliq-channel-492` records the post-platform-214 autonomy-packet
  source-drift/decision evidence showing commit `a03de9e5` still keeps
  `packageChangedSinceManifest=false` while awaiting operator input)
- `ops/scripts/zoho_cli_rc_autonomy_packet.sh` (`platform-214`: read-only
  cross-lane RC autonomy packet that combines native Cliq RC decision state with
  CRM fixture next-command state; emits `agent_next_command_ready` only when the
  CRM command is already allowlisted and dry-run/local, otherwise reports
  operator-input or operator-only stop states while keeping publish/tag/release,
  expectedIntegrity fill, normal CRM upsert execution, and live Zoho writes
  disabled for agents; exposes redacted `operatorActionRequests` with stable
  ids for publish-path selection, fixture cleanup plan, and fixture payload
  file inputs)
- `ops/scripts/openclaw_cliq_bot_no_response_packet.sh`
  (`cliq-channel-472/474`: first responder for Bot no-response reports; runs
  public callback smoke plus live ingress diagnostics, then embeds
  `handlerTrigger` when `no_recent_webhook_ingress` points to a Zoho handler
  trigger/save issue)
- `ops/scripts/openclaw_cliq_handler_trigger_packet.sh`
  (`cliq-channel-473`: redacted handler paste/check packet for Message/Mention/
  Participation/Context handler targets and Deluge `invokeurl` shape)
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
- `ops/scripts/crm_fixture_operator_readiness_bundle.sh` (`crm-015`: no-write
  operator readiness bundle for an existing dry-run smoke summary; requires
  `ready_for_operator_live_fixture`, placeholder email count zero, and keeps
  normal `zoho crm upsert --execute` blocked; `crm-022` adds `reportFiles` and
  `reportsReady` basename metadata for `readinessBundle`, `smokeSummary`, and
  `fixtureEvidence` handoff; `crm-026` adds redacted `operatorReview.nextCommands`
  and the same `operatorReview.actionBoundary` command-id stop/go buckets as the
  operator packet; `crm-028` adds `operatorReview.agentAutomation` for direct
  next-agent-command and stop-command branching)
- `ops/scripts/crm_fixture_operator_packet.sh` (`crm-015`: autonomous no-write
  packet that combines payload preflight and optional dry-run readiness evidence
  into `blocked`, `payload_preflight_ready`, `ready_for_operator_live_fixture`,
  or `live_fixture_recorded`; `crm-017` also requires cleanup plans to include a
  selector such as fixture email, record id, duplicate field, idempotency key, or
  payload digest, otherwise `cleanup_plan_selector_missing` blocks before any
  Zoho-backed smoke; `crm-018` reports redacted `cleanup.selectorTypes` without
  raw selector values; `crm-019` adds redacted `operatorReview.readyFacts` and
  `operatorReview.missingFacts`; `crm-020` adds redacted
  `operatorReview.nextCommands` command previews with explicit agent/live
  execution gates; `crm-021` adds `reportFiles` and `reportsReady` basename
  metadata for packet/preflight/readiness/smoke-summary handoff; `crm-023` adds
  redacted `operatorReview.liveApproval` booleans for approval readiness while
  keeping `agentMayExecute=false`; `crm-024` adds live-approval `readyFacts` and
  `missingFacts` categories for AI handoff decisions; `crm-025` adds
  `operatorReview.actionBoundary` command id buckets for agent-executable vs
  operator-only/Zoho-writing steps; `crm-026` mirrors that boundary on readiness
  bundles; `crm-028` adds `operatorReview.agentAutomation` with
  `nextAgentExecutableCommandId`, `agentMayExecuteNextCommand`,
  `stopCommandIds`, and `stopReason`; `crm-029` adds embedded
  `nextAgentCommand` previews for runnable dry-run/local steps)
- `ops/scripts/crm_fixture_agent_next_command.sh` (`crm-030`: compact no-write
  wrapper that classifies the next CRM fixture step as
  `operator_input_required`, `agent_next_command_ready`, or
  `stop_before_operator_live_fixture`; `crm-032`: enforces the built-in
  local/dry-run command allowlist before reporting `agent_next_command_ready`)
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
