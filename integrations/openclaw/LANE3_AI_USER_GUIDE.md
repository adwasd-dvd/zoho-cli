# Lane3 AI user guide (skill/docs/scripts)

This guide is for AI users who already have a working local `zoho` CLI and only need lane3 updates.

## What is lane3

- skill: `skill/SKILL.md`
- skill references: `skill/references/*`
- skill scripts: `skill/scripts/*`
- OpenClaw lane3 docs/scripts: `integrations/openclaw/*`
- native channel planning docs: `docs/architecture/OPENCLAW_CLIQ_CHANNEL_0_4_PLAN.md`, `skill/references/openclaw-cliq-channel.md`, and `integrations/openclaw/CLIQ_CHANNEL_DEVELOPMENT_GUIDE.md`

## Skill-only update (no CLI upgrade)

Use this when local CLI runtime is already working and aligned. This is the default for `zoho-employee-test` in your current setup.

```bash
bash integrations/openclaw/bin/pull_lane3_only.sh \
  --workspace "$HOME/.openclaw/workspace-zoho-employee-test" \
  --branch autobot/zoho-platform
```

What it does:
1. sparse-pulls lane3 paths from GitHub
2. syncs `skill/` into `<workspace>/skills/zoho-cli-employee/`
3. saves lane3 docs snapshot under `<workspace>/lane3-docs/`
4. keeps CLI binary/runtime untouched

## Full update (CLI + skill)

Only use this when user explicitly approves CLI upgrade.

```bash
git -C ~/zoho-mail-cli-zomacli pull --ff-only
uv tool install --upgrade git+https://github.com/adwasd-dvd/zoho-mail-cli-zomacli
bash integrations/openclaw/bin/pull_lane3_only.sh --workspace "$HOME/.openclaw/workspace-zoho-employee-test"
```

## Alignment checklist before sync

1. inspect code delta
2. inspect docs delta
3. inspect lane3 delta
4. inspect native channel docs when `cliq-channel-*` or v0.4 planning changed
5. summarize command/flag/output, channel, security, and skill-usage changes
6. sync lane3 locally

Current implementation-only delta:
- `cliq-210` moved `zoho cliq status` and `zoho cliq capabilities` command bodies into `zoho_cli/commands/cliq_readiness.py`; AI-user command patterns are unchanged.
- `cliq-210` also moved `zoho cliq whoami` and `zoho cliq user-resolve` command bodies into `zoho_cli/commands/cliq_identity.py`; AI-user command patterns are unchanged.
- `cliq-210` also moved `zoho cliq users` and `zoho cliq teams` command bodies into `zoho_cli/commands/cliq_org_directory.py`; AI-user command patterns are unchanged.
- `cliq-210` also moved org-admin list command bodies (`departments`, `roles`, `designations`, `user-status`, `userfields`) into `zoho_cli/commands/cliq_org_admin.py`; AI-user command patterns are unchanged.
- `cliq-210` also moved productivity/platform list command bodies (`events`, `reminders`, `meetings`, `databases`) into `zoho_cli/commands/cliq_productivity.py`; AI-user command patterns are unchanged.
- `cliq-210` also moved platform-extension list command bodies (`widgets`, `map-tickers`, `custom-domains`, `custom-emails`) into `zoho_cli/commands/cliq_platform_extensions.py`; AI-user command patterns are unchanged.
- v0.4 planning now reserves the next major feature lane for a native OpenClaw Cliq channel; CRM expansion moves to v0.5.

## Required behavior support after lane3 sync

After sync, ensure the AI user follows:

- unread polling with self-reaction exclusion:
  - `zoho cliq chats --unread-only --exclude-reacted-by-self`
- reaction status lifecycle updates via:
  - `zoho cliq status-react --status received|thinking|writing|testing|blocked|done|failed --clear-known`
- context-before-reply in loops:
  - `zoho cliq context ...` before `zoho cliq reply ...`
- native channel development/operation docs when relevant:
  - read `skill/references/openclaw-cliq-channel.md`
  - read `integrations/openclaw/CLIQ_CHANNEL_DEVELOPMENT_GUIDE.md`
