# Install and update (OpenClaw + zoho-cli)

## Approval rule

Before running install/upgrade commands, get explicit user approval.

## One-time install for a new OpenClaw user

```bash
# 1) clone repo
git clone https://github.com/adwasd-dvd/zoho-cli ~/zoho-cli

# 2) install/upgrade CLI (choose one installer)
uv tool install git+https://github.com/adwasd-dvd/zoho-cli
# or
pipx install git+https://github.com/adwasd-dvd/zoho-cli

# 3) install the skill into OpenClaw
~/zoho-cli/integrations/openclaw/bin/install_openclaw_skill.sh --repo ~/zoho-cli --skill-name zoho-cli-employee
```

## Update flow after GitHub changes

```bash
~/zoho-cli/integrations/openclaw/bin/update_openclaw_zoho_stack.sh --repo ~/zoho-cli
```

What this does:

1. `git pull --ff-only` in the local repo.
2. upgrades the CLI (`uv` first, then `pipx` fallback).
3. re-installs the latest skill files to `~/.openclaw/skills/zoho-cli-employee`.

## Manual fallback

```bash
git -C ~/zoho-cli pull --ff-only
uv tool install --upgrade git+https://github.com/adwasd-dvd/zoho-cli
~/zoho-cli/integrations/openclaw/bin/install_openclaw_skill.sh --repo ~/zoho-cli --skill-name zoho-cli-employee
```
