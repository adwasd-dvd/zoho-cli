import type { OpenClawConfig } from "openclaw/plugin-sdk";
import type { CliqResolvedAccount } from "./config.js";
import { type CliqInboundDedupeStore, type CliqMentionMatcher, type CliqNormalizedInboundEvent } from "./inbound.js";
export type CliqPollingSkipReason = "invalid_chat" | "invalid_message" | "duplicate" | "security_denied";
export type CliqPollingSkippedEvent = {
    reason: CliqPollingSkipReason;
    chat?: unknown;
    message?: unknown;
    event?: CliqNormalizedInboundEvent;
    securityReasonCode?: string;
    securityReason?: string;
};
export type CliqPollingResult = {
    events: CliqNormalizedInboundEvent[];
    dispatchedCount: number;
    skipped: CliqPollingSkippedEvent[];
};
export type CliqPollingOptions = {
    cfg?: OpenClawConfig;
    account: CliqResolvedAccount;
    limit?: number;
    contextLimit?: number;
    mentionMatchers?: CliqMentionMatcher[];
    selfUserIds?: string[];
    dedupe?: CliqInboundDedupeStore;
    onEvent?: (event: CliqNormalizedInboundEvent) => void | Promise<void>;
};
export declare function pollCliqInboundOnce(options: CliqPollingOptions): Promise<CliqPollingResult>;
