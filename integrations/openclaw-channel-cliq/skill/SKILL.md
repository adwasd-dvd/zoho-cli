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
- Configure sensitive values with SecretRef/env references. Do not ask for or
  store plaintext token passwords, webhook secrets, OAuth tokens, bot tokens, app
  tokens, or private keys in setup input.

## Required local readiness

```bash
zoho cliq status --check-auth --network <network>
zoho cliq capabilities --network <network>
```

If readiness fails, report the failing `zoho-cli` command, exit code, and
redacted stderr summary.

## Setup states

- `host_too_old`: upgrade OpenClaw to `>=2026.5.3-1`.
- `zoho_missing`: install `zoho-cli` and put `zoho` on `PATH`.
- `not_logged_in`: run `zoho login --with-cliq`.
- `missing_scope`: re-auth and rerun `zoho cliq status --check-auth`.
- `network_missing`: set the Cliq network.
- `webhook_unverified`: configure webhook secret or choose polling later.
- `allowlist_empty`: add trusted Cliq user ids to `allowFrom`.

## Config shape

```json
{
  "channels": {
    "cliq": {
      "defaultAccount": "default",
      "accounts": {
        "default": {
          "accountEmail": "bot@example.com",
          "configPath": {
            "source": "env",
            "provider": "default",
            "id": "ZOHO_CONFIG"
          },
          "tokenPassword": {
            "source": "env",
            "provider": "default",
            "id": "ZOHO_TOKEN_PASSWORD"
          },
          "webhookSecret": {
            "source": "env",
            "provider": "default",
            "id": "ZOHO_CLIQ_WEBHOOK_SECRET"
          },
          "network": "<network>",
          "cliPath": "zoho",
          "dmPolicy": "allowlist",
          "allowFrom": ["<cliq_user_id>"]
        }
      }
    }
  }
}
```
