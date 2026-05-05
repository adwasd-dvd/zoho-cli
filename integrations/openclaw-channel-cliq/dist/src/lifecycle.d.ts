import type { PluginLogger } from "openclaw/plugin-sdk";
import type { CliqResolvedAccount } from "./config.js";
import type { CliqNormalizedInboundEvent } from "./inbound.js";
import { type CliqLifecycleStatus } from "./zoho-cli.js";
export type CliqInboundLifecycleActionKind = "status" | "mark_read";
export type CliqInboundLifecycleAction = {
    kind: CliqInboundLifecycleActionKind;
    ok: boolean;
    applied: boolean;
    status?: CliqLifecycleStatus;
    command?: string[];
    reason?: string;
    errorKind?: string;
    error?: string;
};
export type CliqInboundLifecycleResult = {
    eventKey: string;
    messageId: string;
    dispatched: boolean;
    actions: CliqInboundLifecycleAction[];
};
export type CliqInboundLifecycleOptions = {
    statusReactions?: boolean;
    markRead?: boolean;
    startStatuses?: CliqLifecycleStatus[];
    successStatus?: CliqLifecycleStatus | null;
    failureStatus?: CliqLifecycleStatus | null;
    logger?: Partial<PluginLogger>;
};
export type CliqInboundLifecycleOption = false | CliqInboundLifecycleOptions | undefined;
export declare class CliqInboundLifecycleDispatchError extends Error {
    readonly lifecycle: CliqInboundLifecycleResult;
    readonly cause: unknown;
    constructor(error: unknown, lifecycle: CliqInboundLifecycleResult);
}
export declare function runCliqInboundLifecycle(params: {
    account: CliqResolvedAccount;
    event: CliqNormalizedInboundEvent;
    lifecycle?: CliqInboundLifecycleOption;
    onEvent?: (event: CliqNormalizedInboundEvent) => void | Promise<void>;
}): Promise<CliqInboundLifecycleResult>;
