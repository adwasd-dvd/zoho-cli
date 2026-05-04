from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "integrations" / "openclaw-channel-cliq"


def read(path: str) -> str:
    return (PLUGIN_ROOT / path).read_text(encoding="utf-8")


def read_json(path: str) -> dict:
    return json.loads(read(path))


def test_openclaw_cliq_channel_package_metadata_is_installable() -> None:
    package = read_json("package.json")
    openclaw = package["openclaw"]

    assert package["name"] == "@adwasd/openclaw-zoho-cliq"
    assert package["version"] == "0.4.0-alpha.0"
    assert package["engines"]["node"] == ">=22.14.0"
    assert package["peerDependencies"]["openclaw"] == ">=2026.5.3-1"
    assert package["devDependencies"]["openclaw"] == "2026.5.3-1"

    assert openclaw["extensions"] == ["./dist/index.js"]
    assert openclaw["setupEntry"] == "./dist/setup-entry.js"
    assert openclaw["channel"]["id"] == "cliq"
    assert openclaw["channel"]["configuredState"] == {
        "specifier": "./dist/configured-state.js",
        "exportName": "hasCliqConfiguredState",
    }
    assert openclaw["channel"]["persistedAuthState"] == {
        "specifier": "./dist/auth-presence.js",
        "exportName": "hasCliqAuthState",
    }
    assert openclaw["install"]["minHostVersion"] == ">=2026.5.3-1"
    assert openclaw["compat"]["pluginApi"] == ">=2026.5.3-1"


def test_openclaw_cliq_channel_manifest_matches_contract() -> None:
    manifest = read_json("openclaw.plugin.json")

    assert manifest["id"] == "zoho-cliq"
    assert manifest["channels"] == ["cliq"]
    assert manifest["activation"]["channels"] == ["cliq"]
    assert manifest["skills"] == ["./skill"]
    assert manifest["channelEnvVars"]["cliq"] == [
        "ZOHO_ACCOUNT",
        "ZOHO_CONFIG",
        "ZOHO_TOKEN_PASSWORD",
        "ZOHO_CLIQ_WEBHOOK_SECRET",
    ]
    assert manifest["channelConfigs"]["cliq"]["schema"] == {
        "type": "object",
        "additionalProperties": False,
        "properties": {},
    }


def test_openclaw_cliq_channel_sources_use_locked_sdk_surfaces() -> None:
    source = "\n".join(
        [
            read("index.ts"),
            read("setup-entry.ts"),
            read("configured-state.ts"),
            read("auth-presence.ts"),
            read("src/channel.ts"),
            read("src/config.ts"),
            read("src/zoho-cli.ts"),
        ]
    )

    for marker in [
        "defineChannelPluginEntry",
        "defineSetupPluginEntry",
        "createChannelPluginBase",
        "createChatChannelPlugin",
        "resolveInboundMentionDecision",
        "resolveSessionConversation",
        "openclaw/plugin-sdk/channel-core",
        "openclaw/plugin-sdk/channel-inbound",
        "openclaw/plugin-sdk/secret-ref-runtime",
    ]:
        assert marker in source

    assert "cliq_send" not in source
    assert "ChannelPlugin.approvals" not in source
    assert "child_process" not in source
    assert "cliq-channel-404" in source


def test_openclaw_cliq_channel_dist_runtime_outputs_exist() -> None:
    for path in [
        "dist/index.js",
        "dist/setup-entry.js",
        "dist/configured-state.js",
        "dist/auth-presence.js",
        "dist/src/channel.js",
        "dist/src/config.js",
        "dist/src/constants.js",
        "dist/src/zoho-cli.js",
    ]:
        assert (PLUGIN_ROOT / path).exists(), f"missing build output: {path}"

    built = "\n".join(
        [
            read("dist/index.js"),
            read("dist/setup-entry.js"),
            read("dist/src/channel.js"),
            read("dist/src/zoho-cli.js"),
        ]
    )
    assert "child_process" not in built
