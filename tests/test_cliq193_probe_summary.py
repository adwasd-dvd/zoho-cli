from __future__ import annotations

import json

from tests.auto_pilot.cliq193_probe_summary import build_summary


def test_build_summary_handles_string_auth_and_empty_app_output(tmp_path):
    status_file = tmp_path / "status.json"
    app_commands_file = tmp_path / "app_commands.json"
    status_file.write_text(
        json.dumps(
            {
                "oauthReady": True,
                "exportOauthReady": True,
                "auth": "ok",
            }
        )
    )
    app_commands_file.write_text("")

    summary = build_summary(
        stamp="20260416_025358",
        probe_app_id="APP_PROBE_FAKE_20260416_025358",
        status_command="status",
        app_commands_command="app-commands",
        status_exit_code=0,
        app_commands_exit_code=1,
        status_file=status_file,
        app_commands_file=app_commands_file,
        timestamp_utc="2026-04-16T02:53:58Z",
    )

    assert summary["oauthReady"] is True
    assert summary["exportOauthReady"] is True
    assert summary["appCommandsError"] == "empty_output"


def test_build_summary_extracts_api_error(tmp_path):
    status_file = tmp_path / "status.json"
    app_commands_file = tmp_path / "app_commands.json"
    status_file.write_text(json.dumps({"oauthReady": True, "exportOauthReady": True}))
    app_commands_file.write_text(
        json.dumps(
            {
                "status": "error",
                "error": "not_supported",
                "details": "unsupported endpoint",
            }
        )
    )

    summary = build_summary(
        stamp="20260416_025449",
        probe_app_id="APP_PROBE_FAKE_20260416_025449",
        status_command="status",
        app_commands_command="app-commands",
        status_exit_code=0,
        app_commands_exit_code=1,
        status_file=status_file,
        app_commands_file=app_commands_file,
        timestamp_utc="2026-04-16T02:54:52Z",
    )

    assert summary["appCommandsError"] == "not_supported"
