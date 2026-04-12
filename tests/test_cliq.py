"""Tests for zoho_cli.cliq helpers."""

import json
from pathlib import Path
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
        "ZohoCliq.Chats.ALL",
        "ZohoCliq.Webhooks.CREATE",
    ]


def test_missing_cliq_export_scopes_reports_missing_values() -> None:
    missing = cliq.missing_cliq_export_scopes(["ZohoCliq.OrganizationChats.READ"])
    assert missing == ["ZohoCliq.OrganizationMessages.READ"]


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
def test_cliq_client_chats(client: cliq.ZohoCliqClient) -> None:
    route = respx.get("https://cliq.zoho.com/api/v2/chats").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"id": "CT_1", "name": "DM David", "type": "direct"}]},
        )
    )
    result = client.chats(limit=9)
    assert result["data"][0]["id"] == "CT_1"
    assert dict(route.calls.last.request.url.params)["limit"] == "9"


@respx.mock
def test_cliq_client_chats_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/chats").mock(
        return_value=httpx.Response(401, json={"code": "oauthtoken_scope_invalid"})
    )

    with pytest.raises(SystemExit):
        client.chats(limit=3)

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "zoho cliq status --check-auth" in err
    assert "ZohoCliq.Chats.ALL" in err


@respx.mock
def test_cliq_client_export_conversations(client: cliq.ZohoCliqClient) -> None:
    route = respx.get("https://cliq.zoho.com/maintenanceapi/v2/chats").mock(
        return_value=httpx.Response(
            200,
            json={
                "list": [
                    {
                        "chat_id": "CT_1",
                        "title": "DM David",
                        "chat_type": "direct",
                    }
                ]
            },
        )
    )

    result = client.export_conversations()

    assert route.called
    assert dict(route.calls.last.request.url.params).get("fields") == "title,chat_id"
    assert result["list"][0]["chat_id"] == "CT_1"


@respx.mock
def test_cliq_client_export_conversations_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/maintenanceapi/v2/chats").mock(
        return_value=httpx.Response(401, json={"code": "oauthtoken_scope_invalid"})
    )
    respx.get(
        "https://cliq.zoho.com/maintenanceapi/v2/chats?fields=title,chat_id"
    ).mock(return_value=httpx.Response(401, json={"code": "oauthtoken_scope_invalid"}))

    with pytest.raises(SystemExit):
        client.export_conversations()

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "--with-cliq-export" in err
    assert "ZohoCliq.OrganizationChats.READ" in err


@respx.mock
def test_cliq_client_export_conversations_oauth_scope_invalid_code_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/maintenanceapi/v2/chats").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get(
        "https://cliq.zoho.com/maintenanceapi/v2/chats?fields=title,chat_id"
    ).mock(return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"}))

    with pytest.raises(SystemExit):
        client.export_conversations()

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.OrganizationChats.READ" in err


@respx.mock
def test_cliq_client_export_chat_messages(client: cliq.ZohoCliqClient) -> None:
    route = respx.get(
        "https://cliq.zoho.com/maintenanceapi/v2/chats/CT_1/messages"
    ).mock(
        return_value=httpx.Response(200, json={"data": [{"id": "M1", "text": "hi"}]})
    )

    result = client.export_chat_messages("CT_1")

    assert route.called
    assert result["data"][0]["id"] == "M1"


@respx.mock
def test_cliq_client_export_chat_messages_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/maintenanceapi/v2/chats/CT_1/messages").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )

    with pytest.raises(SystemExit):
        client.export_chat_messages("CT_1")

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "--with-cliq-export" in err
    assert "ZohoCliq.OrganizationMessages.READ" in err


@respx.mock
def test_cliq_client_get_dm_history_falls_back_from_conversations_to_buddies(
    client: cliq.ZohoCliqClient,
) -> None:
    conversations = respx.get(
        "https://cliq.zoho.com/api/v2/conversations/U1/messages"
    ).mock(return_value=httpx.Response(404, text="request_url_invalid"))
    buddies = respx.get("https://cliq.zoho.com/api/v2/buddies/U1/messages").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "data": [{"id": "m1"}, {"id": "m2"}],
                    "has_more": True,
                    "next_page_token": "dm-page-2",
                },
            ),
            httpx.Response(
                200,
                json={
                    "data": [{"id": "m3"}],
                    "has_more": False,
                },
            ),
        ]
    )

    history = client.get_dm_history("U1", limit=25)
    meta = client.get_last_dm_history_meta()

    assert [entry["id"] for entry in history] == ["m1", "m2", "m3"]
    assert meta["result"] == "ok"
    assert meta["selectedPath"] == "/buddies/U1/messages"
    assert meta["attemptedPaths"] == [
        "/conversations/U1/messages",
        "/buddies/U1/messages",
    ]
    assert conversations.called
    assert buddies.call_count == 2
    assert dict(buddies.calls[0].request.url.params) == {"limit": "25"}
    assert dict(buddies.calls[1].request.url.params) == {
        "limit": "25",
        "next_page_token": "dm-page-2",
    }


@respx.mock
def test_cliq_client_get_dm_history_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    for path in (
        "/conversations/U1/messages",
        "/buddies/U1/messages",
        "/users/U1/messages",
        "/chats/U1/messages",
    ):
        respx.get(f"https://cliq.zoho.com/api/v2{path}").mock(
            return_value=httpx.Response(401, json={"code": "oauthtoken_scope_invalid"})
        )

    with pytest.raises(SystemExit):
        client.get_dm_history("U1", limit=3)

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Messages.READ" in err


@respx.mock
def test_cliq_client_get_dm_history_all_candidate_misses_returns_empty(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/conversations/U1/messages").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/buddies/U1/messages").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/users/U1/messages").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/U1/messages").mock(
        return_value=httpx.Response(400, json={"code": "operation_failed"})
    )

    history = client.get_dm_history("U1", limit=3)
    meta = client.get_last_dm_history_meta()

    assert history == []
    assert meta["result"] == "not_supported"
    assert meta["selectedPath"] is None
    assert meta["attemptedPaths"] == [
        "/conversations/U1/messages",
        "/buddies/U1/messages",
        "/users/U1/messages",
        "/chats/U1/messages",
    ]


def test_cliq_client_infer_message_types_detects_voice_sticker_and_text() -> None:
    message = {
        "text": "hello :thumbsup:",
        "attachments": [
            {
                "mimeType": "audio/ogg",
                "url": "https://example.com/voice.ogg",
            }
        ],
        "sticker": {"id": "S1"},
    }

    result = cliq.ZohoCliqClient.infer_message_types(message)

    assert "text" in result
    assert "voice" in result
    assert "sticker" in result


def test_cliq_client_infer_message_types_detects_scalar_attachment_string() -> None:
    message = {
        "id": "M_local",
        "file": "https://example.com/contracts/latest.pdf",
    }

    result = cliq.ZohoCliqClient.infer_message_types(message)

    assert result == ["file"]


def test_cliq_client_infer_message_types_detects_image_from_unfurled_details() -> None:
    message = {
        "id": "M_card",
        "type": "card",
        "content": {"text": "see image"},
        "unfurled_details": {
            "url": "https://upload.wikimedia.org/wikipedia/commons/3/3f/JPEG_example_flower.jpg"
        },
    }

    result = cliq.ZohoCliqClient.infer_message_types(message)

    assert "image" in result


@respx.mock
def test_cliq_client_resolve_users_email_exact_first(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/users").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "zuid": "U2",
                        "display_name": "David Wang",
                        "email_id": "david@happy-distro.com",
                    },
                    {
                        "zuid": "U3",
                        "display_name": "David Wang 2",
                        "email_id": "david2@happy-distro.com",
                    },
                ]
            },
        )
    )

    result = client.resolve_users("david@happy-distro.com", by="email")

    assert result["count"] == 1
    assert result["matches"][0]["userId"] == "U2"
    assert result["matches"][0]["emailExact"] is True


@respx.mock
def test_cliq_client_resolve_users_name_contains(client: cliq.ZohoCliqClient) -> None:
    respx.get("https://cliq.zoho.com/api/v2/users").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "zuid": "U2",
                        "display_name": "David Wang",
                        "email_id": "david@happy-distro.com",
                    },
                    {
                        "zuid": "U3",
                        "display_name": "Alice",
                        "email_id": "alice@happy-distro.com",
                    },
                ]
            },
        )
    )

    result = client.resolve_users("david", by="name")

    assert result["count"] == 1
    assert result["matches"][0]["userId"] == "U2"
    assert result["matches"][0]["name"] == "David Wang"


@respx.mock
def test_cliq_client_whoami_from_users_me_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/users/me").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "zuid": "U_SELF",
                    "display_name": "Ai Dev",
                    "email_id": "ai-dev@happy-distro.co.uk",
                }
            },
        )
    )

    result = client.whoami(account_email="ai-dev@happy-distro.co.uk")

    assert result["status"] == "ok"
    assert result["source"] == "/users/me"
    assert result["user"]["userId"] == "U_SELF"
    assert result["user"]["email"] == "ai-dev@happy-distro.co.uk"


@respx.mock
def test_cliq_client_whoami_falls_back_to_email_match(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/users/me").mock(
        return_value=httpx.Response(403, json={"code": "inactive_appaccount_user"})
    )
    respx.get("https://cliq.zoho.com/api/v2/users/self").mock(
        return_value=httpx.Response(403, json={"code": "inactive_appaccount_user"})
    )
    respx.get("https://cliq.zoho.com/api/v2/users/current").mock(
        return_value=httpx.Response(404, json={"code": "request_url_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/users").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "zuid": "U_MATCH",
                        "display_name": "David Wang",
                        "email_id": "david@happy-distro.com",
                    }
                ]
            },
        )
    )

    result = client.whoami(account_email="david@happy-distro.com")

    assert result["status"] == "best_effort"
    assert result["source"] == "users.email_match"
    assert result["user"]["userId"] == "U_MATCH"
    assert "warning" in result


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
    respx.post("https://cliq.zoho.com/api/v2/channels/O1/message").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    descriptor = respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"chat_id": "CT_1", "unique_name": "ops-room"}},
        )
    )
    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/message").mock(
        return_value=httpx.Response(200, json={"data": {"status": "ok"}})
    )

    result = client.send_message("hello", channel_id="O1")

    assert descriptor.call_count == 1
    assert route.called
    assert result["data"]["status"] == "ok"


@respx.mock
def test_cliq_client_send_to_channel_id_tries_channels_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.post("https://cliq.zoho.com/api/v2/channelsbyname/O1/message").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.post("https://cliq.zoho.com/api/v2/chats/O1/message").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    route = respx.post("https://cliq.zoho.com/api/v2/channels/O1/message").mock(
        return_value=httpx.Response(200, json={"data": {"status": "ok"}})
    )
    descriptor = respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(404, text="not_found")
    )

    result = client.send_message("hello", channel_id="O1")

    assert descriptor.call_count == 1
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
def test_cliq_client_send_to_user_with_attachment_payload(
    client: cliq.ZohoCliqClient,
) -> None:
    route = respx.post("https://cliq.zoho.com/api/v2/buddies/U1/message").mock(
        return_value=httpx.Response(200, json={"data": {"status": "ok"}})
    )

    result = client.send_message(
        "media test",
        user_id="U1",
        attachment={
            "title": "Image",
            "url": "https://example.com/image.jpg",
            "button_label": "View",
        },
    )

    payload = json.loads(route.calls.last.request.content.decode("utf-8"))
    assert payload["attachments"]["url"] == "https://example.com/image.jpg"
    assert result["data"]["status"] == "ok"


@respx.mock
def test_cliq_client_send_with_strict_media_does_not_fallback_to_text_only(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    buddies_route = respx.post("https://cliq.zoho.com/api/v2/buddies/U1/message").mock(
        return_value=httpx.Response(400, json={"code": "operation_failed"})
    )
    respx.post("https://cliq.zoho.com/api/v2/buddies/U1/messages").mock(
        return_value=httpx.Response(400, json={"code": "operation_failed"})
    )
    users_route = respx.post("https://cliq.zoho.com/api/v2/users/U1/message").mock(
        return_value=httpx.Response(400, json={"code": "operation_failed"})
    )
    respx.post("https://cliq.zoho.com/api/v2/users/U1/messages").mock(
        return_value=httpx.Response(400, json={"code": "operation_failed"})
    )

    with pytest.raises(SystemExit):
        client.send_message(
            "hello",
            user_id="U1",
            attachment={
                "title": "Image",
                "url": "https://example.com/image.jpg",
                "button_label": "View",
            },
            strict_media=True,
        )

    sent_payloads = [
        json.loads(call.request.content.decode("utf-8"))
        for route in (buddies_route, users_route)
        for call in route.calls
    ]
    assert sent_payloads
    assert all("attachments" in payload for payload in sent_payloads)
    assert all("text" in payload for payload in sent_payloads)
    assert all(set(payload.keys()) != {"text"} for payload in sent_payloads)
    err = capsys.readouterr().err
    assert "api_error" in err


@respx.mock
def test_cliq_client_send_local_file_message_to_user(
    client: cliq.ZohoCliqClient,
    tmp_path: Path,
) -> None:
    sample = tmp_path / "voice.m4a"
    sample.write_bytes(b"voice-bytes")

    route = respx.post("https://cliq.zoho.com/api/v2/buddies/U1/message").mock(
        return_value=httpx.Response(200, json={"data": {"status": "ok"}})
    )

    result = client.send_local_file_message(
        str(sample),
        user_id="U1",
        text="voice",
        media_kind="voice",
    )

    assert route.called
    raw = route.calls.last.request.content
    assert b'name="voice"' in raw
    assert b'filename="voice.m4a"' in raw
    assert result["data"]["status"] == "ok"
    assert result["data"]["upload"]["path"] == "/buddies/U1/message"
    assert result["data"]["upload"]["field"] == "voice"
    assert result["data"]["upload"]["fileName"] == "voice.m4a"
    assert result["data"]["upload"]["mimeType"].startswith("audio/")


@respx.mock
def test_cliq_client_send_local_file_message_user_tries_plural_message_endpoint(
    client: cliq.ZohoCliqClient,
    tmp_path: Path,
) -> None:
    sample = tmp_path / "voice.m4a"
    sample.write_bytes(b"voice-bytes")

    respx.post("https://cliq.zoho.com/api/v2/buddies/U1/message").mock(
        return_value=httpx.Response(400, json={"code": "request_url_invalid"})
    )
    route = respx.post("https://cliq.zoho.com/api/v2/buddies/U1/messages").mock(
        return_value=httpx.Response(200, json={"data": {"status": "ok"}})
    )

    result = client.send_local_file_message(
        str(sample),
        user_id="U1",
        text="voice",
        media_kind="voice",
    )

    assert route.called
    assert result["data"]["status"] == "ok"
    assert result["data"]["upload"]["path"] == "/buddies/U1/messages"


@respx.mock
def test_cliq_client_send_local_file_message_error_reports_form_field(
    client: cliq.ZohoCliqClient,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sample = tmp_path / "voice.m4a"
    sample.write_bytes(b"voice-bytes")

    respx.post("https://cliq.zoho.com/api/v2/buddies/U1/message").mock(
        return_value=httpx.Response(500, text="server_error")
    )

    with pytest.raises(SystemExit):
        client.send_local_file_message(
            str(sample),
            user_id="U1",
            text="voice",
            media_kind="voice",
        )

    err = capsys.readouterr().err
    assert "api_error" in err
    assert "POST /buddies/U1/message" in err
    assert "field=voice" in err
    assert "attempts:" in err
    assert "status=500" in err
    assert "code=server_error" in err


@respx.mock
def test_cliq_client_send_local_file_message_all_endpoint_misses_report_not_supported(
    client: cliq.ZohoCliqClient,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sample = tmp_path / "probe.txt"
    sample.write_text("hello", encoding="utf-8")

    respx.post("https://cliq.zoho.com/api/v2/buddies/U1/message").mock(
        return_value=httpx.Response(400, json={"code": "operation_failed"})
    )
    respx.post("https://cliq.zoho.com/api/v2/buddies/U1/messages").mock(
        return_value=httpx.Response(400, json={"code": "request_url_invalid"})
    )
    respx.post("https://cliq.zoho.com/api/v2/users/U1/message").mock(
        return_value=httpx.Response(400, json={"code": "request_method_invalid"})
    )
    respx.post("https://cliq.zoho.com/api/v2/users/U1/messages").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.post("https://cliq.zoho.com/api/v2/buddies/U1/files").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.post("https://cliq.zoho.com/api/v2/users/U1/files").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )

    with pytest.raises(SystemExit):
        client.send_local_file_message(
            str(sample),
            user_id="U1",
            text="file",
            media_kind="file",
        )

    err = capsys.readouterr().err
    assert "not_supported" in err
    assert "local multipart upload endpoints are not supported" in err
    assert "attempts:" in err


@respx.mock
def test_cliq_client_send_local_file_message_resolves_email_user_id(
    client: cliq.ZohoCliqClient,
    tmp_path: Path,
) -> None:
    sample = tmp_path / "voice.m4a"
    sample.write_bytes(b"voice-bytes")

    users_route = respx.get("https://cliq.zoho.com/api/v2/users").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "zuid": "U1",
                        "display_name": "David Wang",
                        "email_id": "david@happy-distro.com",
                    }
                ]
            },
        )
    )
    respx.post(
        "https://cliq.zoho.com/api/v2/buddies/david@happy-distro.com/message"
    ).mock(return_value=httpx.Response(400, json={"code": "request_url_invalid"}))
    respx.post(
        "https://cliq.zoho.com/api/v2/buddies/david@happy-distro.com/messages"
    ).mock(return_value=httpx.Response(400, json={"code": "request_url_invalid"}))
    respx.post(
        "https://cliq.zoho.com/api/v2/users/david@happy-distro.com/message"
    ).mock(return_value=httpx.Response(400, json={"code": "request_url_invalid"}))
    respx.post(
        "https://cliq.zoho.com/api/v2/users/david@happy-distro.com/messages"
    ).mock(return_value=httpx.Response(400, json={"code": "request_url_invalid"}))
    respx.post(
        "https://cliq.zoho.com/api/v2/buddies/david@happy-distro.com/files"
    ).mock(return_value=httpx.Response(400, json={"code": "request_url_invalid"}))
    respx.post("https://cliq.zoho.com/api/v2/users/david@happy-distro.com/files").mock(
        return_value=httpx.Response(400, json={"code": "request_url_invalid"})
    )
    route = respx.post("https://cliq.zoho.com/api/v2/buddies/U1/message").mock(
        return_value=httpx.Response(200, json={"data": {"status": "ok"}})
    )

    result = client.send_local_file_message(
        str(sample),
        user_id="david@happy-distro.com",
        text="voice",
        media_kind="voice",
    )

    assert users_route.called
    assert route.called
    assert result["data"]["status"] == "ok"
    assert result["data"]["upload"]["path"] == "/buddies/U1/message"


@respx.mock
def test_cliq_client_send_message_resolves_email_user_id(
    client: cliq.ZohoCliqClient,
) -> None:
    users_route = respx.get("https://cliq.zoho.com/api/v2/users").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "zuid": "U1",
                        "display_name": "David Wang",
                        "email_id": "david@happy-distro.com",
                    }
                ]
            },
        )
    )
    respx.post(
        "https://cliq.zoho.com/api/v2/buddies/david@happy-distro.com/message"
    ).mock(return_value=httpx.Response(400, json={"code": "request_url_invalid"}))
    respx.post(
        "https://cliq.zoho.com/api/v2/buddies/david@happy-distro.com/messages"
    ).mock(return_value=httpx.Response(400, json={"code": "request_url_invalid"}))
    respx.post(
        "https://cliq.zoho.com/api/v2/users/david@happy-distro.com/message"
    ).mock(return_value=httpx.Response(400, json={"code": "request_url_invalid"}))
    respx.post(
        "https://cliq.zoho.com/api/v2/users/david@happy-distro.com/messages"
    ).mock(return_value=httpx.Response(400, json={"code": "request_url_invalid"}))
    route = respx.post("https://cliq.zoho.com/api/v2/buddies/U1/message").mock(
        return_value=httpx.Response(204, text="")
    )

    result = client.send_message("hello", user_id="david@happy-distro.com")

    assert users_route.called
    assert route.called
    assert result["status"] == "ok"
    assert result["httpStatus"] == 204


@respx.mock
def test_cliq_client_send_local_image_message_prefers_image_field(
    client: cliq.ZohoCliqClient,
    tmp_path: Path,
) -> None:
    sample = tmp_path / "image.png"
    sample.write_bytes(b"png-bytes")

    route = respx.post("https://cliq.zoho.com/api/v2/buddies/U1/message").mock(
        return_value=httpx.Response(200, json={"data": {"status": "ok"}})
    )

    result = client.send_local_file_message(
        str(sample),
        user_id="U1",
        text="image",
        media_kind="image",
    )

    assert route.called
    raw = route.calls.last.request.content
    assert b'name="image"' in raw
    assert b'filename="image.png"' in raw
    assert result["data"]["status"] == "ok"
    assert result["data"]["upload"]["path"] == "/buddies/U1/message"
    assert result["data"]["upload"]["field"] == "image"
    assert result["data"]["upload"]["fileName"] == "image.png"
    assert result["data"]["upload"]["mimeType"] == "image/png"


@respx.mock
def test_cliq_client_send_local_file_message_user_falls_back_to_files_endpoint(
    client: cliq.ZohoCliqClient,
    tmp_path: Path,
) -> None:
    sample = tmp_path / "doc.txt"
    sample.write_text("hello")

    respx.post("https://cliq.zoho.com/api/v2/buddies/U1/message").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.post("https://cliq.zoho.com/api/v2/buddies/U1/messages").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.post("https://cliq.zoho.com/api/v2/users/U1/message").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.post("https://cliq.zoho.com/api/v2/users/U1/messages").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    route = respx.post("https://cliq.zoho.com/api/v2/buddies/U1/files").mock(
        return_value=httpx.Response(200, json={"data": {"status": "ok"}})
    )

    result = client.send_local_file_message(
        str(sample),
        user_id="U1",
        text="file via files endpoint",
        media_kind="file",
    )

    assert route.called
    raw = route.calls.last.request.content
    assert b'name="files"' in raw
    assert b'name="comments"' in raw
    assert result["data"]["status"] == "ok"
    assert result["data"]["upload"]["path"] == "/buddies/U1/files"
    assert result["data"]["upload"]["field"] == "files"


@respx.mock
def test_cliq_client_send_local_file_message_channel_falls_back_to_files_endpoint(
    client: cliq.ZohoCliqClient,
    tmp_path: Path,
) -> None:
    sample = tmp_path / "image.png"
    sample.write_bytes(b"png-bytes")

    respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"chat_id": "CT_1", "unique_name": "channel-one"}},
        )
    )

    for path in [
        "https://cliq.zoho.com/api/v2/chats/CT_1/message",
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages",
        "https://cliq.zoho.com/api/v2/channelsbyname/channel-one/message",
        "https://cliq.zoho.com/api/v2/channelsbyname/channel-one/messages",
        "https://cliq.zoho.com/api/v2/chats/O1/message",
        "https://cliq.zoho.com/api/v2/chats/O1/messages",
        "https://cliq.zoho.com/api/v2/channels/O1/message",
        "https://cliq.zoho.com/api/v2/channels/O1/messages",
    ]:
        respx.post(path).mock(
            return_value=httpx.Response(404, text="request_url_invalid")
        )

    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/files").mock(
        return_value=httpx.Response(200, json={"data": {"status": "ok"}})
    )

    result = client.send_local_file_message(
        str(sample),
        channel_id="O1",
        text="image via files endpoint",
        media_kind="image",
    )

    assert route.called
    raw = route.calls.last.request.content
    assert b'name="files"' in raw
    assert b'name="comments"' in raw
    assert result["data"]["status"] == "ok"
    assert result["data"]["upload"]["path"] == "/chats/CT_1/files"
    assert result["data"]["upload"]["field"] == "files"


@respx.mock
def test_cliq_client_send_local_file_message_channel_id_tries_channels_endpoint(
    client: cliq.ZohoCliqClient,
    tmp_path: Path,
) -> None:
    sample = tmp_path / "voice.m4a"
    sample.write_bytes(b"voice-bytes")

    respx.post("https://cliq.zoho.com/api/v2/channelsbyname/O1/message").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.post("https://cliq.zoho.com/api/v2/channelsbyname/O1/messages").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.post("https://cliq.zoho.com/api/v2/chats/O1/message").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.post("https://cliq.zoho.com/api/v2/chats/O1/messages").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    route = respx.post("https://cliq.zoho.com/api/v2/channels/O1/message").mock(
        return_value=httpx.Response(200, json={"data": {"status": "ok"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(404, text="not_found")
    )

    result = client.send_local_file_message(
        str(sample),
        channel_id="O1",
        text="voice",
        media_kind="voice",
    )

    assert route.called
    assert result["data"]["status"] == "ok"
    assert result["data"]["upload"]["path"] == "/channels/O1/message"


@respx.mock
def test_cliq_client_send_local_file_message_channel_prefers_resolved_chat_path(
    client: cliq.ZohoCliqClient,
    tmp_path: Path,
) -> None:
    sample = tmp_path / "voice.m4a"
    sample.write_bytes(b"voice-bytes")

    respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"chat_id": "CT_1", "unique_name": "channel-one"}},
        )
    )
    resolved = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/message").mock(
        return_value=httpx.Response(200, json={"data": {"status": "ok"}})
    )
    raw = respx.post("https://cliq.zoho.com/api/v2/chats/O1/message").mock(
        return_value=httpx.Response(200, json={"data": {"status": "ok"}})
    )

    result = client.send_local_file_message(
        str(sample),
        channel_id="O1",
        text="voice",
        media_kind="voice",
    )

    assert resolved.called
    assert not raw.called
    assert result["data"]["upload"]["path"] == "/chats/CT_1/message"


@respx.mock
def test_cliq_client_send_local_file_message_channel_id_tries_plural_message_endpoint(
    client: cliq.ZohoCliqClient,
    tmp_path: Path,
) -> None:
    sample = tmp_path / "voice.m4a"
    sample.write_bytes(b"voice-bytes")

    respx.post("https://cliq.zoho.com/api/v2/channelsbyname/O1/message").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.post("https://cliq.zoho.com/api/v2/channelsbyname/O1/messages").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.post("https://cliq.zoho.com/api/v2/chats/O1/message").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    route = respx.post("https://cliq.zoho.com/api/v2/chats/O1/messages").mock(
        return_value=httpx.Response(200, json={"data": {"status": "ok"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(404, text="not_found")
    )

    result = client.send_local_file_message(
        str(sample),
        channel_id="O1",
        text="voice",
        media_kind="voice",
    )

    assert route.called
    assert result["data"]["status"] == "ok"
    assert result["data"]["upload"]["path"] == "/chats/O1/messages"


@respx.mock
def test_cliq_client_send_message_channel_prefers_resolved_chat_path(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"chat_id": "CT_1", "unique_name": "channel-one"}},
        )
    )
    resolved = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/message").mock(
        return_value=httpx.Response(204, text="")
    )
    raw = respx.post("https://cliq.zoho.com/api/v2/chats/O1/message").mock(
        return_value=httpx.Response(204, text="")
    )

    result = client.send_message("hello", channel_id="O1")

    assert resolved.called
    assert not raw.called
    assert result["status"] == "ok"
    assert result["httpStatus"] == 204


@respx.mock
def test_cliq_client_send_local_file_message_request_method_invalid_skips_path(
    client: cliq.ZohoCliqClient,
    tmp_path: Path,
) -> None:
    sample = tmp_path / "voice.m4a"
    sample.write_bytes(b"voice-bytes")

    respx.post("https://cliq.zoho.com/api/v2/channelsbyname/O1/message").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.post("https://cliq.zoho.com/api/v2/channelsbyname/O1/messages").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    first = respx.post("https://cliq.zoho.com/api/v2/chats/O1/message").mock(
        return_value=httpx.Response(400, json={"code": "request_method_invalid"})
    )
    second = respx.post("https://cliq.zoho.com/api/v2/chats/O1/messages").mock(
        return_value=httpx.Response(200, json={"data": {"status": "ok"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(404, text="not_found")
    )

    result = client.send_local_file_message(
        str(sample),
        channel_id="O1",
        text="voice",
        media_kind="voice",
    )

    assert first.called
    assert len(first.calls) == 1
    assert second.called
    assert result["data"]["status"] == "ok"
    assert result["data"]["upload"]["path"] == "/chats/O1/messages"


@respx.mock
def test_cliq_client_send_local_file_message_operation_failed_skips_path(
    client: cliq.ZohoCliqClient,
    tmp_path: Path,
) -> None:
    sample = tmp_path / "voice.m4a"
    sample.write_bytes(b"voice-bytes")

    respx.post("https://cliq.zoho.com/api/v2/channelsbyname/O1/message").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.post("https://cliq.zoho.com/api/v2/channelsbyname/O1/messages").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    first = respx.post("https://cliq.zoho.com/api/v2/chats/O1/message").mock(
        return_value=httpx.Response(400, json={"code": "operation_failed"})
    )
    second = respx.post("https://cliq.zoho.com/api/v2/chats/O1/messages").mock(
        return_value=httpx.Response(200, json={"data": {"status": "ok"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(404, text="not_found")
    )

    result = client.send_local_file_message(
        str(sample),
        channel_id="O1",
        text="voice",
        media_kind="voice",
    )

    assert first.called
    assert len(first.calls) == 1
    assert second.called
    assert result["data"]["status"] == "ok"
    assert result["data"]["upload"]["path"] == "/chats/O1/messages"


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
    respx.post("https://cliq.zoho.com/api/v2/channels/C1/message").mock(
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


def test_cliq_client_send_requires_message_or_media(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        client.send_message("   ", user_id="U1")

    err = capsys.readouterr().err
    assert "invalid_message" in err


@respx.mock
def test_cliq_client_list_messages_from_channel_id(client: cliq.ZohoCliqClient) -> None:
    descriptor = respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(200, json={"data": {"chat_id": "CT_1"}})
    )
    route = respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "M1"}]})
    )

    result = client.list_messages(channel_id="O1", limit=7)

    assert descriptor.call_count == 1
    assert result["data"][0]["id"] == "M1"
    assert dict(route.calls.last.request.url.params) == {"limit": "7"}


def test_build_watch_context_seed_with_cursor_found() -> None:
    payload = cliq.ZohoCliqClient.build_watch_context_seed(
        [
            {"id": "M5", "text": "latest", "sender_id": "U5", "time": "5000"},
            {
                "id": "M4",
                "message": "next",
                "sender": {"id": "U4"},
                "created_time": "4000",
            },
            {"id": "M3", "text": "anchor", "sender_id": "U3", "time": "3000"},
        ],
        since_message_id="M3",
        max_messages=10,
    )

    assert payload["cursorFound"] is True
    assert payload["latestMessageId"] == "M5"
    assert payload["nextSinceMessageId"] == "M5"
    assert payload["newCount"] == 2
    assert [item["messageId"] for item in payload["messages"]] == ["M4", "M5"]


def test_build_watch_context_seed_truncates_when_cursor_not_found() -> None:
    payload = cliq.ZohoCliqClient.build_watch_context_seed(
        [
            {"id": "M4", "text": "4"},
            {"id": "M3", "text": "3"},
            {"id": "M2", "text": "2"},
            {"id": "M1", "text": "1"},
        ],
        since_message_id="M0",
        max_messages=2,
    )

    assert payload["cursorFound"] is False
    assert payload["truncated"] is True
    assert payload["newCount"] == 2
    assert [item["messageId"] for item in payload["messages"]] == ["M3", "M4"]


def test_build_watch_reply_action_selects_latest_message() -> None:
    action = cliq.ZohoCliqClient.build_watch_reply_action(
        {
            "chatId": "CT_1",
            "channelId": "O1",
            "messages": [
                {"messageId": "M1", "senderId": "U1", "text": "first"},
                {"messageId": "M2", "senderId": "U2", "text": "latest"},
            ],
        },
        text="ack",
    )

    assert action["action"] == "reply-latest"
    assert action["chatId"] == "CT_1"
    assert action["channelId"] == "O1"
    assert action["targetMessageId"] == "M2"
    assert action["hasTarget"] is True


@respx.mock
def test_execute_watch_reply_action_replies_to_latest_message(
    client: cliq.ZohoCliqClient,
) -> None:
    route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/reply"
    ).mock(return_value=httpx.Response(200, json={"data": {"id": "M3"}}))

    result = client.execute_watch_reply_action(
        {
            "chatId": "CT_1",
            "channelId": "O1",
            "messages": [
                {"messageId": "M1", "senderId": "U1", "text": "first"},
                {"messageId": "M2", "senderId": "U2", "text": "latest"},
            ],
        },
        text="ack",
    )

    assert route.called
    assert result["status"] == "ok"
    assert result["applied"] is True
    assert result["targetMessageId"] == "M2"
    assert result["result"]["id"] == "M3"


def test_execute_watch_reply_action_no_messages_returns_noop(
    client: cliq.ZohoCliqClient,
) -> None:
    result = client.execute_watch_reply_action(
        {
            "chatId": "CT_1",
            "channelId": "O1",
            "messages": [],
        },
        text="ack",
    )

    assert result["status"] == "ok"
    assert result["applied"] is False
    assert result["reason"] == "no_new_messages"
    assert result["targetMessageId"] == ""


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
def test_cliq_client_search_messages_retries_on_extra_param_found(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/search").mock(
        return_value=httpx.Response(
            400,
            json={
                "code": "extra_param_found",
                "message": "'search' is an extra param in the query.",
            },
        )
    )
    fallback = respx.get(
        "https://cliq.zoho.com/api/v2/chats/CT_1/search/messages"
    ).mock(return_value=httpx.Response(200, json={"data": [{"id": "M2"}]}))

    result = client.search_messages("deploy", chat_id="CT_1", limit=3)

    assert fallback.called
    assert result["data"][0]["id"] == "M2"


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
def test_cliq_client_get_message_files_with_fallback_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/files").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    route = respx.get(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/attachments"
    ).mock(return_value=httpx.Response(200, json={"data": [{"id": "F1"}]}))

    result = client.get_message_files("M1", chat_id="CT_1")

    assert route.called
    assert result["data"][0]["id"] == "F1"
    assert result["fetch"]["path"] == "/chats/CT_1/messages/M1/attachments"


@respx.mock
def test_cliq_client_get_message_files_not_supported_reports_capability_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/files").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/attachments").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )

    with pytest.raises(SystemExit):
        client.get_message_files("M1", chat_id="CT_1")

    err = capsys.readouterr().err
    assert "not_supported" in err
    assert "cliq capabilities" in err


@respx.mock
def test_cliq_client_get_message_files_falls_back_when_files_reports_no_attachment(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/files").mock(
        return_value=httpx.Response(
            400,
            json={
                "code": "message_attachment_not_found",
                "message": "No attachment found for this message.",
            },
        )
    )
    fallback = respx.get(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/attachments"
    ).mock(return_value=httpx.Response(200, json={"data": [{"id": "F2"}]}))

    result = client.get_message_files("M1", chat_id="CT_1")

    assert fallback.called
    assert result["data"][0]["id"] == "F2"
    assert result["fetch"]["path"] == "/chats/CT_1/messages/M1/attachments"


@respx.mock
def test_cliq_client_get_message_files_no_attachment_returns_empty(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/files").mock(
        return_value=httpx.Response(
            400,
            json={
                "code": "message_attachment_not_found",
                "message": "No attachment found for this message.",
            },
        )
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/attachments").mock(
        return_value=httpx.Response(
            400,
            json={
                "code": "no_attachments_found",
                "message": "No attachments.",
            },
        )
    )

    result = client.get_message_files("M1", chat_id="CT_1")

    assert result == {
        "files": [],
        "fetch": {"path": "/chats/CT_1/messages/M1/files"},
    }


@respx.mock
def test_cliq_client_get_message_from_chat_id(client: cliq.ZohoCliqClient) -> None:
    route = respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M1", "text": "hello"}})
    )

    result = client.get_message("M1", chat_id="CT_1")

    assert route.called
    assert result["data"]["id"] == "M1"


@respx.mock
def test_cliq_client_get_message_from_channel_id(client: cliq.ZohoCliqClient) -> None:
    descriptor = respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(200, json={"data": {"chat_id": "CT_1"}})
    )
    route = respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M1", "text": "ok"}})
    )

    result = client.get_message("M1", channel_id="O1")

    assert descriptor.call_count == 1
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
def test_cliq_client_create_thread(client: cliq.ZohoCliqClient) -> None:
    route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/C1/messages/M1/threads"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "thread_id": "T1",
                    "message_id": "TM1",
                }
            },
        )
    )

    payload = client.create_thread("M1", "hello thread", chat_id="C1")
    assert route.called
    assert payload["data"]["thread_id"] == "T1"


@respx.mock
def test_cliq_client_list_threads_falls_back_to_thread_path(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/chats/C1/threads").mock(
        return_value=httpx.Response(
            404,
            json={
                "code": "request_url_invalid",
                "message": "Not found",
            },
        )
    )
    route = respx.get("https://cliq.zoho.com/api/v2/chats/C1/thread").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "T1"}]})
    )

    payload = client.list_threads(chat_id="C1", limit=5)
    assert route.called
    assert payload["data"][0]["id"] == "T1"


@respx.mock
def test_cliq_client_schedule_message_falls_back_to_messages_scheduled(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.post("https://cliq.zoho.com/api/v2/chats/C1/scheduled").mock(
        return_value=httpx.Response(
            404,
            json={
                "code": "request_url_invalid",
                "message": "Not found",
            },
        )
    )
    route = respx.post("https://cliq.zoho.com/api/v2/chats/C1/messages/scheduled").mock(
        return_value=httpx.Response(200, json={"data": {"id": "S1"}})
    )

    payload = client.schedule_message(
        "hello schedule",
        "2026-04-13T10:00:00Z",
        chat_id="C1",
    )
    assert route.called
    assert payload["data"]["id"] == "S1"


@respx.mock
def test_cliq_client_list_scheduled_messages_falls_back_to_messages_scheduled(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/chats/C1/scheduled").mock(
        return_value=httpx.Response(
            404,
            json={
                "code": "request_url_invalid",
                "message": "Not found",
            },
        )
    )
    route = respx.get("https://cliq.zoho.com/api/v2/chats/C1/messages/scheduled").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "S1"}]})
    )

    payload = client.list_scheduled_messages(chat_id="C1", limit=3)
    assert route.called
    assert payload["data"][0]["id"] == "S1"


@respx.mock
def test_cliq_client_get_scheduled_message_falls_back_to_messages_scheduled(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/chats/C1/scheduled/S1").mock(
        return_value=httpx.Response(
            404,
            json={
                "code": "request_url_invalid",
                "message": "Not found",
            },
        )
    )
    route = respx.get(
        "https://cliq.zoho.com/api/v2/chats/C1/messages/scheduled/S1"
    ).mock(return_value=httpx.Response(200, json={"data": {"id": "S1"}}))

    payload = client.get_scheduled_message("S1", chat_id="C1")
    assert route.called
    assert payload["data"]["id"] == "S1"


@respx.mock
def test_cliq_client_cancel_scheduled_message_falls_back_to_messages_scheduled(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.delete("https://cliq.zoho.com/api/v2/chats/C1/scheduled/S1").mock(
        return_value=httpx.Response(
            404,
            json={
                "code": "request_url_invalid",
                "message": "Not found",
            },
        )
    )
    route = respx.delete(
        "https://cliq.zoho.com/api/v2/chats/C1/messages/scheduled/S1"
    ).mock(return_value=httpx.Response(204, text=""))

    payload = client.cancel_scheduled_message("S1", chat_id="C1")
    assert route.called
    assert payload["status"] == "ok"


@respx.mock
def test_cliq_client_post_to_bot_falls_back_to_messages(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.post("https://cliq.zoho.com/api/v2/bots/B1/message").mock(
        return_value=httpx.Response(
            404,
            json={
                "code": "request_url_invalid",
                "message": "Not found",
            },
        )
    )
    route = respx.post("https://cliq.zoho.com/api/v2/bots/B1/messages").mock(
        return_value=httpx.Response(200, json={"data": {"id": "BM1"}})
    )

    payload = client.post_to_bot("B1", "hello bot")
    assert route.called
    assert payload["data"]["id"] == "BM1"


@respx.mock
def test_cliq_client_post_to_bot_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.post(url__regex=r"https://cliq\.zoho\.com/api/v2/bot[s]?/B1/.*").mock(
        return_value=httpx.Response(
            401,
            json={
                "code": "oauthtoken_scope_invalid",
                "message": "scope missing",
            },
        )
    )

    with pytest.raises(SystemExit):
        client.post_to_bot("B1", "hello bot")

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Webhooks.CREATE" in err


@respx.mock
def test_cliq_client_list_bot_subscribers_falls_back_to_followers(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/bots/B1/subscribers").mock(
        return_value=httpx.Response(
            404,
            json={
                "code": "request_url_invalid",
                "message": "Not found",
            },
        )
    )
    route = respx.get("https://cliq.zoho.com/api/v2/bots/B1/followers").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "U1"}]})
    )

    payload = client.list_bot_subscribers("B1", limit=2)
    assert route.called
    assert payload["data"][0]["id"] == "U1"


@respx.mock
def test_cliq_client_list_bot_subscribers_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get(url__regex=r"https://cliq\.zoho\.com/api/v2/bot[s]?/B1/.*").mock(
        return_value=httpx.Response(
            401,
            json={
                "code": "oauthtoken_scope_invalid",
                "message": "scope missing",
            },
        )
    )

    with pytest.raises(SystemExit):
        client.list_bot_subscribers("B1")

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Bots.READ" in err


@respx.mock
def test_cliq_client_trigger_bot_call_falls_back_to_call_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.post("https://cliq.zoho.com/api/v2/bots/B1/calls").mock(
        return_value=httpx.Response(
            404,
            json={
                "code": "request_url_invalid",
                "message": "Not found",
            },
        )
    )
    route = respx.post("https://cliq.zoho.com/api/v2/bots/B1/call").mock(
        return_value=httpx.Response(200, json={"data": {"id": "BC1"}})
    )

    payload = client.trigger_bot_call("B1", "daily_digest", inputs={"limit": 5})
    assert route.called
    assert payload["data"]["id"] == "BC1"


@respx.mock
def test_cliq_client_trigger_bot_call_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.post(url__regex=r"https://cliq\.zoho\.com/api/v2/bot[s]?/B1/.*").mock(
        return_value=httpx.Response(
            401,
            json={
                "code": "oauthtoken_scope_invalid",
                "message": "scope missing",
            },
        )
    )

    with pytest.raises(SystemExit):
        client.trigger_bot_call("B1", "daily_digest")

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Webhooks.CREATE" in err


@respx.mock
def test_cliq_client_leave_chat_falls_back_to_leave_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    primary = respx.delete("https://cliq.zoho.com/api/v2/chats/C1/members/me").mock(
        return_value=httpx.Response(
            404,
            json={
                "code": "request_url_invalid",
                "message": "Not found",
            },
        )
    )
    fallback = respx.post("https://cliq.zoho.com/api/v2/chats/C1/leave").mock(
        return_value=httpx.Response(200, json={"data": {"id": "C1"}})
    )

    payload = client.leave_chat(chat_id="C1")
    assert primary.called
    assert fallback.called
    assert payload["data"]["id"] == "C1"


@respx.mock
def test_cliq_client_leave_chat_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    scope_error = {
        "code": "oauthtoken_scope_invalid",
        "message": "scope missing",
    }
    respx.delete("https://cliq.zoho.com/api/v2/chats/C1/members/me").mock(
        return_value=httpx.Response(401, json=scope_error)
    )
    respx.post("https://cliq.zoho.com/api/v2/chats/C1/leave").mock(
        return_value=httpx.Response(401, json=scope_error)
    )
    respx.post("https://cliq.zoho.com/api/v2/chats/C1/members/leave").mock(
        return_value=httpx.Response(401, json=scope_error)
    )
    respx.delete("https://cliq.zoho.com/api/v2/chats/C1/member/me").mock(
        return_value=httpx.Response(401, json=scope_error)
    )
    respx.post("https://cliq.zoho.com/api/v2/chats/C1/exit").mock(
        return_value=httpx.Response(401, json=scope_error)
    )

    with pytest.raises(SystemExit):
        client.leave_chat(chat_id="C1")

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Channels.UPDATE" in err


@respx.mock
def test_cliq_client_set_chat_mute_falls_back_to_notifications_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    primary = respx.post("https://cliq.zoho.com/api/v2/chats/C1/mute").mock(
        return_value=httpx.Response(
            404,
            json={
                "code": "request_url_invalid",
                "message": "Not found",
            },
        )
    )
    fallback = respx.post(
        "https://cliq.zoho.com/api/v2/chats/C1/notifications/mute"
    ).mock(return_value=httpx.Response(200, json={"data": {"muted": True}}))

    payload = client.set_chat_mute(chat_id="C1", muted=True)
    assert primary.called
    assert fallback.called
    assert payload["data"]["muted"] is True


@respx.mock
def test_cliq_client_set_chat_unmute_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    scope_error = {
        "code": "oauthtoken_scope_invalid",
        "message": "scope missing",
    }
    respx.post("https://cliq.zoho.com/api/v2/chats/C1/unmute").mock(
        return_value=httpx.Response(401, json=scope_error)
    )
    respx.post("https://cliq.zoho.com/api/v2/chats/C1/notifications/unmute").mock(
        return_value=httpx.Response(401, json=scope_error)
    )
    respx.post("https://cliq.zoho.com/api/v2/chats/C1/members/me/unmute").mock(
        return_value=httpx.Response(401, json=scope_error)
    )
    respx.patch("https://cliq.zoho.com/api/v2/chats/C1/notifications").mock(
        return_value=httpx.Response(401, json=scope_error)
    )
    respx.put("https://cliq.zoho.com/api/v2/chats/C1/notifications").mock(
        return_value=httpx.Response(401, json=scope_error)
    )

    with pytest.raises(SystemExit):
        client.set_chat_mute(chat_id="C1", muted=False)

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Channels.UPDATE" in err


@respx.mock
def test_cliq_client_set_chat_pin_falls_back_to_messages_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    primary = respx.post("https://cliq.zoho.com/api/v2/chats/C1/pin").mock(
        return_value=httpx.Response(
            404,
            json={
                "code": "request_url_invalid",
                "message": "Not found",
            },
        )
    )
    fallback = respx.post("https://cliq.zoho.com/api/v2/chats/C1/messages/pin").mock(
        return_value=httpx.Response(200, json={"data": {"pinned": True}})
    )

    payload = client.set_chat_pin(chat_id="C1", pinned=True)
    assert primary.called
    assert fallback.called
    assert payload["data"]["pinned"] is True


@respx.mock
def test_cliq_client_set_chat_unpin_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    scope_error = {
        "code": "oauthtoken_scope_invalid",
        "message": "scope missing",
    }
    respx.post("https://cliq.zoho.com/api/v2/chats/C1/unpin").mock(
        return_value=httpx.Response(401, json=scope_error)
    )
    respx.post("https://cliq.zoho.com/api/v2/chats/C1/messages/unpin").mock(
        return_value=httpx.Response(401, json=scope_error)
    )
    respx.post("https://cliq.zoho.com/api/v2/chats/C1/settings/unpin").mock(
        return_value=httpx.Response(401, json=scope_error)
    )
    respx.patch("https://cliq.zoho.com/api/v2/chats/C1/settings").mock(
        return_value=httpx.Response(401, json=scope_error)
    )
    respx.put("https://cliq.zoho.com/api/v2/chats/C1/settings").mock(
        return_value=httpx.Response(401, json=scope_error)
    )

    with pytest.raises(SystemExit):
        client.set_chat_pin(chat_id="C1", pinned=False)

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Channels.UPDATE" in err


@respx.mock
def test_cliq_client_list_thread_followers_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get(url__regex=r"https://cliq\.zoho\.com/api/v2/chats/C1/.*").mock(
        return_value=httpx.Response(
            401,
            json={
                "code": "oauthtoken_scope_invalid",
                "message": "scope missing",
            },
        )
    )

    with pytest.raises(SystemExit):
        client.list_thread_followers("T1", chat_id="C1")

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Messages.READ" in err


@respx.mock
def test_cliq_client_update_thread_state(client: cliq.ZohoCliqClient) -> None:
    route = respx.post("https://cliq.zoho.com/api/v2/chats/C1/threads/T1/state").mock(
        return_value=httpx.Response(200, json={"data": {"state": "closed"}})
    )

    payload = client.update_thread_state("T1", "closed", chat_id="C1")
    assert route.called
    assert payload["data"]["state"] == "closed"


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


@respx.mock
def test_cliq_client_probe_capabilities_with_message_context(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/channels").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    respx.get("https://cliq.zoho.com/api/v2/users").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(200, json={"data": {"chat_id": "CT_1"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/O1/messages").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M1"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/files").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/attachments").mock(
        return_value=httpx.Response(401, json={"code": "oauthtoken_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/O1/messages/M1").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M1"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/O1/messages/M1/files").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/O1/messages/M1/attachments").mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    result = client.probe_capabilities(channel_id="O1", message_id="M1")

    checks = {item["name"]: item for item in result["checks"]}
    assert checks["chats.messages.get"]["ok"] is True
    assert checks["chats.messages.files"]["status"] == "not_supported"
    assert checks["chats.messages.attachments"]["status"] == "forbidden_or_scope"
    assert checks["channels.messages.attachments"]["ok"] is True


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
