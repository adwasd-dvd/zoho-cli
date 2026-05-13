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
  callback auth/reachability and one controlled trusted Mention-to-agent reply
  have been verified through the operator Cloudflare route, with durable
  tunnel/gateway selection remaining as the production operations decision.
- Accepted webhook and polling turns keep OpenClaw `Provider`/`Surface` set to
  the native channel id `cliq`; handler source details stay in supplemental
  context. This keeps normal final answers on the Cliq outbound adapter instead
  of being treated as cross-channel route-reply traffic.
- Direct Bot replies are robust to handler-generated ids: synthetic
  `webhook-*` and `zoho-message-*` message ids are treated as non-replyable, so
  the assistant answer is sent to the provided direct `chatId`. When the handler
  exposes a real Zoho message id plus `chatId`, native dispatch replies through
  that real chat/message pair.

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
For tunnel-agnostic public callback verification, use
`ops/scripts/openclaw_cliq_public_callback_smoke.sh`.

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
script. For direct Bot DMs, use the Message Handler template that wraps Zoho's
text-like `message` value into an explicit `msg` map with `text`, `messageId`,
`senderId`, `chatId`, and `chatType`. Full Deluge templates for all four
accepted handlers live in `docs/releases/OPENCLAW_CLIQ_BOT_HANDLER_TEMPLATES.md`.
Current real-Bot handlers should set `reply_mode` to `deluge_response`, assign
the `invokeurl` result to `webhook_response`, and return that map when it has a
`text` key so Zoho renders the OpenClaw agent's final answer as the Bot's native
handler response.

```deluge
response = Map();
webhook_url = "https://<your-tunnel-or-gateway>/webhooks/cliq";
payload = Map();
payload.put("handler","mention");
payload.put("reply_mode","deluge_response");
payload.put("message",message);
payload.put("user",user);
payload.put("chat",chat);
payload.put("mentions",mentions);
webhook_response = invokeurl
[
  url :webhook_url
  type :POST
  body:payload.toString()
  headers:{"Content-Type":"application/json","X-Cliq-Webhook-Secret":"<rotated-secret>"}
]
if(webhook_response != null && webhook_response.containKey("text") && webhook_response.get("text") != null)
{
  response.put("text",webhook_response.get("text"));
}
return response;
```

`parameters:payload.toString()` is also accepted by the current plugin parser,
but `body:payload.toString()` is the clearer Deluge shape for a JSON request.
The webhook parser also tolerates Deluge Map-string bodies such as
`{handler=message, message=..., user={...}}` when Zoho does not emit strict
JSON. Rotate any webhook secret that appeared in screenshots, chat, logs, or
docs before using a real Bot.

If the OpenClaw audit log shows `handlerKind:"message"` with
`reason:"invalid_payload"`, the public route and secret are already working; the
next fix is to re-paste the wrapped Message Handler template so OpenClaw can
read both text and sender/chat identity.

A delayed literal `received` message is only a Deluge handler ACK. It does not
prove OpenClaw final delivery succeeded, and it should be removed once
`deluge_response` mode is installed.

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
non-default network, gateway, path, or public tunnel. When
`ZOHO_CLIQ_PUBLIC_WEBHOOK_URL` is set, the live smoke invokes
`ops/scripts/openclaw_cliq_public_callback_smoke.sh` to POST through the public
URL; this is tunnel/gateway agnostic and is not tied to Cloudflare.

For just the public ingress check, set the public HTTPS URL plus the same
webhook secret used by OpenClaw:

```bash
ZOHO_CLIQ_PUBLIC_WEBHOOK_URL=https://<your-tunnel-or-gateway>/webhooks/cliq \
ZOHO_CLIQ_PUBLIC_CALLBACK_REPORT_FILE=tests/auto_pilot/reports/openclaw_cliq_public_callback.json \
  ops/scripts/openclaw_cliq_public_callback_smoke.sh
```

The public callback smoke rejects placeholder URLs with
`public_webhook_url_placeholder`, requires HTTPS unless
`ZOHO_CLIQ_ALLOW_INSECURE_PUBLIC_WEBHOOK=1` is explicitly set for a local lab,
checks a missing-secret POST returns `401`, checks an authenticated
unsupported-handler POST returns `200`, and emits redacted
`openclaw_cliq_public_callback_smoke` JSON. The success status is
`public_callback_verified`; the report stores status codes, scheme/host/path,
and redaction booleans, but not webhook bodies, response bodies, or secrets.

If a user sends a real Bot message but no response appears, first run the
read-only no-response packet against the expected send window:

```bash
ZOHO_CLIQ_PUBLIC_WEBHOOK_URL=https://cliq.hpyio.com/webhooks/cliq \
ZOHO_CLIQ_INGRESS_LOOKBACK_SECONDS=900 \
ZOHO_CLIQ_EXPECTED_AGENT_ID=zoho-employee-test \
ZOHO_CLIQ_EXPECTED_AGENT_MODEL=openai-codex/gpt-5.3-codex \
  ops/scripts/openclaw_cliq_bot_no_response_packet.sh
```

If you only need the log-window classifier, run the diagnostic directly:

```bash
ZOHO_CLIQ_INGRESS_LOOKBACK_SECONDS=900 \
  ops/scripts/openclaw_cliq_live_ingress_diagnostic.sh
```

The packet runs the public callback smoke when `ZOHO_CLIQ_PUBLIC_WEBHOOK_URL`
is set, then runs the live ingress diagnostic and returns one `nextAction`.
When the ingress diagnostic reports `no_recent_webhook_ingress` and public
callback setup is not the blocker, the wrapper also embeds a redacted
`handlerTrigger` subpacket plus evidence filename. Self-generated public
callback smoke records are ignored by the ingress diagnostic so they do not
mask the latest real Bot message window.
`no_recent_webhook_ingress` means the Zoho Bot handler did not POST to the
gateway during the window, so check the saved Message/Mention Handler URL,
secret header, and handler type before chasing OAuth. `latest_webhook_not_dispatched`
means the gateway saw the handler but payload or policy blocked dispatch.
`dispatch_reply_not_delivered` means OpenClaw accepted the turn but no Cliq
reply delivery was recorded. `live_ingress_active` means the latest observed
handler event dispatched and delivered at least one reply. The packet and
diagnostic do not store raw webhook payloads, message bodies, reply bodies,
callback response bodies, or secrets.

When `nextAction=fix_zoho_bot_handler_trigger`, first inspect
`handlerTrigger` in the no-response packet. You can also generate the same
copy/check packet directly before changing Zoho:

```bash
ZOHO_CLIQ_PUBLIC_WEBHOOK_URL=https://cliq.hpyio.com/webhooks/cliq \
ZOHO_CLIQ_HANDLER_TARGETS=mention,message \
ZOHO_CLIQ_EXPECTED_BOT_NAME=oldsix \
  ops/scripts/openclaw_cliq_handler_trigger_packet.sh
```

The packet validates that the public URL is HTTPS and ends in `/webhooks/cliq`,
checks that selected handler targets are one of Message, Mention,
Participation, or Context, points to the matching sections in
`docs/releases/OPENCLAW_CLIQ_BOT_HANDLER_TEMPLATES.md`, and repeats the Deluge
contract: use `body:payload.toString()`, `Content-Type: application/json`, and
`X-Cliq-Webhook-Secret` from `ZOHO_CLIQ_WEBHOOK_SECRET`. Current packets also
require `reply_mode=deluge_response`, `webhook_response = invokeurl [...]`, and
returning `webhook_response` when it has a `text` key; a fixed `received` ACK is
only a handler smoke signal. The packet reports whether a secret is available in
the current environment, but it never stores the secret value, webhook payload,
message body, response body, or reply body.

### Cloudflare Tunnel fast path

When using Cloudflare Zero Trust Tunnels for the first RC smoke, create a route
with **Published application**, not Private hostname / Private CIDR / Workers
VPC. The route should publish a public hostname and forward it to the local
OpenClaw gateway:

- Public hostname: an operator-owned hostname, for example
  `cliq-test-bot.<your-domain>`
- Path: empty
- Service type: `HTTP`
- Service URL: `127.0.0.1:18789`

After saving, set
`ZOHO_CLIQ_PUBLIC_WEBHOOK_URL=https://<published-hostname>/webhooks/cliq` and
run `ops/scripts/openclaw_cliq_public_callback_smoke.sh`. The tunnel route is
ready for Zoho Bot handler traffic only after the smoke reports
`public_callback_verified`. If the Cloudflare route count is zero, add the
Published application route before debugging Zoho or OpenClaw.

Set `ZOHO_CLIQ_EXPECTED_AGENT_ID` before live rollout smoke when a Cliq account
must route to a specific OpenClaw agent. The gate reads OpenClaw config,
verifies `cliq/<account>` binding, and can also enforce
`ZOHO_CLIQ_EXPECTED_AGENT_MODEL` plus `ZOHO_CLIQ_EXPECTED_ACCOUNT_ID` when the
smoke is pinned to a named account/model pair. Set
`ZOHO_CLIQ_ROUTE_BINDING_ONLY=1` for an offline preflight that runs only this
binding check; use `OPENCLAW_CONFIG_PATH` to point it at a temporary or
operator-provided config file. Set `ZOHO_CLIQ_ROUTE_REPORT_FILE` when automation
needs the route result written as a single JSON evidence file. The evidence uses
`schemaVersion=1`, includes `kind=openclaw_cliq_route_preflight`, `runId`,
`checkedAt`, expected/actual agent facts, and does not include the local config
path. Route gate failures are machine-readable JSON with `status=error` and
error codes such as `route_binding_missing`, `expected_agent_missing`,
`agent_binding_mismatch`, `agent_missing`, or `agent_model_mismatch`. In
route-only mode, `ZOHO_CLIQ_EXPECTED_AGENT_ID` is required so the preflight
cannot pass without checking a route.

`token_refresh_rate_limited` and repeated endpoint availability failures are
recorded as `skip_deferred` so the gate does not hammer Zoho refresh endpoints
or block unrelated local channel work. Public Bot callback auth/reachability can
be tested with an operator tunnel; final rollout evidence also requires a
trusted Bot event to route to the intended OpenClaw agent and deliver one Cliq
reply. Store only redacted `openclaw_cliq_trusted_reply_evidence` JSON and run
`ops/scripts/openclaw_cliq_trusted_reply_evidence.sh` with
`ZOHO_CLIQ_TRUSTED_REPLY_EVIDENCE_FILE`; the result must be
`trusted_reply_recorded` before production readiness claims. The evidence must
store the trusted sender id, trusted message id, and reply delivery id only as
`sha256:` references. Use
`docs/releases/OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_TEMPLATE.json` as a
copy/edit starting point; it intentionally does not pass unchanged. Prefer
`ops/scripts/openclaw_cliq_trusted_reply_evidence_bundle.sh` after the trusted
reply: provide `ZOHO_CLIQ_ROUTE_REPORT_FILE`,
`ZOHO_CLIQ_TRUSTED_SENDER_ID`, `ZOHO_CLIQ_TRUSTED_MESSAGE_ID`, and
`ZOHO_CLIQ_DELIVERY_ID` for one-shot local hash/prepare/check, or use
`ops/scripts/openclaw_cliq_hash_ref.sh` first and pass
`ZOHO_CLIQ_TRUSTED_SENDER_ID_HASH`, `ZOHO_CLIQ_TRUSTED_MESSAGE_ID_HASH`, and
`ZOHO_CLIQ_DELIVERY_ID_HASH`. The bundle keeps stdout to the final checker JSON
and does not echo raw ids. If `ZOHO_CLIQ_ROUTE_REPORT_FILE` is omitted, the
bundle runs the offline route preflight itself and writes route/evidence/check
reports under `ZOHO_CLIQ_TRUSTED_REPLY_REPORT_DIR` or
`tests/auto_pilot/reports`. If route preflight fails with blockers such as
`agent_binding_mismatch`, the bundle exits non-zero with route JSON only and
does not create trusted reply evidence/check reports. Before sending a fresh
trusted Mention, run the bundle with `ZOHO_CLIQ_TRUSTED_REPLY_PLAN_ONLY=1`; the
plan output `openclaw_cliq_trusted_reply_evidence_bundle_plan` should report
`status=awaiting_live_delivery_facts` until the sender/message/reply ids have
been captured. The plan is written to `ZOHO_CLIQ_TRUSTED_REPLY_PLAN_FILE` or
`openclaw_cliq_trusted_reply_plan_<run-id>.json` under the report directory and
includes `nextAction`, `readyForFinalBundle`, `missingFacts`, and `readyFacts`
for machine-readable handoff, plus `reportFiles` and `reportsReady` for
artifact handoff by filename. Its `collectionGuide` tells agents to enforce
`sendExactlyOneTrustedMention`, read `requiredLiveFacts`, collect only
`trustedSenderId`, `trustedMessageId`, and `deliveryId`, hash raw ids before
evidence, use `factPrepareCommand`, and honor `forbiddenEvidence` by keeping
`rawWebhookPayload`, `rawMessageBody`, `rawCliqReplyBody`, and `secrets` out of
the artifact. Its
`acceptedFactSources` includes `env`, `hashFactsFile`, and `rawFactsFile`;
prefer `ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE` for the final run when a hash-only
local facts JSON is available, or pass
`ZOHO_CLIQ_TRUSTED_REPLY_RAW_FACTS_FILE` directly to the final bundle when only
an id-only raw-facts JSON is available. The plan also declares
`collectionGuide.factsFileKind=openclaw_cliq_trusted_reply_facts` and
`collectionGuide.factsPrepareReadyStatus=facts_file_ready`; it also exposes
`collectionGuide.rawFactsPrepareEnv=ZOHO_CLIQ_TRUSTED_REPLY_RAW_FACTS_FILE` and
`collectionGuide.rawFactsFileKind=openclaw_cliq_trusted_reply_raw_facts` when an
agent/operator wants to hand the three raw facts to the prepare script through a
temporary local JSON file. The final facts file must use
`kind=openclaw_cliq_trusted_reply_facts` and contain only
`trustedSenderIdHash`, `trustedMessageIdHash`, and `deliveryIdHash` as
`sha256:` references; the bundle rejects raw fields such as `trustedSenderId`,
`trustedMessageId`, or `deliveryId` with `facts_file_raw_ids_present`, and
rejects secret markers with `facts_file_secret_marker_present`. Its `redaction`
object must keep raw ids, hash values, local
paths, and secrets out of the plan.

After the real trusted Mention succeeds, prefer preparing the hash-only facts
file before running the final bundle. Either provide the three raw facts as env
vars:

```bash
ZOHO_CLIQ_TRUSTED_REPLY_REPORT_DIR=tests/auto_pilot/reports \
ZOHO_CLIQ_TRUSTED_SENDER_ID="$TRUSTED_SENDER_ID" \
ZOHO_CLIQ_TRUSTED_MESSAGE_ID="$TRUSTED_MESSAGE_ID" \
ZOHO_CLIQ_DELIVERY_ID="$DELIVERY_ID" \
  ops/scripts/openclaw_cliq_trusted_reply_facts_prepare.sh
```

The prepare script prints `openclaw_cliq_trusted_reply_facts_prepare` with
`status=facts_file_ready`, writes `openclaw_cliq_trusted_reply_facts` JSON under
the trusted reply report directory, and keeps raw ids plus local paths out of
stdout. Set `ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE` to that file for the final
bundle.

Or store only those three raw ids in an untracked local JSON file:

```json
{
  "schemaVersion": 1,
  "kind": "openclaw_cliq_trusted_reply_raw_facts",
  "trustedMention": {
    "trustedSenderId": "<trusted_cliq_user_id>",
    "messageId": "<trusted_mention_message_id>"
  },
  "delivery": {
    "messageId": "<agent_reply_delivery_id>"
  }
}
```

Then either run the prepare step explicitly:

```bash
ZOHO_CLIQ_TRUSTED_REPLY_RAW_FACTS_FILE=/path/to/trusted-reply-raw-facts.json \
ZOHO_CLIQ_TRUSTED_REPLY_REPORT_DIR=tests/auto_pilot/reports \
  ops/scripts/openclaw_cliq_trusted_reply_facts_prepare.sh
```

The raw-facts file is for local handoff only. Do not put raw webhook payloads,
message text, reply bodies, token values, or webhook secrets into it; the
prepare script rejects body fields with
`raw_facts_file_forbidden_body_present` and secret markers with
`raw_facts_file_secret_marker_present`. It also rejects placeholder raw id
values such as `<trusted_cliq_user_id>` or `replace-me` with stable errors such
as `trusted_sender_raw_placeholder`, `trusted_message_raw_placeholder`, or
`delivery_id_raw_placeholder`. The final bundle also accepts
`ZOHO_CLIQ_TRUSTED_REPLY_RAW_FACTS_FILE` directly; when no
`ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE` is set, it auto-runs facts prepare,
loads the generated hash-only facts file, and still keeps stdout to the final
trusted reply checker JSON.

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
| `deliveryCount=0` after a successful assistant answer | The native turn reached the agent but no visible Cliq reply was delivered through the adapter. | Confirm the running plugin build sets `Provider` and `Surface` to `cliq`, rebuild/restart the gateway if needed, then replay one fresh trusted Mention. |
| Agent session has an answer but the direct Bot chat shows no reply | The handler likely supplied no real Cliq message id, so an old build may have tried to reply against a synthetic `webhook-*` or `zoho-message-*` id, or sent to a user id that is not sendable in Bot direct context. | Rebuild/restart with the direct Bot fallback fix, then replay one fresh trusted direct Message/Mention and confirm the outbound route is a direct `chatId` send unless a real message id is available. |
| `dispatch_reply_rate_limited` | The handler and OpenClaw dispatch worked, but the final `zoho cliq send` was throttled by Zoho. | Wait for cooldown, avoid bursty probe loops, make sure the quiet webhook lifecycle build is installed, then replay exactly one fresh Bot message. |
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
   `ops/scripts/openclaw_cliq_live_smoke.sh`, setting
   `ZOHO_CLIQ_EXPECTED_AGENT_ID` when the account must route to a specific
   agent. Use `ZOHO_CLIQ_ROUTE_BINDING_ONLY=1` first when only route config is
   being checked. Finish with a controlled trusted Bot event that produces
   exactly one native agent turn and one Cliq reply, then validate the redacted
   evidence with `ops/scripts/openclaw_cliq_trusted_reply_evidence.sh` before
   production agent rollout; raw ids and message/reply bodies do not belong in
   the evidence file.
