# CRM v0.5 SDK adoption plan

Updated: `2026-05-05T11:51:41Z`.

This is the `crm-003` handoff for phasing the official Zoho CRM server-side
Python SDK into `zoho-cli` without breaking the current AI-safe CLI contract.

## Source check

Primary sources checked on 2026-05-05:

- Zoho CRM server-side Python SDK guide:
  <https://www.zoho.com/crm/developer/docs/sdk/server-side/python-sdk.html>
- Official SDK repository:
  <https://github.com/zoho/zohocrm-python-sdk-8.0>
- Zoho CRM v8 API docs:
  <https://www.zoho.com/crm/developer/docs/api/v8/>
- Zoho CRM v8 OpenAPI docs:
  <https://www.zoho.com/crm/developer/docs/api/v8/openapi-specification.html>

Observed facts:

- The official SDK package for CRM API v8 is `zohocrmsdk8_0`
  / `zohocrmsdk8-0`, imported as `zohocrmsdk`.
- PyPI currently reports `zohocrmsdk8_0==5.0.0`.
- The official GitHub repository lists `5.0.0` as the latest release and uses
  CRM API v8 endpoints.
- The Zoho web guide still references older v8 SDK release wording in places,
  so the implementation source of truth for package versioning is the official
  GitHub/PyPI package metadata.
- The SDK depends on `requests==2.32.4`, `urllib3`, `python-dateutil`, and
  `setuptools`; it also has optional MySQL token-store support.

## Decision

Adopt the SDK behind an adapter boundary, not directly in command handlers.

For v0.5, keep the current `http-v2` CRM adapter as the default until the SDK
adapter proves parity on the read-only surface. The CLI contract remains:

- JSON-safe stdout for agents and scripts.
- diagnostics/errors on stderr.
- no SDK global state, token CSV files, or resource metadata files leaking into
  the project root by default.
- no shape change for `crm modules`, `crm fields`, `crm list`, `crm get`, or
  `crm search` until a documented major or explicit compatibility slice.

## Implemented in crm-003

- Added optional dependency extra: `zoho-cli[crm-sdk]` ->
  `zohocrmsdk8_0==5.0.0`.
- Added `zoho crm sdk-status` for AI/operator diagnostics.
- Added SDK readiness facts without importing the SDK at runtime:
  distribution, import package, target version, installed version, default
  adapter (`http-v2`), proposed adapter (`sdk-v8`), source links, and JSON
  contract reminders.

## Implemented in crm-004

- Added `zoho_cli/crm_sdk.py` as the optional SDK boundary. The module imports
  without the SDK installed, so normal `http-v2` CRM commands stay lightweight.
- Added SDK data-center mapping from existing account config hosts to official
  production environments (`us`, `eu`, `in`, `au`, `jp`, `ca`, `cn`, `sa`).
- Added a CLI-managed resource/cache policy. By default resources live under
  the platform cache directory; operators can override with
  `ZOHO_CRM_SDK_RESOURCE_PATH`. The skeleton prevents SDK cwd token/resource
  defaults from becoming the project root behavior.
- Added a read-only `ZohoCrmSdkAdapter` skeleton with injectable backend methods
  for `modules`, `fields`, `list_records`, `get_record`, and `search_records`.
  It normalizes SDK response/model objects into plain JSON-compatible dict/list
  payloads for parity tests.
- Extended `zoho crm sdk-status` with `adapterSkeleton` facts so AI agents can
  see the resolved data-center, managed resource path, token-store path,
  default-disabled status, and JSON-safe output contract.

## Implemented in crm-005

- Added an explicit `--adapter http-v2|sdk-v8` option to read-only commands:
  `crm modules`, `crm fields`, `crm list`, `crm get`, and `crm search`.
- Kept `http-v2` as the default. `sdk-v8` is opt-in only and returns a
  structured `sdk_not_installed`/`sdk_initialization_failed` error when the
  optional SDK path is unavailable.
- Added `OfficialZohoCrmSdkBackend` to initialize the official SDK from the
  CLI-refreshed access token, not by changing the base OAuth storage contract.
  SDK token/resource files remain under the CLI-managed resource path.
- Added fixture-backed parity coverage for SDK operation parameter mapping:
  modules, fields, list records, get record, and search records all normalize
  SDK responses into the same JSON-safe dict/list payload shape expected by
  command handlers.
- Refreshed Lane 3 help snapshot so agents can see the explicit `--adapter`
  gate before attempting SDK mode.

## Implemented in crm-006

- Locked the v0.5 API version policy in code via `crm_api_version_policy()`.
- Current default remains `http-v2` against CRM API v2 to preserve existing
  output shapes.
- SDK mode remains explicit with `--adapter sdk-v8` and uses CRM API v8.
- HTTP v8 URL inference is available for compatibility work
  (`infer_crm_base_url(api_version="v8")`), but HTTP v8 is not the default.
- `zoho crm status` and `zoho crm sdk-status` now expose `apiVersionPolicy` so
  AI agents can see the HTTP v2 versus SDK/API v8 decision before choosing a
  path.

## Implemented in crm-007

- Added `crm_write_surface_policy()` and `zoho crm write-plan` so the future CRM
  write surface is machine-readable before live writes exist.
- Exposed `writeSurfacePolicy` through `zoho crm status`, `zoho crm sdk-status`,
  and `zoho crm write-plan`.
- Locked `writesEnabled=false`, dry-run default, exact confirmation,
  idempotency-key, JSON-payload, and audit-envelope requirements.
- Chose `upsert` as the first implementation candidate; `delete` remains blocked
  until recovery/audit replay guidance is documented and tested.
- Added `docs/architecture/CRM_WRITE_SURFACE_CONTRACT.md` as the source of truth
  for CRM write command planning.

## Implemented in crm-008

- Added `zoho crm upsert` as a dry-run-only command.
- The command accepts `--data-json` or `--data-file`, duplicate-check fields,
  and an idempotency key.
- Dry-run output includes `fieldNames`, `recordCount`, `payloadDigest`,
  `recordDigests`, `requiredConfirmation`, and audit metadata without raw field
  values.
- `--execute` remains blocked with `live_write_not_enabled` after exact
  confirmation, so no live CRM writes are enabled in this slice.

## Implemented in crm-009

- Added `crm_upsert_live_gate_policy()` and `zoho crm upsert-gate`.
- The gate reports `liveWritesEnabled=false`, `decision=defer_live_execution`,
  accepted upsert scopes, matching granted scopes, and blocking reasons.
- `--check-auth` can refresh OAuth scopes for the selected account without
  writing CRM data.
- Live upsert remains blocked until audit persistence and controlled live
  fixture evidence are implemented.

## Implemented in crm-010

- Added redacted CRM write audit helpers and JSONL persistence.
- `zoho crm upsert` now persists `crm.write.plan` events before returning a
  dry-run envelope or blocked live-write error.
- `zoho crm upsert-gate` now persists `crm.write.gate` events.
- Added `zoho crm write-audit` for recent audit inspection with operation,
  module, event-type, and limit filters.
- `--audit-file` and `ZOHO_CRM_WRITE_AUDIT` support isolated CI/agent audit
  stores.
- Broad CRM writes remain disabled.

## Implemented in crm-011

- Added `crm_controlled_live_fixture_policy()` and `zoho crm fixture-plan`.
- The command reads redacted write audit events and reports whether matching
  dry-run, upsert-gate, and accepted-scope evidence exists for a proposed
  controlled fixture.
- `fixture-plan` persists `crm.write.fixture_plan` when audit storage is
  configured.
- Broad CRM writes remain disabled.

## Implemented in crm-012

- Added `crm_guarded_fixture_execution_policy()`, safe approval/cleanup helpers,
  redacted CRM upsert response summaries, and `zoho crm fixture-execute`.
- `fixture-execute` defaults to dry-run and reports `requiredApproval`.
- A live fixture upsert requires `--execute`, `ZOHO_CRM_ALLOW_LIVE_FIXTURE=1`,
  exact `--fixture-approval`, `--cleanup-plan`, a one-record payload, matching
  payload digest, idempotency key, and persisted dry-run/gate/fixture-plan audit
  evidence.
- The command writes `crm.write.fixture_attempt` before a live attempt and
  `crm.write.fixture_result` after the API response, without storing raw field
  values, raw cleanup text, raw approval text, or raw API responses.
- Normal `zoho crm upsert --execute` remains blocked.

## Implemented in crm-013

- Added `ops/scripts/crm_fixture_live_smoke.sh` as the operator/AI entrypoint
  for repeatable controlled CRM fixture evidence.
- The script generates redacted report files for upsert dry-run, upsert-gate
  `--check-auth`, fixture-plan, fixture-execute dry-run, write-audit summary,
  and a top-level smoke summary.
- Live execution is skipped by default and requires both
  `ZOHO_CRM_FIXTURE_EXECUTE=1` and `ZOHO_CRM_ALLOW_LIVE_FIXTURE=1`.
- The script requires a dedicated payload file and cleanup plan before live
  execution and never passes `--execute` when the environment gate is absent.

## Implemented in crm-014

- Added `crm_operator_fixture_evidence_status()` and
  `zoho crm fixture-evidence`.
- The command reads a smoke summary, resolves referenced report files, reads the
  redacted CRM write audit JSONL, and classifies evidence as `incomplete`,
  `ready_for_operator_live_fixture`, or `live_fixture_recorded`.
- It checks for dry-run plan, upsert-gate, accepted-scope, fixture-plan,
  fixture-attempt, and fixture-result audit evidence without making a network
  write.
- It reports the `crm-014-operator-fixture-evidence` policy, redaction facts,
  missing reports/events, expected dry-run blockers, and live env gates.
- Broad CRM writes remain disabled.

## Implemented in crm-015

- Added `ops/scripts/crm_fixture_operator_readiness_bundle.sh` as the no-write
  operator handoff wrapper for an existing dry-run smoke summary.
- The bundle runs `zoho crm fixture-evidence`, requires
  `payloadTemplatePlaceholders.emailCount=0`, keeps normal
  `zoho crm upsert --execute` blocked, and reports
  `ready_for_operator_live_fixture` only when the remaining action is operator
  live-fixture approval.
- It blocks incomplete handoffs with stable reasons such as
  `summary_file_missing`, `fixture_evidence_not_ready`,
  `payload_placeholder_count_missing`, and `fixture_payload_placeholder_email`.

## v0.5 slices

1. `crm-004` SDK adapter skeleton (completed):
   - create a small `zoho_cli/crm_sdk.py` boundary;
   - map Zoho data center from existing config;
   - initialize SDK resources under a CLI-managed cache directory;
   - expose read-only adapter methods returning plain dict/list JSON.
2. `crm-005` read-only parity (completed):
   - make `modules`, `fields`, `list`, `get`, and `search` runnable through
     the SDK adapter behind an explicit flag/config gate;
   - preserve current HTTP adapter as default;
   - add parity fixtures and live smoke commands.
3. `crm-006` v8 REST alignment (completed):
   - decide whether the default HTTP adapter should move from `/crm/v2` to
     `/crm/v8`;
   - keep version selection explicit if v2 and v8 responses differ.
4. `crm-007` write-surface planning (completed):
   - only after read parity is green, add draft-first create/update/delete
     commands with scope checks, confirmation gates, and audit-friendly output.
5. `crm-008` first write dry-run implementation (completed):
   - implement `zoho crm upsert` as dry-run by default;
   - require `--execute`, exact `--confirm`, idempotency key, and audit envelope
     before any live call.
6. `crm-009` live upsert gate planning (completed):
   - decide whether to enable live upsert execution in guarded mode;
   - require OAuth scope checks, exact confirmation, idempotency key, and audit
     output before any network write.
7. `crm-010` write audit persistence (completed):
   - persist CRM write dry-run/live gate audit events before any future network
     write;
   - add replay/search guidance for AI agents and operators.
8. `crm-011` controlled live fixture gate (completed):
   - define the smallest safe real-CRM fixture for upsert validation;
   - require explicit operator approval and persisted audit evidence before any
     network write is attempted.
9. `crm-012` guarded fixture execution harness (completed):
   - decide whether a special fixture-only execution path should exist;
   - keep normal `zoho crm upsert --execute` blocked.
10. `crm-013` controlled CRM fixture live smoke harness (completed):
   - prepare the smoke script for a dedicated test record when operator
     approval, scopes, cleanup plan, and environment gates are ready;
   - generate redacted report paths for dry-run evidence and future live
     attempt/result evidence.
11. `crm-014` operator fixture evidence checker (completed):
   - add a CLI evidence checker for the smoke summary and audit JSONL;
   - classify operator readiness and recorded live fixture evidence without
     writing CRM data.
12. `crm-015` operator fixture readiness and live evidence:
   - use the smoke script against a real dedicated CRM fixture payload when the
     operator provides one;
   - run the local payload preflight first so placeholder emails, missing Leads
     fields, and missing cleanup plans are caught before any Zoho-backed smoke;
   - run the no-write readiness bundle before live mode;
   - archive redacted reports and decide whether v0.5 should broaden guarded
     upsert support or stop at fixture evidence.

## Non-goals

- Do not install the SDK as a mandatory dependency in the base CLI yet.
- Do not replace the current HTTP client until parity evidence is recorded.
- Do not add broad CRM write commands before fixture safety evidence is recorded.
