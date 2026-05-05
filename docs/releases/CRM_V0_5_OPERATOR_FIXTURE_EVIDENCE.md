# CRM v0.5 operator fixture evidence

This runbook is the operator-facing path for proving one controlled CRM fixture
write before deciding whether CRM v0.5 can broaden guarded upsert support.

## Dry-run evidence

Prepare a dedicated fixture payload outside the repo. Use a record that is safe
to create or update and easy to clean up.

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
