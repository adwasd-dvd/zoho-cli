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
    if (target.kind === "channel" || target.kind === "chat") {
        return [...args, "--channel-id", target.id];
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
export async function sendCliqText(params) {
    const result = await runZohoCliqJson(params.account, buildCliqDeliveryArgs(params));
    return { messageId: extractCliqMessageId(result.stdout) };
}
