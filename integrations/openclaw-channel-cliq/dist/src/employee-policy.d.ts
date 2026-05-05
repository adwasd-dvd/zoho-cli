import type { CliqResolvedAccount } from "./config.js";
export type CliqEmployeeIntent = "cliq.reply" | "cliq.status" | "mail.triage" | "mail.reply" | "mail.send_with_review" | "external_send" | "delete" | "system.debug" | "system.install" | "system.config_write" | "system.exec" | "secrets.read" | "policy.bypass" | "unknown";
export type CliqEmployeePolicyDecision = {
    allowed: true;
    intent: CliqEmployeeIntent;
    requiresReview: boolean;
    scopeProfile: string;
    reason: string;
    auditCode: "employee_allow" | "employee_review_required";
} | {
    allowed: false;
    intent: CliqEmployeeIntent;
    scopeProfile?: string;
    reason: string;
    auditCode: "employee_mode_disabled" | "employee_scope_empty" | "employee_surface_denied" | "employee_intent_denied" | "employee_intent_unknown" | "employee_admin_override_denied";
};
export declare function classifyCliqEmployeeIntent(params: {
    text?: string | null;
    intent?: string | null;
}): CliqEmployeeIntent;
export declare function evaluateCliqEmployeePolicy(params: {
    account: CliqResolvedAccount;
    text?: string | null;
    intent?: string | null;
    surface?: string | null;
    senderId?: string | null;
}): CliqEmployeePolicyDecision;
