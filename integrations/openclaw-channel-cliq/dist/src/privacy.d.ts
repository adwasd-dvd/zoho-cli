export declare const CLIQ_REDACTED = "[redacted]";
export type CliqPrivacyRetentionPolicy = {
    rawMessageBodies: "never_in_diagnostics";
    rawWebhookPayloads: "transient_request_only";
    webhookSecrets: "secretref_or_env_only";
    tokenPasswords: "secretref_or_env_only";
    diagnosticBundleRetention: "operator_managed_short_lived";
    turnLedgerRetention: {
        storage: "in_memory_by_default";
        containsRawBodies: false;
        boundedEntries: number;
        replayRequiresOperatorAction: true;
    };
    deadLetterRetention: {
        containsRawBodies: false;
        replayDefault: "blocked";
        replayGuidance: string;
    };
    localDiagnosticBundle: {
        includes: string[];
        excludes: string[];
    };
};
export declare function isCliqSensitiveDiagnosticKey(key: string): boolean;
export declare function redactCliqDiagnosticValue(value: unknown, key?: string): unknown;
export declare function redactCliqDiagnosticObject(value: Record<string, unknown>): Record<string, unknown>;
export declare function resolveCliqPrivacyRetentionPolicy(params?: {
    turnLedgerMaxEntries?: number;
}): CliqPrivacyRetentionPolicy;
