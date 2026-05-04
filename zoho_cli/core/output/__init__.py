"""Output formatting: JSON (default) and Markdown tables."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from rich.console import Console

logger = logging.getLogger(__name__)

_err = Console(stderr=True, highlight=False)
_out = Console(highlight=False)

_md_mode: bool = False


def configure(*, md: bool = False) -> None:
    global _md_mode
    _md_mode = md


def is_md_mode() -> bool:
    return _md_mode


def output(data: Any, *, md_render: Optional[Callable[[Any], None]] = None) -> None:
    """JSON by default. If --md is set and md_render provided, call it."""
    if _md_mode and md_render is not None:
        md_render(data)
    else:
        _print_json(data)


def output_json(data: Any) -> None:
    """Always print JSON (used where only JSON makes sense)."""
    _print_json(data)


def output_status(message: str, extra: Optional[dict] = None) -> None:
    """Success result.

    JSON mode → {"status": "ok", ...extra}
    Markdown  → ✓ message
    """
    if _md_mode:
        _out.print(f"[bold green]✓[/bold green]  {message}")
    else:
        payload: dict = {"status": "ok"}
        if extra:
            payload.update(extra)
        _print_json(payload)


def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    """Generate a GitHub-flavoured markdown table."""
    sep = ["---"] * len(headers)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(sep) + " |",
        *("| " + " | ".join(str(c) for c in row) + " |" for row in rows),
    ]
    return "\n".join(lines)


def format_date(raw: Any) -> str:
    """Format Zoho ms-epoch timestamp to a readable string."""
    if not raw:
        return ""
    try:
        ts = int(raw)
        dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        now = datetime.now(tz=timezone.utc)
        if dt.date() == now.date():
            return dt.strftime("%H:%M")
        if dt.year == now.year:
            return dt.strftime("%b %d")
        return dt.strftime("%b %d %Y")
    except (ValueError, TypeError):
        return str(raw)[:16]


def format_size(size: int) -> str:
    """Format bytes to human-readable size."""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f} {unit}"
        size //= 1024
    return f"{size} TB"


__all__ = [
    "configure",
    "is_md_mode",
    "output",
    "output_json",
    "output_status",
    "md_table",
    "format_date",
    "format_size",
]
