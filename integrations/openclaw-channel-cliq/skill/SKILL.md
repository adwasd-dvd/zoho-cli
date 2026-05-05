# Zoho Cliq channel skill

Use this skill when operating through the native OpenClaw Zoho Cliq channel.

## Rules

- Use OpenClaw's shared message tool for sends and replies.
- Prefer explicit targets: `channel:<id>` for channels and `user:<id>` for DMs.
- Do not call Zoho REST APIs directly from the plugin; use `zoho cliq ...`.
- Native outbound delivery maps OpenClaw text sends to `zoho cliq send`,
  message replies to `zoho cliq reply`, and thread replies to
  `zoho cliq thread-reply`.
- Native inbound polling uses `zoho cliq chats --unread-only
  --exclude-reacted-by-self` plus `zoho cliq context`; normalize events before
  dispatch, skip self-authored messages, and dedupe by account/network/chat/message.
- Native Bot webhook intake uses `/webhooks/cliq` by default. Zoho Cliq Bot
  Message, Mention, Participation, and Context handlers must POST with
  `X-Cliq-Webhook-Secret`; normalize, dedupe, and apply the same security gates
  as polling before dispatch.
- Accepted native webhook and polling events should run through the shared
  lifecycle wrapper. Use `zoho cliq status-react --clear-known` for visible
  status (`received`, `thinking`, `writing`, `testing`, `blocked`, `done`,
  `failed`) and `zoho cliq mark-read` for read acknowledgement when available.
  Treat status/read failures as diagnostics, not new inbound work.
- Run accepted native events through the turn ledger before dispatch. Duplicate
  completed events, active same-conversation bursts, and dead-lettered replays
  must not start another agent turn.
- Inspect native status, capability, and routing diagnostics before lower-level
  CLI probing; use setup states, controlled-smoke readiness, production
  blockers, and normalized session routes to choose the next operator action.
- Treat stdout as machine data and stderr as diagnostics.
- Never reveal token passwords, webhook secrets, OAuth tokens, raw webhook
  signatures, or private message bodies in logs.
- In group/channel conversations, require an explicit bot mention unless config
  allows a narrower implicit mention policy.
- Keep target/session routing on OpenClaw native message surfaces; use
  account/network/chat/thread-aware targets and do not add parallel send tools.
- Mention-gated command bypass requires an authorized control command, not just
  slash-like text.
- Keep `dmPolicy=pairing`, `groupPolicy=allowlist`, `requireMention=true`, and
  `employeeMode.enabled=true` as the normal production posture.
- Refuse chat-originated debug, install, config-write, secret-read,
  shell/system, and policy-bypass requests before agent dispatch.
- Configure sensitive values with SecretRef/env references. Do not ask for or
  store plaintext token passwords, webhook secrets, OAuth tokens, bot tokens, app
  tokens, or private keys in setup input.
- For host/plugin API changes, follow
  `docs/releases/OPENCLAW_CLIQ_CHANNEL_COMPATIBILITY.md` and patch OpenClaw
  adapter/setup metadata before changing Zoho CLI command contracts.
- For v0.4 RC decisions, follow
  `docs/releases/OPENCLAW_CLIQ_CHANNEL_V0_4_RC_CHECKLIST.md` and keep
  production rollout blocked until public Bot callback reachability is verified.
- Before cutting a local/operator or npm/GitHub RC artifact, run
  `ops/scripts/openclaw_cliq_rc_pack.sh`; it must not publish or bump versions.

## Required local readiness

```bash
openclaw plugins inspect zoho-cliq --json
openclaw channels status --channel cliq --deep
openclaw channels capabilities --channel cliq
zoho cliq status --check-auth --network <network>
zoho cliq capabilities --network <network>
ops/scripts/openclaw_cliq_live_smoke.sh
ops/scripts/openclaw_cliq_rc_pack.sh
```

If readiness fails, report the failing `zoho-cli` command, exit code,
classified error kind, and redacted stderr summary.

## Troubleshooting order

1. Start with native OpenClaw status/capability/routing diagnostics.
2. Fix setup states before sending or dispatching: `host_too_old`,
   `zoho_missing`, `not_logged_in`, `missing_scope`, `network_missing`,
   `webhook_unverified`, `allowlist_empty`, and `employee_scope_empty`.
3. Treat `webhook_secret_missing` as a SecretRef/env configuration blocker; use
   `ZOHO_CLIQ_WEBHOOK_SECRET` and rotate any value exposed in chat or
   screenshots.
4. Native dispatch is implemented for accepted webhook/polling events. Treat
   dispatch failures/dead letters as terminal diagnostics, use the redacted
   diagnostic bundle for support handoff, and keep public Bot callback
   reachability as the remaining production deployment blocker when no
   tunnel/gateway URL is configured.
5. For unresolved routes, prefer explicit `channel:<id>`, `user:<id>`, or
   `cliq:channel:<id>:thread:<thread_id>` targets.
6. For repeated Zoho-side `not_supported`, `inactive_appaccount_user`, or
   `token_refresh_rate_limited` errors, report `skip_deferred` and keep
   unrelated channel work moving.

## Setup states

- `host_too_old`: upgrade OpenClaw to `>=2026.5.3-1`.
- `zoho_missing`: install `zoho-cli` and put `zoho` on `PATH`.
- `not_logged_in`: run `zoho login --with-cliq`.
- `missing_scope`: re-auth and rerun `zoho cliq status --check-auth`.
- `network_missing`: set the Cliq network.
- `webhook_unverified`: configure webhook secret and test `/webhooks/cliq`, or
  use polling dry-runs until live inbound is ready.
- `allowlist_empty`: add trusted Cliq user ids to `allowFrom` and group/channel
  ids to `groupAllowFrom`.
- `employee_scope_empty`: add a valid `workScopes.<profile>` entry.

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
          "webhookPath": "/webhooks/cliq",
          "network": "<network>",
          "cliPath": "zoho",
          "dmPolicy": "pairing",
          "groupPolicy": "allowlist",
          "allowFrom": ["<cliq_user_id>"],
          "groupAllowFrom": ["channel:<channel_id>"],
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
          }
        }
      }
    }
  }
}
```

## Bot handler setup

Use Zoho Cliq Bot Message, Mention, Participation, or Context handlers for live
inbound smoke. POST JSON to `webhookPath` with `X-Cliq-Webhook-Secret`; keep the
secret in `ZOHO_CLIQ_WEBHOOK_SECRET` and rotate any value that was exposed in
chat or screenshots. Welcome, Incoming Webhook, Call, and Menu handlers are
ignored until a later slice assigns explicit OpenClaw workflows.
