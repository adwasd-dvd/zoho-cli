const DANGEROUS_INTENT_PATTERNS = [
    {
        intent: "secrets.read",
        pattern: /\b(secret|token|password|api[-_\s]?key|private\s+key|webhook\s+secret)\b|密钥|令牌|密码/u,
    },
    {
        intent: "system.exec",
        pattern: /\b(shell|terminal|bash|zsh|exec|sudo|rm\s+-rf|curl\s+|wget\s+|chmod|chown)\b|执行命令|运行命令|终端/u,
    },
    {
        intent: "system.install",
        pattern: /\b(install|upgrade|npm\s+install|pip\s+install|plugin\s+install|host\s+upgrade)\b|安装插件|升级/u,
    },
    {
        intent: "system.config_write",
        pattern: /\b(config|configuration|settings|secretref)\b.{0,40}\b(write|change|edit|set|update)\b|修改配置|写配置/u,
    },
    {
        intent: "system.debug",
        pattern: /\b(debug|trace|stack|logs?|diagnostic|dump)\b|调试|内部日志/u,
    },
    {
        intent: "policy.bypass",
        pattern: /\b(ignore\s+previous|system\s+prompt|developer\s+message|jailbreak|bypass|override\s+policy)\b|越权|绕过策略/u,
    },
    {
        intent: "delete",
        pattern: /\b(delete|destroy|remove permanently|purge)\b|删除|销毁/u,
    },
];
function normalizeIntent(value) {
    if (!value)
        return "unknown";
    const known = [
        "cliq.reply",
        "cliq.status",
        "mail.triage",
        "mail.reply",
        "mail.send_with_review",
        "external_send",
        "delete",
        "system.debug",
        "system.install",
        "system.config_write",
        "system.exec",
        "secrets.read",
        "policy.bypass",
    ];
    return known.includes(value)
        ? value
        : "unknown";
}
export function classifyCliqEmployeeIntent(params) {
    const explicit = normalizeIntent(params.intent);
    if (explicit !== "unknown")
        return explicit;
    const text = params.text?.trim();
    if (!text)
        return "unknown";
    for (const candidate of DANGEROUS_INTENT_PATTERNS) {
        if (candidate.pattern.test(text))
            return candidate.intent;
    }
    return "cliq.reply";
}
function normalizeList(value) {
    return (value ?? []).map((entry) => entry.trim()).filter(Boolean);
}
function normalizeEntry(raw) {
    return String(raw)
        .trim()
        .replace(/^user:/iu, "")
        .replace(/^@/u, "")
        .toLowerCase();
}
function listIncludesEntry(list, raw) {
    if (!raw)
        return false;
    const normalized = normalizeEntry(raw);
    return (list ?? []).some((entry) => normalizeEntry(entry) === normalized);
}
function intentNeedsAdminOverride(intent) {
    return (intent === "system.debug" ||
        intent === "system.install" ||
        intent === "system.config_write" ||
        intent === "system.exec" ||
        intent === "secrets.read" ||
        intent === "policy.bypass");
}
function accountAllowsDangerousIntent(account, intent) {
    const mode = account.employeeMode;
    if (intent === "system.debug")
        return mode.allowDebugFromChannel === true;
    if (intent === "system.install")
        return mode.allowInstallFromChannel === true;
    if (intent === "system.config_write") {
        return mode.allowConfigWritesFromChannel === true;
    }
    return false;
}
export function evaluateCliqEmployeePolicy(params) {
    const account = params.account;
    const mode = account.employeeMode;
    const intent = classifyCliqEmployeeIntent({
        text: params.text,
        intent: params.intent,
    });
    if (mode.enabled === false) {
        return {
            allowed: false,
            intent,
            reason: "Scoped employee mode is disabled for this Cliq account.",
            auditCode: "employee_mode_disabled",
        };
    }
    const scopeProfile = mode.scopeProfile || "default";
    const scope = account.workScopes[scopeProfile];
    if (!scope) {
        return {
            allowed: false,
            intent,
            scopeProfile,
            reason: `Scoped employee mode needs workScopes.${scopeProfile}.`,
            auditCode: "employee_scope_empty",
        };
    }
    const surface = params.surface || "cliq";
    const allowedSurfaces = normalizeList(scope.allowedSurfaces);
    if (allowedSurfaces.length > 0 && !allowedSurfaces.includes(surface)) {
        return {
            allowed: false,
            intent,
            scopeProfile,
            reason: `The ${surface} surface is outside this employee work scope.`,
            auditCode: "employee_surface_denied",
        };
    }
    const deniedIntents = new Set([
        ...normalizeList(mode.deniedIntents),
        ...normalizeList(scope.deniedIntents),
    ]);
    if (deniedIntents.has(intent) || intentNeedsAdminOverride(intent)) {
        const hasAdminOverride = accountAllowsDangerousIntent(account, intent) &&
            listIncludesEntry(mode.adminAllowFrom, params.senderId);
        if (!hasAdminOverride) {
            return {
                allowed: false,
                intent,
                scopeProfile,
                reason: "This chat-originated request is outside the Cliq employee work scope.",
                auditCode: intentNeedsAdminOverride(intent)
                    ? "employee_admin_override_denied"
                    : "employee_intent_denied",
            };
        }
    }
    const allowedIntents = normalizeList(scope.allowedIntents).length
        ? normalizeList(scope.allowedIntents)
        : normalizeList(mode.allowedIntents);
    if (allowedIntents.length > 0 &&
        intent !== "unknown" &&
        !allowedIntents.includes(intent)) {
        return {
            allowed: false,
            intent,
            scopeProfile,
            reason: `Intent ${intent} is outside this employee work scope.`,
            auditCode: "employee_intent_denied",
        };
    }
    if (intent === "unknown") {
        return {
            allowed: false,
            intent,
            scopeProfile,
            reason: "The request needs a recognized in-scope business intent.",
            auditCode: "employee_intent_unknown",
        };
    }
    const reviewRequired = new Set(normalizeList(scope.requiresReviewFor));
    const requiresReview = reviewRequired.has(intent);
    return {
        allowed: true,
        intent,
        requiresReview,
        scopeProfile,
        reason: requiresReview
            ? `Intent ${intent} requires OpenClaw review.`
            : `Intent ${intent} is inside the Cliq employee work scope.`,
        auditCode: requiresReview ? "employee_review_required" : "employee_allow",
    };
}
