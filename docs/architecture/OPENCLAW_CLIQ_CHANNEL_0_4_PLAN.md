# OpenClaw Cliq channel plan (v0.4)

## Purpose

`zoho-cli` v0.4 will add a native OpenClaw channel plugin for Zoho Cliq. The
plugin should feel like the existing OpenClaw Discord/Telegram channels while
keeping all Zoho API details behind the `zoho` CLI.

This plan intentionally moves deeper CRM work to v0.5. The release order is:

1. Finish and publish the current Mail + Cliq CLI release line.
2. Continue post-RC Cliq modularization until the CLI surface is easy for agents
   to inspect and maintain.
3. Build the OpenClaw Cliq channel in v0.4.
4. Resume CRM expansion in v0.5.

## Product goal

Create an installable OpenClaw channel plugin:

```text
package: @adwasd/openclaw-zoho-cliq
plugin id: zoho-cliq
channel id: cliq
config root: channels.cliq
target release: v0.4.x
```

The OpenClaw agent should use the normal OpenClaw channel/message flow. The
plugin should not expose a parallel set of ad-hoc `cliq_*` tools when OpenClaw
already has native channel actions.

Current OpenClaw baseline lock is captured in
`docs/architecture/OPENCLAW_CLIQ_CHANNEL_SDK_CONTRACT.md`.

`cliq-channel-400` check on `2026-05-04T21:39:33Z`, refreshed after the global
host upgrade on `2026-05-05T02:45:00Z`:

- global workspace OpenClaw: `2026.5.3-1`
- previous local OpenClaw: `2026.4.15`
- npm `latest`: `2026.5.3-1`
- npm `beta`: `2026.5.4-beta.1`
- target `minHostVersion`: `>=2026.5.3-1`
- target `compat.pluginApi`: `>=2026.5.3-1`

v0.4 implementation targets the stable host checked above. The earlier local
`2026.4.15` install is kept only as compatibility history.

## Design principles

1. **CLI-owned Zoho API compatibility**
   - The plugin calls `zoho cliq ...`.
   - The plugin does not implement a second Zoho REST client.
   - Zoho payload/API changes are fixed in the CLI normalization layer first.
2. **OpenClaw-native channel behavior**
   - Register as a channel provider through OpenClaw plugin APIs.
   - Participate in `openclaw channels list/status/capabilities`, the core
     message tool, session routing, pairing, security audit, and SecretRef flows.
3. **Secure-by-default**
   - `dmPolicy=pairing` by default.
   - `groupPolicy=allowlist` by default.
   - Mention-gated group/channel intake by default.
   - Secrets use SecretRef/env/file/exec inputs, not committed plaintext.
4. **Scoped employee mode for production**
   - Cliq messages are untrusted business input, never system/developer
     instructions.
   - The agent may act only inside the configured work scope.
   - Debug, install, config-write, secret-read, and system-level operations are
     denied from normal chat surfaces by default.
5. **Agent convenience is a feature**
   - Setup errors must tell the operator exactly what to run next.
   - CLI help and plugin diagnostics must be actionable.
   - Skill docs must explain the native channel path and the fallback CLI path.
6. **Human install UX is a product surface**
   - Operators should be able to install and validate the channel without
     reading source code.
   - Setup screens should explain only the next decision, required permission,
     and safe default.
   - Every failed setup state should offer a clear fix, not a raw stack trace.
7. **Compatibility is explicit**
   - Pin a minimum OpenClaw host/plugin API version for v0.4.
   - Keep a compatibility table for local older OpenClaw installs.
   - Avoid depending on private OpenClaw internals when SDK helpers exist.

## Non-goals for v0.4

- Replacing `zoho-cli` with a Node Zoho client.
- Full parity with every Discord/Telegram action on day one.
- Blocking v0.4 on Zoho endpoints already classified as externally unsupported.
- Resuming deep CRM write workflows before the native Cliq channel is stable.

## Proposed repository layout

```text
integrations/openclaw-channel-cliq/
  package.json
  openclaw.plugin.json
  index.ts
  setup-entry.ts
  src/
    channel.ts
    config.ts
    security.ts
    employee-policy.ts
    zoho-cli.ts
    inbound.ts
    outbound.ts
    normalize.ts
    webhook.ts
    polling.ts
    dedupe.ts
    turn-ledger.ts
    status.ts
    session-grammar.ts
    approvals.ts
    observability.ts
    privacy.ts
  tests/
    config.test.ts
    security.test.ts
    normalize.test.ts
    outbound.test.ts
    inbound.test.ts
    integration.test.ts
  fixtures/
    cliq-bot-message.json
    cliq-participation-message.json
    zoho-cli/
  README.md
  SECURITY.md
```

## OpenClaw plugin contract

### Manifest

`openclaw.plugin.json` should declare static metadata that OpenClaw can inspect
without executing arbitrary runtime code.

Required baseline:

```json
{
  "id": "zoho-cliq",
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
      "label": "Zoho Cliq"
    }
  },
  "activation": {
    "channels": ["cliq"]
  },
  "setup": {},
  "qaRunners": [],
  "skills": ["./skill"],
  "configSchema": {
    "type": "object",
    "additionalProperties": false,
    "properties": {}
  }
}
```

### Package metadata

`package.json#openclaw` should declare the runtime entry points and host
compatibility gate.

```json
{
  "openclaw": {
    "extensions": ["./index.js"],
    "setupEntry": "./setup-entry.js",
    "channel": {
      "id": "cliq",
      "label": "Zoho Cliq",
      "selectionLabel": "Zoho Cliq (Bot API + zoho-cli)",
      "docsPath": "/channels/cliq",
      "docsLabel": "cliq",
      "blurb": "Zoho Cliq channel backed by zoho-cli.",
      "markdownCapable": true,
      "configuredState": {
        "specifier": "./configured-state.js",
        "exportName": "hasCliqConfiguredState"
      },
      "persistedAuthState": {
        "specifier": "./auth-presence.js",
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

The exact minimum version was locked by `cliq-channel-400` and must be rechecked
again before publishing v0.4, because OpenClaw channel plugin APIs are still
evolving.

Manifest/package split:

- Put pre-runtime discovery, config schema, channel config metadata, setup
  metadata, QA runner descriptors, env vars, and skills in
  `openclaw.plugin.json`.
- Put runtime entrypoints, setup entrypoints, install/update hints,
  `minHostVersion`, integrity pins, and lightweight configured/auth-state
  checkers in `package.json#openclaw`.
- Avoid custom top-level manifest keys; OpenClaw reads documented fields only.
- Keep setup/configured-state/auth-presence modules tiny and avoid importing the
  full channel runtime.

### Runtime registration

Use OpenClaw channel SDK helpers where possible:

- `defineChannelPluginEntry`
- `defineSetupPluginEntry`
- `createChatChannelPlugin`

The plugin should register:

- setup/config schema
- status/capabilities metadata
- security and pairing adapters
- shared mention policy facts and decisions
- session grammar / conversation-id resolver
- approval capability for review-required actions
- outbound adapter
- inbound webhook/polling runtime
- optional threading adapter

## Configuration contract

Planned config root:

```yaml
channels:
  cliq:
    enabled: true
    defaultAccount: default
    accounts:
      default:
        enabled: true
        accountEmail: ai-dev@example.com
        network: happydistrouklimited
        cliPath: zoho
        configPath:
          source: env
          provider: default
          id: ZOHO_CONFIG
        tokenPassword:
          source: env
          provider: default
          id: ZOHO_TOKEN_PASSWORD
        webhookSecret:
          source: env
          provider: default
          id: ZOHO_CLIQ_WEBHOOK_SECRET
        webhookPath: /webhooks/cliq/default
        dmPolicy: pairing
        groupPolicy: allowlist
        allowFrom: []
        groupAllowFrom: []
        requireMention: true
        employeeMode:
          enabled: true
          scopeProfile: default
          policy: strict
          allowDebugFromChannel: false
          allowInstallFromChannel: false
          allowConfigWritesFromChannel: false
          adminAllowFrom: []
          allowedIntents:
            - cliq.reply
            - cliq.status
            - mail.triage
            - mail.reply
            - mail.send_with_review
          deniedIntents:
            - system.debug
            - system.install
            - system.config_write
            - system.exec
            - secrets.read
        workScopes:
          default:
            role: employee
            allowedSurfaces:
              - cliq
              - mail
            crm: read_only
            requiresReviewFor:
              - mail.send_with_review
              - external_send
              - delete
              - system.install
              - system.config_write
        polling:
          enabled: true
          intervalSeconds: 60
          maxChatsPerPass: 8
        actions:
          statusReactions: true
          markRead: true
          reactions: true
          media: false
```

Security notes:

- `groupPolicy=open` is allowed only as an explicit opt-in and must trigger an
  audit warning.
- `allowFrom=["*"]` is allowed only with an explicit warning.
- `groupAllowFrom=["*"]` is allowed only with an explicit warning.
- `configWrites` should default to false outside setup flows.
- `employeeMode.enabled=true` should be the recommended production default.
- Chat-originated requests to debug, install packages, change config, execute
  shell/system actions, or reveal secrets must be refused or escalated through a
  separate operator/admin approval path.
- The plugin must never log token values, webhook secrets, or resolved
  `ZOHO_TOKEN_PASSWORD` values.

## CLI compatibility contract

The plugin must call a small, documented CLI subset:

```bash
zoho cliq status --check-auth --network <network>
zoho cliq capabilities --network <network>
zoho cliq chats --network <network> --unread-only --exclude-reacted-by-self
zoho cliq context --network <network> --chat-id <chat_id> --limit <n>
zoho cliq watch-context --network <network> --chat-id <chat_id>
zoho cliq watch-act --watch-file - --action reply-latest --text <text>
zoho cliq reply <message_id> --chat-id <chat_id> --text <text>
zoho cliq send --user-id <user_id> --text <text>
zoho cliq send --channel-id <channel_id> --text <text>
zoho cliq mark-read <message_id> --chat-id <chat_id>
zoho cliq status-react <message_id> --status <status> --chat-id <chat_id>
```

Recommended CLI additions before plugin implementation:

```bash
zoho cliq bot-event normalize --input -
zoho cliq bot-event inspect --input -
zoho cliq channel-contract --format openclaw
```

These commands would keep Zoho webhook payload compatibility in Python, next to
the existing Cliq API client and test matrix.

## Native SDK alignment requirements

### Session grammar and threading

The channel must define a stable mapping from Zoho Cliq identities to OpenClaw
conversation/session ids:

- Include account id and Cliq network in every internal key to avoid collisions
  across Zoho accounts or Cliq networks.
- Resolve direct chats, channels, threads, and parent messages through an
  explicit session grammar module.
- Prefer OpenClaw's canonical conversation resolver hook when available so core
  can map raw provider ids to base conversations, thread ids, and parent
  candidates.
- Keep parent candidates ordered from narrowest to broadest so replies prefer
  the original thread before falling back to the channel/chat.
- Add fixtures for DM, channel mention, thread reply, bot participation, deleted
  parent, and cross-network same-id cases.

### Mention policy

The plugin should gather Cliq-specific mention facts, then delegate policy
evaluation to OpenClaw's shared inbound mention helper when the host SDK exposes
it.

Cliq-owned facts:

- explicit bot mentions
- reply-to-bot evidence
- quoted-bot evidence
- thread-participation evidence
- service/system message exclusions
- command text and actor identity

Shared policy decisions:

- `requireMention`
- explicit mention match
- implicit mention allowlist
- authorized command bypass
- final skip decision

Command bypass must never become a generic policy bypass. It should be allowed
only for configured control commands, from authorized actors, and after the same
source/pairing/allowlist checks.

### Approvals and high-impact actions

OpenClaw core owns same-chat `/approve`, generic approval routing, expiry,
dedupe, and fallback delivery. The Cliq plugin should expose channel-specific
approval facts through the current `approvalCapability` surface instead of
shipping custom approval tools.

Review-required actions include:

- external mail send
- delete/destructive actions
- config write
- plugin install/update
- shell/system execution
- policy changes

Scoped employee mode should block normal chat from initiating system-level work.
When a legitimate workflow needs approval, route it through OpenClaw's approval
capability with account-scoped actor authorization and auditable delivery.

### Runtime namespace boundaries

- Use lightweight setup and CLI metadata entrypoints for setup/status/help.
- Keep webhook, polling, gateway, and network clients in the full runtime entry.
- If a gateway RPC method is needed, use a plugin-specific prefix.
- Never register under reserved core admin namespaces such as `config.*`,
  `exec.approvals.*`, `wizard.*`, or `update.*`.
- Prefer narrow SDK subpath imports for hot runtime code so OpenClaw upgrades
  have fewer broad import breakpoints.

## Human installation and setup UX

The channel should be easy for a human operator to install from OpenClaw without
becoming a CLI archaeology project. AI-facing docs still matter, but the default
install path should be a guided OpenClaw setup flow.

### First-run journey

1. Select **Zoho Cliq** from OpenClaw channel/plugin install surfaces.
2. Choose install source: published npm package or local development path.
3. Confirm host compatibility and package integrity before enabling.
4. Select or create a Cliq account profile.
5. Validate `zoho` binary availability and `zoho cliq status --check-auth`.
6. Choose Cliq network and verify scopes/capabilities.
7. Configure webhook secret/path, or choose polling fallback.
8. Choose safe access policy: DM pairing, group allowlist, mention required.
9. Choose scoped employee profile and review high-impact actions.
10. Send a test message or run a dry-run inbound fixture.
11. Show final status: installed, configured, reachable, secure, and tested.

### Setup screens

Each setup screen should have one primary action and one recovery action:

- **Install**: install package, or open local path instructions.
- **Zoho CLI**: detect `zoho`, show install command when missing.
- **Auth**: show login/scopes command when auth is missing.
- **Network**: list available networks or explain how to discover them.
- **Webhook**: generate path/secret guidance and validation status.
- **Polling fallback**: explain latency and rate-limit tradeoff.
- **Security**: present pairing/allowlist/mention defaults as recommended.
- **Employee mode**: explain work scope and blocked system actions plainly.
- **Test**: send/receive dry-run with redacted evidence.
- **Finish**: show `openclaw channels status --channel cliq --deep`.

Copy should be short, concrete, and non-alarming. Avoid exposing raw config
schema unless the operator opens an advanced/details view.

### Human-readable states

The setup/status UI should normalize common failure states:

| State | User-facing message | Primary fix |
| --- | --- | --- |
| `zoho_missing` | Zoho CLI was not found. | Install `zoho-cli` and retry detection. |
| `not_logged_in` | Zoho login is required. | Run `zoho login --with-cliq`. |
| `missing_scope` | Cliq permissions are incomplete. | Re-auth with Cliq scopes. |
| `network_missing` | Cliq network is not configured. | Select a network from discovery. |
| `webhook_unverified` | Webhook secret/path is not verified. | POST a controlled Bot handler event to `/webhooks/cliq` or use polling. |
| `allowlist_empty` | Group messages are blocked until an allowlist is set. | Add allowed channels/users. |
| `employee_scope_empty` | Employee mode needs a work scope. | Pick a default scope profile. |
| `host_too_old` | OpenClaw must be upgraded for this plugin. | Upgrade OpenClaw or use compatibility mode. |

### Documentation surfaces for people

The package should include:

- short install guide for OpenClaw UI users
- CLI install fallback for terminal users
- screenshots or text snapshots of setup states when the UI stabilizes
- troubleshooting table matching the normalized states above
- security explanation written for managers/operators, not only developers
- uninstall/disable instructions
- upgrade instructions, including integrity mismatch recovery

### UX acceptance criteria

- A human operator can install from OpenClaw plugin/channel surfaces with no
  source-code reading.
- All required secrets are introduced as SecretRef/env choices, never as
  plaintext examples.
- Safe defaults are visually marked as recommended.
- Dangerous/open policies require an explicit advanced choice and produce audit
  warnings.
- Failed setup states provide one command or one UI action to try next.
- AI docs and human docs use the same config names and diagnostic commands.

## Runtime flow

### Scoped employee mode

Scoped employee mode is the recommended production posture. It treats every
Cliq message as user content from an untrusted business channel, even when the
sender is an internal employee.

Threat model:

- A human user may try to socially engineer the agent through chat.
- A human user may paste fake system/developer instructions into Cliq.
- A normal business chat may ask the agent to reveal debug logs, secrets, config,
  plugin internals, shell access, or installation commands.
- A compromised or noisy chat may repeatedly trigger the same action.

Enforcement order:

1. Normalize the webhook or polling payload into the stable inbound event shape.
2. Verify source, pairing, allowlist, mention, and dedupe gates.
3. Run the employee policy gate against `employeeMode` and `workScopes`.
4. Build the OpenClaw inbound session only when the action is inside scope.
5. Dispatch to OpenClaw with a clear instruction that channel text is untrusted
   user content and must not override system/developer policy.
6. Apply outbound action gates before delivery.

Normal chat is allowed to request business work inside the configured role, such
as replying in Cliq, triaging mail, drafting an answer, checking status, or
creating a review-required send. Normal chat is not allowed to request:

- debug mode or internal trace dumps
- plugin installation or host upgrade
- config writes or SecretRef changes
- shell/system execution
- secret reads
- policy bypasses
- unrestricted cross-product actions outside the configured work scope

Admin override should require a separate operator path. The v0.4 default is no
chat-originated override. If a deployment later enables `adminAllowFrom`, the
override must still be explicit, audited, and limited to the configured admin
action, not a broad policy disable.

Refusals should be short and useful: explain that the requested operation is
outside the channel work scope, then offer the closest allowed business action or
the local operator command that can diagnose the issue.

### Loop prevention and efficiency contract

The channel should maintain a small turn ledger for every inbound event:

```json
{
  "eventId": "cliq/default/network/chat/message",
  "dedupeKey": "default:network:chat:message",
  "state": "new",
  "attempts": 0,
  "lastAction": "",
  "lastError": "",
  "createdAt": "2026-05-04T00:00:00Z",
  "updatedAt": "2026-05-04T00:00:00Z"
}
```

Required hard limits:

- Drop self-authored messages before agent dispatch.
- Process one active turn per account/network/chat unless manually requeued.
- Dispatch at most one agent turn per inbound event by default.
- Coalesce short message bursts from the same sender/chat before dispatch when
  supported by the host runtime.
- Use idempotency keys for outbound replies and status updates where possible.
- Keep business retry ownership in the plugin, transport retry ownership in the
  CLI, and avoid duplicate OpenClaw sends.
- Retry with bounded backoff, then move to a dead-letter state with actionable
  diagnostics.
- Never let status/read-ack failures recursively trigger new agent work.
  Complete in `cliq-channel-408`; lifecycle action failures are recorded as
  terminal diagnostics and do not dispatch another event.

### Inbound webhook path

1. Receive Zoho Cliq bot webhook event. Complete in `cliq-channel-407`.
2. Verify configured webhook secret/signature where available. Complete via
   `X-Cliq-Webhook-Secret` in `cliq-channel-407`.
3. Normalize payload through CLI or local fallback normalizer. Complete locally
   for Message/Mention/Participation/Context handler payloads.
4. Drop self-authored or duplicate events. Duplicate suppression is complete;
   self-authored webhook detection remains dependent on Zoho payload fields.
5. Enforce `dmPolicy`, `groupPolicy`, `allowFrom`, and mention gating. Complete.
6. Enforce scoped employee mode and action policy. Complete through the shared
   inbound security path.
7. Record the turn ledger state transition before dispatch. Complete in
   `cliq-channel-413`.
8. Build OpenClaw inbound session route. Next.
9. Dispatch to the configured agent through OpenClaw native reply pipeline.
   Next.
10. Apply status reaction / read ack around accepted processing. Complete in
    `cliq-channel-408`; dispatch-grade turn ledger ownership is complete in
    `cliq-channel-413`.

### Polling fallback path

1. Run `zoho cliq chats --unread-only --exclude-reacted-by-self`.
2. For each eligible chat, run `zoho cliq context`.
3. Normalize the newest target message into the same inbound event shape used by
   webhooks.
4. Reuse the same security, policy, dedupe, routing, status/read lifecycle, and
   turn-ledger loop prevention.

### Outbound path

1. Receive OpenClaw outbound delivery request.
2. Resolve direct/channel/thread target to Cliq `user_id`, `channel_id`, or
   `chat_id`.
3. Call `zoho cliq send` or `zoho cliq reply`.
4. Parse JSON stdout.
5. Return normalized OpenClaw delivery result.

### Observability and incident response

Production installs need operator-visible evidence without leaking private chat
content or secrets.

Required diagnostics:

- structured audit events for source deny, policy deny, approval required,
  dispatch accepted, dispatch failed, retry, dead-letter, and outbound delivery
- redacted diagnostic bundle command or script for support handoff
- safe correlation ids connecting webhook/polling event, turn ledger row, CLI
  invocation, and OpenClaw delivery result
- counters for accepted, skipped, refused, retried, failed, dead-lettered, and
  rate-limited events
- explicit operator runbook for stuck turns and dead-letter replay

Logs must redact secrets, token paths, webhook signatures, raw auth headers,
mail addresses where not needed, and message bodies unless an operator enables a
local debug mode outside normal Cliq chat.

### Privacy and retention

The channel should minimize what it stores:

- Keep raw Zoho webhook payloads out of durable state by default.
- Store normalized metadata and short redacted excerpts only when needed for
  debugging.
- Make attachment/media handling opt-in and capability-gated.
- Avoid indexing private channel history outside the OpenClaw memory policy.
- Document how to purge turn ledger and dead-letter state.
- Ensure live test fixtures do not commit real employee names, emails, message
  bodies, tokens, webhook secrets, or organization identifiers.

### Rate limits and backpressure

Zoho and OpenClaw runtime limits should be treated as first-class design inputs:

- Cap polling chats per pass and outbound sends per turn.
- Use bounded concurrency per account/network.
- Back off on Zoho 429/5xx and classify retryable vs terminal errors.
- Prefer status/read-ack degradation over repeated agent dispatch.
- Surface rate-limit blockers in channel status with the next retry time.

### Packaging and supply chain

- Keep third-party dependencies minimal and prefer pure TypeScript/JavaScript
  packages unless a native module is clearly justified.
- If publishing to npm, pin the installed artifact with
  `openclaw.install.expectedIntegrity` after release.
- Document any package-manager build-script allowlist if native modules ever
  become unavoidable.
- Include a release checklist that verifies the published artifact, manifest,
  package metadata, and docs all describe the same channel id and config root.

## Normalized inbound event

Internal plugin normalizers should produce a stable shape before handing work to
OpenClaw:

```json
{
  "channel": "cliq",
  "accountId": "default",
  "chatType": "direct",
  "peerId": "chat-or-user-id",
  "senderId": "zoho-user-id",
  "senderLabel": "Human Name",
  "messageId": "message-id",
  "threadId": "",
  "text": "message text",
  "mentioned": true,
  "timestamp": "2026-05-04T00:00:00Z",
  "raw": {}
}
```

## Development stack

### cliq-channel-400: Version and SDK contract

- Recheck latest OpenClaw plugin docs and npm version. Completed at
  `2026-05-04T21:39:33Z`.
- Choose `minHostVersion` and `compat.pluginApi`. Locked to `>=2026.5.3-1`.
- Capture compatibility notes for local older OpenClaw installs. The previous
  `2026.4.15` host is too old for install/inspect validation; the upgraded
  global host is `2026.5.3-1`.
- Record local/latest/beta host versions and decide whether beta API drift
  requires follow-up before release. Beta `2026.5.4-beta.1` does not change the
  skeleton dependency; recheck before v0.4 release.
- Acceptance: `docs/architecture/OPENCLAW_CLIQ_CHANNEL_SDK_CONTRACT.md`,
  this plan, Lane 3 guide, and tests agree.

### cliq-channel-401: Plugin skeleton

- Create package skeleton under `integrations/openclaw-channel-cliq/`. Complete.
- Add manifest, package metadata, setup entry, runtime entry. Complete with
  TypeScript source and compiled `dist/*.js` OpenClaw runtime entrypoints.
- Add lightweight configured-state/auth-presence modules, declared skills,
  channel config metadata, and QA runner descriptors when supported. Complete;
  richer config and QA runners are deferred to `cliq-channel-402` and later.
- Acceptance: package-local `openclaw@2026.5.3-1` install/inspect discovers
  plugin `zoho-cliq` and channel `cliq`; plugin doctor reports no issues.

### cliq-channel-402: Config, SecretRef, and setup

- Implement config schema and setup helper. Complete.
- Support env/SecretRef for Zoho account/config/token/webhook secret. Complete
  for `accountEmail`, `configPath`, `tokenPassword`, and `webhookSecret`;
  `tokenPassword` and `webhookSecret` are documented as SecretRef-only in the
  manifest schema.
- Reject plaintext setup token inputs. Complete for `token`, `accessToken`,
  `password`, `privateKey`, `secret`, `botToken`, and `appToken`.
- Acceptance: package-local `openclaw@2026.5.3-1` linked install, `plugins
  inspect zoho-cliq --json`, and `plugins doctor` remain green.

### cliq-channel-416: Human install and setup UX

- Implement OpenClaw setup/onboarding surfaces for install source, host
  compatibility, Zoho CLI detection, auth/scopes, network selection,
  webhook/polling choice, security defaults, employee scope, and test message.
  Complete for setup wizard status, env shortcut, text inputs, allowFrom, and
  disable behavior; employee scope state is now covered by `cliq-channel-403`,
  while the test message stays linked to later outbound slices.
- Normalize setup failures into actionable user-facing states. Complete for
  `host_too_old`, `zoho_missing`, `not_logged_in`, `missing_scope`,
  `network_missing`, `webhook_unverified`, and `allowlist_empty`.
- Add human install guide, troubleshooting table, uninstall/disable flow, and
  upgrade/integrity recovery guidance. Complete in
  `docs/releases/OPENCLAW_CLIQ_CHANNEL_SETUP.md`.
- Acceptance: a human operator can install, configure, disable, uninstall, and
  diagnose config/auth smoke from UI/setup surfaces and docs without reading
  source; controlled outbound smoke is now covered by `cliq-channel-405`, and
  inbound loop prevention is covered by `cliq-channel-413`, and native
  dispatch is covered by `cliq-channel-417`. Production readiness remains gated
  by observability/privacy hardening.

### cliq-channel-403: Security, pairing, and scoped employee mode

- Implement DM pairing, group allowlist, mention gating, and audit warnings.
  Complete for runtime policy helpers, native allowlist adapter metadata, and
  `createChatChannelPlugin` security warning/audit surfaces.
- Implement `employeeMode` and `workScopes` policy enforcement.
  Complete in `src/employee-policy.ts` for scoped employee defaults and denied
  chat-originated system actions.
- Block chat-originated debug, install, config-write, secret-read, shell/system,
  and policy-bypass requests by default.
  Complete before inbound dispatch integration; `cliq-channel-414/406` will
  wire these decisions into live inbound routes.
- Acceptance: unsafe open access emits warnings; allowlist denies unknown
  senders; out-of-scope employee requests are refused before agent dispatch.
  Complete in package runtime policy functions; live inbound fixture coverage
  remains in the inbound slices.

### cliq-channel-414: Native SDK policy seams

- Implement session grammar/conversation resolver for DM, channel, thread, and
  parent fallback routing. Complete in `src/session.ts` with account/network
  scoped peer ids and thread-aware outbound routes.
- Implement Cliq mention fact gathering and delegate final decisions to
  OpenClaw's shared inbound mention policy helper when available. Complete for
  explicit mentions, reply-to-bot, quoted-bot, bot-thread participation, and
  authorized command bypass boundaries.
- Expose approval capability for review-required actions instead of custom
  approval tools. Complete through `approvalCapability`.
- Keep runtime gateway methods out of reserved core admin namespaces. Complete;
  the plugin still declares no custom gateway methods.
- Acceptance: session, mention, command-bypass, and approval fixtures match the
  latest stable OpenClaw SDK behavior. Complete with runtime skeleton tests.

### cliq-channel-404: CLI adapter

- Implement `zoho-cli.ts` command runner with JSON stdout parsing. Complete via
  `runPluginCommandWithTimeout`.
- Classify known CLI errors and preserve stderr diagnostics safely. Complete for
  auth missing, scope missing, unsupported endpoint, invalid JSON, timeout,
  command-not-found, and generic command failure.
- Acceptance: fake `zoho` fixtures cover success, auth missing, scope missing,
  unsupported endpoint, invalid JSON, timeout, missing command, env injection,
  redaction, and message-id extraction. Complete with runtime skeleton tests.

### cliq-channel-405: Outbound delivery

- Implement direct/channel reply and send. Complete through
  `cliqOutboundAdapter` and `sendCliqText`.
- Implement text chunk behavior aligned with OpenClaw outbound limits. Complete
  via `chunkerMode: "markdown"` on the native outbound adapter.
- Acceptance: OpenClaw outbound calls map to expected CLI invocations. Complete
  with fake `zoho` coverage for `send`, `reply`, `thread-reply`, message-id
  extraction, and classified/redacted failure propagation.

### cliq-channel-406: Inbound polling fallback

- Implement polling watcher using `chats` and `context`. Complete via
  `listCliqChats`, `fetchCliqContext`, and `pollCliqInboundOnce`.
- Add dedupe state keyed by account/network/chat/message. Complete via
  `buildCliqInboundDedupeKey` and `CliqInboundDedupeStore`.
- Acceptance: polling fixture dispatches exactly one inbound event per message.
  Complete with fake `zoho` coverage for accepted, duplicate,
  mention-denied, and self-authored messages.

### cliq-channel-407: Webhook inbound

- Implement webhook route registration and payload verification. Complete with
  exact OpenClaw plugin HTTP routes such as `/webhooks/cliq` and
  `X-Cliq-Webhook-Secret` verification.
- Normalize bot message and participation handler payloads. Complete for
  Message, Mention, Participation, and Context handlers; Welcome, Incoming
  Webhook, Call, and Menu handlers are ignored until explicit workflows exist.
- Acceptance: webhook fixtures dispatch the same event shape as polling.
  Complete with fixture coverage for accepted mention/direct messages,
  duplicate suppression, mention-denied channel messages, unsupported handlers,
  and multi-account path/secret filtering.

### cliq-channel-408: Status/read lifecycle

- Integrate status reactions and mark-read fallback. Complete with
  `src/lifecycle.ts`, `src/zoho-cli.ts` helpers for `status-react` and
  `mark-read`, and shared wrapping for accepted webhook and polling events.
- Map lifecycle: `received`, `thinking`, `writing`, `testing`, `blocked`,
  `done`, `failed`. Complete for default `received -> thinking -> mark-read ->
  done`, with `failed` attempted on dispatch errors.
- Acceptance: success and failure paths leave visible Cliq status evidence.
  Complete with fake-runtime coverage for success, unsupported read-ack
  degradation, and dispatch failure.

### cliq-channel-413: Turn ledger and loop prevention

- Implement turn ledger state for webhook and polling events. Complete with
  `src/turn-ledger.ts`, exported turn helpers, webhook/polling turn metadata,
  and handler-scoped in-memory ledger state.
- Add one-active-turn-per-chat guard, bounded retries, burst coalescing,
  dead-letter diagnostics, and outbound idempotency keys where possible.
  Complete for inbound duplicate/active/dead-letter prevention and generated
  idempotency keys on turn entries; outbound transport idempotency remains
  dependent on host/CLI support.
- Acceptance: duplicate/self/retry fixtures never dispatch repeated agent work,
  and failed turns stop with actionable dead-letter evidence. Complete with
  runtime tests for active same-conversation coalescing, completed duplicate
  skips, dispatch failure dead-letter, and dead-letter replay blocking.

### cliq-channel-409: OpenClaw native UX

- Wire capabilities, status, setup, docs labels, and target resolution.
  Complete with `src/status.ts` status, capability, and routing diagnostic
  summaries plus setup wizard status lines for webhook, polling, lifecycle, and
  turn-ledger readiness.
- Ensure `openclaw channels list/status/capabilities` output is helpful.
  Complete for package-exported status/capability summaries that keep secrets
  and message bodies out of diagnostics while exposing setup blockers,
  controlled-smoke readiness, and the remaining production blocker.
- Acceptance: channel looks and behaves like a native OpenClaw channel.
  Complete for local/native surfaces with runtime tests covering status,
  capability, and route/session diagnostics; native dispatch is now covered by
  `cliq-channel-417`, and redacted observability/privacy diagnostics are
  covered by `cliq-channel-415`.

### cliq-channel-410: AI-facing docs and skill alignment

- Update README, Lane 3 guide, skill references, and CLI help guidance.
  Complete with the root skill, native channel skill, Lane 3 guide, development
  guide, setup runbook, README, and tests aligned on the diagnostic-first
  workflow.
- Add troubleshooting prompts for missing login/scopes/network/webhook secret.
  Complete with an AI troubleshooting ladder for `not_logged_in`,
  `missing_scope`, `network_missing`, `webhook_unverified`,
  `webhook_secret_missing`, `allowlist_empty`, `employee_scope_empty`,
  `target_unresolved`, native dispatch failure/dead-letter diagnostics,
  `live_verification_pending`, and repeated Zoho-side `not_supported` /
  `inactive_appaccount_user` blockers.
- Acceptance: an OpenClaw AI agent can install, diagnose, and use the channel
  from docs without reading source code. Complete for controlled smoke and
  diagnostics; docs explicitly forbid claiming production incident readiness
  until fake plus live verification passes.

### cliq-channel-417: Native agent turn dispatch

- Wire accepted webhook and polling events into OpenClaw's native agent turn
  dispatch surface instead of fixture-only optional callbacks.
- Preserve the existing security gates, lifecycle wrapper, turn ledger,
  dead-letter behavior, and native outbound reply routing.
- Acceptance: a trusted Bot webhook event and polling event can start exactly
  one OpenClaw agent turn and route the reply back through the Cliq outbound
  adapter, while duplicate/denied/dead-letter events fail closed.
- Status: complete in `src/native-dispatch.ts`; webhook registration now uses
  `createCliqNativeEventDispatcher`, and polling exposes the same
  `nativeDispatch` path for service/test callers.

### cliq-channel-415: Observability, privacy, and supply-chain hardening

- Add redacted audit events, correlation ids, diagnostic bundle/runbook, rate
  limit status, privacy retention rules, and dead-letter replay guidance.
- Add npm artifact integrity pinning to release flow when the package is
  published.
- Status: complete in `src/observability.ts` and `src/privacy.ts`; status and
  capability diagnostics now advertise the redacted observability bundle, rate
  limits, privacy retention rules, dead-letter replay guard, and release
  integrity placeholder. The active production blocker is now
  `live_verification_pending`.
- Acceptance: operators can diagnose production incidents without exposing
  secrets or raw chat bodies, and release artifacts fail closed on integrity
  mismatch.

### cliq-channel-411: Live verification and release gate

- Run fake fixtures, local OpenClaw integration, and live Cliq smoke tests.
- Record live blockers as capability-gated skips when external.
- Include latest stable, local older host, and current beta compatibility checks
  where practical.
- Acceptance: v0.4 release gate produces pass/skip/fail evidence.
- Status: complete with `ops/scripts/openclaw_cliq_live_smoke.sh`; local
  OpenClaw plugin/channel checks, Zoho auth/capability/polling probes, local
  webhook security gates, and native polling pass. Public Bot callback remains
  deployment-dependent on a reachable tunnel/gateway URL.

### cliq-channel-412: Compatibility maintenance

- Add a compatibility matrix for OpenClaw host/plugin API versions.
- Add a lightweight revalidation checklist for future OpenClaw updates.
- Acceptance: future SDK breakage has a documented repair path.
- Status: complete in `docs/releases/OPENCLAW_CLIQ_CHANNEL_COMPATIBILITY.md`;
  global `2026.5.3-1`, latest `2026.5.4`, and beta `2026.5.4-beta.3` pass
  Temp-HOME linked install/inspect/doctor checks while the v0.4 floor remains
  `>=2026.5.3-1`.

### cliq-channel-418: v0.4 RC packaging handoff

- Summarize included scope, green evidence, and remaining deployment blockers.
- Add final operator checklist for public Bot callback verification, package
  version decision, and npm artifact integrity handling.
- Acceptance: an operator or AI maintainer can decide whether to cut a local
  test RC, npm/GitHub RC, or defer production rollout without reading source.
- Status: complete in
  `docs/releases/OPENCLAW_CLIQ_CHANNEL_V0_4_RC_CHECKLIST.md`; local/operator RC
  package is ready, and production rollout remains gated on public Bot callback
  reachability.

## Test strategy

### Unit tests

- config schema accepts safe config and rejects unknown/risky keys
- SecretRef config stays opaque in logs
- normalizer handles webhook fixtures
- dedupe prevents repeated dispatch
- turn ledger prevents duplicate active turns and reaches dead-letter after
  bounded retries
- session grammar distinguishes account/network/chat/thread collisions
- mention fact gathering handles explicit mention, reply-to-bot, quoted-bot,
  service/system messages, and unauthorized command bypass
- `zoho-cli.ts` parses JSON stdout and classifies stderr errors
- outbound maps OpenClaw targets to CLI commands

### Integration tests

- fake `zoho` binary receives expected command arguments
- plugin inspect/doctor sees channel metadata
- `openclaw channels capabilities --channel cliq` reports expected actions
- webhook route fixture dispatches a native inbound event
- polling fallback produces the same normalized inbound shape
- short message bursts coalesce instead of spawning repeated agent turns
- approval-required outbound flows use OpenClaw native approval capability
- redacted diagnostic bundle links audit event, ledger state, CLI invocation, and
  delivery result without exposing secrets

### Security tests

- `groupPolicy=open` emits audit warning
- no allowlist denies group/channel messages
- DM pairing denies unknown sender until approved
- scoped employee mode allows in-scope business requests
- scoped employee mode blocks chat-originated debug, install, config-write,
  secret-read, shell/system, and policy-bypass requests
- admin override is unavailable by default and works only through the configured
  explicit operator/admin path when enabled
- prompt-injection text remains user content and cannot override host policy
- resolved secrets never appear in logs or errors
- self-authored bot messages are dropped
- webhook signature/header failures are denied before normalization
- raw message bodies and attachments are not persisted by default

### Live smoke tests

- `zoho cliq status --check-auth --network <network>`
- Cliq DM -> OpenClaw agent -> Cliq reply
- Cliq channel mention -> OpenClaw agent -> threaded/channel reply
- mark-read success or capability-gated reaction fallback
- missing scope produces actionable re-auth hint

## Documentation requirements

Every implementation slice that changes behavior must update:

- Lane 2: README and docs under `docs/*`
- Lane 3: `skill/*` and `integrations/openclaw/*`
- Lane 1: `ops/state/*` and daily memory when used

The channel package must include:

- user setup guide
- operator troubleshooting guide
- security guide
- AI-agent skill reference
- compatibility/revalidation guide for OpenClaw host updates
- human install/onboarding guide with setup-state copy
- uninstall/disable and upgrade/recovery guide

## Definition of done for v0.4

- Plugin installs as an OpenClaw channel.
- Human setup/onboarding flow covers install, auth, network, webhook/polling,
  security defaults, employee scope, test, disable, and recovery.
- Channel configuration supports safe SecretRef/env-based credentials.
- Inbound works through webhook or polling fallback.
- Outbound direct/channel reply works through `zoho` CLI.
- Pairing/allowlist/mention gating are enforced.
- Scoped employee mode blocks out-of-scope chat requests before dispatch.
- Session grammar, threading, and approval capability align with the current
  OpenClaw stable SDK.
- Turn ledger, dedupe, retry limits, and dead-letter handling prevent loops.
- Redacted observability, privacy retention, rate-limit, and incident-response
  guidance are in place.
- Published package metadata includes a verified integrity pin when released to
  npm.
- Status reaction and read-ack behavior are visible and auditable.
- OpenClaw channel status/capabilities output is useful.
- Lane 2/Lane 3 docs and ops state are aligned.
- CRM expansion remains queued for v0.5.

## External references

- OpenClaw Building Channel Plugins: https://docs.openclaw.ai/plugins/sdk-channel-plugins
- OpenClaw Plugin Manifest: https://docs.openclaw.ai/plugins/manifest
- OpenClaw Setup and Config: https://docs.openclaw.ai/plugins/sdk-setup
- OpenClaw Security: https://docs.openclaw.ai/gateway/security
- OpenClaw Secrets: https://docs.openclaw.ai/gateway/secrets
