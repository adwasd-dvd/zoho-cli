from __future__ import annotations

import typer

from zoho_cli.registry import register_root_commands


def test_register_root_commands_is_noop_scaffold() -> None:
    app = typer.Typer()
    before = len(app.registered_commands)

    register_root_commands(app)

    assert len(app.registered_commands) == before


def test_register_root_commands_runs_supplied_registrars_in_order() -> None:
    app = typer.Typer()
    seen: list[str] = []

    def first(_app: typer.Typer) -> None:
        seen.append("first")

    def second(_app: typer.Typer) -> None:
        seen.append("second")

    register_root_commands(app, registrars=(first, second))

    assert seen == ["first", "second"]
