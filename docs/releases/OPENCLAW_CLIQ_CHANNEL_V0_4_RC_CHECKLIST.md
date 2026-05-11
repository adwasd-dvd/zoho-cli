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

Updated: `2026-05-11T21:48:15Z`.

## Decision

Status: **RC package ready, public callback and trusted reply verified**.

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
| Focused channel/docs tests | `tests/test_auto_pilot_scripts.py -k openclaw_cliq`, `tests/test_openclaw_channel_contract.py`, `tests/test_lane3_docs.py`, and `tests/test_markdown_update.py` passed with `40 passed, 18 deselected in 2.91s`. |
| Full CI | `make ci` passed with ruff format/check clean and `1876 passed in 50.38s`. |
| Local live smoke | `ops/scripts/openclaw_cliq_live_smoke.sh` passed: Zoho auth/capability/polling OK, local webhook missing-secret/authenticated-non-dispatch/authenticated-deny OK, native polling OK with zero events. |
| Package linked baseline | Temp-HOME `openclaw plugins install ./integrations/openclaw-channel-cliq --link`, `plugins inspect zoho-cliq --json`, and `plugins doctor` passed on global `OpenClaw 2026.5.3-1`. |
| Latest stable host | Temp-HOME `npx -y openclaw@2026.5.4` linked install/inspect/doctor passed. |
| Beta early warning | Temp-HOME `npx -y openclaw@2026.5.4-beta.3` linked install/inspect/doctor passed. |
| Local package artifact preflight | `NPM_CONFIG_CACHE=/private/tmp/zoho-cli-npm-cache OPENCLAW_CLIQ_PACK_RUN_ID=20260511T214240Z-live-reply ops/scripts/openclaw_cliq_rc_pack.sh` passed at `2026-05-11T21:47:10Z`; the script reran typecheck/build and then packed from the plugin directory into `.tmp/openclaw-cliq-rc-pack`. Tarball `adwasd-openclaw-zoho-cliq-0.4.0-rc.1.tgz`, size `95394`, unpacked size `470591`, entry count `67`, shasum `7717aa539f3ccf8d1ee1be560283ea30fa6a87b6`, integrity `sha512-2gp4TAicx7Ax07jBI2HNl9WFlIrVaqMh082mLAN5NVxF3p3BL7AWEgQDJfs+TOzwU2zLiSNdEu79BEFNZGsNEw==`. Summary report path pattern: `tests/auto_pilot/reports/openclaw_cliq_rc_pack_summary_<run-id>.json`. |
| Public callback auth/reachability | Cloudflare Published application route `https://cliq.hpyio.com/webhooks/cliq` is reachable; `ops/scripts/openclaw_cliq_public_callback_smoke.sh` passed with `status=public_callback_verified`, missing-secret `401`, authenticated unsupported-handler `200`, and no stored webhook bodies, response bodies, or secrets. |
| Live route binding | `openclaw config validate` passes with `cliq/default -> zoho-employee-test`; both `main` and `zoho-employee-test` are configured for `openai-codex/gpt-5.3-codex`. |
| Native dispatch identity | Accepted webhook/polling turns set OpenClaw `Provider`/`Surface` to `cliq` so normal final answers deliver through the Cliq outbound adapter; handler source facts stay in supplemental context. |
| Trusted live Bot reply | A controlled trusted Cliq Bot Mention through `https://cliq.hpyio.com/webhooks/cliq` routed to `zoho-employee-test`, used `openai-codex/gpt-5.3-codex`, delivered exactly one Cliq reply (`deliveryCount=1`), and the redacted bundle/check run `20260511T214135Z-real-mention` reported `trusted_reply_recorded`. |
| Trusted reply evidence bundle | `ops/scripts/openclaw_cliq_trusted_reply_evidence_bundle.sh` auto-runs offline route preflight when no route report is supplied, hashes live raw ids when needed, prepares redacted `openclaw_cliq_trusted_reply_evidence` JSON, and runs `ops/scripts/openclaw_cliq_trusted_reply_evidence.sh`; the checker reports `trusted_reply_recorded` only when the route, callback, trusted Mention hash facts, agent/model, one-turn, one-reply, duplicate/dead-letter, and redaction facts all pass. `ZOHO_CLIQ_TRUSTED_REPLY_PLAN_ONLY=1` emits `openclaw_cliq_trusted_reply_evidence_bundle_plan` and writes a redacted plan report with `nextAction`, `readyForFinalBundle`, `missingFacts`, `readyFacts`, `reportFiles`, `reportsReady`, `collectionGuide`, `factPrepareCommand`, `acceptedFactSources`, and `redaction` so agents can verify the route, missing live facts, archived filenames, and the exact fact-collection boundary before asking for a fresh Bot Mention. The final bundle can read a hash-only `ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE` with `kind=openclaw_cliq_trusted_reply_facts`, or auto-run facts prepare from an id-only `ZOHO_CLIQ_TRUSTED_REPLY_RAW_FACTS_FILE` when no hash facts file is supplied; it rejects raw id fields in hash facts files with `facts_file_raw_ids_present`, body fields in raw facts files with `raw_facts_file_forbidden_body_present`, and secret markers. If route preflight fails with blockers such as `agent_binding_mismatch`, the bundle exits non-zero with route JSON only and does not create evidence/check reports. |
| Bot API outbound sanity | `zoho cliq post-to-bot oldsix --network happydistrouklimited --text <redacted smoke>` returned `status=ok` for bot `oldsix`; this is supplemental CLI-to-Bot API evidence and does not replace the trusted inbound Mention-to-agent evidence. |

## Trusted Reply Live Evidence

Trusted agent reply:

1. Keep the operator tunnel or provision a durable gateway URL.
2. Keep `ZOHO_CLIQ_PUBLIC_WEBHOOK_URL` pointed at that URL plus
   `/webhooks/cliq` when running the live smoke harness.
   For Cloudflare Zero Trust Tunnels, add a **Published application** route to
   the tunnel and forward it to `HTTP` service `127.0.0.1:18789`; do not use
   Private hostname, Private CIDR, or Workers VPC for the public Zoho Bot
   callback. A Cloudflare tunnel with zero routes is not ready for Zoho.
   For an ingress-only check before asking Zoho to call the Bot, run:

   ```bash
   ZOHO_CLIQ_PUBLIC_WEBHOOK_URL=https://<your-tunnel-or-gateway>/webhooks/cliq \
   ZOHO_CLIQ_PUBLIC_CALLBACK_REPORT_FILE=tests/auto_pilot/reports/openclaw_cliq_public_callback.json \
     ops/scripts/openclaw_cliq_public_callback_smoke.sh
   ```

   The report kind is `openclaw_cliq_public_callback_smoke`; success is
   `public_callback_verified`. The script rejects placeholder URLs with
   `public_webhook_url_placeholder`, requires HTTPS by default with
   `public_webhook_url_requires_https`, expects missing-secret `401` and
   authenticated unsupported-handler `200`, and stores no webhook bodies,
   response bodies, or secrets.
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

6. Before sending the mention, run the one-shot bundle in plan-only mode to
   confirm the route and list the remaining live delivery facts without writing
   trusted reply evidence:

   ```bash
   ZOHO_CLIQ_TRUSTED_REPLY_PLAN_ONLY=1 \
   ZOHO_CLIQ_TRUSTED_REPLY_REPORT_DIR=tests/auto_pilot/reports \
   ZOHO_CLIQ_EXPECTED_AGENT_ID=zoho-employee-test \
   ZOHO_CLIQ_EXPECTED_AGENT_MODEL=openai-codex/gpt-5.3-codex \
     ops/scripts/openclaw_cliq_trusted_reply_evidence_bundle.sh
   ```

   The JSON should have
   `kind=openclaw_cliq_trusted_reply_evidence_bundle_plan`. A status of
   `awaiting_live_delivery_facts` is expected before the real Bot turn. Archive
   `ZOHO_CLIQ_TRUSTED_REPLY_PLAN_FILE` or the default
   `openclaw_cliq_trusted_reply_plan_<run-id>.json` from the report directory,
   and use `nextAction` / `readyForFinalBundle` plus `missingFacts` /
   `readyFacts` as the machine-readable checklist. Use `reportFiles` /
   `reportsReady` to confirm the route and plan report filenames; the plan
   should not include local config paths, raw ids, hash values, or secrets, and
   its `redaction` booleans must all be false. Use `collectionGuide` to enforce
   `sendExactlyOneTrustedMention`, collect only `trustedSenderId`,
   `trustedMessageId`, and `deliveryId`, and keep `rawWebhookPayload`,
   `rawMessageBody`, `rawCliqReplyBody`, and `secrets` out of evidence. Use
   `factPrepareCommand` plus `collectionGuide.factsFileKind`,
   `collectionGuide.factsPrepareReadyStatus`,
   `collectionGuide.rawFactsPrepareEnv`, and
   `collectionGuide.rawFactsFileKind` to create the hash-only facts handoff
   before the final bundle.
   Latest operator route state: the public callback is verified at
   `https://cliq.hpyio.com/webhooks/cliq`; after rebuilding/restarting with the
   `Provider`/`Surface=cliq` dispatch identity fix, a fresh controlled Mention
   routed to `zoho-employee-test`, delivered exactly one Cliq reply
   (`deliveryCount=1`), and the final bundle run
   `20260511T214135Z-real-mention` reported `trusted_reply_recorded`.
7. Send a controlled trusted mention from Cliq and verify exactly one native
   OpenClaw turn routes to `zoho-employee-test`, uses a Codex model, and emits
   exactly one Cliq reply.
8. Record only redacted evidence and validate it. Prefer the one-shot bundle;
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

   To use a hash-only local facts JSON instead of three separate hash env vars,
   set `ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE` to a file containing
   `kind=openclaw_cliq_trusted_reply_facts`, `trustedSenderIdHash`,
   `trustedMessageIdHash`, and `deliveryIdHash` as `sha256:` references only.
   Do not include raw `trustedSenderId`, `trustedMessageId`, or `deliveryId`
   fields; the bundle rejects raw facts files with `facts_file_raw_ids_present`
   and secret markers with `facts_file_secret_marker_present`.
   `ops/scripts/openclaw_cliq_trusted_reply_facts_prepare.sh` can create this
   hash-only facts file from the three raw live facts supplied as env vars or
   from an untracked local `openclaw_cliq_trusted_reply_raw_facts` JSON file
   passed via `ZOHO_CLIQ_TRUSTED_REPLY_RAW_FACTS_FILE`; it reports
   `openclaw_cliq_trusted_reply_facts_prepare` with `status=facts_file_ready`
   and writes only `sha256:` references to
   `openclaw_cliq_trusted_reply_facts` JSON. The raw-facts file must contain
   only ids, not raw webhook payloads, message/reply bodies, or secrets; body
   fields are rejected with `raw_facts_file_forbidden_body_present`;
   placeholder ids such as `<trusted_cliq_user_id>` or `replace-me` are rejected
   with `trusted_sender_raw_placeholder`, `trusted_message_raw_placeholder`, or
   `delivery_id_raw_placeholder`. The final bundle can take
   `ZOHO_CLIQ_TRUSTED_REPLY_RAW_FACTS_FILE` directly and auto-run that prepare
   step when no `ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE` is set, leaving stdout as
   the final checker JSON.

   To use an already-reviewed route report, set `ZOHO_CLIQ_ROUTE_REPORT_FILE`.
   If it is omitted, the bundle runs `ZOHO_CLIQ_ROUTE_BINDING_ONLY=1` internally
   and writes `openclaw_cliq_route_preflight_<run-id>.json` under the report
   directory. If this route preflight fails, keep only the route JSON, fix the
   OpenClaw binding, and rerun before collecting trusted reply evidence.

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
7. Publish release notes that explicitly list trusted agent reply evidence as
   completed for the operator Cloudflare route; durable production
   tunnel/gateway selection remains an operations decision.

## Non-goals

- Do not block the RC package on unsupported Zoho endpoints already classified
  as deferred external constraints.
- Do not add parallel `cliq_send` or custom approval tools; use OpenClaw native
  message and approval surfaces.
- Do not store OAuth tokens, webhook secrets, raw webhook payloads, or raw Cliq
  message bodies in release evidence.
