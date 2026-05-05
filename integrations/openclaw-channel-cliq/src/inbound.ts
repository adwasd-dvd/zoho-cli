import type { OpenClawConfig } from "openclaw/plugin-sdk";

import type { CliqResolvedAccount } from "./config.js";
import {
  evaluateCliqInboundSecurity,
  type CliqChatKind,
  type CliqInboundSecurityDecision,
} from "./security.js";

const DEFAULT_CLIQ_NETWORK = "default";

export type CliqMentionMatcher = RegExp | string;

export type CliqNormalizedInboundEvent = {
  channel: "cliq";
  accountId: string;
  network: string;
  chatType: CliqChatKind;
  peerId: string;
  nativePeerId: string;
  chatId?: string;
  channelId?: string;
  messageId: string;
  senderId?: string;
  senderLabel?: string;
  threadId?: string;
  text: string;
  mentioned: boolean;
  timestamp?: string;
  dedupeKey: string;
  raw: unknown;
};

export type CliqInboundEvent = CliqNormalizedInboundEvent;

export type CliqInboundDedupeStore = {
  readonly size: number;
  has(keyOrEvent: string | CliqNormalizedInboundEvent): boolean;
  claim(keyOrEvent: string | CliqNormalizedInboundEvent): boolean;
  mark(keyOrEvent: string | CliqNormalizedInboundEvent): void;
  takeNew(events: CliqNormalizedInboundEvent[]): CliqNormalizedInboundEvent[];
  clear(): void;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function normalizeText(value: unknown): string | undefined {
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed || undefined;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  return undefined;
}

function normalizeBool(value: unknown): boolean | undefined {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["true", "yes", "1"].includes(normalized)) return true;
    if (["false", "no", "0"].includes(normalized)) return false;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    if (value === 1) return true;
    if (value === 0) return false;
  }
  return undefined;
}

function readFirstText(
  value: Record<string, unknown> | undefined,
  keys: string[],
): string | undefined {
  if (!value) return undefined;
  for (const key of keys) {
    const normalized = normalizeText(value[key]);
    if (normalized) return normalized;
  }
  return undefined;
}

function readFirstBool(
  value: Record<string, unknown> | undefined,
  keys: string[],
): boolean | undefined {
  if (!value) return undefined;
  for (const key of keys) {
    const normalized = normalizeBool(value[key]);
    if (normalized !== undefined) return normalized;
  }
  return undefined;
}

function readFirstRecord(
  value: Record<string, unknown> | undefined,
  keys: string[],
): Record<string, unknown> | undefined {
  if (!value) return undefined;
  for (const key of keys) {
    const nested = value[key];
    if (isRecord(nested)) return nested;
  }
  return undefined;
}

function normalizeDedupePart(value: string | undefined, fallback: string): string {
  return (value?.trim() || fallback).toLowerCase();
}

function normalizeNetwork(network?: string | null): string {
  return network?.trim() || DEFAULT_CLIQ_NETWORK;
}

function normalizeTimestamp(value: unknown): string | undefined {
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

function readTimestamp(
  message: Record<string, unknown>,
  raw: Record<string, unknown> | undefined,
): string | undefined {
  for (const record of [message, raw]) {
    if (!record) continue;
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
      if (timestamp) return timestamp;
    }
  }
  return undefined;
}

function readSenderLabel(
  message: Record<string, unknown>,
  sender: Record<string, unknown> | undefined,
): string | undefined {
  return (
    readFirstText(sender, ["displayName", "display_name", "name", "email"]) ??
    readFirstText(message, [
      "senderLabel",
      "sender_label",
      "senderName",
      "sender_name",
      "fromName",
      "from_name",
    ])
  );
}

function readMessageText(
  message: Record<string, unknown>,
  raw: Record<string, unknown> | undefined,
): string | undefined {
  const direct =
    readFirstText(message, [
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
  if (direct !== undefined) return direct;

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
    if (nested !== undefined) return nested;
  }
  return undefined;
}

function inferChatKind(params: {
  chat?: Record<string, unknown>;
  message: Record<string, unknown>;
  raw?: Record<string, unknown>;
  threadId?: string;
}): CliqChatKind {
  const kind =
    readFirstText(params.message, [
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
  if (normalized.includes("thread")) return "thread";
  if (
    ["dm", "direct", "user", "one_to_one", "one-to-one", "private"].some(
      (needle) => normalized.includes(needle),
    )
  ) {
    return "direct";
  }
  if (normalized.includes("channel")) return "channel";
  if (
    ["group", "chat", "conversation", "room"].some((needle) =>
      normalized.includes(needle),
    )
  ) {
    return "group";
  }
  if (params.threadId) return "thread";
  if (
    readFirstText(params.message, ["userId", "user_id"]) ||
    readFirstText(params.chat, ["userId", "user_id"])
  ) {
    return "direct";
  }
  if (
    readFirstText(params.message, ["channelId", "channel_id"]) ||
    readFirstText(params.chat, ["channelId", "channel_id"])
  ) {
    return "channel";
  }
  return "group";
}

function buildPeerId(chatType: CliqChatKind, nativePeerId: string): string {
  if (chatType === "direct") return `user:${nativePeerId}`;
  if (chatType === "channel" || chatType === "thread") {
    return `channel:${nativePeerId}`;
  }
  return `chat:${nativePeerId}`;
}

function messageMentionsText(
  text: string,
  mentionMatchers: CliqMentionMatcher[] | undefined,
): boolean {
  if (!mentionMatchers?.length) return false;
  return mentionMatchers.some((matcher) => {
    if (typeof matcher === "string") {
      return text.toLowerCase().includes(matcher.trim().toLowerCase());
    }
    matcher.lastIndex = 0;
    return matcher.test(text);
  });
}

function messageMentionsBot(
  message: Record<string, unknown>,
  raw: Record<string, unknown> | undefined,
  text: string,
  mentionMatchers: CliqMentionMatcher[] | undefined,
): boolean {
  const explicit =
    readFirstBool(message, [
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
  if (explicit !== undefined) return explicit;
  return messageMentionsText(text, mentionMatchers);
}

export function isCliqSelfAuthoredMessage(
  message: unknown,
  selfUserIds: string[] = [],
): boolean {
  const record = isRecord(message) ? message : undefined;
  if (!record) return false;
  const raw = readFirstRecord(record, ["raw"]);
  const explicit =
    readFirstBool(record, [
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
  if (explicit !== undefined) return explicit;

  const sender =
    readFirstRecord(record, ["sender", "from", "user", "createdBy", "created_by"]) ??
    readFirstRecord(raw, ["sender", "from", "user", "createdBy", "created_by"]);
  const senderId =
    readFirstText(record, ["senderId", "sender_id", "userId", "user_id"]) ??
    readFirstText(raw, ["senderId", "sender_id", "userId", "user_id"]) ??
    readFirstText(sender, ["id", "zuid", "userId", "user_id", "email"]);
  if (!senderId || selfUserIds.length === 0) return false;
  const normalizedSender = senderId.trim().toLowerCase();
  return selfUserIds.some((id) => id.trim().toLowerCase() === normalizedSender);
}

export function buildCliqInboundDedupeKey(event: {
  accountId: string;
  network?: string;
  peerId?: string;
  chatId?: string;
  channelId?: string;
  messageId: string;
}): string {
  const peerId =
    event.peerId ||
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

export function normalizeCliqInboundMessage(params: {
  accountId: string;
  network?: string | null;
  chat?: unknown;
  message: unknown;
  mentionMatchers?: CliqMentionMatcher[];
  selfUserIds?: string[];
  skipSelfAuthored?: boolean;
}): CliqNormalizedInboundEvent | null {
  const message = isRecord(params.message) ? params.message : undefined;
  if (!message) return null;
  if (params.skipSelfAuthored !== false) {
    if (isCliqSelfAuthoredMessage(message, params.selfUserIds)) return null;
  }

  const chat = isRecord(params.chat) ? params.chat : undefined;
  const raw = readFirstRecord(message, ["raw"]) ?? message;
  const messageId =
    readFirstText(message, ["messageId", "message_id", "msgId", "msg_id", "id"]) ??
    readFirstText(raw, ["messageId", "message_id", "msgId", "msg_id", "id"]);
  if (!messageId) return null;

  const sender =
    readFirstRecord(message, ["sender", "from", "user", "createdBy", "created_by"]) ??
    readFirstRecord(raw, ["sender", "from", "user", "createdBy", "created_by"]);
  const senderId =
    readFirstText(message, [
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
  if (text === undefined) return null;

  const chatId =
    readFirstText(message, ["chatId", "chat_id", "conversationId", "conversation_id"]) ??
    readFirstText(raw, ["chatId", "chat_id", "conversationId", "conversation_id"]) ??
    readFirstText(chat, [
      "chatId",
      "chat_id",
      "conversationId",
      "conversation_id",
      "id",
    ]);
  const channelId =
    readFirstText(message, ["channelId", "channel_id"]) ??
    readFirstText(raw, ["channelId", "channel_id"]) ??
    readFirstText(chat, ["channelId", "channel_id"]);
  const groupId =
    readFirstText(message, ["groupId", "group_id", "roomId", "room_id"]) ??
    readFirstText(raw, ["groupId", "group_id", "roomId", "room_id"]) ??
    readFirstText(chat, ["groupId", "group_id", "roomId", "room_id"]);
  const threadId =
    readFirstText(message, [
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
  const nativePeerId =
    (chatType === "direct" ? senderId : undefined) ??
    (chatType === "channel" || chatType === "thread" ? channelId : undefined) ??
    groupId ??
    chatId;
  if (!nativePeerId) return null;

  const peerId = buildPeerId(chatType, nativePeerId);
  const mentioned =
    chatType === "direct"
      ? true
      : messageMentionsBot(message, raw, text, params.mentionMatchers);
  const network = normalizeNetwork(params.network);
  const event: CliqNormalizedInboundEvent = {
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

function extractPayloadMessages(payload: unknown): unknown[] {
  if (Array.isArray(payload)) return payload;
  if (!isRecord(payload)) return [];
  for (const key of ["messages", "data", "items", "records", "result"]) {
    const value = payload[key];
    if (Array.isArray(value)) return value;
    if (isRecord(value)) {
      const nested = extractPayloadMessages(value);
      if (nested.length > 0) return nested;
    }
  }
  return [];
}

export function normalizeCliqContextMessages(params: {
  accountId: string;
  network?: string;
  payload: unknown;
  chat?: unknown;
  defaultChatId?: string;
  defaultChannelId?: string;
  mentionMatchers?: CliqMentionMatcher[];
  selfUserIds?: string[];
}): CliqNormalizedInboundEvent[] {
  const payloadRecord = isRecord(params.payload) ? params.payload : undefined;
  const chat = {
    ...(isRecord(params.chat) ? params.chat : {}),
    ...(payloadRecord ? payloadRecord : {}),
    ...(params.defaultChatId ? { chatId: params.defaultChatId } : {}),
    ...(params.defaultChannelId ? { channelId: params.defaultChannelId } : {}),
  };
  return extractPayloadMessages(params.payload)
    .map((message) =>
      normalizeCliqInboundMessage({
        accountId: params.accountId,
        network: params.network,
        chat,
        message,
        mentionMatchers: params.mentionMatchers,
        selfUserIds: params.selfUserIds,
      }),
    )
    .filter((event): event is CliqNormalizedInboundEvent => Boolean(event));
}

export function normalizeCliqWatchMessages(
  params: Parameters<typeof normalizeCliqContextMessages>[0],
): CliqNormalizedInboundEvent[] {
  return normalizeCliqContextMessages(params);
}

function keyOf(keyOrEvent: string | CliqNormalizedInboundEvent): string {
  return typeof keyOrEvent === "string" ? keyOrEvent : keyOrEvent.dedupeKey;
}

class InMemoryCliqInboundDedupeStore implements CliqInboundDedupeStore {
  private readonly seen = new Map<string, number>();
  private readonly maxEntries: number;

  constructor(maxEntries = 5000) {
    this.maxEntries = Math.max(100, Math.floor(maxEntries));
  }

  get size(): number {
    return this.seen.size;
  }

  has(keyOrEvent: string | CliqNormalizedInboundEvent): boolean {
    const key = keyOf(keyOrEvent);
    return Boolean(key) && this.seen.has(key);
  }

  claim(keyOrEvent: string | CliqNormalizedInboundEvent): boolean {
    const key = keyOf(keyOrEvent);
    if (!key || this.seen.has(key)) return false;
    this.mark(key);
    return true;
  }

  mark(keyOrEvent: string | CliqNormalizedInboundEvent): void {
    const key = keyOf(keyOrEvent);
    if (!key) return;
    this.seen.set(key, Date.now());
    while (this.seen.size > this.maxEntries) {
      const oldest = this.seen.keys().next().value;
      if (typeof oldest !== "string") break;
      this.seen.delete(oldest);
    }
  }

  takeNew(events: CliqNormalizedInboundEvent[]): CliqNormalizedInboundEvent[] {
    return events.filter((event) => this.claim(event));
  }

  clear(): void {
    this.seen.clear();
  }
}

export const CliqInboundDedupeStore = InMemoryCliqInboundDedupeStore;

export function createCliqInboundDedupeStore(
  maxEntries?: number,
): CliqInboundDedupeStore {
  return new InMemoryCliqInboundDedupeStore(maxEntries);
}

export function evaluateCliqPollingEventSecurity(params: {
  cfg?: OpenClawConfig;
  account: CliqResolvedAccount;
  event: CliqNormalizedInboundEvent;
  intent?: string | null;
}): CliqInboundSecurityDecision {
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
