import { markCliqMessageRead, setCliqStatusReaction, ZohoCliqCommandError, } from "./zoho-cli.js";
export class CliqInboundLifecycleDispatchError extends Error {
    lifecycle;
    cause;
    constructor(error, lifecycle) {
        const message = error instanceof Error ? error.message : String(error || "dispatch failed");
        super(message);
        this.name = "CliqInboundLifecycleDispatchError";
        this.cause = error;
        this.lifecycle = lifecycle;
    }
}
function routeForEvent(event) {
    return {
        messageId: event.messageId,
        ...(event.chatId ? { chatId: event.chatId } : {}),
        ...(event.channelId ? { channelId: event.channelId } : {}),
    };
}
function errorAction(params) {
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
    const message = params.error instanceof Error ? params.error.message : String(params.error);
    return {
        kind: params.kind,
        ok: false,
        applied: false,
        ...(params.status ? { status: params.status } : {}),
        reason: "lifecycle_action_failed",
        error: message,
    };
}
function shouldAttemptRoute(event) {
    return Boolean(event.messageId && (event.chatId || event.channelId));
}
function normalizeLifecycleOptions(option) {
    if (option === false)
        return null;
    return option ?? {};
}
export async function runCliqInboundLifecycle(params) {
    const lifecycle = normalizeLifecycleOptions(params.lifecycle);
    const actions = [];
    const route = routeForEvent(params.event);
    let dispatched = false;
    const result = () => ({
        eventKey: params.event.dedupeKey,
        messageId: params.event.messageId,
        dispatched,
        actions,
    });
    const addStatus = async (status) => {
        if (!lifecycle || lifecycle.statusReactions === false)
            return;
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
        }
        catch (error) {
            const action = errorAction({ kind: "status", status, error });
            actions.push(action);
            lifecycle.logger?.warn?.(`[zoho-cliq] status lifecycle ${status} failed: ${action.errorKind ?? action.reason}`);
        }
    };
    const markRead = async () => {
        if (!lifecycle || lifecycle.markRead === false)
            return;
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
        }
        catch (error) {
            const action = errorAction({ kind: "mark_read", error });
            actions.push(action);
            lifecycle.logger?.warn?.(`[zoho-cliq] read lifecycle failed: ${action.errorKind ?? action.reason}`);
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
    }
    catch (error) {
        if (lifecycle.failureStatus !== null) {
            await addStatus(lifecycle.failureStatus ?? "failed");
        }
        throw new CliqInboundLifecycleDispatchError(error, result());
    }
}
