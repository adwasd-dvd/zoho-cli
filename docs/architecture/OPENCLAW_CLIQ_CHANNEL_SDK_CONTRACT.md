# OpenClaw Cliq channel SDK contract

This is the `cliq-channel-400` source of truth for the v0.4 native Zoho Cliq
channel plugin.

## Version lock

Checked at `2026-05-04T21:39:33Z`.

| Surface | Observed value | Decision |
| --- | --- | --- |
| Local OpenClaw | `OpenClaw 2026.4.15 (041266a)` | Too old for v0.4 plugin install tests; keep only as compatibility reference. |
| npm `openclaw@latest` | `2026.5.3-1` | Target stable host/plugin API. |
| npm `openclaw@beta` | `2026.5.4-beta.1` | Recheck before v0.4 release; no beta-only API dependency for skeleton. |
| Node engine | `>=22.14.0` from local OpenClaw package | Use the same floor for plugin package metadata. |

The v0.4 plugin contract is:

```json
{
  "minHostVersion": ">=2026.5.3-1",
  "compat": {
    "pluginApi": ">=2026.5.3-1"
  }
}
```

`cliq-channel-401` must not rely on local `2026.4.15` behavior. Before running
native install/inspect checks, upgrade the local host to the current stable
OpenClaw version or use a throwaway environment pinned to `openclaw@2026.5.3-1`.

## Package contract

Runtime entrypoint and install metadata live under `package.json#openclaw`.

Package identity:

```text
package: @adwasd/openclaw-zoho-cliq
plugin id: zoho-cliq
channel id: cliq
config root: channels.cliq
target release: v0.4.x
```

The initial `package.json` skeleton should include:

```json
{
  "name": "@adwasd/openclaw-zoho-cliq",
  "version": "0.4.0-alpha.0",
  "type": "module",
  "engines": {
    "node": ">=22.14.0"
  },
  "peerDependencies": {
    "openclaw": ">=2026.5.3-1"
  },
  "devDependencies": {
    "openclaw": "2026.5.3-1"
  },
  "openclaw": {
    "extensions": ["./dist/index.js"],
    "setupEntry": "./dist/setup-entry.js",
    "channel": {
      "id": "cliq",
      "label": "Zoho Cliq",
      "selectionLabel": "Zoho Cliq (Bot API + zoho-cli)",
      "docsPath": "/channels/cliq",
      "docsLabel": "cliq",
      "blurb": "Zoho Cliq channel backed by zoho-cli.",
      "markdownCapable": true,
      "configuredState": {
        "specifier": "./dist/configured-state.js",
        "exportName": "hasCliqConfiguredState"
      },
      "persistedAuthState": {
        "specifier": "./dist/auth-presence.js",
        "exportName": "hasCliqAuthState"
      }
    },
    "install": {
      "npmSpec": "@adwasd/openclaw-zoho-cliq",
      "defaultChoice": "npm",
      "minHostVersion": ">=2026.5.3-1",
      "expectedIntegrity": "<filled-at-release>"
    },
    "startup": {
      "deferConfiguredChannelFullLoadUntilAfterListen": true
    },
    "compat": {
      "pluginApi": ">=2026.5.3-1"
    }
  }
}
```

Keep TypeScript source in the repo-local development package, but point OpenClaw
runtime metadata at compiled `dist/*.js` files. `cliq-channel-401` verified that
`openclaw@2026.5.3-1` local path installs reject TypeScript-only runtime
entrypoints before discovery.

Package-local validation flow:

```bash
npm --prefix integrations/openclaw-channel-cliq run typecheck
npm --prefix integrations/openclaw-channel-cliq run build
HOME="$PWD/.tmp/openclaw-home-2026.5.3-1" \
  integrations/openclaw-channel-cliq/node_modules/.bin/openclaw \
  plugins install ./integrations/openclaw-channel-cliq --link
HOME="$PWD/.tmp/openclaw-home-2026.5.3-1" \
  integrations/openclaw-channel-cliq/node_modules/.bin/openclaw \
  plugins inspect zoho-cliq --json
HOME="$PWD/.tmp/openclaw-home-2026.5.3-1" \
  integrations/openclaw-channel-cliq/node_modules/.bin/openclaw \
  plugins doctor
```

## Manifest contract

`openclaw.plugin.json` is pre-runtime metadata. It must not contain runtime
entrypoints or npm install metadata.

Required manifest baseline after `cliq-channel-402`:

```json
{
  "id": "zoho-cliq",
  "name": "Zoho Cliq",
  "description": "Native OpenClaw channel for Zoho Cliq backed by zoho-cli.",
  "version": "0.4.0-alpha.0",
  "channels": ["cliq"],
  "channelEnvVars": {
    "cliq": [
      "ZOHO_ACCOUNT",
      "ZOHO_CONFIG",
      "ZOHO_TOKEN_PASSWORD",
      "ZOHO_CLIQ_WEBHOOK_SECRET"
    ]
  },
  "channelConfigs": {
    "cliq": {
      "label": "Zoho Cliq",
      "description": "Zoho Cliq channel backed by zoho-cli.",
      "schema": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "enabled": { "type": "boolean" },
          "defaultAccount": { "type": "string", "minLength": 1 },
          "accountEmail": { "$ref": "#/definitions/configValue" },
          "configPath": { "$ref": "#/definitions/configValue" },
          "network": { "type": "string", "minLength": 1 },
          "cliPath": { "type": "string", "minLength": 1 },
          "tokenPassword": { "$ref": "#/definitions/secretRef" },
          "webhookSecret": { "$ref": "#/definitions/secretRef" },
          "dmPolicy": {
            "type": "string",
            "enum": ["allowlist", "pairing", "open", "disabled"]
          },
          "allowFrom": { "$ref": "#/definitions/allowFrom" },
          "defaultTo": { "type": "string", "minLength": 1 },
          "accounts": {
            "type": "object",
            "additionalProperties": { "$ref": "#/definitions/account" }
          }
        },
        "definitions": {
          "secretRef": {
            "type": "object",
            "additionalProperties": false,
            "required": ["source", "provider", "id"],
            "properties": {
              "source": { "type": "string", "enum": ["env", "file", "exec"] },
              "provider": { "type": "string", "minLength": 1 },
              "id": { "type": "string", "minLength": 1 }
            }
          },
          "configValue": {
            "anyOf": [
              { "type": "string", "minLength": 1 },
              { "$ref": "#/definitions/secretRef" }
            ]
          },
          "allowFrom": {
            "type": "array",
            "items": {
              "anyOf": [
                { "type": "string", "minLength": 1 },
                { "type": "number" }
              ]
            }
          },
          "account": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "accountEmail": { "$ref": "#/definitions/configValue" },
              "configPath": { "$ref": "#/definitions/configValue" },
              "network": { "type": "string", "minLength": 1 },
              "cliPath": { "type": "string", "minLength": 1 },
              "tokenPassword": { "$ref": "#/definitions/secretRef" },
              "webhookSecret": { "$ref": "#/definitions/secretRef" },
              "dmPolicy": {
                "type": "string",
                "enum": ["allowlist", "pairing", "open", "disabled"]
              },
              "allowFrom": { "$ref": "#/definitions/allowFrom" },
              "defaultTo": { "type": "string", "minLength": 1 }
            }
          }
        }
      },
      "uiHints": {
        "tokenPassword": { "sensitive": true },
        "webhookSecret": { "sensitive": true }
      }
    }
  },
  "activation": {
    "channels": ["cliq"]
  },
  "skills": ["./skill"],
  "configSchema": {
    "type": "object",
    "additionalProperties": false,
    "properties": {}
  }
}
```

`channelConfigs.cliq.schema` is required because OpenClaw uses channel config
metadata before the runtime loads. Keep the manifest schema and
`src/config.ts#cliqChannelConfigSchema` in sync for account/config/SecretRef
fields.

## Runtime SDK contract

Use these OpenClaw SDK imports as the stable v0.4 baseline:

```ts
import {
  createChannelPluginBase,
  createChatChannelPlugin,
  defineChannelPluginEntry,
  defineSetupPluginEntry,
} from "openclaw/plugin-sdk/channel-core";
import {
  implicitMentionKindWhen,
  matchesMentionWithExplicit,
  resolveInboundMentionDecision,
} from "openclaw/plugin-sdk/channel-inbound";
import type { SecretInput, SecretRef } from "openclaw/plugin-sdk/secret-ref-runtime";
```

Required runtime surfaces:

- `createChannelPluginBase(...)` for id, meta, config/setup, status, doctor, and
  lightweight capabilities.
- `setupWizard` for human setup status lines, env shortcut, text inputs,
  allowlist handling, completion guidance, and disable behavior.
- `createChatChannelPlugin(...)` for DM security, pairing, threading, and
  outbound delivery composition.
- `defineChannelPluginEntry(...)` for the full runtime entry.
- `defineSetupPluginEntry(...)` for setup-only startup.
- `messaging.resolveSessionConversation(...)` for account/network/chat/thread
  session grammar and parent candidates when implemented.
- `resolveInboundMentionDecision({ facts, policy })` for the final mention gate.
- `approvalCapability`, not `ChannelPlugin.approvals`, for native approval facts.

Do not register custom `cliq_send`, `cliq_reply`, or `cliq_approve` agent tools
when OpenClaw core channel/message/approval surfaces already cover the behavior.
The plugin owns transport, routing, security, setup, and diagnostics; OpenClaw
core owns the shared message tool and generic approval lifecycle.

## SecretRef contract

Use OpenClaw's SecretRef object shape:

```json
{ "source": "env", "provider": "default", "id": "ZOHO_TOKEN_PASSWORD" }
```

Supported secret-bearing config fields for v0.4:

- `channels.cliq.accountEmail` / `channels.cliq.accounts.<id>.accountEmail`
  may be direct strings or SecretRef/env references to `ZOHO_ACCOUNT`.
- `channels.cliq.configPath` / `channels.cliq.accounts.<id>.configPath` may be
  direct strings or SecretRef/env references to `ZOHO_CONFIG`.
- `channels.cliq.accounts.<id>.tokenPassword`
- `channels.cliq.accounts.<id>.webhookSecret`
- future optional OAuth override fields only if the user explicitly approves
  plugin-managed auth

Plain env values remain supported through `channelEnvVars`, but committed docs
and examples must prefer SecretRef/env references over plaintext secrets.
Setup input must reject plaintext `token`, `accessToken`, `password`,
`privateKey`, `secret`, `botToken`, and `appToken` fields.

## Setup UX contract

`src/setup-wizard.ts` owns human setup metadata. It must expose these setup
states with one clear next action each:

- `host_too_old`
- `zoho_missing`
- `not_logged_in`
- `missing_scope`
- `network_missing`
- `webhook_unverified`
- `allowlist_empty`

The wizard must not perform process execution before `cliq-channel-404`; it only
describes status, writes config patches, and points operators at the relevant
`zoho` / `openclaw` commands.

## CLI contract

The plugin calls `zoho cliq ...` and parses JSON stdout. It does not call Zoho
REST APIs directly.

Minimum CLI commands for the first skeleton-through-outbound path:

```bash
zoho cliq status --check-auth --network <network>
zoho cliq capabilities --network <network>
zoho cliq chats --network <network> --unread-only --exclude-reacted-by-self
zoho cliq context --network <network> --chat-id <chat_id> --limit 20
zoho cliq reply <message_id> --network <network> --chat-id <chat_id> --text "..."
zoho cliq send --network <network> --channel-id <channel_id> --text "..."
zoho cliq send --network <network> --user-id <user_id> --text "..."
zoho cliq mark-read <message_id> --network <network> --chat-id <chat_id>
zoho cliq status-react <message_id> --network <network> --chat-id <chat_id> --status done
```

CLI stderr is diagnostics only. Runtime logs must redact command env, secrets,
webhook signatures, token passwords, and raw message bodies.

## Compatibility rule

Before every plugin implementation slice:

1. Recheck `npm view openclaw version dist-tags --json`.
2. Recheck the OpenClaw channel plugin, manifest, security, and secrets docs.
3. Re-run package-local typecheck/tests.
4. Re-run `openclaw plugins inspect` and `openclaw plugins doctor` on a host
   satisfying `>=2026.5.3-1`.
5. Record beta-only API drift as a follow-up unless it blocks the next stable
   release.

## Sources checked

- https://docs.openclaw.ai/plugins/sdk-channel-plugins
- https://docs.openclaw.ai/plugins/manifest
- https://docs.openclaw.ai/gateway/security
- https://docs.openclaw.ai/gateway/secrets
