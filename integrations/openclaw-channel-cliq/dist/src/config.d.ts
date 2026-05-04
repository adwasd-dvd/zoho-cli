import type { ChannelAccountSnapshot, ChannelConfigSchema, ChannelSetupInput, OpenClawConfig } from "openclaw/plugin-sdk";
import type { SecretInput, SecretRef } from "openclaw/plugin-sdk/secret-ref-runtime";
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
    dmPolicy?: string;
    dmSecurity?: string;
    allowFrom?: Array<string | number>;
    defaultTo?: string;
};
export type CliqChannelConfig = CliqAccountConfig & {
    defaultAccount?: string;
    accounts?: Record<string, CliqAccountConfig>;
};
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
    dmPolicy?: string;
    allowFrom: Array<string | number>;
    defaultTo?: string;
};
export declare const cliqChannelConfigSchema: ChannelConfigSchema;
export declare function listCliqAccountIds(cfg: OpenClawConfig): string[];
export declare function defaultCliqAccountId(cfg: OpenClawConfig): string;
export declare function resolveCliqAccount(cfg: OpenClawConfig, accountId?: string | null): CliqResolvedAccount;
export declare function envSecretRef(id: string): SecretRef;
export declare function isCliqAccountConfigured(account: CliqResolvedAccount): boolean;
export declare function describeCliqAccount(account: CliqResolvedAccount): ChannelAccountSnapshot;
export declare function hasCliqConfiguredState(params?: {
    cfg?: OpenClawConfig;
    env?: NodeJS.ProcessEnv;
}): boolean;
export declare function hasCliqAuthState(params?: {
    cfg?: OpenClawConfig;
    env?: NodeJS.ProcessEnv;
}): boolean;
export declare function applyCliqAccountConfig(params: {
    cfg: OpenClawConfig;
    accountId: string;
    input: ChannelSetupInput;
}): OpenClawConfig;
export declare function validateCliqSetupInput(params: {
    input: ChannelSetupInput;
}): string | null;
