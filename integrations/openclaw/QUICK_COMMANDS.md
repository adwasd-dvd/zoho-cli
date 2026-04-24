# Quick commands

## 1) In your repo root

```bash
git pull
bash integrations/openclaw/bin/bootstrap_openclaw_workspace.sh --repo "$(pwd)"
bash integrations/openclaw/bin/install_openclaw_skill.sh --repo "$(pwd)" --skill-name zoho-cli-employee
openclaw gateway restart
openclaw tui
```

## 2) In the agent chat, paste this

```text
Read `integrations/openclaw/templates/ZOHO_EMPLOYEE_AGENT_PROMPT.md` and `skill/SKILL.md`, then act on them now. Work only inside this repository. Follow the product order Mail → Cliq → CRM. Use `ops/state/` as the source of truth and update it as you go.
```

## 3) For recurring jobs, use these prompt files

- `ops/prompts/planner.md`
- `ops/prompts/builder.md`
- `ops/prompts/verifier.md`
- `ops/prompts/fixer.md`
- `ops/prompts/release-manager.md`
- `ops/prompts/nightly-smoke.md`

## 4) Schedule reference

See:

- `ops/cron/README.md`
- `ops/cron/cron-jobs.example.md`
