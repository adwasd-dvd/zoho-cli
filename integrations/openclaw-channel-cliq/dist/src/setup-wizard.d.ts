import type { OpenClawConfig } from "openclaw/plugin-sdk";
import type { ChannelSetupWizard } from "openclaw/plugin-sdk/setup";
export declare const CLIQ_SETUP_STATE_COPY: {
    readonly host_too_old: {
        readonly copy: "OpenClaw is too old for this plugin.";
        readonly nextAction: "Upgrade OpenClaw to >=2026.5.3-1.";
    };
    readonly zoho_missing: {
        readonly copy: "Zoho CLI was not found.";
        readonly nextAction: "Install zoho-cli and make sure the zoho command is on PATH.";
    };
    readonly not_logged_in: {
        readonly copy: "Zoho login is required.";
        readonly nextAction: "Run zoho login --with-cliq, then retry setup.";
    };
    readonly missing_scope: {
        readonly copy: "Cliq permissions are incomplete.";
        readonly nextAction: "Re-auth with Cliq scopes and run zoho cliq status --check-auth.";
    };
    readonly network_missing: {
        readonly copy: "Cliq network is not selected.";
        readonly nextAction: "Set channels.cliq.accounts.<id>.network.";
    };
    readonly webhook_unverified: {
        readonly copy: "Webhook delivery is not verified.";
        readonly nextAction: "Configure webhookSecret or choose the polling fallback slice later.";
    };
    readonly allowlist_empty: {
        readonly copy: "Group and DM allowlist is empty.";
        readonly nextAction: "Add trusted Zoho Cliq user ids to allowFrom.";
    };
};
export type CliqSetupStateCode = keyof typeof CLIQ_SETUP_STATE_COPY;
export declare function resolveCliqSetupStateCodes(params: {
    cfg: OpenClawConfig;
    accountId?: string;
    env?: NodeJS.ProcessEnv;
}): CliqSetupStateCode[];
export declare function resolveCliqSetupStatusLines(params: {
    cfg: OpenClawConfig;
    accountId?: string;
    configured: boolean;
}): string[];
export declare const cliqSetupWizard: ChannelSetupWizard;
