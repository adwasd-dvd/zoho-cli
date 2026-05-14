import { createHash, timingSafeEqual } from "node:crypto";
import { resolveConfiguredSecretInputString } from "openclaw/plugin-sdk/secret-input-runtime";
import { beginWebhookRequestPipelineOrReject, createFixedWindowRateLimiter, createWebhookInFlightLimiter, readWebhookBodyOrReject, } from "openclaw/plugin-sdk/webhook-ingress";
import { defaultCliqAccountId, listCliqAccountIds, resolveCliqAccount, } from "./config.js";
import { CLIQ_CHANNEL_ID, CLIQ_WEBHOOK_SECRET_HEADER, DEFAULT_ACCOUNT_ID, DEFAULT_CLIQ_WEBHOOK_PATH, } from "./constants.js";
import { createCliqInboundDedupeStore, evaluateCliqPollingEventSecurity, normalizeCliqInboundMessage, } from "./inbound.js";
import { createCliqNativeEventDispatcher } from "./native-dispatch.js";
import { buildCliqAuditEvent, CLIQ_WEBHOOK_BODY_MAX_BYTES, CLIQ_WEBHOOK_BODY_TIMEOUT_MS, CLIQ_WEBHOOK_MAX_IN_FLIGHT_PER_KEY, CLIQ_WEBHOOK_MAX_TRACKED_KEYS, CLIQ_WEBHOOK_RATE_LIMIT_MAX_REQUESTS, CLIQ_WEBHOOK_RATE_LIMIT_WINDOW_MS, emitCliqAuditEvent, } from "./observability.js";
import { resolveCliqTurnLedger, runCliqInboundTurn, } from "./turn-ledger.js";
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
function readFirstRecord(value, keys) {
    if (!value)
        return undefined;
    for (const key of keys) {
        const nested = value[key];
        if (isRecord(nested))
            return nested;
        if (typeof nested === "string") {
            const parsed = parseCliqWebhookPayload(nested);
            if (isRecord(parsed))
                return parsed;
        }
    }
    return undefined;
}
function normalizeHeaderValue(value) {
    if (Array.isArray(value))
        return normalizeText(value[0]);
    return normalizeText(value);
}
function secureStringEquals(left, right) {
    const leftDigest = createHash("sha256").update(left).digest();
    const rightDigest = createHash("sha256").update(right).digest();
    return timingSafeEqual(leftDigest, rightDigest);
}
function stablePayloadHash(value) {
    const raw = typeof value === "string" ? value : JSON.stringify(value);
    return createHash("sha256").update(raw ?? "").digest("hex").slice(0, 16);
}
function parseMaybeJson(value) {
    try {
        const parsed = JSON.parse(value);
        if (typeof parsed === "string")
            return parseCliqWebhookPayload(parsed);
        return parsed;
    }
    catch {
        return undefined;
    }
}
function parseUrlEncodedBody(value) {
    if (!value.includes("="))
        return undefined;
    const params = new URLSearchParams(value);
    const record = {};
    for (const [key, entry] of params.entries()) {
        const trimmed = entry.trim();
        const parsed = trimmed.startsWith("{") || trimmed.startsWith("[")
            ? parseMaybeJson(trimmed)
            : undefined;
        record[key] = parsed === undefined ? entry : parsed;
    }
    if (Object.keys(record).length === 1) {
        const payload = record.payload ?? record.parameters ?? record.body;
        if (typeof payload === "string") {
            const parsed = parseCliqWebhookPayload(payload);
            if (isRecord(parsed))
                return parsed;
        }
        if (isRecord(payload))
            return payload;
    }
    return record;
}
function splitDelugeEntries(value) {
    const entries = [];
    let depth = 0;
    let quote;
    let start = 0;
    let escaped = false;
    for (let index = 0; index < value.length; index += 1) {
        const char = value[index];
        if (!char)
            continue;
        if (quote) {
            if (escaped) {
                escaped = false;
                continue;
            }
            if (char === "\\") {
                escaped = true;
                continue;
            }
            if (char === quote)
                quote = undefined;
            continue;
        }
        if (char === '"' || char === "'") {
            quote = char;
            continue;
        }
        if (char === "{" || char === "[") {
            depth += 1;
            continue;
        }
        if (char === "}" || char === "]") {
            depth = Math.max(0, depth - 1);
            continue;
        }
        if (char === "," && depth === 0) {
            entries.push(value.slice(start, index).trim());
            start = index + 1;
        }
    }
    entries.push(value.slice(start).trim());
    return entries.filter(Boolean);
}
function findDelugeEntrySeparator(value) {
    let depth = 0;
    let quote;
    let escaped = false;
    for (let index = 0; index < value.length; index += 1) {
        const char = value[index];
        if (!char)
            continue;
        if (quote) {
            if (escaped) {
                escaped = false;
                continue;
            }
            if (char === "\\") {
                escaped = true;
                continue;
            }
            if (char === quote)
                quote = undefined;
            continue;
        }
        if (char === '"' || char === "'") {
            quote = char;
            continue;
        }
        if (char === "{" || char === "[") {
            depth += 1;
            continue;
        }
        if (char === "}" || char === "]") {
            depth = Math.max(0, depth - 1);
            continue;
        }
        if (depth === 0 && (char === "=" || char === ":"))
            return index;
    }
    return -1;
}
function stripDelugeQuotes(value) {
    const trimmed = value.trim();
    if (trimmed.length < 2)
        return trimmed;
    const first = trimmed[0];
    const last = trimmed[trimmed.length - 1];
    if ((first === '"' || first === "'") && first === last) {
        return trimmed
            .slice(1, -1)
            .replace(/\\(["'\\])/g, "$1")
            .trim();
    }
    return trimmed;
}
function parseDelugeListString(value) {
    const trimmed = value.trim();
    if (!trimmed.startsWith("[") || !trimmed.endsWith("]"))
        return undefined;
    const inner = trimmed.slice(1, -1).trim();
    if (!inner)
        return [];
    return splitDelugeEntries(inner).map(parseDelugeScalar);
}
function parseDelugeScalar(value) {
    const trimmed = value.trim();
    if (!trimmed)
        return "";
    if (trimmed.startsWith("{") ||
        trimmed.startsWith("[") ||
        trimmed.startsWith('"')) {
        try {
            return JSON.parse(trimmed);
        }
        catch {
            // Deluge Map#toString output is often JSON-like but not strict JSON.
        }
    }
    const parsedMap = parseDelugeMapString(trimmed);
    if (parsedMap)
        return parsedMap;
    const parsedList = parseDelugeListString(trimmed);
    if (parsedList)
        return parsedList;
    const unquoted = stripDelugeQuotes(trimmed);
    if (/^null$/i.test(unquoted))
        return null;
    if (/^true$/i.test(unquoted))
        return true;
    if (/^false$/i.test(unquoted))
        return false;
    return unquoted;
}
function parseDelugeMapString(value) {
    const trimmed = value.trim();
    if (!trimmed.startsWith("{") || !trimmed.endsWith("}"))
        return undefined;
    const inner = trimmed.slice(1, -1).trim();
    if (!inner)
        return {};
    if (findDelugeEntrySeparator(inner) < 0)
        return undefined;
    const record = {};
    let lastKey;
    for (const entry of splitDelugeEntries(inner)) {
        const separator = findDelugeEntrySeparator(entry);
        if (separator < 0) {
            if (lastKey && typeof record[lastKey] === "string") {
                record[lastKey] = `${record[lastKey]}, ${entry.trim()}`;
                continue;
            }
            return undefined;
        }
        const key = stripDelugeQuotes(entry.slice(0, separator));
        if (!key)
            return undefined;
        record[key] = parseDelugeScalar(entry.slice(separator + 1));
        lastKey = key;
    }
    return record;
}
export function parseCliqWebhookPayload(body, contentType) {
    if (Buffer.isBuffer(body)) {
        return parseCliqWebhookPayload(body.toString("utf8"), contentType);
    }
    if (typeof body !== "string")
        return body;
    const trimmed = body.trim();
    if (!trimmed)
        return {};
    const contentTypeText = Array.isArray(contentType)
        ? contentType.join(";")
        : (contentType ?? "");
    const parsedJson = trimmed.startsWith("{") ||
        trimmed.startsWith("[") ||
        contentTypeText.includes("json")
        ? parseMaybeJson(trimmed)
        : undefined;
    if (parsedJson !== undefined)
        return parsedJson;
    const parsedDelugeMap = parseDelugeMapString(trimmed);
    if (parsedDelugeMap)
        return parsedDelugeMap;
    const parsedForm = parseUrlEncodedBody(trimmed);
    if (parsedForm)
        return parsedForm;
    return { message: trimmed };
}
export function normalizeCliqWebhookPath(value) {
    const trimmed = value?.trim() || DEFAULT_CLIQ_WEBHOOK_PATH;
    const withoutQuery = trimmed.split("?")[0]?.trim() || DEFAULT_CLIQ_WEBHOOK_PATH;
    return withoutQuery.startsWith("/") ? withoutQuery : `/${withoutQuery}`;
}
export function listCliqWebhookRoutePaths(cfg) {
    const accountIds = listCliqAccountIds(cfg);
    const ids = accountIds.length > 0 ? accountIds : [defaultCliqAccountId(cfg)];
    const paths = ids.map((accountId) => normalizeCliqWebhookPath(resolveCliqAccount(cfg, accountId).webhookPath));
    return [...new Set(paths.length > 0 ? paths : [DEFAULT_CLIQ_WEBHOOK_PATH])];
}
function normalizeHandlerKind(raw) {
    const normalized = (raw ?? "")
        .trim()
        .toLowerCase()
        .replace(/[\s-]+/g, "_");
    if (normalized.includes("mention"))
        return "mention";
    if (normalized.includes("participation"))
        return "participation";
    if (normalized.includes("context"))
        return "context";
    if (normalized.includes("incoming") || normalized.includes("webhook")) {
        return "incoming_webhook";
    }
    if (normalized.includes("welcome"))
        return "welcome";
    if (normalized.includes("call"))
        return "call";
    if (normalized.includes("menu"))
        return "menu";
    if (normalized.includes("message") || normalized === "msg")
        return "message";
    return "unknown";
}
function normalizeReplyMode(raw) {
    const normalized = (raw ?? "")
        .trim()
        .toLowerCase()
        .replace(/[\s-]+/g, "_");
    if (normalized === "deluge_response" || normalized === "deluge") {
        return "deluge_response";
    }
    if (normalized === "zoho_cli" || normalized === "cli" || normalized === "oauth") {
        return "zoho_cli";
    }
    return undefined;
}
function shouldAcceptHandler(kind) {
    return ["message", "mention", "participation", "context"].includes(kind);
}
export function shouldProcessCliqWebhookPayloadInBackground(payload) {
    const envelope = extractCliqWebhookEnvelope(payload);
    return (envelope?.replyMode === "zoho_cli" && shouldAcceptHandler(envelope.handlerKind));
}
function extractCliqWebhookEnvelope(payload) {
    const record = isRecord(payload) ? payload : { message: payload };
    const nestedPayload = readFirstRecord(record, ["payload", "data", "event"]);
    const root = nestedPayload && !record.message && !record.user && !record.chat
        ? nestedPayload
        : record;
    const handler = readFirstText(root, [
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
    const replyMode = normalizeReplyMode(readFirstText(root, [
        "replyMode",
        "reply_mode",
        "openclawReplyMode",
        "openclaw_reply_mode",
    ]));
    const user = readFirstRecord(root, [
        "user",
        "sender",
        "from",
        "createdBy",
        "created_by",
    ]);
    const chat = readFirstRecord(root, ["chat", "conversation", "channel", "room"]);
    const messageValue = root.message ??
        root.messageData ??
        root.message_data ??
        root.text ??
        root.body ??
        root.content ??
        root;
    const message = typeof messageValue === "string"
        ? { text: messageValue }
        : isRecord(messageValue)
            ? { ...messageValue }
            : null;
    if (!message)
        return null;
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
        ...(replyMode ? { replyMode } : {}),
        message,
        ...(user ? { user } : {}),
        ...(chat ? { chat } : {}),
        raw: payload,
    };
}
function copyFirstText(params) {
    if (params.targetKeys.some((key) => normalizeText(params.target[key])))
        return;
    for (const source of params.sources) {
        const value = readFirstText(source, params.sourceKeys);
        if (!value)
            continue;
        params.target[params.targetKeys[0] ?? params.sourceKeys[0] ?? "value"] =
            value;
        return;
    }
}
function enrichMessageFromWebhook(params) {
    const { message, user, chat, root } = params;
    message.raw = message.raw ?? params.rawPayload;
    if (!isRecord(message.sender) && user)
        message.sender = user;
    if (!isRecord(message.user) && user)
        message.user = user;
    if (params.handlerKind === "mention")
        message.mentioned = true;
    copyFirstText({
        target: message,
        targetKeys: ["messageId", "message_id", "id"],
        sources: [message, root],
        sourceKeys: ["messageId", "message_id", "msgId", "msg_id", "id"],
    });
    if (!normalizeText(message.messageId) && !normalizeText(message.id)) {
        message.messageId = `webhook-${stablePayloadHash(params.rawPayload)}`;
    }
    const senderId = readFirstText(message, [
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
        if (!normalizeText(message.senderId))
            message.senderId = senderId;
        if (!normalizeText(message.userId))
            message.userId = senderId;
    }
    copyFirstText({
        target: message,
        targetKeys: ["chatId", "chat_id", "conversationId", "conversation_id"],
        sources: [message, root],
        sourceKeys: ["chatId", "chat_id", "conversationId", "conversation_id"],
    });
    copyFirstText({
        target: message,
        targetKeys: ["chatId", "chat_id", "conversationId", "conversation_id"],
        sources: [chat],
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
export function normalizeCliqWebhookPayload(params) {
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
async function resolveAccountSecretCandidates(params) {
    const accountIds = listCliqAccountIds(params.cfg);
    const ids = accountIds.length > 0 ? accountIds : [DEFAULT_ACCOUNT_ID];
    const candidates = [];
    const routePath = params.webhookPath
        ? normalizeCliqWebhookPath(params.webhookPath)
        : undefined;
    for (const accountId of ids) {
        const account = resolveCliqAccount(params.cfg, accountId);
        if (routePath &&
            normalizeCliqWebhookPath(account.webhookPath) !== routePath) {
            continue;
        }
        const configured = await resolveConfiguredSecretInputString({
            config: params.cfg,
            env: params.env,
            value: account.webhookSecret,
            path: accountId === DEFAULT_ACCOUNT_ID
                ? `channels.${CLIQ_CHANNEL_ID}.webhookSecret`
                : `channels.${CLIQ_CHANNEL_ID}.accounts.${accountId}.webhookSecret`,
        });
        const secret = configured.value ?? params.env.ZOHO_CLIQ_WEBHOOK_SECRET;
        if (secret?.trim())
            candidates.push({ account, secret: secret.trim() });
    }
    return candidates;
}
export async function verifyCliqWebhookSecret(params) {
    const provided = normalizeHeaderValue(params.headers[CLIQ_WEBHOOK_SECRET_HEADER]);
    if (!provided)
        return { ok: false, reason: "missing_secret" };
    const candidates = await resolveAccountSecretCandidates({
        cfg: params.cfg,
        env: params.env ?? process.env,
        webhookPath: params.webhookPath,
    });
    if (candidates.length === 0)
        return { ok: false, reason: "unconfigured_secret" };
    const matched = candidates.find((candidate) => secureStringEquals(provided, candidate.secret));
    if (!matched)
        return { ok: false, reason: "invalid_secret" };
    return {
        ok: true,
        account: matched.account,
        accountId: matched.account.accountId,
    };
}
export function evaluateCliqWebhookEventSecurity(params) {
    return evaluateCliqPollingEventSecurity(params);
}
function webhookReasonForTurnSkip(reason) {
    if (reason === "conversation_active")
        return "turn_active";
    if (reason === "dead_lettered")
        return "dead_lettered";
    return "duplicate";
}
function emitWebhookAudit(params) {
    emitCliqAuditEvent(params.options.logger, buildCliqAuditEvent({
        kind: "webhook_ingress",
        outcome: params.outcome,
        account: params.options.account,
        source: "webhook",
        handlerKind: params.handlerKind,
        reason: params.reason,
        event: params.event,
        security: params.security,
        turn: params.turn,
        lifecycle: params.lifecycle,
    }));
}
export async function processCliqWebhookPayload(options) {
    const dedupe = options.dedupe ?? createCliqInboundDedupeStore();
    const turnLedger = options.resolvedTurnLedger ?? resolveCliqTurnLedger(options.turnLedger);
    const { envelope, event } = normalizeCliqWebhookPayload({
        account: options.account,
        payload: options.payload,
        mentionMatchers: options.mentionMatchers,
    });
    if (!envelope) {
        emitWebhookAudit({
            options,
            outcome: "ignored",
            reason: "invalid_payload",
        });
        return {
            ok: true,
            accepted: false,
            status: "ignored",
            reason: "invalid_payload",
            accountId: options.account.accountId,
        };
    }
    if (!shouldAcceptHandler(envelope.handlerKind)) {
        emitWebhookAudit({
            options,
            outcome: "ignored",
            handlerKind: envelope.handlerKind,
            reason: "unsupported_handler",
        });
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
        emitWebhookAudit({
            options,
            outcome: "ignored",
            handlerKind: envelope.handlerKind,
            reason: "invalid_payload",
        });
        return {
            ok: true,
            accepted: false,
            status: "ignored",
            reason: "invalid_payload",
            accountId: options.account.accountId,
            handlerKind: envelope.handlerKind,
        };
    }
    const existingTurn = turnLedger?.get(event);
    if (existingTurn?.state === "dead_letter") {
        emitWebhookAudit({
            options,
            outcome: "skipped",
            handlerKind: envelope.handlerKind,
            reason: "dead_lettered",
            event,
            turn: existingTurn,
        });
        return {
            ok: true,
            accepted: false,
            status: "ignored",
            reason: "dead_lettered",
            accountId: options.account.accountId,
            handlerKind: envelope.handlerKind,
            event,
            turn: existingTurn,
        };
    }
    if (existingTurn?.state === "completed") {
        emitWebhookAudit({
            options,
            outcome: "skipped",
            handlerKind: envelope.handlerKind,
            reason: "duplicate",
            event,
            turn: existingTurn,
        });
        return {
            ok: true,
            accepted: false,
            status: "ignored",
            reason: "duplicate",
            accountId: options.account.accountId,
            handlerKind: envelope.handlerKind,
            event,
            turn: existingTurn,
        };
    }
    if (!dedupe.claim(event)) {
        emitWebhookAudit({
            options,
            outcome: "skipped",
            handlerKind: envelope.handlerKind,
            reason: "duplicate",
            event,
            turn: existingTurn,
        });
        return {
            ok: true,
            accepted: false,
            status: "ignored",
            reason: "duplicate",
            accountId: options.account.accountId,
            handlerKind: envelope.handlerKind,
            event,
            ...(existingTurn ? { turn: existingTurn } : {}),
        };
    }
    const security = evaluateCliqWebhookEventSecurity({
        cfg: options.cfg,
        account: options.account,
        event,
    });
    if (!security.allowed) {
        emitWebhookAudit({
            options,
            outcome: "denied",
            handlerKind: envelope.handlerKind,
            reason: security.reasonCode,
            event,
            security,
        });
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
    let nativeDispatch;
    const turn = await runCliqInboundTurn({
        account: options.account,
        event,
        turnLedger,
        lifecycle: options.lifecycle,
        onEvent: options.onEvent
            ? async (acceptedEvent) => {
                nativeDispatch = await options.onEvent?.(acceptedEvent, {
                    account: options.account,
                    handlerKind: envelope.handlerKind,
                    replyMode: envelope.replyMode,
                    security,
                });
            }
            : undefined,
    });
    if (turn.turn.state === "failed") {
        dedupe.forget(event);
    }
    if (turn.skipped) {
        emitWebhookAudit({
            options,
            outcome: "skipped",
            handlerKind: envelope.handlerKind,
            reason: webhookReasonForTurnSkip(turn.skipReason),
            event,
            security,
            turn: turn.turn,
            lifecycle: turn.lifecycle,
        });
        return {
            ok: true,
            accepted: false,
            status: "ignored",
            reason: webhookReasonForTurnSkip(turn.skipReason),
            accountId: options.account.accountId,
            handlerKind: envelope.handlerKind,
            event,
            security,
            turn: turn.turn,
        };
    }
    emitWebhookAudit({
        options,
        outcome: turn.error ? "failed" : turn.dispatched ? "dispatched" : "accepted",
        handlerKind: envelope.handlerKind,
        reason: turn.error,
        event,
        security,
        turn: turn.turn,
        lifecycle: turn.lifecycle,
    });
    return {
        ok: true,
        accepted: true,
        accountId: options.account.accountId,
        handlerKind: envelope.handlerKind,
        event,
        security,
        lifecycle: turn.lifecycle,
        turn: turn.turn,
        ...(turn.error ? { dispatchError: turn.error } : {}),
        ...(nativeDispatch === undefined ? {} : { nativeDispatch }),
        dispatched: turn.dispatched,
    };
}
function responseLifecycleSummary(lifecycle) {
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
function responseTurnSummary(turn) {
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
    };
}
function isCliqNativeDispatchResult(value) {
    return value !== null && typeof value === "object" && "deliveryTransport" in value;
}
function responseNativeDispatchSummary(value) {
    if (!isCliqNativeDispatchResult(value))
        return undefined;
    return {
        dispatched: value.dispatched,
        admission: value.admission,
        agentId: value.agentId,
        target: value.target,
        replyToId: value.replyToId,
        threadId: value.threadId,
        deliveryTransport: value.deliveryTransport,
        deliveryCount: value.deliveryCount,
        messageIdCount: value.messageIds.length,
        deliveryFailures: value.deliveryFailures,
        reactionFallback: value.reactionFallback,
        replyTextCaptured: typeof value.replyText === "string" && value.replyText.length > 0,
        replyTextLength: value.replyText?.length ?? 0,
    };
}
function responseReplyText(value) {
    if (!isCliqNativeDispatchResult(value))
        return undefined;
    if (value.deliveryTransport !== "deluge_response")
        return undefined;
    const text = value.replyText?.trim();
    return text || undefined;
}
function sendJson(res, statusCode, payload) {
    if (res.headersSent)
        return;
    res.statusCode = statusCode;
    res.setHeader("content-type", "application/json; charset=utf-8");
    res.end(JSON.stringify(payload));
}
function responseEventSummary(event) {
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
export function createCliqWebhookHttpHandler(options) {
    const dedupe = options.dedupe ?? createCliqInboundDedupeStore();
    const turnLedger = resolveCliqTurnLedger(options.turnLedger);
    const rateLimiter = createFixedWindowRateLimiter({
        windowMs: CLIQ_WEBHOOK_RATE_LIMIT_WINDOW_MS,
        maxRequests: CLIQ_WEBHOOK_RATE_LIMIT_MAX_REQUESTS,
        maxTrackedKeys: CLIQ_WEBHOOK_MAX_TRACKED_KEYS,
    });
    const inFlightLimiter = createWebhookInFlightLimiter({
        maxInFlightPerKey: CLIQ_WEBHOOK_MAX_IN_FLIGHT_PER_KEY,
        maxTrackedKeys: CLIQ_WEBHOOK_MAX_TRACKED_KEYS,
    });
    return async (req, res) => {
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
        if (!pipeline.ok)
            return true;
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
                maxBytes: CLIQ_WEBHOOK_BODY_MAX_BYTES,
                timeoutMs: CLIQ_WEBHOOK_BODY_TIMEOUT_MS,
                profile: "post-auth",
                invalidBodyMessage: "invalid Cliq webhook body",
            });
            if (!body.ok)
                return true;
            const payload = parseCliqWebhookPayload(body.value, req.headers["content-type"]);
            if (shouldProcessCliqWebhookPayloadInBackground(payload)) {
                const envelope = extractCliqWebhookEnvelope(payload);
                void processCliqWebhookPayload({
                    ...options,
                    account: verified.account,
                    payload,
                    dedupe,
                    resolvedTurnLedger: turnLedger,
                }).catch((error) => {
                    options.logger?.error?.(`[zoho-cliq] background webhook handler failed: ${error instanceof Error ? error.message : String(error)}`);
                });
                sendJson(res, 200, {
                    ok: true,
                    accepted: true,
                    background: true,
                    transport: "zoho_cli",
                    accountId: verified.accountId,
                    handlerKind: envelope?.handlerKind,
                    dispatched: false,
                });
                return true;
            }
            const result = await processCliqWebhookPayload({
                ...options,
                account: verified.account,
                payload,
                dedupe,
                resolvedTurnLedger: turnLedger,
            });
            if (result.accepted) {
                const replyText = responseReplyText(result.nativeDispatch);
                sendJson(res, 200, {
                    ok: true,
                    accepted: true,
                    ...(replyText ? { text: replyText } : {}),
                    accountId: result.accountId,
                    handlerKind: result.handlerKind,
                    dispatched: result.dispatched,
                    event: responseEventSummary(result.event),
                    lifecycle: responseLifecycleSummary(result.lifecycle),
                    turn: responseTurnSummary(result.turn),
                    nativeDispatch: responseNativeDispatchSummary(result.nativeDispatch),
                    dispatchError: result.dispatchError,
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
                turn: responseTurnSummary(result.turn),
                securityReason: result.security && !result.security.allowed
                    ? result.security.reasonCode
                    : undefined,
            });
            return true;
        }
        catch (error) {
            options.logger?.error?.(`[zoho-cliq] webhook handler failed: ${error instanceof Error ? error.message : String(error)}`);
            sendJson(res, 500, {
                ok: false,
                error: "webhook_handler_failed",
            });
            return true;
        }
        finally {
            pipeline.release();
        }
    };
}
export function registerCliqWebhookRoutes(api) {
    const nativeDispatcher = createCliqNativeEventDispatcher(api);
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
                lifecycle: {
                    statusReactions: true,
                    markRead: false,
                    startStatuses: ["received"],
                    successStatus: null,
                    failureStatus: null,
                },
                onEvent: async (event, context) => {
                    return nativeDispatcher(event, {
                        ...context,
                        source: "webhook",
                        replyTransport: context.replyMode === "deluge_response"
                            ? "deluge_response"
                            : "zoho_cli",
                    });
                },
            }),
        });
        api.logger.info?.(`[zoho-cliq] registered webhook route ${path}`);
    }
}
