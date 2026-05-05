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
