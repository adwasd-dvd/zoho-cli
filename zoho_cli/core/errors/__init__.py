"""Core error types and utilities."""

from __future__ import annotations

import json
import sys
from typing import Any


class ApiError(Exception):
    """Raised when a Zoho API call fails."""

    def __init__(self, code: str, details: str, exit_code: int = 1) -> None:
        self.code = code
        self.details = details
        self.exit_code = exit_code
        super().__init__(details)

    @classmethod
    def from_response(cls, resp: Any) -> ApiError:
        """Create an ApiError from an httpx.Response."""
        try:
            data = resp.json()
            code = data.get("code", "api_error")
            details = data.get("description", f"HTTP {resp.status_code}")
        except Exception:
            code = "api_error"
            details = f"HTTP {resp.status_code}: {resp.text[:200]}"
        return cls(code, details)


def error_exit(code: str, details: str, exit_code: int = 1) -> None:
    """Print error to stderr and exit."""
    payload = {"status": "error", "error": code, "details": details}
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
    sys.exit(exit_code)


__all__ = ["ApiError", "error_exit"]
