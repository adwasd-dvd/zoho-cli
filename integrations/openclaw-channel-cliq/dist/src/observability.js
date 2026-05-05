import { createHash } from "node:crypto";
import { redactCliqDiagnosticObject, resolveCliqPrivacyRetentionPolicy, } from "./privacy.js";
export const CLIQ_WEBHOOK_BODY_MAX_BYTES = 512 * 1024;
export const CLIQ_WEBHOOK_BODY_TIMEOUT_MS = 5_000;
export const CLIQ_WEBHOOK_RATE_LIMIT_WINDOW_MS = 60_000;
export const CLIQ_WEBHOOK_RATE_LIMIT_MAX_REQUESTS = 120;
export const CLIQ_WEBHOOK_MAX_IN_FLIGHT_PER_KEY = 4;
export const CLIQ_WEBHOOK_MAX_TRACKED_KEYS = 2048;
function stableHash(parts) {
    return createHash("sha256")
        .update(JSON.stringify(parts))
        .digest("hex")
        .slice(0, 16);
}
export function buildCliqCorrelationId(params) {
    return `cliq-${stableHash([
        params.accountId ?? "default",
        params.network ?? "default",
        params.source ?? "unknown",
        params.dedupeKey ?? "",
        params.peerId ?? "",
        params.messageId ?? "",
        params.threadId ?? "",
        params.fallback ?? "",
    ])}`;
}
export function correlationIdForCliqEvent(params) {
    return buildCliqCorrelationId({
        accountId: params.event.accountId,
        network: params.event.network,
        source: params.source,
        messageId: params.event.messageId,
        peerId: params.event.peerId,
        threadId: params.event.threadId,
        dedupeKey: params.event.dedupeKey,
    });
}
export function summarizeCliqInboundEventForDiagnostics(event, source) {
    return {
        correlationId: correlationIdForCliqEvent({ event, source }),
        accountId: event.accountId,
        network: event.network,
        chatType: event.chatType,
        peerId: event.peerId,
        nativePeerId: event.nativePeerId,
        chatId: event.chatId,
        channelId: event.channelId,
        threadId: event.threadId,
        messageId: event.messageId,
        senderId: event.senderId,
        mentioned: event.mentioned,
        timestamp: event.timestamp,
        textLength: event.text.length,
    };
}
export function summarizeCliqTurnForDiagnostics(turn) {
    if (!turn)
        return undefined;
    return {
        turnId: turn.turnId,
        eventKey: turn.eventKey,
        conversationKey: turn.conversationKey,
        idempotencyKey: turn.idempotencyKey,
        state: turn.state,
        attempts: turn.attempts,
        maxAttempts: turn.maxAttempts,
        lastAction: turn.lastAction,
        lastError: turn.lastError,
        deadLetterReason: turn.deadLetterReason,
        coalescedCount: turn.coalescedCount,
        createdAt: turn.createdAt,
        updatedAt: turn.updatedAt,
        activeExpiresAt: turn.activeExpiresAt,
    };
}
export function summarizeCliqLifecycleForDiagnostics(lifecycle) {
    if (!lifecycle)
        return undefined;
    return {
        dispatched: lifecycle.dispatched,
        actions: lifecycle.actions.map((action) => ({
            kind: action.kind,
            ok: action.ok,
            applied: action.applied,
            status: action.status,
            reason: action.reason,
            errorKind: action.errorKind,
        })),
    };
}
export function describeCliqRateLimitDiagnostics() {
    return {
        webhook: {
            windowMs: CLIQ_WEBHOOK_RATE_LIMIT_WINDOW_MS,
            maxRequests: CLIQ_WEBHOOK_RATE_LIMIT_MAX_REQUESTS,
            maxInFlightPerKey: CLIQ_WEBHOOK_MAX_IN_FLIGHT_PER_KEY,
            maxTrackedKeys: CLIQ_WEBHOOK_MAX_TRACKED_KEYS,
            key: "remote_address",
            bodyMaxBytes: CLIQ_WEBHOOK_BODY_MAX_BYTES,
            bodyTimeoutMs: CLIQ_WEBHOOK_BODY_TIMEOUT_MS,
            rejectionStage: "pre_body_read",
        },
        polling: {
            defaultChatLimit: 50,
            defaultContextLimit: 20,
            dedupe: "bounded_in_memory",
            selfAuthoredMessagesSkipped: true,
        },
        lifecycle: {
            statusReadAckFailures: "terminal_diagnostic",
            recursiveDispatchOnLifecycleFailure: false,
        },
        nativeDispatch: {
            emptyOrReasoningPayloadsSkipped: true,
            missingOutboundAdapterError: "cliq_outbound_adapter_unavailable",
        },
    };
}
export function describeCliqReleaseIntegrityDiagnostics() {
    return {
        npmExpectedIntegrity: "<filled-at-release>",
        localLinkedDevelopmentAllowed: true,
        releaseChecklist: [
            "npm pack artifact generated from clean tree",
            "package-local typecheck/build completed",
            "OpenClaw linked install inspect and doctor completed",
            "expectedIntegrity filled before npm promotion",
            "make ci and release gate completed",
        ],
    };
}
export function describeCliqObservabilityDiagnostics() {
    return {
        redactedAuditEvents: true,
        correlationIds: true,
        diagnosticBundle: true,
        rateLimitDiagnostics: true,
        privacyRetention: true,
        deadLetterReplayGuard: true,
        npmIntegrityPlaceholder: true,
        rateLimits: describeCliqRateLimitDiagnostics(),
        privacy: resolveCliqPrivacyRetentionPolicy(),
        releaseIntegrity: describeCliqReleaseIntegrityDiagnostics(),
    };
}
export function buildCliqAuditEvent(params) {
    const eventSummary = params.event
        ? summarizeCliqInboundEventForDiagnostics(params.event, params.source)
        : undefined;
    const correlationId = eventSummary?.correlationId ??
        buildCliqCorrelationId({
            accountId: params.account.accountId,
            network: params.account.network,
            source: params.source,
            fallback: `${params.kind}:${params.outcome}:${params.reason ?? ""}`,
        });
    return redactCliqDiagnosticObject({
        channel: "cliq",
        kind: params.kind,
        outcome: params.outcome,
        correlationId,
        accountId: params.account.accountId,
        network: params.account.network || "default",
        source: params.source,
        handlerKind: params.handlerKind,
        reason: params.reason,
        event: eventSummary,
        security: params.security,
        turn: summarizeCliqTurnForDiagnostics(params.turn),
        lifecycle: summarizeCliqLifecycleForDiagnostics(params.lifecycle),
        nativeDispatch: params.nativeDispatch,
        createdAt: (params.now?.() ?? new Date()).toISOString(),
    });
}
export function emitCliqAuditEvent(logger, event) {
    logger?.info?.(`[zoho-cliq-audit] ${JSON.stringify(event)}`);
}
export function buildCliqDiagnosticBundle(params) {
    const generatedAt = (params.now?.() ?? new Date()).toISOString();
    const correlationId = params.event
        ? correlationIdForCliqEvent({
            event: params.event,
            source: params.source,
        })
        : buildCliqCorrelationId({
            accountId: params.account.accountId,
            network: params.account.network,
            source: params.source,
            fallback: generatedAt,
        });
    return redactCliqDiagnosticObject({
        channel: "cliq",
        generatedAt,
        correlationId,
        account: {
            accountId: params.account.accountId,
            network: params.account.network || "default",
            enabled: params.account.enabled,
            webhookPath: params.account.webhookPath,
            dmPolicy: params.account.dmPolicy,
            groupPolicy: params.account.groupPolicy,
            requireMention: params.account.requireMention,
        },
        event: params.event
            ? summarizeCliqInboundEventForDiagnostics(params.event, params.source)
            : undefined,
        turn: summarizeCliqTurnForDiagnostics(params.turn),
        lifecycle: summarizeCliqLifecycleForDiagnostics(params.lifecycle),
        nativeDispatch: params.nativeDispatch,
        rateLimits: describeCliqRateLimitDiagnostics(),
        privacy: resolveCliqPrivacyRetentionPolicy(),
        releaseIntegrity: describeCliqReleaseIntegrityDiagnostics(),
    });
}
