# CRM v0.5 Fixture Local Precheck Examples

These examples are for local, no-write preparation only. They are meant to help
operators produce a dedicated fixture payload and cleanup plan without exposing
real emails, record ids, OAuth tokens, or production identifiers in committed
files.

Do not run live CRM fixture execution from this file. Live execution remains
operator-only and still requires the dedicated payload, copied cleanup plan,
exact approval token, dry-run evidence, and live environment gates.

## Copy The Templates

Copy the payload template and cleanup-plan template outside the repository:

```bash
cp docs/releases/CRM_V0_5_FIXTURE_PAYLOAD_TEMPLATE.json /tmp/zoho-crm-fixture.json
cp docs/releases/CRM_V0_5_FIXTURE_CLEANUP_PLAN_TEMPLATE.md /tmp/zoho-crm-cleanup-plan.md
```

Edit the copied payload so it contains exactly one dedicated test `Leads`
record. Replace the template email with an operator-owned fixture address.
Keep the raw address out of committed files and issue comments.

## Cleanup Plan Shape

Use a cleanup plan with an explicit action, target, selector category, and scope
limit. Example shape:

```text
After the fixture evidence is captured, delete only the dedicated Zoho CRM Leads
fixture record created for the CRM v0.5 test run. Select the fixture by fixture
email=<operator-owned-test-fixture-email>. Do not touch any production records
or records that do not match the dedicated test fixture.
```

Other accepted selector categories include record id, duplicate field,
idempotency key, and payload digest. Use one selector category that can identify
only the dedicated test record.

## Local Recheck

Run the compact no-write wrapper after preparing the copied files:

```bash
ZOHO_CRM_FIXTURE_PAYLOAD_FILE=/tmp/zoho-crm-fixture.json \
ZOHO_CRM_FIXTURE_CLEANUP_PLAN="$(cat /tmp/zoho-crm-cleanup-plan.md)" \
ops/scripts/crm_fixture_agent_next_command.sh
```

Expected local-only outcomes:

- `operator_input_required`: the payload or cleanup plan still needs operator
  input.
- `agent_next_command_ready`: the next command is an allowlisted dry-run/local
  command.
- `stop_before_operator_live_fixture`: the next step is operator-only or would
  write Zoho data.

The wrapper output is redacted and should not contain raw fixture email values,
raw cleanup text, OAuth tokens, or local payload paths.

## Common Fixes

- `fixture_payload_placeholder_email`: replace `example.invalid`, `replace-me`,
  and other template markers in the copied payload.
- `cleanup_plan_action_missing`: name the cleanup action, such as delete,
  remove, update, or archive.
- `cleanup_plan_target_missing`: name the target as the dedicated Zoho CRM Leads
  fixture record.
- `cleanup_plan_selector_missing`: name a selector category such as fixture
  email, record id, duplicate field, idempotency key, or payload digest.
