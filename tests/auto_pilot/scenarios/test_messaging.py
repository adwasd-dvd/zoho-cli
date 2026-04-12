from __future__ import annotations

import httpx
import respx

from zoho_cli.cliq import ZohoCliqClient


@respx.mock
def test_send_text_message_to_channel_fallback() -> None:
    client = ZohoCliqClient("fake-token", base_url="https://cliq.zoho.com/api/v2")

    respx.get("https://cliq.zoho.com/api/v2/channels/C1").mock(
        return_value=httpx.Response(404, text="not_found")
    )
    respx.post("https://cliq.zoho.com/api/v2/channelsbyname/C1/message").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    route = respx.post("https://cliq.zoho.com/api/v2/chats/C1/message").mock(
        return_value=httpx.Response(200, json={"data": {"status": "ok"}})
    )

    result = client.send_message("hello from auto-pilot", channel_id="C1")

    assert route.called
    assert result["data"]["status"] == "ok"


@respx.mock
def test_send_media_message_local_file_to_channel(tmp_path) -> None:
    client = ZohoCliqClient("fake-token", base_url="https://cliq.zoho.com/api/v2")
    media_file = tmp_path / "demo.png"
    media_file.write_bytes(b"fake-image-bytes")

    respx.get("https://cliq.zoho.com/api/v2/channels/C1").mock(
        return_value=httpx.Response(404, text="not_found")
    )
    respx.post("https://cliq.zoho.com/api/v2/chats/C1/message").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.post("https://cliq.zoho.com/api/v2/chats/C1/messages").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.post("https://cliq.zoho.com/api/v2/channels/C1/message").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.post("https://cliq.zoho.com/api/v2/channels/C1/messages").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    route = respx.post("https://cliq.zoho.com/api/v2/chats/C1/files").mock(
        return_value=httpx.Response(200, json={"data": {"status": "ok"}})
    )

    result = client.send_local_file_message(
        str(media_file),
        text="media test",
        channel_id="C1",
        media_kind="image",
    )

    assert route.called
    assert result["data"]["status"] == "ok"
    assert result["data"]["upload"]["path"] == "/chats/C1/files"
    assert result["data"]["upload"]["fileName"] == "demo.png"
