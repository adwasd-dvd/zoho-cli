export { buildCliqInboundDedupeKey, createCliqInboundDedupeStore, evaluateCliqPollingEventSecurity, normalizeCliqContextMessages, normalizeCliqInboundMessage, normalizeCliqWatchMessages, } from "./src/inbound.js";
export { runCliqInboundLifecycle } from "./src/lifecycle.js";
export { pollCliqInboundOnce } from "./src/polling.js";
export { buildCliqTurnConversationKey, buildCliqTurnId, createCliqTurnLedgerStore, resolveCliqTurnLedger, runCliqInboundTurn, } from "./src/turn-ledger.js";
export { createCliqWebhookHttpHandler, evaluateCliqWebhookEventSecurity, listCliqWebhookRoutePaths, normalizeCliqWebhookPayload, normalizeCliqWebhookPath, parseCliqWebhookPayload, processCliqWebhookPayload, registerCliqWebhookRoutes, verifyCliqWebhookSecret, } from "./src/webhook.js";
declare const _default: {
    id: string;
    name: string;
    description: string;
    configSchema: import("openclaw/plugin-sdk").ChannelConfigSchema;
    register: (api: import("openclaw/plugin-sdk/channel-core").OpenClawPluginApi) => void;
    channelPlugin: import("openclaw/plugin-sdk/channel-core").ChannelPlugin<import("./src/config.js").CliqResolvedAccount, unknown, unknown>;
    setChannelRuntime?: (runtime: import("openclaw/plugin-sdk/channel-core").PluginRuntime) => void;
};
export default _default;
