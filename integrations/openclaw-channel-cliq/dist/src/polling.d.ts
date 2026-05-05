import type { OpenClawConfig } from "openclaw/plugin-sdk";
import type { CliqResolvedAccount } from "./config.js";
import { type CliqInboundDedupeStore, type CliqMentionMatcher, type CliqNormalizedInboundEvent } from "./inbound.js";
import { type CliqInboundLifecycleResult } from "./lifecycle.js";
import { runCliqInboundTurn, type CliqInboundTurnResult, type CliqTurnLedgerOption } from "./turn-ledger.js";
import type { CliqNativeEventDispatcher } from "./native-dispatch.js";
export type CliqPollingSkipReason = "invalid_chat" | "invalid_message" | "duplicate" | "security_denied" | "turn_active" | "dead_lettered";
export type CliqPollingSkippedEvent = {
    reason: CliqPollingSkipReason;
    chat?: unknown;
    message?: unknown;
    event?: CliqNormalizedInboundEvent;
    turn?: CliqInboundTurnResult["turn"];
    securityReasonCode?: string;
    securityReason?: string;
};
export type CliqPollingResult = {
    events: CliqNormalizedInboundEvent[];
    dispatchedCount: number;
    lifecycle: CliqInboundLifecycleResult[];
    turns: CliqInboundTurnResult[];
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
    lifecycle?: Parameters<typeof runCliqInboundTurn>[0]["lifecycle"];
    turnLedger?: CliqTurnLedgerOption;
    nativeDispatch?: CliqNativeEventDispatcher;
    onEvent?: (event: CliqNormalizedInboundEvent) => void | Promise<void>;
};
export declare function pollCliqInboundOnce(options: CliqPollingOptions): Promise<CliqPollingResult>;
