import { buildChannelOutboundSessionRoute, createChannelPluginBase, createChatChannelPlugin, stripChannelTargetPrefix, stripTargetKindPrefix, } from "openclaw/plugin-sdk/channel-core";
import { implicitMentionKindWhen, matchesMentionWithExplicit, resolveInboundMentionDecision, } from "openclaw/plugin-sdk/channel-inbound";
import { applyCliqAccountConfig, cliqChannelConfigSchema, defaultCliqAccountId, describeCliqAccount, hasCliqAuthState, hasCliqConfiguredState, isCliqAccountConfigured, listCliqAccountIds, resolveCliqAccount, validateCliqSetupInput, } from "./config.js";
import { CLIQ_CHANNEL_ID, CLIQ_PLUGIN_ID } from "./constants.js";
import { cliqSetupWizard } from "./setup-wizard.js";
function normalizeCliqTarget(raw) {
    const stripped = stripTargetKindPrefix(stripChannelTargetPrefix(raw.trim(), "cliq", "zoho-cliq", "zoho"));
    return stripped || undefined;
}
const cliqCapabilities = {
    chatTypes: ["direct", "group", "channel", "thread"],
    reactions: true,
    reply: false,
    threads: true,
    nativeCommands: false,
    media: false,
    polls: false,
};
const cliqConfigAdapter = {
    listAccountIds: listCliqAccountIds,
    defaultAccountId: defaultCliqAccountId,
    resolveAccount: resolveCliqAccount,
    inspectAccount: (cfg, accountId) => describeCliqAccount(resolveCliqAccount(cfg, accountId)),
    isEnabled: (account) => account.enabled,
    disabledReason: () => "Zoho Cliq account is disabled in config.",
    isConfigured: isCliqAccountConfigured,
    unconfiguredReason: () => "Zoho Cliq needs zoho-cli auth, account metadata, or env/SecretRef credentials.",
    describeAccount: describeCliqAccount,
    resolveAllowFrom: ({ cfg, accountId }) => resolveCliqAccount(cfg, accountId).allowFrom,
    formatAllowFrom: ({ allowFrom }) => allowFrom.map(String),
    hasConfiguredState: hasCliqConfiguredState,
    hasPersistedAuthState: hasCliqAuthState,
    resolveDefaultTo: ({ cfg, accountId }) => resolveCliqAccount(cfg, accountId).defaultTo,
};
const cliqMessagingAdapter = {
    targetPrefixes: ["cliq", "zoho-cliq", "zoho"],
    normalizeTarget: normalizeCliqTarget,
    inferTargetChatType: ({ to }) => to.startsWith("user:") || to.startsWith("@") ? "direct" : "channel",
    parseExplicitTarget: ({ raw }) => {
        const target = normalizeCliqTarget(raw);
        if (!target)
            return null;
        if (target.startsWith("user:")) {
            return { to: target, chatType: "direct" };
        }
        if (target.startsWith("@")) {
            return { to: `user:${target.slice(1)}`, chatType: "direct" };
        }
        if (target.startsWith("channel:")) {
            return { to: target, chatType: "channel" };
        }
        return { to: `channel:${target}`, chatType: "channel" };
    },
    resolveSessionConversation: ({ kind, rawId }) => {
        const [baseConversationId, threadId] = rawId.split(":", 2);
        const id = threadId ? `${baseConversationId}:${threadId}` : rawId;
        return {
            id,
            threadId: threadId || null,
            baseConversationId,
            parentConversationCandidates: kind === "channel" || kind === "group" ? [baseConversationId] : [],
        };
    },
    resolveSessionTarget: ({ kind, id, threadId }) => {
        const prefix = kind === "channel" ? "channel" : "chat";
        return threadId ? `${prefix}:${id}:${threadId}` : `${prefix}:${id}`;
    },
    resolveOutboundSessionRoute: (params) => {
        const resolved = params.resolvedTarget;
        const normalized = resolved?.to || normalizeCliqTarget(params.target) || params.target;
        const chatType = resolved?.kind === "user"
            ? "direct"
            : resolved?.kind === "group"
                ? "group"
                : "channel";
        return buildChannelOutboundSessionRoute({
            cfg: params.cfg,
            agentId: params.agentId,
            channel: CLIQ_CHANNEL_ID,
            accountId: params.accountId,
            peer: {
                kind: chatType,
                id: normalized,
            },
            chatType,
            from: `${CLIQ_PLUGIN_ID}:${params.accountId || "default"}`,
            to: normalized,
            threadId: params.threadId ?? undefined,
        });
    },
};
const cliqBase = {
    ...createChannelPluginBase({
        id: CLIQ_CHANNEL_ID,
        meta: {
            id: CLIQ_CHANNEL_ID,
            label: "Zoho Cliq",
            selectionLabel: "Zoho Cliq (Bot API + zoho-cli)",
            docsPath: "/channels/cliq",
            docsLabel: "cliq",
            blurb: "Zoho Cliq channel backed by zoho-cli.",
            markdownCapable: true,
            exposure: {
                configured: true,
                setup: true,
                docs: true,
            },
        },
        capabilities: cliqCapabilities,
        configSchema: cliqChannelConfigSchema,
        config: cliqConfigAdapter,
        setup: {
            resolveAccountId: ({ accountId }) => accountId || "default",
            applyAccountConfig: applyCliqAccountConfig,
            validateInput: ({ input }) => validateCliqSetupInput({ input }),
        },
        setupWizard: cliqSetupWizard,
        groups: {
            resolveRequireMention: () => true,
            resolveGroupIntroHint: () => "Mention the configured Zoho Cliq bot before asking OpenClaw to act.",
        },
        agentPrompt: {
            messageToolHints: () => [
                "Use the shared OpenClaw message tool for Zoho Cliq sends and replies.",
                "Prefer explicit cliq channel targets such as channel:<id> or user:<id>.",
            ],
            messageToolCapabilities: () => [
                "Zoho Cliq text send through zoho-cli JSON stdout.",
                "Mention-gated group/channel operation.",
            ],
            inboundFormattingHints: () => ({
                text_markup: "markdown",
                rules: [
                    "Keep replies concise.",
                    "Do not include secrets, token values, or raw webhook signatures.",
                ],
            }),
        },
    }),
    capabilities: cliqCapabilities,
    config: cliqConfigAdapter,
    messaging: cliqMessagingAdapter,
};
export const zohoCliqPlugin = createChatChannelPlugin({
    base: cliqBase,
    security: {
        dm: {
            channelKey: CLIQ_CHANNEL_ID,
            resolvePolicy: (account) => account.dmPolicy,
            resolveAllowFrom: (account) => account.allowFrom,
            defaultPolicy: "allowlist",
            approveHint: "Add the Zoho Cliq user id to channels.cliq allowFrom.",
        },
    },
    pairing: {
        text: {
            idLabel: "Zoho Cliq user id",
            message: "Send this code to verify your Zoho Cliq identity:",
            notify: async () => {
                throw new Error("Zoho Cliq pairing delivery is not implemented until cliq-channel-403.");
            },
        },
    },
    threading: {
        topLevelReplyToMode: "reply",
    },
});
export function resolveCliqMentionDecision(params) {
    const wasMentioned = matchesMentionWithExplicit({
        text: params.text,
        mentionRegexes: params.mentionRegexes ?? [],
    });
    return resolveInboundMentionDecision({
        facts: {
            canDetectMention: true,
            wasMentioned,
            hasAnyMention: wasMentioned,
            implicitMentionKinds: [
                ...implicitMentionKindWhen("reply_to_bot", Boolean(params.isReplyToBot)),
                ...implicitMentionKindWhen("quoted_bot", Boolean(params.isQuoteOfBot)),
            ],
        },
        policy: {
            isGroup: params.isGroup,
            requireMention: params.requireMention,
            allowedImplicitMentionKinds: ["reply_to_bot", "quoted_bot"],
            allowTextCommands: false,
            hasControlCommand: false,
            commandAuthorized: false,
        },
    });
}
