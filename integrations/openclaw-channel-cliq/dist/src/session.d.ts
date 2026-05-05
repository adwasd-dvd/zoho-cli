import type { OpenClawConfig } from "openclaw/plugin-sdk";
import { buildChannelOutboundSessionRoute } from "openclaw/plugin-sdk/channel-core";
import type { CliqResolvedAccount } from "./config.js";
type ChannelOutboundSessionRoute = ReturnType<typeof buildChannelOutboundSessionRoute>;
export type CliqTargetChatType = "direct" | "group" | "channel";
export type CliqParsedTarget = {
    to: string;
    nativeId: string;
    chatType: CliqTargetChatType;
    kind: "user" | "group" | "channel";
    threadId?: string;
};
type CliqPreferredTargetKind = "user" | "group" | "channel";
type CliqSessionPeer = {
    accountId: string;
    network: string;
    chatType: CliqTargetChatType;
    nativeId: string;
};
export declare function normalizeCliqSessionToken(raw: string | number): string;
export declare function parseCliqExplicitTarget(raw: string, preferredKind?: CliqPreferredTargetKind): CliqParsedTarget | null;
export declare function normalizeCliqTarget(raw: string): string | undefined;
export declare function inferCliqTargetChatType(raw: string): CliqTargetChatType;
export declare function buildCliqSessionPeerId(peer: CliqSessionPeer): string;
export declare function resolveCliqSessionConversation(params: {
    kind: "group" | "channel";
    rawId: string;
}): {
    id: string;
    threadId: string | null;
    baseConversationId: string;
    parentConversationCandidates: string[];
} | null;
export declare function resolveCliqSessionTarget(params: {
    kind: "group" | "channel";
    id: string;
    threadId?: string | null;
}): string | undefined;
export declare function buildCliqOutboundSessionRoute(params: {
    cfg: OpenClawConfig;
    agentId: string;
    account: CliqResolvedAccount;
    target: string;
    resolvedTarget?: {
        to: string;
        kind: "user" | "group" | "channel";
        display?: string;
        source: "normalized" | "directory";
    };
    replyToId?: string | null;
    threadId?: string | number | null;
    currentSessionKey?: string | null;
}): ChannelOutboundSessionRoute;
export {};
