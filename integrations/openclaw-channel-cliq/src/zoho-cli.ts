import { runPluginCommandWithTimeout } from "openclaw/plugin-sdk/run-command";

import type { CliqConfigValueInput, CliqResolvedAccount } from "./config.js";

const ZOHO_CLI_TIMEOUT_MS = 30_000;

export type ZohoCliqCommandErrorKind =
  | "auth_missing"
  | "scope_missing"
  | "unsupported_endpoint"
  | "invalid_json"
  | "timeout"
  | "command_not_found"
  | "command_failed";

export type ZohoCliJsonResult<T = unknown> = {
  command: string[];
  stdout: T;
  stderr: string;
};

export type ZohoCliqRunOptions = {
  timeoutMs?: number;
};

export class ZohoCliqCommandError extends Error {
  readonly command: string[];
  readonly exitCode: number | null;
  readonly stderr: string;
  readonly kind: ZohoCliqCommandErrorKind;

  constructor(params: {
    command: string[];
    exitCode: number | null;
    stderr: string;
    kind?: ZohoCliqCommandErrorKind;
    redactionValues?: string[];
  }) {
    const kind = params.kind ?? "command_failed";
    super(
      `zoho-cli command failed (${kind}) with exit code ${
        params.exitCode ?? "unknown"
      }: ${params.command.join(" ")}`,
    );
    this.name = "ZohoCliqCommandError";
    this.command = params.command;
    this.exitCode = params.exitCode;
    this.stderr = redactCliqDiagnostics(params.stderr, params.redactionValues);
    this.kind = kind;
  }
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function redactCliqDiagnostics(raw: string, values: string[] = []): string {
  const uniqueValues = [...new Set(values.map((value) => value.trim()))].filter(
    (value) => value.length >= 4,
  );
  return uniqueValues
    .reduce(
      (text, value) =>
        text.replace(new RegExp(escapeRegExp(value), "g"), "<redacted>"),
      raw,
    )
    .replace(/(ZOHO_TOKEN_PASSWORD=)[^\s]+/g, "$1<redacted>")
    .replace(/(ZOHO_CLIQ_WEBHOOK_SECRET=)[^\s]+/g, "$1<redacted>")
    .replace(
      /(access_token|refresh_token|id_token|token|password|secret|webhook_secret|webhookSecret)(["']?\s*[:=]\s*["']?)[^"',\s]+/gi,
      "$1$2<redacted>",
    )
    .replace(
      /(Authorization:\s*(?:Bearer|Zoho-oauthtoken)\s+)[^\s]+/gi,
      "$1<redacted>",
    );
}

function normalizeConfigInput(input?: CliqConfigValueInput): string | undefined {
  if (!input) return undefined;
  if (typeof input === "string") {
    const value = input.trim();
    return value || undefined;
  }
  if (input.source !== "env") return undefined;
  const envKey = input.id?.trim();
  if (!envKey) return undefined;
  const value = process.env[envKey]?.trim();
  return value || undefined;
}

function normalizeSecretInput(input?: CliqResolvedAccount["tokenPassword"]):
  | string
  | undefined {
  if (!input) return undefined;
  if (typeof input === "string") {
    const value = input.trim();
    return value || undefined;
  }
  if (input.source !== "env") return undefined;
  const envKey = input.id?.trim();
  if (!envKey) return undefined;
  const value = process.env[envKey]?.trim();
  return value || undefined;
}

function buildZohoCliRuntimeEnv(account: CliqResolvedAccount): {
  env: NodeJS.ProcessEnv;
  redactionValues: string[];
} {
  const env: NodeJS.ProcessEnv = { ...process.env };
  const accountEmail = normalizeConfigInput(account.accountEmail);
  const configPath = normalizeConfigInput(account.configPath);
  const tokenPassword = normalizeSecretInput(account.tokenPassword);
  const webhookSecret = normalizeSecretInput(account.webhookSecret);
  const redactionValues = [tokenPassword, webhookSecret].filter(
    (value): value is string => Boolean(value),
  );

  if (accountEmail) env.ZOHO_ACCOUNT = accountEmail;
  if (configPath) env.ZOHO_CONFIG = configPath;
  if (tokenPassword) env.ZOHO_TOKEN_PASSWORD = tokenPassword;
  if (webhookSecret) env.ZOHO_CLIQ_WEBHOOK_SECRET = webhookSecret;
  return { env, redactionValues };
}

function classifyZohoCliError(stderr: string): ZohoCliqCommandErrorKind {
  const text = stderr.toLowerCase();
  if (text.includes("enoent") || text.includes("not found")) {
    return "command_not_found";
  }
  if (text.includes("timeout") || text.includes("timed out")) {
    return "timeout";
  }
  if (
    text.includes("missing_scope") ||
    text.includes("insufficient_scope") ||
    text.includes("oauth_scope_mismatch") ||
    text.includes("scope")
  ) {
    return "scope_missing";
  }
  if (
    text.includes("not_supported") ||
    text.includes("unsupported") ||
    text.includes("request_url_invalid") ||
    text.includes("extra_param_found") ||
    text.includes("inactive_appaccount_user")
  ) {
    return "unsupported_endpoint";
  }
  if (
    text.includes("not_logged_in") ||
    text.includes("not logged in") ||
    text.includes("login required") ||
    text.includes("authentication required") ||
    text.includes("auth")
  ) {
    return "auth_missing";
  }
  return "command_failed";
}

function normalizeOptionalText(
  value: string | number | null | undefined,
): string | undefined {
  if (value === null || value === undefined) return undefined;
  const text = String(value).trim();
  return text || undefined;
}

function normalizePositiveInt(
  value: number | undefined,
  fallback: number,
): number {
  if (!Number.isFinite(value ?? Number.NaN)) return fallback;
  return Math.max(1, Math.floor(value as number));
}

function normalizeNonNegativeInt(
  value: number | undefined,
  fallback: number,
): number {
  if (!Number.isFinite(value ?? Number.NaN)) return fallback;
  return Math.max(0, Math.floor(value as number));
}

function networkArgs(account: CliqResolvedAccount): string[] {
  return account.network ? ["--network", account.network] : [];
}

export async function runZohoCliqJson<T = unknown>(
  account: CliqResolvedAccount,
  args: string[],
  options: ZohoCliqRunOptions = {},
): Promise<ZohoCliJsonResult<T>> {
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
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const lower = message.toLowerCase();
    const kind =
      lower.includes("enoent") || lower.includes("not found")
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
      stdout: JSON.parse(text) as T,
      stderr: redactCliqDiagnostics(result.stderr, runtime.redactionValues),
    };
  } catch {
    throw new ZohoCliqCommandError({
      command,
      exitCode: result.code,
      stderr: redactCliqDiagnostics(
        `invalid JSON stdout: ${text.slice(0, 400)}`,
        runtime.redactionValues,
      ),
      kind: "invalid_json",
      redactionValues: runtime.redactionValues,
    });
  }
}

function normalizeCliqTargetRef(targetRaw: string): {
  kind: "channel" | "user" | "chat";
  id: string;
} {
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

export function buildCliqSendArgs(params: {
  account: CliqResolvedAccount;
  to: string;
  text: string;
  threadId?: string | number | null;
}): string[] {
  const target = normalizeCliqTargetRef(params.to);
  const args = ["send", "--text", params.text, ...networkArgs(params.account)];

  if (target.kind === "channel" || target.kind === "chat") {
    return [...args, "--channel-id", target.id];
  }
  return [...args, "--user-id", target.id];
}

export function buildCliqReplyArgs(params: {
  account: CliqResolvedAccount;
  to: string;
  text: string;
  replyToId: string;
  threadId?: string | number | null;
}): string[] {
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

export function buildCliqThreadReplyArgs(params: {
  account: CliqResolvedAccount;
  to: string;
  text: string;
  threadId: string | number;
}): string[] {
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

export function buildCliqDeliveryArgs(params: {
  account: CliqResolvedAccount;
  to: string;
  text: string;
  replyToId?: string | null;
  threadId?: string | number | null;
}): string[] {
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

export function buildCliqChatsArgs(params: {
  account: CliqResolvedAccount;
  limit?: number;
  unreadOnly?: boolean;
  excludeReactedBySelf?: boolean;
}): string[] {
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

export function buildCliqContextArgs(params: {
  account: CliqResolvedAccount;
  chatId?: string | null;
  channelId?: string | null;
  messageId?: string | null;
  before?: number;
  after?: number;
  limit?: number;
}): string[] {
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

function readStringField(
  value: Record<string, unknown>,
  ...keys: string[]
): string | undefined {
  for (const key of keys) {
    const raw = value[key];
    if (typeof raw === "string" && raw.trim()) return raw.trim();
    if (typeof raw === "number") return String(raw);
  }
  return undefined;
}

function extractCliqMessageId(payload: unknown): string | undefined {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return undefined;
  }
  const record = payload as Record<string, unknown>;
  const direct = readStringField(record, "messageId", "message_id", "id");
  if (direct) return direct;

  for (const key of ["message", "data", "result"]) {
    const nested = record[key];
    if (nested && typeof nested === "object" && !Array.isArray(nested)) {
      const nestedId = readStringField(
        nested as Record<string, unknown>,
        "messageId",
        "message_id",
        "id",
      );
      if (nestedId) return nestedId;
    }
  }
  return undefined;
}

function extractCliqChatsRows(payload: unknown): Record<string, unknown>[] {
  if (Array.isArray(payload)) {
    return payload.filter(
      (item): item is Record<string, unknown> =>
        Boolean(item) && typeof item === "object" && !Array.isArray(item),
    );
  }
  if (!payload || typeof payload !== "object") return [];

  const root = payload as Record<string, unknown>;
  for (const key of ["chats", "data", "items", "records", "result", "results"]) {
    const value = root[key];
    if (Array.isArray(value)) {
      return value.filter(
        (item): item is Record<string, unknown> =>
          Boolean(item) && typeof item === "object" && !Array.isArray(item),
      );
    }
    if (value && typeof value === "object" && !Array.isArray(value)) {
      const nested = extractCliqChatsRows(value);
      if (nested.length > 0) return nested;
    }
  }
  return [];
}

function extractCliqMessagesRows(payload: unknown): unknown[] {
  if (Array.isArray(payload)) return payload;
  if (!payload || typeof payload !== "object") return [];

  const root = payload as Record<string, unknown>;
  for (const key of ["messages", "data", "items", "records", "result"]) {
    const value = root[key];
    if (Array.isArray(value)) return value;
    if (value && typeof value === "object" && !Array.isArray(value)) {
      const nested = extractCliqMessagesRows(value);
      if (nested.length > 0) return nested;
    }
  }
  return [];
}

function normalizeContextPayload(
  payload: unknown,
): Record<string, unknown> {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return { messages: [] };
  }
  const root = payload as Record<string, unknown>;
  return {
    ...root,
    messages: extractCliqMessagesRows(payload),
  };
}

export async function sendCliqText(params: {
  account: CliqResolvedAccount;
  to: string;
  text: string;
  replyToId?: string | null;
  threadId?: string | number | null;
}): Promise<{ messageId?: string }> {
  const result = await runZohoCliqJson<Record<string, unknown>>(
    params.account,
    buildCliqDeliveryArgs(params),
  );
  return { messageId: extractCliqMessageId(result.stdout) };
}

export async function listCliqChats(params: {
  account: CliqResolvedAccount;
  limit?: number;
  unreadOnly?: boolean;
  excludeReactedBySelf?: boolean;
}): Promise<{ chats: Record<string, unknown>[] }> {
  const result = await runZohoCliqJson<unknown>(
    params.account,
    buildCliqChatsArgs(params),
  );
  return { chats: extractCliqChatsRows(result.stdout) };
}

export async function fetchCliqContext(params: {
  account: CliqResolvedAccount;
  chatId?: string | null;
  channelId?: string | null;
  messageId?: string | null;
  before?: number;
  after?: number;
  limit?: number;
}): Promise<Record<string, unknown>> {
  const result = await runZohoCliqJson<unknown>(
    params.account,
    buildCliqContextArgs(params),
  );
  return normalizeContextPayload(result.stdout);
}
