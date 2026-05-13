# OpenClaw Zoho Cliq channel

Native OpenClaw channel package for Zoho Cliq, backed by `zoho-cli`.

This package includes the `cliq-channel-401` installable skeleton,
`cliq-channel-402` config/SecretRef/setup slice, `cliq-channel-416` human
setup UX slice, `cliq-channel-403` security/policy slice, and
`cliq-channel-414` native SDK seam slice, `cliq-channel-404` CLI adapter slice,
`cliq-channel-405` outbound delivery slice, `cliq-channel-406` inbound
polling slice, `cliq-channel-407` webhook inbound slice,
`cliq-channel-408` status/read lifecycle slice, `cliq-channel-413`
turn-ledger loop-prevention slice, `cliq-channel-409` native UX/status
diagnostics slice, and `cliq-channel-410` AI troubleshooting docs slice. It
also includes the `cliq-channel-417` native agent turn dispatch slice and the
`cliq-channel-415` observability/privacy hardening slice plus the
`cliq-channel-411` fake/live smoke gate harness, `cliq-channel-412`
compatibility maintenance slice, `cliq-channel-419` repeatable RC pack
preflight script, `cliq-channel-420` Bot handler templates,
`cliq-channel-421` runtime contract coverage for those handlers, and
`cliq-channel-422` RC package metadata. It
declares the plugin/channel metadata, setup/runtime entrypoints,
configured/auth-state probes, a native
OpenClaw channel object, config schema metadata, DM pairing, group allowlist,
mention gating, scoped employee policy gates, audit warnings,
account/network/thread-aware session grammar, native mention-policy delegation,
approval capability metadata, a JSON-safe `zoho cliq ...` process adapter,
native outbound send/reply/thread-reply delivery, normalized/deduped polling
fallback events from `zoho cliq chats` + `zoho cliq context`, and Bot webhook
intake at `/webhooks/cliq`, shared status/read lifecycle handling, a native
turn ledger for duplicate/active/dead-letter loop prevention, and status/
capability/routing diagnostic summaries plus AI-facing troubleshooting guidance
for operator surfaces. Accepted webhook and polling events now enter OpenClaw's
native channel turn runtime and route replies through the Cliq outbound adapter;
direct Bot events with synthetic `webhook-*` / `zoho-message-*` ids fall back to
ordinary direct sends through the real Cliq chat id, while direct events with
real message ids reply through that same chat id.
The adapter requires `zoho cliq send --chat-id` for synthetic Bot direct events
that have no replyable Zoho message id, so answers stay visible in the Bot chat
instead of being delivered as a separate user DM.
Redacted audit events, correlation ids, diagnostic bundles, rate-limit
diagnostics, privacy retention rules, dead-letter replay guidance, and the npm
integrity release placeholder are now part of the channel diagnostics surface.
The live smoke harness records Zoho refresh throttling as `rate_limited` /
`skip_deferred` and keeps public Bot callback verification separate from local
gateway/webhook security gates. The RC pack harness runs typecheck/build and
packs from the package directory, then writes an ignored JSON summary for
release evidence without publishing or mutating version metadata at pack time.
`ops/scripts/openclaw_cliq_rc_promotion_check.sh` combines that pack summary
with artifact verification, Temp-HOME install smoke, trusted reply evidence,
and package metadata, then reports `ready_for_operator_publish` only when
`expectedIntegrity` is still the release placeholder and no
publish/tag/version-bump action has occurred.
`ops/scripts/openclaw_cliq_rc_operator_publish_bundle.sh` then gathers the
latest pack, artifact, install smoke, promotion, and trusted reply reports into
one operator review JSON with artifact shasum/integrity, release posture, and
explicit `agentMayPublish=false`, `agentMayTag=false`, and
`agentMayFillExpectedIntegrity=false` flags before reporting
`operator_publish_bundle_ready`.
`ops/scripts/openclaw_cliq_rc_release_notes_draft.sh` generates a read-only
Markdown release-notes draft from that bundle and refuses to run if the bundle
is not ready or any agent publish/tag/integrity-fill permission is true.
`ops/scripts/openclaw_cliq_rc_publish_plan.sh` then creates a read-only
operator publish plan from the ready bundle plus safe release-notes draft,
reports `operator_publish_plan_ready`, and keeps `agentMayExecutePlan=false`
while listing local/operator, npm RC, and GitHub artifact paths.
`ops/scripts/openclaw_cliq_rc_operator_handoff_manifest.sh` indexes the ready
bundle, release-notes draft, publish plan, artifact facts, report filenames,
source commit, and false agent permission flags before reporting
`operator_handoff_manifest_ready`.
`ops/scripts/openclaw_cliq_rc_source_drift_check.sh` keeps the handoff manifest
current after later repo commits by reporting `package_source_unchanged` only
when `integrations/openclaw-channel-cliq/` did not drift. When no explicit
`OPENCLAW_CLIQ_HANDOFF_MANIFEST_FILE` is provided, it selects the newest
`operator_handoff_manifest_ready` report and skips newer blocked drafts so
recurring autonomy checks do not stop on stale failed manifest attempts.
`ops/scripts/openclaw_cliq_rc_operator_selection_review.sh` validates a selected
operator path without running it, and
`ops/scripts/openclaw_cliq_rc_operator_decision_packet.sh` is the preferred
one-command handoff: it returns `awaiting_operator_publish_path` until the
operator chooses `local_operator_rc`, `npm_rc_publish`, or
`github_release_artifact`, then `operator_publish_selection_ready` after a
reviewed selection, while keeping `agentMayExecuteSelectedPath=false`.
`docs/releases/OPENCLAW_CLIQ_CHANNEL_V0_4_OPERATOR_PUBLISH_HANDOFF.md` is the
operator handoff for the approval boundary, preflight commands, publish path
choice, post-publish checks, and abort conditions; agents must not run
`npm publish`, create tags/releases, or fill `openclaw.install.expectedIntegrity`
without explicit operator approval.
`ops/scripts/openclaw_cliq_bot_handler_operator_prompt.sh --md` renders the
current direct-DM Bot handler handoff for humans: it names the required Message
Handler visible signal, links the Message Handler template section, includes the
public callback and one-message recheck commands, and stores no raw payloads,
message text, reply text, local paths, or secrets.
`ops/scripts/openclaw_cliq_rc_artifact_check.sh` verifies the packed tarball
without publishing: it checks the pack summary, shasum, package metadata,
manifest/channel identity, required runtime/docs/skill entries, and no
publish/tag/version-bump posture before reporting `artifact_verified`.
`ops/scripts/openclaw_cliq_rc_install_smoke.sh` verifies that artifact in a
Temp-HOME OpenClaw profile by running local `plugins install`, `plugins inspect
zoho-cliq --json`, and `plugins doctor` before reporting
`install_smoke_passed`.

## Contract

- Package: `@adwasd/openclaw-zoho-cliq`
- Version: `0.4.0-rc.1`
- Plugin id: `zoho-cliq`
- Channel id: `cliq`
- Config root: `channels.cliq`
- Host/plugin API: `>=2026.5.3-1`
- Node: `>=22.14.0`

The source of truth is
`../../docs/architecture/OPENCLAW_CLIQ_CHANNEL_SDK_CONTRACT.md`.

Human setup and troubleshooting live in
`../../docs/releases/OPENCLAW_CLIQ_CHANNEL_SETUP.md`.
Real Zoho Bot Deluge handler templates live in
`../../docs/releases/OPENCLAW_CLIQ_BOT_HANDLER_TEMPLATES.md`.
Host compatibility maintenance lives in
`../../docs/releases/OPENCLAW_CLIQ_CHANNEL_COMPATIBILITY.md`.
The v0.4 RC decision checklist lives in
`../../docs/releases/OPENCLAW_CLIQ_CHANNEL_V0_4_RC_CHECKLIST.md`.
The v0.4 operator publish handoff lives in
`../../docs/releases/OPENCLAW_CLIQ_CHANNEL_V0_4_OPERATOR_PUBLISH_HANDOFF.md`.

Repeatable local RC package preflight:
`../../ops/scripts/openclaw_cliq_rc_pack.sh`.

No-publish local RC artifact check:
`../../ops/scripts/openclaw_cliq_rc_artifact_check.sh`.

No-publish Temp-HOME OpenClaw install smoke:
`../../ops/scripts/openclaw_cliq_rc_install_smoke.sh`.

No-publish local RC promotion preflight:
`../../ops/scripts/openclaw_cliq_rc_promotion_check.sh`.

No-publish operator review bundle:
`../../ops/scripts/openclaw_cliq_rc_operator_publish_bundle.sh`.

Read-only release-notes draft:
`../../ops/scripts/openclaw_cliq_rc_release_notes_draft.sh`.

Read-only operator publish plan:
`../../ops/scripts/openclaw_cliq_rc_publish_plan.sh`.

Read-only operator handoff manifest:
`../../ops/scripts/openclaw_cliq_rc_operator_handoff_manifest.sh`.

Read-only source drift guard:
`../../ops/scripts/openclaw_cliq_rc_source_drift_check.sh`.

Read-only selected path review:
`../../ops/scripts/openclaw_cliq_rc_operator_selection_review.sh`.

Read-only operator decision packet:
`../../ops/scripts/openclaw_cliq_rc_operator_decision_packet.sh`.

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
          "webhookPath": "/webhooks/cliq",
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

## Bot handler webhook

Configure the Zoho Cliq Bot Message, Mention, Participation, or Context Handler
to POST to the OpenClaw plugin route. The route verifies
`X-Cliq-Webhook-Secret`, normalizes the payload into the same inbound event
shape as polling, dedupes by account/network/chat/message, and applies the
same allowlist, mention, and employee policy gates.

Use `../../docs/releases/OPENCLAW_CLIQ_BOT_HANDLER_TEMPLATES.md` for
copy-ready Message, Mention, Participation, and Context Handler Deluge code.
Direct Bot DMs should use the Message Handler template that wraps Zoho's
text-like `message` value into an explicit message map before posting.
For plain direct Bot chats, the Zoho Bot details **Handlers** list must include
**Message Handler**; saving only **Mention Handler** is enough for @mentions in
channel/group contexts but will not handle regular direct messages from another
account.
Current Bot handlers should set `reply_mode` to `deluge_response`, assign
`webhook_response = invokeurl [...]`, and return that map when it contains a
`text` key. That lets Zoho render OpenClaw's final answer as the native Bot
handler response instead of relying on a second OAuth send. If the handler
cannot expose a real Zoho message id, use the template's `zoho-message-*`
dedupe id; native dispatch will not attempt a reply against that synthetic id.

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
  return webhook_response;
}
return response;
```

`response.put("text","received")` is only a Zoho handler ACK. It may appear
before or after the OpenClaw answer and does not prove final agent reply
delivery. Remove fixed ACKs once `deluge_response` mode is installed.
The no-response packet includes a `diagnosis` object; when public callback smoke
is green but no recent webhook arrives, `diagnosis.code=zoho_bot_handler_not_posting`
points at a Zoho handler save/trigger issue rather than OAuth or tunnel
delivery.

`parameters:payload.toString()` is tolerated for Deluge compatibility, but
`body:payload.toString()` keeps the HTTP JSON intent clearer. The webhook parser
also accepts Deluge Map-string bodies such as
`{handler=message, message=..., user={...}}` when Zoho does not emit strict
JSON. Rotate any secret that was pasted into screenshots or chat before using a
real Bot.

The RC intake accepts Message, Mention, Participation, and Context handlers.
Welcome, Incoming Webhook, Call, and Menu handlers are intentionally ignored
until a later slice maps them to explicit channel workflows.

References: `https://www.zoho.com/cliq/help/platform/bot-mentionshandler.html`
and `https://www.zoho.com/deluge/help/`.

## Development

```bash
npm install --ignore-scripts
npm run typecheck
npm run build
openclaw plugins install . --link
openclaw plugins inspect zoho-cliq --json
openclaw plugins doctor
../../ops/scripts/openclaw_cliq_live_smoke.sh
../../ops/scripts/openclaw_cliq_hash_ref.sh
../../ops/scripts/openclaw_cliq_rc_pack.sh
../../ops/scripts/openclaw_cliq_trusted_reply_evidence_bundle.sh
../../ops/scripts/openclaw_cliq_trusted_reply_evidence_prepare.sh
../../ops/scripts/openclaw_cliq_trusted_reply_evidence.sh
```

Use a host satisfying `>=2026.5.3-1` for inspect/install validation. The
upgraded global `OpenClaw 2026.5.3-1` host is the supported baseline;
`openclaw@latest` `2026.5.4` and `openclaw@beta` `2026.5.4-beta.3` currently
pass Temp-HOME linked install/inspect/doctor checks.

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
timeout, rate-limit, missing-command, and generic failures while keeping stderr
diagnostics redacted. Native outbound delivery uses OpenClaw's shared message
surface with markdown chunking and maps text sends to `zoho cliq send`, message
replies to `zoho cliq reply`, and thread delivery to `zoho cliq thread-reply`.
Inbound webhook delivery registers OpenClaw plugin HTTP routes with
`auth: "plugin"` and exact matching. Accepted events can be observed through
the native OpenClaw channel turn runtime. Registered Bot webhook routes default
to quiet lifecycle mode so direct Bot DMs do not spend Zoho send quota on
status/read-ack calls before the final answer. The shared lifecycle wrapper
still supports `received -> thinking`, native agent dispatch, `mark-read`, and
`done` for explicit smoke/polling runtimes; dispatch failures attempt `failed`.
Final delivery failures record redacted `deliveryFailures[].errorKind`, so
`rate_limited` is visible in diagnostics without storing message bodies. The
turn ledger blocks duplicate completed events, coalesces concurrent
same-conversation bursts, and dead-letters failed turns after bounded attempts.
`src/native-dispatch.ts` records session and last-route metadata, then delivers
agent replies through the Cliq outbound adapter. It sets OpenClaw
`Provider`/`Surface` to the channel id `cliq` for accepted turns and keeps the
webhook/polling source in supplemental context, so final answers are not
misclassified as cross-channel route-reply traffic. `src/status.ts` exposes
status, capability, and routing summaries for OpenClaw/operator diagnostics.
`src/observability.ts` and `src/privacy.ts` keep support bundles redacted:
message bodies, raw webhook payloads, token passwords, webhook secrets,
authorization headers, and raw signatures are excluded. The Lane 3 docs now map
setup states, diagnostic blockers, and explicit routing targets to AI-safe next
actions. Public Bot callback verification remains a deployment prerequisite
when no reachable tunnel/gateway URL is configured.
