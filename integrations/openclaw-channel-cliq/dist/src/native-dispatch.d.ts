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
export type CliqNativeDispatchContext = {
    account: CliqResolvedAccount;
    source?: CliqNativeDispatchSource;
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
    deliveryCount: number;
    messageIds: string[];
    deliveryFailures: DeliveryFailure[];
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
    handlerKind?: string;
    security?: CliqAllowedSecurityDecision;
};
export declare function dispatchCliqEventToNativeOpenClaw(options: CliqNativeDispatchOptions): Promise<CliqNativeDispatchResult>;
export declare function createCliqNativeEventDispatcher(api: OpenClawPluginApi): CliqNativeEventDispatcher;
export {};
