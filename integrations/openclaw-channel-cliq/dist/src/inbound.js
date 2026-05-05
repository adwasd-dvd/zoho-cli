import { evaluateCliqInboundSecurity, } from "./security.js";
const DEFAULT_CLIQ_NETWORK = "default";
function isRecord(value) {
    return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
function normalizeText(value) {
    if (typeof value === "string") {
        const trimmed = value.trim();
        return trimmed || undefined;
    }
    if (typeof value === "number" && Number.isFinite(value)) {
        return String(value);
    }
    return undefined;
}
function normalizeBool(value) {
    if (typeof value === "boolean")
        return value;
    if (typeof value === "string") {
        const normalized = value.trim().toLowerCase();
        if (["true", "yes", "1"].includes(normalized))
            return true;
        if (["false", "no", "0"].includes(normalized))
            return false;
    }
    if (typeof value === "number" && Number.isFinite(value)) {
        if (value === 1)
            return true;
        if (value === 0)
            return false;
    }
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
function readFirstBool(value, keys) {
    if (!value)
        return undefined;
    for (const key of keys) {
        const normalized = normalizeBool(value[key]);
        if (normalized !== undefined)
            return normalized;
    }
    return undefined;
}
function readFirstRecord(value, keys) {
    if (!value)
        return undefined;
    for (const key of keys) {
        const nested = value[key];
        if (isRecord(nested))
            return nested;
    }
    return undefined;
}
function normalizeDedupePart(value, fallback) {
    return (value?.trim() || fallback).toLowerCase();
}
function normalizeNetwork(network) {
    return network?.trim() || DEFAULT_CLIQ_NETWORK;
}
function normalizeTimestamp(value) {
    if (typeof value === "number" && Number.isFinite(value)) {
        const milliseconds = value > 10_000_000_000 ? value : value * 1000;
        return new Date(milliseconds).toISOString();
    }
    if (typeof value === "string" && value.trim()) {
        const parsedNumber = Number(value.trim());
        if (Number.isFinite(parsedNumber)) {
            return normalizeTimestamp(parsedNumber);
        }
        const parsedDate = Date.parse(value);
        if (Number.isFinite(parsedDate)) {
            return new Date(parsedDate).toISOString();
        }
    }
    return undefined;
}
function readTimestamp(message, raw) {
    for (const record of [message, raw]) {
        if (!record)
            continue;
        for (const key of [
            "timestamp",
            "timestampMs",
            "time",
            "createdTime",
            "created_time",
            "createdAt",
            "created_at",
            "sentTime",
            "sent_time",
        ]) {
            const timestamp = normalizeTimestamp(record[key]);
            if (timestamp)
                return timestamp;
        }
    }
    return undefined;
}
function readSenderLabel(message, sender) {
    return (readFirstText(sender, ["displayName", "display_name", "name", "email"]) ??
        readFirstText(message, [
            "senderLabel",
            "sender_label",
            "senderName",
            "sender_name",
            "fromName",
            "from_name",
        ]));
}
function readMessageText(message, raw) {
    const direct = readFirstText(message, [
        "text",
        "plainText",
        "plain_text",
        "message",
        "messageText",
        "message_text",
        "body",
        "contentText",
        "content_text",
    ]) ??
        readFirstText(raw, [
            "text",
            "plainText",
            "plain_text",
            "message",
            "messageText",
            "message_text",
            "body",
            "contentText",
            "content_text",
        ]);
    if (direct !== undefined)
        return direct;
    for (const container of [
        readFirstRecord(message, ["content", "payload"]),
        readFirstRecord(raw, ["content", "payload"]),
    ]) {
        const nested = readFirstText(container, [
            "text",
            "plainText",
            "plain_text",
            "message",
            "body",
        ]);
        if (nested !== undefined)
            return nested;
    }
    return undefined;
}
function inferChatKind(params) {
    const kind = readFirstText(params.message, [
        "chatType",
        "chat_type",
        "conversationType",
        "conversation_type",
        "type",
        "kind",
    ]) ??
        readFirstText(params.raw, [
            "chatType",
            "chat_type",
            "conversationType",
            "conversation_type",
            "type",
            "kind",
        ]) ??
        readFirstText(params.chat, [
            "chatType",
            "chat_type",
            "conversationType",
            "conversation_type",
            "type",
            "kind",
        ]);
    const normalized = kind?.trim().toLowerCase() ?? "";
    if (normalized.includes("thread"))
        return "thread";
    if (["dm", "direct", "user", "one_to_one", "one-to-one", "private"].some((needle) => normalized.includes(needle))) {
        return "direct";
    }
    if (normalized.includes("channel"))
        return "channel";
    if (["group", "chat", "conversation", "room"].some((needle) => normalized.includes(needle))) {
        return "group";
    }
    if (params.threadId)
        return "thread";
    if (readFirstText(params.message, ["userId", "user_id"]) ||
        readFirstText(params.chat, ["userId", "user_id"])) {
        return "direct";
    }
    if (readFirstText(params.message, ["channelId", "channel_id"]) ||
        readFirstText(params.chat, ["channelId", "channel_id"])) {
        return "channel";
    }
    return "group";
}
function buildPeerId(chatType, nativePeerId) {
    if (chatType === "direct")
        return `user:${nativePeerId}`;
    if (chatType === "channel" || chatType === "thread") {
        return `channel:${nativePeerId}`;
    }
    return `chat:${nativePeerId}`;
}
function messageMentionsText(text, mentionMatchers) {
    if (!mentionMatchers?.length)
        return false;
    return mentionMatchers.some((matcher) => {
        if (typeof matcher === "string") {
            return text.toLowerCase().includes(matcher.trim().toLowerCase());
        }
        matcher.lastIndex = 0;
        return matcher.test(text);
    });
}
function messageMentionsBot(message, raw, text, mentionMatchers) {
    const explicit = readFirstBool(message, [
        "mentioned",
        "isMentioned",
        "is_mentioned",
        "mentionsBot",
        "mentions_bot",
        "botMentioned",
        "bot_mentioned",
    ]) ??
        readFirstBool(raw, [
            "mentioned",
            "isMentioned",
            "is_mentioned",
            "mentionsBot",
            "mentions_bot",
            "botMentioned",
            "bot_mentioned",
        ]);
    if (explicit !== undefined)
        return explicit;
    return messageMentionsText(text, mentionMatchers);
}
export function isCliqSelfAuthoredMessage(message, selfUserIds = []) {
    const record = isRecord(message) ? message : undefined;
    if (!record)
        return false;
    const raw = readFirstRecord(record, ["raw"]);
    const explicit = readFirstBool(record, [
        "self",
        "isSelf",
        "is_self",
        "fromMe",
        "from_me",
        "sentByMe",
        "sent_by_me",
        "authoredBySelf",
        "authored_by_self",
    ]) ??
        readFirstBool(raw, [
            "self",
            "isSelf",
            "is_self",
            "fromMe",
            "from_me",
            "sentByMe",
            "sent_by_me",
            "authoredBySelf",
            "authored_by_self",
        ]);
    if (explicit !== undefined)
        return explicit;
    const sender = readFirstRecord(record, ["sender", "from", "user", "createdBy", "created_by"]) ??
        readFirstRecord(raw, ["sender", "from", "user", "createdBy", "created_by"]);
    const senderId = readFirstText(record, ["senderId", "sender_id", "userId", "user_id"]) ??
        readFirstText(raw, ["senderId", "sender_id", "userId", "user_id"]) ??
        readFirstText(sender, ["id", "zuid", "userId", "user_id", "email"]);
    if (!senderId || selfUserIds.length === 0)
        return false;
    const normalizedSender = senderId.trim().toLowerCase();
    return selfUserIds.some((id) => id.trim().toLowerCase() === normalizedSender);
}
export function buildCliqInboundDedupeKey(event) {
    const peerId = event.peerId ||
        (event.channelId ? `channel:${event.channelId}` : undefined) ||
        (event.chatId ? `chat:${event.chatId}` : undefined);
    return [
        "account",
        normalizeDedupePart(event.accountId, "default"),
        "network",
        normalizeDedupePart(event.network, DEFAULT_CLIQ_NETWORK),
        "peer",
        normalizeDedupePart(peerId, "unknown"),
        "message",
        normalizeDedupePart(event.messageId, "unknown"),
    ].join(":");
}
export function normalizeCliqInboundMessage(params) {
    const message = isRecord(params.message) ? params.message : undefined;
    if (!message)
        return null;
    if (params.skipSelfAuthored !== false) {
        if (isCliqSelfAuthoredMessage(message, params.selfUserIds))
            return null;
    }
    const chat = isRecord(params.chat) ? params.chat : undefined;
    const rawRecord = readFirstRecord(message, ["raw"]);
    const raw = rawRecord ?? message;
    const messageId = readFirstText(message, ["messageId", "message_id", "msgId", "msg_id", "id"]) ??
        readFirstText(raw, ["messageId", "message_id", "msgId", "msg_id", "id"]);
    if (!messageId)
        return null;
    const sender = readFirstRecord(message, ["sender", "from", "user", "createdBy", "created_by"]) ??
        readFirstRecord(raw, ["sender", "from", "user", "createdBy", "created_by"]);
    const senderId = readFirstText(message, [
        "senderId",
        "sender_id",
        "fromId",
        "from_id",
        "userId",
        "user_id",
    ]) ??
        readFirstText(raw, [
            "senderId",
            "sender_id",
            "fromId",
            "from_id",
            "userId",
            "user_id",
        ]) ??
        readFirstText(sender, ["id", "zuid", "userId", "user_id", "email"]);
    const text = readMessageText(message, raw);
    if (text === undefined)
        return null;
    const chatId = readFirstText(message, ["chatId", "chat_id", "conversationId", "conversation_id"]) ??
        readFirstText(rawRecord, [
            "chatId",
            "chat_id",
            "conversationId",
            "conversation_id",
        ]) ??
        readFirstText(chat, [
            "chatId",
            "chat_id",
            "conversationId",
            "conversation_id",
            "id",
        ]);
    const channelId = readFirstText(message, ["channelId", "channel_id"]) ??
        readFirstText(raw, ["channelId", "channel_id"]) ??
        readFirstText(chat, ["channelId", "channel_id"]);
    const groupId = readFirstText(message, ["groupId", "group_id", "roomId", "room_id"]) ??
        readFirstText(raw, ["groupId", "group_id", "roomId", "room_id"]) ??
        readFirstText(chat, ["groupId", "group_id", "roomId", "room_id"]);
    const threadId = readFirstText(message, [
        "threadId",
        "thread_id",
        "replyToId",
        "reply_to_id",
        "parentMessageId",
        "parent_message_id",
    ]) ??
        readFirstText(raw, [
            "threadId",
            "thread_id",
            "replyToId",
            "reply_to_id",
            "parentMessageId",
            "parent_message_id",
        ]);
    const chatType = inferChatKind({ chat, message, raw, threadId });
    const nativePeerId = (chatType === "direct" ? senderId : undefined) ??
        (chatType === "channel" || chatType === "thread" ? channelId : undefined) ??
        groupId ??
        chatId;
    if (!nativePeerId)
        return null;
    const peerId = buildPeerId(chatType, nativePeerId);
    const mentioned = chatType === "direct"
        ? true
        : messageMentionsBot(message, raw, text, params.mentionMatchers);
    const network = normalizeNetwork(params.network);
    const event = {
        channel: "cliq",
        accountId: params.accountId,
        network,
        chatType,
        peerId,
        nativePeerId,
        ...(chatId ? { chatId } : {}),
        ...(channelId ? { channelId } : {}),
        messageId,
        ...(senderId ? { senderId } : {}),
        ...(readSenderLabel(message, sender)
            ? { senderLabel: readSenderLabel(message, sender) }
            : {}),
        ...(threadId ? { threadId } : {}),
        text,
        mentioned,
        ...(readTimestamp(message, raw) ? { timestamp: readTimestamp(message, raw) } : {}),
        dedupeKey: "",
        raw: params.message,
    };
    return {
        ...event,
        dedupeKey: buildCliqInboundDedupeKey(event),
    };
}
function extractPayloadMessages(payload) {
    if (Array.isArray(payload))
        return payload;
    if (!isRecord(payload))
        return [];
    for (const key of ["messages", "data", "items", "records", "result"]) {
        const value = payload[key];
        if (Array.isArray(value))
            return value;
        if (isRecord(value)) {
            const nested = extractPayloadMessages(value);
            if (nested.length > 0)
                return nested;
        }
    }
    return [];
}
export function normalizeCliqContextMessages(params) {
    const payloadRecord = isRecord(params.payload) ? params.payload : undefined;
    const chat = {
        ...(isRecord(params.chat) ? params.chat : {}),
        ...(payloadRecord ? payloadRecord : {}),
        ...(params.defaultChatId ? { chatId: params.defaultChatId } : {}),
        ...(params.defaultChannelId ? { channelId: params.defaultChannelId } : {}),
    };
    return extractPayloadMessages(params.payload)
        .map((message) => normalizeCliqInboundMessage({
        accountId: params.accountId,
        network: params.network,
        chat,
        message,
        mentionMatchers: params.mentionMatchers,
        selfUserIds: params.selfUserIds,
    }))
        .filter((event) => Boolean(event));
}
export function normalizeCliqWatchMessages(params) {
    return normalizeCliqContextMessages(params);
}
function keyOf(keyOrEvent) {
    return typeof keyOrEvent === "string" ? keyOrEvent : keyOrEvent.dedupeKey;
}
class InMemoryCliqInboundDedupeStore {
    seen = new Map();
    maxEntries;
    constructor(maxEntries = 5000) {
        this.maxEntries = Math.max(100, Math.floor(maxEntries));
    }
    get size() {
        return this.seen.size;
    }
    has(keyOrEvent) {
        const key = keyOf(keyOrEvent);
        return Boolean(key) && this.seen.has(key);
    }
    claim(keyOrEvent) {
        const key = keyOf(keyOrEvent);
        if (!key || this.seen.has(key))
            return false;
        this.mark(key);
        return true;
    }
    mark(keyOrEvent) {
        const key = keyOf(keyOrEvent);
        if (!key)
            return;
        this.seen.set(key, Date.now());
        while (this.seen.size > this.maxEntries) {
            const oldest = this.seen.keys().next().value;
            if (typeof oldest !== "string")
                break;
            this.seen.delete(oldest);
        }
    }
    forget(keyOrEvent) {
        const key = keyOf(keyOrEvent);
        if (!key)
            return;
        this.seen.delete(key);
    }
    takeNew(events) {
        return events.filter((event) => this.claim(event));
    }
    clear() {
        this.seen.clear();
    }
}
export const CliqInboundDedupeStore = InMemoryCliqInboundDedupeStore;
export function createCliqInboundDedupeStore(maxEntries) {
    return new InMemoryCliqInboundDedupeStore(maxEntries);
}
export function evaluateCliqPollingEventSecurity(params) {
    return evaluateCliqInboundSecurity({
        cfg: params.cfg,
        account: params.account,
        chatKind: params.event.chatType,
        senderId: params.event.senderId,
        conversationId: params.event.peerId,
        text: params.event.text,
        intent: params.intent,
        mentioned: params.event.mentioned,
    });
}
