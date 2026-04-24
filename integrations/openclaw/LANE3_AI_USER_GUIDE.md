# Lane3 AI user guide (skill/docs/scripts)

This guide is for AI users who already have a working local `zoho` CLI and only need lane3 updates.

## What is lane3

- skill: `skill/SKILL.md`
- skill references: `skill/references/*`
- skill scripts: `skill/scripts/*`
- OpenClaw lane3 docs/scripts: `integrations/openclaw/*`

## Skill-only update (no CLI upgrade)

Use this when local CLI runtime is already working and aligned.

```bash
bash integrations/openclaw/bin/pull_lane3_only.sh \
  --workspace "$HOME/.openclaw/workspace-zoho-employee-test" \
  --branch autobot/zoho-platform
```

What it does:
1. sparse-pulls lane3 paths from GitHub
2. syncs `skill/` into `<workspace>/skills/zoho-cli-employee/`
3. saves lane3 docs snapshot under `<workspace>/lane3-docs/`

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
4. summarize command/flag/output and skill-usage changes
5. sync lane3 locally
