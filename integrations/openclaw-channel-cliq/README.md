# OpenClaw Zoho Cliq channel

Native OpenClaw channel package for Zoho Cliq, backed by `zoho-cli`.

This package includes the `cliq-channel-401` installable skeleton and the
`cliq-channel-402` config/SecretRef/setup slice. It declares the plugin/channel
metadata, setup/runtime entrypoints, configured/auth-state probes, a minimal
OpenClaw channel object, config schema metadata, and a typed `zoho cliq send`
argument contract. Security hardening, process execution, inbound delivery, and
outbound behavior follow in later slices.

## Contract

- Package: `@adwasd/openclaw-zoho-cliq`
- Plugin id: `zoho-cliq`
- Channel id: `cliq`
- Config root: `channels.cliq`
- Host/plugin API: `>=2026.5.3-1`
- Node: `>=22.14.0`

The source of truth is
`../../docs/architecture/OPENCLAW_CLIQ_CHANNEL_SDK_CONTRACT.md`.

## Config example

```json
{
  "channels": {
    "cliq": {
      "enabled": true,
      "defaultAccount": "default",
      "accounts": {
        "default": {
          "accountEmail": "bot@example.com",
          "network": "happydistrouklimited",
          "cliPath": "zoho",
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
          "dmPolicy": "allowlist",
          "allowFrom": ["123456789"],
          "defaultTo": "channel:123456789"
        }
      }
    }
  }
}
```

Setup rejects plaintext token/password/secret-style inputs. Use `zoho login`
for OAuth bootstrap and SecretRef/env references for sensitive values.

## Development

```bash
npm install --ignore-scripts
npm run typecheck
npm run build
openclaw plugins install . --link
openclaw plugins inspect zoho-cliq --json
openclaw plugins doctor
```

Use a host satisfying `>=2026.5.3-1` for inspect/install validation. The local
`OpenClaw 2026.4.15` install is too old for this package.

## Runtime boundary

The plugin shells out to `zoho cliq ...` and parses JSON stdout. It must not call
Zoho REST APIs directly or expose parallel `cliq_send`/`cliq_reply` agent tools
when OpenClaw core message and approval surfaces already cover those behaviors.
