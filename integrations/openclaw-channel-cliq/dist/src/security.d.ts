import type { OpenClawConfig } from "openclaw/plugin-sdk";
import type { CliqResolvedAccount } from "./config.js";
import { type CliqEmployeePolicyDecision } from "./employee-policy.js";
export type CliqChatKind = "direct" | "group" | "channel" | "thread";
export type CliqAuditSeverity = "info" | "warn" | "critical";
export type CliqSecurityAuditEvent = {
    code: string;
    severity: CliqAuditSeverity;
    message: string;
};
export type CliqInboundSecurityDecision = {
    allowed: true;
    audit: CliqSecurityAuditEvent[];
    employee: CliqEmployeePolicyDecision;
} | {
    allowed: false;
    reasonCode: "dm_disabled" | "dm_pairing_required" | "dm_allowlist_denied" | "group_disabled" | "group_allowlist_denied" | "mention_required" | CliqEmployeePolicyDecision["auditCode"];
    reason: string;
    audit: CliqSecurityAuditEvent[];
    employee?: CliqEmployeePolicyDecision;
};
export declare function normalizeCliqAllowEntry(raw: string | number): string;
export declare function resolveCliqGroupAllowFrom(account: CliqResolvedAccount): Array<string | number>;
export declare function collectCliqSecurityWarnings(account: CliqResolvedAccount): string[];
export declare function collectCliqSecurityAuditFindings(account: CliqResolvedAccount): Array<{
    checkId: string;
    severity: "info" | "warn" | "critical";
    title: string;
    detail: string;
    remediation?: string;
}>;
export declare function evaluateCliqInboundSecurity(params: {
    cfg?: OpenClawConfig;
    account: CliqResolvedAccount;
    chatKind: CliqChatKind;
    senderId?: string | null;
    conversationId?: string | null;
    text?: string | null;
    intent?: string | null;
    mentioned: boolean;
}): CliqInboundSecurityDecision;
