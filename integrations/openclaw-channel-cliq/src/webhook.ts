import { createHash, timingSafeEqual } from "node:crypto";
import type { IncomingHttpHeaders } from "node:http";
import type { IncomingMessage, ServerResponse } from "node:http";

import type {
  OpenClawConfig,
  OpenClawPluginApi,
  PluginLogger,
} from "openclaw/plugin-sdk";
import { resolveConfiguredSecretInputString } from "openclaw/plugin-sdk/secret-input-runtime";
import {
  beginWebhookRequestPipelineOrReject,
  createFixedWindowRateLimiter,
  createWebhookInFlightLimiter,
  readWebhookBodyOrReject,
} from "openclaw/plugin-sdk/webhook-ingress";

import {
  defaultCliqAccountId,
  listCliqAccountIds,
  resolveCliqAccount,
  type CliqResolvedAccount,
} from "./config.js";
import {
  CLIQ_CHANNEL_ID,
  CLIQ_WEBHOOK_SECRET_HEADER,
  DEFAULT_ACCOUNT_ID,
  DEFAULT_CLIQ_WEBHOOK_PATH,
} from "./constants.js";
import {
  createCliqInboundDedupeStore,
  evaluateCliqPollingEventSecurity,
  normalizeCliqInboundMessage,
  type CliqInboundDedupeStore,
  type CliqMentionMatcher,
  type CliqNormalizedInboundEvent,
} from "./inbound.js";
import type { CliqInboundSecurityDecision } from "./security.js";

const BODY_MAX_BYTES = 512 * 1024;
const BODY_TIMEOUT_MS = 5_000;

export type CliqWebhookHandlerKind =
  | "message"
  | "mention"
  | "participation"
  | "context"
  | "incoming_webhook"
  | "welcome"
  | "call"
  | "menu"
  | "unknown";

export type CliqWebhookPayloadEnvelope = {
  handler: string;
  handlerKind: CliqWebhookHandlerKind;
  message: Record<string, unknown>;
  user?: Record<string, unknown>;
  chat?: Record<string, unknown>;
  raw: unknown;
};

export type CliqWebhookSecretVerificationResult =
  | {
      ok: true;
      account: CliqResolvedAccount;
      accountId: string;
    }
  | {
      ok: false;
      reason: "missing_secret" | "unconfigured_secret" | "invalid_secret";
    };

export type CliqWebhookProcessResult =
  | {
      ok: true;
      accepted: true;
      accountId: string;
      handlerKind: CliqWebhookHandlerKind;
      event: CliqNormalizedInboundEvent;
      security: Extract<CliqInboundSecurityDecision, { allowed: true }>;
      dispatched: boolean;
    }
  | {
      ok: true;
      accepted: false;
      status: "ignored";
      reason:
        | "unsupported_handler"
        | "invalid_payload"
        | "duplicate"
        | "security_denied";
      accountId: string;
      handlerKind?: CliqWebhookHandlerKind;
      event?: CliqNormalizedInboundEvent;
      security?: CliqInboundSecurityDecision;
    };

export type CliqWebhookHandlerOptions = {
  cfg: OpenClawConfig;
  webhookPath?: string;
  dedupe?: CliqInboundDedupeStore;
  mentionMatchers?: CliqMentionMatcher[];
  env?: NodeJS.ProcessEnv;
  logger?: Partial<PluginLogger>;
  onEvent?: (
    event: CliqNormalizedInboundEvent,
    context: {
      account: CliqResolvedAccount;
      handlerKind: CliqWebhookHandlerKind;
      security: Extract<CliqInboundSecurityDecision, { allowed: true }>;
    },
  ) => void | Promise<void>;
};

type AccountSecretCandidate = {
  account: CliqResolvedAccount;
  secret: string;
};

type CliqWebhookHttpRouteHandler = (
  req: IncomingMessage,
  res: ServerResponse,
) => Promise<boolean | void> | boolean | void;

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

function readFirstRecord(
  value: Record<string, unknown> | undefined,
  keys: string[],
): Record<string, unknown> | undefined {
  if (!value) return undefined;
  for (const key of keys) {
    const nested = value[key];
    if (isRecord(nested)) return nested;
    if (typeof nested === "string") {
      const parsed = parseCliqWebhookPayload(nested);
      if (isRecord(parsed)) return parsed;
    }
  }
  return undefined;
}

function normalizeHeaderValue(
  value: string | string[] | undefined,
): string | undefined {
  if (Array.isArray(value)) return normalizeText(value[0]);
  return normalizeText(value);
}

function secureStringEquals(left: string, right: string): boolean {
  const leftDigest = createHash("sha256").update(left).digest();
  const rightDigest = createHash("sha256").update(right).digest();
  return timingSafeEqual(leftDigest, rightDigest);
}

function stablePayloadHash(value: unknown): string {
  const raw = typeof value === "string" ? value : JSON.stringify(value);
  return createHash("sha256").update(raw ?? "").digest("hex").slice(0, 16);
}

function parseMaybeJson(value: string): unknown {
  try {
    const parsed = JSON.parse(value);
    if (typeof parsed === "string") return parseCliqWebhookPayload(parsed);
    return parsed;
  } catch {
    return undefined;
  }
}

function parseUrlEncodedBody(value: string): Record<string, unknown> | undefined {
  if (!value.includes("=")) return undefined;
  const params = new URLSearchParams(value);
  const record: Record<string, unknown> = {};
  for (const [key, entry] of params.entries()) {
    const trimmed = entry.trim();
    const parsed =
      trimmed.startsWith("{") || trimmed.startsWith("[")
        ? parseMaybeJson(trimmed)
        : undefined;
    record[key] = parsed === undefined ? entry : parsed;
  }
  if (Object.keys(record).length === 1) {
    const payload = record.payload ?? record.parameters ?? record.body;
    if (typeof payload === "string") {
      const parsed = parseCliqWebhookPayload(payload);
      if (isRecord(parsed)) return parsed;
    }
    if (isRecord(payload)) return payload;
  }
  return record;
}

export function parseCliqWebhookPayload(
  body: string | Buffer | unknown,
  contentType?: string | string[],
): unknown {
  if (Buffer.isBuffer(body)) {
    return parseCliqWebhookPayload(body.toString("utf8"), contentType);
  }
  if (typeof body !== "string") return body;

  const trimmed = body.trim();
  if (!trimmed) return {};

  const contentTypeText = Array.isArray(contentType)
    ? contentType.join(";")
    : (contentType ?? "");
  const parsedJson =
    trimmed.startsWith("{") ||
    trimmed.startsWith("[") ||
    contentTypeText.includes("json")
      ? parseMaybeJson(trimmed)
      : undefined;
  if (parsedJson !== undefined) return parsedJson;

  const parsedForm = parseUrlEncodedBody(trimmed);
  if (parsedForm) return parsedForm;

  return { message: trimmed };
}

export function normalizeCliqWebhookPath(value?: string | null): string {
  const trimmed = value?.trim() || DEFAULT_CLIQ_WEBHOOK_PATH;
  const withoutQuery = trimmed.split("?")[0]?.trim() || DEFAULT_CLIQ_WEBHOOK_PATH;
  return withoutQuery.startsWith("/") ? withoutQuery : `/${withoutQuery}`;
}

export function listCliqWebhookRoutePaths(cfg: OpenClawConfig): string[] {
  const accountIds = listCliqAccountIds(cfg);
  const ids = accountIds.length > 0 ? accountIds : [defaultCliqAccountId(cfg)];
  const paths = ids.map((accountId) =>
    normalizeCliqWebhookPath(resolveCliqAccount(cfg, accountId).webhookPath),
  );
  return [...new Set(paths.length > 0 ? paths : [DEFAULT_CLIQ_WEBHOOK_PATH])];
}

function normalizeHandlerKind(raw: string | undefined): CliqWebhookHandlerKind {
  const normalized = (raw ?? "")
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, "_");
  if (normalized.includes("mention")) return "mention";
  if (normalized.includes("participation")) return "participation";
  if (normalized.includes("context")) return "context";
  if (normalized.includes("incoming") || normalized.includes("webhook")) {
    return "incoming_webhook";
  }
  if (normalized.includes("welcome")) return "welcome";
  if (normalized.includes("call")) return "call";
  if (normalized.includes("menu")) return "menu";
  if (normalized.includes("message") || normalized === "msg") return "message";
  return "unknown";
}

function shouldAcceptHandler(kind: CliqWebhookHandlerKind): boolean {
  return ["message", "mention", "participation", "context"].includes(kind);
}

function extractCliqWebhookEnvelope(
  payload: unknown,
): CliqWebhookPayloadEnvelope | null {
  const record = isRecord(payload) ? payload : { message: payload };
  const nestedPayload = readFirstRecord(record, ["payload", "data", "event"]);
  const root =
    nestedPayload && !record.message && !record.user && !record.chat
      ? nestedPayload
      : record;
  const handler =
    readFirstText(root, [
      "handler",
      "handlerName",
      "handler_name",
      "handlerType",
      "handler_type",
      "event",
      "eventType",
      "event_type",
      "type",
    ]) ?? "message";
  const handlerKind = normalizeHandlerKind(handler);
  const user = readFirstRecord(root, [
    "user",
    "sender",
    "from",
    "createdBy",
    "created_by",
  ]);
  const chat = readFirstRecord(root, ["chat", "conversation", "channel", "room"]);
  const messageValue =
    root.message ??
    root.messageData ??
    root.message_data ??
    root.text ??
    root.body ??
    root.content ??
    root;
  const message =
    typeof messageValue === "string"
      ? { text: messageValue }
      : isRecord(messageValue)
        ? { ...messageValue }
        : null;
  if (!message) return null;

  enrichMessageFromWebhook({
    message,
    user,
    chat,
    root,
    handlerKind,
    rawPayload: payload,
  });

  return {
    handler,
    handlerKind,
    message,
    ...(user ? { user } : {}),
    ...(chat ? { chat } : {}),
    raw: payload,
  };
}

function copyFirstText(params: {
  target: Record<string, unknown>;
  targetKeys: string[];
  sources: Array<Record<string, unknown> | undefined>;
  sourceKeys: string[];
}): void {
  if (params.targetKeys.some((key) => normalizeText(params.target[key]))) return;
  for (const source of params.sources) {
    const value = readFirstText(source, params.sourceKeys);
    if (!value) continue;
    params.target[params.targetKeys[0] ?? params.sourceKeys[0] ?? "value"] =
      value;
    return;
  }
}

function enrichMessageFromWebhook(params: {
  message: Record<string, unknown>;
  user?: Record<string, unknown>;
  chat?: Record<string, unknown>;
  root: Record<string, unknown>;
  handlerKind: CliqWebhookHandlerKind;
  rawPayload: unknown;
}): void {
  const { message, user, chat, root } = params;
  message.raw = message.raw ?? params.rawPayload;
  if (!isRecord(message.sender) && user) message.sender = user;
  if (!isRecord(message.user) && user) message.user = user;
  if (params.handlerKind === "mention") message.mentioned = true;

  copyFirstText({
    target: message,
    targetKeys: ["messageId", "message_id", "id"],
    sources: [message, root],
    sourceKeys: ["messageId", "message_id", "msgId", "msg_id", "id"],
  });
  if (!normalizeText(message.messageId) && !normalizeText(message.id)) {
    message.messageId = `webhook-${stablePayloadHash(params.rawPayload)}`;
  }

  const senderId =
    readFirstText(message, [
      "senderId",
      "sender_id",
      "fromId",
      "from_id",
      "userId",
      "user_id",
    ]) ??
    readFirstText(user, ["id", "zuid", "userId", "user_id", "email"]) ??
    readFirstText(root, [
      "senderId",
      "sender_id",
      "fromId",
      "from_id",
      "userId",
      "user_id",
    ]);
  if (senderId) {
    if (!normalizeText(message.senderId)) message.senderId = senderId;
    if (!normalizeText(message.userId)) message.userId = senderId;
  }
  copyFirstText({
    target: message,
    targetKeys: ["chatId", "chat_id", "conversationId", "conversation_id"],
    sources: [message, chat, root],
    sourceKeys: ["chatId", "chat_id", "conversationId", "conversation_id", "id"],
  });
  copyFirstText({
    target: message,
    targetKeys: ["channelId", "channel_id"],
    sources: [message, chat, root],
    sourceKeys: [
      "channelId",
      "channel_id",
      "channelUniqueName",
      "channel_unique_name",
    ],
  });
  copyFirstText({
    target: message,
    targetKeys: ["threadId", "thread_id"],
    sources: [message, root],
    sourceKeys: [
      "threadId",
      "thread_id",
      "parentMessageId",
      "parent_message_id",
    ],
  });
  copyFirstText({
    target: message,
    targetKeys: ["chatType", "chat_type"],
    sources: [message, chat, root],
    sourceKeys: [
      "chatType",
      "chat_type",
      "conversationType",
      "conversation_type",
      "type",
      "kind",
    ],
  });
  copyFirstText({
    target: message,
    targetKeys: ["text", "message"],
    sources: [message, root],
    sourceKeys: [
      "text",
      "plainText",
      "plain_text",
      "messageText",
      "message_text",
      "body",
      "content",
    ],
  });
}

export function normalizeCliqWebhookPayload(params: {
  account: CliqResolvedAccount;
  payload: unknown;
  mentionMatchers?: CliqMentionMatcher[];
}): {
  envelope: CliqWebhookPayloadEnvelope | null;
  event: CliqNormalizedInboundEvent | null;
} {
  const envelope = extractCliqWebhookEnvelope(params.payload);
  if (!envelope || !shouldAcceptHandler(envelope.handlerKind)) {
    return { envelope, event: null };
  }
  return {
    envelope,
    event: normalizeCliqInboundMessage({
      accountId: params.account.accountId,
      network: params.account.network,
      chat: envelope.chat,
      message: envelope.message,
      mentionMatchers: params.mentionMatchers,
      skipSelfAuthored: false,
    }),
  };
}

async function resolveAccountSecretCandidates(params: {
  cfg: OpenClawConfig;
  env: NodeJS.ProcessEnv;
  webhookPath?: string;
}): Promise<AccountSecretCandidate[]> {
  const accountIds = listCliqAccountIds(params.cfg);
  const ids = accountIds.length > 0 ? accountIds : [DEFAULT_ACCOUNT_ID];
  const candidates: AccountSecretCandidate[] = [];
  const routePath = params.webhookPath
    ? normalizeCliqWebhookPath(params.webhookPath)
    : undefined;
  for (const accountId of ids) {
    const account = resolveCliqAccount(params.cfg, accountId);
    if (
      routePath &&
      normalizeCliqWebhookPath(account.webhookPath) !== routePath
    ) {
      continue;
    }
    const configured = await resolveConfiguredSecretInputString({
      config: params.cfg,
      env: params.env,
      value: account.webhookSecret,
      path:
        accountId === DEFAULT_ACCOUNT_ID
          ? `channels.${CLIQ_CHANNEL_ID}.webhookSecret`
          : `channels.${CLIQ_CHANNEL_ID}.accounts.${accountId}.webhookSecret`,
    });
    const secret = configured.value ?? params.env.ZOHO_CLIQ_WEBHOOK_SECRET;
    if (secret?.trim()) candidates.push({ account, secret: secret.trim() });
  }
  return candidates;
}

export async function verifyCliqWebhookSecret(params: {
  cfg: OpenClawConfig;
  headers: IncomingHttpHeaders;
  env?: NodeJS.ProcessEnv;
  webhookPath?: string;
}): Promise<CliqWebhookSecretVerificationResult> {
  const provided = normalizeHeaderValue(params.headers[CLIQ_WEBHOOK_SECRET_HEADER]);
  if (!provided) return { ok: false, reason: "missing_secret" };
  const candidates = await resolveAccountSecretCandidates({
    cfg: params.cfg,
    env: params.env ?? process.env,
    webhookPath: params.webhookPath,
  });
  if (candidates.length === 0) return { ok: false, reason: "unconfigured_secret" };
  const matched = candidates.find((candidate) =>
    secureStringEquals(provided, candidate.secret),
  );
  if (!matched) return { ok: false, reason: "invalid_secret" };
  return {
    ok: true,
    account: matched.account,
    accountId: matched.account.accountId,
  };
}

export function evaluateCliqWebhookEventSecurity(params: {
  cfg?: OpenClawConfig;
  account: CliqResolvedAccount;
  event: CliqNormalizedInboundEvent;
  intent?: string | null;
}): CliqInboundSecurityDecision {
  return evaluateCliqPollingEventSecurity(params);
}

export async function processCliqWebhookPayload(
  options: CliqWebhookHandlerOptions & {
    account: CliqResolvedAccount;
    payload: unknown;
  },
): Promise<CliqWebhookProcessResult> {
  const dedupe = options.dedupe ?? createCliqInboundDedupeStore();
  const { envelope, event } = normalizeCliqWebhookPayload({
    account: options.account,
    payload: options.payload,
    mentionMatchers: options.mentionMatchers,
  });
  if (!envelope) {
    return {
      ok: true,
      accepted: false,
      status: "ignored",
      reason: "invalid_payload",
      accountId: options.account.accountId,
    };
  }
  if (!shouldAcceptHandler(envelope.handlerKind)) {
    return {
      ok: true,
      accepted: false,
      status: "ignored",
      reason: "unsupported_handler",
      accountId: options.account.accountId,
      handlerKind: envelope.handlerKind,
    };
  }
  if (!event) {
    return {
      ok: true,
      accepted: false,
      status: "ignored",
      reason: "invalid_payload",
      accountId: options.account.accountId,
      handlerKind: envelope.handlerKind,
    };
  }
  if (!dedupe.claim(event)) {
    return {
      ok: true,
      accepted: false,
      status: "ignored",
      reason: "duplicate",
      accountId: options.account.accountId,
      handlerKind: envelope.handlerKind,
      event,
    };
  }
  const security = evaluateCliqWebhookEventSecurity({
    cfg: options.cfg,
    account: options.account,
    event,
  });
  if (!security.allowed) {
    return {
      ok: true,
      accepted: false,
      status: "ignored",
      reason: "security_denied",
      accountId: options.account.accountId,
      handlerKind: envelope.handlerKind,
      event,
      security,
    };
  }
  await options.onEvent?.(event, {
    account: options.account,
    handlerKind: envelope.handlerKind,
    security,
  });
  return {
    ok: true,
    accepted: true,
    accountId: options.account.accountId,
    handlerKind: envelope.handlerKind,
    event,
    security,
    dispatched: Boolean(options.onEvent),
  };
}

function sendJson(
  res: ServerResponse,
  statusCode: number,
  payload: Record<string, unknown>,
): void {
  if (res.headersSent) return;
  res.statusCode = statusCode;
  res.setHeader("content-type", "application/json; charset=utf-8");
  res.end(JSON.stringify(payload));
}

function responseEventSummary(event: CliqNormalizedInboundEvent): Record<string, unknown> {
  return {
    messageId: event.messageId,
    chatType: event.chatType,
    peerId: event.peerId,
    senderId: event.senderId,
    threadId: event.threadId,
    dedupeKey: event.dedupeKey,
    mentioned: event.mentioned,
  };
}

export function createCliqWebhookHttpHandler(
  options: CliqWebhookHandlerOptions,
): CliqWebhookHttpRouteHandler {
  const dedupe = options.dedupe ?? createCliqInboundDedupeStore();
  const rateLimiter = createFixedWindowRateLimiter({
    windowMs: 60_000,
    maxRequests: 120,
    maxTrackedKeys: 2048,
  });
  const inFlightLimiter = createWebhookInFlightLimiter({
    maxInFlightPerKey: 4,
    maxTrackedKeys: 2048,
  });
  return async (req: IncomingMessage, res: ServerResponse) => {
    const clientKey = req.socket.remoteAddress ?? "unknown";
    const pipeline = beginWebhookRequestPipelineOrReject({
      req,
      res,
      allowMethods: ["POST"],
      rateLimiter,
      rateLimitKey: clientKey,
      inFlightLimiter,
      inFlightKey: clientKey,
      requireJsonContentType: false,
    });
    if (!pipeline.ok) return true;
    try {
      const verified = await verifyCliqWebhookSecret({
        cfg: options.cfg,
        headers: req.headers,
        env: options.env,
        webhookPath: options.webhookPath,
      });
      if (!verified.ok) {
        sendJson(res, verified.reason === "missing_secret" ? 401 : 403, {
          ok: false,
          error: verified.reason,
        });
        return true;
      }
      const body = await readWebhookBodyOrReject({
        req,
        res,
        maxBytes: BODY_MAX_BYTES,
        timeoutMs: BODY_TIMEOUT_MS,
        profile: "post-auth",
        invalidBodyMessage: "invalid Cliq webhook body",
      });
      if (!body.ok) return true;
      const payload = parseCliqWebhookPayload(
        body.value,
        req.headers["content-type"],
      );
      const result = await processCliqWebhookPayload({
        ...options,
        account: verified.account,
        payload,
        dedupe,
      });
      if (result.accepted) {
        sendJson(res, 200, {
          ok: true,
          accepted: true,
          accountId: result.accountId,
          handlerKind: result.handlerKind,
          dispatched: result.dispatched,
          event: responseEventSummary(result.event),
        });
        return true;
      }
      sendJson(res, 200, {
        ok: true,
        accepted: false,
        accountId: result.accountId,
        handlerKind: result.handlerKind,
        reason: result.reason,
        event: result.event ? responseEventSummary(result.event) : undefined,
        securityReason:
          result.security && !result.security.allowed
            ? result.security.reasonCode
            : undefined,
      });
      return true;
    } catch (error) {
      options.logger?.error?.(
        `[zoho-cliq] webhook handler failed: ${
          error instanceof Error ? error.message : String(error)
        }`,
      );
      sendJson(res, 500, {
        ok: false,
        error: "webhook_handler_failed",
      });
      return true;
    } finally {
      pipeline.release();
    }
  };
}

export function registerCliqWebhookRoutes(api: OpenClawPluginApi): void {
  for (const path of listCliqWebhookRoutePaths(api.config)) {
    api.registerHttpRoute({
      path,
      auth: "plugin",
      match: "exact",
      replaceExisting: true,
      handler: createCliqWebhookHttpHandler({
        cfg: api.config,
        webhookPath: path,
        logger: api.logger,
      }),
    });
    api.logger.info?.(`[zoho-cliq] registered webhook route ${path}`);
  }
}
