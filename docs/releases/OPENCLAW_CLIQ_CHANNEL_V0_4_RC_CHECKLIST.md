# OpenClaw Cliq channel v0.4 RC checklist

This checklist is the `cliq-channel-418` handoff for deciding whether the
native OpenClaw Zoho Cliq channel package can be cut as a v0.4 release
candidate. `cliq-channel-419` codifies the local package artifact preflight
used by this checklist. `cliq-channel-420` adds real Zoho Bot handler templates
for the remaining public callback gate, `cliq-channel-421` verifies those
accepted handler families against native webhook processing, and
`cliq-channel-422` promotes the source-controlled package metadata to
`0.4.0-rc.1`.

SDK contract source of truth:
`docs/architecture/OPENCLAW_CLIQ_CHANNEL_SDK_CONTRACT.md`.

Updated: `2026-05-05T22:10:51Z`.

## Decision

Status: **RC package ready, public callback verified, agent reply pending**.

The native channel code, package metadata, fake/runtime tests, local gateway
webhook checks, Zoho auth/capability/polling smoke, and OpenClaw host
compatibility checks are green. A reachable public callback has been verified
with an operator Cloudflare tunnel and a Zoho Cliq Bot handler POSTing to
`/webhooks/cliq` with `X-Cliq-Webhook-Secret`.

Do not claim production incident readiness until one controlled trusted Bot
Mention proves `cliq/default` routes to the intended Codex-backed agent and
delivers exactly one Cliq reply. The live environment currently binds
`cliq/default` to `zoho-employee-test`.

## Included scope

- Installable package: `integrations/openclaw-channel-cliq/`
- Package: `@adwasd/openclaw-zoho-cliq`
- Plugin id: `zoho-cliq`
- Channel id: `cliq`
- Host floor: OpenClaw `>=2026.5.3-1`
- Package version: `0.4.0-rc.1`
- Implemented slices:
  `cliq-channel-401/402/416/403/414/404/405/406/407/408/413/409/410/417/415/411/412/418/419/420/421/422`

## Evidence

| Gate | Latest result |
| --- | --- |
| TypeScript typecheck/build | `npm --prefix integrations/openclaw-channel-cliq run typecheck` and `run build` passed. |
| Focused channel/docs tests | `tests/test_openclaw_channel_contract.py`, `tests/test_lane3_docs.py`, and `tests/test_markdown_update.py` passed with `16 passed`. |
| Full CI | `make ci` passed with ruff format/check clean and `1841 passed in 48.64s`. |
| Local live smoke | `ops/scripts/openclaw_cliq_live_smoke.sh` passed: Zoho auth/capability/polling OK, local webhook missing-secret/authenticated-non-dispatch/authenticated-deny OK, native polling OK with zero events. |
| Package linked baseline | Temp-HOME `openclaw plugins install ./integrations/openclaw-channel-cliq --link`, `plugins inspect zoho-cliq --json`, and `plugins doctor` passed on global `OpenClaw 2026.5.3-1`. |
| Latest stable host | Temp-HOME `npx -y openclaw@2026.5.4` linked install/inspect/doctor passed. |
| Beta early warning | Temp-HOME `npx -y openclaw@2026.5.4-beta.3` linked install/inspect/doctor passed. |
| Local package artifact preflight | `NPM_CONFIG_CACHE=/private/tmp/zoho-cli-npm-cache OPENCLAW_CLIQ_PACK_RUN_ID=20260505T142129Z-rc1 ops/scripts/openclaw_cliq_rc_pack.sh` passed at `2026-05-05T14:22:51Z`; the script reran typecheck/build and then packed from the plugin directory into `.tmp/openclaw-cliq-rc-pack`. Tarball `adwasd-openclaw-zoho-cliq-0.4.0-rc.1.tgz`, size `93879`, unpacked size `466025`, entry count `67`, shasum `87b553ad5bbec1c920a05b342630a57cea58b96b`, integrity `sha512-PVaBZFB0+m2sll7dl+c47iPnb6+KgRcCNkiqvFJzv8qtuHB8Lb153/27rqC1izmmybGP1CtrqMH4ZVrBkvBgBg==`. Summary report path pattern: `tests/auto_pilot/reports/openclaw_cliq_rc_pack_summary_<run-id>.json`. |
| Public callback auth/reachability | Operator Cloudflare tunnel to local OpenClaw gateway is reachable; missing-secret webhook calls return `401`, authenticated unsupported-handler calls return `200` with `unsupported_handler`, and the Zoho Cliq Bot Mention Handler has reached local OpenClaw. |
| Live route binding | `openclaw config validate` passes with `cliq/default -> zoho-employee-test`; both `main` and `zoho-employee-test` are configured for `openai-codex/gpt-5.3-codex`. |
| Trusted reply evidence bundle | `ops/scripts/openclaw_cliq_trusted_reply_evidence_bundle.sh` auto-runs offline route preflight when no route report is supplied, hashes live raw ids when needed, prepares redacted `openclaw_cliq_trusted_reply_evidence` JSON, and runs `ops/scripts/openclaw_cliq_trusted_reply_evidence.sh`; the checker reports `trusted_reply_recorded` only when the route, callback, trusted Mention hash facts, agent/model, one-turn, one-reply, duplicate/dead-letter, and redaction facts all pass. |

## Remaining deployment gate

Trusted agent reply:

1. Keep the operator tunnel or provision a durable gateway URL.
2. Keep `ZOHO_CLIQ_PUBLIC_WEBHOOK_URL` pointed at that URL plus
   `/webhooks/cliq` when running the live smoke harness.
3. Keep the Zoho Cliq Bot Message, Mention, Participation, or Context Handler
   posting to the same URL using
   `docs/releases/OPENCLAW_CLIQ_BOT_HANDLER_TEMPLATES.md`.
4. Rotate any webhook secret that appeared in screenshots, chat, logs, or docs
   before production use.
5. Run the offline route preflight, then run the full
   `ops/scripts/openclaw_cliq_live_smoke.sh` with the same expected-agent
   values for the current operator environment. Route-only mode requires
   `ZOHO_CLIQ_EXPECTED_AGENT_ID` and exits non-zero if it is omitted:

   ```bash
   ZOHO_CLIQ_ROUTE_BINDING_ONLY=1 \
   ZOHO_CLIQ_ROUTE_REPORT_FILE=tests/auto_pilot/reports/openclaw_cliq_route_preflight.json \
   ZOHO_CLIQ_EXPECTED_AGENT_ID=zoho-employee-test \
   ZOHO_CLIQ_EXPECTED_AGENT_MODEL=openai-codex/gpt-5.3-codex \
     ops/scripts/openclaw_cliq_live_smoke.sh
   ```

6. Send a controlled trusted mention from Cliq and verify exactly one native
   OpenClaw turn routes to `zoho-employee-test`, uses a Codex model, and emits
   exactly one Cliq reply.
7. Record only redacted evidence and validate it. Prefer the one-shot bundle;
   it hashes raw ids locally when `ZOHO_CLIQ_TRUSTED_SENDER_ID`,
   `ZOHO_CLIQ_TRUSTED_MESSAGE_ID`, and `ZOHO_CLIQ_DELIVERY_ID` are supplied,
   writes the evidence/check reports, and leaves stdout as the final checker
   JSON:

   ```bash
   ZOHO_CLIQ_TRUSTED_REPLY_REPORT_DIR=tests/auto_pilot/reports \
   ZOHO_CLIQ_TRUSTED_REPLY_EVIDENCE_FILE=tests/auto_pilot/reports/openclaw_cliq_trusted_reply.json \
   ZOHO_CLIQ_TRUSTED_REPLY_REPORT_FILE=tests/auto_pilot/reports/openclaw_cliq_trusted_reply_check.json \
   ZOHO_CLIQ_TRUSTED_SENDER_ID="$TRUSTED_SENDER_ID" \
   ZOHO_CLIQ_TRUSTED_MESSAGE_ID="$TRUSTED_MESSAGE_ID" \
   ZOHO_CLIQ_DELIVERY_ID="$DELIVERY_ID" \
   ZOHO_CLIQ_EXPECTED_AGENT_ID=zoho-employee-test \
   ZOHO_CLIQ_EXPECTED_AGENT_MODEL=openai-codex/gpt-5.3-codex \
     ops/scripts/openclaw_cliq_trusted_reply_evidence_bundle.sh
   ```

   To use an already-reviewed route report, set `ZOHO_CLIQ_ROUTE_REPORT_FILE`.
   If it is omitted, the bundle runs `ZOHO_CLIQ_ROUTE_BINDING_ONLY=1` internally
   and writes `openclaw_cliq_route_preflight_<run-id>.json` under the report
   directory.

   If raw ids must be transformed separately, hash them first with
   `ops/scripts/openclaw_cliq_hash_ref.sh` and pass the resulting
   `ZOHO_CLIQ_TRUSTED_SENDER_ID_HASH`,
   `ZOHO_CLIQ_TRUSTED_MESSAGE_ID_HASH`, and `ZOHO_CLIQ_DELIVERY_ID_HASH`
   instead of raw-id variables. The evidence must include
   `trustedMention.handler=mention`,
   `trustedMention.trustedSenderIdHash`, `trustedMention.messageIdHash`, and
   `delivery.deliveryIdHash` as `sha256:` references only. The check must report
   `status=trusted_reply_recorded`. It fails with stable blockers such as
   `trusted_mention_handler_invalid`, `trusted_sender_hash_missing`,
   `trusted_message_hash_missing`, `delivery_id_hash_missing`,
   `agent_turn_count_not_one`, `cliq_reply_count_not_one`, `agent_mismatch`,
   `route_preflight_not_ok`, or `secret_marker_present`.

If Zoho returns `token_refresh_rate_limited`, record `skip_deferred`, wait for
cooldown, and rerun without bursty refresh loops.

## RC cut steps

1. Confirm `git status --short` is clean.
2. Re-run `ops/scripts/openclaw_cliq_rc_pack.sh`, focused channel/docs tests,
   and `make ci`.
3. Re-run `docs/releases/OPENCLAW_CLIQ_CHANNEL_COMPATIBILITY.md` latest/beta
   checks if OpenClaw published a newer stable or beta after this checklist.
4. Package metadata is already set to `0.4.0-rc.1` for the source-controlled
   RC artifact; do not bump again unless cutting a newer RC.
5. Before npm promotion, fill `openclaw.install.expectedIntegrity` with the
   published artifact integrity and update `docs/releases/CHANGELOG.next.md`.
6. Install the published artifact in a Temp-HOME OpenClaw profile and rerun
   `plugins inspect`, `plugins doctor`, `channels status`, and `channels
   capabilities`.
7. Publish release notes that explicitly list the public Bot callback gate as
   deployment-dependent when it has not been completed.

## Non-goals

- Do not block the RC package on unsupported Zoho endpoints already classified
  as deferred external constraints.
- Do not add parallel `cliq_send` or custom approval tools; use OpenClaw native
  message and approval surfaces.
- Do not store OAuth tokens, webhook secrets, raw webhook payloads, or raw Cliq
  message bodies in release evidence.
