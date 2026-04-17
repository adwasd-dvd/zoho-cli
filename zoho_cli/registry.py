"""Central command registration hooks for modularized CLI wiring.

Platform-200 starts with this no-op scaffold so later platform-201/202 slices can
move command registration out of ``zoho_cli.cli`` without changing CLI behavior.
"""

from __future__ import annotations

import typer


def register_root_commands(app: typer.Typer) -> None:
    """Register sub-apps/commands on the root app.

    This is intentionally a no-op until registration extraction lands.
    """
    return None


__all__ = ["register_root_commands"]
