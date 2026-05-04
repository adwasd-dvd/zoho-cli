# Zoho Cliq channel skill

Use this skill when operating through the native OpenClaw Zoho Cliq channel.

## Rules

- Use OpenClaw's shared message tool for sends and replies.
- Prefer explicit targets: `channel:<id>` for channels and `user:<id>` for DMs.
- Do not call Zoho REST APIs directly from the plugin; use `zoho cliq ...`.
- Treat stdout as machine data and stderr as diagnostics.
- Never reveal token passwords, webhook secrets, OAuth tokens, raw webhook
  signatures, or private message bodies in logs.
- In group/channel conversations, require an explicit bot mention unless config
  allows a narrower implicit mention policy.

## Required local readiness

```bash
zoho cliq status --check-auth --network <network>
zoho cliq capabilities --network <network>
```

If readiness fails, report the failing `zoho-cli` command, exit code, and
redacted stderr summary.
