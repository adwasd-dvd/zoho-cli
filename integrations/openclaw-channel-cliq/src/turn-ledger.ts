import type { CliqResolvedAccount } from "./config.js";
import type { CliqNormalizedInboundEvent } from "./inbound.js";
import {
  CliqInboundLifecycleDispatchError,
  runCliqInboundLifecycle,
  type CliqInboundLifecycleOption,
  type CliqInboundLifecycleResult,
} from "./lifecycle.js";

export type CliqTurnLedgerState =
  | "active"
  | "completed"
  | "failed"
  | "dead_letter"
  | "coalesced";

export type CliqTurnLedgerRejectReason =
  | "duplicate_event"
  | "conversation_active"
  | "dead_lettered";

export type CliqTurnLedgerEntry = {
  turnId: string;
  eventKey: string;
  conversationKey: string;
  idempotencyKey: string;
  state: CliqTurnLedgerState;
  attempts: number;
  maxAttempts: number;
  messageId: string;
  accountId: string;
  network: string;
  peerId: string;
  chatId?: string;
  channelId?: string;
  threadId?: string;
  senderId?: string;
  lastAction: string;
  lastError?: string;
  deadLetterReason?: string;
  coalescedCount: number;
  coalescedEventKeys: string[];
  createdAt: string;
  updatedAt: string;
  activeExpiresAt?: string;
};

export type CliqTurnLedgerBeginResult =
  | {
      accepted: true;
      entry: CliqTurnLedgerEntry;
    }
  | {
      accepted: false;
      reason: CliqTurnLedgerRejectReason;
      entry: CliqTurnLedgerEntry;
    };

export type CliqTurnLedgerOptions = {
  maxEntries?: number;
  maxAttempts?: number;
  activeTtlMs?: number;
  now?: () => number;
};

export type CliqTurnLedgerStore = {
  readonly size: number;
  begin(event: CliqNormalizedInboundEvent): CliqTurnLedgerBeginResult;
  complete(event: CliqNormalizedInboundEvent): CliqTurnLedgerEntry;
  fail(event: CliqNormalizedInboundEvent, error: unknown): CliqTurnLedgerEntry;
  get(eventOrKey: CliqNormalizedInboundEvent | string): CliqTurnLedgerEntry | undefined;
  snapshot(): CliqTurnLedgerEntry[];
  clear(): void;
};

export type CliqTurnLedgerOption =
  | false
  | CliqTurnLedgerStore
  | CliqTurnLedgerOptions
  | undefined;

export type CliqInboundTurnResult = {
  eventKey: string;
  messageId: string;
  dispatched: boolean;
  turn: CliqTurnLedgerEntry;
  lifecycle?: CliqInboundLifecycleResult;
  skipped?: boolean;
  skipReason?: CliqTurnLedgerRejectReason;
  error?: string;
};

const DEFAULT_MAX_ENTRIES = 5000;
const DEFAULT_MAX_ATTEMPTS = 1;
const DEFAULT_ACTIVE_TTL_MS = 5 * 60 * 1000;

function normalizeKeyPart(value: string | undefined, fallback: string): string {
  return (value?.trim() || fallback).toLowerCase();
}

export function buildCliqTurnId(event: CliqNormalizedInboundEvent): string {
  return `turn:${event.dedupeKey}`;
}

export function buildCliqTurnConversationKey(
  event: CliqNormalizedInboundEvent,
): string {
  const conversationId =
    event.threadId ?? event.chatId ?? event.channelId ?? event.peerId;
  return [
    "account",
    normalizeKeyPart(event.accountId, "default"),
    "network",
    normalizeKeyPart(event.network, "default"),
    event.threadId ? "thread" : "conversation",
    normalizeKeyPart(conversationId, "unknown"),
  ].join(":");
}

function isTurnLedgerStore(value: unknown): value is CliqTurnLedgerStore {
  return Boolean(
    value &&
      typeof value === "object" &&
      "begin" in value &&
      "complete" in value &&
      "fail" in value &&
      "snapshot" in value,
  );
}

function cloneEntry(entry: CliqTurnLedgerEntry): CliqTurnLedgerEntry {
  return {
    ...entry,
    coalescedEventKeys: [...entry.coalescedEventKeys],
  };
}

function safeErrorText(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  return message.replace(/\s+/g, " ").trim().slice(0, 500);
}

class InMemoryCliqTurnLedgerStore implements CliqTurnLedgerStore {
  private readonly entries = new Map<string, CliqTurnLedgerEntry>();
  private readonly activeByConversation = new Map<string, string>();
  private readonly maxEntries: number;
  private readonly maxAttempts: number;
  private readonly activeTtlMs: number;
  private readonly now: () => number;

  constructor(options: CliqTurnLedgerOptions = {}) {
    this.maxEntries = Math.max(
      100,
      Math.floor(options.maxEntries ?? DEFAULT_MAX_ENTRIES),
    );
    this.maxAttempts = Math.max(
      1,
      Math.floor(options.maxAttempts ?? DEFAULT_MAX_ATTEMPTS),
    );
    this.activeTtlMs = Math.max(
      1000,
      Math.floor(options.activeTtlMs ?? DEFAULT_ACTIVE_TTL_MS),
    );
    this.now = options.now ?? Date.now;
  }

  get size(): number {
    return this.entries.size;
  }

  begin(event: CliqNormalizedInboundEvent): CliqTurnLedgerBeginResult {
    this.prune();
    const turnId = buildCliqTurnId(event);
    const conversationKey = buildCliqTurnConversationKey(event);
    const nowMs = this.now();
    const nowIso = new Date(nowMs).toISOString();
    let entry = this.entries.get(turnId);

    if (entry) {
      const terminal = this.rejectTerminalEntry(entry, nowIso);
      if (terminal) return terminal;

      if (entry.state === "active" && !this.isExpired(entry, nowMs)) {
        return {
          accepted: false,
          reason: "duplicate_event",
          entry: cloneEntry(entry),
        };
      }

      if (entry.state === "active") {
        this.expireActiveEntry(entry, nowIso);
      }
    }

    const activeTurnId = this.activeByConversation.get(conversationKey);
    if (activeTurnId && activeTurnId !== turnId) {
      const active = this.entries.get(activeTurnId);
      if (active && active.state === "active" && !this.isExpired(active, nowMs)) {
        active.coalescedCount += 1;
        active.coalescedEventKeys.push(event.dedupeKey);
        active.updatedAt = nowIso;
        const coalesced = entry ?? this.createEntry(event, nowIso);
        coalesced.state = "coalesced";
        coalesced.lastAction = "coalesced_into_active_turn";
        coalesced.updatedAt = nowIso;
        this.entries.set(turnId, coalesced);
        return {
          accepted: false,
          reason: "conversation_active",
          entry: cloneEntry(coalesced),
        };
      }
      this.activeByConversation.delete(conversationKey);
    }

    if (!entry) {
      entry = this.createEntry(event, nowIso);
      this.entries.set(turnId, entry);
    }

    entry.state = "active";
    entry.attempts += 1;
    entry.lastAction = "dispatch_started";
    entry.lastError = undefined;
    entry.deadLetterReason = undefined;
    entry.updatedAt = nowIso;
    entry.activeExpiresAt = new Date(nowMs + this.activeTtlMs).toISOString();
    this.activeByConversation.set(conversationKey, turnId);
    return { accepted: true, entry: cloneEntry(entry) };
  }

  complete(event: CliqNormalizedInboundEvent): CliqTurnLedgerEntry {
    const entry = this.entryForUpdate(event);
    const nowIso = new Date(this.now()).toISOString();
    entry.state = "completed";
    entry.lastAction = "dispatch_completed";
    entry.updatedAt = nowIso;
    entry.activeExpiresAt = undefined;
    this.activeByConversation.delete(entry.conversationKey);
    return cloneEntry(entry);
  }

  fail(event: CliqNormalizedInboundEvent, error: unknown): CliqTurnLedgerEntry {
    const entry = this.entryForUpdate(event);
    const nowIso = new Date(this.now()).toISOString();
    entry.lastError = safeErrorText(error);
    entry.updatedAt = nowIso;
    entry.activeExpiresAt = undefined;
    this.activeByConversation.delete(entry.conversationKey);
    if (entry.attempts >= entry.maxAttempts) {
      entry.state = "dead_letter";
      entry.lastAction = "dead_letter";
      entry.deadLetterReason = "max_attempts_exhausted";
    } else {
      entry.state = "failed";
      entry.lastAction = "dispatch_failed";
    }
    return cloneEntry(entry);
  }

  get(
    eventOrKey: CliqNormalizedInboundEvent | string,
  ): CliqTurnLedgerEntry | undefined {
    const key =
      typeof eventOrKey === "string" ? eventOrKey : buildCliqTurnId(eventOrKey);
    const entry = this.entries.get(key);
    return entry ? cloneEntry(entry) : undefined;
  }

  snapshot(): CliqTurnLedgerEntry[] {
    return [...this.entries.values()].map(cloneEntry);
  }

  clear(): void {
    this.entries.clear();
    this.activeByConversation.clear();
  }

  private createEntry(
    event: CliqNormalizedInboundEvent,
    nowIso: string,
  ): CliqTurnLedgerEntry {
    return {
      turnId: buildCliqTurnId(event),
      eventKey: event.dedupeKey,
      conversationKey: buildCliqTurnConversationKey(event),
      idempotencyKey: `cliq:${event.dedupeKey}`,
      state: "active",
      attempts: 0,
      maxAttempts: this.maxAttempts,
      messageId: event.messageId,
      accountId: event.accountId,
      network: event.network,
      peerId: event.peerId,
      ...(event.chatId ? { chatId: event.chatId } : {}),
      ...(event.channelId ? { channelId: event.channelId } : {}),
      ...(event.threadId ? { threadId: event.threadId } : {}),
      ...(event.senderId ? { senderId: event.senderId } : {}),
      lastAction: "created",
      coalescedCount: 0,
      coalescedEventKeys: [],
      createdAt: nowIso,
      updatedAt: nowIso,
    };
  }

  private entryForUpdate(event: CliqNormalizedInboundEvent): CliqTurnLedgerEntry {
    const turnId = buildCliqTurnId(event);
    let entry = this.entries.get(turnId);
    if (!entry) {
      entry = this.createEntry(event, new Date(this.now()).toISOString());
      this.entries.set(turnId, entry);
    }
    return entry;
  }

  private rejectTerminalEntry(
    entry: CliqTurnLedgerEntry,
    nowIso: string,
  ): CliqTurnLedgerBeginResult | null {
    if (entry.state === "completed") {
      entry.lastAction = "duplicate_completed_event";
      entry.updatedAt = nowIso;
      return {
        accepted: false,
        reason: "duplicate_event",
        entry: cloneEntry(entry),
      };
    }
    if (entry.state === "dead_letter") {
      entry.lastAction = "dead_letter_replay_blocked";
      entry.updatedAt = nowIso;
      return {
        accepted: false,
        reason: "dead_lettered",
        entry: cloneEntry(entry),
      };
    }
    if (entry.state === "failed" && entry.attempts >= entry.maxAttempts) {
      entry.state = "dead_letter";
      entry.lastAction = "dead_letter";
      entry.deadLetterReason = "max_attempts_exhausted";
      entry.updatedAt = nowIso;
      return {
        accepted: false,
        reason: "dead_lettered",
        entry: cloneEntry(entry),
      };
    }
    return null;
  }

  private expireActiveEntry(entry: CliqTurnLedgerEntry, nowIso: string): void {
    entry.state = "failed";
    entry.lastAction = "active_turn_expired";
    entry.lastError = "active turn expired";
    entry.updatedAt = nowIso;
    entry.activeExpiresAt = undefined;
    this.activeByConversation.delete(entry.conversationKey);
  }

  private isExpired(entry: CliqTurnLedgerEntry, nowMs: number): boolean {
    if (!entry.activeExpiresAt) return false;
    return Date.parse(entry.activeExpiresAt) <= nowMs;
  }

  private prune(): void {
    while (this.entries.size > this.maxEntries) {
      const oldest = this.entries.keys().next().value;
      if (typeof oldest !== "string") return;
      const entry = this.entries.get(oldest);
      if (entry) this.activeByConversation.delete(entry.conversationKey);
      this.entries.delete(oldest);
    }
  }
}

export function createCliqTurnLedgerStore(
  options: CliqTurnLedgerOptions = {},
): CliqTurnLedgerStore {
  return new InMemoryCliqTurnLedgerStore(options);
}

export function resolveCliqTurnLedger(
  option: CliqTurnLedgerOption,
): CliqTurnLedgerStore | null {
  if (option === false) return null;
  if (isTurnLedgerStore(option)) return option;
  return createCliqTurnLedgerStore(option);
}

export async function runCliqInboundTurn(params: {
  account: CliqResolvedAccount;
  event: CliqNormalizedInboundEvent;
  turnLedger?: CliqTurnLedgerStore | null;
  lifecycle?: CliqInboundLifecycleOption;
  onEvent?: (event: CliqNormalizedInboundEvent) => void | Promise<void>;
}): Promise<CliqInboundTurnResult> {
  const ledger = params.turnLedger;
  if (!ledger) {
    const lifecycle = await runCliqInboundLifecycle({
      account: params.account,
      event: params.event,
      lifecycle: params.lifecycle,
      onEvent: params.onEvent,
    });
    return {
      eventKey: params.event.dedupeKey,
      messageId: params.event.messageId,
      dispatched: lifecycle.dispatched,
      lifecycle,
      turn: createCliqTurnLedgerStore().complete(params.event),
    };
  }

  const begin = ledger.begin(params.event);
  if (!begin.accepted) {
    return {
      eventKey: params.event.dedupeKey,
      messageId: params.event.messageId,
      dispatched: false,
      turn: begin.entry,
      skipped: true,
      skipReason: begin.reason,
    };
  }

  try {
    const lifecycle = await runCliqInboundLifecycle({
      account: params.account,
      event: params.event,
      lifecycle: params.lifecycle,
      onEvent: params.onEvent,
    });
    const turn = ledger.complete(params.event);
    return {
      eventKey: params.event.dedupeKey,
      messageId: params.event.messageId,
      dispatched: lifecycle.dispatched,
      lifecycle,
      turn,
    };
  } catch (error) {
    const turn = ledger.fail(params.event, error);
    return {
      eventKey: params.event.dedupeKey,
      messageId: params.event.messageId,
      dispatched: false,
      lifecycle:
        error instanceof CliqInboundLifecycleDispatchError
          ? error.lifecycle
          : undefined,
      turn,
      error: safeErrorText(error),
    };
  }
}
