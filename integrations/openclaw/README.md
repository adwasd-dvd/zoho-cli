# OpenClaw integration helpers

This folder contains a cleaned, GitHub-safe copy of the OpenClaw-facing material that was previously scattered across a local workspace.

## Included

- `SKILL.md` — agent-facing skill document
- `SKILL_INDEX.md` — short index for maintainers
- `bin/run-scan.example.sh` — example long-running mail scan wrapper
- `quick_test.sh` — generic smoke test that auto-finds a message with attachments
- `repair_pipx_install.sh` — patch helper for an already-installed pipx copy

## Notes

- All hard-coded user paths, account emails, channel IDs, and message IDs were removed.
- For public GitHub maintenance, keep real account names, tokens, and message IDs out of the repo.
- The canonical packaged skill file in this repository remains `skill/SKILL.md`. This folder just adds operational helpers.
