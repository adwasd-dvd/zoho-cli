import { createCliqInboundDedupeStore, evaluateCliqPollingEventSecurity, normalizeCliqInboundMessage, } from "./inbound.js";
import { resolveCliqTurnLedger, runCliqInboundTurn, } from "./turn-ledger.js";
import { fetchCliqContext, listCliqChats } from "./zoho-cli.js";
function isRecord(value) {
    return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
function normalizeText(value) {
    if (typeof value === "string") {
        const trimmed = value.trim();
        return trimmed || undefined;
    }
    if (typeof value === "number" && Number.isFinite(value))
        return String(value);
    return undefined;
}
function readFirstText(value, keys) {
    if (!value)
        return undefined;
    for (const key of keys) {
        const normalized = normalizeText(value[key]);
        if (normalized)
            return normalized;
    }
    return undefined;
}
function resolveChatLookup(chat) {
    const record = isRecord(chat) ? chat : undefined;
    const channelId = readFirstText(record, [
        "channelId",
        "channel_id",
        "channel",
    ]);
    const chatId = readFirstText(record, [
        "chatId",
        "chat_id",
        "conversationId",
        "conversation_id",
        "id",
    ]);
    return {
        ...(chatId ? { chatId } : {}),
        ...(channelId ? { channelId } : {}),
    };
}
function extractMessages(context) {
    if (Array.isArray(context))
        return context;
    if (!isRecord(context))
        return [];
    const messages = context.messages;
    return Array.isArray(messages) ? messages : [];
}
export async function pollCliqInboundOnce(options) {
    const dedupe = options.dedupe ?? createCliqInboundDedupeStore();
    const turnLedger = resolveCliqTurnLedger(options.turnLedger);
    const chats = await listCliqChats({
        account: options.account,
        limit: options.limit ?? 50,
        unreadOnly: true,
        excludeReactedBySelf: true,
    });
    const events = [];
    const lifecycle = [];
    const turns = [];
    const skipped = [];
    let dispatchedCount = 0;
    for (const chat of chats.chats) {
        const lookup = resolveChatLookup(chat);
        if (!lookup.chatId && !lookup.channelId) {
            skipped.push({ reason: "invalid_chat", chat });
            continue;
        }
        const context = await fetchCliqContext({
            account: options.account,
            chatId: lookup.chatId,
            channelId: lookup.channelId,
            limit: options.contextLimit ?? 20,
        });
        const messages = extractMessages(context);
        for (const message of messages) {
            const event = normalizeCliqInboundMessage({
                accountId: options.account.accountId,
                network: options.account.network,
                chat: { ...chat, ...lookup, ...context },
                message,
                mentionMatchers: options.mentionMatchers,
                selfUserIds: options.selfUserIds,
            });
            if (!event) {
                skipped.push({ reason: "invalid_message", chat, message });
                continue;
            }
            if (!dedupe.claim(event)) {
                skipped.push({ reason: "duplicate", chat, message, event });
                continue;
            }
            const security = evaluateCliqPollingEventSecurity({
                cfg: options.cfg,
                account: options.account,
                event,
            });
            if (!security.allowed) {
                skipped.push({
                    reason: "security_denied",
                    chat,
                    message,
                    event,
                    securityReasonCode: security.reasonCode,
                    securityReason: security.reason,
                });
                continue;
            }
            events.push(event);
            const dispatchEvent = options.nativeDispatch
                ? async (acceptedEvent) => {
                    await options.nativeDispatch?.(acceptedEvent, {
                        account: options.account,
                        source: "polling",
                        security,
                    });
                }
                : options.onEvent;
            if (dispatchEvent) {
                const turnResult = await runCliqInboundTurn({
                    account: options.account,
                    event,
                    turnLedger,
                    lifecycle: options.lifecycle,
                    onEvent: dispatchEvent,
                });
                turns.push(turnResult);
                if (turnResult.turn.state === "failed") {
                    dedupe.forget(event);
                }
                if (turnResult.skipped) {
                    skipped.push({
                        reason: turnResult.skipReason === "conversation_active"
                            ? "turn_active"
                            : turnResult.skipReason === "dead_lettered"
                                ? "dead_lettered"
                                : "duplicate",
                        event,
                        turn: turnResult.turn,
                    });
                    continue;
                }
                if (turnResult.lifecycle)
                    lifecycle.push(turnResult.lifecycle);
                if (turnResult.dispatched)
                    dispatchedCount += 1;
            }
        }
    }
    return {
        events,
        dispatchedCount,
        lifecycle,
        turns,
        skipped,
    };
}
