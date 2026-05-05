import type { PluginLogger } from "openclaw/plugin-sdk";

import type { CliqResolvedAccount } from "./config.js";
import type { CliqNormalizedInboundEvent } from "./inbound.js";
import {
  markCliqMessageRead,
  setCliqStatusReaction,
  ZohoCliqCommandError,
  type CliqLifecycleStatus,
} from "./zoho-cli.js";

export type CliqInboundLifecycleActionKind = "status" | "mark_read";

export type CliqInboundLifecycleAction = {
  kind: CliqInboundLifecycleActionKind;
  ok: boolean;
  applied: boolean;
  status?: CliqLifecycleStatus;
  command?: string[];
  reason?: string;
  errorKind?: string;
  error?: string;
};

export type CliqInboundLifecycleResult = {
  eventKey: string;
  messageId: string;
  dispatched: boolean;
  actions: CliqInboundLifecycleAction[];
};

export type CliqInboundLifecycleOptions = {
  statusReactions?: boolean;
  markRead?: boolean;
  startStatuses?: CliqLifecycleStatus[];
  successStatus?: CliqLifecycleStatus | null;
  failureStatus?: CliqLifecycleStatus | null;
  logger?: Partial<PluginLogger>;
};

export type CliqInboundLifecycleOption =
  | false
  | CliqInboundLifecycleOptions
  | undefined;

function routeForEvent(event: CliqNormalizedInboundEvent): {
  messageId: string;
  chatId?: string;
  channelId?: string;
} {
  return {
    messageId: event.messageId,
    ...(event.chatId ? { chatId: event.chatId } : {}),
    ...(event.channelId ? { channelId: event.channelId } : {}),
  };
}

function errorAction(params: {
  kind: CliqInboundLifecycleActionKind;
  status?: CliqLifecycleStatus;
  error: unknown;
}): CliqInboundLifecycleAction {
  if (params.error instanceof ZohoCliqCommandError) {
    return {
      kind: params.kind,
      ok: false,
      applied: false,
      ...(params.status ? { status: params.status } : {}),
      command: params.error.command,
      reason: "zoho_cli_failed",
      errorKind: params.error.kind,
      error: params.error.stderr,
    };
  }
  const message =
    params.error instanceof Error ? params.error.message : String(params.error);
  return {
    kind: params.kind,
    ok: false,
    applied: false,
    ...(params.status ? { status: params.status } : {}),
    reason: "lifecycle_action_failed",
    error: message,
  };
}

function shouldAttemptRoute(event: CliqNormalizedInboundEvent): boolean {
  return Boolean(event.messageId && (event.chatId || event.channelId));
}

function normalizeLifecycleOptions(
  option: CliqInboundLifecycleOption,
): CliqInboundLifecycleOptions | null {
  if (option === false) return null;
  return option ?? {};
}

export async function runCliqInboundLifecycle(params: {
  account: CliqResolvedAccount;
  event: CliqNormalizedInboundEvent;
  lifecycle?: CliqInboundLifecycleOption;
  onEvent?: (event: CliqNormalizedInboundEvent) => void | Promise<void>;
}): Promise<CliqInboundLifecycleResult> {
  const lifecycle = normalizeLifecycleOptions(params.lifecycle);
  const actions: CliqInboundLifecycleAction[] = [];
  const route = routeForEvent(params.event);
  let dispatched = false;

  const result = (): CliqInboundLifecycleResult => ({
    eventKey: params.event.dedupeKey,
    messageId: params.event.messageId,
    dispatched,
    actions,
  });

  const addStatus = async (status: CliqLifecycleStatus): Promise<void> => {
    if (!lifecycle || lifecycle.statusReactions === false) return;
    if (!shouldAttemptRoute(params.event)) {
      actions.push({
        kind: "status",
        ok: false,
        applied: false,
        status,
        reason: "missing_message_route",
      });
      return;
    }
    try {
      const commandResult = await setCliqStatusReaction({
        account: params.account,
        ...route,
        status,
        clearKnown: true,
      });
      actions.push({
        kind: "status",
        ok: true,
        applied: true,
        status,
        command: commandResult.command,
      });
    } catch (error) {
      const action = errorAction({ kind: "status", status, error });
      actions.push(action);
      lifecycle.logger?.warn?.(
        `[zoho-cliq] status lifecycle ${status} failed: ${
          action.errorKind ?? action.reason
        }`,
      );
    }
  };

  const markRead = async (): Promise<void> => {
    if (!lifecycle || lifecycle.markRead === false) return;
    if (!shouldAttemptRoute(params.event)) {
      actions.push({
        kind: "mark_read",
        ok: false,
        applied: false,
        reason: "missing_message_route",
      });
      return;
    }
    try {
      const commandResult = await markCliqMessageRead({
        account: params.account,
        ...route,
      });
      actions.push({
        kind: "mark_read",
        ok: true,
        applied: true,
        command: commandResult.command,
      });
    } catch (error) {
      const action = errorAction({ kind: "mark_read", error });
      actions.push(action);
      lifecycle.logger?.warn?.(
        `[zoho-cliq] read lifecycle failed: ${
          action.errorKind ?? action.reason
        }`,
      );
    }
  };

  if (!lifecycle) {
    await params.onEvent?.(params.event);
    return {
      ...result(),
      dispatched: Boolean(params.onEvent),
    };
  }

  const startStatuses = lifecycle.startStatuses ?? ["received", "thinking"];
  for (const status of startStatuses) {
    await addStatus(status);
  }

  try {
    if (params.onEvent) {
      await params.onEvent(params.event);
      dispatched = true;
    }
    await markRead();
    if (lifecycle.successStatus !== null) {
      await addStatus(lifecycle.successStatus ?? "done");
    }
    return result();
  } catch (error) {
    if (lifecycle.failureStatus !== null) {
      await addStatus(lifecycle.failureStatus ?? "failed");
    }
    throw error;
  }
}
