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
        "webhookPath",
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
    assert properties["webhookPath"] == {"type": "string", "minLength": 1}
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
    assert definitions["account"]["properties"]["webhookPath"] == {
        "type": "string",
        "minLength": 1,
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
    assert ui_hints["webhookPath"]["advanced"] is True
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
            read("src/constants.ts"),
            read("src/employee-policy.ts"),
            read("src/inbound.ts"),
            read("src/lifecycle.ts"),
            read("src/native-dispatch.ts"),
            read("src/observability.ts"),
            read("src/polling.ts"),
            read("src/privacy.ts"),
            read("src/session.ts"),
            read("src/security.ts"),
            read("src/setup-wizard.ts"),
            read("src/status.ts"),
            read("src/turn-ledger.ts"),
            read("src/webhook.ts"),
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
        "listCliqChats",
        "fetchCliqContext",
        "buildCliqContextArgs",
        "normalizeCliqContextMessages",
        "normalizeCliqWatchMessages",
        "normalizeCliqInboundMessage",
        "pollCliqInboundOnce",
        "runCliqInboundLifecycle",
        "dispatchCliqEventToNativeOpenClaw",
        "createCliqNativeEventDispatcher",
        "buildCliqDiagnosticBundle",
        "redactCliqDiagnosticObject",
        "resolveCliqPrivacyRetentionPolicy",
        "describeCliqRateLimitDiagnostics",
        "runtime.turn.run",
        "resolveAgentRoute",
        "sendTextMediaPayload",
        "runCliqInboundTurn",
        "createCliqTurnLedgerStore",
        "buildCliqTurnConversationKey",
        "resolveCliqChannelStatusSummary",
        "resolveCliqChannelCapabilitySummary",
        "resolveCliqRoutingDiagnostic",
        "setCliqStatusReaction",
        "markCliqMessageRead",
        "buildCliqStatusReactArgs",
        "buildCliqMarkReadArgs",
        "CliqInboundDedupeStore",
        "evaluateCliqPollingEventSecurity",
        "registerHttpRoute",
        'auth: "plugin"',
        "registerCliqWebhookRoutes",
        "processCliqWebhookPayload",
        "normalizeCliqWebhookPayload",
        "verifyCliqWebhookSecret",
        "X-Cliq-Webhook-Secret".lower(),
        "openclaw/plugin-sdk/webhook-ingress",
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
        "webhookPath",
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
        "dist/src/inbound.js",
        "dist/src/lifecycle.js",
        "dist/src/native-dispatch.js",
        "dist/src/observability.js",
        "dist/src/polling.js",
        "dist/src/privacy.js",
        "dist/src/session.js",
        "dist/src/security.js",
        "dist/src/setup-wizard.js",
        "dist/src/status.js",
        "dist/src/turn-ledger.js",
        "dist/src/webhook.js",
        "dist/src/zoho-cli.js",
    ]:
        assert (PLUGIN_ROOT / path).exists(), f"missing build output: {path}"

    built = "\n".join(
        [
            read("dist/index.js"),
            read("dist/setup-entry.js"),
            read("dist/src/channel.js"),
            read("dist/src/employee-policy.js"),
            read("dist/src/inbound.js"),
            read("dist/src/lifecycle.js"),
            read("dist/src/native-dispatch.js"),
            read("dist/src/observability.js"),
            read("dist/src/polling.js"),
            read("dist/src/privacy.js"),
            read("dist/src/session.js"),
            read("dist/src/security.js"),
            read("dist/src/setup-wizard.js"),
            read("dist/src/status.js"),
            read("dist/src/turn-ledger.js"),
            read("dist/src/webhook.js"),
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


def test_openclaw_cliq_channel_status_diagnostics_runtime() -> None:
    script = """
import assert from "node:assert/strict";
import {
  resolveCliqChannelCapabilitySummary,
  resolveCliqChannelStatusSummary,
  resolveCliqRoutingDiagnostic,
} from "./integrations/openclaw-channel-cliq/dist/src/status.js";

const cfg = {
  channels: {
    cliq: {
      accounts: {
        default: {
          accountEmail: { source: "env", provider: "default", id: "ZOHO_ACCOUNT" },
          configPath: { source: "env", provider: "default", id: "ZOHO_CONFIG" },
          network: "happy",
          webhookSecret: { source: "env", provider: "default", id: "ZOHO_CLIQ_WEBHOOK_SECRET" },
          webhookPath: "/webhooks/cliq",
          dmPolicy: "allowlist",
          allowFrom: ["U2"],
          groupPolicy: "allowlist",
          groupAllowFrom: ["channel:C123"],
          requireMention: true,
          employeeMode: { enabled: true, scopeProfile: "default", policy: "strict" },
          workScopes: { default: { role: "employee", allowedSurfaces: ["cliq", "mail"], crm: "read_only" } },
        },
      },
    },
  },
};

const status = resolveCliqChannelStatusSummary({ cfg });
assert.equal(status.channel, "cliq");
assert.equal(status.enabled, true);
assert.equal(status.configured, true);
assert.deepEqual(status.setupStates, []);
assert.equal(status.diagnostics.capabilities.inboundWebhook, true);
assert.equal(status.diagnostics.capabilities.turnLedger, true);
assert.equal(status.diagnostics.capabilities.observabilityBundle, true);
assert.equal(status.diagnostics.capabilities.rateLimitDiagnostics, true);
assert.equal(status.diagnostics.productionReadiness, "pending_live_verification");
assert.deepEqual(status.diagnostics.blockers, ["live_verification_pending"]);
assert.equal(status.diagnostics.observability.rateLimits.webhook.maxRequests, 120);
assert.equal(status.diagnostics.observability.privacy.rawMessageBodies, "never_in_diagnostics");
assert(status.statusLines.some((line) => line.includes("turn ledger")));
assert(status.diagnostics.implementedSlices.includes("cliq-channel-413"));
assert(status.diagnostics.implementedSlices.includes("cliq-channel-409"));
assert(status.diagnostics.implementedSlices.includes("cliq-channel-410"));
assert(status.diagnostics.implementedSlices.includes("cliq-channel-417"));
assert(status.diagnostics.implementedSlices.includes("cliq-channel-415"));
assert(status.diagnostics.implementedSlices.includes("cliq-channel-411"));
assert(status.diagnostics.implementedSlices.includes("cliq-channel-412"));
assert(status.diagnostics.implementedSlices.includes("cliq-channel-418"));
assert(status.diagnostics.smokeChecks.includes("ops/scripts/openclaw_cliq_live_smoke.sh"));
assert.equal(status.diagnostics.nextSlice, "public-bot-callback-verification");

const capabilities = resolveCliqChannelCapabilitySummary({ cfg });
assert.equal(capabilities.nativeMessageSurface, true);
assert.equal(capabilities.nativeApprovalSurface, true);
assert.equal(capabilities.customSendTools, false);
assert.equal(capabilities.capabilities.nativeAgentDispatch, true);
assert.equal(capabilities.capabilities.redactedAuditEvents, true);

const route = resolveCliqRoutingDiagnostic({
  cfg,
  target: "cliq:channel:C123:thread:T9",
  replyToId: "M1",
});
assert.equal(route.normalized, "channel:C123");
assert.equal(route.chatType, "channel");
assert.equal(route.nativeId, "C123");
assert.equal(route.threadId, "T9");
assert.equal(route.sessionRoute.to, "channel:C123");
"""
    subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )


def test_openclaw_cliq_channel_observability_privacy_runtime() -> None:
    script = """
import assert from "node:assert/strict";
import { resolveCliqAccount } from "./integrations/openclaw-channel-cliq/dist/src/config.js";
import { normalizeCliqInboundMessage } from "./integrations/openclaw-channel-cliq/dist/src/inbound.js";
import {
  buildCliqAuditEvent,
  buildCliqCorrelationId,
  buildCliqDiagnosticBundle,
  describeCliqRateLimitDiagnostics,
  describeCliqReleaseIntegrityDiagnostics,
} from "./integrations/openclaw-channel-cliq/dist/src/observability.js";
import {
  CLIQ_REDACTED,
  redactCliqDiagnosticObject,
  resolveCliqPrivacyRetentionPolicy,
} from "./integrations/openclaw-channel-cliq/dist/src/privacy.js";
import { createCliqTurnLedgerStore } from "./integrations/openclaw-channel-cliq/dist/src/turn-ledger.js";
import { normalizeCliqWebhookPayload } from "./integrations/openclaw-channel-cliq/dist/src/webhook.js";

const cfg = {
  channels: {
    cliq: {
      accounts: {
        default: {
          network: "happy",
          webhookSecret: { source: "env", provider: "default", id: "ZOHO_CLIQ_WEBHOOK_SECRET" },
          tokenPassword: { source: "env", provider: "default", id: "ZOHO_TOKEN_PASSWORD" },
          groupPolicy: "allowlist",
          groupAllowFrom: ["channel:C123"],
        },
      },
    },
  },
};
const account = resolveCliqAccount(cfg, "default");
const event = normalizeCliqInboundMessage({
  accountId: "default",
  network: "happy",
  chat: { channelId: "C123", chatType: "channel" },
  message: {
    id: "M1",
    text: "@bot this body must not appear in diagnostics",
    user: { id: "U2", name: "Alice" },
  },
  mentionMatchers: [/@bot\\b/i],
});
assert.ok(event);
assert.equal(event.chatId, undefined);
assert.equal(event.channelId, "C123");
const webhookNormalized = normalizeCliqWebhookPayload({
  account,
  payload: {
    handler: "mention",
    message: { id: "M-WEBHOOK", text: "@bot webhook smoke" },
    user: { id: "U2" },
    chat: { channelId: "C123", chatType: "channel" },
  },
  mentionMatchers: [/@bot\\b/i],
});
assert.ok(webhookNormalized.event);
assert.equal(webhookNormalized.event.chatId, undefined);
assert.equal(webhookNormalized.event.channelId, "C123");
assert.equal(webhookNormalized.event.messageId, "M-WEBHOOK");
const ledger = createCliqTurnLedgerStore({ now: () => Date.parse("2026-05-05T00:00:00Z") });
const begin = ledger.begin(event);
assert.equal(begin.accepted, true);
const failedTurn = ledger.fail(event, new Error("dispatch failed"));
const audit = buildCliqAuditEvent({
  kind: "webhook_ingress",
  outcome: "denied",
  account,
  source: "webhook",
  handlerKind: "mention",
  reason: "mention_required",
  event,
  security: {
    reasonCode: "mention_required",
    webhookSecret: "SHOULD_NOT_LEAK",
    rawSignature: "SHOULD_NOT_LEAK_EITHER",
    message: { text: "raw body leak" },
  },
  turn: failedTurn,
  now: () => new Date("2026-05-05T00:00:01Z"),
});
const auditText = JSON.stringify(audit);
assert.match(audit.correlationId, /^cliq-[0-9a-f]{16}$/);
assert.equal(audit.event.textLength, event.text.length);
assert(!auditText.includes(event.text));
assert(!auditText.includes("SHOULD_NOT_LEAK"));
assert(!auditText.includes("raw body leak"));
assert(auditText.includes(CLIQ_REDACTED));

const bundle = buildCliqDiagnosticBundle({
  account,
  event,
  turn: failedTurn,
  nativeDispatch: {
    target: "channel:C123",
    deliveryCount: 0,
    tokenPassword: "SHOULD_NOT_LEAK",
    payload: "@bot this body must not appear in diagnostics",
  },
  source: "webhook",
  now: () => new Date("2026-05-05T00:00:02Z"),
});
const bundleText = JSON.stringify(bundle);
assert.equal(bundle.rateLimits.webhook.maxRequests, 120);
assert.equal(bundle.privacy.rawMessageBodies, "never_in_diagnostics");
assert.equal(bundle.privacy.deadLetterRetention.replayDefault, "blocked");
assert.equal(bundle.releaseIntegrity.npmExpectedIntegrity, "<filled-at-release>");
assert(!bundleText.includes(event.text));
assert(!bundleText.includes("SHOULD_NOT_LEAK"));

const redacted = redactCliqDiagnosticObject({
  tokenPassword: "secret",
  messageText: "body",
  messageId: "M1",
  nested: { authorization: "bearer secret" },
});
assert.equal(redacted.tokenPassword, CLIQ_REDACTED);
assert.equal(redacted.messageText, CLIQ_REDACTED);
assert.equal(redacted.messageId, "M1");
assert.equal(redacted.nested.authorization, CLIQ_REDACTED);

const firstCorrelation = buildCliqCorrelationId({
  accountId: event.accountId,
  network: event.network,
  source: "webhook",
  messageId: event.messageId,
  peerId: event.peerId,
  dedupeKey: event.dedupeKey,
});
const secondCorrelation = buildCliqCorrelationId({
  accountId: event.accountId,
  network: event.network,
  source: "webhook",
  messageId: event.messageId,
  peerId: event.peerId,
  dedupeKey: event.dedupeKey,
});
assert.equal(firstCorrelation, secondCorrelation);
assert.equal(describeCliqRateLimitDiagnostics().webhook.bodyTimeoutMs, 5000);
assert.equal(resolveCliqPrivacyRetentionPolicy().turnLedgerRetention.containsRawBodies, false);
assert.equal(describeCliqReleaseIntegrityDiagnostics().localLinkedDevelopmentAllowed, true);
"""
    subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )


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
  buildCliqMarkReadArgs,
  buildCliqReplyArgs,
  buildCliqSendArgs,
  buildCliqStatusReactArgs,
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
  buildCliqStatusReactArgs({{ account, messageId: "M77", status: "thinking", chatId: "CHAT1" }}),
  ["status-react", "M77", "--status", "thinking", "--network", "happy", "--chat-id", "CHAT1", "--clear-known"],
);
assert.deepEqual(
  buildCliqStatusReactArgs({{ account, messageId: "M77", status: "done", channelId: "C123", clearKnown: false }}),
  ["status-react", "M77", "--status", "done", "--network", "happy", "--channel-id", "C123", "--keep-existing"],
);
assert.deepEqual(
  buildCliqMarkReadArgs({{ account, messageId: "M77", chatId: "CHAT1" }}),
  ["mark-read", "M77", "--network", "happy", "--chat-id", "CHAT1"],
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


def test_openclaw_cliq_channel_inbound_polling_normalization_runtime(tmp_path) -> None:
    fake_zoho = tmp_path / "fake-zoho.mjs"
    fake_zoho.write_text(
        """#!/usr/bin/env node
const args = process.argv.slice(2);
if (args[0] !== "cliq") {
  console.error("expected cliq command");
  process.exit(7);
}

if (args[1] === "chats") {
  console.log(JSON.stringify({
    data: {
      chats: [
        { id: "CHAT-1", chat_type: "channel", unread_message_count: 2, channel_id: "C123" },
        { id: "CHAT-2", chat_type: "dm", unread_message_count: 1 }
      ]
    }
  }));
  process.exit(0);
}

if (args[1] === "context") {
  const chatId = args[args.indexOf("--chat-id") + 1];
  if (chatId === "CHAT-1") {
    console.log(JSON.stringify({
      chatId,
      channelId: "C123",
      messages: [
        { messageId: "M100", senderId: "U1", senderName: "Alice", text: "@bot hello", timestamp: 1710000000000, raw: { message_id: "M100", thread_id: "TH-7" } },
        { messageId: "M101", senderId: "U1", text: "forgot mention", timestamp: 1710000001000, raw: { message_id: "M101" } },
        { messageId: "SELF", senderId: "BOT", text: "@bot ignore self", isSelf: true }
      ]
    }));
    process.exit(0);
  }
  console.log(JSON.stringify({
    chatId,
    messages: [
      { messageId: "DM1", chatType: "dm", senderId: "U2", text: "direct hello", timestamp: "2026-05-05T04:00:00Z" }
    ]
  }));
  process.exit(0);
}

console.log(JSON.stringify({ ok: true, args }));
""",
        encoding="utf-8",
    )
    fake_zoho.chmod(0o755)

    script = f"""
import assert from "node:assert/strict";
import {{
  buildCliqChatsArgs,
  buildCliqContextArgs,
  fetchCliqContext,
  listCliqChats,
}} from "./integrations/openclaw-channel-cliq/dist/src/zoho-cli.js";
import {{
  buildCliqInboundDedupeKey,
  CliqInboundDedupeStore,
  evaluateCliqPollingEventSecurity,
  normalizeCliqWatchMessages,
}} from "./integrations/openclaw-channel-cliq/dist/src/inbound.js";
import {{
  pollCliqInboundOnce,
}} from "./integrations/openclaw-channel-cliq/dist/src/polling.js";

const account = {{
  accountId: "default",
  enabled: true,
  cliPath: {json.dumps(str(fake_zoho))},
  network: "happy",
  dmPolicy: "pairing",
  groupPolicy: "allowlist",
  groupAllowFrom: ["channel:C123"],
  allowFrom: ["U2"],
  requireMention: true,
  employeeMode: {{}},
  workScopes: {{ default: {{ allowedSurfaces: ["cliq"], allowedIntents: ["cliq.reply"] }} }},
}};

assert.deepEqual(
  buildCliqChatsArgs({{ account, limit: 25, unreadOnly: true, excludeReactedBySelf: true }}),
  ["chats", "--limit", "25", "--network", "happy", "--unread-only", "--exclude-reacted-by-self"],
);
assert.deepEqual(
  buildCliqContextArgs({{
    account,
    channelId: "C123",
    limit: 30,
    before: 0,
    after: 2,
  }}),
  [
    "context",
    "--limit",
    "30",
    "--network",
    "happy",
    "--channel-id",
    "C123",
    "--before",
    "0",
    "--after",
    "2",
  ],
);

const chats = await listCliqChats({{ account, limit: 25 }});
assert.equal(chats.chats.length, 2);
assert.equal(chats.chats[0].id, "CHAT-1");

const contextPayload = await fetchCliqContext({{
  account,
  chatId: "CHAT-1",
  limit: 30,
}});
assert.equal(contextPayload.chatId, "CHAT-1");
assert.ok(Array.isArray(contextPayload.messages));

const events = normalizeCliqWatchMessages({{
  accountId: "default",
  network: "happy",
  payload: contextPayload,
  defaultChannelId: "C123",
  mentionMatchers: [/@bot\\b/i],
}});
assert.equal(events.length, 2);
assert.equal(events[0].chatId, "CHAT-1");
assert.equal(events[0].channelId, "C123");
assert.equal(events[0].threadId, "TH-7");
assert.equal(events[0].peerId, "channel:C123");
assert.equal(events[0].mentioned, true);
assert.equal(
  events[0].dedupeKey,
  buildCliqInboundDedupeKey({{
    accountId: "default",
    network: "happy",
    peerId: "channel:C123",
    messageId: "M100",
  }}),
);
assert.equal(
  evaluateCliqPollingEventSecurity({{ account, event: events[0] }}).allowed,
  true,
);
assert.equal(
  evaluateCliqPollingEventSecurity({{ account, event: events[1] }}).allowed,
  false,
);

const dedupe = new CliqInboundDedupeStore(100);
const firstPass = dedupe.takeNew(events);
const secondPass = dedupe.takeNew(events);
assert.equal(firstPass.length, 2);
assert.equal(secondPass.length, 0);

const dispatched = [];
const pollingDedupe = new CliqInboundDedupeStore(100);
const firstPoll = await pollCliqInboundOnce({{
  account,
  dedupe: pollingDedupe,
  mentionMatchers: [/@bot\\b/i],
  onEvent: (event) => dispatched.push(event.messageId),
}});
assert.deepEqual(firstPoll.events.map((event) => event.messageId), ["M100", "DM1"]);
assert.deepEqual(dispatched, ["M100", "DM1"]);
assert.equal(firstPoll.dispatchedCount, 2);
assert.equal(firstPoll.skipped.some((item) => item.reason === "security_denied" && item.securityReasonCode === "mention_required"), true);
assert.equal(firstPoll.skipped.some((item) => item.reason === "invalid_message"), true);

const secondPoll = await pollCliqInboundOnce({{
  account,
  dedupe: pollingDedupe,
  mentionMatchers: [/@bot\\b/i],
  onEvent: (event) => dispatched.push(event.messageId),
}});
assert.equal(secondPoll.events.length, 0);
assert.equal(secondPoll.dispatchedCount, 0);
assert.equal(secondPoll.skipped.filter((item) => item.reason === "duplicate").length, 3);
"""
    subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )


def test_openclaw_cliq_channel_lifecycle_runtime(tmp_path) -> None:
    fake_zoho = tmp_path / "fake-zoho.mjs"
    calls_file = tmp_path / "calls.jsonl"
    fake_zoho.write_text(
        """#!/usr/bin/env node
import fs from "node:fs";

const args = process.argv.slice(2);
fs.appendFileSync(process.env.FAKE_ZOHO_CALLS, `${JSON.stringify(args)}\\n`);
if (args[0] !== "cliq") {
  console.error("expected cliq command");
  process.exit(7);
}
if (args[1] === "mark-read" && process.env.FAKE_MARK_READ_FAIL === "1") {
  console.error(JSON.stringify({ error: "not_supported", secret: process.env.ZOHO_CLIQ_WEBHOOK_SECRET }));
  process.exit(1);
}
console.log(JSON.stringify({ ok: true, args }));
""",
        encoding="utf-8",
    )
    fake_zoho.chmod(0o755)

    script = f"""
import assert from "node:assert/strict";
import fs from "node:fs";
import {{ runCliqInboundLifecycle }} from "./integrations/openclaw-channel-cliq/dist/src/lifecycle.js";

process.env.FAKE_ZOHO_CALLS = {json.dumps(str(calls_file))};
process.env.FAKE_ZOHO_WEBHOOK_SECRET = "webhook-secret";

const account = {{
  accountId: "default",
  enabled: true,
  cliPath: {json.dumps(str(fake_zoho))},
  network: "happy",
  webhookSecret: {{ source: "env", provider: "default", id: "FAKE_ZOHO_WEBHOOK_SECRET" }},
  dmPolicy: "pairing",
  groupPolicy: "allowlist",
  groupAllowFrom: [],
  allowFrom: [],
  requireMention: true,
  employeeMode: {{}},
  workScopes: {{}},
}};
const event = {{
  channel: "cliq",
  accountId: "default",
  network: "happy",
  chatType: "channel",
  peerId: "channel:C123",
  nativePeerId: "C123",
  chatId: "CHAT1",
  channelId: "C123",
  messageId: "M1",
  senderId: "U2",
  text: "@bot hello",
  mentioned: true,
  dedupeKey: "cliq:default:happy:channel:c123:m1",
  raw: {{}},
}};

const dispatched = [];
const success = await runCliqInboundLifecycle({{
  account,
  event,
  onEvent: (inbound) => dispatched.push(inbound.messageId),
}});
assert.equal(success.dispatched, true);
assert.deepEqual(dispatched, ["M1"]);
assert.deepEqual(
  success.actions.map((action) => [action.kind, action.status ?? "", action.ok]),
  [
    ["status", "received", true],
    ["status", "thinking", true],
    ["mark_read", "", true],
    ["status", "done", true],
  ],
);

const successCalls = fs.readFileSync(process.env.FAKE_ZOHO_CALLS, "utf8")
  .trim()
  .split("\\n")
  .map((line) => JSON.parse(line));
assert.deepEqual(successCalls[0], ["cliq", "status-react", "M1", "--status", "received", "--network", "happy", "--chat-id", "CHAT1", "--clear-known"]);
assert.deepEqual(successCalls[1], ["cliq", "status-react", "M1", "--status", "thinking", "--network", "happy", "--chat-id", "CHAT1", "--clear-known"]);
assert.deepEqual(successCalls[2], ["cliq", "mark-read", "M1", "--network", "happy", "--chat-id", "CHAT1"]);
assert.deepEqual(successCalls[3], ["cliq", "status-react", "M1", "--status", "done", "--network", "happy", "--chat-id", "CHAT1", "--clear-known"]);

fs.writeFileSync(process.env.FAKE_ZOHO_CALLS, "");
process.env.FAKE_MARK_READ_FAIL = "1";
const readFailure = await runCliqInboundLifecycle({{
  account,
  event: {{ ...event, messageId: "M2", dedupeKey: "m2" }},
  onEvent: () => undefined,
}});
assert.equal(readFailure.dispatched, true);
assert.equal(readFailure.actions.find((action) => action.kind === "mark_read").ok, false);
assert.equal(readFailure.actions.find((action) => action.kind === "mark_read").errorKind, "unsupported_endpoint");
assert.equal(readFailure.actions.at(-1).status, "done");
process.env.FAKE_MARK_READ_FAIL = "";

fs.writeFileSync(process.env.FAKE_ZOHO_CALLS, "");
await assert.rejects(
  () => runCliqInboundLifecycle({{
    account,
    event: {{ ...event, messageId: "M3", dedupeKey: "m3" }},
    onEvent: () => {{
      throw new Error("dispatch failed");
    }},
  }}),
  /dispatch failed/,
);
const failureCalls = fs.readFileSync(process.env.FAKE_ZOHO_CALLS, "utf8")
  .trim()
  .split("\\n")
  .map((line) => JSON.parse(line));
assert.equal(failureCalls.at(-1)[2], "M3");
assert.deepEqual(failureCalls.at(-1).slice(0, 5), ["cliq", "status-react", "M3", "--status", "failed"]);
"""
    subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )


def test_openclaw_cliq_channel_turn_ledger_runtime() -> None:
    script = """
import assert from "node:assert/strict";
import {
  buildCliqTurnConversationKey,
  createCliqTurnLedgerStore,
  runCliqInboundTurn,
} from "./integrations/openclaw-channel-cliq/dist/src/turn-ledger.js";

let now = Date.parse("2026-05-05T00:00:00Z");
const ledger = createCliqTurnLedgerStore({
  maxAttempts: 1,
  now: () => now,
});
const account = {
  accountId: "default",
  enabled: true,
  cliPath: "zoho",
  network: "happy",
  dmPolicy: "pairing",
  groupPolicy: "allowlist",
  groupAllowFrom: [],
  allowFrom: [],
  requireMention: true,
  employeeMode: {},
  workScopes: {},
};
const baseEvent = {
  channel: "cliq",
  accountId: "default",
  network: "happy",
  chatType: "channel",
  peerId: "channel:C123",
  nativePeerId: "C123",
  chatId: "CHAT1",
  channelId: "C123",
  messageId: "M1",
  senderId: "U2",
  text: "@bot hello",
  mentioned: true,
  dedupeKey: "account:default:network:happy:peer:channel:c123:message:m1",
  raw: {},
};

assert.equal(
  buildCliqTurnConversationKey(baseEvent),
  "account:default:network:happy:conversation:chat1",
);

let releaseActive;
const active = runCliqInboundTurn({
  account,
  event: baseEvent,
  turnLedger: ledger,
  lifecycle: false,
  onEvent: () => new Promise((resolve) => {
    releaseActive = resolve;
  }),
});

const burstEvent = {
  ...baseEvent,
  messageId: "M2",
  dedupeKey: "account:default:network:happy:peer:channel:c123:message:m2",
};
const coalesced = await runCliqInboundTurn({
  account,
  event: burstEvent,
  turnLedger: ledger,
  lifecycle: false,
  onEvent: () => {
    throw new Error("must not dispatch coalesced event");
  },
});
assert.equal(coalesced.skipped, true);
assert.equal(coalesced.skipReason, "conversation_active");
assert.equal(coalesced.turn.state, "coalesced");
assert.equal(ledger.get(baseEvent).coalescedCount, 1);

releaseActive();
const completed = await active;
assert.equal(completed.dispatched, true);
assert.equal(completed.turn.state, "completed");

const duplicate = await runCliqInboundTurn({
  account,
  event: baseEvent,
  turnLedger: ledger,
  lifecycle: false,
  onEvent: () => {
    throw new Error("must not dispatch duplicate event");
  },
});
assert.equal(duplicate.skipped, true);
assert.equal(duplicate.skipReason, "duplicate_event");
assert.equal(duplicate.turn.state, "completed");

const failingEvent = {
  ...baseEvent,
  messageId: "M3",
  dedupeKey: "account:default:network:happy:peer:channel:c123:message:m3",
};
const failed = await runCliqInboundTurn({
  account,
  event: failingEvent,
  turnLedger: ledger,
  lifecycle: false,
  onEvent: () => {
    throw new Error("dispatch failed");
  },
});
assert.equal(failed.dispatched, false);
assert.equal(failed.turn.state, "dead_letter");
assert.equal(failed.turn.deadLetterReason, "max_attempts_exhausted");
assert.match(failed.error, /dispatch failed/);

const deadLetterReplay = await runCliqInboundTurn({
  account,
  event: failingEvent,
  turnLedger: ledger,
  lifecycle: false,
  onEvent: () => {
    throw new Error("must not dispatch dead-letter replay");
  },
});
assert.equal(deadLetterReplay.skipped, true);
assert.equal(deadLetterReplay.skipReason, "dead_lettered");
assert.equal(deadLetterReplay.turn.state, "dead_letter");
"""
    subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )


def test_openclaw_cliq_channel_webhook_inbound_runtime(tmp_path) -> None:
    fake_zoho = tmp_path / "fake-zoho.mjs"
    fake_zoho.write_text(
        """#!/usr/bin/env node
const args = process.argv.slice(2);
if (args[0] !== "cliq") {
  console.error("expected cliq command");
  process.exit(7);
}
console.log(JSON.stringify({ ok: true, args }));
""",
        encoding="utf-8",
    )
    fake_zoho.chmod(0o755)

    script = """
import assert from "node:assert/strict";
import { resolveCliqAccount } from "./integrations/openclaw-channel-cliq/dist/src/config.js";
import { CliqInboundDedupeStore } from "./integrations/openclaw-channel-cliq/dist/src/inbound.js";
import {
  listCliqWebhookRoutePaths,
  normalizeCliqWebhookPath,
  normalizeCliqWebhookPayload,
  parseCliqWebhookPayload,
  processCliqWebhookPayload,
  verifyCliqWebhookSecret,
} from "./integrations/openclaw-channel-cliq/dist/src/webhook.js";
import { createCliqTurnLedgerStore } from "./integrations/openclaw-channel-cliq/dist/src/turn-ledger.js";

process.env.FAKE_ZOHO_WEBHOOK_SECRET = "webhook-secret";
process.env.OTHER_ZOHO_WEBHOOK_SECRET = "other-secret";

const cfg = {
  channels: {
    cliq: {
      accounts: {
        default: {
          network: "happy",
          cliPath: __FAKE_ZOHO__,
          webhookSecret: {
            source: "env",
            provider: "default",
            id: "FAKE_ZOHO_WEBHOOK_SECRET",
          },
          webhookPath: "webhooks/cliq",
          dmPolicy: "allowlist",
          allowFrom: ["U2"],
          groupPolicy: "allowlist",
          groupAllowFrom: ["channel:C123"],
          requireMention: true,
        },
      },
    },
  },
};
const account = resolveCliqAccount(cfg, "default");

assert.equal(normalizeCliqWebhookPath("webhooks/cliq?debug=1"), "/webhooks/cliq");
assert.deepEqual(listCliqWebhookRoutePaths(cfg), ["/webhooks/cliq"]);

const verified = await verifyCliqWebhookSecret({
  cfg,
  headers: { "x-cliq-webhook-secret": "webhook-secret" },
  env: process.env,
});
assert.equal(verified.ok, true);
assert.equal(verified.accountId, "default");
assert.equal((await verifyCliqWebhookSecret({
  cfg,
  headers: { "x-cliq-webhook-secret": "wrong" },
  env: process.env,
})).reason, "invalid_secret");

const multiCfg = {
  channels: {
    cliq: {
      accounts: {
        default: cfg.channels.cliq.accounts.default,
        other: {
          network: "happy",
          webhookSecret: {
            source: "env",
            provider: "default",
            id: "OTHER_ZOHO_WEBHOOK_SECRET",
          },
          webhookPath: "/webhooks/other",
        },
      },
    },
  },
};
assert.equal((await verifyCliqWebhookSecret({
  cfg: multiCfg,
  headers: { "x-cliq-webhook-secret": "other-secret" },
  env: process.env,
  webhookPath: "/webhooks/cliq",
})).reason, "invalid_secret");
assert.equal((await verifyCliqWebhookSecret({
  cfg: multiCfg,
  headers: { "x-cliq-webhook-secret": "other-secret" },
  env: process.env,
  webhookPath: "/webhooks/other",
})).accountId, "other");

const mentionPayload = parseCliqWebhookPayload(JSON.stringify({
  handler: "mention",
  message: { id: "M1", text: "@bot hello" },
  user: { id: "U2", name: "Alice" },
  chat: { channelId: "C123", chatType: "channel" },
}), "application/json");
const mentionNormalized = normalizeCliqWebhookPayload({
  account,
  payload: mentionPayload,
  mentionMatchers: [/@bot\\b/i],
});
assert.equal(mentionNormalized.envelope.handlerKind, "mention");
assert.equal(mentionNormalized.event.peerId, "channel:C123");
assert.equal(mentionNormalized.event.senderId, "U2");
assert.equal(mentionNormalized.event.mentioned, true);

const dedupe = new CliqInboundDedupeStore(100);
const turnLedger = createCliqTurnLedgerStore();
const dispatched = [];
const accepted = await processCliqWebhookPayload({
  cfg,
  account,
  payload: mentionPayload,
  dedupe,
  turnLedger,
  mentionMatchers: [/@bot\\b/i],
  onEvent: (event) => dispatched.push(event.messageId),
});
assert.equal(accepted.accepted, true);
assert.deepEqual(dispatched, ["M1"]);
assert.equal(accepted.turn.state, "completed");
assert.deepEqual(
  accepted.lifecycle.actions.map((action) => [action.kind, action.status ?? "", action.ok]),
  [
    ["status", "received", true],
    ["status", "thinking", true],
    ["mark_read", "", true],
    ["status", "done", true],
  ],
);

const duplicate = await processCliqWebhookPayload({
  cfg,
  account,
  payload: mentionPayload,
  dedupe,
  turnLedger,
  mentionMatchers: [/@bot\\b/i],
});
assert.equal(duplicate.accepted, false);
assert.equal(duplicate.reason, "duplicate");
assert.equal(duplicate.turn.state, "completed");

const failurePayload = {
  handler: "mention",
  message: { id: "MFAIL", text: "@bot fail" },
  user: { id: "U2", name: "Alice" },
  chat: { channelId: "C123", chatType: "channel" },
};
const failed = await processCliqWebhookPayload({
  cfg,
  account,
  payload: failurePayload,
  dedupe,
  turnLedger,
  mentionMatchers: [/@bot\\b/i],
  onEvent: () => {
    throw new Error("dispatch failed");
  },
});
assert.equal(failed.accepted, true);
assert.equal(failed.dispatched, false);
assert.equal(failed.turn.state, "dead_letter");
assert.equal(failed.turn.deadLetterReason, "max_attempts_exhausted");
assert.match(failed.dispatchError, /dispatch failed/);
assert.equal(failed.lifecycle.actions.at(-1).status, "failed");

const deadLetterReplay = await processCliqWebhookPayload({
  cfg,
  account,
  payload: failurePayload,
  dedupe,
  turnLedger,
  mentionMatchers: [/@bot\\b/i],
});
assert.equal(deadLetterReplay.accepted, false);
assert.equal(deadLetterReplay.reason, "dead_lettered");
assert.equal(deadLetterReplay.turn.state, "dead_letter");

const denied = await processCliqWebhookPayload({
  cfg,
  account,
  payload: {
    handler: "message",
    message: { id: "M2", text: "hello without mention" },
    user: { id: "U2" },
    chat: { channelId: "C123", chatType: "channel" },
  },
  dedupe,
  turnLedger,
});
assert.equal(denied.accepted, false);
assert.equal(denied.reason, "security_denied");
assert.equal(denied.security.reasonCode, "mention_required");

const direct = await processCliqWebhookPayload({
  cfg,
  account,
  payload: {
    handler: "message",
    message: { id: "DM1", text: "direct hello" },
    user: { id: "U2", name: "Alice" },
  },
  dedupe,
  turnLedger,
});
assert.equal(direct.accepted, true);
assert.equal(direct.event.chatType, "direct");
assert.equal(direct.event.peerId, "user:U2");

const unsupported = await processCliqWebhookPayload({
  cfg,
  account,
  payload: {
    handler: "call",
    message: { id: "CALL1", text: "ring" },
    user: { id: "U2" },
  },
  dedupe,
  turnLedger,
});
assert.equal(unsupported.accepted, false);
assert.equal(unsupported.reason, "unsupported_handler");
assert.equal(unsupported.handlerKind, "call");
"""
    script = script.replace("__FAKE_ZOHO__", json.dumps(str(fake_zoho)))
    subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )


def test_openclaw_cliq_channel_native_agent_dispatch_runtime(tmp_path) -> None:
    fake_zoho = tmp_path / "fake-zoho.mjs"
    fake_zoho.write_text(
        """#!/usr/bin/env node
const args = process.argv.slice(2);
if (args[0] !== "cliq") {
  console.error("expected cliq command");
  process.exit(7);
}

if (args[1] === "chats") {
  console.log(JSON.stringify({
    chats: [
      { id: "CHAT-POLL", chat_type: "channel", channel_id: "C456" }
    ]
  }));
  process.exit(0);
}

if (args[1] === "context") {
  console.log(JSON.stringify({
    chatId: "CHAT-POLL",
    channelId: "C456",
    messages: [
      { messageId: "MPOLL", senderId: "U2", text: "@bot poll me", timestamp: "2026-05-05T08:00:00Z" }
    ]
  }));
  process.exit(0);
}

console.log(JSON.stringify({ ok: true, args }));
""",
        encoding="utf-8",
    )
    fake_zoho.chmod(0o755)

    script = """
import assert from "node:assert/strict";
import { resolveCliqAccount } from "./integrations/openclaw-channel-cliq/dist/src/config.js";
import { CliqInboundDedupeStore } from "./integrations/openclaw-channel-cliq/dist/src/inbound.js";
import { dispatchCliqEventToNativeOpenClaw } from "./integrations/openclaw-channel-cliq/dist/src/native-dispatch.js";
import { pollCliqInboundOnce } from "./integrations/openclaw-channel-cliq/dist/src/polling.js";
import { createCliqTurnLedgerStore } from "./integrations/openclaw-channel-cliq/dist/src/turn-ledger.js";
import { processCliqWebhookPayload } from "./integrations/openclaw-channel-cliq/dist/src/webhook.js";

const cfg = {
  channels: {
    cliq: {
      accounts: {
        default: {
          network: "happy",
          cliPath: __FAKE_ZOHO__,
          dmPolicy: "allowlist",
          allowFrom: ["U2"],
          groupPolicy: "allowlist",
          groupAllowFrom: ["channel:C123", "channel:C456"],
          requireMention: true,
        },
      },
    },
  },
};
const account = resolveCliqAccount(cfg, "default");

function createFakeRuntime() {
  const sent = [];
  const records = [];
  let failDispatch = false;
  const runtime = {
    channel: {
      routing: {
        resolveAgentRoute: ({ channel, accountId, peer }) => ({
          agentId: "main",
          channel,
          accountId: accountId || "default",
          sessionKey: `agent:main:${channel}:${peer.kind}:${peer.id}`,
          mainSessionKey: "agent:main:main",
          lastRoutePolicy: "session",
          matchedBy: "default",
        }),
      },
      session: {
        resolveStorePath: (_store, { agentId }) => `/tmp/${agentId}.sessions.json`,
        recordInboundSession: async (params) => {
          records.push(params);
        },
      },
      reply: {
        dispatchReplyWithBufferedBlockDispatcher: async ({ dispatcherOptions }) => {
          if (failDispatch) throw new Error("native dispatch failed");
          await dispatcherOptions.deliver({ text: "agent reply" }, { kind: "final" });
          return { queuedFinal: true, counts: { final: 1, block: 0, tool: 0 } };
        },
      },
      outbound: {
        loadAdapter: async () => ({
          deliveryMode: "direct",
          sendText: async (ctx) => {
            const messageId = `OUT-${sent.length + 1}`;
            sent.push(ctx);
            return {
              channel: "cliq",
              messageId,
              conversationId: ctx.to,
              meta: { replyToId: ctx.replyToId, threadId: ctx.threadId },
            };
          },
        }),
      },
      turn: {
        buildContext: (params) => ({
          Body: params.message.body ?? params.message.rawBody,
          BodyForAgent: params.message.bodyForAgent ?? params.message.rawBody,
          RawBody: params.message.rawBody,
          CommandBody: params.message.commandBody ?? params.message.rawBody,
          BodyForCommands: params.message.commandBody ?? params.message.rawBody,
          From: params.from,
          To: params.reply.to,
          SessionKey: params.route.routeSessionKey,
          AccountId: params.route.accountId ?? params.accountId,
          MessageSid: params.messageId,
          ReplyToId: params.reply.replyToId,
          ChatType: params.conversation.kind,
          ConversationLabel: params.conversation.label,
          SenderId: params.sender.id,
          SenderName: params.sender.name ?? params.sender.displayLabel,
          Timestamp: params.timestamp,
          WasMentioned: params.access?.mentions?.wasMentioned,
          OriginatingChannel: params.channel,
          OriginatingTo: params.reply.originatingTo,
          MessageThreadId: params.reply.messageThreadId,
          NativeChannelId: params.reply.nativeChannelId,
          ExplicitDeliverRoute: params.extra?.ExplicitDeliverRoute,
          CommandAuthorized: false,
        }),
        run: async (params) => {
          const input = await params.adapter.ingest(params.raw);
          assert.ok(input);
          const resolved = await params.adapter.resolveTurn(input, {
            kind: "message",
            canStartAgentTurn: true,
          }, {});
          await resolved.recordInboundSession({
            storePath: resolved.storePath,
            sessionKey: resolved.ctxPayload.SessionKey ?? resolved.routeSessionKey,
            ctx: resolved.ctxPayload,
            createIfMissing: resolved.record?.createIfMissing,
            updateLastRoute: resolved.record?.updateLastRoute,
            onRecordError: resolved.record?.onRecordError ?? (() => {}),
          });
          const dispatchResult = await resolved.dispatchReplyWithBufferedBlockDispatcher({
            ctx: resolved.ctxPayload,
            cfg: resolved.cfg,
            dispatcherOptions: {
              deliver: async (payload, info) => {
                await resolved.delivery.deliver(payload, info);
              },
              onError: resolved.delivery.onError,
            },
          });
          const result = {
            admission: { kind: "dispatch" },
            dispatched: true,
            ctxPayload: resolved.ctxPayload,
            routeSessionKey: resolved.routeSessionKey,
            dispatchResult,
          };
          await params.adapter.onFinalize?.(result);
          return result;
        },
      },
    },
  };
  return {
    runtime,
    sent,
    records,
    setFailDispatch: (value) => {
      failDispatch = value;
    },
  };
}

const fake = createFakeRuntime();
const webhookDedupe = new CliqInboundDedupeStore(100);
const webhookLedger = createCliqTurnLedgerStore();
const nativeResults = [];
const mentionPayload = {
  handler: "mention",
  message: { id: "M1", text: "@bot hello", threadId: "T9" },
  user: { id: "U2", name: "Alice" },
  chat: { channelId: "C123", chatType: "channel" },
};

const accepted = await processCliqWebhookPayload({
  cfg,
  account,
  payload: mentionPayload,
  dedupe: webhookDedupe,
  turnLedger: webhookLedger,
  lifecycle: false,
  mentionMatchers: [/@bot\\b/i],
  onEvent: async (event, context) => {
    nativeResults.push(await dispatchCliqEventToNativeOpenClaw({
      cfg,
      runtime: fake.runtime,
      account: context.account,
      event,
      source: "webhook",
      handlerKind: context.handlerKind,
      security: context.security,
    }));
  },
});
assert.equal(accepted.accepted, true);
assert.equal(accepted.dispatched, true);
assert.equal(nativeResults.length, 1);
assert.equal(nativeResults[0].target, "channel:C123");
assert.equal(nativeResults[0].threadId, "T9");
assert.equal(nativeResults[0].deliveryCount, 1);
assert.deepEqual(nativeResults[0].messageIds, ["OUT-1"]);
assert.equal(fake.sent[0].to, "channel:C123");
assert.equal(fake.sent[0].replyToId, "M1");
assert.equal(fake.sent[0].threadId, "T9");
assert.equal(fake.records[0].updateLastRoute.channel, "cliq");
assert.equal(fake.records[0].updateLastRoute.to, "channel:C123");
assert.equal(fake.records[0].updateLastRoute.threadId, "T9");

const duplicate = await processCliqWebhookPayload({
  cfg,
  account,
  payload: mentionPayload,
  dedupe: webhookDedupe,
  turnLedger: webhookLedger,
  lifecycle: false,
  mentionMatchers: [/@bot\\b/i],
  onEvent: () => {
    throw new Error("duplicate must not dispatch");
  },
});
assert.equal(duplicate.accepted, false);
assert.equal(duplicate.reason, "duplicate");
assert.equal(fake.sent.length, 1);

const denied = await processCliqWebhookPayload({
  cfg,
  account,
  payload: {
    handler: "message",
    message: { id: "M2", text: "hello without mention" },
    user: { id: "U2" },
    chat: { channelId: "C123", chatType: "channel" },
  },
  dedupe: webhookDedupe,
  turnLedger: webhookLedger,
  lifecycle: false,
});
assert.equal(denied.accepted, false);
assert.equal(denied.reason, "security_denied");
assert.equal(fake.sent.length, 1);

fake.setFailDispatch(true);
const failed = await processCliqWebhookPayload({
  cfg,
  account,
  payload: {
    handler: "mention",
    message: { id: "MFAIL", text: "@bot fail" },
    user: { id: "U2" },
    chat: { channelId: "C123", chatType: "channel" },
  },
  dedupe: webhookDedupe,
  turnLedger: webhookLedger,
  lifecycle: false,
  mentionMatchers: [/@bot\\b/i],
  onEvent: async (event, context) => {
    await dispatchCliqEventToNativeOpenClaw({
      cfg,
      runtime: fake.runtime,
      account: context.account,
      event,
      source: "webhook",
      handlerKind: context.handlerKind,
      security: context.security,
    });
  },
});
assert.equal(failed.accepted, true);
assert.equal(failed.dispatched, false);
assert.equal(failed.turn.state, "dead_letter");
assert.match(failed.dispatchError, /native dispatch failed/);
assert.equal(fake.sent.length, 1);

fake.setFailDispatch(false);
const pollDedupe = new CliqInboundDedupeStore(100);
const pollLedger = createCliqTurnLedgerStore();
const pollResults = [];
const firstPoll = await pollCliqInboundOnce({
  cfg,
  account,
  dedupe: pollDedupe,
  turnLedger: pollLedger,
  lifecycle: false,
  mentionMatchers: [/@bot\\b/i],
  nativeDispatch: async (event, context) => {
    pollResults.push(await dispatchCliqEventToNativeOpenClaw({
      cfg,
      runtime: fake.runtime,
      account: context.account,
      event,
      source: "polling",
      security: context.security,
    }));
  },
});
assert.deepEqual(firstPoll.events.map((event) => event.messageId), ["MPOLL"]);
assert.equal(firstPoll.dispatchedCount, 1);
assert.equal(pollResults.length, 1);
assert.equal(pollResults[0].target, "channel:C456");
assert.equal(fake.sent.at(-1).to, "channel:C456");
assert.equal(fake.sent.at(-1).replyToId, "MPOLL");

const secondPoll = await pollCliqInboundOnce({
  cfg,
  account,
  dedupe: pollDedupe,
  turnLedger: pollLedger,
  lifecycle: false,
  mentionMatchers: [/@bot\\b/i],
  nativeDispatch: () => {
    throw new Error("duplicate polling event must not dispatch");
  },
});
assert.equal(secondPoll.events.length, 0);
assert.equal(secondPoll.dispatchedCount, 0);
assert.equal(fake.sent.length, 2);
"""
    script = script.replace("__FAKE_ZOHO__", json.dumps(str(fake_zoho)))
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
if (mode === "rate") {
  console.error('{"status":"error","error":"token_refresh_rate_limited","details":"too many requests"}');
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
await expectKind("rate", "rate_limited");
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
