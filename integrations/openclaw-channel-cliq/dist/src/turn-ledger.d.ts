import type { CliqResolvedAccount } from "./config.js";
import type { CliqNormalizedInboundEvent } from "./inbound.js";
import { type CliqInboundLifecycleOption, type CliqInboundLifecycleResult } from "./lifecycle.js";
export type CliqTurnLedgerState = "active" | "completed" | "failed" | "dead_letter" | "coalesced";
export type CliqTurnLedgerRejectReason = "duplicate_event" | "conversation_active" | "dead_lettered";
export type CliqTurnLedgerEntry = {
    turnId: string;
    eventKey: string;
    conversationKey: string;
    idempotencyKey: string;
    state: CliqTurnLedgerState;
    attempts: number;
    maxAttempts: number;
    messageId: string;
    accountId: string;
    network: string;
    peerId: string;
    chatId?: string;
    channelId?: string;
    threadId?: string;
    senderId?: string;
    lastAction: string;
    lastError?: string;
    deadLetterReason?: string;
    coalescedCount: number;
    coalescedEventKeys: string[];
    createdAt: string;
    updatedAt: string;
    activeExpiresAt?: string;
};
export type CliqTurnLedgerBeginResult = {
    accepted: true;
    entry: CliqTurnLedgerEntry;
} | {
    accepted: false;
    reason: CliqTurnLedgerRejectReason;
    entry: CliqTurnLedgerEntry;
};
export type CliqTurnLedgerOptions = {
    maxEntries?: number;
    maxAttempts?: number;
    activeTtlMs?: number;
    now?: () => number;
};
export type CliqTurnLedgerStore = {
    readonly size: number;
    begin(event: CliqNormalizedInboundEvent): CliqTurnLedgerBeginResult;
    complete(event: CliqNormalizedInboundEvent): CliqTurnLedgerEntry;
    fail(event: CliqNormalizedInboundEvent, error: unknown): CliqTurnLedgerEntry;
    get(eventOrKey: CliqNormalizedInboundEvent | string): CliqTurnLedgerEntry | undefined;
    snapshot(): CliqTurnLedgerEntry[];
    clear(): void;
};
export type CliqTurnLedgerOption = false | CliqTurnLedgerStore | CliqTurnLedgerOptions | undefined;
export type CliqInboundTurnResult = {
    eventKey: string;
    messageId: string;
    dispatched: boolean;
    turn: CliqTurnLedgerEntry;
    lifecycle?: CliqInboundLifecycleResult;
    skipped?: boolean;
    skipReason?: CliqTurnLedgerRejectReason;
    error?: string;
};
export declare function buildCliqTurnId(event: CliqNormalizedInboundEvent): string;
export declare function buildCliqTurnConversationKey(event: CliqNormalizedInboundEvent): string;
export declare function createCliqTurnLedgerStore(options?: CliqTurnLedgerOptions): CliqTurnLedgerStore;
export declare function resolveCliqTurnLedger(option: CliqTurnLedgerOption): CliqTurnLedgerStore | null;
export declare function runCliqInboundTurn(params: {
    account: CliqResolvedAccount;
    event: CliqNormalizedInboundEvent;
    turnLedger?: CliqTurnLedgerStore | null;
    lifecycle?: CliqInboundLifecycleOption;
    onEvent?: (event: CliqNormalizedInboundEvent) => void | Promise<void>;
}): Promise<CliqInboundTurnResult>;
