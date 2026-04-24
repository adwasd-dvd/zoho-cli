# Zoho CLI + OpenClaw index

## Status

- Core repo: `zoho-mail-cli-zomacli`
- Maintained fork: `adwasd-dvd/zoho-mail-cli-zomacli`
- Canonical skill file: `skill/SKILL.md`
- OpenClaw helper files: `integrations/openclaw/`

## Required maintenance workflow

1. Make CLI/test changes in `zoho_cli/` and `tests/`.
2. Update human-facing docs (`README.md`, `docs/*`) for any user-visible change.
3. Update AI-facing docs (`skill/SKILL.md`, `integrations/openclaw/*`) for command/install/update changes.
4. Keep `docs/DOCUMENTATION_LANES.md` contract satisfied before merge.

## AI-user update alignment checklist (after GitHub pull)

1. Compare code changes (`git log --oneline <old>..HEAD`).
2. Compare human-impact docs (`README.md`, `docs/releases/CHANGELOG.next.md`).
3. Compare AI-impact docs (`skill/SKILL.md`, `integrations/openclaw/*`).
4. Summarize CLI changes + skill usage changes.
5. Confirm understanding, then update local CLI + local skill together.

## Safety checks before pushing

- Search for real email addresses or message IDs.
- Search for local absolute paths.
- Search for `client_secret`, `refresh_token`, `access_token`.
- Run focused tests relevant to the changed surface.
