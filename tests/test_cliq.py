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
def test_cliq_client_search_messages_with_fallback_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(200, json={"data": {"chat_id": "CT_1"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/search").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    route = respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/search/messages").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "M1"}]})
    )

    result = client.search_messages(
        "deploy",
        channel_id="O1",
        limit=5,
        from_time="1710000000",
        to_time="1710009999",
    )

    assert route.called
    assert result["data"][0]["id"] == "M1"
    assert dict(route.calls.last.request.url.params).get("limit") == "5"


@respx.mock
def test_cliq_client_search_messages_not_supported_reports_capability_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/search").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/search/messages").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )

    with pytest.raises(SystemExit):
        client.search_messages("deploy", chat_id="CT_1")

    err = capsys.readouterr().err
    assert "not_supported" in err
    assert "cliq capabilities" in err


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
def test_cliq_client_reply_message_success(client: cliq.ZohoCliqClient) -> None:
    respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(200, json={"data": {"chat_id": "CT_1"}})
    )
    route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/reply"
    ).mock(return_value=httpx.Response(200, json={"data": {"id": "M2"}}))

    result = client.reply_message("hello", message_id="M1", channel_id="O1")

    assert route.called
    assert result["data"]["id"] == "M2"


@respx.mock
def test_cliq_client_edit_message_success(client: cliq.ZohoCliqClient) -> None:
    route = respx.put("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M1", "text": "updated"}})
    )

    result = client.edit_message("M1", "updated", chat_id="CT_1")

    assert route.called
    assert result["data"]["text"] == "updated"


@respx.mock
def test_cliq_client_delete_message_success(client: cliq.ZohoCliqClient) -> None:
    route = respx.delete("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1").mock(
        return_value=httpx.Response(204, text="")
    )

    result = client.delete_message("M1", chat_id="CT_1")

    assert route.called
    assert result["status"] == "ok"


@respx.mock
def test_cliq_client_react_message_add_success(client: cliq.ZohoCliqClient) -> None:
    route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/reactions"
    ).mock(return_value=httpx.Response(200, json={"data": {"status": "ok"}}))

    result = client.react_message("M1", ":thumbsup:", chat_id="CT_1")

    assert route.called
    assert result["data"]["status"] == "ok"


@respx.mock
def test_cliq_client_react_message_remove_success(client: cliq.ZohoCliqClient) -> None:
    route = respx.delete(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/reactions/:thumbsup:"
    ).mock(return_value=httpx.Response(204, text=""))

    result = client.react_message("M1", ":thumbsup:", remove=True, chat_id="CT_1")

    assert route.called
    assert result["status"] == "ok"


@respx.mock
def test_request_with_candidates_retries_on_extra_key_found(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.post("https://cliq.zoho.com/api/v2/channels/O2/topic").mock(
        return_value=httpx.Response(
            400,
            json={
                "code": "extra_key_found",
                "message": "'topic' is an extra key in the JSON Object.",
            },
        )
    )
    fallback = respx.put("https://cliq.zoho.com/api/v2/channels/O2").mock(
        return_value=httpx.Response(204, text="")
    )

    result = client.update_channel_topic("O2", "deploy updates")

    assert fallback.called
    assert result["status"] == "ok"


@respx.mock
def test_request_with_candidates_retries_on_request_method_invalid(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.post("https://cliq.zoho.com/api/v2/channels/O2/members/add").mock(
        return_value=httpx.Response(
            400,
            json={
                "code": "request_method_invalid",
                "message": "The HTTP Method you are trying is invalid.",
            },
        )
    )
    fallback = respx.post("https://cliq.zoho.com/api/v2/channels/O2/members").mock(
        return_value=httpx.Response(200, json={"data": {"status": "ok"}})
    )

    result = client._request_with_candidates(
        [
            ("POST", "/channels/O2/members/add", {"member_id": "U1"}),
            ("POST", "/channels/O2/members", {"member_id": "U1"}),
        ],
        scope_hint="ZohoCliq.Channels.ALL",
        operation_label="member-add",
    )

    assert fallback.called
    assert result["data"]["status"] == "ok"


@respx.mock
def test_cliq_client_list_members_from_channel(client: cliq.ZohoCliqClient) -> None:
    route = respx.get("https://cliq.zoho.com/api/v2/channels/O1/members").mock(
        return_value=httpx.Response(200, json={"members": [{"id": "U1"}]})
    )

    result = client.list_members(channel_id="O1")

    assert route.called
    assert result["members"][0]["id"] == "U1"


@respx.mock
def test_cliq_client_add_member_success(client: cliq.ZohoCliqClient) -> None:
    respx.get("https://cliq.zoho.com/api/v2/channels/O2").mock(
        return_value=httpx.Response(200, json={"data": {"chat_id": "CT_2"}})
    )
    route = respx.post("https://cliq.zoho.com/api/v2/channels/O2/members").mock(
        return_value=httpx.Response(200, json={"data": {"status": "ok"}})
    )

    result = client.add_member("U1", channel_id="O2")

    assert route.called
    assert result["data"]["status"] == "ok"


@respx.mock
def test_cliq_client_remove_member_success(client: cliq.ZohoCliqClient) -> None:
    respx.get("https://cliq.zoho.com/api/v2/channels/O2").mock(
        return_value=httpx.Response(200, json={"data": {"chat_id": "CT_2"}})
    )
    route = respx.delete("https://cliq.zoho.com/api/v2/channels/O2/members/U1").mock(
        return_value=httpx.Response(204, text="")
    )

    result = client.remove_member("U1", channel_id="O2")

    assert route.called
    assert result["status"] == "ok"


@respx.mock
def test_cliq_client_create_channel_success(client: cliq.ZohoCliqClient) -> None:
    route = respx.post("https://cliq.zoho.com/api/v2/channels").mock(
        return_value=httpx.Response(200, json={"channel_id": "O2", "name": "ops"})
    )

    result = client.create_channel("ops", level="organization")

    assert route.called
    assert result["channel_id"] == "O2"


@respx.mock
def test_cliq_client_rename_channel_success(client: cliq.ZohoCliqClient) -> None:
    route = respx.post("https://cliq.zoho.com/api/v2/channels/O2/rename").mock(
        return_value=httpx.Response(200, json={"channel_id": "O2", "name": "ops-2"})
    )

    result = client.rename_channel("O2", "ops-2")

    assert route.called
    assert result["name"] == "ops-2"


@respx.mock
def test_cliq_client_update_channel_topic_success(client: cliq.ZohoCliqClient) -> None:
    route = respx.post("https://cliq.zoho.com/api/v2/channels/O2/topic").mock(
        return_value=httpx.Response(204, text="")
    )

    result = client.update_channel_topic("O2", "deploy updates")

    assert route.called
    assert result["status"] == "ok"


@respx.mock
def test_cliq_client_archive_channel_success(client: cliq.ZohoCliqClient) -> None:
    route = respx.post("https://cliq.zoho.com/api/v2/channels/O2/archive").mock(
        return_value=httpx.Response(204, text="")
    )

    result = client.archive_channel("O2")

    assert route.called
    assert result["status"] == "ok"


@respx.mock
def test_cliq_client_unarchive_channel_success(client: cliq.ZohoCliqClient) -> None:
    route = respx.post("https://cliq.zoho.com/api/v2/channels/O2/unarchive").mock(
        return_value=httpx.Response(204, text="")
    )

    result = client.archive_channel("O2", unarchive=True)

    assert route.called
    assert result["status"] == "ok"


@respx.mock
def test_cliq_client_delete_channel_success(client: cliq.ZohoCliqClient) -> None:
    route = respx.delete("https://cliq.zoho.com/api/v2/channels/O2").mock(
        return_value=httpx.Response(204, text="")
    )

    result = client.delete_channel("O2")

    assert route.called
    assert result["status"] == "ok"


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
