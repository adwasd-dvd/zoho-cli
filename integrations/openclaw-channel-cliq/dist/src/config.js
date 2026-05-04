import { CLIQ_CHANNEL_ID, DEFAULT_ACCOUNT_ID, DEFAULT_ZOHO_CLI, } from "./constants.js";
const secretRefSchema = {
    type: "object",
    additionalProperties: false,
    required: ["source", "provider", "id"],
    properties: {
        source: {
            type: "string",
            enum: ["env", "file", "exec"],
        },
        provider: {
            type: "string",
            minLength: 1,
        },
        id: {
            type: "string",
            minLength: 1,
        },
    },
};
const configValueSchema = {
    anyOf: [
        {
            type: "string",
            minLength: 1,
        },
        {
            $ref: "#/definitions/secretRef",
        },
    ],
};
const secretOnlySchema = {
    $ref: "#/definitions/secretRef",
};
const allowFromSchema = {
    type: "array",
    items: {
        anyOf: [
            {
                type: "string",
                minLength: 1,
            },
            {
                type: "number",
            },
        ],
    },
};
const accountSchema = {
    type: "object",
    additionalProperties: false,
    properties: {
        name: {
            type: "string",
            minLength: 1,
        },
        enabled: {
            type: "boolean",
        },
        accountEmail: configValueSchema,
        configPath: configValueSchema,
        network: {
            type: "string",
            minLength: 1,
        },
        cliPath: {
            type: "string",
            minLength: 1,
        },
        tokenPassword: secretOnlySchema,
        webhookSecret: secretOnlySchema,
        dmPolicy: {
            type: "string",
            enum: ["allowlist", "pairing", "open", "disabled"],
        },
        allowFrom: allowFromSchema,
        defaultTo: {
            type: "string",
            minLength: 1,
        },
    },
};
export const cliqChannelConfigSchema = {
    schema: {
        type: "object",
        additionalProperties: false,
        properties: {
            enabled: {
                type: "boolean",
            },
            defaultAccount: {
                type: "string",
                minLength: 1,
            },
            name: {
                type: "string",
                minLength: 1,
            },
            accountEmail: configValueSchema,
            configPath: configValueSchema,
            network: {
                type: "string",
                minLength: 1,
            },
            cliPath: {
                type: "string",
                minLength: 1,
            },
            tokenPassword: secretOnlySchema,
            webhookSecret: secretOnlySchema,
            dmPolicy: {
                type: "string",
                enum: ["allowlist", "pairing", "open", "disabled"],
            },
            allowFrom: allowFromSchema,
            defaultTo: {
                type: "string",
                minLength: 1,
            },
            accounts: {
                type: "object",
                additionalProperties: {
                    $ref: "#/definitions/account",
                },
            },
        },
        definitions: {
            secretRef: secretRefSchema,
            account: accountSchema,
        },
    },
    uiHints: {
        accountEmail: {
            label: "Zoho account",
            help: "Zoho account email or a SecretRef/env reference to ZOHO_ACCOUNT.",
        },
        configPath: {
            label: "Zoho config path",
            help: "zoho-cli config path or a SecretRef/env reference to ZOHO_CONFIG.",
            advanced: true,
        },
        tokenPassword: {
            label: "Token password",
            help: "SecretRef/env reference to ZOHO_TOKEN_PASSWORD.",
            sensitive: true,
        },
        webhookSecret: {
            label: "Webhook secret",
            help: "SecretRef/env reference to ZOHO_CLIQ_WEBHOOK_SECRET.",
            sensitive: true,
        },
        allowFrom: {
            label: "Allowed Cliq senders",
            help: "Zoho Cliq user ids allowed to talk to this channel.",
        },
        accounts: {
            label: "Cliq accounts",
            advanced: true,
        },
    },
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
        section.configPath ||
        section.network ||
        section.cliPath ||
        section.tokenPassword ||
        section.webhookSecret ||
        section.dmPolicy ||
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
        configPath: entry.configPath,
        network: entry.network,
        cliPath: entry.cliPath || section.cliPath || DEFAULT_ZOHO_CLI,
        tokenPassword: entry.tokenPassword,
        webhookSecret: entry.webhookSecret,
        dmPolicy: entry.dmPolicy ||
            entry.dmSecurity ||
            section.dmPolicy ||
            section.dmSecurity,
        allowFrom: Array.isArray(entry.allowFrom)
            ? entry.allowFrom
            : Array.isArray(section.allowFrom)
                ? section.allowFrom
                : [],
        defaultTo: entry.defaultTo || section.defaultTo,
    };
}
export function envSecretRef(id) {
    return {
        source: "env",
        provider: "default",
        id,
    };
}
function isSecretRefLike(value) {
    if (!isRecord(value))
        return false;
    return ((value.source === "env" ||
        value.source === "file" ||
        value.source === "exec") &&
        typeof value.provider === "string" &&
        value.provider.length > 0 &&
        typeof value.id === "string" &&
        value.id.length > 0);
}
function hasConfiguredInput(value) {
    if (typeof value === "string")
        return value.trim().length > 0;
    return isSecretRefLike(value);
}
function inputSource(value) {
    if (typeof value === "string" && value.trim().length > 0)
        return "inline";
    if (!isSecretRefLike(value))
        return undefined;
    return `${value.source}:${value.id}`;
}
function configValuePreview(value) {
    if (typeof value === "string" && value.trim().length > 0)
        return value;
    if (!isSecretRefLike(value))
        return undefined;
    return `${value.source}:${value.id}`;
}
export function isCliqAccountConfigured(account) {
    return Boolean(hasConfiguredInput(account.accountEmail) ||
        hasConfiguredInput(account.configPath) ||
        account.network ||
        hasConfiguredInput(account.tokenPassword) ||
        hasConfiguredInput(account.webhookSecret) ||
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
        tokenStatus: hasConfiguredInput(account.tokenPassword)
            ? "configured"
            : "env-or-cli",
        tokenSource: inputSource(account.tokenPassword),
        signingSecretStatus: hasConfiguredInput(account.webhookSecret)
            ? "configured"
            : "optional",
        signingSecretSource: inputSource(account.webhookSecret),
        credentialSource: inputSource(account.accountEmail) || inputSource(account.configPath),
        dmPolicy: account.dmPolicy,
        allowFrom: account.allowFrom.map(String),
        cliPath: account.cliPath,
        probe: {
            accountEmail: configValuePreview(account.accountEmail),
            configPath: configValuePreview(account.configPath),
            network: account.network,
        },
    };
}
export function hasCliqConfiguredState(params) {
    const cfg = params?.cfg;
    const env = params?.env ?? process.env;
    if (env.ZOHO_ACCOUNT ||
        env.ZOHO_CONFIG ||
        env.ZOHO_TOKEN_PASSWORD ||
        env.ZOHO_CLIQ_WEBHOOK_SECRET) {
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
        return Boolean(hasConfiguredInput(account.tokenPassword) ||
            hasConfiguredInput(account.accountEmail) ||
            hasConfiguredInput(account.configPath));
    });
}
export function patchCliqAccountConfig(params) {
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
        ...params.patch,
    };
    section.accounts = accounts;
    section.defaultAccount = section.defaultAccount ?? params.accountId;
    next.channels[CLIQ_CHANNEL_ID] = section;
    return next;
}
export function setCliqAccountEnabled(params) {
    return patchCliqAccountConfig({
        cfg: params.cfg,
        accountId: params.accountId,
        patch: { enabled: params.enabled },
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
        configPath: params.input.tokenFile ??
            params.input.authDir ??
            accounts[params.accountId]?.configPath,
        network: params.input.region ?? accounts[params.accountId]?.network,
        tokenPassword: params.input.useEnv
            ? envSecretRef("ZOHO_TOKEN_PASSWORD")
            : accounts[params.accountId]?.tokenPassword,
        webhookSecret: params.input.useEnv
            ? envSecretRef("ZOHO_CLIQ_WEBHOOK_SECRET")
            : accounts[params.accountId]?.webhookSecret,
        defaultTo: params.input.audience ?? accounts[params.accountId]?.defaultTo,
        dmPolicy: accounts[params.accountId]?.dmPolicy ?? "allowlist",
        allowFrom: params.input.dmAllowlist ?? accounts[params.accountId]?.allowFrom ?? [],
        enabled: true,
    };
    section.accounts = accounts;
    section.defaultAccount = section.defaultAccount ?? params.accountId;
    next.channels[CLIQ_CHANNEL_ID] = section;
    return next;
}
export function validateCliqSetupInput(params) {
    const input = params.input;
    if (input.token ||
        input.accessToken ||
        input.password ||
        input.privateKey ||
        input.secret ||
        input.botToken ||
        input.appToken) {
        return "Zoho Cliq setup must use zoho-cli auth or SecretRef/env references, not plaintext token input.";
    }
    return null;
}
