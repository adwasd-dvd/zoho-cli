# Command playbook

## Mail

```bash
# Inbox triage
zoho mail list --folder Inbox --limit 20

# Search and inspect one message
zoho mail search "invoice" --limit 5
zoho mail get <message_id>

# Reply and mark read
zoho mail reply <message_id> --text "Received. I will follow up shortly."
zoho mail mark-read <message_id>
```

## Cliq (network-scoped)

```bash
# Basic health and capability check
zoho cliq status --check-auth --network happydistrouklimited
zoho cliq capabilities --network happydistrouklimited

# Unread intake loop (exclude messages already reacted by this account)
zoho cliq chats --network happydistrouklimited --unread-only --exclude-reacted-by-self

# Context + reply
zoho cliq context --network happydistrouklimited --chat-id <chat_id> --limit 20
zoho cliq reply --network happydistrouklimited --chat-id <chat_id> --message-id <msg_id> --text "On it."

# Acknowledge after handling
zoho cliq mark-read --network happydistrouklimited --chat-id <chat_id> --latest
```

## Cliq reaction status lifecycle

```bash
# received
zoho cliq status-react <msg_id> --status received --chat-id <chat_id> --network happydistrouklimited --clear-known

# thinking
zoho cliq status-react <msg_id> --status thinking --chat-id <chat_id> --network happydistrouklimited --clear-known

# writing
zoho cliq status-react <msg_id> --status writing --chat-id <chat_id> --network happydistrouklimited --clear-known

# testing
zoho cliq status-react <msg_id> --status testing --chat-id <chat_id> --network happydistrouklimited --clear-known

# blocked / done / failed
zoho cliq status-react <msg_id> --status blocked --chat-id <chat_id> --network happydistrouklimited --clear-known
zoho cliq status-react <msg_id> --status done    --chat-id <chat_id> --network happydistrouklimited --clear-known
zoho cliq status-react <msg_id> --status failed  --chat-id <chat_id> --network happydistrouklimited --clear-known
```

## CRM (read-first)

```bash
zoho crm status --check-auth
zoho crm sdk-status
zoho crm modules
zoho crm fields --module Leads
zoho crm list --module Leads --limit 5
```

For SDK migration work, inspect `zoho crm sdk-status` and
`docs/architecture/CRM_V0_5_SDK_ADOPTION_PLAN.md` first. `crm-004` keeps the
`zoho_cli/crm_sdk.py` data-center adapter skeleton default-disabled; SDK
resources must stay under `ZOHO_CRM_SDK_RESOURCE_PATH` or the CLI-managed cache.
Use explicit `--adapter sdk-v8` only for SDK parity checks:

```bash
zoho crm modules --adapter sdk-v8
zoho crm list --module Leads --adapter sdk-v8 --limit 5
```

`zoho crm status` and `zoho crm sdk-status` expose `apiVersionPolicy`; keep
HTTP v2 as default and SDK/API v8 explicit-only unless a later compatibility
slice records live shape parity.

Before any CRM write work, inspect the write contract:

```bash
zoho crm write-plan
zoho crm write-plan --operation upsert
```

`crm-007` exposes `writeSurfacePolicy` with `writesEnabled=false`, dry-run
default, exact confirmation, idempotency-key, JSON-payload, and audit-envelope
requirements. Do not invent live write commands while `writesEnabled=false`;
the next candidate is `zoho crm upsert` dry-run, and delete remains blocked.

`crm-008` implements that first dry-run command:

```bash
zoho crm upsert \
  --module Leads \
  --data-json '{"Last_Name":"Example","Email":"example@example.com"}' \
  --duplicate-check-field Email \
  --idempotency-key crm-leads-upsert-$(date +%F)
```

Use the returned `payloadDigest`, `fieldNames`, `recordCount`, and
`requiredConfirmation` for review. The command does not echo raw field values.
`--execute` is intentionally blocked with `live_write_not_enabled`.

Before any future live upsert decision, inspect the gate:

```bash
zoho crm upsert-gate --module Leads
zoho crm upsert-gate --module Leads --check-auth
```

`crm-009` keeps `liveWritesEnabled=false` and `decision=defer_live_execution`.
Use `scopeGate.matchingScopes` only as readiness evidence; blockers such as
`audit_persistence_not_implemented` and `controlled_live_fixture_not_recorded`
mean live writes remain disabled.

`crm-010` persists redacted JSONL audit events for dry-run and gate commands.
Use `--audit-file` or `ZOHO_CRM_WRITE_AUDIT` to isolate an agent run:

```bash
zoho crm upsert \
  --module Leads \
  --data-json '{"Last_Name":"Example","Email":"example@example.com"}' \
  --duplicate-check-field Email \
  --idempotency-key crm-leads-upsert-$(date +%F) \
  --audit-file /tmp/zoho-crm-audit.jsonl

zoho crm write-audit \
  --audit-file /tmp/zoho-crm-audit.jsonl \
  --operation upsert \
  --module Leads \
  --limit 10
```

Audit events should show `rawFieldValuesStored=false`; do not paste raw field
values, tokens, or secrets into audit reports.

For a future real-environment CRM test, plan the fixture gate first:

```bash
zoho crm fixture-plan \
  --audit-file /tmp/zoho-crm-audit.jsonl \
  --module Leads \
  --duplicate-check-field Email \
  --idempotency-key crm-leads-upsert-$(date +%F) \
  --payload-digest sha256:<reviewed-digest>
```

`crm-011` reports dry-run/gate/scope audit evidence and fixture blockers. It is
not a live write command; `liveWritesEnabled=false` remains authoritative.

To prepare the guarded fixture execution harness, first run it without
`--execute` and copy only the returned `requiredApproval` token:

```bash
zoho crm fixture-execute \
  --audit-file /tmp/zoho-crm-audit.jsonl \
  --module Leads \
  --data-file /tmp/lead-fixture.json \
  --duplicate-check-field Email \
  --idempotency-key crm-leads-upsert-$(date +%F) \
  --payload-digest sha256:<reviewed-digest>
```

Only run a real fixture when the user has approved the dedicated test record and
cleanup plan:

```bash
ZOHO_CRM_ALLOW_LIVE_FIXTURE=1 zoho crm fixture-execute \
  --audit-file /tmp/zoho-crm-audit.jsonl \
  --module Leads \
  --data-file /tmp/lead-fixture.json \
  --duplicate-check-field Email \
  --idempotency-key crm-leads-upsert-$(date +%F) \
  --payload-digest sha256:<reviewed-digest> \
  --fixture-approval crm:fixture:upsert:Leads:<digest-prefix>:<idempotency-key> \
  --cleanup-plan "remove or update the dedicated fixture record after validation" \
  --execute
```

`crm-012` persists `crm.write.fixture_attempt` and
`crm.write.fixture_result`, redacts raw field values and raw responses, and keeps
normal `zoho crm upsert --execute` blocked.

For operator/live smoke evidence, prefer the repeatable script:

```bash
cp docs/releases/CRM_V0_5_FIXTURE_PAYLOAD_TEMPLATE.json /tmp/lead-fixture.json
$EDITOR /tmp/lead-fixture.json
```

The template is safe for dry-run planning only. Before live mode, replace the
`.example.invalid` email with a dedicated operator-owned test address and keep
the payload to one `Leads` record with a cleanup plan. The smoke summary reports
`payloadTemplatePlaceholders.emailCount`, and live mode fails with
`fixture_payload_placeholder_email` if template email markers remain.

Preflight the copied payload locally before any Zoho-backed smoke:

```bash
ZOHO_CRM_FIXTURE_PAYLOAD_FILE=/tmp/lead-fixture.json \
ZOHO_CRM_FIXTURE_CLEANUP_PLAN="remove the dedicated fixture record by fixture email after validation" \
ops/scripts/crm_fixture_payload_preflight.sh
```

Require `status=payload_preflight_ready`, `payload.placeholderEmailCount=0`,
`cleanup.present=true`, `cleanup.selectorPresent=true`, and
`nextAction=run_crm_fixture_live_smoke_dry_run`; inspect
`cleanup.selectorTypes` for redacted categories such as `email_keyword`,
`record_id`, `idempotency_key`, or `payload_digest`. The preflight blocks with
`fixture_payload_placeholder_email`, `required_fields_missing`,
`cleanup_plan_missing`, `cleanup_plan_too_short`,
`cleanup_plan_action_missing`, `cleanup_plan_target_missing`, or
`cleanup_plan_selector_missing` and stores no raw email or cleanup plan.

For automation, prefer the combined packet:

```bash
ZOHO_CRM_FIXTURE_PAYLOAD_FILE=/tmp/lead-fixture.json \
ZOHO_CRM_FIXTURE_CLEANUP_PLAN="remove the dedicated fixture record by fixture email after validation" \
ops/scripts/crm_fixture_operator_packet.sh
```

It emits one redacted `crm_fixture_operator_packet` with `status=blocked`,
`payload_preflight_ready`, `ready_for_operator_live_fixture`, or
`live_fixture_recorded`, and keeps `agentMayExecuteLiveFixture=false`. Use
`operatorReview.readyFacts` and `operatorReview.missingFacts` to decide whether
the next safe step is providing a payload, improving cleanup, running dry-run
smoke, or asking for operator live approval; these facts are category names only
and must not contain raw payload, email, cleanup, or selector values.
Use `operatorReview.nextCommands` when an automation needs a command preview:
commands are placeholder-only and include `agentMayExecute`, `dryRunOnly`,
`writesZohoData`, and `requiresExplicitOperatorApproval` gates. Do not run
entries marked `agentMayExecute=false`.
Prefer `operatorReview.actionBoundary.agentExecutableCommandIds` as the
runnable command bucket. Treat `operatorOnlyCommandIds`, `zohoWriteCommandIds`,
and `requiresExplicitOperatorApprovalCommandIds` as stop-and-handoff lists.
Prefer `operatorReview.agentAutomation.nextAgentCommand` when
`agentMayExecuteNextCommand=true`; it already matches the next runnable
dry-run/local id and uses placeholders. Treat `nextAgentCommand=null` as a stop
boundary and explain `stopReason` instead of reconstructing a command.
Use `operatorReview.liveApproval` before asking for live approval: it reports
only booleans for summary/evidence readiness, payload digest, idempotency key,
required approval presence, placeholder state, and the operator-only execution
boundary. Prefer `operatorReview.liveApproval.readyFacts` / `missingFacts` to
explain missing approval categories, and do not log or reconstruct the exact
approval token.
Use `reportFiles` and `reportsReady` to hand off the packet, preflight,
readiness bundle, and smoke-summary basenames without exposing local paths.

For a recurring RC heartbeat or autonomous sweep across both native Cliq RC
publish readiness and CRM fixture readiness, run:

```bash
ops/scripts/zoho_cli_rc_autonomy_packet.sh
```

It emits `zoho_cli_rc_autonomy_packet`. Execute a command only when
`status=agent_next_command_ready` and
`safety.crmNextCommandAllowedForAgent=true`; use `recommendedAgentCommand` as
the redacted command preview. `safety.crmNextCommandAllowlistedDryRunLocal`
only means the underlying CRM command id/path is recognized; it is not enough
to execute while the top-level status is still an operator-input state. Treat
`operator_input_required`,
`operator_publish_path_required`, `stop_before_operator_publish`, and
`stop_before_operator_live_fixture` as handoff boundaries. The packet is
read-only and keeps publish/tag/GitHub release/expectedIntegrity fill plus live
Zoho writes disabled for agents. Read `operatorActionRequests` for the exact
human-facing asks, such as `select_openclaw_cliq_publish_path`,
`provide_crm_fixture_cleanup_plan`, and `provide_crm_fixture_payload_file`;
these entries are guidance only, include placeholder-only `commandPreview` /
`unblocks` hints for the next local recheck, and always keep
`agentMayExecute=false`.

To render the exact human handoff from those requests, run:

```bash
ops/scripts/zoho_cli_rc_operator_action_prompt.sh
```

It runs or reads the autonomy packet and emits
`zoho_cli_rc_operator_action_prompt`. Treat
`status=operator_action_prompt_ready` and
`nextAction=send_operator_action_prompt` as a notify/handoff state, not an
execution grant. The `messageMarkdown` field is intentionally compact and
redacted: report files are basenames, command previews use placeholders, and
publish/tag/GitHub release/expectedIntegrity fill plus live Zoho writes remain
disabled for agents. Use `--md` when printing that handoff directly to a human;
without `--md`, stdout stays JSON for scripts and agents.

For a compact AI go/stop summary, run:

```bash
ops/scripts/crm_fixture_agent_next_command.sh
```

It runs or reads the operator packet and emits
`crm_fixture_agent_next_command`. Treat `status=agent_next_command_ready` as the
only direct execution state, and require
`safety.nextCommandAllowedForAgent=true`. `status=operator_input_required` means
the command preview is safe but still needs an operator-provided payload,
cleanup plan, or summary value; `status=agent_command_not_allowlisted` means the
packet exposed an unknown command id or script path and must be fixed before
automation; `status=stop_before_operator_live_fixture` means the next step is
operator-only, Zoho-writing, or explicit-approval-gated.

```bash
ZOHO_CRM_FIXTURE_PAYLOAD_FILE=/tmp/lead-fixture.json \
ZOHO_CRM_FIXTURE_CLEANUP_PLAN="remove or update the dedicated fixture record after validation" \
ops/scripts/crm_fixture_live_smoke.sh
```

It writes redacted reports under `tests/auto_pilot/reports` by default. It only
passes `--execute` when both live gates are present:

```bash
ZOHO_CRM_FIXTURE_EXECUTE=1 \
ZOHO_CRM_ALLOW_LIVE_FIXTURE=1 \
ZOHO_CRM_FIXTURE_PAYLOAD_FILE=/tmp/lead-fixture.json \
ZOHO_CRM_FIXTURE_CLEANUP_PLAN="remove or update the dedicated fixture record after validation" \
ops/scripts/crm_fixture_live_smoke.sh
```

Classify the smoke reports before and after a live fixture:

```bash
zoho crm fixture-evidence \
  --summary-file tests/auto_pilot/reports/crm_fixture_live_smoke_summary_<run>.json
```

Bundle the dry-run readiness handoff before live mode:

```bash
ZOHO_CRM_FIXTURE_SUMMARY_FILE=tests/auto_pilot/reports/crm_fixture_live_smoke_summary_<run>.json \
ops/scripts/crm_fixture_operator_readiness_bundle.sh
```

`crm-014` reports `incomplete`, `ready_for_operator_live_fixture`, or
`live_fixture_recorded`. Treat `redaction.ok=true` as required evidence and keep
normal `zoho crm upsert --execute` blocked.
The readiness bundle must report `ready_for_operator_live_fixture`,
`normalUpsertExecuteBlocked=true`, and `agentMayExecuteLiveFixture=false`; it
blocks with `fixture_payload_placeholder_email` until the copied fixture payload
uses a dedicated non-placeholder test email. Use its `reportFiles` and
`reportsReady` entries to hand off `readinessBundle`, `smokeSummary`, and
`fixtureEvidence` by basename without exposing local paths. It also exposes
redacted `operatorReview.nextCommands` and `operatorReview.actionBoundary`; run
only ids in `agentExecutableCommandIds` and stop on operator-only,
Zoho-writing, or explicit-approval ids. Its
`operatorReview.agentAutomation.nextAgentCommand` mirrors that boundary.

## Bridge fallback (explicit)

```bash
zoho cliq bridge-run --bridge membrane --action-id <action_id> --input-json '{"limit":5}'
zoho crm bridge-run --bridge membrane --action-id <action_id> --input-json '{"module":"Leads","limit":5}'
```
