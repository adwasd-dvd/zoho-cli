export const CLIQ_REDACTED = "[redacted]";

export type CliqPrivacyRetentionPolicy = {
  rawMessageBodies: "never_in_diagnostics";
  rawWebhookPayloads: "transient_request_only";
  webhookSecrets: "secretref_or_env_only";
  tokenPasswords: "secretref_or_env_only";
  diagnosticBundleRetention: "operator_managed_short_lived";
  turnLedgerRetention: {
    storage: "in_memory_by_default";
    containsRawBodies: false;
    boundedEntries: number;
    replayRequiresOperatorAction: true;
  };
  deadLetterRetention: {
    containsRawBodies: false;
    replayDefault: "blocked";
    replayGuidance: string;
  };
  localDiagnosticBundle: {
    includes: string[];
    excludes: string[];
  };
};

const DEFAULT_TURN_LEDGER_MAX_ENTRIES = 5000;

const SENSITIVE_KEY_PATTERNS = [
  /secret/i,
  /token/i,
  /password/i,
  /authorization/i,
  /cookie/i,
  /signature/i,
  /credential/i,
  /refresh/i,
  /access[_-]?token/i,
];

const RAW_BODY_KEYS = new Set([
  "body",
  "rawbody",
  "raw_body",
  "raw",
  "text",
  "rawtext",
  "raw_text",
  "bodyforagent",
  "body_for_agent",
  "commandbody",
  "command_body",
  "message",
  "messagetext",
  "message_text",
  "payload",
  "parameters",
]);

function normalizeKey(key: string): string {
  return key.replace(/[^a-zA-Z0-9_-]/g, "").toLowerCase();
}

export function isCliqSensitiveDiagnosticKey(key: string): boolean {
  const normalized = normalizeKey(key);
  if (RAW_BODY_KEYS.has(normalized)) return true;
  return SENSITIVE_KEY_PATTERNS.some((pattern) => pattern.test(key));
}

function truncateDiagnosticString(value: string): string {
  if (value.length <= 300) return value;
  return `${value.slice(0, 297)}...`;
}

export function redactCliqDiagnosticValue(
  value: unknown,
  key = "",
): unknown {
  if (key && isCliqSensitiveDiagnosticKey(key)) return CLIQ_REDACTED;
  if (Array.isArray(value)) {
    return value.map((entry) => redactCliqDiagnosticValue(entry));
  }
  if (value && typeof value === "object") {
    return redactCliqDiagnosticObject(value as Record<string, unknown>);
  }
  if (typeof value === "string") return truncateDiagnosticString(value);
  return value;
}

export function redactCliqDiagnosticObject(
  value: Record<string, unknown>,
): Record<string, unknown> {
  const redacted: Record<string, unknown> = {};
  for (const [key, entry] of Object.entries(value)) {
    if (entry === undefined) continue;
    redacted[key] = redactCliqDiagnosticValue(entry, key);
  }
  return redacted;
}

export function resolveCliqPrivacyRetentionPolicy(params?: {
  turnLedgerMaxEntries?: number;
}): CliqPrivacyRetentionPolicy {
  return {
    rawMessageBodies: "never_in_diagnostics",
    rawWebhookPayloads: "transient_request_only",
    webhookSecrets: "secretref_or_env_only",
    tokenPasswords: "secretref_or_env_only",
    diagnosticBundleRetention: "operator_managed_short_lived",
    turnLedgerRetention: {
      storage: "in_memory_by_default",
      containsRawBodies: false,
      boundedEntries:
        params?.turnLedgerMaxEntries ?? DEFAULT_TURN_LEDGER_MAX_ENTRIES,
      replayRequiresOperatorAction: true,
    },
    deadLetterRetention: {
      containsRawBodies: false,
      replayDefault: "blocked",
      replayGuidance:
        "Inspect the redacted diagnostic bundle, fix the cause, then clear or reset the specific turn entry before replaying a trusted event.",
    },
    localDiagnosticBundle: {
      includes: [
        "correlation ids",
        "account/network ids",
        "rate-limit settings",
        "webhook/polling/lifecycle/turn-ledger states",
        "native dispatch admission and delivery metadata",
      ],
      excludes: [
        "webhook secrets",
        "token passwords",
        "authorization headers",
        "raw request signatures",
        "raw message bodies",
        "raw webhook payloads",
      ],
    },
  };
}
