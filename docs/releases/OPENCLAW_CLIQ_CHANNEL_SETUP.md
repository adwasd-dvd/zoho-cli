# OpenClaw Zoho Cliq channel setup

This runbook is for the native OpenClaw `cliq` channel package in
`integrations/openclaw-channel-cliq/`.

## Current readiness

- Config/auth smoke testing is ready now.
- Security policy smoke testing is ready now: DM pairing, group allowlist,
  mention gating, scoped employee mode, and unsafe-policy audit warnings are in
  the package runtime.
- SDK seam smoke testing is ready now: session routing is
  account/network/thread aware, mention policy delegates to OpenClaw shared
  helpers, and review-required actions advertise native approval capability.
- CLI adapter smoke testing is ready now: `zoho` process execution parses JSON
  stdout, classifies common failures, and keeps diagnostics redacted.
- Native outbound smoke testing is ready now: OpenClaw message delivery maps to
  `zoho cliq send`, `zoho cliq reply`, and `zoho cliq thread-reply`.
- Inbound polling dry-run testing is ready now: unread chat polling uses
  `zoho cliq chats --unread-only --exclude-reacted-by-self`, fetches context
  with `zoho cliq context`, normalizes events, skips self-authored messages,
  applies mention/allowlist/employee policy checks, and dedupes by
  account/network/chat/message.
- Inbound webhook smoke testing is ready now: Zoho Cliq Bot Message, Mention,
  Participation, and Context handlers can POST to `/webhooks/cliq`; the plugin
  verifies `X-Cliq-Webhook-Secret`, normalizes events, dedupes by
  account/network/chat/message, and applies the same security gates as polling.
- Status/read lifecycle smoke testing is ready now: accepted native events can
  apply visible `received -> thinking -> done` or `failed` reactions through
  `zoho cliq status-react --clear-known` and attempt `zoho cliq mark-read`
  without recursively creating new inbound work on lifecycle failures.
- Turn-ledger loop-prevention smoke testing is ready now: accepted native events
  record a small turn row, duplicate completed events are skipped, active
  same-conversation bursts are coalesced, and failed turns can stop in
  dead-letter with actionable metadata.
- Native UX/status diagnostics smoke testing is ready now: channel status
  summaries include setup state, webhook/polling/lifecycle/ledger readiness,
  capabilities, and target routing previews without exposing secrets or message
  bodies.
- Production/bidirectional agent replies now have native dispatch plus redacted
  observability support. The fake/live gate harness is in place; public Bot
  callback verification remains a deployment prerequisite when no reachable
  tunnel or gateway URL is configured.

## Requirements

- OpenClaw `>=2026.5.3-1`.
- `zoho-cli` installed and available as `zoho`.
- A Zoho Cliq Bot handler that can invoke the local OpenClaw webhook route
  through a tunnel or gateway.
- One interactive bootstrap login:

```bash
zoho login --with-cliq
zoho cliq status --check-auth --network <network>
```

Use `ZOHO_CONFIG` for the config file and `ZOHO_TOKEN_PASSWORD` for encrypted
file fallback. Do not paste OAuth tokens or webhook secrets into setup prompts.
For host compatibility updates, use
`docs/releases/OPENCLAW_CLIQ_CHANNEL_COMPATIBILITY.md`.
For RC cut decisions, use
`docs/releases/OPENCLAW_CLIQ_CHANNEL_V0_4_RC_CHECKLIST.md` and run
`ops/scripts/openclaw_cliq_rc_pack.sh` before cutting an artifact.
For real Zoho Bot handler code, use
`docs/releases/OPENCLAW_CLIQ_BOT_HANDLER_TEMPLATES.md`.

## Install from the workspace

```bash
npm --prefix integrations/openclaw-channel-cliq install --ignore-scripts
npm --prefix integrations/openclaw-channel-cliq run build
openclaw plugins install ./integrations/openclaw-channel-cliq --link
openclaw plugins inspect zoho-cliq --json
openclaw plugins doctor
```

The upgraded global `OpenClaw 2026.5.3-1` host is the supported baseline. The
latest npm stable (`2026.5.4`) and beta (`2026.5.4-beta.3`) currently pass
Temp-HOME linked install/inspect/doctor checks. For isolated validation in this
repository, use package-local OpenClaw with a throwaway home:

```bash
HOME="$PWD/.tmp/openclaw-home-2026.5.3-1" \
  npm --prefix integrations/openclaw-channel-cliq run openclaw:install
HOME="$PWD/.tmp/openclaw-home-2026.5.3-1" \
  npm --prefix integrations/openclaw-channel-cliq run inspect
HOME="$PWD/.tmp/openclaw-home-2026.5.3-1" \
  npm --prefix integrations/openclaw-channel-cliq run doctor
```

## Config baseline

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
          "webhookPath": "/webhooks/cliq",
          "dmPolicy": "pairing",
          "groupPolicy": "allowlist",
          "allowFrom": ["<trusted_cliq_user_id>"],
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
          },
          "defaultTo": "channel:<channel_id>"
        }
      }
    }
  }
}
```

## Zoho Cliq Bot handler

Use a Bot Message, Mention, Participation, or Context Handler for inbound
OpenClaw channel messages. Mention Handler is the best first live smoke because
Zoho provides `message`, `mentions`, `user`, and `chat` objects to the Deluge
script. Full Deluge templates for all four accepted handlers live in
`docs/releases/OPENCLAW_CLIQ_BOT_HANDLER_TEMPLATES.md`.

```deluge
response = Map();
webhook_url = "https://<your-tunnel-or-gateway>/webhooks/cliq";
payload = Map();
payload.put("handler","mention");
payload.put("message",message);
payload.put("user",user);
payload.put("chat",chat);
payload.put("mentions",mentions);
invokeurl
[
  url :webhook_url
  type :POST
  body:payload.toString()
  headers:{"Content-Type":"application/json","X-Cliq-Webhook-Secret":"<rotated-secret>"}
]
response.put("text","received");
return response;
```

`parameters:payload.toString()` is also accepted by the current plugin parser,
but `body:payload.toString()` is the clearer Deluge shape for a JSON request.
Rotate any webhook secret that appeared in screenshots, chat, logs, or docs
before using a real Bot.

For RC, Welcome, Incoming Webhook, Call, and Menu handlers are ignored with a
200 `unsupported_handler` response so Zoho does not retry unrelated bot events.
They can be mapped later when each workflow has an explicit OpenClaw behavior.

References: Zoho Cliq Bot Mention Handler
(`https://www.zoho.com/cliq/help/platform/bot-mentionshandler.html`) and Zoho
Deluge help (`https://www.zoho.com/deluge/help/`).

## Live smoke gate

Run the repository smoke gate from the project root after OpenClaw is configured
and the gateway is running:

```bash
ops/scripts/openclaw_cliq_live_smoke.sh
```

The script checks Zoho Cliq auth/capability probes, OpenClaw plugin
inspect/doctor, channel status/capabilities, local webhook missing-secret
rejection, authenticated non-dispatch handling, authenticated allowlist-deny
handling, safe unread polling, and native polling adapter behavior. It reads
`ZOHO_CLIQ_WEBHOOK_SECRET` from the environment or `launchctl` and never prints
the secret. Override `ZOHO_CLIQ_NETWORK`, `OPENCLAW_GATEWAY_URL`,
`ZOHO_CLIQ_WEBHOOK_PATH`, or `ZOHO_CLIQ_PUBLIC_WEBHOOK_URL` when testing a
non-default network, gateway, path, or public tunnel.

`token_refresh_rate_limited` and repeated endpoint availability failures are
recorded as `skip_deferred` so the gate does not hammer Zoho refresh endpoints
or block unrelated local channel work. A public Bot callback cannot pass until a
reachable tunnel/gateway URL is configured and the Bot handler points to it.

## Setup states

| State | Meaning | Next action |
| --- | --- | --- |
| `host_too_old` | OpenClaw is too old. | Upgrade OpenClaw to `>=2026.5.3-1`. |
| `zoho_missing` | `zoho` was not found. | Install `zoho-cli` and put `zoho` on `PATH`. |
| `not_logged_in` | Zoho auth/config is missing. | Run `zoho login --with-cliq`. |
| `missing_scope` | Cliq scopes are incomplete. | Re-auth and rerun `zoho cliq status --check-auth`. |
| `network_missing` | Cliq network is not set. | Set `channels.cliq.accounts.<id>.network`. |
| `webhook_unverified` | Inbound webhook is not verified. | Configure `webhookSecret` and POST a controlled Bot handler event to `/webhooks/cliq`; polling fallback dry-runs can still be tested locally. |
| `allowlist_empty` | No trusted Cliq senders are configured. | Add trusted user ids to `allowFrom` and group/channel ids to `groupAllowFrom`. |
| `employee_scope_empty` | Scoped employee mode has no work scope. | Add `workScopes.<profile>` or pick a valid `employeeMode.scopeProfile`. |

## AI diagnostic prompts

When an AI agent is operating the channel, it should inspect diagnostics in this
order before trying ad hoc Cliq API calls:

1. `openclaw plugins inspect zoho-cliq --json`
2. `openclaw channels status --channel cliq --deep`
3. `openclaw channels capabilities --channel cliq`
4. routing diagnostics for the intended `channel:<id>`, `user:<id>`, or
   `cliq:channel:<id>:thread:<thread_id>` target
5. `zoho cliq status --check-auth --network <network>`

Diagnostic blockers that are not setup-state names:

| Blocker | Meaning | AI action |
| --- | --- | --- |
| `webhook_secret_missing` | No SecretRef/env webhook secret is configured. | Set `webhookSecret` to `ZOHO_CLIQ_WEBHOOK_SECRET`, test a controlled Bot POST, and rotate exposed values. |
| native dispatch failure / dead-letter | A trusted event reached dispatch but the OpenClaw turn failed or was dead-lettered. | Inspect turn id, dispatch error, and dead-letter metadata before replay; do not retry blindly. |
| `live_verification_pending` | Redacted production diagnostics are ready, but fake plus live verification has not passed yet. | Keep reports redacted and run the verification gate before production rollout. |
| `token_refresh_rate_limited` | Zoho OAuth refresh is temporarily throttled. | Mark the check `skip_deferred`, wait for cooldown, and avoid bursty probe loops. |
| repeated `not_supported` / `inactive_appaccount_user` | Zoho-side endpoint availability is blocking a specific live check. | Mark the check `skip_deferred` and continue unrelated local channel work. |

## Security smoke

Before live traffic, keep these defaults unless an operator explicitly accepts
the audit warning:

- `dmPolicy=pairing`
- `groupPolicy=allowlist`
- `requireMention=true`
- `employeeMode.enabled=true`

Chat-originated requests to debug internals, install plugins/packages, write
config, read secrets, run shell/system actions, or bypass policy are refused
before agent dispatch. Add trusted DM users to `allowFrom`; add trusted
group/channel routes or senders to `groupAllowFrom`.

## Disable, uninstall, and recovery

Disable the plugin:

```bash
openclaw plugins disable zoho-cliq
```

Disable or remove the channel account:

```bash
openclaw channels remove --channel cliq --account default
```

Uninstall the plugin:

```bash
openclaw plugins uninstall zoho-cliq
```

Recovery checklist:

1. Rebuild the package: `npm --prefix integrations/openclaw-channel-cliq run build`.
2. Reinstall with `openclaw plugins install ./integrations/openclaw-channel-cliq --link`.
3. Run `openclaw plugins inspect zoho-cliq --json` and `openclaw plugins doctor`.
4. Re-run `zoho cliq status --check-auth --network <network>`.
5. Run controlled outbound smoke, local inbound polling dry-runs, a real Bot
   webhook receive/auth/normalize smoke, status/read lifecycle smoke,
   turn-ledger loop-prevention smoke, status/routing diagnostics smoke, and a
   controlled native dispatch and redacted diagnostic bundle smoke through
   `ops/scripts/openclaw_cliq_live_smoke.sh`. Wait for a reachable public Bot
   callback before production agent rollout.
