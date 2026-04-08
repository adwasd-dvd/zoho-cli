"""Tests for zoho_cli.cliq helpers."""

import httpx
import pytest
import respx

from zoho_cli import cliq


def test_infer_cliq_base_url_from_mail_host() -> None:
    url = cliq.infer_cliq_base_url(mail_base_url="https://mail.zoho.eu/api")
    assert url == "https://cliq.zoho.eu/api/v2"


def test_infer_cliq_base_url_from_accounts_host() -> None:
    url = cliq.infer_cliq_base_url(accounts_server="https://accounts.zoho.in")
    assert url == "https://cliq.zoho.in/api/v2"


def test_infer_cliq_base_url_defaults_to_com() -> None:
    url = cliq.infer_cliq_base_url()
    assert url == "https://cliq.zoho.com/api/v2"


def test_infer_cliq_base_url_from_network_slug() -> None:
    url = cliq.infer_cliq_base_url(network="happydistrouklimited")
    assert url == "https://cliq.zoho.com/network/happydistrouklimited/api/v2"


def test_missing_cliq_scopes_reports_missing_values() -> None:
    missing = cliq.missing_cliq_scopes(["ZohoCliq.Channels.READ"])
    assert missing == [
        "ZohoCliq.Users.READ",
        "ZohoCliq.Messages.CREATE",
        "ZohoCliq.Webhooks.CREATE",
    ]


@pytest.fixture
def client() -> cliq.ZohoCliqClient:
    return cliq.ZohoCliqClient("fake-token", base_url="https://cliq.zoho.com/api/v2")


@respx.mock
def test_cliq_client_channels(client: cliq.ZohoCliqClient) -> None:
    route = respx.get("https://cliq.zoho.com/api/v2/channels").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "C1"}]})
    )
    result = client.channels(limit=7)
    assert result["data"][0]["id"] == "C1"
    assert dict(route.calls.last.request.url.params)["limit"] == "7"


@respx.mock
def test_cliq_client_send_to_channel(client: cliq.ZohoCliqClient) -> None:
    respx.post("https://cliq.zoho.com/api/v2/channelsbyname/C1/message").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    route = respx.post("https://cliq.zoho.com/api/v2/chats/C1/message").mock(
        return_value=httpx.Response(200, json={"data": {"status": "ok"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/C1").mock(
        return_value=httpx.Response(404, text="not_found")
    )
    result = client.send_message("hello", channel_id="C1")
    assert route.called
    assert result["data"]["status"] == "ok"


@respx.mock
def test_cliq_client_send_to_channel_id_resolves_channel_lookup(client: cliq.ZohoCliqClient) -> None:
    respx.post("https://cliq.zoho.com/api/v2/channelsbyname/O1/message").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.post("https://cliq.zoho.com/api/v2/chats/O1/message").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"chat_id": "CT_1", "unique_name": "ops-room"}},
        )
    )
    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/message").mock(
        return_value=httpx.Response(200, json={"data": {"status": "ok"}})
    )

    result = client.send_message("hello", channel_id="O1")

    assert route.called
    assert result["data"]["status"] == "ok"


@respx.mock
def test_cliq_client_send_to_user_uses_buddies_endpoint(client: cliq.ZohoCliqClient) -> None:
    route = respx.post("https://cliq.zoho.com/api/v2/buddies/U1/message").mock(
        return_value=httpx.Response(200, json={"data": {"status": "ok"}})
    )

    result = client.send_message("hello", user_id="U1")

    assert route.called
    assert result["data"]["status"] == "ok"


def test_cliq_client_send_requires_exactly_one_destination(client: cliq.ZohoCliqClient) -> None:
    with pytest.raises(ValueError, match="exactly one"):
        client.send_message("hello")


def test_build_mail_notification_text() -> None:
    text = cliq.build_mail_notification_text(
        {
            "messageId": "M1",
            "from": "alice@example.com",
            "subject": "Status",
            "textBody": "Body line",
        },
        include_body=True,
    )
    assert "New Mail" in text
    assert "From: alice@example.com" in text
    assert "Subject: Status" in text
    assert "Message ID: M1" in text
    assert "Snippet: Body line" in text
