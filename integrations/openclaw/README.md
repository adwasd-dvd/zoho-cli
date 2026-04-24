# OpenClaw integration helpers

This folder contains OpenClaw-facing skill docs and operational helpers.

## Included

- `SKILL.md` — OpenClaw skill-facing document copy
- `SKILL_INDEX.md` — maintainer workflow + alignment checklist
- `bin/run-scan.example.sh` — example long-running mail scan wrapper
- `quick_test.sh` — generic smoke test that auto-finds a message with attachments
- `repair_pipx_install.sh` — patch helper for an already-installed pipx copy

## Contract

- Canonical skill file in this repository: `skill/SKILL.md`.
- Keep this folder aligned when CLI commands/flags/install/update behavior changes.
- Follow `docs/DOCUMENTATION_LANES.md` and update both human docs and AI docs in the same change slice.

## Safety notes

- Keep real account names, tokens, and message IDs out of committed docs/scripts.
- Do not publish local absolute machine-specific paths.
