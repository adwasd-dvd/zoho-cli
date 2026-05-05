import type { OpenClawConfig } from "openclaw/plugin-sdk";
import type { CliqResolvedAccount } from "./config.js";
import { type CliqChatKind, type CliqInboundSecurityDecision } from "./security.js";
export type CliqMentionMatcher = RegExp | string;
export type CliqNormalizedInboundEvent = {
    channel: "cliq";
    accountId: string;
    network: string;
    chatType: CliqChatKind;
    peerId: string;
    nativePeerId: string;
    chatId?: string;
    channelId?: string;
    messageId: string;
    senderId?: string;
    senderLabel?: string;
    threadId?: string;
    text: string;
    mentioned: boolean;
    timestamp?: string;
    dedupeKey: string;
    raw: unknown;
};
export type CliqInboundEvent = CliqNormalizedInboundEvent;
export type CliqInboundDedupeStore = {
    readonly size: number;
    has(keyOrEvent: string | CliqNormalizedInboundEvent): boolean;
    claim(keyOrEvent: string | CliqNormalizedInboundEvent): boolean;
    mark(keyOrEvent: string | CliqNormalizedInboundEvent): void;
    forget(keyOrEvent: string | CliqNormalizedInboundEvent): void;
    takeNew(events: CliqNormalizedInboundEvent[]): CliqNormalizedInboundEvent[];
    clear(): void;
};
export declare function isCliqSelfAuthoredMessage(message: unknown, selfUserIds?: string[]): boolean;
export declare function buildCliqInboundDedupeKey(event: {
    accountId: string;
    network?: string;
    peerId?: string;
    chatId?: string;
    channelId?: string;
    messageId: string;
}): string;
export declare function normalizeCliqInboundMessage(params: {
    accountId: string;
    network?: string | null;
    chat?: unknown;
    message: unknown;
    mentionMatchers?: CliqMentionMatcher[];
    selfUserIds?: string[];
    skipSelfAuthored?: boolean;
}): CliqNormalizedInboundEvent | null;
export declare function normalizeCliqContextMessages(params: {
    accountId: string;
    network?: string;
    payload: unknown;
    chat?: unknown;
    defaultChatId?: string;
    defaultChannelId?: string;
    mentionMatchers?: CliqMentionMatcher[];
    selfUserIds?: string[];
}): CliqNormalizedInboundEvent[];
export declare function normalizeCliqWatchMessages(params: Parameters<typeof normalizeCliqContextMessages>[0]): CliqNormalizedInboundEvent[];
declare class InMemoryCliqInboundDedupeStore implements CliqInboundDedupeStore {
    private readonly seen;
    private readonly maxEntries;
    constructor(maxEntries?: number);
    get size(): number;
    has(keyOrEvent: string | CliqNormalizedInboundEvent): boolean;
    claim(keyOrEvent: string | CliqNormalizedInboundEvent): boolean;
    mark(keyOrEvent: string | CliqNormalizedInboundEvent): void;
    forget(keyOrEvent: string | CliqNormalizedInboundEvent): void;
    takeNew(events: CliqNormalizedInboundEvent[]): CliqNormalizedInboundEvent[];
    clear(): void;
}
export declare const CliqInboundDedupeStore: typeof InMemoryCliqInboundDedupeStore;
export declare function createCliqInboundDedupeStore(maxEntries?: number): CliqInboundDedupeStore;
export declare function evaluateCliqPollingEventSecurity(params: {
    cfg?: OpenClawConfig;
    account: CliqResolvedAccount;
    event: CliqNormalizedInboundEvent;
    intent?: string | null;
}): CliqInboundSecurityDecision;
export {};
