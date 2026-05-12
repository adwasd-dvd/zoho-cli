# CRM v0.5 Fixture Cleanup Plan Template

Copy this template outside the repo, replace the placeholder text, and pair it
with a copied `CRM_V0_5_FIXTURE_PAYLOAD_TEMPLATE.json` payload before any
operator-reviewed fixture run.

This file is a planning aid only. It is not an approval to run live CRM writes.

## Plan Text To Copy

```text
After the fixture evidence is captured, remove or update only the dedicated Zoho
CRM Leads fixture record created for <fixture-idempotency-key>. Select the
fixture by <selector-category>=<operator-provided-selector-value>. Do not touch
any production records or records that do not match the dedicated test fixture.
```

## Required Details

- Action: remove, delete, update, archive, or another explicit cleanup action.
- Target: the dedicated Zoho CRM Leads fixture record.
- Selector category: fixture email, record id, duplicate field, idempotency key,
  or payload digest.
- Scope limit: one operator-owned test fixture only.

## Agent Boundary

Agents may use the finished cleanup plan only for local preflight and dry-run
readiness checks. Live fixture execution remains operator-only and still
requires a dedicated payload, exact approval token, readiness evidence, and the
live environment gates.

Do not store raw selector values, raw fixture email addresses, OAuth tokens,
webhook secrets, or production record identifiers in committed files.
