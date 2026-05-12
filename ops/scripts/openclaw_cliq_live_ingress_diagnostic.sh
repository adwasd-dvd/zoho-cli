#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
RUN_ID="${ZOHO_CLIQ_INGRESS_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
REPORT_FILE="${ZOHO_CLIQ_INGRESS_REPORT_FILE:-}"
LOOKBACK_SECONDS="${ZOHO_CLIQ_INGRESS_LOOKBACK_SECONDS:-900}"
NOW_ISO="${ZOHO_CLIQ_INGRESS_NOW_ISO:-$CHECKED_AT}"
SINCE_ISO="${ZOHO_CLIQ_INGRESS_SINCE_ISO:-}"
EXPECTED_AGENT_ID="${ZOHO_CLIQ_EXPECTED_AGENT_ID:-}"
EXPECTED_AGENT_MODEL="${ZOHO_CLIQ_EXPECTED_AGENT_MODEL:-}"
LOG_FILE="${OPENCLAW_LOG_FILE:-}"

if [[ -z "$LOG_FILE" ]]; then
  LOG_FILE="$(ls -t /private/tmp/openclaw/openclaw-*.log 2>/dev/null | head -1 || true)"
fi

OPENCLAW_LOG_FILE="$LOG_FILE" \
CHECKED_AT="$CHECKED_AT" \
RUN_ID="$RUN_ID" \
REPORT_FILE="$REPORT_FILE" \
LOOKBACK_SECONDS="$LOOKBACK_SECONDS" \
NOW_ISO="$NOW_ISO" \
SINCE_ISO="$SINCE_ISO" \
EXPECTED_AGENT_ID="$EXPECTED_AGENT_ID" \
EXPECTED_AGENT_MODEL="$EXPECTED_AGENT_MODEL" \
node --input-type=module <<'NODE'
import fs from "node:fs";
import path from "node:path";

const env = process.env;

const writePayload = (payload, exitCode = 0) => {
  const text = `${JSON.stringify(payload)}\n`;
  process.stdout.write(text);
  if (env.REPORT_FILE) {
    fs.mkdirSync(path.dirname(env.REPORT_FILE), { recursive: true });
    fs.writeFileSync(env.REPORT_FILE, text);
  }
  process.exit(exitCode);
};

const basePayload = {
  schemaVersion: 1,
  kind: "openclaw_cliq_live_ingress_diagnostic",
  runId: env.RUN_ID,
  checkedAt: env.CHECKED_AT,
  channel: "cliq",
};

const fail = (error, blockers, nextAction, details = {}) =>
  writePayload(
    {
      ...basePayload,
      status: "blocked",
      error,
      blockers,
      nextAction,
      ...details,
      redaction: {
        rawWebhookPayloadStored: false,
        rawMessageBodyStored: false,
        rawCliqReplyBodyStored: false,
        secretsStored: false,
      },
    },
    1,
  );

const logFile = env.OPENCLAW_LOG_FILE;
if (!logFile || !fs.existsSync(logFile)) {
  fail("log_file_missing", ["log_file_missing"], "start_openclaw_gateway", {
    logFile: logFile || null,
  });
}

const nowMs = Date.parse(env.NOW_ISO);
if (!Number.isFinite(nowMs)) {
  fail("now_iso_invalid", ["now_iso_invalid"], "fix_ingress_diagnostic_env", {
    nowIso: env.NOW_ISO,
  });
}

const lookbackSeconds = Number.parseInt(env.LOOKBACK_SECONDS || "900", 10);
const lookbackMs = Number.isFinite(lookbackSeconds)
  ? Math.max(0, lookbackSeconds) * 1000
  : 900000;
const sinceMs = env.SINCE_ISO ? Date.parse(env.SINCE_ISO) : nowMs - lookbackMs;
if (!Number.isFinite(sinceMs)) {
  fail("since_iso_invalid", ["since_iso_invalid"], "fix_ingress_diagnostic_env", {
    sinceIso: env.SINCE_ISO,
  });
}

const extractAuditMessage = (line) => {
  let message = line;
  try {
    const outer = JSON.parse(line);
    if (typeof outer?.message === "string") {
      message = outer.message;
    }
  } catch {
    // Plain text fixture lines are supported for focused script tests.
  }
  const markerIndex = message.indexOf("[zoho-cliq-audit]");
  if (markerIndex < 0) {
    return null;
  }
  const jsonIndex = message.indexOf("{", markerIndex);
  if (jsonIndex < 0) {
    return null;
  }
  try {
    return JSON.parse(message.slice(jsonIndex));
  } catch {
    return null;
  }
};

const summarize = (record) => {
  if (!record) {
    return null;
  }
  const event = record.event || {};
  const nativeDispatch = record.nativeDispatch || {};
  const turn = record.turn || {};
  return {
    createdAt: record.createdAt || null,
    kind: record.kind || null,
    outcome: record.outcome || null,
    handlerKind: record.handlerKind || null,
    reason: record.reason || null,
    correlationId: record.correlationId || null,
    accountId: record.accountId || null,
    network: record.network || null,
    chatType: event.chatType || null,
    mentioned: typeof event.mentioned === "boolean" ? event.mentioned : null,
    textLength: Number.isFinite(event.textLength) ? event.textLength : null,
    agentId: nativeDispatch.agentId || null,
    agentModel: nativeDispatch.agentModel || null,
    deliveryCount: Number.isFinite(nativeDispatch.deliveryCount)
      ? nativeDispatch.deliveryCount
      : null,
    messageIdCount: Array.isArray(nativeDispatch.messageIds)
      ? nativeDispatch.messageIds.length
      : null,
    turnState: turn.state || null,
    lifecycleDispatched:
      typeof record.lifecycle?.dispatched === "boolean"
        ? record.lifecycle.dispatched
        : null,
  };
};

const isDiagnosticSmokeRecord = (record) =>
  record?.kind === "webhook_ingress" &&
  record?.handlerKind === "welcome" &&
  record?.reason === "unsupported_handler";

const rawLines = fs.readFileSync(logFile, "utf8").split(/\r?\n/);
const windowRecords = rawLines
  .map(extractAuditMessage)
  .filter(Boolean)
  .map((record) => ({ record, createdMs: Date.parse(record.createdAt || "") }))
  .filter((entry) => Number.isFinite(entry.createdMs) && entry.createdMs >= sinceMs)
  .sort((a, b) => a.createdMs - b.createdMs)
  .map((entry) => entry.record);
const records = windowRecords.filter((record) => !isDiagnosticSmokeRecord(record));
const ignoredDiagnosticSmokeRecords = windowRecords.length - records.length;

const webhookRecords = records.filter((record) => record.kind === "webhook_ingress");
const nativeDispatchRecords = records.filter(
  (record) => record.kind === "native_dispatch",
);
const latestWebhook = webhookRecords.at(-1) || null;
const latestNativeForWebhook = latestWebhook
  ? nativeDispatchRecords
      .filter((record) => record.correlationId === latestWebhook.correlationId)
      .at(-1) || null
  : null;

const common = {
  logFile,
  window: {
    since: new Date(sinceMs).toISOString(),
    until: new Date(nowMs).toISOString(),
    lookbackSeconds: Math.floor((nowMs - sinceMs) / 1000),
  },
  counts: {
    auditRecords: records.length,
    ignoredDiagnosticSmokeRecords,
    webhookIngress: webhookRecords.length,
    nativeDispatch: nativeDispatchRecords.length,
  },
  latestWebhook: summarize(latestWebhook),
  latestNativeDispatch: summarize(latestNativeForWebhook),
};

if (webhookRecords.length === 0) {
  fail(
    "no_recent_webhook_ingress",
    ["no_recent_webhook_ingress"],
    "send_or_fix_zoho_bot_handler",
    common,
  );
}

if (latestWebhook?.outcome !== "dispatched") {
  fail(
    "latest_webhook_not_dispatched",
    ["latest_webhook_not_dispatched"],
    "fix_webhook_payload_or_policy",
    common,
  );
}

if (!latestNativeForWebhook) {
  fail(
    "native_dispatch_missing",
    ["native_dispatch_missing"],
    "check_openclaw_channel_dispatch",
    common,
  );
}

const nativeSummary = summarize(latestNativeForWebhook);
const blockers = [];
if (env.EXPECTED_AGENT_ID && nativeSummary.agentId !== env.EXPECTED_AGENT_ID) {
  blockers.push("agent_mismatch");
}
if (env.EXPECTED_AGENT_MODEL && nativeSummary.agentModel !== env.EXPECTED_AGENT_MODEL) {
  blockers.push("agent_model_mismatch");
}
if (!Number.isFinite(nativeSummary.deliveryCount) || nativeSummary.deliveryCount < 1) {
  blockers.push("dispatch_reply_not_delivered");
}

if (blockers.length > 0) {
  fail(
    blockers.includes("dispatch_reply_not_delivered")
      ? "dispatch_reply_not_delivered"
      : "route_mismatch",
    blockers,
    blockers.includes("dispatch_reply_not_delivered")
      ? "check_cliq_reply_delivery"
      : "fix_openclaw_route_binding",
    common,
  );
}

writePayload({
  ...basePayload,
  status: "live_ingress_active",
  blockers: [],
  nextAction: "collect_trusted_reply_facts_if_needed",
  ...common,
  redaction: {
    rawWebhookPayloadStored: false,
    rawMessageBodyStored: false,
    rawCliqReplyBodyStored: false,
    secretsStored: false,
  },
});
NODE
