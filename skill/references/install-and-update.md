# Install and update (agent-local skill + Zoho CLI `zoho`)

## Approval rule

Before running install/upgrade commands, get explicit user approval.

## One-time install for a new OpenClaw user

```bash
# 1) clone repo
git clone https://github.com/adwasd-dvd/zoho-mail-cli-zomacli ~/zoho-mail-cli-zomacli

# 2) install/upgrade CLI (choose one installer)
uv tool install git+https://github.com/adwasd-dvd/zoho-mail-cli-zomacli
# or
pipx install git+https://github.com/adwasd-dvd/zoho-mail-cli-zomacli

# 3) install skill into this agent-local workspace (NOT global ~/.openclaw/skills)
bash ~/zoho-mail-cli-zomacli/integrations/openclaw/bin/pull_lane3_only.sh \
  --workspace "$HOME/.openclaw/workspace-zoho-employee-test" \
  --branch autobot/zoho-platform
```

## Skill-only update after GitHub changes (no CLI upgrade)

Use this when local CLI runtime is already working:

```bash
bash ~/zoho-mail-cli-zomacli/integrations/openclaw/bin/pull_lane3_only.sh \
  --workspace "$HOME/.openclaw/workspace-zoho-employee-test" \
  --branch autobot/zoho-platform
```

## Full update flow (CLI + skill)

```bash
git -C ~/zoho-mail-cli-zomacli pull --ff-only
uv tool install --upgrade git+https://github.com/adwasd-dvd/zoho-mail-cli-zomacli
bash ~/zoho-mail-cli-zomacli/integrations/openclaw/bin/pull_lane3_only.sh \
  --workspace "$HOME/.openclaw/workspace-zoho-employee-test" \
  --branch autobot/zoho-platform
```

What this does:

1. pulls latest repository state from GitHub.
2. optionally upgrades CLI (only in full update flow).
3. syncs lane3 skill/docs/scripts into the agent-local workspace.

## RC alignment check

For the `0.2.1rc1` AI-employee RC, verify the CLI and skill update together:

```bash
zoho --version
zoho cliq --help >/dev/null
zoho mail --help >/dev/null
```

Expected version after the RC update: `0.2.1rc1`.
