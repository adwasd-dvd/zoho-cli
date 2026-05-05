import type { OpenClawConfig } from "openclaw/plugin-sdk";

import type { CliqResolvedAccount } from "./config.js";
import {
  createCliqInboundDedupeStore,
  evaluateCliqPollingEventSecurity,
  normalizeCliqInboundMessage,
  type CliqInboundDedupeStore,
  type CliqMentionMatcher,
  type CliqNormalizedInboundEvent,
} from "./inbound.js";
import { fetchCliqContext, listCliqChats } from "./zoho-cli.js";

export type CliqPollingSkipReason =
  | "invalid_chat"
  | "invalid_message"
  | "duplicate"
  | "security_denied";

export type CliqPollingSkippedEvent = {
  reason: CliqPollingSkipReason;
  chat?: unknown;
  message?: unknown;
  event?: CliqNormalizedInboundEvent;
  securityReasonCode?: string;
  securityReason?: string;
};

export type CliqPollingResult = {
  events: CliqNormalizedInboundEvent[];
  dispatchedCount: number;
  skipped: CliqPollingSkippedEvent[];
};

export type CliqPollingOptions = {
  cfg?: OpenClawConfig;
  account: CliqResolvedAccount;
  limit?: number;
  contextLimit?: number;
  mentionMatchers?: CliqMentionMatcher[];
  selfUserIds?: string[];
  dedupe?: CliqInboundDedupeStore;
  onEvent?: (event: CliqNormalizedInboundEvent) => void | Promise<void>;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function normalizeText(value: unknown): string | undefined {
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed || undefined;
  }
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
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

function resolveChatLookup(chat: unknown): {
  chatId?: string;
  channelId?: string;
} {
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

function extractMessages(context: unknown): unknown[] {
  if (Array.isArray(context)) return context;
  if (!isRecord(context)) return [];
  const messages = context.messages;
  return Array.isArray(messages) ? messages : [];
}

export async function pollCliqInboundOnce(
  options: CliqPollingOptions,
): Promise<CliqPollingResult> {
  const dedupe = options.dedupe ?? createCliqInboundDedupeStore();
  const chats = await listCliqChats({
    account: options.account,
    limit: options.limit ?? 50,
    unreadOnly: true,
    excludeReactedBySelf: true,
  });
  const events: CliqNormalizedInboundEvent[] = [];
  const skipped: CliqPollingSkippedEvent[] = [];
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
      if (options.onEvent) {
        await options.onEvent(event);
        dispatchedCount += 1;
      }
    }
  }

  return {
    events,
    dispatchedCount,
    skipped,
  };
}
