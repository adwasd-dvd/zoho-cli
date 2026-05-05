import { evaluateCliqEmployeePolicy, } from "./employee-policy.js";
export function normalizeCliqAllowEntry(raw) {
    return String(raw)
        .trim()
        .replace(/^user:/iu, "")
        .replace(/^@/u, "")
        .toLowerCase();
}
function normalizePolicy(value, fallback) {
    const normalized = value?.trim().toLowerCase();
    return normalized || fallback;
}
function formatAllowFrom(list) {
    return list.map(normalizeCliqAllowEntry).filter(Boolean);
}
function allowlistMatches(allowFrom, candidates) {
    const allowed = formatAllowFrom(allowFrom);
    if (allowed.includes("*"))
        return true;
    const normalizedCandidates = candidates
        .map((candidate) => candidate === undefined || candidate === null
        ? ""
        : normalizeCliqAllowEntry(candidate))
        .filter(Boolean);
    return normalizedCandidates.some((candidate) => allowed.includes(candidate));
}
export function resolveCliqGroupAllowFrom(account) {
    return account.groupAllowFrom.length > 0
        ? account.groupAllowFrom
        : account.allowFrom;
}
export function collectCliqSecurityWarnings(account) {
    const warnings = [];
    const dmPolicy = normalizePolicy(account.dmPolicy, "pairing");
    const groupPolicy = normalizePolicy(account.groupPolicy, "allowlist");
    const groupAllowFrom = resolveCliqGroupAllowFrom(account);
    if (dmPolicy === "open") {
        warnings.push("channels.cliq dmPolicy=open allows any Cliq user to DM the agent; prefer pairing or allowlist.");
    }
    if (groupPolicy === "open") {
        warnings.push("channels.cliq groupPolicy=open allows mention-gated group/channel intake without an allowlist.");
    }
    if (formatAllowFrom(account.allowFrom).includes("*")) {
        warnings.push("channels.cliq allowFrom includes '*'; every Cliq DM sender can reach the agent.");
    }
    if (formatAllowFrom(groupAllowFrom).includes("*")) {
        warnings.push("channels.cliq groupAllowFrom includes '*'; every group/channel sender can reach mention-gated intake.");
    }
    if (account.requireMention === false) {
        warnings.push("channels.cliq requireMention=false allows group/channel messages without an explicit bot mention.");
    }
    if (account.employeeMode.enabled === false) {
        warnings.push("channels.cliq employeeMode.enabled=false disables the scoped employee policy gate.");
    }
    return warnings;
}
export function collectCliqSecurityAuditFindings(account) {
    const warnings = collectCliqSecurityWarnings(account);
    const findings = warnings.map((warning, index) => ({
        checkId: `cliq-security-warning-${index + 1}`,
        severity: "warn",
        title: "Zoho Cliq unsafe access setting",
        detail: warning,
        remediation: "Use dmPolicy=pairing, groupPolicy=allowlist, requireMention=true, and scoped employee mode.",
    }));
    const scopeProfile = account.employeeMode.scopeProfile || "default";
    if (account.employeeMode.enabled !== false && !account.workScopes[scopeProfile]) {
        findings.push({
            checkId: "cliq-employee-scope-empty",
            severity: "critical",
            title: "Zoho Cliq employee scope is missing",
            detail: `employeeMode.scopeProfile=${scopeProfile} has no matching workScopes entry.`,
            remediation: `Add channels.cliq.accounts.${account.accountId}.workScopes.${scopeProfile}.`,
        });
    }
    return findings;
}
function deny(reasonCode, reason, audit, employee) {
    return {
        allowed: false,
        reasonCode,
        reason,
        audit,
        ...(employee ? { employee } : {}),
    };
}
export function evaluateCliqInboundSecurity(params) {
    void params.cfg;
    const account = params.account;
    const audit = [];
    if (params.chatKind === "direct") {
        const dmPolicy = normalizePolicy(account.dmPolicy, "pairing");
        if (dmPolicy === "disabled") {
            return deny("dm_disabled", "Zoho Cliq DM intake is disabled.", audit);
        }
        if (dmPolicy === "pairing") {
            if (!allowlistMatches(account.allowFrom, [params.senderId])) {
                return deny("dm_pairing_required", "Pair this Zoho Cliq user before dispatching DM requests.", audit);
            }
        }
        else if (dmPolicy === "allowlist") {
            if (!allowlistMatches(account.allowFrom, [params.senderId])) {
                return deny("dm_allowlist_denied", "This Zoho Cliq user is not in allowFrom.", audit);
            }
        }
        else if (dmPolicy === "open") {
            audit.push({
                code: "dm_open",
                severity: "warn",
                message: "DM request accepted under dmPolicy=open.",
            });
        }
    }
    else {
        const groupPolicy = normalizePolicy(account.groupPolicy, "allowlist");
        const groupAllowFrom = resolveCliqGroupAllowFrom(account);
        if (groupPolicy === "disabled") {
            return deny("group_disabled", "Zoho Cliq group/channel intake is disabled.", audit);
        }
        if (groupPolicy === "allowlist") {
            if (!allowlistMatches(groupAllowFrom, [
                params.senderId,
                params.conversationId,
            ])) {
                return deny("group_allowlist_denied", "This Zoho Cliq sender or conversation is not in groupAllowFrom.", audit);
            }
        }
        else if (groupPolicy === "open") {
            audit.push({
                code: "group_open",
                severity: "warn",
                message: "Group/channel request accepted under groupPolicy=open.",
            });
        }
        if (account.requireMention && !params.mentioned) {
            return deny("mention_required", "Mention the configured Zoho Cliq bot before dispatch.", audit);
        }
    }
    const employee = evaluateCliqEmployeePolicy({
        account,
        text: params.text,
        intent: params.intent,
        surface: "cliq",
        senderId: params.senderId,
    });
    if (!employee.allowed) {
        return deny(employee.auditCode, employee.reason, audit, employee);
    }
    audit.push({
        code: employee.auditCode,
        severity: employee.requiresReview ? "warn" : "info",
        message: employee.reason,
    });
    return {
        allowed: true,
        audit,
        employee,
    };
}
