import { runPluginCommandWithTimeout } from "openclaw/plugin-sdk/run-command";
const ZOHO_CLI_TIMEOUT_MS = 30_000;
export class ZohoCliqCommandError extends Error {
    command;
    exitCode;
    stderr;
    kind;
    constructor(params) {
        const kind = params.kind ?? "command_failed";
        super(`zoho-cli command failed (${kind}) with exit code ${params.exitCode ?? "unknown"}: ${params.command.join(" ")}`);
        this.name = "ZohoCliqCommandError";
        this.command = params.command;
        this.exitCode = params.exitCode;
        this.stderr = redactCliqDiagnostics(params.stderr, params.redactionValues);
        this.kind = kind;
    }
}
function escapeRegExp(value) {
    return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
function redactCliqDiagnostics(raw, values = []) {
    const uniqueValues = [...new Set(values.map((value) => value.trim()))].filter((value) => value.length >= 4);
    return uniqueValues
        .reduce((text, value) => text.replace(new RegExp(escapeRegExp(value), "g"), "<redacted>"), raw)
        .replace(/(ZOHO_TOKEN_PASSWORD=)[^\s]+/g, "$1<redacted>")
        .replace(/(ZOHO_CLIQ_WEBHOOK_SECRET=)[^\s]+/g, "$1<redacted>")
        .replace(/(access_token|refresh_token|id_token|token|password|secret|webhook_secret|webhookSecret)(["']?\s*[:=]\s*["']?)[^"',\s]+/gi, "$1$2<redacted>")
        .replace(/(Authorization:\s*(?:Bearer|Zoho-oauthtoken)\s+)[^\s]+/gi, "$1<redacted>");
}
function normalizeConfigInput(input) {
    if (!input)
        return undefined;
    if (typeof input === "string") {
        const value = input.trim();
        return value || undefined;
    }
    if (input.source !== "env")
        return undefined;
    const envKey = input.id?.trim();
    if (!envKey)
        return undefined;
    const value = process.env[envKey]?.trim();
    return value || undefined;
}
function normalizeSecretInput(input) {
    if (!input)
        return undefined;
    if (typeof input === "string") {
        const value = input.trim();
        return value || undefined;
    }
    if (input.source !== "env")
        return undefined;
    const envKey = input.id?.trim();
    if (!envKey)
        return undefined;
    const value = process.env[envKey]?.trim();
    return value || undefined;
}
function buildZohoCliRuntimeEnv(account) {
    const env = { ...process.env };
    const accountEmail = normalizeConfigInput(account.accountEmail);
    const configPath = normalizeConfigInput(account.configPath);
    const tokenPassword = normalizeSecretInput(account.tokenPassword);
    const webhookSecret = normalizeSecretInput(account.webhookSecret);
    const redactionValues = [tokenPassword, webhookSecret].filter((value) => Boolean(value));
    if (accountEmail)
        env.ZOHO_ACCOUNT = accountEmail;
    if (configPath)
        env.ZOHO_CONFIG = configPath;
    if (tokenPassword)
        env.ZOHO_TOKEN_PASSWORD = tokenPassword;
    if (webhookSecret)
        env.ZOHO_CLIQ_WEBHOOK_SECRET = webhookSecret;
    return { env, redactionValues };
}
function classifyZohoCliError(stderr) {
    const text = stderr.toLowerCase();
    if (text.includes("enoent") || text.includes("not found")) {
        return "command_not_found";
    }
    if (text.includes("timeout") || text.includes("timed out")) {
        return "timeout";
    }
    if (text.includes("token_refresh_rate_limited") ||
        text.includes("rate_limited") ||
        text.includes("rate limited") ||
        text.includes("rate limit") ||
        text.includes("too many requests") ||
        text.includes("try again after")) {
        return "rate_limited";
    }
    if (text.includes("missing_scope") ||
        text.includes("insufficient_scope") ||
        text.includes("oauth_scope_mismatch") ||
        text.includes("scope")) {
        return "scope_missing";
    }
    if (text.includes("not_supported") ||
        text.includes("unsupported") ||
        text.includes("request_url_invalid") ||
        text.includes("extra_param_found") ||
        text.includes("inactive_appaccount_user")) {
        return "unsupported_endpoint";
    }
    if (text.includes("not_logged_in") ||
        text.includes("not logged in") ||
        text.includes("login required") ||
        text.includes("authentication required") ||
        text.includes("auth")) {
        return "auth_missing";
    }
    return "command_failed";
}
function normalizeOptionalText(value) {
    if (value === null || value === undefined)
        return undefined;
    const text = String(value).trim();
    return text || undefined;
}
function normalizePositiveInt(value, fallback) {
    if (!Number.isFinite(value ?? Number.NaN))
        return fallback;
    return Math.max(1, Math.floor(value));
}
function normalizeNonNegativeInt(value, fallback) {
    if (!Number.isFinite(value ?? Number.NaN))
        return fallback;
    return Math.max(0, Math.floor(value));
}
function networkArgs(account) {
    return account.network ? ["--network", account.network] : [];
}
export async function runZohoCliqJson(account, args, options = {}) {
    const cliPath = (account.cliPath || "zoho").trim() || "zoho";
    const command = [cliPath, "cliq", ...args];
    const runtime = buildZohoCliRuntimeEnv(account);
    let result;
    try {
        result = await runPluginCommandWithTimeout({
            argv: command,
            timeoutMs: options.timeoutMs ?? ZOHO_CLI_TIMEOUT_MS,
            env: runtime.env,
        });
    }
    catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        const lower = message.toLowerCase();
        const kind = lower.includes("enoent") || lower.includes("not found")
            ? "command_not_found"
            : lower.includes("timeout") || lower.includes("timed out")
                ? "timeout"
                : "command_failed";
        throw new ZohoCliqCommandError({
            command,
            exitCode: null,
            stderr: message,
            kind,
            redactionValues: runtime.redactionValues,
        });
    }
    if (result.code !== 0) {
        throw new ZohoCliqCommandError({
            command,
            exitCode: result.code,
            stderr: result.stderr,
            kind: classifyZohoCliError(result.stderr),
            redactionValues: runtime.redactionValues,
        });
    }
    const text = result.stdout.trim();
    if (!text) {
        throw new ZohoCliqCommandError({
            command,
            exitCode: result.code,
            stderr: "zoho-cli returned empty stdout while JSON output was expected",
            kind: "invalid_json",
            redactionValues: runtime.redactionValues,
        });
    }
    try {
        return {
            command,
            stdout: JSON.parse(text),
            stderr: redactCliqDiagnostics(result.stderr, runtime.redactionValues),
        };
    }
    catch {
        throw new ZohoCliqCommandError({
            command,
            exitCode: result.code,
            stderr: redactCliqDiagnostics(`invalid JSON stdout: ${text.slice(0, 400)}`, runtime.redactionValues),
            kind: "invalid_json",
            redactionValues: runtime.redactionValues,
        });
    }
}
function normalizeCliqTargetRef(targetRaw) {
    const target = targetRaw.trim();
    if (target.startsWith("channel:")) {
        return { kind: "channel", id: target.slice("channel:".length) };
    }
    if (target.startsWith("user:")) {
        return { kind: "user", id: target.slice("user:".length) };
    }
    if (target.startsWith("chat:")) {
        return { kind: "chat", id: target.slice("chat:".length) };
    }
    if (target.startsWith("group:")) {
        return { kind: "chat", id: target.slice("group:".length) };
    }
    if (target.startsWith("@")) {
        return { kind: "user", id: target.slice(1) };
    }
    return { kind: "channel", id: target };
}
export function buildCliqSendArgs(params) {
    const target = normalizeCliqTargetRef(params.to);
    const args = ["send", "--text", params.text, ...networkArgs(params.account)];
    if (target.kind === "channel") {
        return [...args, "--channel-id", target.id];
    }
    if (target.kind === "chat") {
        return [...args, "--chat-id", target.id];
    }
    return [...args, "--user-id", target.id];
}
export function buildCliqReplyArgs(params) {
    const target = normalizeCliqTargetRef(params.to);
    const args = [
        "reply",
        params.replyToId,
        "--text",
        params.text,
        ...networkArgs(params.account),
    ];
    const threadId = normalizeOptionalText(params.threadId);
    if (threadId) {
        return [...args, "--chat-id", threadId];
    }
    if (target.kind === "channel") {
        return [...args, "--channel-id", target.id];
    }
    return [...args, "--chat-id", target.id];
}
export function buildCliqThreadReplyArgs(params) {
    const target = normalizeCliqTargetRef(params.to);
    const threadId = normalizeOptionalText(params.threadId) || "";
    const args = [
        "thread-reply",
        threadId,
        "--text",
        params.text,
        ...networkArgs(params.account),
    ];
    if (target.kind === "channel") {
        return [...args, "--channel-id", target.id];
    }
    return [...args, "--chat-id", target.id];
}
export function buildCliqDeliveryArgs(params) {
    const threadId = normalizeOptionalText(params.threadId);
    if (threadId) {
        return buildCliqThreadReplyArgs({
            account: params.account,
            to: params.to,
            text: params.text,
            threadId,
        });
    }
    const replyToId = normalizeOptionalText(params.replyToId);
    if (replyToId) {
        return buildCliqReplyArgs({
            account: params.account,
            to: params.to,
            text: params.text,
            replyToId,
        });
    }
    return buildCliqSendArgs({
        account: params.account,
        to: params.to,
        text: params.text,
    });
}
function cliqMessageRouteArgs(params) {
    const chatId = normalizeOptionalText(params.chatId);
    if (chatId)
        return ["--chat-id", chatId];
    const channelId = normalizeOptionalText(params.channelId);
    if (channelId)
        return ["--channel-id", channelId];
    throw new Error("cliq message route requires chatId or channelId");
}
export function buildCliqStatusReactArgs(params) {
    const messageId = normalizeOptionalText(params.messageId);
    if (!messageId)
        throw new Error("cliq status-react requires messageId");
    return [
        "status-react",
        messageId,
        "--status",
        params.status,
        ...networkArgs(params.account),
        ...cliqMessageRouteArgs(params),
        params.clearKnown === false ? "--keep-existing" : "--clear-known",
    ];
}
export function buildCliqMarkReadArgs(params) {
    const messageId = normalizeOptionalText(params.messageId);
    if (!messageId)
        throw new Error("cliq mark-read requires messageId");
    return [
        "mark-read",
        messageId,
        ...networkArgs(params.account),
        ...cliqMessageRouteArgs(params),
    ];
}
export function buildCliqChatsArgs(params) {
    const args = [
        "chats",
        "--limit",
        String(normalizePositiveInt(params.limit, 50)),
        ...networkArgs(params.account),
    ];
    if (params.unreadOnly !== false) {
        args.push("--unread-only");
    }
    if (params.excludeReactedBySelf) {
        args.push("--exclude-reacted-by-self");
    }
    return args;
}
export function buildCliqContextArgs(params) {
    const chatId = normalizeOptionalText(params.chatId);
    const channelId = normalizeOptionalText(params.channelId);
    if (!chatId && !channelId) {
        throw new Error("cliq context requires chatId or channelId");
    }
    const args = [
        "context",
        "--limit",
        String(normalizePositiveInt(params.limit, 50)),
        ...networkArgs(params.account),
    ];
    if (chatId) {
        args.push("--chat-id", chatId);
    }
    if (channelId) {
        args.push("--channel-id", channelId);
    }
    const messageId = normalizeOptionalText(params.messageId);
    if (messageId) {
        args.push("--message-id", messageId);
    }
    if (params.before !== undefined) {
        args.push("--before", String(normalizeNonNegativeInt(params.before, 0)));
    }
    if (params.after !== undefined) {
        args.push("--after", String(normalizeNonNegativeInt(params.after, 0)));
    }
    return args;
}
function readStringField(value, ...keys) {
    for (const key of keys) {
        const raw = value[key];
        if (typeof raw === "string" && raw.trim())
            return raw.trim();
        if (typeof raw === "number")
            return String(raw);
    }
    return undefined;
}
function extractCliqMessageId(payload) {
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
        return undefined;
    }
    const record = payload;
    const direct = readStringField(record, "messageId", "message_id", "id");
    if (direct)
        return direct;
    for (const key of ["message", "data", "result"]) {
        const nested = record[key];
        if (nested && typeof nested === "object" && !Array.isArray(nested)) {
            const nestedId = readStringField(nested, "messageId", "message_id", "id");
            if (nestedId)
                return nestedId;
        }
    }
    return undefined;
}
function extractCliqChatsRows(payload) {
    if (Array.isArray(payload)) {
        return payload.filter((item) => Boolean(item) && typeof item === "object" && !Array.isArray(item));
    }
    if (!payload || typeof payload !== "object")
        return [];
    const root = payload;
    for (const key of ["chats", "data", "items", "records", "result", "results"]) {
        const value = root[key];
        if (Array.isArray(value)) {
            return value.filter((item) => Boolean(item) && typeof item === "object" && !Array.isArray(item));
        }
        if (value && typeof value === "object" && !Array.isArray(value)) {
            const nested = extractCliqChatsRows(value);
            if (nested.length > 0)
                return nested;
        }
    }
    return [];
}
function extractCliqMessagesRows(payload) {
    if (Array.isArray(payload))
        return payload;
    if (!payload || typeof payload !== "object")
        return [];
    const root = payload;
    for (const key of ["messages", "data", "items", "records", "result"]) {
        const value = root[key];
        if (Array.isArray(value))
            return value;
        if (value && typeof value === "object" && !Array.isArray(value)) {
            const nested = extractCliqMessagesRows(value);
            if (nested.length > 0)
                return nested;
        }
    }
    return [];
}
function normalizeContextPayload(payload) {
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
        return { messages: [] };
    }
    const root = payload;
    return {
        ...root,
        messages: extractCliqMessagesRows(payload),
    };
}
export async function sendCliqText(params) {
    const result = await runZohoCliqJson(params.account, buildCliqDeliveryArgs(params));
    return { messageId: extractCliqMessageId(result.stdout) };
}
export async function setCliqStatusReaction(params) {
    return runZohoCliqJson(params.account, buildCliqStatusReactArgs(params));
}
export async function markCliqMessageRead(params) {
    return runZohoCliqJson(params.account, buildCliqMarkReadArgs(params));
}
export async function listCliqChats(params) {
    const result = await runZohoCliqJson(params.account, buildCliqChatsArgs(params));
    return { chats: extractCliqChatsRows(result.stdout) };
}
export async function fetchCliqContext(params) {
    const result = await runZohoCliqJson(params.account, buildCliqContextArgs(params));
    return normalizeContextPayload(result.stdout);
}
