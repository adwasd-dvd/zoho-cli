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
        "RC package ready, public callback verified, agent reply pending",
        "cliq-channel-418",
        "cliq-channel-419",
        "cliq-channel-420",
        "cliq-channel-421",
        "cliq-channel-422",
        "ops/scripts/openclaw_cliq_rc_pack.sh",
        "OPENCLAW_CLIQ_BOT_HANDLER_TEMPLATES.md",
        "Public callback auth/reachability",
        "ops/scripts/openclaw_cliq_public_callback_smoke.sh",
        "public_callback_verified",
        "Published application",
        "127.0.0.1:18789",
        "Trusted agent reply",
        "ZOHO_CLIQ_PUBLIC_WEBHOOK_URL",
        "0.4.0-rc.1",
        "adwasd-openclaw-zoho-cliq-0.4.0-rc.1.tgz",
        "87b553ad5bbec1c920a05b342630a57cea58b96b",
        "expectedIntegrity",
        "1876 passed in 50.38s",
        "token_refresh_rate_limited",
        "skip_deferred",
        "Do not add parallel `cliq_send`",
    ]

    for marker in required:
        assert marker in checklist


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
        "body:payload.toString()",
        "ZOHO_CLIQ_WEBHOOK_SECRET",
        "Published application route",
        "127.0.0.1:18789",
        "Welcome, Incoming Webhook, Call, and Menu handlers",
        "cliq-channel-421",
        "processCliqWebhookPayload()",
    ]

    for marker in required:
        assert marker in templates

    assert "qSEeU3" not in templates
    assert "trycloudflare.com" not in templates
