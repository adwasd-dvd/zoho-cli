"""Tests for the optional Zoho CRM SDK adapter boundary."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from zoho_cli import crm_sdk


def test_crm_sdk_data_center_infers_from_accounts_hosts() -> None:
    assert (
        crm_sdk.infer_crm_sdk_data_center(accounts_server="https://accounts.zoho.eu")
        == "eu"
    )
    assert (
        crm_sdk.infer_crm_sdk_data_center(
            accounts_server="https://accounts.zohocloud.ca"
        )
        == "ca"
    )
    assert (
        crm_sdk.infer_crm_sdk_data_center(
            accounts_server="https://accounts.zoho.com.au"
        )
        == "au"
    )


def test_crm_sdk_data_center_infers_from_crm_or_mail_hosts() -> None:
    assert (
        crm_sdk.infer_crm_sdk_data_center(crm_base_url="https://www.zohoapis.jp/crm/v8")
        == "jp"
    )
    assert (
        crm_sdk.infer_crm_sdk_data_center(mail_base_url="https://mail.zoho.in/api")
        == "in"
    )
    assert crm_sdk.infer_crm_sdk_data_center() == "us"


def test_crm_sdk_environment_spec_for_account_is_json_safe() -> None:
    spec = crm_sdk.crm_sdk_environment_spec_for_account(
        {"accounts_server": "https://accounts.zoho.sa"}
    )

    assert spec.key == "sa"
    payload = spec.to_dict()
    assert payload["apiDomain"] == "https://www.zohoapis.sa"
    assert payload["accountsTokenUrl"] == "https://accounts.zoho.sa/oauth/v2/token"
    assert payload["sdkClassName"] == "SADataCenter"


def test_crm_sdk_resource_path_uses_cli_managed_account_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(crm_sdk.SDK_RESOURCE_ENV_VAR, str(tmp_path))

    path = crm_sdk.crm_sdk_resource_path(
        account_email="agent/test@example.com",
        create=True,
    )

    assert path == tmp_path / "agent_test_at_example.com"
    assert path.is_dir()
    assert crm_sdk.crm_sdk_token_store_path(path) == path / "tokens.csv"


def test_crm_sdk_initialization_plan_keeps_http_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(crm_sdk.SDK_RESOURCE_ENV_VAR, str(tmp_path))

    plan = crm_sdk.build_crm_sdk_initialization_plan(
        account_cfg={"accounts_server": "https://accounts.zoho.eu"},
        account_email="bot@example.com",
    )

    assert plan["adapter"] == "sdk-v8"
    assert plan["stage"] == "skeleton"
    assert plan["defaultEnabled"] is False
    assert plan["currentCliAdapter"] == "http-v2"
    assert plan["dataCenter"]["key"] == "eu"
    assert plan["resourcePath"].endswith("bot_at_example.com")
    assert plan["tokenStorePath"].endswith("bot_at_example.com/tokens.csv")
    assert plan["preventsSdkCwdDefaults"] is True
    assert "modules" in plan["readOnlyMethods"]
    assert plan["outputShape"]["plainJson"] is True
    assert plan["outputShape"]["preserveCurrentCommands"] is True


def test_load_crm_sdk_bindings_reports_optional_dependency_missing() -> None:
    def missing_import(_: str) -> object:
        raise ModuleNotFoundError("No module named 'zohocrmsdk'", name="zohocrmsdk")

    with pytest.raises(crm_sdk.CrmSdkUnavailableError) as exc:
        crm_sdk.load_crm_sdk_bindings(importer=missing_import)

    assert exc.value.to_dict()["error"] == "sdk_not_installed"


def test_load_crm_sdk_bindings_uses_official_paths() -> None:
    seen: list[str] = []

    class FakeModule:
        def __getattr__(self, name: str) -> object:
            return type(name, (), {})

    def fake_import(path: str) -> object:
        seen.append(path)
        return FakeModule()

    bindings = crm_sdk.load_crm_sdk_bindings(
        data_center_key="eu",
        importer=fake_import,
    )

    assert bindings.environment_spec.key == "eu"
    assert "zohocrmsdk.src.com.zoho.crm.api.dc.eu_data_center" in seen
    assert "zohocrmsdk.src.com.zoho.crm.api.record.record_operations" in seen


def test_normalize_sdk_json_unwraps_sdk_response_shapes() -> None:
    class FakeModel:
        def to_dict(self) -> dict[str, str]:
            return {"id": "1001", "Last_Name": "Wang"}

    class FakeResponse:
        def get_data(self) -> list[FakeModel]:
            return [FakeModel()]

    assert crm_sdk.normalize_sdk_json(FakeResponse()) == {
        "data": [{"id": "1001", "Last_Name": "Wang"}]
    }


def test_sdk_adapter_methods_return_plain_json_with_injected_backend() -> None:
    calls: list[tuple[str, dict]] = []

    class Backend:
        def modules(self, **kwargs: object) -> object:
            calls.append(("modules", kwargs))
            return {"data": [{"api_name": "Leads"}]}

        def fields(self, **kwargs: object) -> object:
            calls.append(("fields", kwargs))
            return {"data": [{"api_name": "Company"}]}

        def list_records(self, **kwargs: object) -> object:
            calls.append(("list_records", kwargs))
            return SimpleNamespace(data=[{"id": "1001"}])

        def get_record(self, **kwargs: object) -> object:
            calls.append(("get_record", kwargs))
            return {"data": [{"id": "1001"}]}

        def search_records(self, **kwargs: object) -> object:
            calls.append(("search_records", kwargs))
            return {"data": [{"id": "1002"}]}

    adapter = crm_sdk.ZohoCrmSdkAdapter(Backend())

    assert adapter.modules(limit=2, page=3)["data"][0]["api_name"] == "Leads"
    assert adapter.fields("Leads")["data"][0]["api_name"] == "Company"
    assert adapter.list_records("Leads", fields=["Email"])["data"][0]["id"] == "1001"
    assert adapter.get_record("Leads", "1001")["data"][0]["id"] == "1001"
    assert adapter.search_records("Leads", word="acme")["data"][0]["id"] == "1002"
    assert calls[0] == ("modules", {"limit": 2, "page": 3})
    assert calls[-1][1]["word"] == "acme"


def test_sdk_adapter_without_backend_reports_not_initialized() -> None:
    adapter = crm_sdk.ZohoCrmSdkAdapter()

    with pytest.raises(crm_sdk.CrmSdkAdapterNotInitialized) as exc:
        adapter.modules()

    assert exc.value.to_dict()["error"] == "sdk_adapter_not_initialized"
