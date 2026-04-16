from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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
) -> dict[str, Any]:
    status_payload = _read_json_dict(status_file)
    app_payload = _read_json_dict(app_commands_file)

    auth_payload = status_payload.get("auth")
    auth_ok = isinstance(auth_payload, dict) and str(
        auth_payload.get("status", "")
    ).lower() in {"ok", "ready"}

    oauth_ready = bool(status_payload.get("oauthReady")) or auth_ok
    export_oauth_ready = bool(status_payload.get("exportOauthReady"))

    return {
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
        "appCommandsError": _extract_app_error(app_payload),
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
    args = parser.parse_args()

    stamp = str(args.stamp)
    probe_app_id = args.probe_app_id or f"APP_PROBE_FAKE_{stamp}"

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
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
