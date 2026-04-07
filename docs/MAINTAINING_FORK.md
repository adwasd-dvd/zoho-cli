# Maintaining this fork

## What was found in the original local workspace

The local workspace contained three layers mixed together:

1. the real `zoho-cli` source repository
2. OpenClaw skill/helper files
3. one-off debugging experiments and local workspace artifacts

This cleaned package separates them so the GitHub repo can stay maintainable.

## Canonical directories

- `zoho_cli/` — source code
- `tests/` — automated tests
- `skill/` — canonical agent skill file shipped with the repo
- `integrations/openclaw/` — optional helper material for OpenClaw
- `experiments/attachment-debug/` — sanitized debugging history

## Things to keep out of GitHub

- local workspace memory files
- mailbox dumps and attachment outputs
- personal email addresses when not necessary
- local absolute paths
- OAuth config / secrets / token files
- account-specific message IDs in docs or tests

## Release checklist

1. Run `pytest -q`
2. Search the repo for sensitive strings
3. Update `README.md` and `skill/SKILL.md` together
4. Bump version in `pyproject.toml` and `zoho_cli/__init__.py`
5. Tag release

## Suggested GitHub model

- `main` = stable fork
- feature branches for fixes
- keep `upstream` remote pointed at the original repo
- periodically rebase or cherry-pick from upstream if the fork diverges
