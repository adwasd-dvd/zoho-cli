# CRM write-surface safety contract

Updated: `2026-05-05T12:04:56Z`.

This is the `crm-007` contract for adding CRM write commands without making AI
agents accidentally mutate production data.

## Current decision

Normal CRM writes are **not enabled** in this slice. The only live write path is
the controlled fixture harness introduced in `crm-012`, and it requires a
dedicated command plus multiple independent gates.

`zoho crm write-plan` exposes the machine-readable contract through
`writeSurfacePolicy`:

- `writesEnabled=false`
- default mode is `dry-run`
- first implementation candidate is `zoho crm upsert`
- `zoho crm delete` remains blocked until a later slice
- live writes must require `--execute`, exact `--confirm`, an idempotency key,
  JSON payload input, and an audit envelope

The current read adapter remains `http-v2`. Write implementation should target
CRM API v8 explicitly through the later write command contract, not by changing
read defaults.

## Implemented in crm-008

`zoho crm upsert` is now implemented as a dry-run-only command.

Supported input:

```bash
zoho crm upsert \
  --module Leads \
  --data-json '{"Last_Name":"Wang","Email":"wang@example.com"}' \
  --duplicate-check-field Email \
  --idempotency-key crm-leads-import-2026-05-05
```

The command accepts either `--data-json` or `--data-file`, wraps a single JSON
record into a `data` array, preserves a full request body when `data` already
exists, requires duplicate-check fields and an idempotency key, and emits:

- `status=planned`
- `dryRun=true`
- `liveWritesEnabled=false`
- `payloadDigest` and per-record `recordDigests`
- `fieldNames`, `recordCount`, and `duplicateCheckFields`
- `requiredConfirmation`
- redacted audit metadata without raw field values

`--execute` is intentionally blocked in `crm-008`. If confirmation is missing,
the command returns `confirm_required`; even with the exact confirmation it
returns `live_write_not_enabled`.

## Implemented in crm-009

`zoho crm upsert-gate` now exposes the guarded live execution decision:

```bash
zoho crm upsert-gate --module Leads
zoho crm upsert-gate --module Leads --check-auth
```

The command does not write CRM data. It reports:

- `liveWritesEnabled=false`
- `decision=defer_live_execution`
- accepted OAuth scope candidates for the module
- configured or live granted scopes
- matching scopes, when present
- blocking reasons:
  - `live_writes_disabled_by_policy`
  - `live_oauth_not_checked` unless `--check-auth` was used
  - `upsert_scope_not_verified` when no accepted scope is present
  - `audit_persistence_not_implemented`
  - `controlled_live_fixture_not_recorded`

## Implemented in crm-010

CRM write planning events now persist to a redacted local JSONL audit store:

```bash
zoho crm upsert \
  --module Leads \
  --data-json '{"Last_Name":"Wang","Email":"wang@example.com"}' \
  --duplicate-check-field Email \
  --idempotency-key crm-leads-import-2026-05-05

zoho crm upsert-gate --module Leads
zoho crm write-audit --operation upsert --module Leads --limit 10
```

Persistence behavior:

- `zoho crm upsert` records `crm.write.plan` before output or blocked
  `--execute` errors.
- `zoho crm upsert-gate` records `crm.write.gate`.
- The default audit path is `crm_write_audit.jsonl` next to the configured Zoho
  config file.
- `ZOHO_CRM_WRITE_AUDIT` or `--audit-file` can override the JSONL path for CI,
  agents, and controlled tests.
- `zoho crm write-audit` lists recent events and supports `--operation`,
  `--module`, `--event-type`, and `--limit`.

Audit events include operation, module, field API names, record counts, payload
digests, idempotency key, scope-gate facts, blockers, and persistence metadata.
They do not store raw field values, tokens, or secrets, and expose
`rawFieldValuesStored=false`.

Live `upsert` execution remains disabled after `crm-010`. The next safe slice is
controlled live fixture evidence.

## Implemented in crm-011

`zoho crm fixture-plan` now evaluates controlled live fixture readiness without
writing CRM data:

```bash
zoho crm fixture-plan \
  --module Leads \
  --duplicate-check-field Email \
  --idempotency-key crm-leads-import-2026-05-05 \
  --payload-digest sha256:<reviewed-digest> \
  --audit-file /tmp/zoho-crm-audit.jsonl
```

The command reads recent redacted audit events and reports:

- `policyId=crm-011-controlled-live-fixture-gate`
- `liveWritesEnabled=false`
- `decision=defer_controlled_live_fixture`
- whether matching `crm.write.plan` evidence exists
- whether matching `crm.write.gate` and accepted-scope evidence exists
- required gates before any future controlled live fixture
- blockers such as `operator_fixture_approval_required`,
  `fixture_cleanup_plan_required`, and
  `controlled_live_fixture_execution_not_implemented`

`fixture-plan` also persists a `crm.write.fixture_plan` audit event when an
audit path is configured. It is a readiness gate, not an execution command.

## Implemented in crm-012

`zoho crm fixture-execute` now provides the guarded fixture-only upsert harness:

```bash
zoho crm fixture-execute \
  --module Leads \
  --data-file /tmp/lead-fixture.json \
  --duplicate-check-field Email \
  --idempotency-key crm-fixture-2026-05-05 \
  --payload-digest sha256:<reviewed-digest> \
  --audit-file /tmp/zoho-crm-audit.jsonl
```

By default, the command is a dry-run and reports `requiredApproval`. A live
fixture run requires all of the following:

- `--execute`
- `ZOHO_CRM_ALLOW_LIVE_FIXTURE=1`
- exact `--fixture-approval` matching `requiredApproval`
- non-empty `--cleanup-plan` whose text is not stored, only digested
- one-record payload whose computed digest matches `--payload-digest`
- matching `crm.write.plan`, `crm.write.gate`, and `crm.write.fixture_plan`
  events in the redacted audit log
- accepted OAuth upsert scope evidence from the gate event

When every gate matches, the execution decision is
`allow_controlled_live_fixture_execution`.

When all gates pass, the command performs `POST /{module_api_name}/upsert`
against CRM API v8 and persists:

- `crm.write.fixture_attempt` before any network write
- `crm.write.fixture_result` after the API response

The output and audit log store field API names, payload digest, idempotency key,
approval/cleanup summaries, HTTP status, action/code/status, and CRM record IDs
needed for cleanup. They do not store raw CRM field values, tokens, secrets, raw
approval text, raw cleanup text, or raw API responses.

Normal `zoho crm upsert --execute` still returns `live_write_not_enabled`; the
fixture harness is intentionally separate so broad live writes cannot be invoked
accidentally.

## Implemented in crm-013

`ops/scripts/crm_fixture_live_smoke.sh` records the controlled fixture sequence
as repeatable report files:

```bash
ZOHO_CRM_FIXTURE_PAYLOAD_FILE=/tmp/lead-fixture.json \
ZOHO_CRM_FIXTURE_IDEMPOTENCY_KEY=crm-fixture-2026-05-05 \
ZOHO_CRM_FIXTURE_CLEANUP_PLAN="remove or update the dedicated fixture record after validation" \
ops/scripts/crm_fixture_live_smoke.sh
```

Dry-run mode writes:

- upsert dry-run report
- upsert gate report with `--check-auth`
- fixture-plan report
- fixture-execute dry-run report containing `requiredApproval`
- write-audit summary
- top-level smoke summary

To run the live fixture, the operator must deliberately add both gates:

```bash
ZOHO_CRM_FIXTURE_EXECUTE=1 \
ZOHO_CRM_ALLOW_LIVE_FIXTURE=1 \
ZOHO_CRM_FIXTURE_PAYLOAD_FILE=/tmp/lead-fixture.json \
ZOHO_CRM_FIXTURE_CLEANUP_PLAN="remove or update the dedicated fixture record after validation" \
ops/scripts/crm_fixture_live_smoke.sh
```

The script never echoes the raw payload and does not pass `--execute` unless
both live environment gates are present. It is the recommended real-environment
CRM test entrypoint for operators and AI agents.

## Implemented in crm-014

`zoho crm fixture-evidence` checks the smoke harness output without writing CRM
data:

```bash
zoho crm fixture-evidence \
  --summary-file tests/auto_pilot/reports/crm_fixture_live_smoke_summary_<run>.json
```

It reads the top-level smoke summary, resolves the referenced report files,
reads the redacted audit JSONL, and reports:

- `policyId=crm-014-operator-fixture-evidence`
- `status=ready_for_operator_live_fixture` when dry-run evidence is complete and
  the only remaining step is a deliberate operator live run
- `status=live_fixture_recorded` when a network write attempt and
  `crm.write.fixture_result` are both present
- missing reports or audit events before a live fixture is attempted
- redaction facts for raw field values, approval text, cleanup text, and raw API
  responses

This command is the RC evidence checker. It does not enable broad CRM writes;
normal `zoho crm upsert --execute` stays blocked.

## Official API references

Primary Zoho CRM v8 write references checked on 2026-05-05:

- Upsert records:
  <https://www.zoho.com/crm/developer/docs/api/v8/upsert-records.html>
- Update records:
  <https://www.zoho.com/crm/developer/docs/api/v8/update-records.html>
- Insert records:
  <https://www.zoho.com/crm/developer/docs/api/v8/insert-records.html>
- Delete records:
  <https://www.zoho.com/crm/developer/docs/api/v8/delete-records.html>

Observed shared facts:

- record writes use module API names and Field API names;
- insert, update, upsert, and delete record APIs are under
  `{api-domain}/crm/{version}/{module_api_name}`;
- insert, update, upsert, and delete support up to 100 records per request;
- upsert uses `POST /{module_api_name}/upsert`;
- delete uses `DELETE /{module_api_name}/{record_id}` or ids query form.

## Operation order

1. `upsert` first:
   - best fit for AI agents because duplicate/external-id fields make retries
     safer than blind creates;
   - default to dry-run;
   - require duplicate check fields, `--idempotency-key`, `--execute`, and exact
     `--confirm crm:upsert:<module>:<recordCount>` before any live call.
2. `update` second:
   - require record id, preflight read summary, idempotency key, dry-run default,
     and exact `--confirm crm:update:<module>:<recordId>`.
3. `create` third:
   - prefer upsert when a stable duplicate/external-id field exists;
   - require duplicate warning, idempotency key, dry-run default, and exact
     `--confirm crm:create:<module>:<recordCount>`.
4. `delete` later:
   - blocked until recovery/soft-delete semantics, preflight read summaries, and
     delete-specific audit replay guidance are documented and tested.

## Required output contract

Dry-run output must be JSON-safe and scriptable:

```json
{
  "status": "planned",
  "dryRun": true,
  "execute": false,
  "operation": "upsert",
  "module": "Leads",
  "recordCount": 1,
  "fieldNames": ["Last_Name", "Email"],
  "payloadDigest": "sha256:<hex>",
  "adapter": "http-v8",
  "apiVersion": "v8",
  "requiredConfirmation": "crm:upsert:Leads:1",
  "audit": {
    "event": "crm.write.plan",
    "idempotencyKeyRequired": true
  }
}
```

Live output must preserve the same envelope and add Zoho response details under
`result`, never replacing the audit fields.

## Non-goals

- Do not enable live CRM writes in `crm-007` or `crm-008`.
- Do not switch read commands from HTTP v2 to v8 as part of write planning.
- Do not implement delete before upsert/update/create safety evidence exists.
- Do not accept non-JSON ad hoc payload strings for AI-facing write commands.
