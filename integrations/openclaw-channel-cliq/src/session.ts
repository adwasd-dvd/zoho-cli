import type { OpenClawConfig } from "openclaw/plugin-sdk";
import {
  buildChannelOutboundSessionRoute,
  buildThreadAwareOutboundSessionRoute,
  stripChannelTargetPrefix,
} from "openclaw/plugin-sdk/channel-core";

import type { CliqResolvedAccount } from "./config.js";
import { CLIQ_CHANNEL_ID, CLIQ_PLUGIN_ID } from "./constants.js";

type ChannelOutboundSessionRoute = ReturnType<typeof buildChannelOutboundSessionRoute>;

export type CliqTargetChatType = "direct" | "group" | "channel";

export type CliqParsedTarget = {
  to: string;
  nativeId: string;
  chatType: CliqTargetChatType;
  kind: "user" | "group" | "channel";
  threadId?: string;
};

type CliqPreferredTargetKind = "user" | "group" | "channel";

type CliqSessionPeer = {
  accountId: string;
  network: string;
  chatType: CliqTargetChatType;
  nativeId: string;
};

type CliqSessionPeerWithThread = CliqSessionPeer & {
  baseRawId: string;
  threadId?: string;
};

const DEFAULT_CLIQ_NETWORK = "default";

function normalizeNonEmpty(raw: string | number | null | undefined): string {
  return String(raw ?? "").trim();
}

function stripCliqProviderPrefix(raw: string): string {
  return stripChannelTargetPrefix(raw.trim(), "cliq", "zoho-cliq", "zoho");
}

function splitThreadSuffix(raw: string): { base: string; threadId?: string } {
  const marker = ":thread:";
  const markerIndex = raw.toLowerCase().lastIndexOf(marker);
  if (markerIndex === -1) return { base: raw };
  return {
    base: raw.slice(0, markerIndex),
    threadId: normalizeNonEmpty(raw.slice(markerIndex + marker.length)) || undefined,
  };
}

export function normalizeCliqSessionToken(raw: string | number): string {
  const trimmed = normalizeNonEmpty(raw);
  if (!trimmed) return "unknown";
  return encodeURIComponent(trimmed).toLowerCase();
}

function decodeCliqSessionToken(raw: string): string {
  try {
    return decodeURIComponent(raw);
  } catch {
    return raw;
  }
}

function targetFromNative(
  chatType: CliqTargetChatType,
  nativeId: string,
  threadId?: string,
): CliqParsedTarget {
  const id = normalizeNonEmpty(nativeId);
  if (chatType === "direct") {
    return {
      to: `user:${id}`,
      nativeId: id,
      chatType,
      kind: "user",
      ...(threadId ? { threadId } : {}),
    };
  }
  if (chatType === "group") {
    return {
      to: `chat:${id}`,
      nativeId: id,
      chatType,
      kind: "group",
      ...(threadId ? { threadId } : {}),
    };
  }
  return {
    to: `channel:${id}`,
    nativeId: id,
    chatType,
    kind: "channel",
    ...(threadId ? { threadId } : {}),
  };
}

function chatTypeFromPreferredKind(
  preferredKind?: CliqPreferredTargetKind,
): CliqTargetChatType {
  if (preferredKind === "user") return "direct";
  if (preferredKind === "group") return "group";
  return "channel";
}

export function parseCliqExplicitTarget(
  raw: string,
  preferredKind?: CliqPreferredTargetKind,
): CliqParsedTarget | null {
  const stripped = stripCliqProviderPrefix(raw);
  const { base, threadId } = splitThreadSuffix(stripped);
  const target = normalizeNonEmpty(base);
  if (!target) return null;

  const atMatch = /^@(.+)$/u.exec(target);
  if (atMatch?.[1]) return targetFromNative("direct", atMatch[1], threadId);

  const kindMatch = /^(user|dm|direct|channel|group|chat|conversation|room):(.+)$/iu.exec(
    target,
  );
  if (kindMatch?.[1] && kindMatch[2]) {
    const kind = kindMatch[1].toLowerCase();
    if (kind === "user" || kind === "dm" || kind === "direct") {
      return targetFromNative("direct", kindMatch[2], threadId);
    }
    if (kind === "group" || kind === "chat" || kind === "conversation") {
      return targetFromNative("group", kindMatch[2], threadId);
    }
    return targetFromNative("channel", kindMatch[2], threadId);
  }

  return targetFromNative(chatTypeFromPreferredKind(preferredKind), target, threadId);
}

export function normalizeCliqTarget(raw: string): string | undefined {
  return parseCliqExplicitTarget(raw)?.to;
}

export function inferCliqTargetChatType(raw: string): CliqTargetChatType {
  return parseCliqExplicitTarget(raw)?.chatType ?? "channel";
}

export function buildCliqSessionPeerId(peer: CliqSessionPeer): string {
  return [
    "account",
    normalizeCliqSessionToken(peer.accountId),
    "network",
    normalizeCliqSessionToken(peer.network || DEFAULT_CLIQ_NETWORK),
    peer.chatType,
    normalizeCliqSessionToken(peer.nativeId),
  ].join(":");
}

function parseCliqSessionPeerId(rawId: string): CliqSessionPeerWithThread | null {
  const { base, threadId } = splitThreadSuffix(rawId);
  const parts = base.split(":");
  if (parts.length !== 6) return null;
  const [accountLabel, accountId, networkLabel, network, chatType, nativeId] =
    parts;
  if (
    accountLabel !== "account" ||
    networkLabel !== "network" ||
    (chatType !== "direct" && chatType !== "group" && chatType !== "channel")
  ) {
    return null;
  }
  return {
    accountId: decodeCliqSessionToken(accountId),
    network: decodeCliqSessionToken(network),
    chatType,
    nativeId: decodeCliqSessionToken(nativeId),
    baseRawId: base,
    ...(threadId ? { threadId } : {}),
  };
}

export function resolveCliqSessionConversation(params: {
  kind: "group" | "channel";
  rawId: string;
}) {
  const parsed = parseCliqSessionPeerId(params.rawId);
  if (parsed) {
    return {
      id: parsed.baseRawId,
      threadId: parsed.threadId ?? null,
      baseConversationId: parsed.baseRawId,
      parentConversationCandidates: parsed.threadId ? [parsed.baseRawId] : [],
    };
  }

  const { base, threadId } = splitThreadSuffix(params.rawId);
  const fallbackBase = normalizeNonEmpty(base);
  if (!fallbackBase) return null;
  return {
    id: fallbackBase,
    threadId: threadId ?? null,
    baseConversationId: fallbackBase,
    parentConversationCandidates: threadId ? [fallbackBase] : [],
  };
}

export function resolveCliqSessionTarget(params: {
  kind: "group" | "channel";
  id: string;
  threadId?: string | null;
}): string | undefined {
  const parsed = parseCliqSessionPeerId(params.id);
  if (parsed) {
    const threadId = params.threadId ?? parsed.threadId;
    const target = targetFromNative(parsed.chatType, parsed.nativeId, threadId);
    return threadId ? `${target.to}:thread:${threadId}` : target.to;
  }

  const prefix = params.kind === "channel" ? "channel" : "chat";
  const id = normalizeNonEmpty(params.id);
  if (!id) return undefined;
  return params.threadId
    ? `${prefix}:${id}:thread:${params.threadId}`
    : `${prefix}:${id}`;
}

function withCliqDirectSessionScope(cfg: OpenClawConfig): OpenClawConfig {
  return {
    ...cfg,
    session: {
      ...(cfg.session ?? {}),
      dmScope: "per-account-channel-peer",
    },
  };
}

export function buildCliqOutboundSessionRoute(params: {
  cfg: OpenClawConfig;
  agentId: string;
  account: CliqResolvedAccount;
  target: string;
  resolvedTarget?: {
    to: string;
    kind: "user" | "group" | "channel";
    display?: string;
    source: "normalized" | "directory";
  };
  replyToId?: string | null;
  threadId?: string | number | null;
  currentSessionKey?: string | null;
}): ChannelOutboundSessionRoute {
  const parsed =
    parseCliqExplicitTarget(
      params.resolvedTarget?.to ?? params.target,
      params.resolvedTarget?.kind,
    ) ??
    targetFromNative("channel", params.target);
  const network = params.account.network || DEFAULT_CLIQ_NETWORK;
  const sessionPeerId = buildCliqSessionPeerId({
    accountId: params.account.accountId,
    network,
    chatType: parsed.chatType,
    nativeId: parsed.nativeId,
  });
  const route = buildChannelOutboundSessionRoute({
    cfg: withCliqDirectSessionScope(params.cfg),
    agentId: params.agentId,
    channel: CLIQ_CHANNEL_ID,
    accountId: params.account.accountId,
    peer: {
      kind: parsed.chatType,
      id: sessionPeerId,
    },
    chatType: parsed.chatType,
    from: `${CLIQ_PLUGIN_ID}:${params.account.accountId}`,
    to: parsed.to,
  });

  const explicitThreadId = normalizeNonEmpty(params.threadId ?? parsed.threadId);
  if (!explicitThreadId && !params.replyToId) return route;
  return buildThreadAwareOutboundSessionRoute({
    route,
    replyToId: params.replyToId,
    threadId: explicitThreadId || null,
    currentSessionKey: params.currentSessionKey,
    parentSessionKey: route.baseSessionKey,
    normalizeThreadId: normalizeCliqSessionToken,
  });
}
