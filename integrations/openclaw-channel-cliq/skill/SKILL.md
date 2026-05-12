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
- Before editing a real Zoho Bot, use the Deluge templates in
  `docs/releases/OPENCLAW_CLIQ_BOT_HANDLER_TEMPLATES.md` and replace only the
  public webhook URL plus rotated secret placeholders.
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
- Native dispatch should keep OpenClaw `Provider`/`Surface` as `cliq`; carry
  webhook/polling handler source in supplemental context so final replies stay
  on the Cliq outbound adapter.
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
  production rollout blocked until the target environment has public Bot
  callback reachability and one controlled trusted agent reply verified with
  `ops/scripts/openclaw_cliq_trusted_reply_evidence_bundle.sh`. The current
  operator Cloudflare route has `trusted_reply_recorded` evidence for the
  `zoho-employee-test` Codex agent.
- To verify public Bot callback reachability without binding to a specific
  tunnel provider, set `ZOHO_CLIQ_PUBLIC_WEBHOOK_URL` and run
  `ops/scripts/openclaw_cliq_public_callback_smoke.sh`; require
  `openclaw_cliq_public_callback_smoke` with `public_callback_verified`, and
  keep webhook bodies, response bodies, and secrets out of reports.
  For Cloudflare Zero Trust Tunnels, publish the route as a Published
  application to `HTTP` service `127.0.0.1:18789`; zero routes means ingress is
  not ready yet.
- Before cutting a local/operator or npm/GitHub RC artifact, run
  `ops/scripts/openclaw_cliq_rc_pack.sh`; it must not publish or mutate
  package version metadata at pack time. The current RC package metadata is
  `0.4.0-rc.1`.
- After packing and before asking for promotion, run
  `ops/scripts/openclaw_cliq_rc_artifact_check.sh`; require
  `artifact_verified`, matching tarball shasum, package/channel/manifest
  identity, required `dist/`, `README.md`, and `skill/SKILL.md` entries, and
  no publish/tag/version-bump posture.
- Before operator publish handoff, run
  `ops/scripts/openclaw_cliq_rc_install_smoke.sh`; require
  `install_smoke_passed` after Temp-HOME `plugins install`,
  `plugins inspect zoho-cliq --json`, and `plugins doctor` against the local RC
  tarball.
- Before asking an operator to publish/promote, run
  `ops/scripts/openclaw_cliq_rc_promotion_check.sh`; require
  `ready_for_operator_publish`, `expectedIntegrityState=placeholder`,
  `artifact_verified`, `install_smoke_passed`, no pack/install publish/version
  bump, and `trusted_reply_recorded`. Do not fill
  `openclaw.install.expectedIntegrity` until the operator approves the actual
  publish source and the published artifact integrity is known.
- For the final operator review packet, run
  `ops/scripts/openclaw_cliq_rc_operator_publish_bundle.sh`; require
  `operator_publish_bundle_ready`. It gathers pack, artifact, install smoke,
  promotion, and trusted reply report filenames plus artifact shasum/integrity
  while keeping agent publish/tag/integrity-fill permissions false.
- For the release-note handoff, run
  `ops/scripts/openclaw_cliq_rc_release_notes_draft.sh`; it must say no
  npm publish, git tag, GitHub release, version bump, or
  `openclaw.install.expectedIntegrity` fill was performed, and it must fail if
  the operator bundle is missing/not ready or any agent publish/tag/integrity
  permission is true.
- For the final publish-path handoff, run
  `ops/scripts/openclaw_cliq_rc_publish_plan.sh`; require
  `operator_publish_plan_ready`, `agentMayExecutePlan=false`, and
  operator-only local/operator, npm RC, or GitHub artifact choices. Treat
  `release_notes_draft_unsafe` as a stop-before-publish signal.
- For the final packet index, run
  `ops/scripts/openclaw_cliq_rc_operator_handoff_manifest.sh`; require
  `operator_handoff_manifest_ready`, no blockers, `operator_publish_plan_ready`,
  `trusted_reply_recorded`, and false agent publish/tag/release/integrity
  permissions before asking the operator to choose a publish path.
- For the operator approval boundary and release action handoff, use
  `docs/releases/OPENCLAW_CLIQ_CHANNEL_V0_4_OPERATOR_PUBLISH_HANDOFF.md`.
  It defines the no-agent `npm publish`/tag/GitHub release boundary, the
  preflight commands, local/operator vs npm vs GitHub artifact choices,
  post-publish checks, and abort conditions.

## Required local readiness

```bash
openclaw plugins inspect zoho-cliq --json
openclaw channels status --channel cliq --deep
openclaw channels capabilities --channel cliq
zoho cliq status --check-auth --network <network>
zoho cliq capabilities --network <network>
ops/scripts/openclaw_cliq_live_smoke.sh
ops/scripts/openclaw_cliq_public_callback_smoke.sh
ops/scripts/openclaw_cliq_hash_ref.sh
ops/scripts/openclaw_cliq_rc_artifact_check.sh
ops/scripts/openclaw_cliq_rc_install_smoke.sh
ops/scripts/openclaw_cliq_rc_pack.sh
ops/scripts/openclaw_cliq_rc_promotion_check.sh
ops/scripts/openclaw_cliq_rc_operator_publish_bundle.sh
ops/scripts/openclaw_cliq_rc_release_notes_draft.sh
ops/scripts/openclaw_cliq_rc_publish_plan.sh
ops/scripts/openclaw_cliq_rc_operator_handoff_manifest.sh
ops/scripts/openclaw_cliq_trusted_reply_evidence_bundle.sh
ops/scripts/openclaw_cliq_trusted_reply_evidence_prepare.sh
ops/scripts/openclaw_cliq_trusted_reply_evidence.sh
```

For rollout smoke that must target a specific agent, set
`ZOHO_CLIQ_EXPECTED_AGENT_ID` and optionally
`ZOHO_CLIQ_EXPECTED_AGENT_MODEL` before running
`ops/scripts/openclaw_cliq_live_smoke.sh`. Use
`ZOHO_CLIQ_ROUTE_BINDING_ONLY=1` plus `OPENCLAW_CONFIG_PATH` for offline route
preflight without Zoho, gateway, or webhook calls. Set
`ZOHO_CLIQ_ROUTE_REPORT_FILE` to persist the single route result JSON for RC
evidence. The route evidence is schema-versioned, includes `runId` and
`checkedAt`, and omits local config paths. Route preflight failures emit JSON
with `status=error` and stable error codes such as
`expected_agent_missing` or `agent_binding_mismatch`, so parse that before
asking the operator to send a fresh Bot message.

For the final trusted reply gate, set
`ZOHO_CLIQ_TRUSTED_REPLY_EVIDENCE_FILE` to a redacted
`openclaw_cliq_trusted_reply_evidence` JSON artifact and run
`ops/scripts/openclaw_cliq_trusted_reply_evidence.sh`; require
`trusted_reply_recorded` before claiming production readiness. Evidence must
store sender/message/reply ids as `sha256:` references, not raw ids or bodies.
Use `ops/scripts/openclaw_cliq_trusted_reply_evidence_bundle.sh` with
expected agent/model and either raw ids or the three `sha256:` references to
route-preflight, hash, prepare, and check the artifact. Set
`ZOHO_CLIQ_ROUTE_REPORT_FILE` only when reusing an already-reviewed route
report; otherwise the bundle writes one under its report directory. If route
preflight fails with blockers such as `agent_binding_mismatch`, the bundle
emits route JSON only and does not create trusted reply evidence/check reports.
Before requesting a fresh trusted Bot Mention, run the bundle with
`ZOHO_CLIQ_TRUSTED_REPLY_PLAN_ONLY=1`; expect
`openclaw_cliq_trusted_reply_evidence_bundle_plan`, and treat
`awaiting_live_delivery_facts` as the checklist state before collecting live
sender/message/reply facts. The bundle writes this plan to
`ZOHO_CLIQ_TRUSTED_REPLY_PLAN_FILE` or the default
`openclaw_cliq_trusted_reply_plan_<run-id>.json` report path. Use
`nextAction`, `readyForFinalBundle`, `missingFacts`, and `readyFacts` as the
machine-readable checklist, and `reportFiles` / `reportsReady` for report
handoff without relying on absolute local paths. Require the plan `redaction`
object to keep raw ids, hash values, local paths, and secrets out of reports.
Use
`ops/scripts/openclaw_cliq_hash_ref.sh` only when hashing live raw ids as a
separate step; do not paste raw ids into evidence files.

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
ignored until a later slice assigns explicit OpenClaw workflows. After saving a
handler, verify redacted audit logs show `nativeDispatch.agentId` matching the
intended OpenClaw route binding and exactly one outbound Cliq reply for the
trusted smoke message.
