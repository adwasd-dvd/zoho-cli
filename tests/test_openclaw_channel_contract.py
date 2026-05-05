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
        "2026.5.4-beta.1",
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
        read("integrations/openclaw/CLIQ_CHANNEL_DEVELOPMENT_GUIDE.md"),
        read("skill/references/openclaw-cliq-channel.md"),
    ]

    for doc in docs:
        assert contract_path in doc
        assert ">=2026.5.3-1" in doc
