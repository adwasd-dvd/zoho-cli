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
    assert summary["unsupportedSignal"] is True
    assert summary["unsupportedConsecutiveCount"] == 1
    assert summary["postReleaseDeferred"] is False
    assert summary["recommendedNext"] == "continue_focused_verification"


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
    assert summary["unsupportedSignal"] is True
    assert summary["unsupportedConsecutiveCount"] == 1
    assert summary["postReleaseDeferred"] is False


def test_build_summary_marks_post_release_deferred_after_three_strikes(tmp_path):
    status_file = tmp_path / "status.json"
    app_commands_file = tmp_path / "app_commands.json"
    status_file.write_text(json.dumps({"oauthReady": True, "exportOauthReady": True}))
    app_commands_file.write_text(
        json.dumps(
            {
                "status": "error",
                "error": "not_supported",
            }
        )
    )

    previous_a = tmp_path / "cliq193_app_commands_probe_summary_20260417_120001.json"
    previous_b = tmp_path / "cliq193_app_commands_probe_summary_20260417_120101.json"
    previous_a.write_text(
        json.dumps(
            {
                "stamp": "20260417_120001",
                "appCommandsError": "not_supported",
                "unsupportedSignal": True,
            }
        )
    )
    previous_b.write_text(
        json.dumps(
            {
                "stamp": "20260417_120101",
                "appCommandsError": "empty_output",
                "unsupportedSignal": True,
            }
        )
    )

    summary = build_summary(
        stamp="20260417_120201",
        probe_app_id="APP_PROBE_FAKE_20260417_120201",
        status_command="status",
        app_commands_command="app-commands",
        status_exit_code=0,
        app_commands_exit_code=1,
        status_file=status_file,
        app_commands_file=app_commands_file,
        timestamp_utc="2026-04-17T12:02:01Z",
        history_dir=tmp_path,
        unsupported_threshold=3,
    )

    assert summary["unsupportedConsecutiveCount"] == 3
    assert summary["postReleaseDeferred"] is True
    assert (
        summary["recommendedNext"] == "defer_post_release_and_continue_unblocked_work"
    )
