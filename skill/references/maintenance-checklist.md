# Skill maintenance checklist

Run this whenever command surfaces or workflows change.

1. Refresh CLI help snapshot:
   ```bash
   python skill/scripts/refresh_cli_help_snapshot.py --runner "zoho"
   ```
2. Update `skill/references/command-playbook.md` and `skill/references/unread-status-workflow.md` when Cliq polling/status behavior changes.
3. Keep `skill/references/install-and-update.md` aligned with current repo URL and lane3 sync behavior (`integrations/openclaw/bin/pull_lane3_only.sh`).
4. Verify help surface still contains required loop/status commands:
   ```bash
   zoho cliq --help | rg -n "status-react|mark-read|chats|context|reply"
   zoho cliq chats --help | rg -n "unread-only|exclude-reacted-by-self"
   ```
5. Run focused validation:
   ```bash
   ./.venv/bin/python -m pytest -q tests/test_lane3_docs.py
   ```
6. For RC updates, verify `zoho --version` matches the approved RC version before syncing AI-user skill files.
7. For Cliq status/capability maintenance, inspect `zoho_cli/commands/cliq_readiness.py` first; for `whoami` / `user-resolve`, inspect `zoho_cli/commands/cliq_identity.py`; for `users` / `teams`, inspect `zoho_cli/commands/cliq_org_directory.py`; for org-admin list commands, inspect `zoho_cli/commands/cliq_org_admin.py`.
8. Update changelog and state files for traceability.
