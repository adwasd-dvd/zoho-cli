import type { OpenClawConfig } from "openclaw/plugin-sdk";
import { describeCliqAccount, describeCliqAccountDiagnostics, describeCliqAgentBinding, describeCliqCapabilityDiagnostics } from "./config.js";
import { buildCliqOutboundSessionRoute } from "./session.js";
export type CliqChannelStatusSummary = {
    channel: "cliq";
    accountId: string;
    enabled: boolean;
    configured: boolean;
    setupStates: string[];
    statusLines: string[];
    account: ReturnType<typeof describeCliqAccount>;
    diagnostics: ReturnType<typeof describeCliqAccountDiagnostics>;
    agentBinding: ReturnType<typeof describeCliqAgentBinding>;
};
export type CliqChannelCapabilitySummary = {
    channel: "cliq";
    accountId: string;
    capabilities: ReturnType<typeof describeCliqCapabilityDiagnostics>;
    chatTypes: string[];
    nativeMessageSurface: boolean;
    nativeApprovalSurface: boolean;
    customSendTools: false;
};
export type CliqRoutingDiagnostic = {
    channel: "cliq";
    accountId: string;
    network: string;
    input: string;
    normalized?: string;
    chatType: string;
    nativeId?: string;
    threadId?: string;
    sessionRoute?: ReturnType<typeof buildCliqOutboundSessionRoute>;
    error?: string;
};
export declare function resolveCliqChannelStatusSummary(params: {
    cfg: OpenClawConfig;
    accountId?: string;
}): CliqChannelStatusSummary;
export declare function resolveCliqChannelCapabilitySummary(params: {
    cfg: OpenClawConfig;
    accountId?: string;
}): CliqChannelCapabilitySummary;
export declare function resolveCliqRoutingDiagnostic(params: {
    cfg: OpenClawConfig;
    accountId?: string;
    target: string;
    agentId?: string;
    replyToId?: string | null;
    threadId?: string | number | null;
    currentSessionKey?: string | null;
}): CliqRoutingDiagnostic;
