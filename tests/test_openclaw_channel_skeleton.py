from __future__ import annotations

import json
import subprocess
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
    schema = manifest["channelConfigs"]["cliq"]["schema"]
    properties = schema["properties"]
    definitions = schema["definitions"]

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert {
        "accounts",
        "accountEmail",
        "configPath",
        "defaultAccount",
        "tokenPassword",
        "webhookSecret",
        "dmPolicy",
        "groupPolicy",
        "groupAllowFrom",
        "allowFrom",
        "requireMention",
        "employeeMode",
        "workScopes",
    }.issubset(properties)
    assert properties["tokenPassword"] == {"$ref": "#/definitions/secretRef"}
    assert properties["webhookSecret"] == {"$ref": "#/definitions/secretRef"}
    assert properties["accountEmail"] == {"$ref": "#/definitions/configValue"}
    assert properties["configPath"] == {"$ref": "#/definitions/configValue"}
    assert definitions["secretRef"]["required"] == ["source", "provider", "id"]
    assert definitions["secretRef"]["properties"]["source"]["enum"] == [
        "env",
        "file",
        "exec",
    ]
    assert definitions["configValue"]["anyOf"][1] == {"$ref": "#/definitions/secretRef"}
    assert definitions["account"]["properties"]["tokenPassword"] == {
        "$ref": "#/definitions/secretRef"
    }
    assert definitions["account"]["properties"]["groupPolicy"]["enum"] == [
        "allowlist",
        "open",
        "disabled",
    ]
    assert definitions["employeeMode"]["properties"]["scopeProfile"]["minLength"] == 1
    assert definitions["workScopes"]["additionalProperties"] == {
        "$ref": "#/definitions/workScope"
    }

    ui_hints = manifest["channelConfigs"]["cliq"]["uiHints"]
    assert ui_hints["tokenPassword"]["sensitive"] is True
    assert ui_hints["webhookSecret"]["sensitive"] is True
    assert ui_hints["employeeMode"]["advanced"] is True


def test_openclaw_cliq_channel_sources_use_locked_sdk_surfaces() -> None:
    source = "\n".join(
        [
            read("index.ts"),
            read("setup-entry.ts"),
            read("configured-state.ts"),
            read("auth-presence.ts"),
            read("src/channel.ts"),
            read("src/config.ts"),
            read("src/employee-policy.ts"),
            read("src/session.ts"),
            read("src/security.ts"),
            read("src/setup-wizard.ts"),
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
        "setupWizard",
        "cliqSetupWizard",
        "buildDmGroupAccountAllowlistAdapter",
        "evaluateCliqInboundSecurity",
        "evaluateCliqEmployeePolicy",
        "groupPolicy",
        "employeeMode",
        "approvalCapability",
        "getActionAvailabilityState",
        "buildCliqOutboundSessionRoute",
        "buildThreadAwareOutboundSessionRoute",
        "buildCliqSessionPeerId",
        "bot_thread_participant",
        "commandAuthorized",
    ]:
        assert marker in source

    assert "cliq_send" not in source
    assert "ChannelPlugin.approvals" not in source
    assert "child_process" not in source


def test_openclaw_cliq_channel_setup_uses_env_secret_refs() -> None:
    source = read("src/config.ts")

    for marker in [
        "SecretRef",
        "envSecretRef",
        "ZOHO_TOKEN_PASSWORD",
        "ZOHO_CLIQ_WEBHOOK_SECRET",
        "ZOHO_ACCOUNT",
        "ZOHO_CONFIG",
        "configPath",
        "dmPolicy",
    ]:
        assert marker in source

    for forbidden_input in [
        "input.token",
        "input.accessToken",
        "input.password",
        "input.privateKey",
        "input.secret",
        "input.botToken",
        "input.appToken",
    ]:
        assert forbidden_input in source


def test_openclaw_cliq_channel_dist_runtime_outputs_exist() -> None:
    for path in [
        "dist/index.js",
        "dist/setup-entry.js",
        "dist/configured-state.js",
        "dist/auth-presence.js",
        "dist/src/channel.js",
        "dist/src/config.js",
        "dist/src/constants.js",
        "dist/src/employee-policy.js",
        "dist/src/session.js",
        "dist/src/security.js",
        "dist/src/setup-wizard.js",
        "dist/src/zoho-cli.js",
    ]:
        assert (PLUGIN_ROOT / path).exists(), f"missing build output: {path}"

    built = "\n".join(
        [
            read("dist/index.js"),
            read("dist/setup-entry.js"),
            read("dist/src/channel.js"),
            read("dist/src/employee-policy.js"),
            read("dist/src/session.js"),
            read("dist/src/security.js"),
            read("dist/src/setup-wizard.js"),
            read("dist/src/zoho-cli.js"),
        ]
    )
    assert "child_process" not in built


def test_openclaw_cliq_channel_setup_wizard_has_operator_states() -> None:
    source = read("src/setup-wizard.ts")

    for marker in [
        "CLIQ_SETUP_STATE_COPY",
        "host_too_old",
        "zoho_missing",
        "not_logged_in",
        "missing_scope",
        "network_missing",
        "webhook_unverified",
        "allowlist_empty",
        "employee_scope_empty",
        "envShortcut",
        "disable:",
        "resolveCliqSetupStatusLines",
        "ZOHO_ACCOUNT",
        "ZOHO_CONFIG",
        "ZOHO_TOKEN_PASSWORD",
        "ZOHO_CLIQ_WEBHOOK_SECRET",
    ]:
        assert marker in source


def test_openclaw_cliq_channel_security_policy_is_secure_by_default() -> None:
    channel = read("src/channel.ts")
    config = read("src/config.ts")
    security = read("src/security.ts")
    employee = read("src/employee-policy.ts")

    assert 'defaultPolicy: "pairing"' in channel
    assert "resolveRequireMention" in channel
    assert "collectCliqSecurityWarnings" in channel
    assert "collectCliqSecurityAuditFindings" in channel
    assert "normalizeCliqAllowEntry" in channel

    for marker in [
        'dmPolicy: accounts[params.accountId]?.dmPolicy ?? "pairing"',
        'groupPolicy: accounts[params.accountId]?.groupPolicy ?? "allowlist"',
        "requireMention: accounts[params.accountId]?.requireMention ?? true",
        "DEFAULT_CLIQ_EMPLOYEE_MODE",
        "DEFAULT_CLIQ_WORK_SCOPES",
    ]:
        assert marker in config

    for marker in [
        "dm_pairing_required",
        "group_allowlist_denied",
        "mention_required",
        "groupPolicy=open",
        "allowFrom includes '*'",
        "employeeMode.enabled=false",
    ]:
        assert marker in security

    for marker in [
        "system.debug",
        "system.install",
        "system.config_write",
        "system.exec",
        "secrets.read",
        "policy.bypass",
        "employee_admin_override_denied",
        "employee_scope_empty",
    ]:
        assert marker in employee


def test_openclaw_cliq_channel_session_grammar_runtime() -> None:
    script = """
import assert from "node:assert/strict";
import {
  buildCliqOutboundSessionRoute,
  buildCliqSessionPeerId,
  parseCliqExplicitTarget,
  resolveCliqSessionConversation,
  resolveCliqSessionTarget,
} from "./integrations/openclaw-channel-cliq/dist/src/session.js";

assert.deepEqual(parseCliqExplicitTarget("cliq:user:U123"), {
  to: "user:U123",
  nativeId: "U123",
  chatType: "direct",
  kind: "user",
});
assert.deepEqual(parseCliqExplicitTarget("zoho:channel:C123:thread:T9"), {
  to: "channel:C123",
  nativeId: "C123",
  chatType: "channel",
  kind: "channel",
  threadId: "T9",
});

const peer = buildCliqSessionPeerId({
  accountId: "Default",
  network: "HappyNetwork",
  chatType: "channel",
  nativeId: "C123",
});
assert.equal(peer, "account:default:network:happynetwork:channel:c123");

const conversation = resolveCliqSessionConversation({
  kind: "channel",
  rawId: `${peer}:thread:T9`,
});
assert.equal(conversation.id, peer);
assert.equal(conversation.threadId, "T9");
assert.deepEqual(conversation.parentConversationCandidates, [peer]);
assert.equal(
  resolveCliqSessionTarget({ kind: "channel", id: peer, threadId: "T9" }),
  "channel:c123:thread:T9",
);

const route = buildCliqOutboundSessionRoute({
  cfg: {},
  agentId: "main",
  account: {
    accountId: "Default",
    enabled: true,
    cliPath: "zoho",
    network: "HappyNetwork",
    dmPolicy: "pairing",
    groupPolicy: "allowlist",
    groupAllowFrom: [],
    allowFrom: [],
    requireMention: true,
    employeeMode: {},
    workScopes: {},
  },
  target: "channel:C123",
  threadId: "T9",
});
assert.equal(route.to, "channel:C123");
assert.equal(route.threadId, "T9");
assert.match(route.baseSessionKey, /account:default:network:happynetwork:channel:c123/);
assert.match(route.sessionKey, /:thread:t9$/);
"""
    subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )


def test_openclaw_cliq_channel_mention_policy_runtime() -> None:
    script = """
import assert from "node:assert/strict";
import { resolveCliqMentionDecision } from "./integrations/openclaw-channel-cliq/dist/src/channel.js";

assert.equal(resolveCliqMentionDecision({
  text: "please help",
  isGroup: true,
  requireMention: true,
}).shouldSkip, true);

assert.equal(resolveCliqMentionDecision({
  text: "please help",
  isGroup: true,
  requireMention: true,
  isReplyToBot: true,
}).shouldSkip, false);

assert.equal(resolveCliqMentionDecision({
  text: "please help",
  isGroup: true,
  requireMention: true,
  isBotThreadParticipant: true,
}).shouldSkip, false);

const deniedCommand = resolveCliqMentionDecision({
  text: "/approve abc",
  isGroup: true,
  requireMention: true,
  allowTextCommands: true,
  hasControlCommand: true,
  commandAuthorized: false,
});
assert.equal(deniedCommand.shouldSkip, true);
assert.equal(deniedCommand.shouldBypassMention, false);

const allowedCommand = resolveCliqMentionDecision({
  text: "/approve abc",
  isGroup: true,
  requireMention: true,
  allowTextCommands: true,
  hasControlCommand: true,
  commandAuthorized: true,
});
assert.equal(allowedCommand.shouldSkip, false);
assert.equal(allowedCommand.shouldBypassMention, true);
"""
    subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
