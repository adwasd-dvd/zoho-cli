# OpenClaw Cliq channel v0.4 RC checklist

This checklist is the `cliq-channel-418` handoff for deciding whether the
native OpenClaw Zoho Cliq channel package can be cut as a v0.4 release
candidate. `cliq-channel-419` codifies the local package artifact preflight
used by this checklist. `cliq-channel-420` adds real Zoho Bot handler templates
for the remaining public callback gate, `cliq-channel-421` verifies those
accepted handler families against native webhook processing, and
`cliq-channel-422` promotes the source-controlled package metadata to
`0.4.0-rc.1`.
`cliq-channel-453` adds a no-publish promotion preflight, and
`cliq-channel-454` adds the operator publish handoff. `cliq-channel-455` adds
the local RC artifact check. `cliq-channel-456` adds Temp-HOME OpenClaw install
smoke for the RC tarball. `cliq-channel-457` tightens the promotion preflight,
`cliq-channel-458` adds the operator publish review bundle,
`cliq-channel-459` adds the release-notes draft generator,
`cliq-channel-460` adds the read-only operator publish plan, and
`cliq-channel-461` adds the read-only operator handoff manifest.
`cliq-channel-462` hardens direct Bot Message Handler payload parsing,
`cliq-channel-463` refreshes the post-hardening no-publish RC evidence,
`cliq-channel-464` adds the source drift guard as the no-repack check for later
non-package commits, and `cliq-channel-465` adds the read-only selected
publish-path review. `cliq-channel-466` fixes direct Bot reply fallback for
synthetic direct message ids and refreshes the no-publish RC handoff baseline.
`cliq-channel-467` syncs the operator publish baseline to that latest
artifact, `cliq-channel-468` adds a read-only operator decision packet,
`cliq-channel-469` syncs package-local docs with that packet, and
`cliq-channel-470` refreshes the no-publish RC artifact and operator handoff
after the package docs sync. `cliq-channel-471` adds a read-only live ingress
diagnostic for Bot handler no-response triage, and `cliq-channel-472` adds the
combined no-response packet that turns public callback plus ingress evidence
into one next action. `cliq-channel-473` adds a redacted handler trigger packet
for Zoho Bot handler paste/check triage, and `cliq-channel-474` embeds that
handler trigger packet into the no-response wrapper when `no_recent_webhook_ingress`
is the active blocker. `cliq-channel-475` syncs the root README, RC checklist,
Lane 3 skill index, and contract markers with that operator handoff.
`cliq-channel-476` records the post-doc-sync source drift and decision packet
so operator publish review can see that later HEAD changes are docs/state only
and the package source remains unchanged. `cliq-channel-477` records the
post-CRM selector metadata source drift and decision packet after the pushed
CRM docs/state slice; the package source still remains unchanged.
`cliq-channel-478` records the post-CRM command-preview source drift and
decision packet after the pushed operator packet slice; the package source
still remains unchanged.
`cliq-channel-479` records the post-CRM report-metadata source drift and
decision packet after the pushed operator packet metadata slice; the package
source still remains unchanged.
`cliq-channel-480` records the post-CRM readiness-report-metadata source drift
and decision packet after the pushed readiness bundle metadata slice; the
package source still remains unchanged.
`cliq-channel-481` adds basename-only `reportFiles` and `reportsReady` metadata
to the final operator decision packet so AI operators can hand off publish-plan,
source-drift, selection-review, bundle, notes, and manifest reports without
logging local paths.
`cliq-channel-482` records a read-only `local_operator_rc` selected-path
decision packet that reports `operator_publish_selection_ready` while still
keeping agent execution disabled.
`cliq-channel-483` records the same read-only selected-path readiness for
`npm_rc_publish` and `github_release_artifact`, with command previews present
but still non-executable by agents.
`cliq-channel-484` records post-selected-path docs/state source-drift and
decision-packet evidence after the pushed selected-path slice; the package
source remains unchanged and the packet still awaits an operator path.
`cliq-channel-485` records post-CRM live-approval-fact-categories source-drift
and decision-packet evidence after the pushed CRM operator packet/readiness
bundle slice; the package source remains unchanged and the packet still awaits
an operator path.

SDK contract source of truth:
`docs/architecture/OPENCLAW_CLIQ_CHANNEL_SDK_CONTRACT.md`.

Updated: `2026-05-12T12:18:44Z`.

## Decision

Status: **RC package ready, public callback and trusted reply verified**.

The native channel code, package metadata, fake/runtime tests, local gateway
webhook checks, Zoho auth/capability/polling smoke, and OpenClaw host
compatibility checks are green. A reachable public callback has been verified
with an operator Cloudflare tunnel and a Zoho Cliq Bot handler POSTing to
`/webhooks/cliq` with `X-Cliq-Webhook-Secret`.

One controlled trusted Bot Mention has proven `cliq/default` routes to the
intended Codex-backed agent and delivers exactly one Cliq reply. Durable
production tunnel/gateway selection remains an operations decision. The live
environment currently binds `cliq/default` to `zoho-employee-test`.

## Included scope

- Installable package: `integrations/openclaw-channel-cliq/`
- Package: `@adwasd/openclaw-zoho-cliq`
- Plugin id: `zoho-cliq`
- Channel id: `cliq`
- Host floor: OpenClaw `>=2026.5.3-1`
- Package version: `0.4.0-rc.1`
- Implemented slices:
  `cliq-channel-401/402/416/403/414/404/405/406/407/408/413/409/410/417/415/411/412/418/419/420/421/422/453/454/455/456/457/458/459/460/461/462/463/464/465/466/467/468/469/470/471/472/473/474/475/476/477/478/479/480/481/482/483/484`

## Evidence

| Gate | Latest result |
| --- | --- |
| TypeScript typecheck/build | `npm --prefix integrations/openclaw-channel-cliq run typecheck` and `run build` passed. |
| Focused channel/docs tests | `tests/test_auto_pilot_scripts.py -k openclaw_cliq`, `tests/test_openclaw_channel_contract.py`, `tests/test_lane3_docs.py`, and `tests/test_markdown_update.py` passed with `40 passed, 18 deselected in 2.91s`. |
| Full CI | `make ci` passed with ruff format/check clean and `1901 passed in 53.30s` after the direct Bot reply fallback fix. |
| Local live smoke | `ops/scripts/openclaw_cliq_live_smoke.sh` passed: Zoho auth/capability/polling OK, local webhook missing-secret/authenticated-non-dispatch/authenticated-deny OK, native polling OK with zero events. |
| Package linked baseline | Temp-HOME `openclaw plugins install ./integrations/openclaw-channel-cliq --link`, `plugins inspect zoho-cliq --json`, and `plugins doctor` passed on global `OpenClaw 2026.5.3-1`. |
| Latest stable host | Temp-HOME `npx -y openclaw@2026.5.4` linked install/inspect/doctor passed. |
| Beta early warning | Temp-HOME `npx -y openclaw@2026.5.4-beta.3` linked install/inspect/doctor passed. |
| Local package artifact preflight | `NPM_CONFIG_CACHE=/private/tmp/zoho-cli-npm-cache OPENCLAW_CLIQ_PACK_RUN_ID=20260512T055900Z-ingress-diagnostic-rc-restore ops/scripts/openclaw_cliq_rc_pack.sh` passed after the live-ingress diagnostic docs were kept outside the package; the script reran typecheck/build and then packed from the plugin directory into `.tmp/openclaw-cliq-rc-pack`. Tarball `adwasd-openclaw-zoho-cliq-0.4.0-rc.1.tgz`, size `100008`, unpacked size `491032`, entry count `67`, shasum `9fca0282ff0c6bfeec6d6158d1bb6fab3f63bcc5`, integrity `sha512-tOZ8qARh62jh8fQKQ/f1ClihYwofq59qjJXnI9TDdMyZrjjG0V+4pzV6SqJ1a8wnoBmoLkqFhCL+gH6p/fGrfg==`. Summary report path pattern: `tests/auto_pilot/reports/openclaw_cliq_rc_pack_summary_<run-id>.json`. |
| Local RC artifact check | `OPENCLAW_CLIQ_ARTIFACT_RUN_ID=20260512T055900Z-ingress-diagnostic-rc-restore-artifact ops/scripts/openclaw_cliq_rc_artifact_check.sh` passed locally with `status=artifact_verified`, no blockers, tarball shasum matching the pack summary, package `0.4.0-rc.1`, channel id `cliq`, manifest id `zoho-cliq`, required `dist/`, `README.md`, and `skill/SKILL.md` entries present, and release posture still no publish/tag/version bump. |
| Local OpenClaw install smoke | `OPENCLAW_CLIQ_INSTALL_RUN_ID=20260512T055900Z-ingress-diagnostic-rc-restore-install ops/scripts/openclaw_cliq_rc_install_smoke.sh` passed locally with `status=install_smoke_passed`, no blockers, source tarball `adwasd-openclaw-zoho-cliq-0.4.0-rc.1.tgz`, artifact report `artifact_verified`, Temp-HOME OpenClaw install, `plugins inspect zoho-cliq --json`, and `plugins doctor` all passed. |
| RC promotion preflight | `OPENCLAW_CLIQ_PROMOTION_RUN_ID=20260512T055900Z-ingress-diagnostic-rc-restore-promotion ops/scripts/openclaw_cliq_rc_promotion_check.sh` passed locally with `status=ready_for_operator_publish`, no blockers, package version `0.4.0-rc.1`, `expectedIntegrityState=placeholder`, pack `publishPerformed=false`, pack `versionBumped=false`, artifact `artifact_verified`, install smoke `install_smoke_passed`, trusted reply `trusted_reply_recorded`, and `npmPromotionRequiresOperatorApproval=true`. |
| Operator publish review bundle | `OPENCLAW_CLIQ_OPERATOR_BUNDLE_RUN_ID=20260512T055900Z-ingress-diagnostic-rc-restore-bundle ops/scripts/openclaw_cliq_rc_operator_publish_bundle.sh` passed locally with `status=operator_publish_bundle_ready`, no blockers, artifact shasum/integrity carried from the verified local reports, `nextAction=operator_select_publish_path`, and `agentMayPublish=false`, `agentMayTag=false`, `agentMayFillExpectedIntegrity=false`. |
| Release notes draft | `OPENCLAW_CLIQ_RELEASE_NOTES_RUN_ID=20260512T055900Z-ingress-diagnostic-rc-restore-notes ops/scripts/openclaw_cliq_rc_release_notes_draft.sh` generated a read-only Markdown draft from the operator bundle with local artifact facts, evidence report filenames, verified callback/reply facts, and explicit no-publish/no-tag/no-release/no-integrity-fill language. |
| Operator publish plan | `OPENCLAW_CLIQ_PUBLISH_PLAN_RUN_ID=20260512T055900Z-ingress-diagnostic-rc-restore-plan ops/scripts/openclaw_cliq_rc_publish_plan.sh` passed with `status=operator_publish_plan_ready` from the ready operator bundle plus safe release-notes draft; it keeps `agentMayExecutePlan=false`, preserves `agentMayPublish=false` / `agentMayTag=false` / `agentMayFillExpectedIntegrity=false`, lists local/operator, npm RC, and GitHub release artifact choices, and records publish/tag/release/integrity fill as operator-only actions. |
| Operator handoff manifest | `OPENCLAW_CLIQ_HANDOFF_MANIFEST_RUN_ID=20260512T055900Z-ingress-diagnostic-rc-restore-manifest ops/scripts/openclaw_cliq_rc_operator_handoff_manifest.sh` passed with `status=operator_handoff_manifest_ready`, no blockers, package/artifact facts, report filenames, source commit `2a9852dcd407d362bffc2830bcb6aa446234a632`, `operator_publish_plan_ready`, `trusted_reply_recorded`, and blocked agent actions including `npm_publish`, `git_tag`, `github_release_create`, and `expectedIntegrity_fill`. |
| Source drift check | `OPENCLAW_CLIQ_SOURCE_DRIFT_RUN_ID=20260512T121844Z-crm-live-approval-categories-postcommit-source ops/scripts/openclaw_cliq_rc_source_drift_check.sh` passed after the CRM live-approval-fact-categories commit with `status=package_source_unchanged`, no blockers, `headCommit=39642ae7e34286a37d34bdff8413dd47f3a3f1ba`, `headMatchesManifestSource=false`, `repoChangedSinceManifest=true`, `repoChangedFileCount=28`, `packageDrift.packageChangedSinceManifest=false`, and no dirty package files. Any package file drift still blocks with `package_source_drift_detected` before operator publish. |
| Operator selection review | `OPENCLAW_CLIQ_SELECTION_REVIEW_RUN_ID=20260512T031411Z-no-selected-path ops/scripts/openclaw_cliq_rc_operator_selection_review.sh` stopped safely with `status=blocked`, `blockers=["publish_path_not_selected"]`, `nextAction=operator_select_publish_path`, and `agentMayExecuteSelectedPath=false`. After the operator selects a path and reruns the publish plan, the same script must report `operator_publish_selection_ready` before an operator executes any publish command. |
| Operator decision packet | `OPENCLAW_CLIQ_DECISION_PACKET_RUN_ID=20260512T121844Z-crm-live-approval-categories-postcommit-decision ops/scripts/openclaw_cliq_rc_operator_decision_packet.sh` passed locally after the CRM live-approval-fact-categories commit with `status=awaiting_operator_publish_path`, `blockers=["publish_path_not_selected"]`, `nextAction=operator_select_publish_path`, `operator_publish_plan_ready`, `package_source_unchanged`, `artifact_verified`, `install_smoke_passed`, `trusted_reply_recorded`, shasum `9fca0282ff0c6bfeec6d6158d1bb6fab3f63bcc5`, `sourceDrift.headCommit=39642ae7e34286a37d34bdff8413dd47f3a3f1ba`, `sourceDrift.packageChangedSinceManifest=false`, and `agentMayExecuteSelectedPath=false`. It reruns the read-only publish plan, source drift guard, and selection review in one wrapper; when `OPENCLAW_CLIQ_OPERATOR_PUBLISH_PATH` is supplied, it must report `operator_publish_selection_ready` before any operator command is executed. The packet also emits basename-only `reportFiles` and `reportsReady` for the publish plan, source drift, selection review, operator bundle, release notes draft, and handoff manifest. |
| Local/operator RC selected path review | `OPENCLAW_CLIQ_OPERATOR_PUBLISH_PATH=local_operator_rc OPENCLAW_CLIQ_DECISION_PACKET_RUN_ID=20260512T104813Z-local-operator-rc-selection ops/scripts/openclaw_cliq_rc_operator_decision_packet.sh` passed locally with `status=operator_publish_selection_ready`, no blockers, `selectedPublishPath=local_operator_rc`, `selectedPublishPathReview.operatorOnly=true`, `selectedPublishPathReview.requiresExplicitOperatorApproval=true`, `selectedPublishPathReview.agentMayExecute=false`, `package_source_unchanged`, `artifact_verified`, `install_smoke_passed`, `trusted_reply_recorded`, all `reportsReady=true`, and `agentMayExecuteSelectedPath=false`. No publish, tag, release, version bump, or expectedIntegrity fill was performed. |
| npm RC selected path review | `OPENCLAW_CLIQ_OPERATOR_PUBLISH_PATH=npm_rc_publish OPENCLAW_CLIQ_DECISION_PACKET_RUN_ID=20260512T110613Z-npm-rc-selection ops/scripts/openclaw_cliq_rc_operator_decision_packet.sh` passed locally with `status=operator_publish_selection_ready`, no blockers, `selectedPublishPath=npm_rc_publish`, command preview `npm publish .tmp/openclaw-cliq-rc-pack/adwasd-openclaw-zoho-cliq-0.4.0-rc.1.tgz --tag rc --access public`, `fillsExpectedIntegrityAfterPublish=true`, `selectedPublishPathReview.agentMayExecute=false`, `requiresExplicitOperatorApproval=true`, all `reportsReady=true`, and `agentMayExecuteSelectedPath=false`. No npm publish or promotion was performed. |
| GitHub artifact selected path review | `OPENCLAW_CLIQ_OPERATOR_PUBLISH_PATH=github_release_artifact OPENCLAW_CLIQ_DECISION_PACKET_RUN_ID=20260512T110613Z-github-release-selection ops/scripts/openclaw_cliq_rc_operator_decision_packet.sh` passed locally with `status=operator_publish_selection_ready`, no blockers, `selectedPublishPath=github_release_artifact`, command preview `gh release create <operator-approved-rc-tag> ... --prerelease --notes-file <release-notes-draft-path>`, `selectedPublishPathReview.agentMayExecute=false`, `requiresExplicitOperatorApproval=true`, all `reportsReady=true`, and `agentMayExecuteSelectedPath=false`. No git tag or GitHub release was created. |
| Operator publish handoff | `docs/releases/OPENCLAW_CLIQ_CHANNEL_V0_4_OPERATOR_PUBLISH_HANDOFF.md` defines the non-automated approval boundary, required preflight commands, publish path choices, post-publish checks, abort conditions, and release-note facts. |
| Public callback auth/reachability | Cloudflare Published application route `https://cliq.hpyio.com/webhooks/cliq` is reachable; `ops/scripts/openclaw_cliq_public_callback_smoke.sh` passed with `status=public_callback_verified`, missing-secret `401`, authenticated unsupported-handler `200`, and no stored webhook bodies, response bodies, or secrets. |
| Live ingress diagnostic | `ops/scripts/openclaw_cliq_live_ingress_diagnostic.sh` reads only redacted OpenClaw `zoho-cliq-audit` log records and reports `no_recent_webhook_ingress`, `latest_webhook_not_dispatched`, `dispatch_reply_not_delivered`, or `live_ingress_active` for the selected send window. `20260512T054312Z-live-window` reported `no_recent_webhook_ingress` for the recent send window, while `20260512T054312Z-known-good` reported `live_ingress_active` for the earlier trusted reply window. The diagnostic keeps raw webhook payloads, message bodies, reply bodies, and secrets out of stdout/report JSON so agents can distinguish a Zoho Bot handler trigger/save issue from an OpenClaw dispatch or Cliq delivery issue. |
| Bot no-response packet | `ops/scripts/openclaw_cliq_bot_no_response_packet.sh` is the preferred first responder for “I sent the Bot a message but got no answer.” It runs public callback smoke when `ZOHO_CLIQ_PUBLIC_WEBHOOK_URL` is set, then runs live ingress diagnostics and emits one redacted `openclaw_cliq_bot_no_response_packet` with `nextAction` values such as `fix_public_callback`, `fix_zoho_bot_handler_trigger`, `fix_webhook_payload_or_policy`, `check_cliq_reply_delivery`, `fix_openclaw_route_binding`, or `collect_trusted_reply_facts_if_needed`. When ingress reports `no_recent_webhook_ingress` and public callback setup is not failing, it embeds a redacted `handlerTrigger` object and evidence filename from `ops/scripts/openclaw_cliq_handler_trigger_packet.sh`. Real run `20260512T064842Z-embedded-handler-trigger-live` verified public callback auth/reachability, reported `no_recent_webhook_ingress`, embedded `handlerTrigger.status=handler_trigger_packet_ready`, selected Mention/Message handler save targets, and returned `nextAction=fix_zoho_bot_handler_trigger`. It stores no raw webhook payloads, message bodies, reply bodies, callback response bodies, or secrets. |
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
If `ops/scripts/openclaw_cliq_rc_artifact_check.sh` reports
`tarball_shasum_mismatch`, `artifact_version_mismatch`, or
`required_entry_missing_*`, fix the local package build or pack evidence before
asking for operator publish approval.
If `ops/scripts/openclaw_cliq_rc_install_smoke.sh` reports
`artifact_not_verified`, `plugin_install_failed`, `plugin_inspect_failed`,
`plugin_id_missing`, `channel_id_missing`, or `plugin_doctor_failed`, fix the
package installability before asking for operator publish approval.
If `ops/scripts/openclaw_cliq_rc_promotion_check.sh` reports
`artifact_report_missing`, `artifact_not_verified`, `install_smoke_missing`, or
`install_smoke_not_passed`, rerun or fix the local artifact/install gates before
asking for operator publish approval.
If `ops/scripts/openclaw_cliq_rc_operator_publish_bundle.sh` reports
`promotion_report_missing`, `promotion_not_ready`, or anything other than
`operator_publish_bundle_ready`, fix the underlying local evidence before
asking for operator publish approval.
If `ops/scripts/openclaw_cliq_rc_release_notes_draft.sh` reports
`operator_bundle_missing`, `operator_bundle_not_ready`,
`agent_publish_permission_unexpected`, `agent_tag_permission_unexpected`, or
`agent_integrity_fill_permission_unexpected`, fix the operator bundle instead
of editing release notes by hand.
If `ops/scripts/openclaw_cliq_rc_publish_plan.sh` reports
`release_notes_draft_unsafe`, `expected_integrity_not_placeholder`, or anything
other than `operator_publish_plan_ready`, stop before publish/tag/release work.
The plan must keep `agentMayExecutePlan=false`.
If `ops/scripts/openclaw_cliq_rc_operator_handoff_manifest.sh` reports
`publish_plan_permission_unexpected`, `operator_bundle_file_mismatch`,
`release_notes_draft_file_mismatch`, or anything other than
`operator_handoff_manifest_ready`, fix the indexed handoff packet before asking
for an operator publish decision.
If `ops/scripts/openclaw_cliq_rc_source_drift_check.sh` reports
`package_source_drift_detected`, `package_worktree_dirty`,
`package_index_dirty`, `package_untracked_files`, or anything other than
`package_source_unchanged`, rebuild the RC artifact and rerun the handoff
packet before operator publish.
If `ops/scripts/openclaw_cliq_rc_operator_selection_review.sh` reports
`publish_path_not_selected`, wait for the operator to choose
`local_operator_rc`, `npm_rc_publish`, or `github_release_artifact`; if it
reports anything other than `operator_publish_selection_ready` after a path is
chosen, do not execute publish commands.
If `ops/scripts/openclaw_cliq_rc_operator_decision_packet.sh` reports
`awaiting_operator_publish_path`, treat that as the normal waiting state and
ask the operator to choose `local_operator_rc`, `npm_rc_publish`, or
`github_release_artifact`. If it reports `operator_publish_selection_ready`,
the operator still must review and explicitly execute the selected command; the
packet keeps `agentMayExecuteSelectedPath=false`.

## RC cut steps

1. Confirm `git status --short` is clean.
2. Re-run `ops/scripts/openclaw_cliq_rc_pack.sh`,
   `ops/scripts/openclaw_cliq_rc_artifact_check.sh`,
   `ops/scripts/openclaw_cliq_rc_install_smoke.sh`,
   `ops/scripts/openclaw_cliq_rc_promotion_check.sh`,
   `ops/scripts/openclaw_cliq_rc_operator_publish_bundle.sh`,
   `ops/scripts/openclaw_cliq_rc_release_notes_draft.sh`,
   `ops/scripts/openclaw_cliq_rc_publish_plan.sh`,
   `ops/scripts/openclaw_cliq_rc_operator_handoff_manifest.sh`,
   `ops/scripts/openclaw_cliq_rc_source_drift_check.sh`,
   `ops/scripts/openclaw_cliq_rc_operator_selection_review.sh`,
   `ops/scripts/openclaw_cliq_rc_operator_decision_packet.sh`, focused
   channel/docs tests, and `make ci`.
3. Re-run `docs/releases/OPENCLAW_CLIQ_CHANNEL_COMPATIBILITY.md` latest/beta
   checks if OpenClaw published a newer stable or beta after this checklist.
4. Package metadata is already set to `0.4.0-rc.1` for the source-controlled
   RC artifact; do not bump again unless cutting a newer RC.
5. Before npm promotion, keep `openclaw.install.expectedIntegrity` as
   `<filled-at-release>` until the operator approves the publish source; after
   publish, fill it with the published artifact integrity and update
   `docs/releases/CHANGELOG.next.md`.
6. Install the published artifact in a Temp-HOME OpenClaw profile and rerun
   `plugins inspect`, `plugins doctor`, `channels status`, and `channels
   capabilities`.
7. Publish release notes that explicitly list trusted agent reply evidence as
   completed for the operator Cloudflare route; durable production
   tunnel/gateway selection remains an operations decision.

For the operator approval boundary, publish choices, and post-publish checks,
use `docs/releases/OPENCLAW_CLIQ_CHANNEL_V0_4_OPERATOR_PUBLISH_HANDOFF.md`.

## Non-goals

- Do not block the RC package on unsupported Zoho endpoints already classified
  as deferred external constraints.
- Do not add parallel `cliq_send` or custom approval tools; use OpenClaw native
  message and approval surfaces.
- Do not store OAuth tokens, webhook secrets, raw webhook payloads, or raw Cliq
  message bodies in release evidence.
