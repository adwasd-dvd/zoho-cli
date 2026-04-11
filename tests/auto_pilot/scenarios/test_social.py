from __future__ import annotations

from typing import Any

from zoho_cli.cliq import ZohoCliqClient


def test_get_all_users_full_pagination(monkeypatch) -> None:
    client = ZohoCliqClient("test-token", base_url="https://cliq.zoho.com/api/v2")

    calls: list[dict[str, Any]] = []

    def fake_get(path: str, params: dict | None = None) -> dict:
        params = params or {}
        calls.append({"path": path, "params": dict(params)})
        token = params.get("next_page_token")
        if token == "page-2":
            return {
                "data": [{"id": "u3", "name": "Charlie"}],
                "has_more": False,
            }
        return {
            "data": [{"id": "u1", "name": "Alice"}, {"id": "u2", "name": "Bob"}],
            "has_more": True,
            "next_page_token": "page-2",
        }

    monkeypatch.setattr(client, "_get", fake_get)

    users = client.get_all_users(limit=50)

    assert [u["id"] for u in users] == ["u1", "u2", "u3"]
    assert calls[0]["path"] == "/users"
    assert calls[0]["params"]["limit"] == 50
    assert calls[1]["params"]["next_page_token"] == "page-2"


def test_get_dm_history_full_pagination(monkeypatch) -> None:
    client = ZohoCliqClient("test-token", base_url="https://cliq.zoho.com/api/v2")

    def fake_get(path: str, params: dict | None = None) -> dict:
        params = params or {}
        token = params.get("next_page_token")
        if token == "dm-page-2":
            return {
                "data": [{"id": "m3", "text": "page2"}],
                "has_more": False,
            }
        return {
            "data": [{"id": "m1", "text": "hello"}, {"id": "m2", "text": "world"}],
            "has_more": True,
            "next_page_token": "dm-page-2",
        }

    monkeypatch.setattr(client, "_get", fake_get)

    history = client.get_dm_history("user-123", limit=25)

    assert [m["id"] for m in history] == ["m1", "m2", "m3"]


def test_get_channel_history_via_channel_resolution(monkeypatch) -> None:
    client = ZohoCliqClient("test-token", base_url="https://cliq.zoho.com/api/v2")

    monkeypatch.setattr(client, "resolve_chat_id", lambda channel_id: "chat-9001")

    def fake_get(path: str, params: dict | None = None) -> dict:
        assert path == "/chats/chat-9001/messages"
        return {
            "data": [{"id": "c1", "text": "group-msg"}],
            "has_more": False,
        }

    monkeypatch.setattr(client, "_get", fake_get)

    messages = client.get_chat_history(channel_id="channel-1", limit=100)

    assert len(messages) == 1
    assert messages[0]["id"] == "c1"
