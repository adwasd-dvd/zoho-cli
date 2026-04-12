from __future__ import annotations

import json
import os
import sys
from typing import Any

import yaml


def _load_yaml(file_path: str) -> tuple[bool, Any, str]:
    if not os.path.exists(file_path):
        return False, None, f"VALIDATION_FAILED: file not found: {file_path}"
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as exc:  # noqa: BLE001
        return (
            False,
            None,
            f"VALIDATION_FAILED: failed to parse YAML {file_path}: {exc}",
        )

    if data is None:
        data = {}
    if not isinstance(data, dict):
        return (
            False,
            None,
            f"VALIDATION_FAILED: top-level YAML value is not a map in {file_path}",
        )
    return True, data, ""


def walk_and_check(data: dict[str, Any], expected: dict[str, Any]) -> tuple[bool, str]:
    for key, expected_value in expected.items():
        if isinstance(expected_value, dict):
            nested = data.get(key)
            if not isinstance(nested, dict):
                return False, f"key missing or not a map: {key}"
            success, message = walk_and_check(nested, expected_value)
            if not success:
                return False, message
            continue

        if key not in data:
            return False, f"key missing: {key}"
        if data[key] != expected_value:
            return (
                False,
                f"value mismatch for {key}: expected {expected_value!r}, got {data[key]!r}",
            )
    return True, "OK"


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: python state_validator.py <file_path> <expected_json>")
        return 1

    target_file = sys.argv[1]
    try:
        expected_data = json.loads(sys.argv[2])
    except Exception as exc:  # noqa: BLE001
        print(f"VALIDATION_FAILED: invalid expected JSON: {exc}")
        return 1

    if not isinstance(expected_data, dict):
        print("VALIDATION_FAILED: expected_json must decode to an object/map")
        return 1

    loaded, actual_data, message = _load_yaml(target_file)
    if not loaded:
        print(message)
        return 1

    success, result = walk_and_check(actual_data, expected_data)
    if success:
        print("VALIDATION_SUCCESS")
        return 0

    print(f"VALIDATION_FAILED: {result}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
