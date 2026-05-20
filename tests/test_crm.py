"""Tests for zoho_cli.crm helpers."""

from importlib import metadata
import json
from pathlib import Path

import httpx
import pytest
import respx

from zoho_cli import crm


def test_infer_crm_base_url_from_mail_host() -> None:
    url = crm.infer_crm_base_url(mail_base_url="https://mail.zoho.eu/api")
    assert url == "https://www.zohoapis.eu/crm/v2"


def test_infer_crm_base_url_from_accounts_host() -> None:
    url = crm.infer_crm_base_url(accounts_server="https://accounts.zoho.com")
    assert url == "https://www.zohoapis.com/crm/v2"


def test_infer_crm_base_url_supports_explicit_v8() -> None:
    url = crm.infer_crm_base_url(
        accounts_server="https://accounts.zoho.eu",
        api_version="v8",
    )
    assert url == "https://www.zohoapis.eu/crm/v8"


def test_infer_crm_base_url_defaults_to_com() -> None:
    url = crm.infer_crm_base_url()
    assert url == "https://www.zohoapis.com/crm/v2"


def test_infer_crm_base_url_rejects_unknown_api_version() -> None:
    try:
        crm.infer_crm_base_url(api_version="v9")
    except ValueError as exc:
        assert "unsupported CRM API version" in str(exc)
    else:  # pragma: no cover - defensive assertion branch.
        raise AssertionError("expected ValueError")


def test_missing_crm_scopes_reports_missing_values() -> None:
    missing = crm.missing_crm_scopes(["ZohoCRM.modules.ALL"])
    assert missing == ["ZohoCRM.settings.ALL"]


def test_storepilot_crm_scope_profile_extends_default_scopes() -> None:
    scopes = crm.crm_required_scopes("storepilot")
    assert scopes[:2] == crm.DEFAULT_CRM_SCOPES
    assert "ZohoCRM.users.ALL" in scopes
    assert "ZohoCRM.org.ALL" in scopes
    assert "ZohoCRM.bulk.ALL" in scopes
    assert "ZohoCRM.notifications.ALL" in scopes
    assert "ZohoCRM.coql.READ" in scopes


def test_missing_crm_scopes_supports_storepilot_profile() -> None:
    missing = crm.missing_crm_scopes(
        ["ZohoCRM.modules.ALL", "ZohoCRM.settings.ALL"],
        profile="storepilot",
    )
    assert missing == [
        "ZohoCRM.users.ALL",
        "ZohoCRM.org.ALL",
        "ZohoCRM.bulk.ALL",
        "ZohoCRM.notifications.ALL",
        "ZohoCRM.coql.READ",
    ]


def test_crm_scope_profile_rejects_unknown_profile() -> None:
    with pytest.raises(ValueError, match="unsupported CRM scope profile"):
        crm.crm_required_scopes("unknown")


def test_crm_sdk_status_reports_missing_sdk() -> None:
    def missing(_: str) -> str:
        raise metadata.PackageNotFoundError

    result = crm.crm_sdk_status(version_lookup=missing)

    assert result["sdk"]["distribution"] == "zohocrmsdk8_0"
    assert result["sdk"]["targetVersion"] == "5.0.0"
    assert result["sdk"]["installed"] is False
    assert result["sdk"]["installedVersion"] is None
    assert result["sdk"]["versionMatchesTarget"] is False
    assert result["sdk"]["optionalExtra"] == "crm-sdk"
    assert result["sdk"]["defaultAdapter"] == "http-v2"
    assert result["sdk"]["proposedAdapter"] == "sdk-v8"
    assert result["contracts"]["sdkAdapterMustPreserveOutputShape"] is True
    assert result["adapterSkeleton"]["adapter"] == "sdk-v8"
    assert result["adapterSkeleton"]["currentCliAdapter"] == "http-v2"
    assert result["adapterSkeleton"]["defaultEnabled"] is False
    assert result["adapterSkeleton"]["outputShape"]["plainJson"] is True
    assert result["apiVersionPolicy"]["defaultHttpApiVersion"] == "v2"
    assert result["apiVersionPolicy"]["sdkApiVersion"] == "v8"


def test_crm_sdk_status_reports_installed_target_version() -> None:
    result = crm.crm_sdk_status(version_lookup=lambda _: "5.0.0")

    assert result["sdk"]["installed"] is True
    assert result["sdk"]["installedVersion"] == "5.0.0"
    assert result["sdk"]["versionMatchesTarget"] is True


def test_crm_sdk_status_uses_account_context_for_adapter_plan() -> None:
    result = crm.crm_sdk_status(
        account_cfg={"accounts_server": "https://accounts.zoho.eu"},
        account_email="crm.bot@example.com",
        version_lookup=lambda _: "5.0.0",
    )

    adapter = result["adapterSkeleton"]
    assert adapter["dataCenter"]["key"] == "eu"
    assert adapter["resourcePath"].endswith("crm.bot_at_example.com")


def test_crm_api_version_policy_preserves_default_http_v2() -> None:
    policy = crm.crm_api_version_policy()

    assert policy["defaultAdapter"] == "http-v2"
    assert policy["defaultHttpApiVersion"] == "v2"
    assert policy["sdkAdapter"] == "sdk-v8"
    assert policy["sdkApiVersion"] == "v8"
    assert policy["selection"]["sdkV8"] == "explicit --adapter sdk-v8 only"
    assert policy["defaultBehavior"] == "preserve-current-output-shapes"


def test_crm_write_surface_policy_disables_writes_and_prefers_upsert() -> None:
    policy = crm.crm_write_surface_policy()

    assert policy["policyId"] == "crm-007-write-surface-contract"
    assert policy["writesEnabled"] is False
    assert policy["defaultMode"] == "dry-run"
    assert policy["firstImplementationCandidate"] == "upsert"
    assert policy["globalRequiredGates"]["dryRunDefault"] is True
    assert policy["globalRequiredGates"]["exactConfirmationRequired"] is True
    assert policy["globalRequiredGates"]["idempotencyKeyRequired"] is True
    assert policy["operations"]["upsert"]["stage"] == "first_candidate"
    assert policy["operations"]["delete"]["stage"] == "blocked_until_later_slice"


def test_crm_write_surface_policy_filters_operation() -> None:
    policy = crm.crm_write_surface_policy(operation="UPDATE")

    assert list(policy["operations"]) == ["update"]
    assert policy["operations"]["update"]["method"] == "PUT"


def test_crm_write_surface_policy_rejects_unknown_operation() -> None:
    with pytest.raises(ValueError, match="unsupported CRM write operation"):
        crm.crm_write_surface_policy(operation="merge")


def test_build_crm_upsert_dry_run_wraps_record_and_redacts_values() -> None:
    plan = crm.build_crm_upsert_dry_run(
        module_api_name="Leads",
        payload={"Last_Name": "Wang", "Email": "wang@example.com"},
        duplicate_check_fields=["Email"],
        idempotency_key="job-123",
    )

    assert plan["status"] == "planned"
    assert plan["dryRun"] is True
    assert plan["liveWritesEnabled"] is False
    assert plan["operation"] == "upsert"
    assert plan["module"] == "Leads"
    assert plan["recordCount"] == 1
    assert plan["fieldNames"] == ["Last_Name", "Email"]
    assert plan["duplicateCheckFields"] == ["Email"]
    assert plan["payloadDigest"].startswith("sha256:")
    assert plan["endpoint"]["path"] == "/Leads/upsert"
    assert plan["requiredConfirmation"] == "crm:upsert:Leads:1"
    assert plan["confirmation"]["matches"] is False
    assert "Wang" not in json.dumps(plan)
    assert "wang@example.com" not in json.dumps(plan)


def test_build_crm_upsert_dry_run_uses_payload_duplicate_fields() -> None:
    plan = crm.build_crm_upsert_dry_run(
        module_api_name="Contacts",
        payload={
            "data": [{"Last_Name": "Singh", "Email": "singh@example.com"}],
            "duplicate_check_fields": ["Email"],
        },
        duplicate_check_fields=[],
        idempotency_key="job-124",
        confirm="crm:upsert:Contacts:1",
    )

    assert plan["duplicateCheckFields"] == ["Email"]
    assert plan["confirmation"]["matches"] is True


def test_build_crm_upsert_dry_run_requires_duplicate_fields() -> None:
    with pytest.raises(ValueError, match="duplicate check field"):
        crm.build_crm_upsert_dry_run(
            module_api_name="Leads",
            payload={"Last_Name": "Wang"},
            duplicate_check_fields=[],
            idempotency_key="job-125",
        )


def test_build_crm_upsert_dry_run_rejects_too_many_records() -> None:
    with pytest.raises(ValueError, match="at most 100 records"):
        crm.build_crm_upsert_dry_run(
            module_api_name="Leads",
            payload=[{"Last_Name": str(i)} for i in range(101)],
            duplicate_check_fields=["Email"],
            idempotency_key="job-126",
        )


def test_crm_upsert_live_gate_policy_keeps_writes_disabled() -> None:
    policy = crm.crm_upsert_live_gate_policy()

    assert policy["policyId"] == "crm-009-live-upsert-gate"
    assert policy["liveWritesEnabled"] is False
    assert policy["decision"] == "defer_live_execution"
    assert "live_writes_disabled_by_policy" in policy["blockingReasons"]
    assert (
        "module_required_for_module_specific_scope_check" in policy["blockingReasons"]
    )
    assert policy["scopeGate"]["acceptedAny"] == ["ZohoCRM.modules.ALL"]


def test_crm_upsert_live_gate_policy_matches_module_scope() -> None:
    policy = crm.crm_upsert_live_gate_policy(
        module_api_name="Leads",
        granted_scopes=["ZohoCRM.modules.Leads.WRITE"],
        auth_checked=True,
    )

    assert policy["module"] == "Leads"
    assert policy["scopeGate"]["hasAcceptedScope"] is True
    assert policy["scopeGate"]["matchingScopes"] == ["ZohoCRM.modules.Leads.WRITE"]
    assert "live_oauth_not_checked" not in policy["blockingReasons"]
    assert "upsert_scope_not_verified" not in policy["blockingReasons"]
    assert "audit_persistence_not_implemented" in policy["blockingReasons"]


def test_build_crm_write_audit_event_redacts_upsert_values() -> None:
    plan = crm.build_crm_upsert_dry_run(
        module_api_name="Leads",
        payload={"Last_Name": "Wang", "Email": "wang@example.com"},
        duplicate_check_fields=["Email"],
        idempotency_key="job-123",
    )

    event = crm.build_crm_write_audit_event(
        payload=plan,
        event_type="crm.write.plan",
        account="ops@example.com",
        source_command="zoho crm upsert",
        created_at="2026-05-05T11:10:00Z",
    )
    encoded = json.dumps(event, ensure_ascii=False)

    assert event["eventVersion"] == crm.CRM_WRITE_AUDIT_EVENT_VERSION
    assert event["eventType"] == "crm.write.plan"
    assert event["account"] == "ops@example.com"
    assert event["rawFieldValuesStored"] is False
    assert event["fieldNames"] == ["Last_Name", "Email"]
    assert event["payloadDigest"].startswith("sha256:")
    assert event["eventDigest"].startswith("sha256:")
    assert event["eventId"].startswith("crm-write-")
    assert "Wang" not in encoded
    assert "wang@example.com" not in encoded


def test_append_and_read_crm_write_audit_events(tmp_path: Path) -> None:
    audit_path = tmp_path / "crm_audit.jsonl"
    first = crm.build_crm_write_audit_event(
        payload=crm.crm_upsert_live_gate_policy(module_api_name="Leads"),
        event_type="crm.write.gate",
        source_command="zoho crm upsert-gate",
        created_at="2026-05-05T11:11:00Z",
    )
    second = crm.build_crm_write_audit_event(
        payload=crm.crm_upsert_live_gate_policy(module_api_name="Contacts"),
        event_type="crm.write.gate",
        source_command="zoho crm upsert-gate",
        created_at="2026-05-05T11:12:00Z",
    )

    meta = crm.append_crm_write_audit_event(audit_path, first)
    crm.append_crm_write_audit_event(audit_path, second)

    assert meta["status"] == "persisted"
    assert meta["path"] == str(audit_path)
    assert audit_path.stat().st_mode & 0o777 == 0o600
    events = crm.read_crm_write_audit_events(
        audit_path,
        limit=1,
        module="Contacts",
        event_type="crm.write.gate",
    )
    assert events == [second]


def test_crm_controlled_live_fixture_policy_requires_audit_evidence() -> None:
    policy = crm.crm_controlled_live_fixture_policy(module_api_name="Leads")

    assert policy["policyId"] == "crm-011-controlled-live-fixture-gate"
    assert policy["liveWritesEnabled"] is False
    assert policy["decision"] == "defer_controlled_live_fixture"
    assert policy["auditEvidence"]["hasDryRunPlan"] is False
    assert "dry_run_audit_evidence_missing" in policy["blockingReasons"]
    assert "idempotency_key_required" in policy["blockingReasons"]


def test_crm_controlled_live_fixture_policy_matches_audit_evidence() -> None:
    plan = crm.build_crm_upsert_dry_run(
        module_api_name="Leads",
        payload={"Last_Name": "Wang", "Email": "wang@example.com"},
        duplicate_check_fields=["Email"],
        idempotency_key="fixture-123",
    )
    plan_event = crm.build_crm_write_audit_event(
        payload=plan,
        event_type="crm.write.plan",
        created_at="2026-05-05T11:20:00Z",
    )
    gate = crm.crm_upsert_live_gate_policy(
        module_api_name="Leads",
        granted_scopes=["ZohoCRM.modules.Leads.WRITE"],
        auth_checked=True,
    )
    gate_event = crm.build_crm_write_audit_event(
        payload=gate,
        event_type="crm.write.gate",
        created_at="2026-05-05T11:21:00Z",
    )

    policy = crm.crm_controlled_live_fixture_policy(
        module_api_name="Leads",
        duplicate_check_fields=["Email"],
        idempotency_key="fixture-123",
        payload_digest=plan["payloadDigest"],
        audit_events=[plan_event, gate_event],
    )

    assert policy["auditEvidence"]["hasDryRunPlan"] is True
    assert policy["auditEvidence"]["hasGate"] is True
    assert policy["auditEvidence"]["hasScopeEvidence"] is True
    assert "dry_run_audit_evidence_missing" not in policy["blockingReasons"]
    assert "upsert_gate_audit_evidence_missing" not in policy["blockingReasons"]
    assert "upsert_scope_evidence_missing" not in policy["blockingReasons"]
    assert (
        "controlled_live_fixture_execution_not_implemented" in policy["blockingReasons"]
    )


def _build_crm_fixture_audit_events() -> tuple[dict, list[dict]]:
    plan = crm.build_crm_upsert_dry_run(
        module_api_name="Leads",
        payload={"Last_Name": "Wang", "Email": "wang@example.com"},
        duplicate_check_fields=["Email"],
        idempotency_key="fixture-123",
    )
    plan_event = crm.build_crm_write_audit_event(
        payload=plan,
        event_type="crm.write.plan",
        created_at="2026-05-05T11:30:00Z",
    )
    gate = crm.crm_upsert_live_gate_policy(
        module_api_name="Leads",
        granted_scopes=["ZohoCRM.modules.Leads.WRITE"],
        auth_checked=True,
    )
    gate_event = crm.build_crm_write_audit_event(
        payload=gate,
        event_type="crm.write.gate",
        created_at="2026-05-05T11:31:00Z",
    )
    fixture_plan = crm.crm_controlled_live_fixture_policy(
        module_api_name="Leads",
        duplicate_check_fields=["Email"],
        idempotency_key="fixture-123",
        payload_digest=plan["payloadDigest"],
        audit_events=[plan_event, gate_event],
    )
    fixture_plan_event = crm.build_crm_write_audit_event(
        payload=fixture_plan,
        event_type="crm.write.fixture_plan",
        created_at="2026-05-05T11:32:00Z",
    )
    return plan, [plan_event, gate_event, fixture_plan_event]


def test_crm_guarded_fixture_execution_policy_requires_fixture_plan() -> None:
    plan, events = _build_crm_fixture_audit_events()
    approval = crm.crm_fixture_approval_token(
        module_api_name="Leads",
        payload_digest=plan["payloadDigest"],
        idempotency_key="fixture-123",
    )

    policy = crm.crm_guarded_fixture_execution_policy(
        module_api_name="Leads",
        duplicate_check_fields=["Email"],
        idempotency_key="fixture-123",
        payload_digest=plan["payloadDigest"],
        fixture_approval=approval,
        cleanup_plan="remove or update fixture record after validation",
        audit_events=events[:2],
        execute=True,
        env_allows_live_fixture=True,
        record_count=1,
        field_names=plan["fieldNames"],
    )

    assert policy["policyId"] == "crm-012-guarded-fixture-execution-harness"
    assert policy["liveWritesEnabled"] is False
    assert "fixture_plan_audit_evidence_missing" in policy["blockingReasons"]
    assert "operator_fixture_approval_mismatch" not in policy["blockingReasons"]


def test_crm_guarded_fixture_execution_policy_allows_exact_fixture() -> None:
    plan, events = _build_crm_fixture_audit_events()
    approval = crm.crm_fixture_approval_token(
        module_api_name="Leads",
        payload_digest=plan["payloadDigest"],
        idempotency_key="fixture-123",
    )

    policy = crm.crm_guarded_fixture_execution_policy(
        module_api_name="Leads",
        duplicate_check_fields=["Email"],
        idempotency_key="fixture-123",
        payload_digest=plan["payloadDigest"],
        fixture_approval=approval,
        cleanup_plan="remove or update fixture record after validation",
        audit_events=events,
        execute=True,
        env_allows_live_fixture=True,
        record_count=1,
        field_names=plan["fieldNames"],
    )

    assert policy["decision"] == "allow_controlled_live_fixture_execution"
    assert policy["liveWritesEnabled"] is True
    assert policy["controlledLiveFixtureEnabled"] is True
    assert policy["blockingReasons"] == []
    assert policy["fixtureApproval"]["matches"] is True
    assert policy["cleanupPlan"]["descriptionStored"] is False


def _crm_fixture_smoke_summary(plan: dict, *, execute_requested: bool = False) -> dict:
    reports = {
        "upsertPlan": "/tmp/upsert.json",
        "upsertGate": "/tmp/gate.json",
        "fixturePlan": "/tmp/fixture-plan.json",
        "fixtureExecutePlan": "/tmp/fixture-execute-plan.json",
        "auditSummary": "/tmp/audit-summary.json",
    }
    if execute_requested:
        reports["fixtureExecuteResult"] = "/tmp/fixture-execute-result.json"

    return {
        "summaryVersion": 1,
        "runId": "fixture-run-123",
        "module": "Leads",
        "duplicateField": "Email",
        "idempotencyKey": "fixture-123",
        "payloadDigest": plan["payloadDigest"],
        "requiredApproval": crm.crm_fixture_approval_token(
            module_api_name="Leads",
            payload_digest=plan["payloadDigest"],
            idempotency_key="fixture-123",
        ),
        "auditFile": "/tmp/crm_audit.jsonl",
        "executeRequested": execute_requested,
        "liveResultRecorded": execute_requested,
        "reports": reports,
        "redactionContract": {
            "rawFieldValuesStored": False,
            "rawApprovalStored": False,
            "rawCleanupPlanStored": False,
            "rawApiResponseStored": False,
        },
    }


def test_crm_operator_fixture_evidence_status_ready_for_operator_live() -> None:
    plan, events = _build_crm_fixture_audit_events()
    attempt = crm.crm_guarded_fixture_execution_policy(
        module_api_name="Leads",
        duplicate_check_fields=["Email"],
        idempotency_key="fixture-123",
        payload_digest=plan["payloadDigest"],
        cleanup_plan="remove or update fixture record after validation",
        audit_events=events,
        execute=False,
        env_allows_live_fixture=False,
        record_count=1,
        field_names=plan["fieldNames"],
    )
    attempt_event = crm.build_crm_write_audit_event(
        payload=attempt,
        event_type="crm.write.fixture_attempt",
        created_at="2026-05-05T12:00:00Z",
    )
    summary = _crm_fixture_smoke_summary(plan)

    evidence = crm.crm_operator_fixture_evidence_status(
        summary=summary,
        audit_events=[*events, attempt_event],
        report_files_present={key: True for key in summary["reports"]},
    )

    assert evidence["policyId"] == "crm-014-operator-fixture-evidence"
    assert evidence["status"] == "ready_for_operator_live_fixture"
    assert evidence["decision"] == "await_operator_live_fixture"
    assert evidence["operatorReadiness"]["readyForLiveFixture"] is True
    assert evidence["releaseEvidenceReady"] is False
    assert evidence["blockingReasons"] == ["live_fixture_not_recorded"]
    assert evidence["redaction"]["ok"] is True


def test_crm_operator_fixture_evidence_status_records_live_result() -> None:
    plan, events = _build_crm_fixture_audit_events()
    approval = crm.crm_fixture_approval_token(
        module_api_name="Leads",
        payload_digest=plan["payloadDigest"],
        idempotency_key="fixture-123",
    )
    result_payload = crm.crm_guarded_fixture_execution_policy(
        module_api_name="Leads",
        duplicate_check_fields=["Email"],
        idempotency_key="fixture-123",
        payload_digest=plan["payloadDigest"],
        fixture_approval=approval,
        cleanup_plan="remove or update fixture record after validation",
        audit_events=events,
        execute=True,
        env_allows_live_fixture=True,
        record_count=1,
        field_names=plan["fieldNames"],
    )
    result_payload["execution"]["networkWriteAttempted"] = True
    result_payload["status"] = "succeeded"
    result_payload["responseSummary"] = {
        "httpStatus": 201,
        "isSuccess": True,
        "recordCount": 1,
        "recordIds": ["4150868000003194003"],
        "records": [],
        "rawResponseStored": False,
    }
    result_event = crm.build_crm_write_audit_event(
        payload=result_payload,
        event_type="crm.write.fixture_result",
        created_at="2026-05-05T12:01:00Z",
    )
    summary = _crm_fixture_smoke_summary(plan, execute_requested=True)

    evidence = crm.crm_operator_fixture_evidence_status(
        summary=summary,
        audit_events=[*events, result_event],
        report_files_present={key: True for key in summary["reports"]},
    )

    assert evidence["status"] == "live_fixture_recorded"
    assert evidence["decision"] == "operator_fixture_evidence_recorded"
    assert evidence["liveResultRecorded"] is True
    assert evidence["releaseEvidenceReady"] is True
    assert evidence["blockingReasons"] == []


def test_summarize_crm_upsert_response_redacts_user_names() -> None:
    summary = crm.summarize_crm_upsert_response(
        {
            "data": [
                {
                    "code": "SUCCESS",
                    "duplicate_field": "Email",
                    "action": "insert",
                    "details": {
                        "id": "4150868000003194003",
                        "Created_By": {"name": "Patricia Boyle"},
                    },
                    "message": "record added",
                    "status": "success",
                }
            ]
        },
        http_status=201,
        is_success=True,
    )
    encoded = json.dumps(summary)

    assert summary["recordIds"] == ["4150868000003194003"]
    assert summary["records"][0]["action"] == "insert"
    assert summary["rawResponseStored"] is False
    assert "Patricia" not in encoded
    assert "record added" not in encoded


@respx.mock
def test_crm_client_modules() -> None:
    client = crm.ZohoCrmClient("fake-token", base_url="https://www.zohoapis.com/crm/v2")
    route = respx.get("https://www.zohoapis.com/crm/v2/settings/modules").mock(
        return_value=httpx.Response(200, json={"data": [{"api_name": "Leads"}]})
    )

    result = client.modules(limit=7, page=2)

    assert result["data"][0]["api_name"] == "Leads"
    assert dict(route.calls.last.request.url.params) == {"per_page": "7", "page": "2"}


@respx.mock
def test_crm_client_users() -> None:
    client = crm.ZohoCrmClient("fake-token", base_url="https://www.zohoapis.com/crm/v8")
    route = respx.get("https://www.zohoapis.com/crm/v8/users").mock(
        return_value=httpx.Response(200, json={"users": [{"id": "u1"}]})
    )

    result = client.users(user_type="ActiveUsers", limit=10, page=2)

    assert result["users"][0]["id"] == "u1"
    assert dict(route.calls.last.request.url.params) == {
        "per_page": "10",
        "page": "2",
        "type": "ActiveUsers",
    }


@respx.mock
def test_crm_client_get_user() -> None:
    client = crm.ZohoCrmClient("fake-token", base_url="https://www.zohoapis.com/crm/v8")
    respx.get("https://www.zohoapis.com/crm/v8/users/u1").mock(
        return_value=httpx.Response(200, json={"users": [{"id": "u1"}]})
    )

    result = client.get_user("u1")

    assert result["users"][0]["id"] == "u1"


@respx.mock
def test_crm_client_org() -> None:
    client = crm.ZohoCrmClient("fake-token", base_url="https://www.zohoapis.com/crm/v8")
    respx.get("https://www.zohoapis.com/crm/v8/org").mock(
        return_value=httpx.Response(200, json={"org": [{"company_name": "Acme"}]})
    )

    result = client.org()

    assert result["org"][0]["company_name"] == "Acme"


@respx.mock
def test_crm_client_profiles() -> None:
    client = crm.ZohoCrmClient("fake-token", base_url="https://www.zohoapis.com/crm/v8")
    route = respx.get("https://www.zohoapis.com/crm/v8/settings/profiles").mock(
        return_value=httpx.Response(200, json={"profiles": [{"id": "p1"}]})
    )

    result = client.profiles(limit=5, page=2)

    assert result["profiles"][0]["id"] == "p1"
    assert dict(route.calls.last.request.url.params) == {"per_page": "5", "page": "2"}


@respx.mock
def test_crm_client_roles() -> None:
    client = crm.ZohoCrmClient("fake-token", base_url="https://www.zohoapis.com/crm/v8")
    route = respx.get("https://www.zohoapis.com/crm/v8/settings/roles").mock(
        return_value=httpx.Response(200, json={"roles": [{"id": "r1"}]})
    )

    result = client.roles(limit=6, page=3)

    assert result["roles"][0]["id"] == "r1"
    assert dict(route.calls.last.request.url.params) == {"per_page": "6", "page": "3"}


@respx.mock
def test_crm_client_layouts() -> None:
    client = crm.ZohoCrmClient("fake-token", base_url="https://www.zohoapis.com/crm/v8")
    route = respx.get("https://www.zohoapis.com/crm/v8/settings/layouts").mock(
        return_value=httpx.Response(200, json={"layouts": [{"api_name": "Standard"}]})
    )

    result = client.layouts("Accounts", limit=7, page=4)

    assert result["layouts"][0]["api_name"] == "Standard"
    assert dict(route.calls.last.request.url.params) == {
        "module": "Accounts",
        "per_page": "7",
        "page": "4",
    }


@respx.mock
def test_crm_client_coql() -> None:
    client = crm.ZohoCrmClient("fake-token", base_url="https://www.zohoapis.com/crm/v8")
    route = respx.post("https://www.zohoapis.com/crm/v8/coql").mock(
        return_value=httpx.Response(200, json={"data": [{"Last_Name": "Wang"}]})
    )

    result = client.coql("select Last_Name from Leads limit 1")

    assert result["data"][0]["Last_Name"] == "Wang"
    assert json.loads(route.calls.last.request.content.decode()) == {
        "select_query": "select Last_Name from Leads limit 1"
    }


@respx.mock
def test_crm_client_automation_resource() -> None:
    client = crm.ZohoCrmClient("fake-token", base_url="https://www.zohoapis.com/crm/v8")
    route = respx.get(
        "https://www.zohoapis.com/crm/v8/settings/automation/workflow_rules"
    ).mock(return_value=httpx.Response(200, json={"workflow_rules": [{"id": "w1"}]}))

    result = client.automation_resource(
        "workflow_rules", module="Accounts", status="active", limit=8, page=2
    )

    assert result["workflow_rules"][0]["id"] == "w1"
    assert dict(route.calls.last.request.url.params) == {
        "per_page": "8",
        "page": "2",
        "module": "Accounts",
        "status": "active",
    }


@respx.mock
def test_crm_client_settings_resource_related_lists() -> None:
    client = crm.ZohoCrmClient("fake-token", base_url="https://www.zohoapis.com/crm/v8")
    route = respx.get("https://www.zohoapis.com/crm/v8/settings/related_lists").mock(
        return_value=httpx.Response(
            200, json={"related_lists": [{"api_name": "Contacts"}]}
        )
    )

    result = client.settings_resource(
        "related_lists", module="Accounts", layout_id="layout-1"
    )

    assert result["related_lists"][0]["api_name"] == "Contacts"
    assert dict(route.calls.last.request.url.params) == {
        "module": "Accounts",
        "layout_id": "layout-1",
    }


@respx.mock
def test_crm_client_settings_resource_custom_views() -> None:
    client = crm.ZohoCrmClient("fake-token", base_url="https://www.zohoapis.com/crm/v8")
    route = respx.get("https://www.zohoapis.com/crm/v8/settings/custom_views").mock(
        return_value=httpx.Response(200, json={"custom_views": [{"id": "cv1"}]})
    )

    result = client.settings_resource(
        "custom_views", module="Accounts", limit=9, page=2
    )

    assert result["custom_views"][0]["id"] == "cv1"
    assert dict(route.calls.last.request.url.params) == {
        "module": "Accounts",
        "per_page": "9",
        "page": "2",
    }


@respx.mock
def test_crm_client_settings_resource_custom_view_detail() -> None:
    client = crm.ZohoCrmClient("fake-token", base_url="https://www.zohoapis.com/crm/v8")
    route = respx.get("https://www.zohoapis.com/crm/v8/settings/custom_views/cv1").mock(
        return_value=httpx.Response(200, json={"custom_views": [{"id": "cv1"}]})
    )

    result = client.settings_resource(
        "custom_views", module="Accounts", custom_view_id="cv1", limit=9, page=2
    )

    assert result["custom_views"][0]["id"] == "cv1"
    assert dict(route.calls.last.request.url.params) == {
        "module": "Accounts",
        "per_page": "9",
        "page": "2",
    }


def test_build_storepilot_seed_diff_reports_missing_modules_fields_and_counts() -> None:
    snapshot = {
        "kind": crm.STOREPILOT_SNAPSHOT_KIND,
        "modules": [{"api_name": "Accounts"}],
        "fields": {
            "Accounts": [
                {"api_name": "google_place_id", "data_type": "text"},
                {"api_name": "geo_lat", "data_type": "integer"},
            ]
        },
    }
    crm_modules_seed = {
        "version": "0.1.0",
        "standard_modules": [
            {
                "api_name": "Accounts",
                "business_name": "Stores",
                "fields": [
                    {"api_name": "google_place_id", "type": "text"},
                    {"api_name": "geo_lat", "type": "decimal"},
                    {"api_name": "geo_lng", "type": "decimal"},
                ],
            }
        ],
        "custom_modules": [
            {
                "api_name": "Regions",
                "plural_label": "Regions",
                "fields": [{"api_name": "region_code", "type": "text"}],
            }
        ],
    }

    result = crm.build_storepilot_seed_diff(
        snapshot=snapshot,
        crm_modules_seed=crm_modules_seed,
        task_templates_seed={"templates": [{}, {}]},
        budget_rules_seed={"rules": [{}]},
        regions_seed={"regions": [{}, {}, {}]},
    )

    assert result["status"] == "dry_run"
    assert result["liveWritesEnabled"] is False
    assert result["summary"]["modulesToCreate"] == 1
    assert result["summary"]["fieldsToCreate"] == 2
    assert result["summary"]["fieldsWithTypeConflicts"] == 1
    assert result["summary"]["fieldsWithPropertyGaps"] == 0
    assert result["summary"]["fieldMappingContracts"] == 4
    assert result["summary"]["unknownFieldTypeMappings"] == 0
    assert result["readiness"]["blockingReasons"] == ["field_type_conflicts"]
    assert result["records_to_upsert"] == {
        "Regions": 3,
        "Task_Templates": 2,
        "Budget_Rules": 1,
    }
    assert result["modules_to_create"][0]["apiName"] == "Regions"
    geo_lng = next(
        field for field in result["fields_to_create"] if field["apiName"] == "geo_lng"
    )
    assert geo_lng["zohoType"] == "decimal"
    assert geo_lng["typeMappingStatus"] == "mapped"
    assert geo_lng["picklistValuesCount"] == 0


def test_storepilot_seed_diff_reports_field_property_gaps() -> None:
    snapshot = {
        "kind": crm.STOREPILOT_SNAPSHOT_KIND,
        "modules": [{"api_name": "Accounts"}],
        "fields": {
            "Accounts": [
                {
                    "api_name": "store_type",
                    "data_type": "picklist",
                    "pick_list_values": [{"actual_value": "vape_shop"}],
                },
                {
                    "api_name": "region",
                    "data_type": "lookup",
                    "lookup": {"module": {"api_name": "Legacy_Regions"}},
                },
                {"api_name": "google_place_id", "data_type": "text"},
                {"api_name": "notes", "data_type": "textarea"},
            ]
        },
    }
    crm_modules_seed = {
        "standard_modules": [
            {
                "api_name": "Accounts",
                "fields": [
                    {
                        "api_name": "store_type",
                        "type": "picklist",
                        "values": ["vape_shop", "smoke_shop"],
                    },
                    {"api_name": "region", "type": "lookup", "module": "Regions"},
                    {
                        "api_name": "google_place_id",
                        "type": "text",
                        "unique": True,
                        "external": True,
                    },
                    {"api_name": "notes", "type": "multiline"},
                ],
            }
        ],
        "custom_modules": [],
    }

    result = crm.build_storepilot_seed_diff(
        snapshot=snapshot,
        crm_modules_seed=crm_modules_seed,
    )

    assert result["summary"]["fieldsWithPropertyGaps"] == 4
    assert result["summary"]["unknownFieldTypeMappings"] == 0
    assert "field_property_gaps" in result["readiness"]["blockingReasons"]
    assert {
        (gap["apiName"], gap["property"]) for gap in result["fields_with_property_gaps"]
    } == {
        ("store_type", "picklistValues"),
        ("region", "lookupModule"),
        ("google_place_id", "unique"),
        ("google_place_id", "external"),
    }
    notes_mapping = next(
        field
        for field in result["field_mapping_contracts"]
        if field["apiName"] == "notes"
    )
    assert notes_mapping["seedType"] == "textarea"
    assert notes_mapping["zohoType"] == "textarea"


def test_build_storepilot_snapshot_summary_reports_coverage() -> None:
    snapshot = {
        "kind": crm.STOREPILOT_SNAPSHOT_KIND,
        "selectedModules": ["Accounts", "Regions"],
        "org": [{"id": "870137630"}],
        "users": [{"id": "u1"}],
        "profiles": [{"id": "p1"}],
        "roles": [{"id": "r1"}],
        "modules": [{"api_name": "Accounts"}],
        "fields": {
            "Accounts": [{"api_name": "Name"}],
            "Regions": [{"api_name": "region_code"}],
        },
        "layouts": {"Accounts": [{"id": "l1"}]},
        "automation": {
            "workflow_rules": [{"id": "w1"}],
            "webhooks": [{"id": "wh1"}, {"id": "wh2"}],
        },
        "settingsMetadata": {
            "related_lists": {
                "Accounts": [{"api_name": "Contacts"}],
                "Regions": [{"api_name": "Accounts"}],
            },
            "custom_views": {
                "Accounts": [{"id": "cv1"}, {"id": "cv2"}],
            },
        },
    }

    summary = crm.build_storepilot_snapshot_summary(snapshot)

    assert summary["selectedModules"] == 2
    assert summary["fields"] == 2
    assert summary["automationItems"] == 3
    assert summary["settingsItems"] == 4
    assert summary["coverage"]["hasOrg"] is True
    assert summary["coverage"]["hasFieldsForAllSelectedModules"] is True
    assert summary["coverage"]["hasLayoutsForAllSelectedModules"] is False
    assert summary["coverage"]["missingLayoutModules"] == ["Regions"]
    assert summary["coverage"]["automationCounts"] == {
        "workflow_rules": 1,
        "webhooks": 2,
    }
    assert summary["coverage"]["settingsCounts"] == {
        "related_lists": 2,
        "custom_views": 2,
    }
    assert summary["coverage"]["settingsModuleCounts"] == {
        "related_lists": 2,
        "custom_views": 1,
    }
    assert "Blueprints" in summary["manualReviewSurfaces"]


def test_build_storepilot_manual_setup_plan_reports_seed_relationships() -> None:
    crm_modules_seed = {
        "manual_setup_required": ["Review related lists manually."],
        "relationships": [
            {
                "from": "Field_Tasks",
                "to": "Accounts",
                "type": "many_to_one",
                "field": "account",
            }
        ],
    }
    snapshot = {
        "selectedModules": ["Accounts"],
        "org": [{"id": "870137630"}],
        "layouts": {},
    }
    notification_plan = {
        "summary": {"callbackConfigured": False},
        "manual_steps_required": [{"code": "callback_url_required"}],
    }
    cleanup_plan = {"summary": {"legacyAutomationToReview": 2}}

    plan = crm.build_storepilot_manual_setup_plan(
        crm_modules_seed=crm_modules_seed,
        snapshot=snapshot,
        notification_plan=notification_plan,
        cleanup_plan=cleanup_plan,
    )

    assert plan["kind"] == crm.STOREPILOT_MANUAL_SETUP_PLAN_KIND
    assert plan["liveWritesEnabled"] is False
    assert plan["summary"]["seedManualSteps"] == 1
    assert plan["summary"]["relationships"] == 1
    assert plan["summary"]["manualReviewRequired"] >= 4
    assert plan["relationship_checks"][0]["field"] == "account"
    assert {
        check["code"]
        for check in plan["checks"]
        if check["status"] == "manual_review_required"
    } >= {
        "relationship_related_list_review_required",
        "layout_coverage_review",
        "automation_cleanup_review",
        "notification_setup_review",
    }


def test_storepilot_seed_diff_reports_org_mismatch_and_unknown_type() -> None:
    snapshot = {
        "kind": crm.STOREPILOT_SNAPSHOT_KIND,
        "org": [{"id": "wrong-org"}],
        "modules": [{"api_name": "Accounts"}],
        "fields": {"Accounts": []},
    }
    crm_modules_seed = {
        "standard_modules": [
            {
                "api_name": "Accounts",
                "fields": [{"api_name": "mystery", "type": "magic"}],
            }
        ],
        "custom_modules": [],
    }

    result = crm.build_storepilot_seed_diff(
        snapshot=snapshot,
        crm_modules_seed=crm_modules_seed,
        expected_org_id="870137630",
    )

    assert result["orgVerification"]["matches"] is False
    assert result["readiness"]["readyForApplyPlan"] is False
    assert "org_id_mismatch" in result["readiness"]["blockingReasons"]
    assert "unknown_field_type_mapping" in result["readiness"]["blockingReasons"]
    assert result["fields_to_create"][0]["typeMappingStatus"] == "unknown"


def test_build_storepilot_bulk_plan_counts_seed_records_and_exports() -> None:
    result = crm.build_storepilot_bulk_plan(
        task_templates_seed={"templates": [{}, {}]},
        budget_rules_seed={"rules": [{}]},
        regions_seed={"regions": [{}, {}, {}]},
        export_modules=["Accounts", "Accounts", "Contacts"],
        batch_size=2,
    )

    assert result["kind"] == crm.STOREPILOT_BULK_PLAN_KIND
    assert result["liveWritesEnabled"] is False
    assert result["summary"]["importRecords"] == 6
    assert result["imports"][0]["module"] == "Regions"
    assert result["imports"][0]["batchCount"] == 2
    assert [item["module"] for item in result["exports"]] == ["Accounts", "Contacts"]
    assert "bulk_import_requires_guarded_apply" in {
        step["code"] for step in result["manual_steps_required"]
    }


def test_build_storepilot_notification_plan_defaults_and_callback() -> None:
    result = crm.build_storepilot_notification_plan(
        callback_url="https://storepilot.example.com/webhooks/zoho",
        shared_secret_env="ZOHO_WEBHOOK_SECRET",
    )

    assert result["kind"] == crm.STOREPILOT_NOTIFICATION_PLAN_KIND
    assert result["liveWritesEnabled"] is False
    assert result["summary"]["modules"] >= 10
    assert result["summary"]["callbackHost"] == "storepilot.example.com"
    assert result["subscriptions"][0]["events"] == ["create", "edit", "delete"]
    assert result["subscriptions"][0]["sharedSecretEnv"] == "ZOHO_WEBHOOK_SECRET"
    assert "shared_secret_required" in {
        step["code"] for step in result["manual_steps_required"]
    }


def test_build_storepilot_cleanup_and_init_plan() -> None:
    snapshot = {
        "kind": crm.STOREPILOT_SNAPSHOT_KIND,
        "org": [{"id": "870137630"}],
        "modules": [
            {"api_name": "Accounts", "module_name": "Accounts"},
            {"api_name": "Legacy_Module", "module_name": "Legacy"},
        ],
        "fields": {
            "Accounts": [
                {"api_name": "google_place_id", "type": "text"},
                {"api_name": "Legacy_Field", "type": "text", "custom_field": True},
                {
                    "api_name": "Created_Time",
                    "type": "datetime",
                    "system_mandatory": True,
                },
            ]
        },
        "automation": {
            "workflow_rules": [
                {
                    "id": "workflow-1",
                    "name": "Legacy workflow",
                    "module": {"api_name": "Accounts"},
                }
            ],
            "webhooks": [{"id": "webhook-1", "name": "Legacy webhook"}],
        },
    }
    crm_modules_seed = {
        "version": "0.1.0",
        "standard_modules": [
            {
                "api_name": "Accounts",
                "fields": [{"api_name": "google_place_id", "type": "text"}],
            }
        ],
        "custom_modules": [],
    }

    cleanup = crm.build_storepilot_cleanup_plan(
        snapshot=snapshot, crm_modules_seed=crm_modules_seed
    )
    assert cleanup["summary"]["legacyModulesToReview"] == 1
    assert cleanup["summary"]["legacyFieldsToReview"] == 1
    assert cleanup["summary"]["legacyAutomationToReview"] == 2
    assert cleanup["summary"]["protectedFieldsSkipped"] == 1
    assert cleanup["legacy_automation_to_review"][0]["resource"] == "workflow_rules"
    assert cleanup["zoho_only_manual_steps"][0]["code"] == "blueprint_review_required"

    plan = crm.build_storepilot_init_plan(
        snapshot=snapshot,
        crm_modules_seed=crm_modules_seed,
        task_templates_seed={"templates": [{}]},
        regions_seed={"regions": [{}, {}]},
        expected_org_id="870137630",
        callback_url="https://storepilot.example.com/webhooks/zoho",
        export_modules=["Accounts"],
        include_cleanup=True,
    )
    assert plan["kind"] == crm.STOREPILOT_INIT_PLAN_KIND
    assert plan["liveWritesEnabled"] is False
    assert plan["summary"]["recordsToUpsert"] == 3
    assert plan["summary"]["cleanupReviewItems"] == 4
    assert plan["summary"]["manualSetupChecks"] >= 5
    assert plan["summary"]["manualSetupReviews"] >= 1
    assert "cleanup_review_required" in plan["readiness"]["blockingReasons"]
    assert "manual_setup_review_required" in plan["readiness"]["blockingReasons"]
    assert plan["cleanupPlan"]["summary"]["legacyModulesToReview"] == 1
    assert plan["manualSetupPlan"]["kind"] == crm.STOREPILOT_MANUAL_SETUP_PLAN_KIND

    apply_plan = crm.build_storepilot_apply_plan(
        init_plan=plan,
        mode="apply_production",
        expected_org_id="870137630",
    )
    assert apply_plan["kind"] == crm.STOREPILOT_APPLY_PLAN_KIND
    assert apply_plan["liveWritesEnabled"] is False
    assert apply_plan["executionBlocked"] is True
    assert apply_plan["approval"]["required"] is True
    assert (
        "exact_operator_approval_required" in apply_plan["readiness"]["blockingReasons"]
    )
    assert "cleanup_review_required" in apply_plan["readiness"]["blockingReasons"]
    assert apply_plan["plannedOperations"]["recordsToUpsert"] == 3
    assert apply_plan["plannedOperations"]["notificationSubscriptions"] == 19
    assert apply_plan["phases"][0]["writesZohoData"] is False


def test_build_storepilot_apply_plan_rejects_non_init_plan() -> None:
    with pytest.raises(ValueError, match="init_plan"):
        crm.build_storepilot_apply_plan(init_plan={"kind": "other"})


@respx.mock
def test_crm_client_fields() -> None:
    client = crm.ZohoCrmClient("fake-token", base_url="https://www.zohoapis.com/crm/v2")
    route = respx.get("https://www.zohoapis.com/crm/v2/settings/fields").mock(
        return_value=httpx.Response(200, json={"data": [{"api_name": "Company"}]})
    )

    result = client.fields("Leads", limit=10, page=3)

    assert result["data"][0]["api_name"] == "Company"
    assert dict(route.calls.last.request.url.params) == {
        "module": "Leads",
        "per_page": "10",
        "page": "3",
    }


@respx.mock
def test_crm_client_list_records() -> None:
    client = crm.ZohoCrmClient("fake-token", base_url="https://www.zohoapis.com/crm/v2")
    route = respx.get("https://www.zohoapis.com/crm/v2/Leads").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "1001"}]})
    )

    result = client.list_records(
        "Leads", limit=2, page=4, fields=["Last_Name", "Email"]
    )

    assert result["data"][0]["id"] == "1001"
    assert dict(route.calls.last.request.url.params) == {
        "per_page": "2",
        "page": "4",
        "fields": "Last_Name,Email",
    }


@respx.mock
def test_crm_client_get_record() -> None:
    client = crm.ZohoCrmClient("fake-token", base_url="https://www.zohoapis.com/crm/v2")
    route = respx.get("https://www.zohoapis.com/crm/v2/Leads/1001").mock(
        return_value=httpx.Response(
            200, json={"data": [{"id": "1001", "Last_Name": "Wang"}]}
        )
    )

    result = client.get_record("Leads", "1001", fields=["Last_Name"])

    assert result["data"][0]["Last_Name"] == "Wang"
    assert dict(route.calls.last.request.url.params) == {"fields": "Last_Name"}


@respx.mock
def test_crm_client_search_records_by_criteria() -> None:
    client = crm.ZohoCrmClient("fake-token", base_url="https://www.zohoapis.com/crm/v2")
    route = respx.get("https://www.zohoapis.com/crm/v2/Leads/search").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "1002"}]})
    )

    result = client.search_records(
        "Leads", criteria="(Last_Name:equals:Wang)", limit=3, page=2
    )

    assert result["data"][0]["id"] == "1002"
    assert dict(route.calls.last.request.url.params) == {
        "per_page": "3",
        "page": "2",
        "criteria": "(Last_Name:equals:Wang)",
    }


@respx.mock
def test_crm_client_search_records_by_word() -> None:
    client = crm.ZohoCrmClient("fake-token", base_url="https://www.zohoapis.com/crm/v2")
    route = respx.get("https://www.zohoapis.com/crm/v2/Leads/search").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "1003"}]})
    )

    result = client.search_records("Leads", word="acme", limit=5, page=1)

    assert result["data"][0]["id"] == "1003"
    assert dict(route.calls.last.request.url.params) == {
        "per_page": "5",
        "page": "1",
        "word": "acme",
    }
