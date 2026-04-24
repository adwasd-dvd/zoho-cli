# OpenClaw starter pack

This pack is for running `zoho-cli` as a long-lived project with unattended agents.

## What this adds

- project roadmap for Mail → Cliq → CRM
- state files in `ops/state/`
- cron prompt files in `ops/prompts/`
- workspace bootstrap script
- paste-ready kickoff commands

## Fastest path

From the repository root:

```bash
bash integrations/openclaw/bin/bootstrap_openclaw_workspace.sh --repo "$(pwd)"
```

That will create a dedicated OpenClaw project workspace and print the next commands to copy.

## After bootstrap

1. start or restart OpenClaw
2. point your agent at the generated workspace folder
3. paste the kickoff prompt from `integrations/openclaw/templates/KICKOFF_PROMPT.md`
4. create recurring jobs using the prompt files under `ops/prompts/`

## Ground rules for agents

- read `AGENTS.md` first
- use `ops/state/` as the source of truth
- keep work small and test-backed
- follow the product order: Mail, then Cliq, then CRM
