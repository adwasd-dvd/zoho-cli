# OpenClaw Zoho Cliq channel

Native OpenClaw channel package for Zoho Cliq, backed by `zoho-cli`.

This package includes the `cliq-channel-401` installable skeleton,
`cliq-channel-402` config/SecretRef/setup slice, `cliq-channel-416` human
setup UX slice, `cliq-channel-403` security/policy slice, and
`cliq-channel-414` native SDK seam slice, `cliq-channel-404` CLI adapter slice,
and `cliq-channel-405` outbound delivery slice. It declares the plugin/channel
metadata, setup/runtime entrypoints, configured/auth-state probes, a native
OpenClaw channel object, config schema metadata, DM pairing, group allowlist,
mention gating, scoped employee policy gates, audit warnings,
account/network/thread-aware session grammar, native mention-policy delegation,
approval capability metadata, a JSON-safe `zoho cliq ...` process adapter, and
native outbound send/reply/thread-reply delivery. Inbound delivery follows in
later slices.

## Contract

- Package: `@adwasd/openclaw-zoho-cliq`
- Plugin id: `zoho-cliq`
- Channel id: `cliq`
- Config root: `channels.cliq`
- Host/plugin API: `>=2026.5.3-1`
- Node: `>=22.14.0`

The source of truth is
`../../docs/architecture/OPENCLAW_CLIQ_CHANNEL_SDK_CONTRACT.md`.

Human setup and troubleshooting live in
`../../docs/releases/OPENCLAW_CLIQ_CHANNEL_SETUP.md`.

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
          "dmPolicy": "pairing",
          "groupPolicy": "allowlist",
          "allowFrom": ["123456789"],
          "groupAllowFrom": ["channel:123456789"],
          "requireMention": true,
          "employeeMode": {
            "enabled": true,
            "scopeProfile": "default",
            "policy": "strict"
          },
          "workScopes": {
            "default": {
              "role": "employee",
              "allowedSurfaces": ["cliq", "mail"],
              "crm": "read_only",
              "requiresReviewFor": ["mail.send_with_review", "external_send", "delete", "system.install", "system.config_write"]
            }
          },
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

Use a host satisfying `>=2026.5.3-1` for inspect/install validation. The
upgraded global `OpenClaw 2026.5.3-1` host is suitable; package-local
`openclaw@2026.5.3-1` remains useful for isolated checks.

## Setup UX

The setup wizard exposes these operator states: `host_too_old`,
`zoho_missing`, `not_logged_in`, `missing_scope`, `network_missing`,
`webhook_unverified`, `allowlist_empty`, and `employee_scope_empty`.

The wizard offers:

- text inputs for account label, Zoho account email, Cliq network, `zoho`
  command path, zoho-cli config path, and default target
- env shortcut for `ZOHO_ACCOUNT`, `ZOHO_CONFIG`, `ZOHO_TOKEN_PASSWORD`, and
  `ZOHO_CLIQ_WEBHOOK_SECRET`
- DM allowlist entry handling
- account disable behavior for OpenClaw setup surfaces

## Security posture

- `dmPolicy` defaults to `pairing`; approved/pairing users are stored in
  `allowFrom`.
- `groupPolicy` defaults to `allowlist`; group/channel intake uses
  `groupAllowFrom` and still requires a bot mention by default.
- `employeeMode.enabled=true` blocks chat-originated debug, install,
  config-write, secret-read, shell/system, and policy-bypass requests before
  agent dispatch.
- `dmPolicy=open`, `groupPolicy=open`, `allowFrom=["*"]`,
  `groupAllowFrom=["*"]`, `requireMention=false`, or disabled employee mode
  produce audit warnings.
- Mention bypass for text commands is only valid for explicit, authorized
  control commands; normal slash-like chat text still follows mention gating.
- Review-required operations advertise OpenClaw native `approvalCapability`
  facts instead of channel-specific approval tools.

## Runtime boundary

The plugin shells out to `zoho cliq ...` and parses JSON stdout. It must not call
Zoho REST APIs directly or expose parallel `cliq_send`/`cliq_reply` agent tools
when OpenClaw core message and approval surfaces already cover those behaviors.
The process adapter classifies auth, scope, unsupported endpoint, invalid JSON,
timeout, missing-command, and generic failures while keeping stderr diagnostics
redacted. Native outbound delivery uses OpenClaw's shared message surface with
markdown chunking and maps text sends to `zoho cliq send`, message replies to
`zoho cliq reply`, and thread delivery to `zoho cliq thread-reply`.
