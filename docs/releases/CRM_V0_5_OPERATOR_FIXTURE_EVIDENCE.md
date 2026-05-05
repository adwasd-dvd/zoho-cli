# CRM v0.5 operator fixture evidence

This runbook is the operator-facing path for proving one controlled CRM fixture
write before deciding whether CRM v0.5 can broaden guarded upsert support.

## Dry-run evidence

Prepare a dedicated fixture payload outside the repo. Use a record that is safe
to create or update and easy to clean up.

Start from the repo template, but do not use it unchanged for live mode:

```bash
cp docs/releases/CRM_V0_5_FIXTURE_PAYLOAD_TEMPLATE.json /tmp/lead-fixture.json
$EDITOR /tmp/lead-fixture.json
```

Payload checklist:

- Keep the file to one `Leads` record, not a list or bulk import body.
- Keep `Last_Name`, `Company`, and `Email` present.
- Replace the `.example.invalid` email with a dedicated operator-owned CRM test
  address before any live fixture.
- Use fake, searchable values that are not customer, employee, or private data.
- Make the cleanup plan specific enough to remove or update the resulting test
  record by the returned CRM id or dedicated test email.

The smoke script records `payloadTemplatePlaceholders.emailCount` in its summary
and refuses live mode with `fixture_payload_placeholder_email` while the payload
email still contains `example.invalid` or `replace-me`.

```bash
ZOHO_CRM_FIXTURE_PAYLOAD_FILE=/tmp/lead-fixture.json \
ZOHO_CRM_FIXTURE_IDEMPOTENCY_KEY=crm-fixture-$(date +%F) \
ZOHO_CRM_FIXTURE_CLEANUP_PLAN="remove or update the dedicated fixture record after validation" \
ops/scripts/crm_fixture_live_smoke.sh
```

Then check the top-level summary:

```bash
zoho crm fixture-evidence \
  --summary-file tests/auto_pilot/reports/crm_fixture_live_smoke_summary_<run>.json
```

Expected dry-run status before any live write:

- `policyId=crm-014-operator-fixture-evidence`
- `status=ready_for_operator_live_fixture`
- `operatorReadiness.readyForLiveFixture=true`
- `blockingReasons=["live_fixture_not_recorded"]`
- `redaction.ok=true`

If the status is `incomplete`, fix the reported missing report, audit event,
scope evidence, cleanup plan, or redaction blocker before considering live mode.
Before live mode, also inspect the smoke summary JSON directly and require
`payloadTemplatePlaceholders.emailCount=0`.

## Live fixture evidence

Only run live mode when the operator has reviewed the payload, cleanup plan,
payload digest, and `requiredApproval` from the dry-run reports.

```bash
ZOHO_CRM_FIXTURE_EXECUTE=1 \
ZOHO_CRM_ALLOW_LIVE_FIXTURE=1 \
ZOHO_CRM_FIXTURE_PAYLOAD_FILE=/tmp/lead-fixture.json \
ZOHO_CRM_FIXTURE_IDEMPOTENCY_KEY=crm-fixture-$(date +%F) \
ZOHO_CRM_FIXTURE_CLEANUP_PLAN="remove or update the dedicated fixture record after validation" \
ops/scripts/crm_fixture_live_smoke.sh
```

Re-check the new summary:

```bash
zoho crm fixture-evidence \
  --summary-file tests/auto_pilot/reports/crm_fixture_live_smoke_summary_<run>.json
```

Expected live evidence status:

- `status=live_fixture_recorded`
- `releaseEvidenceReady=true`
- `auditEvidence.hasFixtureResult=true`
- `liveResultRecorded=true`
- `blockingReasons=[]`

Normal `zoho crm upsert --execute` must remain blocked throughout this process.
