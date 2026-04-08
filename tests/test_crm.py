"""Tests for zoho_cli.crm helpers."""

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


@respx.mock
def test_crm_client_modules() -> None:
    client = crm.ZohoCrmClient("fake-token", base_url="https://www.zohoapis.com/crm/v2")
    route = respx.get("https://www.zohoapis.com/crm/v2/settings/modules").mock(
        return_value=httpx.Response(200, json={"data": [{"api_name": "Leads"}]})
    )

    result = client.modules(limit=7, page=2)

    assert result["data"][0]["api_name"] == "Leads"
    assert dict(route.calls.last.request.url.params) == {"per_page": "7", "page": "2"}
