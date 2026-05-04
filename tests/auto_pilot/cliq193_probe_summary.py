from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_SUMMARY_FILE_PATTERN = re.compile(
    r"^cliq193_app_commands_probe_summary_(\d{8}_\d{6})\.json$"
)
_UNSUPPORTED_ERRORS = {
    "empty_output",
    "inactive_appaccount_user",
    "not_supported",
    "operation_not_allowed",
    "unsupported",
}

_STDERR_UNSUPPORTED_HINTS: tuple[tuple[str, str], ...] = (
    ("inactive_appaccount_user", "inactive_appaccount_user"),
    ("operation_not_allowed", "operation_not_allowed"),
    ("not_supported", "not_supported"),
    ("unsupported", "unsupported"),
)


def _read_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8", errors="replace").strip()
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return {"_invalid_json": True, "_raw": raw}
    if isinstance(loaded, dict):
        return loaded
    return {"_non_dict_json": True, "value": loaded}


def _extract_app_error(app_payload: dict[str, Any]) -> str | None:
    if not app_payload:
        return "empty_output"
    if app_payload.get("_invalid_json"):
        return "invalid_json_output"
    error = app_payload.get("error")
    if isinstance(error, str) and error.strip():
        return error.strip()
    if app_payload.get("status") == "error":
        return "error"
    return None


def _extract_app_error_from_stderr(app_commands_file: Path) -> str | None:
    candidates = (
        app_commands_file.with_suffix(".stderr"),
        app_commands_file.with_suffix(".stderr.txt"),
        app_commands_file.with_suffix(".stderr.log"),
    )
    for candidate in candidates:
        if not candidate.exists():
            continue
        body = candidate.read_text(encoding="utf-8", errors="replace").strip().lower()
        if not body:
            continue
        for needle, normalized in _STDERR_UNSUPPORTED_HINTS:
            if needle in body:
                return normalized
    return None


def _is_unsupported_error(error: str | None) -> bool:
    if not isinstance(error, str):
        return False
    return error.strip().lower() in _UNSUPPORTED_ERRORS


def _read_previous_summaries(
    history_dir: Path,
    *,
    current_stamp: str,
) -> list[dict[str, Any]]:
    if not history_dir.exists():
        return []

    rows: list[tuple[str, dict[str, Any]]] = []
    for path in history_dir.glob("cliq193_app_commands_probe_summary_*.json"):
        match = _SUMMARY_FILE_PATTERN.match(path.name)
        if not match:
            continue
        stamp = match.group(1)
        if stamp >= current_stamp:
            continue
        payload = _read_json_dict(path)
        if payload:
            rows.append((stamp, payload))

    rows.sort(key=lambda item: item[0], reverse=True)
    return [payload for _, payload in rows]


def _is_unsupported_summary(summary: dict[str, Any]) -> bool:
    marker = summary.get("unsupportedSignal")
    if isinstance(marker, bool):
        return marker
    return _is_unsupported_error(summary.get("appCommandsError"))


def build_summary(
    *,
    stamp: str,
    probe_app_id: str,
    status_command: str,
    app_commands_command: str,
    status_exit_code: int,
    app_commands_exit_code: int,
    status_file: Path,
    app_commands_file: Path,
    timestamp_utc: str | None = None,
    history_dir: Path | None = None,
    unsupported_threshold: int = 3,
) -> dict[str, Any]:
    status_payload = _read_json_dict(status_file)
    app_payload = _read_json_dict(app_commands_file)

    auth_payload = status_payload.get("auth")
    auth_ok = isinstance(auth_payload, dict) and str(
        auth_payload.get("status", "")
    ).lower() in {"ok", "ready"}

    oauth_ready = bool(status_payload.get("oauthReady")) or auth_ok
    export_oauth_ready = bool(status_payload.get("exportOauthReady"))
    app_commands_error = _extract_app_error(app_payload)
    if app_commands_error == "empty_output":
        stderr_error = _extract_app_error_from_stderr(app_commands_file)
        if stderr_error:
            app_commands_error = stderr_error
    unsupported_signal = _is_unsupported_error(app_commands_error)
    unsupported_consecutive_count = 0
    if unsupported_signal:
        unsupported_consecutive_count = 1
        if history_dir is not None:
            for previous in _read_previous_summaries(history_dir, current_stamp=stamp):
                if not _is_unsupported_summary(previous):
                    break
                unsupported_consecutive_count += 1

    post_release_deferred = unsupported_consecutive_count >= max(
        1, int(unsupported_threshold)
    )
    recommended_next = (
        "defer_post_release_and_continue_unblocked_work"
        if post_release_deferred
        else "continue_focused_verification"
    )

    return {
        "summaryVersion": 2,
        "timestampUtc": timestamp_utc
        or datetime.now(tz=timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "stamp": stamp,
        "probeAppId": probe_app_id,
        "statusCommand": status_command,
        "appCommandsCommand": app_commands_command,
        "statusExitCode": status_exit_code,
        "appCommandsExitCode": app_commands_exit_code,
        "statusFile": str(status_file.as_posix()),
        "appCommandsFile": str(app_commands_file.as_posix()),
        "oauthReady": oauth_ready,
        "exportOauthReady": export_oauth_ready,
        "appCommandsError": app_commands_error,
        "unsupportedSignal": unsupported_signal,
        "unsupportedConsecutiveCount": unsupported_consecutive_count,
        "unsupportedThreshold": max(1, int(unsupported_threshold)),
        "postReleaseDeferred": post_release_deferred,
        "recommendedNext": recommended_next,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build cliq-193 app-commands probe summary JSON from report files."
    )
    parser.add_argument("--stamp", required=True)
    parser.add_argument("--status-file", required=True)
    parser.add_argument("--app-commands-file", required=True)
    parser.add_argument("--status-command", required=True)
    parser.add_argument("--app-commands-command", required=True)
    parser.add_argument("--status-exit-code", type=int, required=True)
    parser.add_argument("--app-commands-exit-code", type=int, required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--probe-app-id", default=None)
    parser.add_argument("--timestamp-utc", default=None)
    parser.add_argument("--history-dir", default=None)
    parser.add_argument("--unsupported-threshold", type=int, default=3)
    args = parser.parse_args()

    stamp = str(args.stamp)
    probe_app_id = args.probe_app_id or f"APP_PROBE_FAKE_{stamp}"

    output = Path(args.output)
    history_dir = Path(args.history_dir) if args.history_dir else output.parent

    summary = build_summary(
        stamp=stamp,
        probe_app_id=probe_app_id,
        status_command=args.status_command,
        app_commands_command=args.app_commands_command,
        status_exit_code=args.status_exit_code,
        app_commands_exit_code=args.app_commands_exit_code,
        status_file=Path(args.status_file),
        app_commands_file=Path(args.app_commands_file),
        timestamp_utc=args.timestamp_utc,
        history_dir=history_dir,
        unsupported_threshold=args.unsupported_threshold,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
