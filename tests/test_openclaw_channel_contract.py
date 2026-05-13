from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_openclaw_cliq_channel_contract_locks_versions_and_identity():
    contract = read("docs/architecture/OPENCLAW_CLIQ_CHANNEL_SDK_CONTRACT.md")

    required = [
        "@adwasd/openclaw-zoho-cliq",
        "plugin id: zoho-cliq",
        "channel id: cliq",
        "config root: channels.cliq",
        "OpenClaw 2026.5.3-1 (2eae30e)",
        "OpenClaw 2026.4.15",
        "2026.5.3-1",
        "2026.5.4",
        "2026.5.4-beta.3",
        "docs/releases/OPENCLAW_CLIQ_CHANNEL_COMPATIBILITY.md",
        '"minHostVersion": ">=2026.5.3-1"',
        '"pluginApi": ">=2026.5.3-1"',
        '"node": ">=22.14.0"',
    ]

    for marker in required:
        assert marker in contract


def test_openclaw_cliq_channel_contract_uses_current_sdk_seams():
    contract = read("docs/architecture/OPENCLAW_CLIQ_CHANNEL_SDK_CONTRACT.md")

    required = [
        "openclaw.plugin.json",
        "package.json",
        "package.json#openclaw",
        "defineChannelPluginEntry",
        "defineSetupPluginEntry",
        "createChannelPluginBase",
        "createChatChannelPlugin",
        "setupWizard",
        "buildDmGroupAccountAllowlistAdapter",
        "security.collectWarnings",
        "employee-policy.ts",
        "src/session.ts",
        "src/status.ts",
        "src/native-dispatch.ts",
        "src/observability.ts",
        "src/privacy.ts",
        "src/zoho-cli.ts",
        "runPluginCommandWithTimeout",
        "outbound.sendText",
        "runtime.channel.turn",
        "sendCliqText",
        "resolveInboundMentionDecision",
        "approvalCapability",
        "resolveSessionConversation",
        "SecretRef",
        "openclaw/plugin-sdk/channel-core",
        "openclaw/plugin-sdk/channel-inbound",
        "openclaw/plugin-sdk/secret-ref-runtime",
    ]

    for marker in required:
        assert marker in contract

    assert "not `ChannelPlugin.approvals`" in contract
    assert "cliq_send" in contract


def test_openclaw_cliq_channel_docs_point_to_locked_contract():
    contract_path = "docs/architecture/OPENCLAW_CLIQ_CHANNEL_SDK_CONTRACT.md"

    docs = [
        read("docs/architecture/OPENCLAW_CLIQ_CHANNEL_0_4_PLAN.md"),
        read("docs/releases/OPENCLAW_CLIQ_CHANNEL_COMPATIBILITY.md"),
        read("docs/releases/OPENCLAW_CLIQ_CHANNEL_V0_4_RC_CHECKLIST.md"),
        read("integrations/openclaw/CLIQ_CHANNEL_DEVELOPMENT_GUIDE.md"),
        read("skill/references/openclaw-cliq-channel.md"),
    ]

    for doc in docs:
        assert contract_path in doc
        assert ">=2026.5.3-1" in doc


def test_openclaw_cliq_channel_compatibility_runbook_has_repair_contract():
    runbook = read("docs/releases/OPENCLAW_CLIQ_CHANNEL_COMPATIBILITY.md")

    required = [
        "Compatibility matrix",
        "OpenClaw 2026.5.3-1 (2eae30e)",
        "2026.5.4",
        "2026.5.4-beta.3",
        "host_too_old",
        "plugin discovery failure",
        "manifest schema failure",
        "HTTP route registration failure",
        "native dispatch failure",
        "token_refresh_rate_limited",
        "skip_deferred",
        "npx -y openclaw@latest",
        "npx -y openclaw@beta",
        "ops/scripts/openclaw_cliq_live_smoke.sh",
        "ops/scripts/openclaw_cliq_rc_pack.sh",
    ]

    for marker in required:
        assert marker in runbook


def test_openclaw_cliq_channel_rc_checklist_has_cut_contract():
    checklist = read("docs/releases/OPENCLAW_CLIQ_CHANNEL_V0_4_RC_CHECKLIST.md")

    required = [
        "RC package ready, public callback and trusted reply verified",
        "cliq-channel-418",
        "cliq-channel-419",
        "cliq-channel-420",
        "cliq-channel-421",
        "cliq-channel-422",
        "cliq-channel-453",
        "cliq-channel-454",
        "cliq-channel-455",
        "cliq-channel-456",
        "cliq-channel-458",
        "cliq-channel-459",
        "cliq-channel-460",
        "cliq-channel-461",
        "cliq-channel-464",
        "cliq-channel-465",
        "cliq-channel-466",
        "cliq-channel-467",
        "cliq-channel-468",
        "cliq-channel-469",
        "cliq-channel-470",
        "cliq-channel-471",
        "cliq-channel-472",
        "cliq-channel-473",
        "cliq-channel-474",
        "cliq-channel-475",
        "cliq-channel-476",
        "cliq-channel-477",
        "cliq-channel-478",
        "cliq-channel-479",
        "cliq-channel-480",
        "cliq-channel-481",
        "cliq-channel-482",
        "cliq-channel-483",
        "cliq-channel-484",
        "cliq-channel-485",
        "cliq-channel-486",
        "cliq-channel-487",
        "cliq-channel-488",
        "cliq-channel-489",
        "cliq-channel-492",
        "cliq-channel-493",
        "cliq-channel-494",
        "cliq-channel-495",
        "cliq-channel-510",
        "cliq-channel-511",
        "platform-214",
        "platform-215",
        "platform-216",
        "platform-217",
        "platform-218",
        "ops/scripts/openclaw_cliq_rc_pack.sh",
        "ops/scripts/openclaw_cliq_rc_artifact_check.sh",
        "ops/scripts/openclaw_cliq_rc_install_smoke.sh",
        "ops/scripts/openclaw_cliq_rc_promotion_check.sh",
        "ops/scripts/openclaw_cliq_rc_operator_publish_bundle.sh",
        "ops/scripts/openclaw_cliq_rc_release_notes_draft.sh",
        "ops/scripts/openclaw_cliq_rc_publish_plan.sh",
        "ops/scripts/openclaw_cliq_rc_operator_handoff_manifest.sh",
        "ops/scripts/openclaw_cliq_rc_source_drift_check.sh",
        "ops/scripts/openclaw_cliq_rc_operator_selection_review.sh",
        "ops/scripts/openclaw_cliq_rc_operator_decision_packet.sh",
        "ops/scripts/zoho_cli_rc_autonomy_packet.sh",
        "ops/scripts/zoho_cli_rc_operator_action_prompt.sh",
        "ops/scripts/openclaw_cliq_bot_handler_operator_prompt.sh",
        "ops/scripts/openclaw_cliq_bot_handler_template_render.sh",
        "handler_template_render_ready",
        "save_openclaw_cliq_bot_message_handler",
        "operatorActionRequests",
        "commandPreview",
        "followUpCommandPreview",
        "unblocks",
        "operator_action_prompt_ready",
        "send_operator_action_prompt",
        "20260512T212845Z-operator-action-prompt-dev",
        "20260512T214616Z-operator-action-md-dev",
        "20260512T220116Z-platform218-postcommit-source",
        "20260512T220116Z-platform218-postcommit-decision",
        "20260512T220116Z-platform218-postcommit-prompt",
        "d15a1aebb8c4d2c28f0b7d6a799aa690dc41be87",
        "20260512T223116Z-crm033-postcommit-source",
        "20260512T223116Z-crm033-postcommit-decision",
        "20260512T223116Z-crm033-postcommit-autonomy",
        "20260512T223116Z-crm033-postcommit-prompt",
        "3584cd40a6a99642fdd3297e36383707b7a01663",
        "CRM_V0_5_FIXTURE_CLEANUP_PLAN_TEMPLATE.md",
        "--md",
        "select_openclaw_cliq_publish_path",
        "provide_crm_fixture_cleanup_plan",
        "provide_crm_fixture_payload_file",
        "OPENCLAW_CLIQ_BOT_HANDLER_TEMPLATES.md",
        "OPENCLAW_CLIQ_CHANNEL_V0_4_OPERATOR_PUBLISH_HANDOFF.md",
        "Public callback auth/reachability",
        "Operator publish handoff",
        "https://cliq.hpyio.com/webhooks/cliq",
        "ops/scripts/openclaw_cliq_public_callback_smoke.sh",
        "ops/scripts/openclaw_cliq_live_ingress_diagnostic.sh",
        "ops/scripts/openclaw_cliq_bot_no_response_packet.sh",
        "ops/scripts/openclaw_cliq_handler_trigger_packet.sh",
        "handler_operator_prompt_ready",
        "public_callback_verified",
        "no_recent_webhook_ingress",
        "handlerTrigger",
        "handler_trigger_packet_ready",
        "dispatch_reply_not_delivered",
        "fix_zoho_bot_handler_trigger",
        "Published application",
        "127.0.0.1:18789",
        "Trusted agent reply",
        "ZOHO_CLIQ_PUBLIC_WEBHOOK_URL",
        "0.4.0-rc.1",
        "adwasd-openclaw-zoho-cliq-0.4.0-rc.1.tgz",
        "9fca0282ff0c6bfeec6d6158d1bb6fab3f63bcc5",
        "expectedIntegrity",
        "artifact_verified",
        "install_smoke_passed",
        "tarball_shasum_mismatch",
        "plugin_install_failed",
        "artifact_report_missing",
        "install_smoke_missing",
        "install_smoke_not_passed",
        "operator_publish_bundle_ready",
        "agentMayPublish=false",
        "promotion_report_missing",
        "promotion_not_ready",
        "operator_bundle_not_ready",
        "agent_publish_permission_unexpected",
        "operator_publish_plan_ready",
        "agentMayExecutePlan=false",
        "operator_handoff_manifest_ready",
        "package_source_unchanged",
        "package_source_drift_detected",
        "operator_publish_selection_ready",
        "publish_path_not_selected",
        "awaiting_operator_publish_path",
        "reportFiles",
        "reportsReady",
        "repoChangedSinceManifest",
        "packageChangedSinceManifest=false",
        "20260512T132144Z-crm-readiness-action-boundary-postcommit-source",
        "20260512T132144Z-crm-readiness-action-boundary-postcommit-decision",
        "20260512T135144Z-crm-state-sync-postcommit-source",
        "20260512T135144Z-crm-state-sync-postcommit-decision",
        "20260512T174215Z-platform214-postcommit-source",
        "20260512T174215Z-platform214-postcommit-decision",
        "20260512T174215Z-post-platform214-autonomy",
        "20260512T203845Z-operator-requests-dev",
        "20260512T205345Z-platform215-postcommit-source",
        "20260512T205345Z-platform215-postcommit-decision",
        "20260512T205345Z-platform215-postcommit-autonomy",
        "20260512T210846Z-operator-request-hints-dev",
        "20260512T104813Z-local-operator-rc-selection",
        "20260512T110613Z-npm-rc-selection",
        "20260512T110613Z-github-release-selection",
        "25eb507d75c6100aad6ca7e7ddd418a60815c87e",
        "0319d9b8ebabf532f0b76230991a1feae2ee78a1",
        "a03de9e507f8c0dd8369f5fa19395e0f500b63c1",
        "9fac452e0fd25e6a58f3054369dec01f83cb0950",
        "selectedPublishPath=local_operator_rc",
        "selectedPublishPath=npm_rc_publish",
        "selectedPublishPath=github_release_artifact",
        "fillsExpectedIntegrityAfterPublish=true",
        "selectedPublishPathReview.agentMayExecute=false",
        "repoChangedFileCount=28",
        "repoChangedFileCount=38",
        "operatorInputsNeeded.openclawCliqPublishPath=true",
        "operatorInputsNeeded.openclawCliqBotMessageHandler=true",
        "crmNextCommandAllowedForAgent=false",
        "1901 passed in 53.30s",
        "token_refresh_rate_limited",
        "skip_deferred",
        "Do not add parallel `cliq_send`",
    ]

    for marker in required:
        assert marker in checklist


def test_openclaw_cliq_operator_publish_handoff_has_approval_boundary():
    handoff = read(
        "docs/releases/OPENCLAW_CLIQ_CHANNEL_V0_4_OPERATOR_PUBLISH_HANDOFF.md"
    )

    required = [
        "ready_for_operator_publish",
        "npm publish",
        "Git tag creation",
        "openclaw.install.expectedIntegrity",
        "<filled-at-release>",
        "OPENCLAW_CLIQ_PROMOTION_RUN_ID",
        "OPENCLAW_CLIQ_ARTIFACT_RUN_ID",
        "OPENCLAW_CLIQ_INSTALL_RUN_ID",
        "ops/scripts/openclaw_cliq_rc_artifact_check.sh",
        "ops/scripts/openclaw_cliq_rc_install_smoke.sh",
        "ops/scripts/openclaw_cliq_rc_promotion_check.sh",
        "ops/scripts/openclaw_cliq_rc_operator_publish_bundle.sh",
        "ops/scripts/openclaw_cliq_rc_release_notes_draft.sh",
        "ops/scripts/openclaw_cliq_rc_publish_plan.sh",
        "ops/scripts/openclaw_cliq_rc_operator_handoff_manifest.sh",
        "ops/scripts/openclaw_cliq_rc_source_drift_check.sh",
        "ops/scripts/openclaw_cliq_rc_operator_selection_review.sh",
        "ops/scripts/openclaw_cliq_rc_pack.sh",
        "trusted_reply_recorded",
        "artifact_verified",
        "install_smoke_passed",
        "artifact_report_missing",
        "install_smoke_missing",
        "install_smoke_not_passed",
        "operator_publish_bundle_ready",
        "agentMayPublish=false",
        "agentMayTag=false",
        "agentMayFillExpectedIntegrity=false",
        "promotion_report_missing",
        "promotion_not_ready",
        "operator_bundle_missing",
        "operator_bundle_not_ready",
        "agent_publish_permission_unexpected",
        "agent_tag_permission_unexpected",
        "agent_integrity_fill_permission_unexpected",
        "operator_publish_plan_ready",
        "agentMayExecutePlan=false",
        "release_notes_draft_unsafe",
        "operator_handoff_manifest_ready",
        "publish_plan_permission_unexpected",
        "package_source_unchanged",
        "package_source_drift_detected",
        "package_worktree_dirty",
        "operator_publish_selection_ready",
        "20260512T104813Z-local-operator-rc-selection",
        "20260512T110613Z-npm-rc-selection",
        "20260512T110613Z-github-release-selection",
        "20260512T132144Z-crm-readiness-action-boundary-postcommit-decision",
        "20260512T135144Z-crm-state-sync-postcommit-decision",
        "20260512T143844Z-crm-next-command-preview-postcommit-decision",
        "sourceDrift.headCommit=25eb507d75c6100aad6ca7e7ddd418a60815c87e",
        "sourceDrift.headCommit=0319d9b8ebabf532f0b76230991a1feae2ee78a1",
        "sourceDrift.headCommit=3f1773c7d5deb7e1dae68db84445017d0efd0449",
        "selectedPublishPathReview.agentMayExecute=false",
        "publish_path_not_selected",
        "agentMayExecuteSelectedPath=false",
        "reportFiles",
        "reportsReady",
        "npmPromotionRequiresOperatorApproval=true",
        "Do not let an agent perform",
        "Local/operator RC only",
        "npm RC publish",
        "GitHub release artifact",
        "Abort conditions",
        "token_refresh_rate_limited",
        "tarball_shasum_mismatch",
        "plugin_install_failed",
        "trusted_reply_not_recorded",
    ]

    for marker in required:
        assert marker in handoff


def test_openclaw_cliq_package_docs_include_decision_packet():
    docs = "\n".join(
        [
            read("integrations/openclaw-channel-cliq/README.md"),
            read("integrations/openclaw-channel-cliq/skill/SKILL.md"),
        ]
    )

    for marker in [
        "ops/scripts/openclaw_cliq_rc_operator_decision_packet.sh",
        "awaiting_operator_publish_path",
        "operator_publish_selection_ready",
        "agentMayExecuteSelectedPath=false",
        "local_operator_rc",
        "npm_rc_publish",
        "github_release_artifact",
        "package_source_unchanged",
    ]:
        assert marker in docs


def test_openclaw_cliq_bot_handler_templates_cover_real_handlers():
    templates = read("docs/releases/OPENCLAW_CLIQ_BOT_HANDLER_TEMPLATES.md")

    required = [
        "Bot Message Handler",
        "Bot Mention Handler",
        "Bot Participation Handler",
        "Bot Context Handler",
        "Deluge invokeUrl task",
        "Message Handler",
        "Mention Handler",
        "Participation Handler",
        "Context Handler",
        "https://<your-tunnel-or-gateway>/webhooks/cliq",
        "X-Cliq-Webhook-Secret",
        "<rotated-secret>",
        'payload.put("handler","message");',
        'payload.put("handler","mention");',
        'payload.put("handler","participation");',
        'payload.put("handler","context");',
        'msg.put("text",message.toString());',
        'msg.put("senderId",sender_id);',
        'msg.put("chatId",chat_id);',
        "body:payload.toString()",
        "Deluge Map-string bodies",
        'reason:"invalid_payload"',
        "ZOHO_CLIQ_WEBHOOK_SECRET",
        "Published application route",
        "127.0.0.1:18789",
        "Welcome, Incoming Webhook, Call, and Menu handlers",
        "cliq-channel-421",
        "processCliqWebhookPayload()",
        "openclaw_cliq_bot_handler_template_render.sh --md",
        "handler_template_render_ready",
    ]

    for marker in required:
        assert marker in templates

    assert "qSEeU3" not in templates
    assert "trycloudflare.com" not in templates
