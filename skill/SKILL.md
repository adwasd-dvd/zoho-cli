---
name: zoho-cli-employee
description: Operate Zoho CLI (`zoho ...`) as a Zoho employee agent inside OpenClaw. Use when work involves Zoho Mail triage/send/reply, Zoho Cliq channel/chat operations (including network-scoped work such as happydistrouklimited), CRM read operations, or installing/updating the Zoho CLI and this skill with explicit user approval.
---

# Zoho CLI employee operator

Use this skill as the default operating contract for an OpenClaw agent acting like a new employee with Zoho access.

## Run order

1. Read `references/employee-operating-model.md`.
2. Read `references/command-playbook.md` for concrete command patterns.
3. For unread polling / message handling loops, read `references/unread-status-workflow.md`.
4. When the task is install/update, read `references/install-and-update.md` and require explicit user approval before any upgrade command.
5. If command surfaces changed, refresh `references/cli-help-snapshot.md` with `scripts/refresh_cli_help_snapshot.py`.

## Hard rules

- Keep output machine-safe: prefer JSON output, parse with `jq`, and treat stderr as diagnostics.
- Use module-first CLI routes (`zoho mail ...`, `zoho cliq ...`, `zoho crm ...`).
- Keep Cliq operations network-aware; pass `--network` when the target network is known.
- For unread intake polling, prefer `zoho cliq chats --unread-only --exclude-reacted-by-self`.
- Maintain explicit reaction-based message lifecycle status for human visibility (`received`, `thinking`, `writing`, `testing`, `blocked`, `done`, `failed`) via `zoho cliq status-react --clear-known`.
- Draft before high-impact send/delete actions unless the user explicitly asks for direct execution.
- Ask for explicit approval before running any install/update command that modifies tools or skill files.
- Prefer smallest verifiable step, then report evidence.
