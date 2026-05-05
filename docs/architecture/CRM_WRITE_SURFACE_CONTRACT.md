# CRM write-surface safety contract

Updated: `2026-05-05T10:50:34Z`.

This is the `crm-007` contract for adding CRM write commands without making AI
agents accidentally mutate production data.

## Current decision

CRM writes are **not enabled** in this slice.

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
