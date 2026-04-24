# Skill maintenance checklist

Run this whenever command surfaces or workflows change.

1. Refresh CLI help snapshot:
   ```bash
   python skill/scripts/refresh_cli_help_snapshot.py --runner "./.venv/bin/python -m zoho_cli"
   ```
2. Update `skill/references/command-playbook.md` if new commands are user-facing.
3. Keep `skill/references/install-and-update.md` aligned with current repo URL and installer behavior.
4. Run focused validation:
   ```bash
   ./.venv/bin/python -m pytest -q tests/test_openclaw_skill.py
   ```
5. Update changelog and state files for traceability.
