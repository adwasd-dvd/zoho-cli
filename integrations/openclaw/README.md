# OpenClaw integration helpers (Lane 3)

This directory contains AI-user-facing skill docs/scripts for OpenClaw.

## Canonical skill source

- `skill/SKILL.md`
- `skill/references/*`
- `skill/scripts/*`

`integrations/openclaw/SKILL.md` is only a pointer file to avoid duplicate maintenance.

## Lane 3 docs and scripts

- `LANE3_AI_USER_GUIDE.md` — AI-user update and sync workflow
- `SKILL_INDEX.md` — maintainers checklist for lane3 alignment
- `bin/pull_lane3_only.sh` — pull/sync only lane3 content (skill/docs/scripts) from GitHub
- `bin/run-scan.example.sh` — optional scan example
- `quick_test.sh` — lightweight smoke example

## Rules

1. Keep lane3 content aligned with CLI behavior changes.
2. Keep repo URL/package references accurate (`adwasd-dvd/zoho-mail-cli-zomacli`).
3. For isolated agents, install skill locally inside the agent workspace, not global `~/.openclaw/skills`.
