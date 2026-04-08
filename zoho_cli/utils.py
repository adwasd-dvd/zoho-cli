"""Output helpers.

Default output is always JSON (stdout).
--md flag switches to Markdown tables/text.
Errors always go to stderr.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import NoReturn

from rich.console import Console

from zoho_cli.core.output import (
    configure,
    format_date,
    format_size,
    is_md_mode,
    md_table,
    output,
    output_json,
    output_status,
)

logger = logging.getLogger("zoho_cli")

_err = Console(stderr=True, highlight=False)


# ── errors ────────────────────────────────────────────────────────────────────


def error_exit(code: str, details: str, exit_code: int = 1) -> NoReturn:
    """Print error to stderr and exit."""
    if is_md_mode():
        _err.print(f"[bold red]Error:[/bold red] {details}")
    else:
        print(
            json.dumps({"status": "error", "error": code, "details": details}),
            file=sys.stderr,
        )
    raise SystemExit(exit_code)


# ── debug ─────────────────────────────────────────────────────────────────────


def setup_debug() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        stream=sys.stderr,
        format="[DEBUG] %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
