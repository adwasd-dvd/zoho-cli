# Zoho CLI + OpenClaw index

## Status

- Core repo: `zoho-cli`
- Maintained fork: `adwasd-dvd/zoho-cli`
- OpenClaw skill file: `skill/SKILL.md`
- OpenClaw helper files: `integrations/openclaw/`

## Recommended workflow

1. Make code changes in `zoho_cli/` and tests in `tests/`.
2. Update agent-facing docs in `skill/SKILL.md` if commands or install steps change.
3. Keep only generic helper scripts in this folder.
4. Never commit local workspace notes, raw mailbox output, or account-specific IDs.

## Safety checks before pushing

- Search for real email addresses or message IDs
- Search for local absolute paths
- Search for `client_secret`, `refresh_token`, `access_token`
- Run the test suite
