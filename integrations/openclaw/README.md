# OpenClaw integration helpers

This folder contains operational scripts/templates for running `zoho-cli` with OpenClaw.

## Canonical skill location

- Skill source of truth: `skill/`
- Main file: `skill/SKILL.md`

## Install skill for a local OpenClaw user

```bash
bash integrations/openclaw/bin/install_openclaw_skill.sh --repo "$(pwd)" --skill-name zoho-cli-employee
```

Default target path:

- `~/.openclaw/skills/zoho-cli-employee`

## Update CLI + skill after GitHub changes

```bash
bash integrations/openclaw/bin/update_openclaw_zoho_stack.sh --repo "$(pwd)"
```

This performs:

1. `git pull --ff-only`
2. CLI upgrade (`uv` preferred, `pipx` fallback)
3. skill reinstall to OpenClaw skills directory

## Included helpers

- `bin/install_openclaw_skill.sh`
- `bin/update_openclaw_zoho_stack.sh`
- `bin/bootstrap_openclaw_workspace.sh`
- templates and workspace bootstrap references
