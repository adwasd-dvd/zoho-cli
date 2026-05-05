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
        "cliqOutboundAdapter",
        "outbound: cliqOutboundAdapter",
        'chunkerMode: "markdown"',
        "sendCliqText",
        'from "openclaw/plugin-sdk/run-command"',
        "runPluginCommandWithTimeout",
        "ZohoCliqCommandErrorKind",
        "classifyZohoCliError",
    ]:
        assert marker in source

    assert "cliq_send" not in source
    assert "ChannelPlugin.approvals" not in source


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


def test_openclaw_cliq_channel_zoho_cli_adapter_success_runtime(tmp_path) -> None:
    fake_zoho = tmp_path / "fake-zoho.mjs"
    fake_zoho.write_text(
        """#!/usr/bin/env node
const args = process.argv.slice(2);
if (args[0] !== "cliq") {
  console.error("expected cliq command");
  process.exit(7);
}
console.error(`trace ZOHO_TOKEN_PASSWORD=${process.env.ZOHO_TOKEN_PASSWORD} ZOHO_CLIQ_WEBHOOK_SECRET=${process.env.ZOHO_CLIQ_WEBHOOK_SECRET} access_token=tok123 refresh_token=ref456 Authorization: Bearer auth789`);
const payload = {
  ok: true,
  args,
  env: {
    account: process.env.ZOHO_ACCOUNT,
    config: process.env.ZOHO_CONFIG,
    tokenSeen: process.env.ZOHO_TOKEN_PASSWORD === "token-secret",
    webhookSeen: process.env.ZOHO_CLIQ_WEBHOOK_SECRET === "webhook-secret"
  }
};
if (args.includes("send") || args.includes("reply") || args.includes("thread-reply")) {
  payload.message_id = "M123";
}
console.log(JSON.stringify(payload));
""",
        encoding="utf-8",
    )
    fake_zoho.chmod(0o755)

    script = f"""
import assert from "node:assert/strict";
import {{
  buildCliqDeliveryArgs,
  buildCliqReplyArgs,
  buildCliqSendArgs,
  buildCliqThreadReplyArgs,
  runZohoCliqJson,
  sendCliqText,
}} from "./integrations/openclaw-channel-cliq/dist/src/zoho-cli.js";

process.env.FAKE_ZOHO_ACCOUNT = "bot@example.com";
process.env.FAKE_ZOHO_CONFIG = "/tmp/zoho-config.json";
process.env.FAKE_ZOHO_TOKEN_PASSWORD = "token-secret";
process.env.FAKE_ZOHO_WEBHOOK_SECRET = "webhook-secret";

const account = {{
  accountId: "default",
  enabled: true,
  cliPath: {json.dumps(str(fake_zoho))},
  network: "happy",
  accountEmail: {{ source: "env", provider: "default", id: "FAKE_ZOHO_ACCOUNT" }},
  configPath: {{ source: "env", provider: "default", id: "FAKE_ZOHO_CONFIG" }},
  tokenPassword: {{ source: "env", provider: "default", id: "FAKE_ZOHO_TOKEN_PASSWORD" }},
  webhookSecret: {{ source: "env", provider: "default", id: "FAKE_ZOHO_WEBHOOK_SECRET" }},
  dmPolicy: "pairing",
  groupPolicy: "allowlist",
  groupAllowFrom: [],
  allowFrom: [],
  requireMention: true,
  employeeMode: {{}},
  workScopes: {{}},
}};

const result = await runZohoCliqJson(account, ["status", "--check-auth"]);
assert.deepEqual(result.command.slice(-3), ["cliq", "status", "--check-auth"]);
assert.deepEqual(result.stdout.args, ["cliq", "status", "--check-auth"]);
assert.equal(result.stdout.env.account, "bot@example.com");
assert.equal(result.stdout.env.config, "/tmp/zoho-config.json");
assert.equal(result.stdout.env.tokenSeen, true);
assert.equal(result.stdout.env.webhookSeen, true);
assert.equal(result.stderr.includes("token-secret"), false);
assert.equal(result.stderr.includes("webhook-secret"), false);
assert.equal(result.stderr.includes("tok123"), false);
assert.equal(result.stderr.includes("auth789"), false);
assert.match(result.stderr, /<redacted>/);

assert.deepEqual(
  buildCliqSendArgs({{ account, to: "channel:C123", text: "hello" }}),
  ["send", "--text", "hello", "--network", "happy", "--channel-id", "C123"],
);
assert.deepEqual(
  buildCliqSendArgs({{ account, to: "user:U123", text: "hello" }}),
  ["send", "--text", "hello", "--network", "happy", "--user-id", "U123"],
);
assert.deepEqual(
  buildCliqSendArgs({{ account, to: "chat:CT1", text: "hello" }}),
  ["send", "--text", "hello", "--network", "happy", "--channel-id", "CT1"],
);
assert.deepEqual(
  buildCliqReplyArgs({{ account, to: "channel:C123", text: "hello", replyToId: "M10" }}),
  ["reply", "M10", "--text", "hello", "--network", "happy", "--channel-id", "C123"],
);
assert.deepEqual(
  buildCliqDeliveryArgs({{ account, to: "channel:C123", text: "hello", replyToId: "M11" }}),
  ["reply", "M11", "--text", "hello", "--network", "happy", "--channel-id", "C123"],
);
assert.deepEqual(
  buildCliqDeliveryArgs({{ account, to: "channel:C123", text: "hello", threadId: "T1" }}),
  ["thread-reply", "T1", "--text", "hello", "--network", "happy", "--channel-id", "C123"],
);
assert.deepEqual(
  buildCliqThreadReplyArgs({{ account, to: "chat:CT1", text: "thread", threadId: "T2" }}),
  ["thread-reply", "T2", "--text", "thread", "--network", "happy", "--chat-id", "CT1"],
);
assert.deepEqual(
  await sendCliqText({{ account, to: "channel:C123", text: "hello" }}),
  {{ messageId: "M123" }},
);
assert.deepEqual(
  await sendCliqText({{ account, to: "channel:C123", text: "reply", replyToId: "M33" }}),
  {{ messageId: "M123" }},
);
"""
    subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )


def test_openclaw_cliq_channel_outbound_adapter_runtime(tmp_path) -> None:
    fake_zoho = tmp_path / "fake-zoho.mjs"
    calls_file = tmp_path / "calls.jsonl"
    fake_zoho.write_text(
        """#!/usr/bin/env node
import fs from "node:fs";

const args = process.argv.slice(2);
fs.appendFileSync(process.env.FAKE_ZOHO_CALLS, `${JSON.stringify(args)}\\n`);

if (process.env.FAKE_ZOHO_MODE === "scope") {
  console.error(`missing_scope ZohoCliq.Messages.CREATE ZOHO_TOKEN_PASSWORD=${process.env.ZOHO_TOKEN_PASSWORD}`);
  process.exit(1);
}

let messageId = "MSEND";
if (args.includes("reply")) messageId = "MREPLY";
if (args.includes("thread-reply")) messageId = "MTHREAD";
console.log(JSON.stringify({ result: { messageId } }));
""",
        encoding="utf-8",
    )
    fake_zoho.chmod(0o755)

    script = """
import assert from "node:assert/strict";
import fs from "node:fs";
import { zohoCliqPlugin } from "./integrations/openclaw-channel-cliq/dist/src/channel.js";
import { ZohoCliqCommandError } from "./integrations/openclaw-channel-cliq/dist/src/zoho-cli.js";

const fakeZoho = __FAKE_ZOHO__;
const callsFile = __CALLS_FILE__;
process.env.FAKE_ZOHO_CALLS = callsFile;
process.env.FAKE_ZOHO_TOKEN_PASSWORD = "supersecret";

const cfg = {
  channels: {
    cliq: {
      accounts: {
        default: {
          cliPath: fakeZoho,
          network: "happy",
          tokenPassword: {
            source: "env",
            provider: "default",
            id: "FAKE_ZOHO_TOKEN_PASSWORD",
          },
        },
      },
    },
  },
};

assert.ok(zohoCliqPlugin.outbound?.sendText);
assert.equal(zohoCliqPlugin.outbound.deliveryMode, "direct");
assert.equal(zohoCliqPlugin.outbound.chunkerMode, "markdown");

const direct = await zohoCliqPlugin.outbound.sendText({
  cfg,
  accountId: "default",
  to: "channel:C123",
  text: "hello",
});
assert.equal(direct.channel, "cliq");
assert.equal(direct.messageId, "MSEND");
assert.equal(direct.conversationId, "channel:C123");

const reply = await zohoCliqPlugin.outbound.sendText({
  cfg,
  accountId: "default",
  to: "channel:C123",
  text: "reply",
  replyToId: "M1",
});
assert.equal(reply.messageId, "MREPLY");
assert.deepEqual(reply.meta, { replyToId: "M1", threadId: undefined });

const thread = await zohoCliqPlugin.outbound.sendText({
  cfg,
  accountId: "default",
  to: "channel:C123",
  text: "thread",
  threadId: "T9",
});
assert.equal(thread.messageId, "MTHREAD");
assert.deepEqual(thread.meta, { replyToId: undefined, threadId: "T9" });

const calls = fs.readFileSync(callsFile, "utf8").trim().split("\\n").map(JSON.parse);
assert.deepEqual(calls[0], [
  "cliq",
  "send",
  "--text",
  "hello",
  "--network",
  "happy",
  "--channel-id",
  "C123",
]);
assert.deepEqual(calls[1], [
  "cliq",
  "reply",
  "M1",
  "--text",
  "reply",
  "--network",
  "happy",
  "--channel-id",
  "C123",
]);
assert.deepEqual(calls[2], [
  "cliq",
  "thread-reply",
  "T9",
  "--text",
  "thread",
  "--network",
  "happy",
  "--channel-id",
  "C123",
]);

process.env.FAKE_ZOHO_MODE = "scope";
try {
  await zohoCliqPlugin.outbound.sendText({
    cfg,
    accountId: "default",
    to: "channel:C123",
    text: "blocked",
  });
  assert.fail("expected scope_missing");
} catch (error) {
  assert.ok(error instanceof ZohoCliqCommandError);
  assert.equal(error.kind, "scope_missing");
  assert.equal(error.stderr.includes("supersecret"), false);
}
"""
    script = script.replace("__FAKE_ZOHO__", json.dumps(str(fake_zoho))).replace(
        "__CALLS_FILE__", json.dumps(str(calls_file))
    )
    subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )


def test_openclaw_cliq_channel_zoho_cli_adapter_error_runtime(tmp_path) -> None:
    fake_zoho = tmp_path / "fake-zoho.mjs"
    fake_zoho.write_text(
        """#!/usr/bin/env node
const mode = process.env.FAKE_ZOHO_MODE;
if (mode === "auth") {
  console.error('{"status":"error","error":"not_logged_in"}');
  process.exit(1);
}
if (mode === "scope") {
  console.error("OAUTH_SCOPE_MISMATCH missing_scope ZohoCliq.Messages.READ");
  process.exit(1);
}
if (mode === "unsupported") {
  console.error("request_url_invalid endpoint is not supported");
  process.exit(1);
}
if (mode === "invalid") {
  console.log("{not-json");
  process.exit(0);
}
if (mode === "empty") {
  process.exit(0);
}
if (mode === "slow") {
  await new Promise((resolve) => setTimeout(resolve, 500));
  console.log(JSON.stringify({ ok: true }));
  process.exit(0);
}
console.error("generic failure");
process.exit(7);
""",
        encoding="utf-8",
    )
    fake_zoho.chmod(0o755)

    missing_zoho = tmp_path / "missing-zoho"
    script = f"""
import assert from "node:assert/strict";
import {{
  runZohoCliqJson,
  ZohoCliqCommandError,
}} from "./integrations/openclaw-channel-cliq/dist/src/zoho-cli.js";

const account = {{
  accountId: "default",
  enabled: true,
  cliPath: {json.dumps(str(fake_zoho))},
  network: "happy",
  tokenPassword: {{ source: "env", provider: "default", id: "FAKE_ZOHO_TOKEN_PASSWORD" }},
  webhookSecret: {{ source: "env", provider: "default", id: "FAKE_ZOHO_WEBHOOK_SECRET" }},
  dmPolicy: "pairing",
  groupPolicy: "allowlist",
  groupAllowFrom: [],
  allowFrom: [],
  requireMention: true,
  employeeMode: {{}},
  workScopes: {{}},
}};
process.env.FAKE_ZOHO_TOKEN_PASSWORD = "token-secret";
process.env.FAKE_ZOHO_WEBHOOK_SECRET = "webhook-secret";

async function expectKind(mode, expectedKind, expectedExitCode = 1, timeoutMs = 500) {{
  process.env.FAKE_ZOHO_MODE = mode;
  try {{
    await runZohoCliqJson(account, ["status"], {{ timeoutMs }});
    assert.fail(`expected ${{expectedKind}}`);
  }} catch (error) {{
    assert.ok(error instanceof ZohoCliqCommandError);
    assert.equal(error.kind, expectedKind);
    assert.equal(error.exitCode, expectedExitCode);
    assert.equal(error.stderr.includes("token-secret"), false);
    assert.equal(error.stderr.includes("webhook-secret"), false);
  }}
}}

await expectKind("auth", "auth_missing");
await expectKind("scope", "scope_missing");
await expectKind("unsupported", "unsupported_endpoint");
await expectKind("invalid", "invalid_json", 0);
await expectKind("empty", "invalid_json", 0);
await expectKind("slow", "timeout", 1, 20);

try {{
  await runZohoCliqJson({{ ...account, cliPath: {json.dumps(str(missing_zoho))} }}, ["status"], {{ timeoutMs: 200 }});
  assert.fail("expected missing command");
}} catch (error) {{
  assert.ok(error instanceof ZohoCliqCommandError);
  assert.equal(error.kind, "command_not_found");
  assert.equal(error.exitCode, 1);
}}
"""
    subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
