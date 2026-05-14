import type { ChannelAccountSnapshot, ChannelConfigSchema, ChannelSetupInput, OpenClawConfig } from "openclaw/plugin-sdk";
import type { SecretInput, SecretRef } from "openclaw/plugin-sdk/secret-ref-runtime";
import { CLIQ_CHANNEL_ID } from "./constants.js";
export type CliqConfigValueInput = string | SecretRef;
export type CliqAccountConfig = {
    name?: string;
    enabled?: boolean;
    accountEmail?: CliqConfigValueInput;
    configPath?: CliqConfigValueInput;
    network?: string;
    cliPath?: string;
    tokenPassword?: SecretInput;
    webhookSecret?: SecretInput;
    webhookPath?: string;
    dmPolicy?: string;
    dmSecurity?: string;
    groupPolicy?: string;
    groupAllowFrom?: Array<string | number>;
    allowFrom?: Array<string | number>;
    requireMention?: boolean;
    employeeMode?: CliqEmployeeModeConfig;
    workScopes?: CliqWorkScopesConfig;
    defaultTo?: string;
};
export type CliqChannelConfig = CliqAccountConfig & {
    defaultAccount?: string;
    accounts?: Record<string, CliqAccountConfig>;
};
export type CliqEmployeeModeConfig = {
    enabled?: boolean;
    scopeProfile?: string;
    policy?: "strict" | "review";
    allowDebugFromChannel?: boolean;
    allowInstallFromChannel?: boolean;
    allowConfigWritesFromChannel?: boolean;
    adminAllowFrom?: Array<string | number>;
    allowedIntents?: string[];
    deniedIntents?: string[];
};
export type CliqWorkScopeConfig = {
    role?: string;
    allowedSurfaces?: string[];
    crm?: "none" | "read_only" | "read_write";
    requiresReviewFor?: string[];
    allowedIntents?: string[];
    deniedIntents?: string[];
};
export type CliqWorkScopesConfig = Record<string, CliqWorkScopeConfig>;
export type CliqResolvedAccount = {
    accountId: string;
    name?: string;
    enabled: boolean;
    accountEmail?: CliqConfigValueInput;
    configPath?: CliqConfigValueInput;
    network?: string;
    cliPath: string;
    tokenPassword?: SecretInput;
    webhookSecret?: SecretInput;
    webhookPath: string;
    dmPolicy?: string;
    groupPolicy: string;
    groupAllowFrom: Array<string | number>;
    allowFrom: Array<string | number>;
    requireMention: boolean;
    employeeMode: CliqEmployeeModeConfig;
    workScopes: CliqWorkScopesConfig;
    defaultTo?: string;
};
export declare const DEFAULT_CLIQ_EMPLOYEE_MODE: Required<Pick<CliqEmployeeModeConfig, "enabled" | "scopeProfile" | "policy" | "allowDebugFromChannel" | "allowInstallFromChannel" | "allowConfigWritesFromChannel">> & Pick<CliqEmployeeModeConfig, "adminAllowFrom" | "allowedIntents" | "deniedIntents">;
export declare const DEFAULT_CLIQ_WORK_SCOPES: CliqWorkScopesConfig;
export declare const cliqChannelConfigSchema: ChannelConfigSchema;
export type CliqAgentBindingDiagnostic = {
    channel: typeof CLIQ_CHANNEL_ID;
    accountId: string;
    configured: boolean;
    agentId?: string;
    matchedBy?: "account_binding" | "channel_binding";
    bindingScope?: "account" | "channel";
    configurationPath: "bindings[]";
    nextAction?: "add_openclaw_agent_binding";
};
export declare function listCliqAccountIds(cfg: OpenClawConfig): string[];
export declare function defaultCliqAccountId(cfg: OpenClawConfig): string;
export declare function resolveCliqAccount(cfg: OpenClawConfig, accountId?: string | null): CliqResolvedAccount;
export declare function describeCliqAgentBinding(cfg: OpenClawConfig, accountId?: string | null): CliqAgentBindingDiagnostic;
export declare function envSecretRef(id: string): SecretRef;
export declare function isCliqAccountConfigured(account: CliqResolvedAccount): boolean;
export declare function describeCliqCapabilityDiagnostics(account: CliqResolvedAccount): {
    outboundText: boolean;
    outboundReply: boolean;
    outboundThreadReply: boolean;
    inboundPolling: boolean;
    inboundWebhook: boolean;
    webhookConfigured: boolean;
    statusLifecycle: boolean;
    readAckLifecycle: boolean;
    turnLedger: boolean;
    scopedEmployeeMode: boolean;
    nativeApprovalCapability: boolean;
    nativeAgentDispatch: boolean;
    observabilityBundle: boolean;
    redactedAuditEvents: boolean;
    rateLimitDiagnostics: boolean;
    privacyRetention: boolean;
    deadLetterReplayGuard: boolean;
    npmIntegrityPlaceholder: boolean;
};
export declare function describeCliqAccountDiagnostics(account: CliqResolvedAccount, cfg?: OpenClawConfig): {
    readiness: string;
    productionReadiness: string;
    webhookPath: string;
    defaultTarget: string | undefined;
    agentBinding: CliqAgentBindingDiagnostic | undefined;
    capabilities: {
        outboundText: boolean;
        outboundReply: boolean;
        outboundThreadReply: boolean;
        inboundPolling: boolean;
        inboundWebhook: boolean;
        webhookConfigured: boolean;
        statusLifecycle: boolean;
        readAckLifecycle: boolean;
        turnLedger: boolean;
        scopedEmployeeMode: boolean;
        nativeApprovalCapability: boolean;
        nativeAgentDispatch: boolean;
        observabilityBundle: boolean;
        redactedAuditEvents: boolean;
        rateLimitDiagnostics: boolean;
        privacyRetention: boolean;
        deadLetterReplayGuard: boolean;
        npmIntegrityPlaceholder: boolean;
    };
    blockers: string[];
    observability: {
        redactedAuditEvents: boolean;
        correlationIds: boolean;
        diagnosticBundle: boolean;
        rateLimitDiagnostics: boolean;
        privacyRetention: boolean;
        deadLetterReplayGuard: boolean;
        npmIntegrityPlaceholder: boolean;
        rateLimits: {
            webhook: {
                windowMs: number;
                maxRequests: number;
                maxInFlightPerKey: number;
                maxTrackedKeys: number;
                key: string;
                bodyMaxBytes: number;
                bodyTimeoutMs: number;
                rejectionStage: string;
            };
            polling: {
                defaultChatLimit: number;
                defaultContextLimit: number;
                dedupe: string;
                selfAuthoredMessagesSkipped: boolean;
            };
            lifecycle: {
                statusReadAckFailures: string;
                recursiveDispatchOnLifecycleFailure: boolean;
            };
            nativeDispatch: {
                emptyOrReasoningPayloadsSkipped: boolean;
                missingOutboundAdapterError: string;
            };
        };
        privacy: import("./privacy.js").CliqPrivacyRetentionPolicy;
        releaseIntegrity: {
            npmExpectedIntegrity: string;
            localLinkedDevelopmentAllowed: boolean;
            releaseChecklist: string[];
        };
    };
    smokeChecks: string[];
    implementedSlices: string[];
    nextSlice: string;
};
export declare function describeCliqAccount(account: CliqResolvedAccount): ChannelAccountSnapshot;
export declare function hasCliqConfiguredState(params?: {
    cfg?: OpenClawConfig;
    env?: NodeJS.ProcessEnv;
}): boolean;
export declare function hasCliqAuthState(params?: {
    cfg?: OpenClawConfig;
    env?: NodeJS.ProcessEnv;
}): boolean;
export declare function patchCliqAccountConfig(params: {
    cfg: OpenClawConfig;
    accountId: string;
    patch: CliqAccountConfig;
}): OpenClawConfig;
export declare function setCliqAccountEnabled(params: {
    cfg: OpenClawConfig;
    accountId: string;
    enabled: boolean;
}): OpenClawConfig;
export declare function applyCliqAccountConfig(params: {
    cfg: OpenClawConfig;
    accountId: string;
    input: ChannelSetupInput;
}): OpenClawConfig;
export declare function validateCliqSetupInput(params: {
    input: ChannelSetupInput;
}): string | null;
