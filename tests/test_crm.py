"""Tests for zoho_cli.crm helpers."""

from importlib import metadata

import httpx
import respx

from zoho_cli import crm


def test_infer_crm_base_url_from_mail_host() -> None:
    url = crm.infer_crm_base_url(mail_base_url="https://mail.zoho.eu/api")
    assert url == "https://www.zohoapis.eu/crm/v2"


def test_infer_crm_base_url_from_accounts_host() -> None:
    url = crm.infer_crm_base_url(accounts_server="https://accounts.zoho.com")
    assert url == "https://www.zohoapis.com/crm/v2"


def test_infer_crm_base_url_defaults_to_com() -> None:
    url = crm.infer_crm_base_url()
    assert url == "https://www.zohoapis.com/crm/v2"


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


def test_crm_sdk_status_reports_installed_target_version() -> None:
    result = crm.crm_sdk_status(version_lookup=lambda _: "5.0.0")

    assert result["sdk"]["installed"] is True
    assert result["sdk"]["installedVersion"] == "5.0.0"
    assert result["sdk"]["versionMatchesTarget"] is True


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
