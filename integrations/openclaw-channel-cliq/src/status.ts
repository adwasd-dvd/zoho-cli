import type { OpenClawConfig } from "openclaw/plugin-sdk";

import {
  describeCliqAccount,
  describeCliqAccountDiagnostics,
  describeCliqAgentBinding,
  describeCliqCapabilityDiagnostics,
  isCliqAccountConfigured,
  resolveCliqAccount,
} from "./config.js";
import { CLIQ_CHANNEL_ID } from "./constants.js";
import {
  buildCliqOutboundSessionRoute,
  inferCliqTargetChatType,
  normalizeCliqTarget,
  parseCliqExplicitTarget,
} from "./session.js";
import {
  resolveCliqSetupStateCodes,
  resolveCliqSetupStatusLines,
} from "./setup-wizard.js";

export type CliqChannelStatusSummary = {
  channel: "cliq";
  accountId: string;
  enabled: boolean;
  configured: boolean;
  setupStates: string[];
  statusLines: string[];
  account: ReturnType<typeof describeCliqAccount>;
  diagnostics: ReturnType<typeof describeCliqAccountDiagnostics>;
  agentBinding: ReturnType<typeof describeCliqAgentBinding>;
};

export type CliqChannelCapabilitySummary = {
  channel: "cliq";
  accountId: string;
  capabilities: ReturnType<typeof describeCliqCapabilityDiagnostics>;
  chatTypes: string[];
  nativeMessageSurface: boolean;
  nativeApprovalSurface: boolean;
  customSendTools: false;
};

export type CliqRoutingDiagnostic = {
  channel: "cliq";
  accountId: string;
  network: string;
  input: string;
  normalized?: string;
  chatType: string;
  nativeId?: string;
  threadId?: string;
  sessionRoute?: ReturnType<typeof buildCliqOutboundSessionRoute>;
  error?: string;
};

export function resolveCliqChannelStatusSummary(params: {
  cfg: OpenClawConfig;
  accountId?: string;
}): CliqChannelStatusSummary {
  const account = resolveCliqAccount(params.cfg, params.accountId);
  const configured = isCliqAccountConfigured(account);
  return {
    channel: CLIQ_CHANNEL_ID,
    accountId: account.accountId,
    enabled: account.enabled,
    configured,
    setupStates: resolveCliqSetupStateCodes({
      cfg: params.cfg,
      accountId: account.accountId,
    }),
    statusLines: resolveCliqSetupStatusLines({
      cfg: params.cfg,
      accountId: account.accountId,
      configured,
    }),
    account: describeCliqAccount(account),
    diagnostics: describeCliqAccountDiagnostics(account, params.cfg),
    agentBinding: describeCliqAgentBinding(params.cfg, account.accountId),
  };
}

export function resolveCliqChannelCapabilitySummary(params: {
  cfg: OpenClawConfig;
  accountId?: string;
}): CliqChannelCapabilitySummary {
  const account = resolveCliqAccount(params.cfg, params.accountId);
  return {
    channel: CLIQ_CHANNEL_ID,
    accountId: account.accountId,
    capabilities: describeCliqCapabilityDiagnostics(account),
    chatTypes: ["direct", "group", "channel", "thread"],
    nativeMessageSurface: true,
    nativeApprovalSurface: true,
    customSendTools: false,
  };
}

export function resolveCliqRoutingDiagnostic(params: {
  cfg: OpenClawConfig;
  accountId?: string;
  target: string;
  agentId?: string;
  replyToId?: string | null;
  threadId?: string | number | null;
  currentSessionKey?: string | null;
}): CliqRoutingDiagnostic {
  const account = resolveCliqAccount(params.cfg, params.accountId);
  const parsed = parseCliqExplicitTarget(params.target);
  if (!parsed) {
    return {
      channel: CLIQ_CHANNEL_ID,
      accountId: account.accountId,
      network: account.network || "default",
      input: params.target,
      chatType: "unknown",
      error: "target_unresolved",
    };
  }
  return {
    channel: CLIQ_CHANNEL_ID,
    accountId: account.accountId,
    network: account.network || "default",
    input: params.target,
    normalized: normalizeCliqTarget(params.target),
    chatType: inferCliqTargetChatType(params.target),
    nativeId: parsed.nativeId,
    ...(parsed.threadId ? { threadId: parsed.threadId } : {}),
    sessionRoute: buildCliqOutboundSessionRoute({
      cfg: params.cfg,
      agentId: params.agentId ?? "diagnostic",
      account,
      target: params.target,
      replyToId: params.replyToId ?? null,
      threadId: params.threadId ?? parsed.threadId ?? null,
      currentSessionKey: params.currentSessionKey ?? null,
    }),
  };
}
