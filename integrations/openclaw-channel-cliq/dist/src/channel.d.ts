import type { ChannelPlugin } from "openclaw/plugin-sdk";
import { type CliqResolvedAccount } from "./config.js";
export declare const zohoCliqPlugin: ChannelPlugin<CliqResolvedAccount, unknown, unknown>;
export declare function resolveCliqMentionDecision(params: {
    text: string;
    mentionRegexes?: RegExp[];
    isGroup: boolean;
    requireMention: boolean;
    isReplyToBot?: boolean;
    isQuoteOfBot?: boolean;
}): import("openclaw/plugin-sdk/channel-inbound").InboundMentionDecision;
