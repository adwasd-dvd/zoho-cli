import type { OpenClawConfig, OpenClawPluginApi, PluginLogger } from "openclaw/plugin-sdk";
import type { CliqResolvedAccount } from "./config.js";
import type { CliqNormalizedInboundEvent } from "./inbound.js";
import type { CliqInboundSecurityDecision } from "./security.js";
type PluginRuntime = OpenClawPluginApi["runtime"];
type CliqAllowedSecurityDecision = Extract<CliqInboundSecurityDecision, {
    allowed: true;
}>;
export type DeliveryFailure = {
    stage: string;
    reason: string;
    errorKind?: string;
};
export type CliqNativeDispatchSource = "webhook" | "polling" | "manual";
export type CliqNativeReplyTransport = "zoho_cli" | "deluge_response";
export type CliqReactionFallbackSummary = {
    mode: "emoji_prefixed_reply";
    applied: boolean;
    reason: "synthetic_message_id" | "native_message_id_available";
    messageIdKind: "native" | "synthetic";
    trueReactionEligible: boolean;
};
export type CliqNativeDispatchContext = {
    account: CliqResolvedAccount;
    source?: CliqNativeDispatchSource;
    replyTransport?: CliqNativeReplyTransport;
    handlerKind?: string;
    security?: CliqAllowedSecurityDecision;
};
export type CliqNativeDispatchResult = {
    ok: true;
    dispatched: boolean;
    admission: string;
    agentId?: string;
    accountId: string;
    matchedBy?: string;
    routeSessionKey?: string;
    target: string;
    replyToId: string;
    threadId?: string;
    deliveryTransport: CliqNativeReplyTransport;
    deliveryCount: number;
    messageIds: string[];
    deliveryFailures: DeliveryFailure[];
    reactionFallback?: CliqReactionFallbackSummary;
    replyText?: string;
    dispatchResult?: unknown;
};
export type CliqNativeEventDispatcher = (event: CliqNormalizedInboundEvent, context: CliqNativeDispatchContext) => Promise<CliqNativeDispatchResult>;
export type CliqNativeDispatchOptions = {
    cfg: OpenClawConfig;
    runtime: PluginRuntime;
    logger?: Partial<PluginLogger>;
    account: CliqResolvedAccount;
    event: CliqNormalizedInboundEvent;
    source?: CliqNativeDispatchSource;
    replyTransport?: CliqNativeReplyTransport;
    handlerKind?: string;
    security?: CliqAllowedSecurityDecision;
};
export declare function dispatchCliqEventToNativeOpenClaw(options: CliqNativeDispatchOptions): Promise<CliqNativeDispatchResult>;
export declare function createCliqNativeEventDispatcher(api: OpenClawPluginApi): CliqNativeEventDispatcher;
export {};
