"""Tests for zoho_cli.cliq helpers."""

import itertools
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
def client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> cliq.ZohoCliqClient:
    monkeypatch.setenv(
        "ZOHO_CLIQ_UNSUPPORTED_TRACKER_PATH",
        str(tmp_path / "cliq_unsupported_tracker.json"),
    )
    monkeypatch.delenv("ZOHO_CLIQ_UNSUPPORTED_THRESHOLD", raising=False)
    monkeypatch.delenv("ZOHO_CLIQ_FORCE_UNSUPPORTED_RECHECK", raising=False)
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
def test_cliq_client_list_teams_falls_back_to_admin_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    teams_route = respx.get("https://cliq.zoho.com/api/v2/teams").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_route = respx.get("https://cliq.zoho.com/api/v2/admin/teams").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "team_id": "TM_1",
                        "name": "Ops",
                    }
                ]
            },
        )
    )

    result = client.list_teams(limit=4)

    assert teams_route.called
    assert admin_route.called
    assert dict(admin_route.calls.last.request.url.params) == {"limit": "4"}
    assert result["data"][0]["team_id"] == "TM_1"


@respx.mock
def test_cliq_client_list_teams_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/teams").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/teams").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )

    with pytest.raises(SystemExit):
        client.list_teams(limit=4)

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Teams.READ" in err


@respx.mock
def test_cliq_client_list_teams_three_strike_not_supported_deferred(
    client: cliq.ZohoCliqClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tracker_path = tmp_path / "cliq_unsupported_tracker.json"
    monkeypatch.setenv("ZOHO_CLIQ_UNSUPPORTED_TRACKER_PATH", str(tracker_path))
    monkeypatch.setenv("ZOHO_CLIQ_UNSUPPORTED_THRESHOLD", "3")
    monkeypatch.delenv("ZOHO_CLIQ_FORCE_UNSUPPORTED_RECHECK", raising=False)

    respx.get("https://cliq.zoho.com/api/v2/teams").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/teams").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )

    errors: list[str] = []
    for _ in range(3):
        with pytest.raises(SystemExit):
            client.list_teams(limit=4)
        errors.append(capsys.readouterr().err)

    assert "post-release deferred" not in errors[0].lower()
    assert "post-release deferred" in errors[2].lower()

    tracker_payload = json.loads(tracker_path.read_text(encoding="utf-8"))
    key = client._unsupported_operation_key("teams-list")
    entry = tracker_payload["operations"][key]
    assert entry["unsupportedConsecutiveCount"] == 3
    assert entry["postReleaseDeferred"] is True


@respx.mock
def test_cliq_client_list_teams_inactive_appaccount_three_strike_deferred(
    client: cliq.ZohoCliqClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tracker_path = tmp_path / "cliq_unsupported_tracker.json"
    monkeypatch.setenv("ZOHO_CLIQ_UNSUPPORTED_TRACKER_PATH", str(tracker_path))
    monkeypatch.setenv("ZOHO_CLIQ_UNSUPPORTED_THRESHOLD", "3")
    monkeypatch.delenv("ZOHO_CLIQ_FORCE_UNSUPPORTED_RECHECK", raising=False)

    respx.get("https://cliq.zoho.com/api/v2/teams").mock(
        return_value=httpx.Response(403, json={"code": "inactive_appaccount_user"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/teams").mock(
        return_value=httpx.Response(403, json={"code": "inactive_appaccount_user"})
    )

    errors: list[str] = []
    for _ in range(3):
        with pytest.raises(SystemExit):
            client.list_teams(limit=4)
        errors.append(capsys.readouterr().err)

    assert "inactive_appaccount_user" in errors[0]
    assert "post-release deferred" not in errors[0].lower()
    assert "inactive_appaccount_user" in errors[2]
    assert "post-release deferred" in errors[2].lower()

    tracker_payload = json.loads(tracker_path.read_text(encoding="utf-8"))
    key = client._unsupported_operation_key("teams-list")
    entry = tracker_payload["operations"][key]
    assert entry["unsupportedConsecutiveCount"] == 3
    assert entry["postReleaseDeferred"] is True
    assert entry["lastUnsupportedSignal"] == "inactive_appaccount_user"


def test_cliq_client_list_teams_deferred_guard_blocks_http_calls(
    client: cliq.ZohoCliqClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tracker_path = tmp_path / "cliq_unsupported_tracker.json"
    monkeypatch.setenv("ZOHO_CLIQ_UNSUPPORTED_TRACKER_PATH", str(tracker_path))
    monkeypatch.delenv("ZOHO_CLIQ_FORCE_UNSUPPORTED_RECHECK", raising=False)

    key = client._unsupported_operation_key("teams-list")
    tracker_path.write_text(
        json.dumps(
            {
                "version": 1,
                "operations": {
                    key: {
                        "unsupportedConsecutiveCount": 3,
                        "unsupportedThreshold": 3,
                        "postReleaseDeferred": True,
                        "lastUnsupportedSignal": "not_supported",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    def _unexpected_http_get(*args: object, **kwargs: object) -> httpx.Response:
        raise AssertionError("HTTP GET should not run for deferred operations")

    monkeypatch.setattr(cliq.httpx, "get", _unexpected_http_get)

    with pytest.raises(SystemExit):
        client.list_teams(limit=4)

    err = capsys.readouterr().err
    assert "post-release deferred" in err.lower()


def test_cliq_client_list_teams_deferred_guard_uses_last_unsupported_signal(
    client: cliq.ZohoCliqClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tracker_path = tmp_path / "cliq_unsupported_tracker.json"
    monkeypatch.setenv("ZOHO_CLIQ_UNSUPPORTED_TRACKER_PATH", str(tracker_path))
    monkeypatch.delenv("ZOHO_CLIQ_FORCE_UNSUPPORTED_RECHECK", raising=False)

    key = client._unsupported_operation_key("teams-list")
    tracker_path.write_text(
        json.dumps(
            {
                "version": 1,
                "operations": {
                    key: {
                        "unsupportedConsecutiveCount": 3,
                        "unsupportedThreshold": 3,
                        "postReleaseDeferred": True,
                        "lastUnsupportedSignal": "inactive_appaccount_user",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    def _unexpected_http_get(*args: object, **kwargs: object) -> httpx.Response:
        raise AssertionError("HTTP GET should not run for deferred operations")

    monkeypatch.setattr(cliq.httpx, "get", _unexpected_http_get)

    with pytest.raises(SystemExit):
        client.list_teams(limit=4)

    err = capsys.readouterr().err
    assert "inactive_appaccount_user" in err
    assert "post-release deferred" in err.lower()


@respx.mock
def test_cliq_client_list_teams_success_clears_unsupported_counter(
    client: cliq.ZohoCliqClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tracker_path = tmp_path / "cliq_unsupported_tracker.json"
    monkeypatch.setenv("ZOHO_CLIQ_UNSUPPORTED_TRACKER_PATH", str(tracker_path))

    key = client._unsupported_operation_key("teams-list")
    tracker_path.write_text(
        json.dumps(
            {
                "version": 1,
                "operations": {
                    key: {
                        "unsupportedConsecutiveCount": 2,
                        "unsupportedThreshold": 3,
                        "postReleaseDeferred": False,
                        "lastUnsupportedSignal": "not_supported",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    respx.get("https://cliq.zoho.com/api/v2/teams").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "team_id": "TM_1",
                        "name": "Ops",
                    }
                ]
            },
        )
    )

    result = client.list_teams(limit=4)
    assert result["data"][0]["team_id"] == "TM_1"

    tracker_payload = json.loads(tracker_path.read_text(encoding="utf-8"))
    entry = tracker_payload["operations"][key]
    assert entry["unsupportedConsecutiveCount"] == 0
    assert entry["postReleaseDeferred"] is False


@respx.mock
def test_cliq_client_export_chat_messages_inactive_three_strike_deferred(
    client: cliq.ZohoCliqClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tracker_path = tmp_path / "cliq_unsupported_tracker.json"
    monkeypatch.setenv("ZOHO_CLIQ_UNSUPPORTED_TRACKER_PATH", str(tracker_path))
    monkeypatch.setenv("ZOHO_CLIQ_UNSUPPORTED_THRESHOLD", "3")
    monkeypatch.delenv("ZOHO_CLIQ_FORCE_UNSUPPORTED_RECHECK", raising=False)

    respx.get("https://cliq.zoho.com/maintenanceapi/v2/chats/CT_1/messages").mock(
        return_value=httpx.Response(403, json={"code": "inactive_appaccount_user"})
    )

    errors: list[str] = []
    for _ in range(3):
        with pytest.raises(SystemExit):
            client.export_chat_messages("CT_1")
        errors.append(capsys.readouterr().err)

    assert "post-release deferred" not in errors[0].lower()
    assert "post-release deferred" in errors[2].lower()

    tracker_payload = json.loads(tracker_path.read_text(encoding="utf-8"))
    key = client._unsupported_operation_key("export-chat-messages")
    entry = tracker_payload["operations"][key]
    assert entry["unsupportedConsecutiveCount"] == 3
    assert entry["postReleaseDeferred"] is True
    assert entry["lastUnsupportedSignal"] == "inactive_appaccount_user"


@respx.mock
def test_cliq_client_list_departments_falls_back_to_admin_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    departments_route = respx.get("https://cliq.zoho.com/api/v2/departments").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_route = respx.get("https://cliq.zoho.com/api/v2/admin/departments").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "department_id": "DP_1",
                        "name": "Operations",
                    }
                ]
            },
        )
    )

    result = client.list_departments(limit=5)

    assert departments_route.called
    assert admin_route.called
    assert dict(admin_route.calls.last.request.url.params) == {"limit": "5"}
    assert result["data"][0]["department_id"] == "DP_1"


@respx.mock
def test_cliq_client_list_departments_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/departments").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/departments").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )

    with pytest.raises(SystemExit):
        client.list_departments(limit=5)

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Departments.READ" in err


@respx.mock
def test_cliq_client_list_roles_falls_back_to_admin_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    roles_route = respx.get("https://cliq.zoho.com/api/v2/roles").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_route = respx.get("https://cliq.zoho.com/api/v2/admin/roles").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "role_id": "RL_1",
                        "name": "Manager",
                    }
                ]
            },
        )
    )

    result = client.list_roles(limit=6)

    assert roles_route.called
    assert admin_route.called
    assert dict(admin_route.calls.last.request.url.params) == {"limit": "6"}
    assert result["data"][0]["role_id"] == "RL_1"


@respx.mock
def test_cliq_client_list_roles_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/roles").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/roles").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )

    with pytest.raises(SystemExit):
        client.list_roles(limit=6)

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Roles.READ" in err


@respx.mock
def test_cliq_client_list_designations_falls_back_to_admin_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    designations_route = respx.get("https://cliq.zoho.com/api/v2/designations").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_route = respx.get("https://cliq.zoho.com/api/v2/admin/designations").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "designation_id": "DG_1",
                        "name": "Shift Lead",
                    }
                ]
            },
        )
    )

    result = client.list_designations(limit=7)

    assert designations_route.called
    assert admin_route.called
    assert dict(admin_route.calls.last.request.url.params) == {"limit": "7"}
    assert result["data"][0]["designation_id"] == "DG_1"


@respx.mock
def test_cliq_client_list_designations_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/designations").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/designations").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )

    with pytest.raises(SystemExit):
        client.list_designations(limit=7)

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Designations.READ" in err


@respx.mock
def test_cliq_client_list_user_statuses_falls_back_to_admin_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    statuses_route = respx.get("https://cliq.zoho.com/api/v2/userstatus").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_route = respx.get("https://cliq.zoho.com/api/v2/admin/userstatus").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "status_id": "ST_1",
                        "name": "Available",
                    }
                ]
            },
        )
    )

    result = client.list_user_statuses(limit=8)

    assert statuses_route.called
    assert admin_route.called
    assert dict(admin_route.calls.last.request.url.params) == {"limit": "8"}
    assert result["data"][0]["status_id"] == "ST_1"


@respx.mock
def test_cliq_client_list_user_statuses_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/userstatus").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/userstatus").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )

    with pytest.raises(SystemExit):
        client.list_user_statuses(limit=8)

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Statuses.READ" in err


@respx.mock
def test_cliq_client_list_user_fields_falls_back_to_admin_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    fields_route = respx.get("https://cliq.zoho.com/api/v2/userfields").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_route = respx.get("https://cliq.zoho.com/api/v2/admin/userfields").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "field_id": "UF_1",
                        "label": "Department",
                        "field_type": "text",
                    }
                ]
            },
        )
    )

    result = client.list_user_fields(limit=9)

    assert fields_route.called
    assert admin_route.called
    assert dict(admin_route.calls.last.request.url.params) == {"limit": "9"}
    assert result["data"][0]["field_id"] == "UF_1"


@respx.mock
def test_cliq_client_list_user_fields_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/userfields").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/userfields").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )

    with pytest.raises(SystemExit):
        client.list_user_fields(limit=9)

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.UserFields.READ" in err


@respx.mock
def test_cliq_client_list_events_falls_back_to_admin_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    events_route = respx.get("https://cliq.zoho.com/api/v2/events").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_route = respx.get("https://cliq.zoho.com/api/v2/admin/events").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "event_id": "EV_1",
                        "title": "Daily Sync",
                    }
                ]
            },
        )
    )

    result = client.list_events(limit=11)

    assert events_route.called
    assert admin_route.called
    assert dict(admin_route.calls.last.request.url.params) == {"limit": "11"}
    assert result["data"][0]["event_id"] == "EV_1"


@respx.mock
def test_cliq_client_list_events_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/events").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/events").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )

    with pytest.raises(SystemExit):
        client.list_events(limit=11)

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Events.READ" in err


@respx.mock
def test_cliq_client_list_reminders_falls_back_to_admin_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    reminders_route = respx.get("https://cliq.zoho.com/api/v2/reminders").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_route = respx.get("https://cliq.zoho.com/api/v2/admin/reminders").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "reminder_id": "RM_1",
                        "title": "Standup Reminder",
                    }
                ]
            },
        )
    )

    result = client.list_reminders(limit=13)

    assert reminders_route.called
    assert admin_route.called
    assert dict(admin_route.calls.last.request.url.params) == {"limit": "13"}
    assert result["data"][0]["reminder_id"] == "RM_1"


@respx.mock
def test_cliq_client_list_reminders_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/reminders").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/reminders").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )

    with pytest.raises(SystemExit):
        client.list_reminders(limit=13)

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Reminders.READ" in err


@respx.mock
def test_cliq_client_list_meetings_falls_back_to_admin_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    meetings_route = respx.get("https://cliq.zoho.com/api/v2/meetings").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    calls_route = respx.get("https://cliq.zoho.com/api/v2/calls").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_route = respx.get("https://cliq.zoho.com/api/v2/admin/meetings").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "meeting_id": "MT_1",
                        "title": "Sprint Sync",
                    }
                ]
            },
        )
    )

    result = client.list_meetings(limit=15)

    assert meetings_route.called
    assert calls_route.called
    assert admin_route.called
    assert dict(admin_route.calls.last.request.url.params) == {"limit": "15"}
    assert result["data"][0]["meeting_id"] == "MT_1"


@respx.mock
def test_cliq_client_list_meetings_falls_back_to_calls_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    meetings_route = respx.get("https://cliq.zoho.com/api/v2/meetings").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    calls_route = respx.get("https://cliq.zoho.com/api/v2/calls").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "call_id": "CL_1",
                        "title": "Ops Escalation",
                    }
                ]
            },
        )
    )

    result = client.list_meetings(limit=16)

    assert meetings_route.called
    assert calls_route.called
    assert dict(calls_route.calls.last.request.url.params) == {"limit": "16"}
    assert result["data"][0]["call_id"] == "CL_1"


@respx.mock
def test_cliq_client_list_meetings_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/meetings").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/calls").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/meetings").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/calls").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )

    with pytest.raises(SystemExit):
        client.list_meetings(limit=15)

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Calls.READ" in err


@respx.mock
def test_cliq_client_list_databases_falls_back_to_admin_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    databases_route = respx.get("https://cliq.zoho.com/api/v2/databases").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    database_route = respx.get("https://cliq.zoho.com/api/v2/database").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_route = respx.get("https://cliq.zoho.com/api/v2/admin/databases").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "database_id": "DB_1",
                        "name": "Operations DB",
                    }
                ]
            },
        )
    )

    result = client.list_databases(limit=17)

    assert databases_route.called
    assert database_route.called
    assert admin_route.called
    assert dict(admin_route.calls.last.request.url.params) == {"limit": "17"}
    assert result["data"][0]["database_id"] == "DB_1"


@respx.mock
def test_cliq_client_list_databases_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/databases").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/database").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/databases").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )

    with pytest.raises(SystemExit):
        client.list_databases(limit=17)

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Databases.READ" in err


@respx.mock
def test_cliq_client_list_widgets_falls_back_to_admin_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    widgets_route = respx.get("https://cliq.zoho.com/api/v2/widgets").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    widget_route = respx.get("https://cliq.zoho.com/api/v2/widget").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_route = respx.get("https://cliq.zoho.com/api/v2/admin/widgets").mock(
        return_value=httpx.Response(200, json={"data": [{"widget_id": "WG_1"}]})
    )

    result = client.list_widgets(limit=19)

    assert widgets_route.called
    assert widget_route.called
    assert admin_route.called
    assert dict(admin_route.calls.last.request.url.params) == {"limit": "19"}
    assert result["data"][0]["widget_id"] == "WG_1"


@respx.mock
def test_cliq_client_list_widgets_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/widgets").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/widget").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/widgets").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )

    with pytest.raises(SystemExit):
        client.list_widgets(limit=19)

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Widgets.READ" in err


@respx.mock
def test_cliq_client_list_map_tickers_falls_back_to_admin_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    map_tickers_route = respx.get("https://cliq.zoho.com/api/v2/map/tickers").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    map_ticker_route = respx.get("https://cliq.zoho.com/api/v2/map/ticker").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_route = respx.get("https://cliq.zoho.com/api/v2/admin/map/tickers").mock(
        return_value=httpx.Response(200, json={"data": [{"ticker_id": "TK_1"}]})
    )

    result = client.list_map_tickers(limit=23)

    assert map_tickers_route.called
    assert map_ticker_route.called
    assert admin_route.called
    assert dict(admin_route.calls.last.request.url.params) == {"limit": "23"}
    assert result["data"][0]["ticker_id"] == "TK_1"


@respx.mock
def test_cliq_client_list_map_tickers_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/map/tickers").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/map/ticker").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/map/tickers").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/map/ticker").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )

    with pytest.raises(SystemExit):
        client.list_map_tickers(limit=23)

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Tickers.READ" in err


@respx.mock
def test_cliq_client_list_custom_domains_falls_back_to_admin_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    plural_route = respx.get("https://cliq.zoho.com/api/v2/customdomains").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    singular_route = respx.get("https://cliq.zoho.com/api/v2/customdomain").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_route = respx.get("https://cliq.zoho.com/api/v2/admin/customdomains").mock(
        return_value=httpx.Response(200, json={"data": [{"domain_id": "CD_1"}]})
    )

    result = client.list_custom_domains(limit=29)

    assert plural_route.called
    assert singular_route.called
    assert admin_route.called
    assert dict(admin_route.calls.last.request.url.params) == {"limit": "29"}
    assert result["data"][0]["domain_id"] == "CD_1"


@respx.mock
def test_cliq_client_list_custom_domains_falls_back_to_admin_singular_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/customdomains").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/customdomain").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_plural = respx.get("https://cliq.zoho.com/api/v2/admin/customdomains").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_singular = respx.get("https://cliq.zoho.com/api/v2/admin/customdomain").mock(
        return_value=httpx.Response(200, json={"data": [{"domain_id": "CD_2"}]})
    )

    result = client.list_custom_domains(limit=41)

    assert admin_plural.called
    assert admin_singular.called
    assert dict(admin_singular.calls.last.request.url.params) == {"limit": "41"}
    assert result["data"][0]["domain_id"] == "CD_2"


@respx.mock
def test_cliq_client_list_custom_domains_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/customdomains").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/customdomain").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/customdomains").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/customdomain").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )

    with pytest.raises(SystemExit):
        client.list_custom_domains(limit=29)

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.CustomDomains.READ" in err


@respx.mock
def test_cliq_client_list_custom_emails_falls_back_to_admin_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    plural_route = respx.get("https://cliq.zoho.com/api/v2/customemails").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    singular_route = respx.get("https://cliq.zoho.com/api/v2/customemail").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_route = respx.get("https://cliq.zoho.com/api/v2/admin/customemails").mock(
        return_value=httpx.Response(200, json={"data": [{"email_id": "CE_1"}]})
    )

    result = client.list_custom_emails(limit=31)

    assert plural_route.called
    assert singular_route.called
    assert admin_route.called
    assert dict(admin_route.calls.last.request.url.params) == {"limit": "31"}
    assert result["data"][0]["email_id"] == "CE_1"


@respx.mock
def test_cliq_client_list_custom_emails_falls_back_to_admin_singular_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/customemails").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/customemail").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_plural = respx.get("https://cliq.zoho.com/api/v2/admin/customemails").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_singular = respx.get("https://cliq.zoho.com/api/v2/admin/customemail").mock(
        return_value=httpx.Response(200, json={"data": [{"email_id": "CE_2"}]})
    )

    result = client.list_custom_emails(limit=43)

    assert admin_plural.called
    assert admin_singular.called
    assert dict(admin_singular.calls.last.request.url.params) == {"limit": "43"}
    assert result["data"][0]["email_id"] == "CE_2"


@respx.mock
def test_cliq_client_list_custom_emails_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/customemails").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/customemail").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/customemails").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/customemail").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )

    with pytest.raises(SystemExit):
        client.list_custom_emails(limit=31)

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.CustomEmails.READ" in err


@respx.mock
def test_cliq_client_list_apps_falls_back_to_admin_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    apps_route = respx.get("https://cliq.zoho.com/api/v2/apps").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    singular_route = respx.get("https://cliq.zoho.com/api/v2/app").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_route = respx.get("https://cliq.zoho.com/api/v2/admin/apps").mock(
        return_value=httpx.Response(200, json={"data": [{"app_id": "AP_1"}]})
    )

    result = client.list_apps(limit=37)

    assert apps_route.called
    assert singular_route.called
    assert admin_route.called
    assert dict(admin_route.calls.last.request.url.params) == {"limit": "37"}
    assert result["data"][0]["app_id"] == "AP_1"


@respx.mock
def test_cliq_client_list_apps_falls_back_to_admin_singular_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/apps").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/app").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_plural = respx.get("https://cliq.zoho.com/api/v2/admin/apps").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_singular = respx.get("https://cliq.zoho.com/api/v2/admin/app").mock(
        return_value=httpx.Response(200, json={"data": [{"app_id": "AP_2"}]})
    )

    result = client.list_apps(limit=41)

    assert admin_plural.called
    assert admin_singular.called
    assert dict(admin_singular.calls.last.request.url.params) == {"limit": "41"}
    assert result["data"][0]["app_id"] == "AP_2"


@respx.mock
def test_cliq_client_list_apps_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/apps").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/app").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/apps").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/app").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )

    with pytest.raises(SystemExit):
        client.list_apps(limit=37)

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Apps.READ" in err


@respx.mock
def test_cliq_client_get_app_falls_back_to_admin_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    apps_route = respx.get("https://cliq.zoho.com/api/v2/apps/AP_1").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    singular_route = respx.get("https://cliq.zoho.com/api/v2/app/AP_1").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_route = respx.get("https://cliq.zoho.com/api/v2/admin/apps/AP_1").mock(
        return_value=httpx.Response(200, json={"data": {"app_id": "AP_1"}})
    )

    result = client.get_app("AP_1")

    assert apps_route.called
    assert singular_route.called
    assert admin_route.called
    assert result["data"]["app_id"] == "AP_1"


@respx.mock
def test_cliq_client_get_app_falls_back_to_admin_singular_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/apps/AP_2").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/app/AP_2").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_plural = respx.get("https://cliq.zoho.com/api/v2/admin/apps/AP_2").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_singular = respx.get("https://cliq.zoho.com/api/v2/admin/app/AP_2").mock(
        return_value=httpx.Response(200, json={"data": {"app_id": "AP_2"}})
    )

    result = client.get_app("AP_2")

    assert admin_plural.called
    assert admin_singular.called
    assert result["data"]["app_id"] == "AP_2"


@respx.mock
def test_cliq_client_get_app_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/apps/AP_3").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/app/AP_3").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/apps/AP_3").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/app/AP_3").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )

    with pytest.raises(SystemExit):
        client.get_app("AP_3")

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Apps.READ" in err


@respx.mock
def test_cliq_client_list_app_permissions_falls_back_to_admin_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    apps_route = respx.get("https://cliq.zoho.com/api/v2/apps/AP_1/permissions").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    singular_route = respx.get(
        "https://cliq.zoho.com/api/v2/app/AP_1/permissions"
    ).mock(return_value=httpx.Response(404, text="request_url_invalid"))
    admin_route = respx.get(
        "https://cliq.zoho.com/api/v2/admin/apps/AP_1/permissions"
    ).mock(return_value=httpx.Response(200, json={"data": [{"permission_id": "P_1"}]}))

    result = client.list_app_permissions("AP_1", limit=23)

    assert apps_route.called
    assert singular_route.called
    assert admin_route.called
    assert dict(admin_route.calls.last.request.url.params) == {"limit": "23"}
    assert result["data"][0]["permission_id"] == "P_1"


@respx.mock
def test_cliq_client_list_app_permissions_falls_back_to_admin_singular_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/apps/AP_2/permissions").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/app/AP_2/permissions").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_plural = respx.get(
        "https://cliq.zoho.com/api/v2/admin/apps/AP_2/permissions"
    ).mock(return_value=httpx.Response(404, text="request_url_invalid"))
    admin_singular = respx.get(
        "https://cliq.zoho.com/api/v2/admin/app/AP_2/permissions"
    ).mock(return_value=httpx.Response(200, json={"data": [{"permission_id": "P_2"}]}))

    result = client.list_app_permissions("AP_2", limit=29)

    assert admin_plural.called
    assert admin_singular.called
    assert dict(admin_singular.calls.last.request.url.params) == {"limit": "29"}
    assert result["data"][0]["permission_id"] == "P_2"


@respx.mock
def test_cliq_client_list_app_permissions_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/apps/AP_3/permissions").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/app/AP_3/permissions").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/apps/AP_3/permissions").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/app/AP_3/permissions").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )

    with pytest.raises(SystemExit):
        client.list_app_permissions("AP_3", limit=31)

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Apps.READ" in err


@respx.mock
def test_cliq_client_get_app_permission_falls_back_to_admin_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/apps/AP_4/permissions/P_1").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/app/AP_4/permissions/P_1").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    route = respx.get(
        "https://cliq.zoho.com/api/v2/admin/apps/AP_4/permissions/P_1"
    ).mock(
        return_value=httpx.Response(
            200,
            json={"data": {"permission_id": "P_1", "scope": "ZohoCliq.Apps.READ"}},
        )
    )

    payload = client.get_app_permission("AP_4", "P_1")

    assert route.called
    assert payload["data"]["permission_id"] == "P_1"


@respx.mock
def test_cliq_client_get_app_permission_falls_back_to_admin_singular_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/apps/AP_4/permissions/P_2").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/app/AP_4/permissions/P_2").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/apps/AP_4/permissions/P_2").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    route = respx.get(
        "https://cliq.zoho.com/api/v2/admin/app/AP_4/permissions/P_2"
    ).mock(
        return_value=httpx.Response(
            200,
            json={"data": {"permissionId": "P_2", "scope": "ZohoCliq.Messages.READ"}},
        )
    )

    payload = client.get_app_permission("AP_4", "P_2")

    assert route.called
    assert payload["data"]["permissionId"] == "P_2"


@respx.mock
def test_cliq_client_get_app_permission_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    scope_error = {
        "code": "oauthtoken_scope_invalid",
        "message": "scope missing",
    }
    respx.get("https://cliq.zoho.com/api/v2/apps/AP_4/permissions/P_3").mock(
        return_value=httpx.Response(401, json=scope_error)
    )
    respx.get("https://cliq.zoho.com/api/v2/app/AP_4/permissions/P_3").mock(
        return_value=httpx.Response(401, json=scope_error)
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/apps/AP_4/permissions/P_3").mock(
        return_value=httpx.Response(401, json=scope_error)
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/app/AP_4/permissions/P_3").mock(
        return_value=httpx.Response(401, json=scope_error)
    )

    with pytest.raises(SystemExit):
        client.get_app_permission("AP_4", "P_3")

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Apps.READ" in err


@respx.mock
def test_cliq_client_list_app_installs_falls_back_to_admin_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    apps_route = respx.get("https://cliq.zoho.com/api/v2/apps/AP_1/installs").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    singular_route = respx.get("https://cliq.zoho.com/api/v2/app/AP_1/installs").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_route = respx.get(
        "https://cliq.zoho.com/api/v2/admin/apps/AP_1/installs"
    ).mock(return_value=httpx.Response(200, json={"data": [{"install_id": "I_1"}]}))

    result = client.list_app_installs("AP_1", limit=17)

    assert apps_route.called
    assert singular_route.called
    assert admin_route.called
    assert dict(admin_route.calls.last.request.url.params) == {"limit": "17"}
    assert result["data"][0]["install_id"] == "I_1"


@respx.mock
def test_cliq_client_list_app_installs_falls_back_to_admin_singular_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/apps/AP_2/installs").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/app/AP_2/installs").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_plural = respx.get(
        "https://cliq.zoho.com/api/v2/admin/apps/AP_2/installs"
    ).mock(return_value=httpx.Response(404, text="request_url_invalid"))
    admin_singular = respx.get(
        "https://cliq.zoho.com/api/v2/admin/app/AP_2/installs"
    ).mock(return_value=httpx.Response(200, json={"data": [{"install_id": "I_2"}]}))

    result = client.list_app_installs("AP_2", limit=19)

    assert admin_plural.called
    assert admin_singular.called
    assert dict(admin_singular.calls.last.request.url.params) == {"limit": "19"}
    assert result["data"][0]["install_id"] == "I_2"


@respx.mock
def test_cliq_client_list_app_installs_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/apps/AP_3/installs").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/app/AP_3/installs").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/apps/AP_3/installs").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/app/AP_3/installs").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )

    with pytest.raises(SystemExit):
        client.list_app_installs("AP_3", limit=23)

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Apps.READ" in err


@respx.mock
def test_cliq_client_get_app_install_falls_back_to_admin_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    first = respx.get("https://cliq.zoho.com/api/v2/apps/AP_1/installs/INS_1").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    second = respx.get("https://cliq.zoho.com/api/v2/app/AP_1/installs/INS_1").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_plural = respx.get(
        "https://cliq.zoho.com/api/v2/admin/apps/AP_1/installs/INS_1"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "id": "INS_1",
                    "name": "Ops Relay",
                    "status": "enabled",
                }
            },
        )
    )

    result = client.get_app_install("AP_1", "INS_1")

    assert first.called
    assert second.called
    assert admin_plural.called
    assert result["data"]["id"] == "INS_1"


@respx.mock
def test_cliq_client_get_app_install_falls_back_to_admin_singular_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/apps/AP_2/installs/INS_2").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/app/AP_2/installs/INS_2").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_plural = respx.get(
        "https://cliq.zoho.com/api/v2/admin/apps/AP_2/installs/INS_2"
    ).mock(return_value=httpx.Response(404, text="request_url_invalid"))
    admin_singular = respx.get(
        "https://cliq.zoho.com/api/v2/admin/app/AP_2/installs/INS_2"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "install_id": "INS_2",
                    "display_name": "Support Bot",
                    "state": "active",
                }
            },
        )
    )

    result = client.get_app_install("AP_2", "INS_2")

    assert admin_plural.called
    assert admin_singular.called
    assert result["data"]["install_id"] == "INS_2"


@respx.mock
def test_cliq_client_get_app_install_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/apps/AP_3/installs/INS_3").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/app/AP_3/installs/INS_3").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/apps/AP_3/installs/INS_3").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/app/AP_3/installs/INS_3").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )

    with pytest.raises(SystemExit):
        client.get_app_install("AP_3", "INS_3")

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Apps.READ" in err


@respx.mock
def test_cliq_client_list_app_commands_falls_back_to_admin_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    apps_route = respx.get("https://cliq.zoho.com/api/v2/apps/AP_1/commands").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    singular_route = respx.get("https://cliq.zoho.com/api/v2/app/AP_1/commands").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_route = respx.get(
        "https://cliq.zoho.com/api/v2/admin/apps/AP_1/commands"
    ).mock(return_value=httpx.Response(200, json={"data": [{"command_id": "CMD_1"}]}))

    result = client.list_app_commands("AP_1", limit=13)

    assert apps_route.called
    assert singular_route.called
    assert admin_route.called
    assert dict(admin_route.calls.last.request.url.params) == {"limit": "13"}
    assert result["data"][0]["command_id"] == "CMD_1"


@respx.mock
def test_cliq_client_list_app_commands_falls_back_to_admin_singular_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/apps/AP_2/commands").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/app/AP_2/commands").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_plural = respx.get(
        "https://cliq.zoho.com/api/v2/admin/apps/AP_2/commands"
    ).mock(return_value=httpx.Response(404, text="request_url_invalid"))
    admin_singular = respx.get(
        "https://cliq.zoho.com/api/v2/admin/app/AP_2/commands"
    ).mock(return_value=httpx.Response(200, json={"data": [{"command_id": "CMD_2"}]}))

    result = client.list_app_commands("AP_2", limit=21)

    assert admin_plural.called
    assert admin_singular.called
    assert dict(admin_singular.calls.last.request.url.params) == {"limit": "21"}
    assert result["data"][0]["command_id"] == "CMD_2"


@respx.mock
def test_cliq_client_list_app_commands_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/apps/AP_3/commands").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/app/AP_3/commands").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/apps/AP_3/commands").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/app/AP_3/commands").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )

    with pytest.raises(SystemExit):
        client.list_app_commands("AP_3", limit=17)

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Apps.READ" in err


@respx.mock
def test_cliq_client_get_app_command_falls_back_to_admin_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    first = respx.get("https://cliq.zoho.com/api/v2/apps/AP_1/commands/CMD_1").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    second = respx.get("https://cliq.zoho.com/api/v2/app/AP_1/commands/CMD_1").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_plural = respx.get(
        "https://cliq.zoho.com/api/v2/admin/apps/AP_1/commands/CMD_1"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "id": "CMD_1",
                    "name": "daily_digest",
                    "status": "active",
                }
            },
        )
    )

    result = client.get_app_command("AP_1", "CMD_1")

    assert first.called
    assert second.called
    assert admin_plural.called
    assert result["data"]["id"] == "CMD_1"


@respx.mock
def test_cliq_client_get_app_command_falls_back_to_admin_singular_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/apps/AP_2/commands/CMD_2").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/app/AP_2/commands/CMD_2").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    admin_plural = respx.get(
        "https://cliq.zoho.com/api/v2/admin/apps/AP_2/commands/CMD_2"
    ).mock(return_value=httpx.Response(404, text="request_url_invalid"))
    admin_singular = respx.get(
        "https://cliq.zoho.com/api/v2/admin/app/AP_2/commands/CMD_2"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "command_id": "CMD_2",
                    "command": "weekly_sync",
                    "state": "enabled",
                }
            },
        )
    )

    result = client.get_app_command("AP_2", "CMD_2")

    assert admin_plural.called
    assert admin_singular.called
    assert result["data"]["command_id"] == "CMD_2"


@respx.mock
def test_cliq_client_get_app_command_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/apps/AP_3/commands/CMD_3").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/app/AP_3/commands/CMD_3").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/apps/AP_3/commands/CMD_3").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/admin/app/AP_3/commands/CMD_3").mock(
        return_value=httpx.Response(401, json={"code": "oauth_scope_invalid"})
    )

    with pytest.raises(SystemExit):
        client.get_app_command("AP_3", "CMD_3")

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Apps.READ" in err


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
    assert "zoho login --with-cliq --scope" in err
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
    assert "zoho login --with-cliq --scope" in err
    assert "ZohoCliq.OrganizationMessages.READ" in err


@respx.mock
def test_cliq_client_export_conversations_inactive_appaccount_user_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/maintenanceapi/v2/chats").mock(
        return_value=httpx.Response(403, json={"code": "inactive_appaccount_user"})
    )

    with pytest.raises(SystemExit):
        client.export_conversations()

    err = capsys.readouterr().err
    assert "inactive_appaccount_user" in err
    assert "inactive for app-account export APIs" in err


@respx.mock
def test_cliq_client_export_chat_messages_inactive_appaccount_user_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get("https://cliq.zoho.com/maintenanceapi/v2/chats/CT_1/messages").mock(
        return_value=httpx.Response(403, json={"code": "inactive_appaccount_user"})
    )

    with pytest.raises(SystemExit):
        client.export_chat_messages("CT_1")

    err = capsys.readouterr().err
    assert "inactive_appaccount_user" in err
    assert "inactive for app-account export APIs" in err


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


@respx.mock
def test_cliq_client_get_message_reactions(client: cliq.ZohoCliqClient) -> None:
    route = respx.get(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/reactions"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "emoji_code": "👀",
                        "users": [{"id": "U_SELF"}],
                    }
                ]
            },
        )
    )

    result = client.get_message_reactions("M1", chat_id="CT_1")

    assert route.called
    assert result["data"][0]["emoji_code"] == "👀"


@respx.mock
def test_cliq_client_get_message_reactions_falls_back_to_openapi_alt_path(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/reactions").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    route = respx.get(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/messages/reactions"
    ).mock(return_value=httpx.Response(200, json={"data": [{"emoji_code": "🔥"}]}))

    result = client.get_message_reactions("M1", chat_id="CT_1")

    assert route.called
    assert result["data"][0]["emoji_code"] == "🔥"


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


def test_build_watch_context_seed_includes_watch_intake_contract_metadata() -> None:
    payload = cliq.ZohoCliqClient.build_watch_context_seed(
        [
            {"id": "M2", "text": "latest"},
            {"id": "M1", "text": "older"},
        ],
        since_message_id="M1",
        max_messages=5,
    )

    assert payload["watchIntake"]["triggerMode"] == "web-notification-first"
    assert payload["watchIntake"]["pollFallback"]["mode"] == "adaptive"
    assert payload["watchIntake"]["pollFallback"]["transport"] == "api-poll"
    assert payload["watchIntake"]["consume"]["ackAction"] == "read-ack-latest"
    assert payload["watchIntake"]["consume"]["ackRequired"] is True
    assert payload["watchIntake"]["consume"]["actionId"] == "watch-loop"
    assert payload["operatorWorkflow"]["packageId"] == "cliq-195"
    assert (
        payload["operatorWorkflow"]["internalLoop"]["contractId"]
        == "cliq-195-internal-loop-v1"
    )
    assert (
        payload["operatorWorkflow"]["internalLoop"]["defaultAction"] == "reply-latest"
    )
    assert payload["operatorWorkflow"]["internalLoop"]["consumePolicy"] == {
        "ackRequired": True,
        "ackAction": "read-ack-latest",
        "actionId": "watch-loop",
    }
    assert (
        payload["operatorWorkflow"]["internalLoop"]["actionHint"]["watchActAction"]
        == "reply-latest"
    )
    assert (
        payload["operatorWorkflow"]["internalLoop"]["actionHint"]["readAckAction"]
        == "read-ack-latest"
    )
    assert (
        payload["operatorWorkflow"]["internalLoop"]["actionHint"]["bridgeActionId"]
        == "reply-latest"
    )
    assert (
        payload["operatorWorkflow"]["externalEscalation"]["defaultAction"]
        == "notify-mail"
    )
    assert payload["operatorWorkflow"]["externalEscalation"]["consumePolicy"] == {
        "ackRequired": True,
        "ackAction": "read-ack-latest",
        "actionId": "watch-loop",
    }
    assert (
        payload["operatorWorkflow"]["externalEscalation"]["actionHint"][
            "watchActAction"
        ]
        == "read-ack-latest"
    )
    assert (
        payload["operatorWorkflow"]["externalEscalation"]["actionHint"][
            "bridgeActionId"
        ]
        == "notify-mail"
    )
    assert (
        payload["operatorWorkflow"]["externalEscalation"]["handoff"]["contractId"]
        == "cliq-195-escalation-handoff-v1"
    )
    assert (
        payload["operatorWorkflow"]["externalEscalation"]["handoff"]["target"]
        == "external-contact"
    )
    assert payload["operatorWorkflow"]["externalEscalation"]["handoff"][
        "requiredFields"
    ] == ["recipient", "summary", "reason"]
    assert payload["operatorWorkflow"]["externalEscalation"]["handoff"][
        "payloadTemplate"
    ] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "recipient": "",
        "summary": "",
        "reason": "",
    }
    assert payload["operatorWorkflow"]["externalEscalation"]["handoff"][
        "envelopeHints"
    ] == {
        "templateRoot": "payloadTemplate",
        "targetPath": "payloadTemplate.target",
        "fieldMap": {
            "to": "payloadTemplate.recipient",
            "subject": "payloadTemplate.summary",
            "body": "payloadTemplate.reason",
        },
    }
    assert payload["operatorWorkflow"]["externalEscalation"]["handoff"][
        "envelopeDefaults"
    ] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "to": "",
        "subject": "",
        "body": "",
    }
    assert payload["escalationEnvelope"] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "to": "",
        "subject": "",
        "body": "",
    }
    assert payload["escalationEnvelopeMetadata"] == {
        "source": "top-level-alias",
        "sourcePath": "escalationEnvelope",
        "fromTopLevelAlias": True,
        "fromNestedFallback": False,
        "usedFieldFallback": False,
        "fieldSources": {
            "target": {
                "source": "top-level-alias",
                "sourcePath": "escalationEnvelope.target",
                "fromTopLevelAlias": True,
                "fromNestedFallback": False,
                "usedFallback": False,
            },
            "to": {
                "source": "top-level-alias",
                "sourcePath": "escalationEnvelope.to",
                "fromTopLevelAlias": True,
                "fromNestedFallback": False,
                "usedFallback": False,
            },
            "subject": {
                "source": "top-level-alias",
                "sourcePath": "escalationEnvelope.subject",
                "fromTopLevelAlias": True,
                "fromNestedFallback": False,
                "usedFallback": False,
            },
            "body": {
                "source": "top-level-alias",
                "sourcePath": "escalationEnvelope.body",
                "fromTopLevelAlias": True,
                "fromNestedFallback": False,
                "usedFallback": False,
            },
        },
    }


def test_build_watch_context_seed_internal_loop_consume_policy_matches_watch_intake_consume() -> (
    None
):
    payload = cliq.ZohoCliqClient.build_watch_context_seed(
        [{"id": "M2", "text": "latest"}, {"id": "M1", "text": "older"}],
        since_message_id="M1",
        max_messages=5,
    )

    watch_consume = payload["watchIntake"]["consume"]
    internal_loop = payload["operatorWorkflow"]["internalLoop"]
    external_escalation = payload["operatorWorkflow"]["externalEscalation"]
    assert internal_loop["consumePolicy"] == watch_consume
    assert internal_loop["mode"] == watch_consume["actionId"]
    assert (
        internal_loop["actionHint"]["watchActAction"] == internal_loop["defaultAction"]
    )
    assert (
        internal_loop["actionHint"]["bridgeActionId"] == internal_loop["defaultAction"]
    )
    assert internal_loop["actionHint"]["readAckAction"] == watch_consume["ackAction"]
    assert (
        external_escalation["actionHint"]["watchActAction"]
        == watch_consume["ackAction"]
    )
    assert external_escalation["consumePolicy"] == watch_consume
    assert (
        external_escalation["actionHint"]["bridgeActionId"]
        == external_escalation["defaultAction"]
    )


def test_build_watch_reply_action_preserves_watch_intake_metadata() -> None:
    action = cliq.ZohoCliqClient.build_watch_reply_action(
        {
            "chatId": "CT_1",
            "channelId": "O1",
            "watchIntake": {
                "triggerMode": "web-notification-first",
                "consume": {"ackAction": "read-ack-latest", "ackRequired": True},
            },
            "operatorWorkflow": {
                "packageId": "cliq-195",
                "externalEscalation": {
                    "defaultAction": "notify-mail",
                    "consumePolicy": {
                        "ackAction": "read-ack-latest",
                        "ackRequired": True,
                    },
                    "actionHint": {
                        "watchActAction": "read-ack-latest",
                        "bridgeActionId": "notify-mail",
                    },
                    "handoff": {
                        "contractId": "cliq-195-escalation-handoff-v1",
                        "requiredFields": ["recipient", "summary", "reason"],
                        "payloadTemplate": {
                            "target": {
                                "kind": "external-contact",
                                "channel": "mail",
                                "defaultAction": "notify-mail",
                            },
                            "recipient": "",
                            "summary": "",
                            "reason": "",
                        },
                        "envelopeHints": {
                            "templateRoot": "payloadTemplate",
                            "targetPath": "payloadTemplate.target",
                            "fieldMap": {
                                "to": "payloadTemplate.recipient",
                                "subject": "payloadTemplate.summary",
                                "body": "payloadTemplate.reason",
                            },
                        },
                        "envelopeDefaults": {
                            "target": {
                                "kind": "external-contact",
                                "channel": "mail",
                                "defaultAction": "notify-mail",
                            },
                            "to": "",
                            "subject": "",
                            "body": "",
                        },
                    },
                },
            },
            "messages": [
                {"messageId": "M1", "senderId": "U1", "text": "latest"},
            ],
        },
        text="ack",
    )

    assert action["watchIntake"]["triggerMode"] == "web-notification-first"
    assert action["watchIntake"]["consume"]["ackAction"] == "read-ack-latest"
    assert action["operatorWorkflow"]["packageId"] == "cliq-195"
    assert (
        action["operatorWorkflow"]["externalEscalation"]["defaultAction"]
        == "notify-mail"
    )
    assert action["operatorWorkflow"]["externalEscalation"]["consumePolicy"] == {
        "ackAction": "read-ack-latest",
        "ackRequired": True,
    }
    assert (
        action["operatorWorkflow"]["externalEscalation"]["actionHint"]["bridgeActionId"]
        == "notify-mail"
    )
    assert (
        action["operatorWorkflow"]["externalEscalation"]["handoff"]["contractId"]
        == "cliq-195-escalation-handoff-v1"
    )
    assert action["operatorWorkflow"]["externalEscalation"]["handoff"][
        "requiredFields"
    ] == ["recipient", "summary", "reason"]
    assert action["operatorWorkflow"]["externalEscalation"]["handoff"][
        "payloadTemplate"
    ] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "recipient": "",
        "summary": "",
        "reason": "",
    }
    assert action["operatorWorkflow"]["externalEscalation"]["handoff"][
        "envelopeHints"
    ] == {
        "templateRoot": "payloadTemplate",
        "targetPath": "payloadTemplate.target",
        "fieldMap": {
            "to": "payloadTemplate.recipient",
            "subject": "payloadTemplate.summary",
            "body": "payloadTemplate.reason",
        },
    }
    assert action["operatorWorkflow"]["externalEscalation"]["handoff"][
        "envelopeDefaults"
    ] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "to": "",
        "subject": "",
        "body": "",
    }
    assert action["escalationEnvelope"] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "to": "",
        "subject": "",
        "body": "",
    }


def test_build_watch_reply_action_accepts_snake_case_watch_intake_alias() -> None:
    action = cliq.ZohoCliqClient.build_watch_reply_action(
        {
            "chatId": "CT_1",
            "channelId": "O1",
            "watch_intake": {
                "triggerMode": "web-notification-first",
                "consume": {
                    "actionId": "watch-loop",
                    "ackAction": "read-ack-latest",
                    "ackRequired": True,
                },
            },
            "messages": [
                {"messageId": "M1", "senderId": "U1", "text": "latest"},
            ],
        },
        text="ack",
    )

    assert action["watchIntake"] == {
        "triggerMode": "web-notification-first",
        "consume": {
            "actionId": "watch-loop",
            "ackAction": "read-ack-latest",
            "ackRequired": True,
        },
    }


def test_build_watch_read_ack_action_accepts_snake_case_watch_intake_alias() -> None:
    action = cliq.ZohoCliqClient.build_watch_read_ack_action(
        {
            "chatId": "CT_1",
            "channelId": "O1",
            "watch_intake": {
                "triggerMode": "web-notification-first",
                "consume": {
                    "actionId": "watch-loop",
                    "ackAction": "read-ack-latest",
                    "ackRequired": True,
                },
            },
            "messages": [
                {"messageId": "M1", "senderId": "U1", "text": "latest"},
            ],
        }
    )

    assert action["watchIntake"] == {
        "triggerMode": "web-notification-first",
        "consume": {
            "actionId": "watch-loop",
            "ackAction": "read-ack-latest",
            "ackRequired": True,
        },
    }


def test_build_watch_reply_action_accepts_kebab_case_watch_intake_alias() -> None:
    action = cliq.ZohoCliqClient.build_watch_reply_action(
        {
            "chatId": "CT_1",
            "channelId": "O1",
            "watch-intake": {
                "triggerMode": "web-notification-first",
                "consume": {
                    "actionId": "watch-loop",
                    "ackAction": "read-ack-latest",
                    "ackRequired": True,
                },
            },
            "messages": [
                {"messageId": "M1", "senderId": "U1", "text": "latest"},
            ],
        },
        text="ack",
    )

    assert action["watchIntake"] == {
        "triggerMode": "web-notification-first",
        "consume": {
            "actionId": "watch-loop",
            "ackAction": "read-ack-latest",
            "ackRequired": True,
        },
    }


def test_build_watch_read_ack_action_accepts_kebab_case_watch_intake_alias() -> None:
    action = cliq.ZohoCliqClient.build_watch_read_ack_action(
        {
            "chatId": "CT_1",
            "channelId": "O1",
            "watch-intake": {
                "triggerMode": "web-notification-first",
                "consume": {
                    "actionId": "watch-loop",
                    "ackAction": "read-ack-latest",
                    "ackRequired": True,
                },
            },
            "messages": [
                {"messageId": "M1", "senderId": "U1", "text": "latest"},
            ],
        }
    )

    assert action["watchIntake"] == {
        "triggerMode": "web-notification-first",
        "consume": {
            "actionId": "watch-loop",
            "ackAction": "read-ack-latest",
            "ackRequired": True,
        },
    }


def test_build_watch_read_ack_action_preserves_watch_intake_metadata() -> None:
    action = cliq.ZohoCliqClient.build_watch_read_ack_action(
        {
            "chatId": "CT_1",
            "channelId": "O1",
            "watchIntake": {
                "triggerMode": "web-notification-first",
                "consume": {"ackAction": "read-ack-latest", "ackRequired": True},
            },
            "operatorWorkflow": {
                "packageId": "cliq-195",
                "internalLoop": {"defaultAction": "reply-latest"},
                "externalEscalation": {
                    "defaultAction": "notify-mail",
                    "consumePolicy": {
                        "ackAction": "read-ack-latest",
                        "ackRequired": True,
                    },
                    "actionHint": {
                        "watchActAction": "read-ack-latest",
                        "bridgeActionId": "notify-mail",
                    },
                    "handoff": {
                        "contractId": "cliq-195-escalation-handoff-v1",
                        "payloadTemplate": {
                            "target": {
                                "kind": "external-contact",
                                "channel": "mail",
                                "defaultAction": "notify-mail",
                            },
                            "recipient": "",
                            "summary": "",
                            "reason": "",
                        },
                        "envelopeHints": {
                            "templateRoot": "payloadTemplate",
                            "targetPath": "payloadTemplate.target",
                            "fieldMap": {
                                "to": "payloadTemplate.recipient",
                                "subject": "payloadTemplate.summary",
                                "body": "payloadTemplate.reason",
                            },
                        },
                        "envelopeDefaults": {
                            "target": {
                                "kind": "external-contact",
                                "channel": "mail",
                                "defaultAction": "notify-mail",
                            },
                            "to": "",
                            "subject": "",
                            "body": "",
                        },
                    },
                },
            },
            "messages": [
                {"messageId": "M1", "senderId": "U1", "text": "latest"},
            ],
        }
    )

    assert action["watchIntake"]["triggerMode"] == "web-notification-first"
    assert action["watchIntake"]["consume"]["ackRequired"] is True
    assert action["operatorWorkflow"]["packageId"] == "cliq-195"
    assert action["operatorWorkflow"]["internalLoop"]["defaultAction"] == "reply-latest"
    assert action["operatorWorkflow"]["externalEscalation"]["consumePolicy"] == {
        "ackAction": "read-ack-latest",
        "ackRequired": True,
    }
    assert (
        action["operatorWorkflow"]["externalEscalation"]["handoff"]["contractId"]
        == "cliq-195-escalation-handoff-v1"
    )
    assert (
        action["operatorWorkflow"]["externalEscalation"]["actionHint"]["watchActAction"]
        == "read-ack-latest"
    )
    assert action["operatorWorkflow"]["externalEscalation"]["handoff"][
        "payloadTemplate"
    ] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "recipient": "",
        "summary": "",
        "reason": "",
    }
    assert action["operatorWorkflow"]["externalEscalation"]["handoff"][
        "envelopeHints"
    ] == {
        "templateRoot": "payloadTemplate",
        "targetPath": "payloadTemplate.target",
        "fieldMap": {
            "to": "payloadTemplate.recipient",
            "subject": "payloadTemplate.summary",
            "body": "payloadTemplate.reason",
        },
    }
    assert action["operatorWorkflow"]["externalEscalation"]["handoff"][
        "envelopeDefaults"
    ] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "to": "",
        "subject": "",
        "body": "",
    }
    assert action["escalationEnvelope"] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "to": "",
        "subject": "",
        "body": "",
    }


def test_watch_actions_leave_escalation_envelope_empty_without_alias_or_fallback() -> (
    None
):
    watch_payload = {
        "chatId": "CT_1",
        "channelId": "O1",
        "messages": [{"messageId": "M1", "senderId": "U1", "text": "latest"}],
    }

    reply_action = cliq.ZohoCliqClient.build_watch_reply_action(
        watch_payload,
        text="ack",
    )
    read_ack_action = cliq.ZohoCliqClient.build_watch_read_ack_action(watch_payload)

    expected_metadata = {
        "source": "",
        "sourcePath": "",
        "fromTopLevelAlias": False,
        "fromNestedFallback": False,
        "usedFieldFallback": False,
        "fieldSources": {},
    }

    assert reply_action["escalationEnvelope"] == {}
    assert read_ack_action["escalationEnvelope"] == {}
    assert reply_action["escalationEnvelopeMetadata"] == expected_metadata
    assert read_ack_action["escalationEnvelopeMetadata"] == expected_metadata


def test_watch_actions_prefer_top_level_escalation_envelope_with_nested_fallback() -> (
    None
):
    watch_payload = {
        "chatId": "CT_1",
        "channelId": "O1",
        "escalationEnvelope": {
            "to": "ops@happy-distro.co.uk",
        },
        "operatorWorkflow": {
            "externalEscalation": {
                "handoff": {
                    "envelopeDefaults": {
                        "target": {
                            "kind": "external-contact",
                            "channel": "mail",
                            "defaultAction": "notify-mail",
                        },
                        "to": "fallback@happy-distro.co.uk",
                        "subject": "Fallback subject",
                        "body": "Fallback body",
                    }
                }
            }
        },
        "messages": [
            {"messageId": "M1", "senderId": "U1", "text": "latest"},
        ],
    }
    expected = {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "to": "ops@happy-distro.co.uk",
        "subject": "Fallback subject",
        "body": "Fallback body",
    }

    reply_action = cliq.ZohoCliqClient.build_watch_reply_action(
        watch_payload,
        text="ack",
    )
    read_ack_action = cliq.ZohoCliqClient.build_watch_read_ack_action(watch_payload)

    expected_metadata = {
        "source": "mixed",
        "sourcePath": "mixed",
        "fromTopLevelAlias": True,
        "fromNestedFallback": True,
        "usedFieldFallback": True,
        "fieldSources": {
            "target": {
                "source": "nested-envelope-defaults",
                "sourcePath": (
                    "operatorWorkflow.externalEscalation.handoff."
                    "envelopeDefaults.target"
                ),
                "fromTopLevelAlias": False,
                "fromNestedFallback": True,
                "usedFallback": True,
            },
            "to": {
                "source": "top-level-alias",
                "sourcePath": "escalationEnvelope.to",
                "fromTopLevelAlias": True,
                "fromNestedFallback": False,
                "usedFallback": False,
            },
            "subject": {
                "source": "nested-envelope-defaults",
                "sourcePath": (
                    "operatorWorkflow.externalEscalation.handoff."
                    "envelopeDefaults.subject"
                ),
                "fromTopLevelAlias": False,
                "fromNestedFallback": True,
                "usedFallback": True,
            },
            "body": {
                "source": "nested-envelope-defaults",
                "sourcePath": (
                    "operatorWorkflow.externalEscalation.handoff.envelopeDefaults.body"
                ),
                "fromTopLevelAlias": False,
                "fromNestedFallback": True,
                "usedFallback": True,
            },
        },
    }

    assert reply_action["escalationEnvelope"] == expected
    assert read_ack_action["escalationEnvelope"] == expected
    assert reply_action["escalationEnvelopeMetadata"] == expected_metadata
    assert read_ack_action["escalationEnvelopeMetadata"] == expected_metadata


@pytest.mark.parametrize(
    ("alias_key", "expected_to_source_path"),
    [
        ("escalation_envelope", "escalation_envelope.to"),
        ("escalation-envelope", "escalation-envelope.to"),
    ],
)
def test_watch_actions_accept_non_camel_escalation_envelope_aliases(
    alias_key: str,
    expected_to_source_path: str,
) -> None:
    watch_payload = {
        "chatId": "CT_1",
        "channelId": "O1",
        alias_key: {
            "to": "ops@happy-distro.co.uk",
        },
        "operatorWorkflow": {
            "externalEscalation": {
                "handoff": {
                    "envelopeDefaults": {
                        "target": {
                            "kind": "external-contact",
                            "channel": "mail",
                            "defaultAction": "notify-mail",
                        },
                        "to": "fallback@happy-distro.co.uk",
                        "subject": "Fallback subject",
                        "body": "Fallback body",
                    }
                }
            }
        },
        "messages": [
            {"messageId": "M1", "senderId": "U1", "text": "latest"},
        ],
    }

    reply_action = cliq.ZohoCliqClient.build_watch_reply_action(
        watch_payload,
        text="ack",
    )

    assert reply_action["escalationEnvelope"] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "to": "ops@happy-distro.co.uk",
        "subject": "Fallback subject",
        "body": "Fallback body",
    }
    assert reply_action["escalationEnvelopeMetadata"]["source"] == "mixed"
    assert reply_action["escalationEnvelopeMetadata"]["fieldSources"]["to"] == {
        "source": "top-level-alias",
        "sourcePath": expected_to_source_path,
        "fromTopLevelAlias": True,
        "fromNestedFallback": False,
        "usedFallback": False,
    }


def test_watch_actions_accept_top_level_payload_template_field_aliases() -> None:
    watch_payload = {
        "chatId": "CT_1",
        "channelId": "O1",
        "escalationEnvelope": {
            "recipient": "ops@happy-distro.co.uk",
            "summary": "Escalation subject",
            "reason": "Escalation body",
        },
        "operatorWorkflow": {
            "externalEscalation": {
                "handoff": {
                    "envelopeDefaults": {
                        "target": {
                            "kind": "external-contact",
                            "channel": "mail",
                            "defaultAction": "notify-mail",
                        },
                        "to": "fallback@happy-distro.co.uk",
                        "subject": "Fallback subject",
                        "body": "Fallback body",
                    }
                }
            }
        },
        "messages": [
            {"messageId": "M1", "senderId": "U1", "text": "latest"},
        ],
    }

    reply_action = cliq.ZohoCliqClient.build_watch_reply_action(
        watch_payload,
        text="ack",
    )

    assert reply_action["escalationEnvelope"] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "to": "ops@happy-distro.co.uk",
        "subject": "Escalation subject",
        "body": "Escalation body",
    }
    assert reply_action["escalationEnvelopeMetadata"] == {
        "source": "mixed",
        "sourcePath": "mixed",
        "fromTopLevelAlias": True,
        "fromNestedFallback": True,
        "usedFieldFallback": True,
        "fieldSources": {
            "target": {
                "source": "nested-envelope-defaults",
                "sourcePath": (
                    "operatorWorkflow.externalEscalation.handoff."
                    "envelopeDefaults.target"
                ),
                "fromTopLevelAlias": False,
                "fromNestedFallback": True,
                "usedFallback": True,
            },
            "to": {
                "source": "top-level-alias",
                "sourcePath": "escalationEnvelope.recipient",
                "fromTopLevelAlias": True,
                "fromNestedFallback": False,
                "usedFallback": False,
            },
            "subject": {
                "source": "top-level-alias",
                "sourcePath": "escalationEnvelope.summary",
                "fromTopLevelAlias": True,
                "fromNestedFallback": False,
                "usedFallback": False,
            },
            "body": {
                "source": "top-level-alias",
                "sourcePath": "escalationEnvelope.reason",
                "fromTopLevelAlias": True,
                "fromNestedFallback": False,
                "usedFallback": False,
            },
        },
    }


def test_watch_actions_top_level_escalation_envelope_alias_matrix_invariants() -> None:
    envelope_aliases = (
        "escalationEnvelope",
        "escalation_envelope",
        "escalation-envelope",
    )
    to_aliases = ("to", "recipient")
    subject_aliases = ("subject", "summary")
    body_aliases = ("body", "reason")

    for envelope_alias, to_alias, subject_alias, body_alias in itertools.product(
        envelope_aliases,
        to_aliases,
        subject_aliases,
        body_aliases,
    ):
        target = {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        }
        to_value = f"to-via-{to_alias}"
        subject_value = f"subject-via-{subject_alias}"
        body_value = f"body-via-{body_alias}"

        watch_payload = {
            "chatId": "CT_1",
            "channelId": "O1",
            envelope_alias: {
                "target": target,
                to_alias: to_value,
                subject_alias: subject_value,
                body_alias: body_value,
            },
            "messages": [{"messageId": "M1", "senderId": "U1", "text": "latest"}],
        }

        reply_action = cliq.ZohoCliqClient.build_watch_reply_action(
            watch_payload,
            text="ack",
        )
        read_ack_action = cliq.ZohoCliqClient.build_watch_read_ack_action(watch_payload)

        expected_envelope = {
            "target": target,
            "to": to_value,
            "subject": subject_value,
            "body": body_value,
        }
        expected_metadata = {
            "source": "top-level-alias",
            "sourcePath": envelope_alias,
            "fromTopLevelAlias": True,
            "fromNestedFallback": False,
            "usedFieldFallback": False,
            "fieldSources": {
                "target": {
                    "source": "top-level-alias",
                    "sourcePath": f"{envelope_alias}.target",
                    "fromTopLevelAlias": True,
                    "fromNestedFallback": False,
                    "usedFallback": False,
                },
                "to": {
                    "source": "top-level-alias",
                    "sourcePath": f"{envelope_alias}.{to_alias}",
                    "fromTopLevelAlias": True,
                    "fromNestedFallback": False,
                    "usedFallback": False,
                },
                "subject": {
                    "source": "top-level-alias",
                    "sourcePath": f"{envelope_alias}.{subject_alias}",
                    "fromTopLevelAlias": True,
                    "fromNestedFallback": False,
                    "usedFallback": False,
                },
                "body": {
                    "source": "top-level-alias",
                    "sourcePath": f"{envelope_alias}.{body_alias}",
                    "fromTopLevelAlias": True,
                    "fromNestedFallback": False,
                    "usedFallback": False,
                },
            },
        }

        assert reply_action["escalationEnvelope"] == expected_envelope
        assert read_ack_action["escalationEnvelope"] == expected_envelope
        assert reply_action["escalationEnvelopeMetadata"] == expected_metadata
        assert read_ack_action["escalationEnvelopeMetadata"] == expected_metadata


def test_watch_actions_mixed_source_alias_matrix_invariants() -> None:
    envelope_aliases = (
        "escalationEnvelope",
        "escalation_envelope",
        "escalation-envelope",
    )
    workflow_aliases = (
        "operatorWorkflow",
        "operator_workflow",
        "operator-workflow",
    )
    escalation_aliases = (
        "externalEscalation",
        "external_escalation",
        "external-escalation",
    )
    envelope_defaults_aliases = (
        "envelopeDefaults",
        "envelope_defaults",
        "envelope-defaults",
    )

    for (
        envelope_alias,
        workflow_alias,
        escalation_alias,
        envelope_defaults_alias,
    ) in itertools.product(
        envelope_aliases,
        workflow_aliases,
        escalation_aliases,
        envelope_defaults_aliases,
    ):
        target = {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        }

        watch_payload = {
            "chatId": "CT_1",
            "channelId": "O1",
            envelope_alias: {
                "recipient": "ops@happy-distro.co.uk",
                "summary": "Escalation subject",
                "reason": "Escalation body",
            },
            workflow_alias: {
                escalation_alias: {
                    "handoff": {
                        envelope_defaults_alias: {
                            "target": target,
                            "to": "fallback@happy-distro.co.uk",
                            "subject": "Fallback subject",
                            "body": "Fallback body",
                        }
                    }
                }
            },
            "messages": [{"messageId": "M1", "senderId": "U1", "text": "latest"}],
        }

        reply_action = cliq.ZohoCliqClient.build_watch_reply_action(
            watch_payload,
            text="ack",
        )
        read_ack_action = cliq.ZohoCliqClient.build_watch_read_ack_action(watch_payload)

        expected_envelope = {
            "target": target,
            "to": "ops@happy-distro.co.uk",
            "subject": "Escalation subject",
            "body": "Escalation body",
        }
        fallback_source_root = (
            f"{workflow_alias}.{escalation_alias}.handoff.{envelope_defaults_alias}"
        )
        expected_metadata = {
            "source": "mixed",
            "sourcePath": "mixed",
            "fromTopLevelAlias": True,
            "fromNestedFallback": True,
            "usedFieldFallback": True,
            "fieldSources": {
                "target": {
                    "source": "nested-envelope-defaults",
                    "sourcePath": f"{fallback_source_root}.target",
                    "fromTopLevelAlias": False,
                    "fromNestedFallback": True,
                    "usedFallback": True,
                },
                "to": {
                    "source": "top-level-alias",
                    "sourcePath": f"{envelope_alias}.recipient",
                    "fromTopLevelAlias": True,
                    "fromNestedFallback": False,
                    "usedFallback": False,
                },
                "subject": {
                    "source": "top-level-alias",
                    "sourcePath": f"{envelope_alias}.summary",
                    "fromTopLevelAlias": True,
                    "fromNestedFallback": False,
                    "usedFallback": False,
                },
                "body": {
                    "source": "top-level-alias",
                    "sourcePath": f"{envelope_alias}.reason",
                    "fromTopLevelAlias": True,
                    "fromNestedFallback": False,
                    "usedFallback": False,
                },
            },
        }

        assert reply_action["escalationEnvelope"] == expected_envelope
        assert read_ack_action["escalationEnvelope"] == expected_envelope
        assert reply_action["escalationEnvelopeMetadata"] == expected_metadata
        assert read_ack_action["escalationEnvelopeMetadata"] == expected_metadata


def test_watch_actions_accept_snake_case_nested_envelope_defaults_alias() -> None:
    watch_payload = {
        "chatId": "CT_1",
        "channelId": "O1",
        "escalation_envelope": {
            "to": "ops@happy-distro.co.uk",
        },
        "operatorWorkflow": {
            "external_escalation": {
                "handoff": {
                    "envelope_defaults": {
                        "target": {
                            "kind": "external-contact",
                            "channel": "mail",
                            "defaultAction": "notify-mail",
                        },
                        "to": "fallback@happy-distro.co.uk",
                        "subject": "Fallback subject",
                        "body": "Fallback body",
                    }
                }
            }
        },
        "messages": [
            {"messageId": "M1", "senderId": "U1", "text": "latest"},
        ],
    }

    reply_action = cliq.ZohoCliqClient.build_watch_reply_action(
        watch_payload,
        text="ack",
    )

    assert reply_action["escalationEnvelope"] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "to": "ops@happy-distro.co.uk",
        "subject": "Fallback subject",
        "body": "Fallback body",
    }
    assert reply_action["escalationEnvelopeMetadata"]["fieldSources"]["target"] == {
        "source": "nested-envelope-defaults",
        "sourcePath": (
            "operatorWorkflow.external_escalation.handoff.envelope_defaults.target"
        ),
        "fromTopLevelAlias": False,
        "fromNestedFallback": True,
        "usedFallback": True,
    }


@pytest.mark.parametrize(
    ("workflow_alias_key", "expected_target_source_path"),
    [
        (
            "operator_workflow",
            "operator_workflow.external_escalation.handoff.envelope_defaults.target",
        ),
        (
            "operator-workflow",
            "operator-workflow.external_escalation.handoff.envelope_defaults.target",
        ),
    ],
)
def test_watch_actions_accept_non_camel_operator_workflow_aliases(
    workflow_alias_key: str,
    expected_target_source_path: str,
) -> None:
    watch_payload = {
        "chatId": "CT_1",
        "channelId": "O1",
        "escalation_envelope": {
            "to": "ops@happy-distro.co.uk",
        },
        workflow_alias_key: {
            "external_escalation": {
                "handoff": {
                    "envelope_defaults": {
                        "target": {
                            "kind": "external-contact",
                            "channel": "mail",
                            "defaultAction": "notify-mail",
                        },
                        "to": "fallback@happy-distro.co.uk",
                        "subject": "Fallback subject",
                        "body": "Fallback body",
                    }
                }
            }
        },
        "messages": [
            {"messageId": "M1", "senderId": "U1", "text": "latest"},
        ],
    }

    reply_action = cliq.ZohoCliqClient.build_watch_reply_action(
        watch_payload,
        text="ack",
    )

    assert reply_action["operatorWorkflow"] == watch_payload[workflow_alias_key]
    assert reply_action["escalationEnvelopeMetadata"]["fieldSources"]["target"] == {
        "source": "nested-envelope-defaults",
        "sourcePath": expected_target_source_path,
        "fromTopLevelAlias": False,
        "fromNestedFallback": True,
        "usedFallback": True,
    }


def test_watch_actions_accept_kebab_case_external_escalation_envelope_defaults_aliases() -> (
    None
):
    watch_payload = {
        "chatId": "CT_1",
        "channelId": "O1",
        "escalation_envelope": {
            "to": "ops@happy-distro.co.uk",
        },
        "operator-workflow": {
            "external-escalation": {
                "handoff": {
                    "envelope-defaults": {
                        "target": {
                            "kind": "external-contact",
                            "channel": "mail",
                            "defaultAction": "notify-mail",
                        },
                        "to": "fallback@happy-distro.co.uk",
                        "subject": "Fallback subject",
                        "body": "Fallback body",
                    }
                }
            }
        },
        "messages": [
            {"messageId": "M1", "senderId": "U1", "text": "latest"},
        ],
    }

    reply_action = cliq.ZohoCliqClient.build_watch_reply_action(
        watch_payload,
        text="ack",
    )

    assert reply_action["operatorWorkflow"] == watch_payload["operator-workflow"]
    assert reply_action["escalationEnvelope"] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "to": "ops@happy-distro.co.uk",
        "subject": "Fallback subject",
        "body": "Fallback body",
    }
    assert reply_action["escalationEnvelopeMetadata"]["fieldSources"]["target"] == {
        "source": "nested-envelope-defaults",
        "sourcePath": (
            "operator-workflow.external-escalation.handoff.envelope-defaults.target"
        ),
        "fromTopLevelAlias": False,
        "fromNestedFallback": True,
        "usedFallback": True,
    }


def test_watch_actions_accept_kebab_case_payload_template_alias_source_paths() -> None:
    watch_payload = {
        "chatId": "CT_1",
        "channelId": "O1",
        "operator-workflow": {
            "external-escalation": {
                "handoff": {
                    "payload-template": {
                        "target": {
                            "kind": "external-contact",
                            "channel": "mail",
                            "defaultAction": "notify-mail",
                        },
                        "recipient": "fallback@happy-distro.co.uk",
                        "summary": "Fallback subject",
                        "reason": "Fallback body",
                    }
                }
            }
        },
        "messages": [
            {"messageId": "M1", "senderId": "U1", "text": "latest"},
        ],
    }

    reply_action = cliq.ZohoCliqClient.build_watch_reply_action(
        watch_payload,
        text="ack",
    )

    assert reply_action["escalationEnvelope"] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "to": "fallback@happy-distro.co.uk",
        "subject": "Fallback subject",
        "body": "Fallback body",
    }
    assert (
        reply_action["escalationEnvelopeMetadata"]["fieldSources"]["to"]["sourcePath"]
        == "operator-workflow.external-escalation.handoff.payload-template.recipient"
    )
    assert (
        reply_action["escalationEnvelopeMetadata"]["fieldSources"]["subject"][
            "sourcePath"
        ]
        == "operator-workflow.external-escalation.handoff.payload-template.summary"
    )
    assert (
        reply_action["escalationEnvelopeMetadata"]["fieldSources"]["body"]["sourcePath"]
        == "operator-workflow.external-escalation.handoff.payload-template.reason"
    )


def test_watch_actions_accept_kebab_case_payload_template_envelope_field_aliases() -> (
    None
):
    watch_payload = {
        "chatId": "CT_1",
        "channelId": "O1",
        "operator-workflow": {
            "external-escalation": {
                "handoff": {
                    "payload-template": {
                        "target": {
                            "kind": "external-contact",
                            "channel": "mail",
                            "defaultAction": "notify-mail",
                        },
                        "to": "fallback@happy-distro.co.uk",
                        "subject": "Fallback subject",
                        "body": "Fallback body",
                    }
                }
            }
        },
        "messages": [
            {"messageId": "M1", "senderId": "U1", "text": "latest"},
        ],
    }

    reply_action = cliq.ZohoCliqClient.build_watch_reply_action(
        watch_payload,
        text="ack",
    )

    assert reply_action["escalationEnvelope"] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "to": "fallback@happy-distro.co.uk",
        "subject": "Fallback subject",
        "body": "Fallback body",
    }
    assert (
        reply_action["escalationEnvelopeMetadata"]["fieldSources"]["to"]["sourcePath"]
        == "operator-workflow.external-escalation.handoff.payload-template.to"
    )
    assert (
        reply_action["escalationEnvelopeMetadata"]["fieldSources"]["subject"][
            "sourcePath"
        ]
        == "operator-workflow.external-escalation.handoff.payload-template.subject"
    )
    assert (
        reply_action["escalationEnvelopeMetadata"]["fieldSources"]["body"]["sourcePath"]
        == "operator-workflow.external-escalation.handoff.payload-template.body"
    )


def test_watch_actions_nested_fallback_metadata_source_path_with_kebab_envelope_defaults() -> (
    None
):
    watch_payload = {
        "chatId": "CT_1",
        "channelId": "O1",
        "operator-workflow": {
            "external-escalation": {
                "handoff": {
                    "envelope-defaults": {
                        "target": {
                            "kind": "external-contact",
                            "channel": "mail",
                            "defaultAction": "notify-mail",
                        },
                        "to": "fallback@happy-distro.co.uk",
                        "subject": "Fallback subject",
                        "body": "Fallback body",
                    }
                }
            }
        },
        "messages": [
            {"messageId": "M1", "senderId": "U1", "text": "latest"},
        ],
    }

    reply_action = cliq.ZohoCliqClient.build_watch_reply_action(
        watch_payload,
        text="ack",
    )

    assert reply_action["escalationEnvelopeMetadata"]["source"] == "nested-fallback"
    assert (
        reply_action["escalationEnvelopeMetadata"]["sourcePath"]
        == "operator-workflow.external-escalation.handoff"
    )
    assert reply_action["escalationEnvelopeMetadata"]["fromTopLevelAlias"] is False
    assert reply_action["escalationEnvelopeMetadata"]["fromNestedFallback"] is True
    assert reply_action["escalationEnvelopeMetadata"]["usedFieldFallback"] is True


def test_watch_actions_nested_fallback_metadata_source_path_with_kebab_payload_template() -> (
    None
):
    watch_payload = {
        "chatId": "CT_1",
        "channelId": "O1",
        "operator-workflow": {
            "external-escalation": {
                "handoff": {
                    "payload-template": {
                        "target": {
                            "kind": "external-contact",
                            "channel": "mail",
                            "defaultAction": "notify-mail",
                        },
                        "recipient": "fallback@happy-distro.co.uk",
                        "summary": "Fallback subject",
                        "reason": "Fallback body",
                    }
                }
            }
        },
        "messages": [
            {"messageId": "M1", "senderId": "U1", "text": "latest"},
        ],
    }

    reply_action = cliq.ZohoCliqClient.build_watch_reply_action(
        watch_payload,
        text="ack",
    )

    assert reply_action["escalationEnvelopeMetadata"]["source"] == "nested-fallback"
    assert (
        reply_action["escalationEnvelopeMetadata"]["sourcePath"]
        == "operator-workflow.external-escalation.handoff"
    )
    assert reply_action["escalationEnvelopeMetadata"]["fromTopLevelAlias"] is False
    assert reply_action["escalationEnvelopeMetadata"]["fromNestedFallback"] is True
    assert reply_action["escalationEnvelopeMetadata"]["usedFieldFallback"] is True


@pytest.mark.parametrize(
    ("handoff_alias", "expected_source_path"),
    [
        ("hand_off", "operator-workflow.external-escalation.hand_off"),
        ("hand-off", "operator-workflow.external-escalation.hand-off"),
    ],
)
def test_watch_actions_nested_fallback_metadata_source_path_with_noncanonical_handoff_aliases(
    handoff_alias: str,
    expected_source_path: str,
) -> None:
    watch_payload = {
        "chatId": "CT_1",
        "channelId": "O1",
        "operator-workflow": {
            "external-escalation": {
                handoff_alias: {
                    "payload-template": {
                        "target": {
                            "kind": "external-contact",
                            "channel": "mail",
                            "defaultAction": "notify-mail",
                        },
                        "recipient": "fallback@happy-distro.co.uk",
                        "summary": "Fallback subject",
                        "reason": "Fallback body",
                    }
                }
            }
        },
        "messages": [
            {"messageId": "M1", "senderId": "U1", "text": "latest"},
        ],
    }

    reply_action = cliq.ZohoCliqClient.build_watch_reply_action(
        watch_payload,
        text="ack",
    )

    assert reply_action["escalationEnvelopeMetadata"]["source"] == "nested-fallback"
    assert (
        reply_action["escalationEnvelopeMetadata"]["sourcePath"] == expected_source_path
    )
    assert (
        reply_action["escalationEnvelopeMetadata"]["fieldSources"]["to"]["sourcePath"]
        == f"{expected_source_path}.payload-template.recipient"
    )


def test_watch_actions_preserve_nested_envelope_defaults_alias_source_paths() -> None:
    watch_payload = {
        "chatId": "CT_1",
        "channelId": "O1",
        "operator_workflow": {
            "external_escalation": {
                "handoff": {
                    "envelope_defaults": {
                        "target": {
                            "kind": "external-contact",
                            "channel": "mail",
                            "defaultAction": "notify-mail",
                        },
                        "recipient": "fallback@happy-distro.co.uk",
                        "summary": "Fallback subject",
                        "reason": "Fallback body",
                    }
                }
            }
        },
        "messages": [
            {"messageId": "M1", "senderId": "U1", "text": "latest"},
        ],
    }

    reply_action = cliq.ZohoCliqClient.build_watch_reply_action(
        watch_payload,
        text="ack",
    )

    assert reply_action["escalationEnvelope"] == {
        "target": {
            "kind": "external-contact",
            "channel": "mail",
            "defaultAction": "notify-mail",
        },
        "to": "fallback@happy-distro.co.uk",
        "subject": "Fallback subject",
        "body": "Fallback body",
    }
    assert (
        reply_action["escalationEnvelopeMetadata"]["fieldSources"]["to"]["sourcePath"]
        == "operator_workflow.external_escalation.handoff.envelope_defaults.recipient"
    )
    assert (
        reply_action["escalationEnvelopeMetadata"]["fieldSources"]["subject"][
            "sourcePath"
        ]
        == "operator_workflow.external_escalation.handoff.envelope_defaults.summary"
    )
    assert (
        reply_action["escalationEnvelopeMetadata"]["fieldSources"]["body"]["sourcePath"]
        == "operator_workflow.external_escalation.handoff.envelope_defaults.reason"
    )


def test_watch_actions_nested_envelope_defaults_alias_matrix_invariants() -> None:
    workflow_aliases = (
        "operatorWorkflow",
        "operator_workflow",
        "operator-workflow",
    )
    external_aliases = (
        "externalEscalation",
        "external_escalation",
        "external-escalation",
    )
    handoff_aliases = ("envelopeDefaults", "envelope_defaults", "envelope-defaults")
    to_aliases = ("to", "recipient")
    subject_aliases = ("subject", "summary")
    body_aliases = ("body", "reason")

    target = {
        "kind": "external-contact",
        "channel": "mail",
        "defaultAction": "notify-mail",
    }

    for (
        workflow_alias,
        external_alias,
        handoff_alias,
        to_alias,
        subject_alias,
        body_alias,
    ) in itertools.product(
        workflow_aliases,
        external_aliases,
        handoff_aliases,
        to_aliases,
        subject_aliases,
        body_aliases,
    ):
        to_value = f"to-via-{to_alias}"
        subject_value = f"subject-via-{subject_alias}"
        body_value = f"body-via-{body_alias}"

        watch_payload = {
            "chatId": "CT_1",
            "channelId": "O1",
            workflow_alias: {
                external_alias: {
                    "handoff": {
                        handoff_alias: {
                            "target": target,
                            to_alias: to_value,
                            subject_alias: subject_value,
                            body_alias: body_value,
                        }
                    }
                }
            },
            "messages": [{"messageId": "M1", "senderId": "U1", "text": "latest"}],
        }

        reply_action = cliq.ZohoCliqClient.build_watch_reply_action(
            watch_payload,
            text="ack",
        )
        read_ack_action = cliq.ZohoCliqClient.build_watch_read_ack_action(watch_payload)

        expected_envelope = {
            "target": target,
            "to": to_value,
            "subject": subject_value,
            "body": body_value,
        }
        expected_metadata = {
            "source": "nested-fallback",
            "sourcePath": f"{workflow_alias}.{external_alias}.handoff",
            "fromTopLevelAlias": False,
            "fromNestedFallback": True,
            "usedFieldFallback": True,
            "fieldSources": {
                "target": {
                    "source": "nested-envelope-defaults",
                    "sourcePath": (
                        f"{workflow_alias}.{external_alias}.handoff.{handoff_alias}.target"
                    ),
                    "fromTopLevelAlias": False,
                    "fromNestedFallback": True,
                    "usedFallback": True,
                },
                "to": {
                    "source": "nested-envelope-defaults",
                    "sourcePath": (
                        f"{workflow_alias}.{external_alias}.handoff.{handoff_alias}.{to_alias}"
                    ),
                    "fromTopLevelAlias": False,
                    "fromNestedFallback": True,
                    "usedFallback": True,
                },
                "subject": {
                    "source": "nested-envelope-defaults",
                    "sourcePath": (
                        f"{workflow_alias}.{external_alias}.handoff.{handoff_alias}.{subject_alias}"
                    ),
                    "fromTopLevelAlias": False,
                    "fromNestedFallback": True,
                    "usedFallback": True,
                },
                "body": {
                    "source": "nested-envelope-defaults",
                    "sourcePath": (
                        f"{workflow_alias}.{external_alias}.handoff.{handoff_alias}.{body_alias}"
                    ),
                    "fromTopLevelAlias": False,
                    "fromNestedFallback": True,
                    "usedFallback": True,
                },
            },
        }

        assert reply_action["escalationEnvelope"] == expected_envelope
        assert read_ack_action["escalationEnvelope"] == expected_envelope
        assert reply_action["escalationEnvelopeMetadata"] == expected_metadata
        assert read_ack_action["escalationEnvelopeMetadata"] == expected_metadata


def test_watch_actions_nested_payload_template_alias_matrix_invariants() -> None:
    workflow_aliases = (
        "operatorWorkflow",
        "operator_workflow",
        "operator-workflow",
    )
    external_aliases = (
        "externalEscalation",
        "external_escalation",
        "external-escalation",
    )
    handoff_aliases = ("payloadTemplate", "payload_template", "payload-template")
    to_aliases = ("recipient", "to")
    subject_aliases = ("summary", "subject")
    body_aliases = ("reason", "body")

    target = {
        "kind": "external-contact",
        "channel": "mail",
        "defaultAction": "notify-mail",
    }

    for (
        workflow_alias,
        external_alias,
        handoff_alias,
        to_alias,
        subject_alias,
        body_alias,
    ) in itertools.product(
        workflow_aliases,
        external_aliases,
        handoff_aliases,
        to_aliases,
        subject_aliases,
        body_aliases,
    ):
        to_value = f"to-via-{to_alias}"
        subject_value = f"subject-via-{subject_alias}"
        body_value = f"body-via-{body_alias}"

        watch_payload = {
            "chatId": "CT_1",
            "channelId": "O1",
            workflow_alias: {
                external_alias: {
                    "handoff": {
                        handoff_alias: {
                            "target": target,
                            to_alias: to_value,
                            subject_alias: subject_value,
                            body_alias: body_value,
                        }
                    }
                }
            },
            "messages": [{"messageId": "M1", "senderId": "U1", "text": "latest"}],
        }

        reply_action = cliq.ZohoCliqClient.build_watch_reply_action(
            watch_payload,
            text="ack",
        )
        read_ack_action = cliq.ZohoCliqClient.build_watch_read_ack_action(watch_payload)

        expected_envelope = {
            "target": target,
            "to": to_value,
            "subject": subject_value,
            "body": body_value,
        }
        expected_metadata = {
            "source": "nested-fallback",
            "sourcePath": f"{workflow_alias}.{external_alias}.handoff",
            "fromTopLevelAlias": False,
            "fromNestedFallback": True,
            "usedFieldFallback": True,
            "fieldSources": {
                "target": {
                    "source": "nested-payload-template",
                    "sourcePath": (
                        f"{workflow_alias}.{external_alias}.handoff.{handoff_alias}.target"
                    ),
                    "fromTopLevelAlias": False,
                    "fromNestedFallback": True,
                    "usedFallback": True,
                },
                "to": {
                    "source": "nested-payload-template",
                    "sourcePath": (
                        f"{workflow_alias}.{external_alias}.handoff.{handoff_alias}.{to_alias}"
                    ),
                    "fromTopLevelAlias": False,
                    "fromNestedFallback": True,
                    "usedFallback": True,
                },
                "subject": {
                    "source": "nested-payload-template",
                    "sourcePath": (
                        f"{workflow_alias}.{external_alias}.handoff.{handoff_alias}.{subject_alias}"
                    ),
                    "fromTopLevelAlias": False,
                    "fromNestedFallback": True,
                    "usedFallback": True,
                },
                "body": {
                    "source": "nested-payload-template",
                    "sourcePath": (
                        f"{workflow_alias}.{external_alias}.handoff.{handoff_alias}.{body_alias}"
                    ),
                    "fromTopLevelAlias": False,
                    "fromNestedFallback": True,
                    "usedFallback": True,
                },
            },
        }

        assert reply_action["escalationEnvelope"] == expected_envelope
        assert read_ack_action["escalationEnvelope"] == expected_envelope
        assert reply_action["escalationEnvelopeMetadata"] == expected_metadata
        assert read_ack_action["escalationEnvelopeMetadata"] == expected_metadata


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


def test_build_watch_read_ack_action_selects_latest_message() -> None:
    action = cliq.ZohoCliqClient.build_watch_read_ack_action(
        {
            "chatId": "CT_1",
            "channelId": "O1",
            "messages": [
                {"messageId": "M1", "senderId": "U1", "text": "first"},
                {"messageId": "M2", "senderId": "U2", "text": "latest"},
            ],
        }
    )

    assert action["action"] == "read-ack-latest"
    assert action["chatId"] == "CT_1"
    assert action["channelId"] == "O1"
    assert action["targetMessageId"] == "M2"
    assert action["hasTarget"] is True
    assert action["ackRequired"] is True


def test_build_watch_read_ack_action_honors_explicit_message_id() -> None:
    action = cliq.ZohoCliqClient.build_watch_read_ack_action(
        {
            "chatId": "CT_1",
            "channelId": "O1",
            "messages": [
                {"messageId": "M1", "senderId": "U1", "text": "first"},
                {"messageId": "M2", "senderId": "U2", "text": "latest"},
            ],
        },
        message_id="M1",
    )

    assert action["targetMessageId"] == "M1"
    assert action["hasTarget"] is True
    assert action["ackRequired"] is True


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


@respx.mock
def test_execute_watch_reply_action_marks_read_when_watch_intake_requires_ack(
    client: cliq.ZohoCliqClient,
) -> None:
    reply_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/reply"
    ).mock(return_value=httpx.Response(200, json={"data": {"id": "M3"}}))
    read_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read"
    ).mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = client.execute_watch_reply_action(
        {
            "chatId": "CT_1",
            "channelId": "O1",
            "watchIntake": {
                "consume": {
                    "ackRequired": True,
                    "ackAction": "read-ack-latest",
                }
            },
            "messages": [
                {"messageId": "M1", "senderId": "U1", "text": "first"},
                {"messageId": "M2", "senderId": "U2", "text": "latest"},
            ],
        },
        text="ack",
    )

    assert reply_route.called
    assert read_route.called
    assert result["status"] == "ok"
    assert result["applied"] is True
    assert result["targetMessageId"] == "M2"
    assert result["readAck"]["required"] is True
    assert result["readAck"]["applied"] is True
    assert result["readAck"]["messageId"] == "M2"
    assert result["readAck"]["result"]["status"] == "ok"


@respx.mock
def test_execute_watch_reply_action_marks_read_when_kebab_case_watch_intake_requires_ack(
    client: cliq.ZohoCliqClient,
) -> None:
    reply_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/reply"
    ).mock(return_value=httpx.Response(200, json={"data": {"id": "M3"}}))
    read_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read"
    ).mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = client.execute_watch_reply_action(
        {
            "chatId": "CT_1",
            "channelId": "O1",
            "watch-intake": {
                "consume": {
                    "ackRequired": True,
                    "ackAction": "read-ack-latest",
                }
            },
            "messages": [
                {"messageId": "M1", "senderId": "U1", "text": "first"},
                {"messageId": "M2", "senderId": "U2", "text": "latest"},
            ],
        },
        text="ack",
    )

    assert reply_route.called
    assert read_route.called
    assert result["status"] == "ok"
    assert result["applied"] is True
    assert result["targetMessageId"] == "M2"
    assert result["readAck"]["required"] is True
    assert result["readAck"]["applied"] is True
    assert result["readAck"]["messageId"] == "M2"
    assert result["readAck"]["result"]["status"] == "ok"


@respx.mock
def test_execute_watch_reply_action_honors_operator_workflow_internal_read_ack_action_hint(
    client: cliq.ZohoCliqClient,
) -> None:
    reply_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/reply"
    ).mock(return_value=httpx.Response(200, json={"data": {"id": "M3"}}))
    read_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read"
    ).mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = client.execute_watch_reply_action(
        {
            "chatId": "CT_1",
            "channelId": "O1",
            "operatorWorkflow": {
                "internalLoop": {
                    "actionHint": {
                        "readAckAction": "read-ack-latest",
                    }
                }
            },
            "messages": [
                {"messageId": "M1", "senderId": "U1", "text": "first"},
                {"messageId": "M2", "senderId": "U2", "text": "latest"},
            ],
        },
        text="ack",
    )

    assert reply_route.called
    assert read_route.called
    assert result["status"] == "ok"
    assert result["applied"] is True
    assert result["targetMessageId"] == "M2"
    assert result["readAck"]["required"] is True
    assert result["readAck"]["applied"] is True
    assert result["readAck"]["messageId"] == "M2"
    assert result["readAck"]["result"]["status"] == "ok"


@respx.mock
def test_watch_context_seed_end_to_end_reply_read_ack_and_cursor_dedupe(
    client: cliq.ZohoCliqClient,
) -> None:
    reply_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M3/reply"
    ).mock(return_value=httpx.Response(200, json={"data": {"id": "M4"}}))
    read_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M3/read"
    ).mock(
        return_value=httpx.Response(200, json={"data": {"id": "M3", "status": "ok"}})
    )

    messages = [
        {"id": "M3", "text": "latest", "sender_id": "U3", "time": "3000"},
        {"id": "M2", "text": "next", "sender_id": "U2", "time": "2000"},
        {"id": "M1", "text": "anchor", "sender_id": "U1", "time": "1000"},
    ]

    first_watch = cliq.ZohoCliqClient.build_watch_context_seed(
        messages,
        since_message_id="M1",
        max_messages=10,
    )
    first_watch.update({"chatId": "CT_1", "channelId": "O1"})

    assert first_watch["watchIntake"]["triggerMode"] == "web-notification-first"
    assert first_watch["watchIntake"]["pollFallback"]["transport"] == "api-poll"
    assert first_watch["nextSinceMessageId"] == "M3"
    assert [item["messageId"] for item in first_watch["messages"]] == ["M2", "M3"]

    first_result = client.execute_watch_reply_action(first_watch, text="ack")

    assert first_result["status"] == "ok"
    assert first_result["applied"] is True
    assert first_result["targetMessageId"] == "M3"
    assert first_result["readAck"]["required"] is True
    assert first_result["readAck"]["applied"] is True
    assert first_result["readAck"]["messageId"] == "M3"
    assert first_result["readAck"]["result"]["status"] == "ok"

    second_watch = cliq.ZohoCliqClient.build_watch_context_seed(
        messages,
        since_message_id=first_watch["nextSinceMessageId"],
        max_messages=10,
    )
    second_watch.update({"chatId": "CT_1", "channelId": "O1"})

    assert second_watch["cursorFound"] is True
    assert second_watch["newCount"] == 0
    assert second_watch["messages"] == []

    second_result = client.execute_watch_reply_action(second_watch, text="ack")

    assert second_result["status"] == "ok"
    assert second_result["applied"] is False
    assert second_result["reason"] == "no_new_messages"
    assert second_result["readAck"]["required"] is True
    assert second_result["readAck"]["applied"] is False
    assert second_result["readAck"]["reason"] == "no_new_messages"
    assert reply_route.call_count == 1
    assert read_route.call_count == 1


@respx.mock
def test_execute_watch_reply_action_allows_explicit_skip_read_ack(
    client: cliq.ZohoCliqClient,
) -> None:
    reply_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/reply"
    ).mock(return_value=httpx.Response(200, json={"data": {"id": "M3"}}))
    read_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read"
    ).mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = client.execute_watch_reply_action(
        {
            "chatId": "CT_1",
            "channelId": "O1",
            "watch_intake": {
                "consume": {
                    "ack_action": "read-ack-latest",
                }
            },
            "messages": [
                {"messageId": "M1", "senderId": "U1", "text": "first"},
                {"messageId": "M2", "senderId": "U2", "text": "latest"},
            ],
        },
        text="ack",
        auto_read_ack=False,
    )

    assert reply_route.called
    assert not read_route.called
    assert result["status"] == "ok"
    assert result["applied"] is True
    assert result["readAck"]["required"] is False
    assert result["readAck"]["applied"] is False


@respx.mock
def test_execute_watch_reply_action_honors_kebab_ack_required_alias(
    client: cliq.ZohoCliqClient,
) -> None:
    reply_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/reply"
    ).mock(return_value=httpx.Response(200, json={"data": {"id": "M3"}}))
    read_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read"
    ).mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = client.execute_watch_reply_action(
        {
            "chatId": "CT_1",
            "channelId": "O1",
            "watch-intake": {
                "consume": {
                    "ack-required": True,
                }
            },
            "messages": [
                {"messageId": "M1", "senderId": "U1", "text": "first"},
                {"messageId": "M2", "senderId": "U2", "text": "latest"},
            ],
        },
        text="ack",
    )

    assert reply_route.called
    assert read_route.called
    assert result["status"] == "ok"
    assert result["applied"] is True
    assert result["readAck"]["required"] is True
    assert result["readAck"]["applied"] is True


@respx.mock
def test_execute_watch_reply_action_honors_camel_consume_policy_alias(
    client: cliq.ZohoCliqClient,
) -> None:
    reply_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/reply"
    ).mock(return_value=httpx.Response(200, json={"data": {"id": "M3"}}))
    read_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read"
    ).mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = client.execute_watch_reply_action(
        {
            "chatId": "CT_1",
            "channelId": "O1",
            "watchIntake": {
                "consumePolicy": {
                    "ackRequired": True,
                }
            },
            "messages": [
                {"messageId": "M1", "senderId": "U1", "text": "first"},
                {"messageId": "M2", "senderId": "U2", "text": "latest"},
            ],
        },
        text="ack",
    )

    assert reply_route.called
    assert read_route.called
    assert result["status"] == "ok"
    assert result["applied"] is True
    assert result["readAck"]["required"] is True
    assert result["readAck"]["applied"] is True


@respx.mock
def test_execute_watch_reply_action_honors_kebab_consume_policy_alias(
    client: cliq.ZohoCliqClient,
) -> None:
    reply_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/reply"
    ).mock(return_value=httpx.Response(200, json={"data": {"id": "M3"}}))
    read_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read"
    ).mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = client.execute_watch_reply_action(
        {
            "chatId": "CT_1",
            "channelId": "O1",
            "watch-intake": {
                "consume-policy": {
                    "ack-required": "yes",
                }
            },
            "messages": [
                {"messageId": "M1", "senderId": "U1", "text": "first"},
                {"messageId": "M2", "senderId": "U2", "text": "latest"},
            ],
        },
        text="ack",
    )

    assert reply_route.called
    assert read_route.called
    assert result["status"] == "ok"
    assert result["applied"] is True
    assert result["readAck"]["required"] is True
    assert result["readAck"]["applied"] is True


@respx.mock
def test_execute_watch_reply_action_honors_ack_action_id_alias(
    client: cliq.ZohoCliqClient,
) -> None:
    reply_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/reply"
    ).mock(return_value=httpx.Response(200, json={"data": {"id": "M3"}}))
    read_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read"
    ).mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = client.execute_watch_reply_action(
        {
            "chatId": "CT_1",
            "channelId": "O1",
            "watchIntake": {
                "consume": {
                    "ackActionId": "read-ack-latest",
                }
            },
            "messages": [
                {"messageId": "M1", "senderId": "U1", "text": "first"},
                {"messageId": "M2", "senderId": "U2", "text": "latest"},
            ],
        },
        text="ack",
    )

    assert reply_route.called
    assert read_route.called
    assert result["status"] == "ok"
    assert result["applied"] is True
    assert result["readAck"]["required"] is True
    assert result["readAck"]["applied"] is True


@respx.mock
def test_execute_watch_reply_action_honors_kebab_ack_action_id_alias(
    client: cliq.ZohoCliqClient,
) -> None:
    reply_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/reply"
    ).mock(return_value=httpx.Response(200, json={"data": {"id": "M3"}}))
    read_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read"
    ).mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = client.execute_watch_reply_action(
        {
            "chatId": "CT_1",
            "channelId": "O1",
            "watch-intake": {
                "consume-policy": {
                    "ack-action-id": "read-ack-latest",
                }
            },
            "messages": [
                {"messageId": "M1", "senderId": "U1", "text": "first"},
                {"messageId": "M2", "senderId": "U2", "text": "latest"},
            ],
        },
        text="ack",
    )

    assert reply_route.called
    assert read_route.called
    assert result["status"] == "ok"
    assert result["applied"] is True
    assert result["readAck"]["required"] is True
    assert result["readAck"]["applied"] is True


@respx.mock
def test_execute_watch_reply_action_honors_uppercase_tail_ack_action_id_alias(
    client: cliq.ZohoCliqClient,
) -> None:
    reply_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/reply"
    ).mock(return_value=httpx.Response(200, json={"data": {"id": "M3"}}))
    read_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read"
    ).mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = client.execute_watch_reply_action(
        {
            "chatId": "CT_1",
            "channelId": "O1",
            "watchIntake": {
                "consumePolicy": {
                    "ackActionID": "read-ack-latest",
                }
            },
            "messages": [
                {"messageId": "M1", "senderId": "U1", "text": "first"},
                {"messageId": "M2", "senderId": "U2", "text": "latest"},
            ],
        },
        text="ack",
    )

    assert reply_route.called
    assert read_route.called
    assert result["status"] == "ok"
    assert result["applied"] is True
    assert result["readAck"]["required"] is True
    assert result["readAck"]["applied"] is True


@respx.mock
def test_execute_watch_reply_action_honors_kebab_uppercase_tail_ack_action_id_alias(
    client: cliq.ZohoCliqClient,
) -> None:
    reply_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/reply"
    ).mock(return_value=httpx.Response(200, json={"data": {"id": "M3"}}))
    read_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read"
    ).mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = client.execute_watch_reply_action(
        {
            "chatId": "CT_1",
            "channelId": "O1",
            "watch-intake": {
                "consume-policy": {
                    "ack-action-ID": "read-ack-latest",
                }
            },
            "messages": [
                {"messageId": "M1", "senderId": "U1", "text": "first"},
                {"messageId": "M2", "senderId": "U2", "text": "latest"},
            ],
        },
        text="ack",
    )

    assert reply_route.called
    assert read_route.called
    assert result["status"] == "ok"
    assert result["applied"] is True
    assert result["readAck"]["required"] is True
    assert result["readAck"]["applied"] is True


@respx.mock
def test_execute_watch_reply_action_honors_mixed_ack_required_alias(
    client: cliq.ZohoCliqClient,
) -> None:
    reply_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/reply"
    ).mock(return_value=httpx.Response(200, json={"data": {"id": "M3"}}))
    read_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read"
    ).mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = client.execute_watch_reply_action(
        {
            "chatId": "CT_1",
            "channelId": "O1",
            "watchIntake": {
                "consumePolicy": {
                    "ack-Req_uired": "true",
                }
            },
            "messages": [
                {"messageId": "M1", "senderId": "U1", "text": "first"},
                {"messageId": "M2", "senderId": "U2", "text": "latest"},
            ],
        },
        text="ack",
    )

    assert reply_route.called
    assert read_route.called
    assert result["status"] == "ok"
    assert result["applied"] is True
    assert result["readAck"]["required"] is True
    assert result["readAck"]["applied"] is True


@respx.mock
def test_execute_watch_reply_action_honors_mixed_action_id_alias(
    client: cliq.ZohoCliqClient,
) -> None:
    reply_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/reply"
    ).mock(return_value=httpx.Response(200, json={"data": {"id": "M3"}}))
    read_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read"
    ).mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = client.execute_watch_reply_action(
        {
            "chatId": "CT_1",
            "channelId": "O1",
            "watch-intake": {
                "consume-policy": {
                    "action-ID": "read-ack-latest",
                }
            },
            "messages": [
                {"messageId": "M1", "senderId": "U1", "text": "first"},
                {"messageId": "M2", "senderId": "U2", "text": "latest"},
            ],
        },
        text="ack",
    )

    assert reply_route.called
    assert read_route.called
    assert result["status"] == "ok"
    assert result["applied"] is True
    assert result["readAck"]["required"] is True
    assert result["readAck"]["applied"] is True


@respx.mock
def test_execute_watch_reply_action_honors_mixed_consume_policy_alias(
    client: cliq.ZohoCliqClient,
) -> None:
    reply_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/reply"
    ).mock(return_value=httpx.Response(200, json={"data": {"id": "M3"}}))
    read_route = respx.post(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read"
    ).mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = client.execute_watch_reply_action(
        {
            "chatId": "CT_1",
            "channelId": "O1",
            "watch-intake": {
                "consume-Poli_cy": {
                    "action-ID": "read-ack-latest",
                }
            },
            "messages": [
                {"messageId": "M1", "senderId": "U1", "text": "first"},
                {"messageId": "M2", "senderId": "U2", "text": "latest"},
            ],
        },
        text="ack",
    )

    assert reply_route.called
    assert read_route.called
    assert result["status"] == "ok"
    assert result["applied"] is True
    assert result["readAck"]["required"] is True
    assert result["readAck"]["applied"] is True


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
def test_execute_watch_read_ack_action_marks_latest_message(
    client: cliq.ZohoCliqClient,
) -> None:
    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M2/read").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M2", "status": "ok"}})
    )

    result = client.execute_watch_read_ack_action(
        {
            "chatId": "CT_1",
            "channelId": "O1",
            "messages": [
                {"messageId": "M1", "senderId": "U1", "text": "first"},
                {"messageId": "M2", "senderId": "U2", "text": "latest"},
            ],
        }
    )

    assert route.called
    assert result["status"] == "ok"
    assert result["action"] == "read-ack-latest"
    assert result["applied"] is True
    assert result["targetMessageId"] == "M2"
    assert result["result"]["id"] == "M2"


def test_execute_watch_read_ack_action_no_messages_returns_noop(
    client: cliq.ZohoCliqClient,
) -> None:
    result = client.execute_watch_read_ack_action(
        {
            "chatId": "CT_1",
            "channelId": "O1",
            "messages": [],
        }
    )

    assert result["status"] == "ok"
    assert result["action"] == "read-ack-latest"
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
def test_cliq_client_get_message_falls_back_to_openapi_alt_path(
    client: cliq.ZohoCliqClient,
) -> None:
    primary = respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    fallback = respx.get(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/messages"
    ).mock(return_value=httpx.Response(200, json={"data": {"id": "M1", "text": "ok"}}))

    result = client.get_message("M1", chat_id="CT_1")

    assert primary.called
    assert fallback.called
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
def test_cliq_client_create_thread_falls_back_to_openapi_channel_message(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/channels/O1").mock(
        return_value=httpx.Response(200, json={"data": {"chat_id": "CT_1"}})
    )
    respx.post(url__regex=r"https://cliq\.zoho\.com/api/v2/chats/CT_1/.*").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.post(
        url__regex=r"https://cliq\.zoho\.com/api/v2/channels/O1/messages/M1/.*"
    ).mock(return_value=httpx.Response(404, text="request_url_invalid"))
    respx.post("https://cliq.zoho.com/api/v2/channels/O1/threads").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    route = respx.post("https://cliq.zoho.com/api/v2/channels/O1/message").mock(
        return_value=httpx.Response(200, json={"data": {"thread_id": "T2"}})
    )

    payload = client.create_thread("M1", "hello thread", channel_id="O1")

    assert route.called
    assert payload["data"]["thread_id"] == "T2"


@respx.mock
def test_cliq_client_reply_thread_falls_back_to_openapi_thread_chat_message(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.post(url__regex=r"https://cliq\.zoho\.com/api/v2/chats/C1/.*").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    route = respx.post("https://cliq.zoho.com/api/v2/chats/CT_THREAD_1/message").mock(
        return_value=httpx.Response(200, json={"data": {"id": "TM1"}})
    )

    payload = client.reply_thread("CT_THREAD_1", "hello", chat_id="C1")

    assert route.called
    assert payload["data"]["id"] == "TM1"


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
def test_cliq_client_list_thread_followers_falls_back_to_root_threads_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/chats/C1/threads/T1/followers").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    route = respx.get("https://cliq.zoho.com/api/v2/threads/T1/followers").mock(
        return_value=httpx.Response(200, json={"data": [{"user_id": "U1"}]})
    )

    payload = client.list_thread_followers("T1", chat_id="C1")

    assert route.called
    assert payload["data"][0]["user_id"] == "U1"


@respx.mock
def test_cliq_client_get_thread_state_falls_back_to_root_threads_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.get("https://cliq.zoho.com/api/v2/chats/C1/threads/T1/state").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/C1/threads/T1").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    route = respx.get("https://cliq.zoho.com/api/v2/threads/T1").mock(
        return_value=httpx.Response(200, json={"data": {"state": "open"}})
    )

    payload = client.get_thread_state("T1", chat_id="C1")

    assert route.called
    assert payload["data"]["state"] == "open"


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
def test_cliq_client_list_pinned_messages_falls_back_to_messages_endpoint(
    client: cliq.ZohoCliqClient,
) -> None:
    primary = respx.get("https://cliq.zoho.com/api/v2/chats/C1/pinned").mock(
        return_value=httpx.Response(
            404,
            json={
                "code": "request_url_invalid",
                "message": "Not found",
            },
        )
    )
    fallback = respx.get("https://cliq.zoho.com/api/v2/chats/C1/messages/pinned").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "M1"}]})
    )

    payload = client.list_pinned_messages(chat_id="C1")
    assert primary.called
    assert fallback.called
    assert payload["data"][0]["id"] == "M1"


@respx.mock
def test_cliq_client_list_pinned_messages_scope_invalid_reports_hint(
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
        client.list_pinned_messages(chat_id="C1")

    err = capsys.readouterr().err
    assert "oauth_scope_invalid" in err
    assert "ZohoCliq.Messages.READ" in err


@respx.mock
def test_cliq_client_list_thread_followers_scope_invalid_reports_hint(
    client: cliq.ZohoCliqClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get(
        url__regex=r"https://cliq\.zoho\.com/api/v2/(chats/C1/.*|threads/T1/.*)"
    ).mock(
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
def test_cliq_client_update_thread_state_falls_back_to_root_threads_put(
    client: cliq.ZohoCliqClient,
) -> None:
    respx.post("https://cliq.zoho.com/api/v2/chats/C1/threads/T1/state").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.put("https://cliq.zoho.com/api/v2/chats/C1/threads/T1/state").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.patch("https://cliq.zoho.com/api/v2/chats/C1/threads/T1/state").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.post("https://cliq.zoho.com/api/v2/chats/C1/threads/T1").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    route = respx.put("https://cliq.zoho.com/api/v2/threads/T1").mock(
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
    respx.get("https://cliq.zoho.com/api/v2/chats/O1/threads").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/O1/threads").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
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
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/threads").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/O1/threads").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M1"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/messages").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/files").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/reactions").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get(
        "https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/messages/reactions"
    ).mock(return_value=httpx.Response(404, text="request_url_invalid"))
    respx.get("https://cliq.zoho.com/api/v2/chats/CT_1/messages/M1/attachments").mock(
        return_value=httpx.Response(401, json={"code": "oauthtoken_scope_invalid"})
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/O1/messages/M1").mock(
        return_value=httpx.Response(200, json={"data": {"id": "M1"}})
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/O1/messages/M1/messages").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/O1/messages/M1/files").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get("https://cliq.zoho.com/api/v2/channels/O1/messages/M1/reactions").mock(
        return_value=httpx.Response(404, text="request_url_invalid")
    )
    respx.get(
        "https://cliq.zoho.com/api/v2/channels/O1/messages/M1/messages/reactions"
    ).mock(return_value=httpx.Response(404, text="request_url_invalid"))
    respx.get("https://cliq.zoho.com/api/v2/channels/O1/messages/M1/attachments").mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    result = client.probe_capabilities(channel_id="O1", message_id="M1")

    checks = {item["name"]: item for item in result["checks"]}
    assert checks["chats.messages.get"]["ok"] is True
    assert checks["chats.messages.get.alt"]["status"] == "not_supported"
    assert checks["chats.messages.reactions"]["status"] == "not_supported"
    assert checks["channels.messages.get.alt"]["status"] == "not_supported"
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
