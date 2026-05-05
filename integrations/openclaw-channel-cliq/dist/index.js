import { defineChannelPluginEntry } from "openclaw/plugin-sdk/channel-core";
import { cliqChannelConfigSchema } from "./src/config.js";
import { CLIQ_CHANNEL_ID, CLIQ_PLUGIN_ID } from "./src/constants.js";
import { zohoCliqPlugin } from "./src/channel.js";
import { registerCliqWebhookRoutes } from "./src/webhook.js";
export { buildCliqInboundDedupeKey, createCliqInboundDedupeStore, evaluateCliqPollingEventSecurity, normalizeCliqContextMessages, normalizeCliqInboundMessage, normalizeCliqWatchMessages, } from "./src/inbound.js";
export { pollCliqInboundOnce } from "./src/polling.js";
export { createCliqWebhookHttpHandler, evaluateCliqWebhookEventSecurity, listCliqWebhookRoutePaths, normalizeCliqWebhookPayload, normalizeCliqWebhookPath, parseCliqWebhookPayload, processCliqWebhookPayload, registerCliqWebhookRoutes, verifyCliqWebhookSecret, } from "./src/webhook.js";
export default defineChannelPluginEntry({
    id: CLIQ_PLUGIN_ID,
    name: "Zoho Cliq",
    description: "Native OpenClaw channel for Zoho Cliq backed by zoho-cli.",
    plugin: zohoCliqPlugin,
    configSchema: cliqChannelConfigSchema,
    registerFull(api) {
        registerCliqWebhookRoutes(api);
    },
    registerCliMetadata(api) {
        api.registerCli(({ program }) => {
            program
                .command(CLIQ_CHANNEL_ID)
                .description("Zoho Cliq channel diagnostics and setup metadata.");
        }, {
            descriptors: [
                {
                    name: CLIQ_CHANNEL_ID,
                    description: "Zoho Cliq channel diagnostics and setup metadata.",
                    hasSubcommands: true,
                },
            ],
        });
    },
});
