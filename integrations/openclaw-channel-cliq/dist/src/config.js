import { CLIQ_CHANNEL_ID, DEFAULT_ACCOUNT_ID, DEFAULT_ZOHO_CLI, } from "./constants.js";
export const cliqChannelConfigSchema = {
    schema: {
        type: "object",
        additionalProperties: false,
        properties: {},
    },
    uiHints: {},
};
function isRecord(value) {
    return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
function readCliqSection(cfg) {
    const channels = cfg.channels;
    const raw = channels?.[CLIQ_CHANNEL_ID];
    return isRecord(raw) ? raw : {};
}
function readAccounts(section) {
    return isRecord(section.accounts)
        ? section.accounts
        : {};
}
function hasTopLevelAccount(section) {
    return Boolean(section.enabled ||
        section.accountEmail ||
        section.network ||
        section.cliPath ||
        section.tokenPassword ||
        section.webhookSecret ||
        section.defaultTo ||
        (Array.isArray(section.allowFrom) && section.allowFrom.length > 0));
}
function mergeAccount(section, accountId) {
    const accounts = readAccounts(section);
    const { accounts: _accounts, ...topLevel } = section;
    void _accounts;
    return {
        ...topLevel,
        ...accounts[accountId],
    };
}
export function listCliqAccountIds(cfg) {
    const section = readCliqSection(cfg);
    const ids = Object.keys(readAccounts(section));
    if (ids.length > 0)
        return ids;
    return hasTopLevelAccount(section) ? [DEFAULT_ACCOUNT_ID] : [];
}
export function defaultCliqAccountId(cfg) {
    const section = readCliqSection(cfg);
    if (section.defaultAccount)
        return section.defaultAccount;
    return listCliqAccountIds(cfg)[0] ?? DEFAULT_ACCOUNT_ID;
}
export function resolveCliqAccount(cfg, accountId) {
    const section = readCliqSection(cfg);
    const resolvedAccountId = accountId || defaultCliqAccountId(cfg);
    const entry = mergeAccount(section, resolvedAccountId);
    return {
        accountId: resolvedAccountId,
        name: entry.name,
        enabled: entry.enabled ?? section.enabled ?? true,
        accountEmail: entry.accountEmail,
        network: entry.network,
        cliPath: entry.cliPath || section.cliPath || DEFAULT_ZOHO_CLI,
        tokenPassword: entry.tokenPassword,
        webhookSecret: entry.webhookSecret,
        dmPolicy: entry.dmSecurity || section.dmSecurity,
        allowFrom: Array.isArray(entry.allowFrom)
            ? entry.allowFrom
            : Array.isArray(section.allowFrom)
                ? section.allowFrom
                : [],
        defaultTo: entry.defaultTo || section.defaultTo,
    };
}
export function isCliqAccountConfigured(account) {
    return Boolean(account.accountEmail ||
        account.network ||
        account.tokenPassword ||
        account.webhookSecret ||
        account.defaultTo);
}
export function describeCliqAccount(account) {
    const configured = isCliqAccountConfigured(account);
    return {
        accountId: account.accountId,
        name: account.name,
        enabled: account.enabled,
        configured,
        linked: configured,
        tokenStatus: account.tokenPassword ? "configured" : "env-or-cli",
        signingSecretStatus: account.webhookSecret ? "configured" : "optional",
        dmPolicy: account.dmPolicy,
        allowFrom: account.allowFrom.map(String),
        cliPath: account.cliPath,
        probe: {
            network: account.network,
        },
    };
}
export function hasCliqConfiguredState(params) {
    const cfg = params?.cfg;
    const env = params?.env ?? process.env;
    if (env.ZOHO_ACCOUNT || env.ZOHO_CONFIG || env.ZOHO_TOKEN_PASSWORD) {
        return true;
    }
    return cfg ? listCliqAccountIds(cfg).length > 0 : false;
}
export function hasCliqAuthState(params) {
    const cfg = params?.cfg;
    const env = params?.env ?? process.env;
    if (env.ZOHO_TOKEN_PASSWORD || env.ZOHO_CONFIG)
        return true;
    if (!cfg)
        return false;
    return listCliqAccountIds(cfg).some((accountId) => {
        const account = resolveCliqAccount(cfg, accountId);
        return Boolean(account.tokenPassword || account.accountEmail);
    });
}
export function applyCliqAccountConfig(params) {
    const next = { ...params.cfg };
    next.channels = { ...(next.channels ?? {}) };
    const section = {
        ...(isRecord(next.channels[CLIQ_CHANNEL_ID])
            ? next.channels[CLIQ_CHANNEL_ID]
            : {}),
    };
    const accounts = { ...readAccounts(section) };
    accounts[params.accountId] = {
        ...(accounts[params.accountId] ?? {}),
        name: params.input.name ?? accounts[params.accountId]?.name,
        cliPath: params.input.cliPath ?? accounts[params.accountId]?.cliPath,
        accountEmail: params.input.userId ?? accounts[params.accountId]?.accountEmail,
        network: params.input.region ?? accounts[params.accountId]?.network,
        enabled: true,
    };
    section.accounts = accounts;
    section.defaultAccount = section.defaultAccount ?? params.accountId;
    next.channels[CLIQ_CHANNEL_ID] = section;
    return next;
}
export function validateCliqSetupInput(params) {
    const input = params.input;
    if (input.token || input.accessToken || input.password) {
        return "Zoho Cliq setup must use zoho-cli auth or SecretRef/env references, not plaintext token input.";
    }
    return null;
}
