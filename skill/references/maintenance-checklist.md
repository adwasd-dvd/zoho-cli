# Skill maintenance checklist

Run this whenever command surfaces or workflows change.

1. Refresh CLI help snapshot:
   ```bash
   python skill/scripts/refresh_cli_help_snapshot.py --runner "./.venv/bin/python -m zoho_cli"
   ```
2. Update `skill/references/command-playbook.md` and `skill/references/unread-status-workflow.md` when Cliq polling/status behavior changes.
3. Keep `skill/references/install-and-update.md` aligned with current repo URL and lane3 sync behavior (`integrations/openclaw/bin/pull_lane3_only.sh`).
4. Verify help surface still contains required loop/status commands:
   ```bash
   ./.venv/bin/python -m zoho_cli cliq --help | rg -n "status-react|mark-read|chats|context|reply"
   ./.venv/bin/python -m zoho_cli cliq chats --help | rg -n "unread-only|exclude-reacted-by-self"
   ```
5. Run focused validation:
   ```bash
   ./.venv/bin/python -m pytest -q tests/test_lane3_docs.py
   ```
6. Update changelog and state files for traceability.
