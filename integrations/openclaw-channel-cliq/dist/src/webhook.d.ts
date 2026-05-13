import type { IncomingHttpHeaders } from "node:http";
import type { IncomingMessage, ServerResponse } from "node:http";
import type { OpenClawConfig, OpenClawPluginApi, PluginLogger } from "openclaw/plugin-sdk";
import { type CliqResolvedAccount } from "./config.js";
import { type CliqInboundDedupeStore, type CliqMentionMatcher, type CliqNormalizedInboundEvent } from "./inbound.js";
import { type CliqInboundLifecycleOption, type CliqInboundLifecycleResult } from "./lifecycle.js";
import type { CliqNativeReplyTransport } from "./native-dispatch.js";
import type { CliqInboundSecurityDecision } from "./security.js";
import { type CliqInboundTurnResult, type CliqTurnLedgerOption, type CliqTurnLedgerStore } from "./turn-ledger.js";
export type CliqWebhookHandlerKind = "message" | "mention" | "participation" | "context" | "incoming_webhook" | "welcome" | "call" | "menu" | "unknown";
export type CliqWebhookPayloadEnvelope = {
    handler: string;
    handlerKind: CliqWebhookHandlerKind;
    replyMode?: CliqNativeReplyTransport;
    message: Record<string, unknown>;
    user?: Record<string, unknown>;
    chat?: Record<string, unknown>;
    raw: unknown;
};
export type CliqWebhookSecretVerificationResult = {
    ok: true;
    account: CliqResolvedAccount;
    accountId: string;
} | {
    ok: false;
    reason: "missing_secret" | "unconfigured_secret" | "invalid_secret";
};
export type CliqWebhookProcessResult = {
    ok: true;
    accepted: true;
    accountId: string;
    handlerKind: CliqWebhookHandlerKind;
    event: CliqNormalizedInboundEvent;
    security: Extract<CliqInboundSecurityDecision, {
        allowed: true;
    }>;
    lifecycle?: CliqInboundLifecycleResult;
    turn: CliqInboundTurnResult["turn"];
    dispatchError?: string;
    nativeDispatch?: unknown;
    dispatched: boolean;
} | {
    ok: true;
    accepted: false;
    status: "ignored";
    reason: "unsupported_handler" | "invalid_payload" | "duplicate" | "security_denied" | "turn_active" | "dead_lettered";
    accountId: string;
    handlerKind?: CliqWebhookHandlerKind;
    event?: CliqNormalizedInboundEvent;
    security?: CliqInboundSecurityDecision;
    turn?: CliqInboundTurnResult["turn"];
};
export type CliqWebhookHandlerOptions = {
    cfg: OpenClawConfig;
    webhookPath?: string;
    dedupe?: CliqInboundDedupeStore;
    lifecycle?: CliqInboundLifecycleOption;
    turnLedger?: CliqTurnLedgerOption;
    mentionMatchers?: CliqMentionMatcher[];
    env?: NodeJS.ProcessEnv;
    logger?: Partial<PluginLogger>;
    onEvent?: (event: CliqNormalizedInboundEvent, context: {
        account: CliqResolvedAccount;
        handlerKind: CliqWebhookHandlerKind;
        replyMode?: CliqNativeReplyTransport;
        security: Extract<CliqInboundSecurityDecision, {
            allowed: true;
        }>;
    }) => unknown | Promise<unknown>;
};
type CliqWebhookProcessOptions = CliqWebhookHandlerOptions & {
    account: CliqResolvedAccount;
    payload: unknown;
    resolvedTurnLedger?: CliqTurnLedgerStore | null;
};
type CliqWebhookHttpRouteHandler = (req: IncomingMessage, res: ServerResponse) => Promise<boolean | void> | boolean | void;
export declare function parseCliqWebhookPayload(body: string | Buffer | unknown, contentType?: string | string[]): unknown;
export declare function normalizeCliqWebhookPath(value?: string | null): string;
export declare function listCliqWebhookRoutePaths(cfg: OpenClawConfig): string[];
export declare function normalizeCliqWebhookPayload(params: {
    account: CliqResolvedAccount;
    payload: unknown;
    mentionMatchers?: CliqMentionMatcher[];
}): {
    envelope: CliqWebhookPayloadEnvelope | null;
    event: CliqNormalizedInboundEvent | null;
};
export declare function verifyCliqWebhookSecret(params: {
    cfg: OpenClawConfig;
    headers: IncomingHttpHeaders;
    env?: NodeJS.ProcessEnv;
    webhookPath?: string;
}): Promise<CliqWebhookSecretVerificationResult>;
export declare function evaluateCliqWebhookEventSecurity(params: {
    cfg?: OpenClawConfig;
    account: CliqResolvedAccount;
    event: CliqNormalizedInboundEvent;
    intent?: string | null;
}): CliqInboundSecurityDecision;
export declare function processCliqWebhookPayload(options: CliqWebhookProcessOptions): Promise<CliqWebhookProcessResult>;
export declare function createCliqWebhookHttpHandler(options: CliqWebhookHandlerOptions): CliqWebhookHttpRouteHandler;
export declare function registerCliqWebhookRoutes(api: OpenClawPluginApi): void;
export {};
