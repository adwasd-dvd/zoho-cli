import { formatTextWithAttachmentLinks, hasOutboundReplyContent, resolveOutboundMediaUrls, sendTextMediaPayload, } from "openclaw/plugin-sdk/reply-payload";
import { resolveInboundLastRouteSessionKey } from "openclaw/plugin-sdk/routing";
import { CLIQ_CHANNEL_ID } from "./constants.js";
import { buildCliqAuditEvent, emitCliqAuditEvent } from "./observability.js";
import { buildCliqSessionPeerId, normalizeCliqSessionToken, } from "./session.js";
function isRecord(value) {
    return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
function normalizeTimestamp(value) {
    if (!value)
        return undefined;
    const parsed = Date.parse(value);
    return Number.isFinite(parsed) ? parsed : undefined;
}
function withCliqDirectSessionScope(cfg) {
    return {
        ...cfg,
        session: {
            ...(cfg.session ?? {}),
            dmScope: "per-account-channel-peer",
        },
    };
}
function routeKindForEvent(event) {
    if (event.chatType === "direct")
        return "direct";
    if (event.chatType === "group")
        return "group";
    return "channel";
}
function targetChatTypeForRoute(kind) {
    if (kind === "direct")
        return "direct";
    if (kind === "group")
        return "group";
    return "channel";
}
function targetForEvent(params) {
    if (params.routeKind === "direct")
        return `user:${params.event.nativePeerId}`;
    if (params.routeKind === "group")
        return `chat:${params.event.nativePeerId}`;
    return `channel:${params.event.nativePeerId}`;
}
function normalizeReplyableCliqMessageId(value) {
    const normalized = String(value ?? "").trim();
    if (!normalized)
        return undefined;
    const lower = normalized.toLowerCase();
    return lower.startsWith("webhook-") || lower.startsWith("zoho-message-")
        ? undefined
        : normalized;
}
function resolveCliqDeliveryRoute(params) {
    const replyToId = normalizeReplyableCliqMessageId(params.payloadReplyToId) ??
        normalizeReplyableCliqMessageId(params.event.messageId);
    if (params.facts.routeKind === "direct" && params.event.chatId) {
        return { to: `chat:${params.event.chatId}`, replyToId: replyToId ?? null };
    }
    if (!replyToId) {
        return { to: params.facts.target, replyToId: null };
    }
    return { to: params.facts.target, replyToId };
}
function resolveCliqNativeRouteFacts(params) {
    const routeKind = routeKindForEvent(params.event);
    const targetChatType = targetChatTypeForRoute(routeKind);
    const basePeerId = buildCliqSessionPeerId({
        accountId: params.account.accountId,
        network: params.account.network || params.event.network,
        chatType: targetChatType,
        nativeId: params.event.nativePeerId,
    });
    const threadId = params.event.threadId
        ? normalizeCliqSessionToken(params.event.threadId)
        : undefined;
    const basePeer = {
        kind: routeKind,
        id: basePeerId,
    };
    const routePeer = threadId && routeKind !== "direct"
        ? {
            kind: routeKind,
            id: `${basePeerId}:thread:${threadId}`,
        }
        : basePeer;
    return {
        routeKind,
        targetChatType,
        target: targetForEvent({ event: params.event, routeKind }),
        nativeChannelId: params.event.channelId ?? params.event.chatId,
        basePeer,
        routePeer,
        ...(routePeer.id !== basePeer.id ? { parentPeer: basePeer } : {}),
    };
}
function buildAccessFacts(params) {
    if (params.event.chatType === "direct") {
        return {
            dm: {
                decision: "allow",
                allowFrom: params.account.allowFrom.map(String),
            },
            mentions: {
                canDetectMention: true,
                wasMentioned: true,
                hasAnyMention: true,
            },
        };
    }
    return {
        group: {
            policy: params.account.groupPolicy,
            routeAllowed: true,
            senderAllowed: true,
            allowFrom: params.account.groupAllowFrom.map(String),
            requireMention: params.account.requireMention,
        },
        mentions: {
            canDetectMention: true,
            wasMentioned: params.event.mentioned,
            hasAnyMention: params.event.mentioned,
            implicitMentionKinds: params.event.chatType === "thread" ? ["bot_thread_participant"] : [],
        },
    };
}
function deliveryResultMessageId(result) {
    if (!isRecord(result))
        return undefined;
    const value = result.messageId;
    return typeof value === "string" && value.trim() ? value : undefined;
}
function dispatched(result) {
    return result.dispatched === true;
}
function errorText(error) {
    return error instanceof Error ? error.message : String(error);
}
export async function dispatchCliqEventToNativeOpenClaw(options) {
    const cfg = withCliqDirectSessionScope(options.cfg);
    const runtime = options.runtime.channel;
    const facts = resolveCliqNativeRouteFacts({
        account: options.account,
        event: options.event,
    });
    const route = runtime.routing.resolveAgentRoute({
        cfg,
        channel: CLIQ_CHANNEL_ID,
        accountId: options.account.accountId,
        peer: facts.routePeer,
        parentPeer: facts.parentPeer,
    });
    const storePath = runtime.session.resolveStorePath(undefined, {
        agentId: route.agentId,
    });
    const timestamp = normalizeTimestamp(options.event.timestamp);
    const senderId = options.event.senderId ?? options.event.nativePeerId ?? options.event.peerId;
    const senderLabel = options.event.senderLabel ?? senderId;
    const updateLastRouteSessionKey = resolveInboundLastRouteSessionKey({
        route,
        sessionKey: route.sessionKey,
    });
    const ctxPayload = runtime.turn.buildContext({
        channel: CLIQ_CHANNEL_ID,
        accountId: route.accountId,
        provider: CLIQ_CHANNEL_ID,
        surface: CLIQ_CHANNEL_ID,
        messageId: options.event.messageId,
        timestamp,
        from: senderLabel,
        sender: {
            id: senderId,
            displayLabel: senderLabel,
            name: options.event.senderLabel,
        },
        conversation: {
            kind: facts.routeKind,
            id: facts.routePeer.id,
            label: options.event.peerId,
            parentId: facts.parentPeer?.id,
            threadId: options.event.threadId,
            nativeChannelId: facts.nativeChannelId,
            routePeer: facts.routePeer,
        },
        route: {
            agentId: route.agentId,
            accountId: route.accountId,
            routeSessionKey: route.sessionKey,
            mainSessionKey: route.mainSessionKey,
            createIfMissing: true,
        },
        reply: {
            to: facts.target,
            originatingTo: facts.target,
            nativeChannelId: facts.nativeChannelId,
            replyTarget: facts.target,
            deliveryTarget: facts.target,
            replyToId: options.event.messageId,
            messageThreadId: options.event.threadId,
            threadParentId: facts.parentPeer?.id,
            sourceReplyDeliveryMode: options.event.threadId ? "thread" : "reply",
        },
        message: {
            body: options.event.text,
            rawBody: options.event.text,
            bodyForAgent: options.event.text,
            commandBody: options.event.text,
            envelopeFrom: senderLabel,
            senderLabel,
            preview: options.event.text.slice(0, 200),
        },
        access: buildAccessFacts({
            account: options.account,
            event: options.event,
        }),
        supplemental: {
            untrustedContext: [
                {
                    source: "zoho-cliq",
                    sourceKind: options.source ?? "manual",
                    handlerKind: options.handlerKind,
                    accountId: options.account.accountId,
                    network: options.event.network,
                    chatType: options.event.chatType,
                    peerId: options.event.peerId,
                    chatId: options.event.chatId,
                    channelId: options.event.channelId,
                    threadId: options.event.threadId,
                },
            ],
        },
        extra: {
            ExplicitDeliverRoute: true,
            NativeDirectUserId: options.event.chatType === "direct" ? options.event.nativePeerId : undefined,
        },
    });
    const deliveryStats = {
        count: 0,
        messageIds: [],
    };
    let result;
    try {
        result = await runtime.turn.run({
            channel: CLIQ_CHANNEL_ID,
            accountId: route.accountId,
            raw: options.event,
            adapter: {
                ingest: () => ({
                    id: options.event.messageId,
                    timestamp,
                    rawText: options.event.text,
                    textForAgent: options.event.text,
                    textForCommands: options.event.text,
                    raw: options.event.raw,
                }),
                resolveTurn: () => ({
                    cfg,
                    channel: CLIQ_CHANNEL_ID,
                    accountId: route.accountId,
                    agentId: route.agentId,
                    routeSessionKey: route.sessionKey,
                    storePath,
                    ctxPayload,
                    recordInboundSession: runtime.session.recordInboundSession,
                    dispatchReplyWithBufferedBlockDispatcher: runtime.reply.dispatchReplyWithBufferedBlockDispatcher,
                    record: {
                        createIfMissing: true,
                        updateLastRoute: {
                            sessionKey: updateLastRouteSessionKey,
                            channel: CLIQ_CHANNEL_ID,
                            to: facts.target,
                            accountId: route.accountId,
                            ...(options.event.threadId ? { threadId: options.event.threadId } : {}),
                        },
                        onRecordError: (error) => {
                            options.logger?.warn?.(`[zoho-cliq] native inbound session record failed: ${errorText(error)}`);
                        },
                    },
                    delivery: {
                        deliver: async (payload) => {
                            if (payload.isReasoning === true ||
                                !hasOutboundReplyContent(payload, { trimText: true })) {
                                return { visibleReplySent: false };
                            }
                            const adapter = await runtime.outbound.loadAdapter(CLIQ_CHANNEL_ID);
                            if (!adapter?.sendText) {
                                throw new Error("cliq_outbound_adapter_unavailable");
                            }
                            const mediaUrls = resolveOutboundMediaUrls(payload);
                            const outboundPayload = mediaUrls.length > 0 && !adapter.sendMedia
                                ? {
                                    ...payload,
                                    text: formatTextWithAttachmentLinks(payload.text, mediaUrls),
                                    mediaUrl: undefined,
                                    mediaUrls: [],
                                }
                                : payload;
                            const deliveryRoute = resolveCliqDeliveryRoute({
                                event: options.event,
                                facts,
                                payloadReplyToId: outboundPayload.replyToId,
                            });
                            const sent = await sendTextMediaPayload({
                                channel: CLIQ_CHANNEL_ID,
                                ctx: {
                                    cfg,
                                    accountId: route.accountId,
                                    to: deliveryRoute.to,
                                    text: outboundPayload.text ?? "",
                                    replyToId: deliveryRoute.replyToId,
                                    threadId: options.event.threadId ?? null,
                                    payload: outboundPayload,
                                },
                                adapter,
                            });
                            deliveryStats.count += 1;
                            const messageId = deliveryResultMessageId(sent);
                            if (messageId)
                                deliveryStats.messageIds.push(messageId);
                            return {
                                messageIds: messageId ? [messageId] : [],
                                replyToId: deliveryRoute.replyToId ?? undefined,
                                threadId: options.event.threadId,
                                visibleReplySent: Boolean(messageId || outboundPayload.text),
                            };
                        },
                        onError: (error, info) => {
                            options.logger?.warn?.(`[zoho-cliq] native ${info.kind} reply delivery failed: ${errorText(error)}`);
                        },
                    },
                }),
            },
            log: (event) => {
                if (event.event === "error") {
                    options.logger?.warn?.(`[zoho-cliq] native turn ${event.stage} failed for ${event.messageId ?? options.event.messageId}: ${errorText(event.error)}`);
                }
            },
        });
    }
    catch (error) {
        emitCliqAuditEvent(options.logger, buildCliqAuditEvent({
            kind: "native_dispatch",
            outcome: "failed",
            account: options.account,
            source: options.source ?? "manual",
            handlerKind: options.handlerKind,
            reason: errorText(error),
            event: options.event,
            security: options.security,
            nativeDispatch: {
                target: facts.target,
                routeSessionKey: route.sessionKey,
                deliveryCount: deliveryStats.count,
                messageIds: deliveryStats.messageIds,
            },
        }));
        throw error;
    }
    emitCliqAuditEvent(options.logger, buildCliqAuditEvent({
        kind: "native_dispatch",
        outcome: dispatched(result) ? "dispatched" : "skipped",
        account: options.account,
        source: options.source ?? "manual",
        handlerKind: options.handlerKind,
        event: options.event,
        security: options.security,
        nativeDispatch: {
            admission: result.admission.kind,
            agentId: route.agentId,
            matchedBy: route.matchedBy,
            target: facts.target,
            routeSessionKey: dispatched(result)
                ? result.routeSessionKey
                : result.routeSessionKey,
            deliveryCount: deliveryStats.count,
            messageIds: deliveryStats.messageIds,
        },
    }));
    return {
        ok: true,
        dispatched: dispatched(result),
        admission: result.admission.kind,
        agentId: route.agentId,
        accountId: route.accountId,
        matchedBy: route.matchedBy,
        routeSessionKey: dispatched(result)
            ? result.routeSessionKey
            : result.routeSessionKey,
        target: facts.target,
        replyToId: options.event.messageId,
        ...(options.event.threadId ? { threadId: options.event.threadId } : {}),
        deliveryCount: deliveryStats.count,
        messageIds: deliveryStats.messageIds,
        dispatchResult: dispatched(result) ? result.dispatchResult : undefined,
    };
}
export function createCliqNativeEventDispatcher(api) {
    return async (event, context) => dispatchCliqEventToNativeOpenClaw({
        cfg: api.config,
        runtime: api.runtime,
        logger: api.logger,
        account: context.account,
        event,
        source: context.source ?? "manual",
        handlerKind: context.handlerKind,
        security: context.security,
    });
}
