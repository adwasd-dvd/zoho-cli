#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shlex
import subprocess
from datetime import UTC, datetime
from pathlib import Path


COMMAND_SUFFIXES: list[list[str]] = [
    ["--help"],
    ["login", "--help"],
    ["config", "--help"],
    ["mail", "--help"],
    ["cliq", "--help"],
    ["crm", "--help"],
    ["crm", "upsert", "--help"],
    ["crm", "upsert-gate", "--help"],
    ["crm", "write-audit", "--help"],
]


def _run_command(base_tokens: list[str], suffix: list[str]) -> tuple[str, int, str]:
    cmd = base_tokens + suffix
    proc = subprocess.run(cmd, capture_output=True, text=True)
    text = proc.stdout if proc.stdout.strip() else proc.stderr
    output = "\n".join(line.rstrip() for line in text.rstrip().splitlines())
    return " ".join(shlex.quote(token) for token in cmd), proc.returncode, output


def _build_snapshot(base_tokens: list[str]) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines: list[str] = [
        "# CLI help snapshot",
        "",
        f"Generated at: `{now}`",
        "",
        "Use this file as a quick command-surface reference for the skill.",
        "",
    ]

    for suffix in COMMAND_SUFFIXES:
        command_text, return_code, output = _run_command(base_tokens, suffix)
        lines.extend(
            [
                f"## `{command_text}`",
                "",
                f"Exit code: `{return_code}`",
                "",
                "```text",
                output or "(no output)",
                "```",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Refresh skill/references/cli-help-snapshot.md from live CLI --help output."
    )
    parser.add_argument(
        "--runner",
        default="zoho",
        help="Base command used to invoke the CLI (default: zoho).",
    )
    parser.add_argument(
        "--output",
        default="skill/references/cli-help-snapshot.md",
        help="Output markdown file path (default: skill/references/cli-help-snapshot.md).",
    )
    args = parser.parse_args()

    base_tokens = shlex.split(args.runner)
    if not base_tokens:
        raise SystemExit("--runner must resolve to at least one token")

    output_path = Path(args.output)
    snapshot = _build_snapshot(base_tokens)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(snapshot, encoding="utf-8")
    print(f"wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
