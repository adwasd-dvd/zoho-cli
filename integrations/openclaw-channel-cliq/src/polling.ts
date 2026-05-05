import type { OpenClawConfig, PluginLogger } from "openclaw/plugin-sdk";

import type { CliqResolvedAccount } from "./config.js";
import {
  createCliqInboundDedupeStore,
  evaluateCliqPollingEventSecurity,
  normalizeCliqInboundMessage,
  type CliqInboundDedupeStore,
  type CliqMentionMatcher,
  type CliqNormalizedInboundEvent,
} from "./inbound.js";
import {
  type CliqInboundLifecycleResult,
} from "./lifecycle.js";
import {
  resolveCliqTurnLedger,
  runCliqInboundTurn,
  type CliqInboundTurnResult,
  type CliqTurnLedgerOption,
} from "./turn-ledger.js";
import type { CliqNativeEventDispatcher } from "./native-dispatch.js";
import { buildCliqAuditEvent, emitCliqAuditEvent } from "./observability.js";
import type { CliqInboundSecurityDecision } from "./security.js";
import { fetchCliqContext, listCliqChats } from "./zoho-cli.js";

export type CliqPollingSkipReason =
  | "invalid_chat"
  | "invalid_message"
  | "duplicate"
  | "security_denied"
  | "turn_active"
  | "dead_lettered";

export type CliqPollingSkippedEvent = {
  reason: CliqPollingSkipReason;
  chat?: unknown;
  message?: unknown;
  event?: CliqNormalizedInboundEvent;
  turn?: CliqInboundTurnResult["turn"];
  securityReasonCode?: string;
  securityReason?: string;
};

export type CliqPollingResult = {
  events: CliqNormalizedInboundEvent[];
  dispatchedCount: number;
  lifecycle: CliqInboundLifecycleResult[];
  turns: CliqInboundTurnResult[];
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
  lifecycle?: Parameters<typeof runCliqInboundTurn>[0]["lifecycle"];
  turnLedger?: CliqTurnLedgerOption;
  nativeDispatch?: CliqNativeEventDispatcher;
  onEvent?: (event: CliqNormalizedInboundEvent) => void | Promise<void>;
  logger?: Partial<PluginLogger>;
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

function emitPollingAudit(params: {
  options: CliqPollingOptions;
  outcome: "accepted" | "ignored" | "denied" | "failed" | "dispatched" | "skipped";
  reason?: string;
  event?: CliqNormalizedInboundEvent;
  security?: CliqInboundSecurityDecision;
  turn?: CliqInboundTurnResult["turn"];
  lifecycle?: CliqInboundLifecycleResult;
}): void {
  emitCliqAuditEvent(
    params.options.logger,
    buildCliqAuditEvent({
      kind: "polling_ingress",
      outcome: params.outcome,
      account: params.options.account,
      source: "polling",
      reason: params.reason,
      event: params.event,
      security: params.security as Record<string, unknown> | undefined,
      turn: params.turn,
      lifecycle: params.lifecycle,
    }),
  );
}

export async function pollCliqInboundOnce(
  options: CliqPollingOptions,
): Promise<CliqPollingResult> {
  const dedupe = options.dedupe ?? createCliqInboundDedupeStore();
  const turnLedger = resolveCliqTurnLedger(options.turnLedger);
  const chats = await listCliqChats({
    account: options.account,
    limit: options.limit ?? 50,
    unreadOnly: true,
    excludeReactedBySelf: true,
  });
  const events: CliqNormalizedInboundEvent[] = [];
  const lifecycle: CliqInboundLifecycleResult[] = [];
  const turns: CliqInboundTurnResult[] = [];
  const skipped: CliqPollingSkippedEvent[] = [];
  let dispatchedCount = 0;

  for (const chat of chats.chats) {
    const lookup = resolveChatLookup(chat);
    if (!lookup.chatId && !lookup.channelId) {
      emitPollingAudit({
        options,
        outcome: "ignored",
        reason: "invalid_chat",
      });
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
        emitPollingAudit({
          options,
          outcome: "ignored",
          reason: "invalid_message",
        });
        skipped.push({ reason: "invalid_message", chat, message });
        continue;
      }

      if (!dedupe.claim(event)) {
        emitPollingAudit({
          options,
          outcome: "skipped",
          reason: "duplicate",
          event,
        });
        skipped.push({ reason: "duplicate", chat, message, event });
        continue;
      }

      const security = evaluateCliqPollingEventSecurity({
        cfg: options.cfg,
        account: options.account,
        event,
      });
      if (!security.allowed) {
        emitPollingAudit({
          options,
          outcome: "denied",
          reason: security.reasonCode,
          event,
          security,
        });
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
        ? async (acceptedEvent: CliqNormalizedInboundEvent) => {
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
          emitPollingAudit({
            options,
            outcome: "skipped",
            reason:
              turnResult.skipReason === "conversation_active"
                ? "turn_active"
                : turnResult.skipReason === "dead_lettered"
                  ? "dead_lettered"
                  : "duplicate",
            event,
            security,
            turn: turnResult.turn,
            lifecycle: turnResult.lifecycle,
          });
          skipped.push({
            reason:
              turnResult.skipReason === "conversation_active"
                ? "turn_active"
                : turnResult.skipReason === "dead_lettered"
                  ? "dead_lettered"
                  : "duplicate",
            event,
            turn: turnResult.turn,
          });
          continue;
        }
        if (turnResult.lifecycle) lifecycle.push(turnResult.lifecycle);
        if (turnResult.dispatched) dispatchedCount += 1;
        emitPollingAudit({
          options,
          outcome: turnResult.error
            ? "failed"
            : turnResult.dispatched
              ? "dispatched"
              : "accepted",
          reason: turnResult.error,
          event,
          security,
          turn: turnResult.turn,
          lifecycle: turnResult.lifecycle,
        });
      } else {
        emitPollingAudit({
          options,
          outcome: "accepted",
          event,
          security,
        });
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
