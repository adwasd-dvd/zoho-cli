# CRM v0.5 SDK adoption plan

Updated: `2026-05-05T09:49:08Z`.

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

## v0.5 slices

1. `crm-004` SDK adapter skeleton:
   - create a small `zoho_cli/crm_sdk.py` boundary;
   - map Zoho data center from existing config;
   - initialize SDK resources under a CLI-managed cache directory;
   - expose read-only adapter methods returning plain dict/list JSON.
2. `crm-005` read-only parity:
   - make `modules`, `fields`, `list`, `get`, and `search` runnable through
     the SDK adapter behind an explicit flag/config gate;
   - preserve current HTTP adapter as default;
   - add parity fixtures and live smoke commands.
3. `crm-006` v8 REST alignment:
   - decide whether the default HTTP adapter should move from `/crm/v2` to
     `/crm/v8`;
   - keep version selection explicit if v2 and v8 responses differ.
4. `crm-007` write-surface planning:
   - only after read parity is green, add draft-first create/update/delete
     commands with scope checks, confirmation gates, and audit-friendly output.

## Non-goals

- Do not install the SDK as a mandatory dependency in the base CLI yet.
- Do not replace the current HTTP client until parity evidence is recorded.
- Do not add CRM write commands before read-only SDK parity and live safety
  gates are complete.
