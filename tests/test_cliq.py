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
        "ZohoCliq.Messages.READ",
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
def test_cliq_client_send_to_channel_accepts_204_empty_body(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.post("https://cliq.zoho.com/api/v2/channelsbyname/C1/message").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    route = respx.post("https://cliq.zoho.com/api/v2/chats/C1/message").mock(
        return_value=httpx.Response(204, text="")
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/C1").mock(
        return_value=httpx.Response(404, text="not_found")
    )

    result = client.send_message("hello", channel_id="C1")

    assert route.called
    assert result["status"] == "ok"
    assert result["httpStatus"] == 204


@respx.mock
def test_cliq_client_send_to_channel_id_resolves_channel_lookup(
    client: cliq.ZohoCliqClient,
) -> None:
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
def test_cliq_client_send_to_user_uses_buddies_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    route = respx.post("https://cliq.zoho.com/api/v2/buddies/U1/message").mock(
        return_value=httpx.Response(200, json={"data": {"status": "ok"}})
    )

    result = client.send_message("hello", user_id="U1")

    assert route.called
    assert result["data"]["status"] == "ok"


@respx.mock
def test_cliq_client_send_scope_invalid_reports_reauth_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.post("https://cliq.zoho.com/api/v2/channelsbyname/C1/message").mock(
        return_value=httpx.Response(401, json={"code": "oauthtoken_scope_invalid"})
    )
    respx.post("https://cliq.zoho.com/api/v2/chats/C1/message").mock(
        return_value=httpx.Response(401, json={"code": "oauthtoken_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/C1").mock(
        return_value=httpx.Response(404, text="not_found")
    )

    with pytest.raises(SystemExit):
        client.send_message("hello", channel_id="C1")

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "zoho login --with-cliq" in err
    assert "ZohoCliq.Webhooks.CREATE" in err


def test_cliq_client_send_requires_exactly_one_destination(
    client: cliq.ZohoCliqClient,
) -> None:
    with pytest.raises(ValueError, match="exactly one"):
        client.send_message("hello")


@respx.mock
def test_cliq_client_list_messages_from_channel_id(client: cliq.ZohoCliqClient) -> None:
    respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(200, json={"data": {"chat_id": "CT_1"}})
    )
    route = respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "M1"}]})
    )

    result = client.list_messages(channel_id="O1", limit=7)

    assert result["data"][0]["id"] == "M1"
    assert dict(route.calls.last.request.url.params) == {"limit": "7"}


@respx.mock
def test_cliq_client_get_message_from_chat_id(client: cliq.ZohoCliqClient) -> None:
    route = respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M1", "text": "hello"}})
    )

    result = client.get_message("M1", chat_id="CT_1")

    assert route.called
    assert result["data"]["id"] == "M1"


@respx.mock
def test_cliq_client_list_messages_scope_invalid_reports_reauth_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(200, json={"data": {"chat_id": "CT_1"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages").mock(
        return_value=httpx.Response(401, json={"code": "oauthtoken_scope_invalid"})
    )

    with pytest.raises(SystemExit):
        client.list_messages(channel_id="O1")

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Messages.READ" in err


@respx.mock
def test_cliq_client_probe_capabilities_baseline(client: cliq.ZohoCliqClient) -> None:
    respx.get("https://cliq.zoho.com/api/v2/channels").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    respx.get("https://cliq.zoho.com/api/v2/users").mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    result = client.probe_capabilities()

    assert result["summary"]["total"] == 2
    assert result["summary"]["ok"] == 2


@respx.mock
def test_cliq_client_probe_capabilities_with_channel_context(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/channels").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    respx.get("https://cliq.zoho.com/api/v2/users").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(200, json={"data": {"id": "O1"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/O1/messages").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/O1/messages").mock(
        return_value=httpx.Response(401, json={"code": "oauthtoken_scope_invalid"})
    )

    result = client.probe_capabilities(channel_id="O1")

    checks = {item["name"]: item for item in result["checks"]}
    assert checks["channels.get"]["ok"] is True
    assert checks["chats.messages.list"]["status"] == "not_supported"
    assert checks["channels.messages.list"]["status"] == "forbidden_or_scope"


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
