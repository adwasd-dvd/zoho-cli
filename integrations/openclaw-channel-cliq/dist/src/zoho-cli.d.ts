import type { CliqResolvedAccount } from "./config.js";
export type ZohoCliqCommandErrorKind = "auth_missing" | "scope_missing" | "unsupported_endpoint" | "invalid_json" | "timeout" | "command_not_found" | "command_failed";
export type ZohoCliJsonResult<T = unknown> = {
    command: string[];
    stdout: T;
    stderr: string;
};
export type ZohoCliqRunOptions = {
    timeoutMs?: number;
};
export declare class ZohoCliqCommandError extends Error {
    readonly command: string[];
    readonly exitCode: number | null;
    readonly stderr: string;
    readonly kind: ZohoCliqCommandErrorKind;
    constructor(params: {
        command: string[];
        exitCode: number | null;
        stderr: string;
        kind?: ZohoCliqCommandErrorKind;
        redactionValues?: string[];
    });
}
export declare function runZohoCliqJson<T = unknown>(account: CliqResolvedAccount, args: string[], options?: ZohoCliqRunOptions): Promise<ZohoCliJsonResult<T>>;
export declare function buildCliqSendArgs(params: {
    account: CliqResolvedAccount;
    to: string;
    text: string;
    threadId?: string | number | null;
}): string[];
export declare function buildCliqReplyArgs(params: {
    account: CliqResolvedAccount;
    to: string;
    text: string;
    replyToId: string;
    threadId?: string | number | null;
}): string[];
export declare function buildCliqThreadReplyArgs(params: {
    account: CliqResolvedAccount;
    to: string;
    text: string;
    threadId: string | number;
}): string[];
export declare function buildCliqDeliveryArgs(params: {
    account: CliqResolvedAccount;
    to: string;
    text: string;
    replyToId?: string | null;
    threadId?: string | number | null;
}): string[];
export type CliqLifecycleStatus = "received" | "thinking" | "writing" | "testing" | "blocked" | "done" | "failed";
export declare function buildCliqStatusReactArgs(params: {
    account: CliqResolvedAccount;
    messageId: string | number;
    status: CliqLifecycleStatus;
    chatId?: string | number | null;
    channelId?: string | number | null;
    clearKnown?: boolean;
}): string[];
export declare function buildCliqMarkReadArgs(params: {
    account: CliqResolvedAccount;
    messageId: string | number;
    chatId?: string | number | null;
    channelId?: string | number | null;
}): string[];
export declare function buildCliqChatsArgs(params: {
    account: CliqResolvedAccount;
    limit?: number;
    unreadOnly?: boolean;
    excludeReactedBySelf?: boolean;
}): string[];
export declare function buildCliqContextArgs(params: {
    account: CliqResolvedAccount;
    chatId?: string | null;
    channelId?: string | null;
    messageId?: string | null;
    before?: number;
    after?: number;
    limit?: number;
}): string[];
export declare function sendCliqText(params: {
    account: CliqResolvedAccount;
    to: string;
    text: string;
    replyToId?: string | null;
    threadId?: string | number | null;
}): Promise<{
    messageId?: string;
}>;
export declare function setCliqStatusReaction(params: {
    account: CliqResolvedAccount;
    messageId: string | number;
    status: CliqLifecycleStatus;
    chatId?: string | number | null;
    channelId?: string | number | null;
    clearKnown?: boolean;
}): Promise<ZohoCliJsonResult<unknown>>;
export declare function markCliqMessageRead(params: {
    account: CliqResolvedAccount;
    messageId: string | number;
    chatId?: string | number | null;
    channelId?: string | number | null;
}): Promise<ZohoCliJsonResult<unknown>>;
export declare function listCliqChats(params: {
    account: CliqResolvedAccount;
    limit?: number;
    unreadOnly?: boolean;
    excludeReactedBySelf?: boolean;
}): Promise<{
    chats: Record<string, unknown>[];
}>;
export declare function fetchCliqContext(params: {
    account: CliqResolvedAccount;
    chatId?: string | null;
    channelId?: string | null;
    messageId?: string | null;
    before?: number;
    after?: number;
    limit?: number;
}): Promise<Record<string, unknown>>;
