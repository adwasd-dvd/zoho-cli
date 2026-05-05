import type { PluginLogger } from "openclaw/plugin-sdk";
import type { CliqResolvedAccount } from "./config.js";
import type { CliqNormalizedInboundEvent } from "./inbound.js";
import type { CliqInboundLifecycleResult } from "./lifecycle.js";
import { resolveCliqPrivacyRetentionPolicy } from "./privacy.js";
import type { CliqTurnLedgerEntry } from "./turn-ledger.js";
export declare const CLIQ_WEBHOOK_BODY_MAX_BYTES: number;
export declare const CLIQ_WEBHOOK_BODY_TIMEOUT_MS = 5000;
export declare const CLIQ_WEBHOOK_RATE_LIMIT_WINDOW_MS = 60000;
export declare const CLIQ_WEBHOOK_RATE_LIMIT_MAX_REQUESTS = 120;
export declare const CLIQ_WEBHOOK_MAX_IN_FLIGHT_PER_KEY = 4;
export declare const CLIQ_WEBHOOK_MAX_TRACKED_KEYS = 2048;
export type CliqAuditOutcome = "accepted" | "ignored" | "denied" | "failed" | "dispatched" | "skipped";
export type CliqAuditKind = "webhook_ingress" | "polling_ingress" | "native_dispatch" | "turn_ledger" | "lifecycle";
export type CliqRedactedAuditEvent = {
    channel: "cliq";
    kind: CliqAuditKind;
    outcome: CliqAuditOutcome;
    correlationId: string;
    accountId: string;
    network: string;
    source?: string;
    handlerKind?: string;
    reason?: string;
    event?: Record<string, unknown>;
    security?: Record<string, unknown>;
    turn?: Record<string, unknown>;
    lifecycle?: Record<string, unknown>;
    nativeDispatch?: Record<string, unknown>;
    createdAt: string;
};
export type CliqDiagnosticBundle = {
    channel: "cliq";
    generatedAt: string;
    correlationId: string;
    account: {
        accountId: string;
        network: string;
        enabled: boolean;
        webhookPath: string;
        dmPolicy: string;
        groupPolicy: string;
        requireMention: boolean;
    };
    event?: Record<string, unknown>;
    turn?: Record<string, unknown>;
    lifecycle?: Record<string, unknown>;
    nativeDispatch?: Record<string, unknown>;
    rateLimits: ReturnType<typeof describeCliqRateLimitDiagnostics>;
    privacy: ReturnType<typeof resolveCliqPrivacyRetentionPolicy>;
    releaseIntegrity: ReturnType<typeof describeCliqReleaseIntegrityDiagnostics>;
};
export declare function buildCliqCorrelationId(params: {
    accountId?: string;
    network?: string;
    source?: string;
    messageId?: string;
    peerId?: string;
    threadId?: string;
    dedupeKey?: string;
    fallback?: string;
}): string;
export declare function correlationIdForCliqEvent(params: {
    event: CliqNormalizedInboundEvent;
    source?: string;
}): string;
export declare function summarizeCliqInboundEventForDiagnostics(event: CliqNormalizedInboundEvent, source?: string): Record<string, unknown>;
export declare function summarizeCliqTurnForDiagnostics(turn?: CliqTurnLedgerEntry): Record<string, unknown> | undefined;
export declare function summarizeCliqLifecycleForDiagnostics(lifecycle?: CliqInboundLifecycleResult): Record<string, unknown> | undefined;
export declare function describeCliqRateLimitDiagnostics(): {
    webhook: {
        windowMs: number;
        maxRequests: number;
        maxInFlightPerKey: number;
        maxTrackedKeys: number;
        key: string;
        bodyMaxBytes: number;
        bodyTimeoutMs: number;
        rejectionStage: string;
    };
    polling: {
        defaultChatLimit: number;
        defaultContextLimit: number;
        dedupe: string;
        selfAuthoredMessagesSkipped: boolean;
    };
    lifecycle: {
        statusReadAckFailures: string;
        recursiveDispatchOnLifecycleFailure: boolean;
    };
    nativeDispatch: {
        emptyOrReasoningPayloadsSkipped: boolean;
        missingOutboundAdapterError: string;
    };
};
export declare function describeCliqReleaseIntegrityDiagnostics(): {
    npmExpectedIntegrity: string;
    localLinkedDevelopmentAllowed: boolean;
    releaseChecklist: string[];
};
export declare function describeCliqObservabilityDiagnostics(): {
    redactedAuditEvents: boolean;
    correlationIds: boolean;
    diagnosticBundle: boolean;
    rateLimitDiagnostics: boolean;
    privacyRetention: boolean;
    deadLetterReplayGuard: boolean;
    npmIntegrityPlaceholder: boolean;
    rateLimits: {
        webhook: {
            windowMs: number;
            maxRequests: number;
            maxInFlightPerKey: number;
            maxTrackedKeys: number;
            key: string;
            bodyMaxBytes: number;
            bodyTimeoutMs: number;
            rejectionStage: string;
        };
        polling: {
            defaultChatLimit: number;
            defaultContextLimit: number;
            dedupe: string;
            selfAuthoredMessagesSkipped: boolean;
        };
        lifecycle: {
            statusReadAckFailures: string;
            recursiveDispatchOnLifecycleFailure: boolean;
        };
        nativeDispatch: {
            emptyOrReasoningPayloadsSkipped: boolean;
            missingOutboundAdapterError: string;
        };
    };
    privacy: import("./privacy.js").CliqPrivacyRetentionPolicy;
    releaseIntegrity: {
        npmExpectedIntegrity: string;
        localLinkedDevelopmentAllowed: boolean;
        releaseChecklist: string[];
    };
};
export declare function buildCliqAuditEvent(params: {
    kind: CliqAuditKind;
    outcome: CliqAuditOutcome;
    account: CliqResolvedAccount;
    source?: string;
    handlerKind?: string;
    reason?: string;
    event?: CliqNormalizedInboundEvent;
    security?: Record<string, unknown>;
    turn?: CliqTurnLedgerEntry;
    lifecycle?: CliqInboundLifecycleResult;
    nativeDispatch?: Record<string, unknown>;
    now?: () => Date;
}): CliqRedactedAuditEvent;
export declare function emitCliqAuditEvent(logger: Partial<PluginLogger> | undefined, event: CliqRedactedAuditEvent): void;
export declare function buildCliqDiagnosticBundle(params: {
    account: CliqResolvedAccount;
    event?: CliqNormalizedInboundEvent;
    turn?: CliqTurnLedgerEntry;
    lifecycle?: CliqInboundLifecycleResult;
    nativeDispatch?: Record<string, unknown>;
    source?: string;
    now?: () => Date;
}): CliqDiagnosticBundle;
