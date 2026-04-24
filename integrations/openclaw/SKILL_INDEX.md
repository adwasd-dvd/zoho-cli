# OpenClaw skill index

## Source of truth

- `skill/SKILL.md`
- `skill/references/*`
- `skill/scripts/refresh_cli_help_snapshot.py`

## Install / update helpers

- Install skill locally: `integrations/openclaw/bin/install_openclaw_skill.sh`
- Update repo + CLI + skill: `integrations/openclaw/bin/update_openclaw_zoho_stack.sh`

## Maintenance loop

1. Update CLI surface/docs.
2. Refresh help snapshot:
   ```bash
   ./.venv/bin/python skill/scripts/refresh_cli_help_snapshot.py --runner "./.venv/bin/python -m zoho_cli"
   ```
3. Run focused skill test:
   ```bash
   ./.venv/bin/python -m pytest -q tests/test_openclaw_skill.py
   ```
