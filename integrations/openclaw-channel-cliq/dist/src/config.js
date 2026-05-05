import { CLIQ_CHANNEL_ID, DEFAULT_ACCOUNT_ID, DEFAULT_CLIQ_WEBHOOK_PATH, DEFAULT_ZOHO_CLI, } from "./constants.js";
export const DEFAULT_CLIQ_EMPLOYEE_MODE = {
    enabled: true,
    scopeProfile: "default",
    policy: "strict",
    allowDebugFromChannel: false,
    allowInstallFromChannel: false,
    allowConfigWritesFromChannel: false,
    adminAllowFrom: [],
    allowedIntents: [
        "cliq.reply",
        "cliq.status",
        "mail.triage",
        "mail.reply",
        "mail.send_with_review",
        "external_send",
    ],
    deniedIntents: [
        "system.debug",
        "system.install",
        "system.config_write",
        "system.exec",
        "secrets.read",
        "policy.bypass",
    ],
};
export const DEFAULT_CLIQ_WORK_SCOPES = {
    default: {
        role: "employee",
        allowedSurfaces: ["cliq", "mail"],
        crm: "read_only",
        requiresReviewFor: [
            "mail.send_with_review",
            "external_send",
            "delete",
            "system.install",
            "system.config_write",
        ],
    },
};
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
const stringListSchema = {
    type: "array",
    items: {
        type: "string",
        minLength: 1,
    },
};
const employeeModeSchema = {
    type: "object",
    additionalProperties: false,
    properties: {
        enabled: {
            type: "boolean",
        },
        scopeProfile: {
            type: "string",
            minLength: 1,
        },
        policy: {
            type: "string",
            enum: ["strict", "review"],
        },
        allowDebugFromChannel: {
            type: "boolean",
        },
        allowInstallFromChannel: {
            type: "boolean",
        },
        allowConfigWritesFromChannel: {
            type: "boolean",
        },
        adminAllowFrom: {
            $ref: "#/definitions/allowFrom",
        },
        allowedIntents: stringListSchema,
        deniedIntents: stringListSchema,
    },
};
const workScopeSchema = {
    type: "object",
    additionalProperties: false,
    properties: {
        role: {
            type: "string",
            minLength: 1,
        },
        allowedSurfaces: stringListSchema,
        crm: {
            type: "string",
            enum: ["none", "read_only", "read_write"],
        },
        requiresReviewFor: stringListSchema,
        allowedIntents: stringListSchema,
        deniedIntents: stringListSchema,
    },
};
const workScopesSchema = {
    type: "object",
    additionalProperties: {
        $ref: "#/definitions/workScope",
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
        webhookPath: {
            type: "string",
            minLength: 1,
        },
        dmPolicy: {
            type: "string",
            enum: ["allowlist", "pairing", "open", "disabled"],
        },
        groupPolicy: {
            type: "string",
            enum: ["allowlist", "open", "disabled"],
        },
        groupAllowFrom: allowFromSchema,
        allowFrom: allowFromSchema,
        requireMention: {
            type: "boolean",
        },
        employeeMode: {
            $ref: "#/definitions/employeeMode",
        },
        workScopes: {
            $ref: "#/definitions/workScopes",
        },
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
            webhookPath: {
                type: "string",
                minLength: 1,
            },
            dmPolicy: {
                type: "string",
                enum: ["allowlist", "pairing", "open", "disabled"],
            },
            groupPolicy: {
                type: "string",
                enum: ["allowlist", "open", "disabled"],
            },
            groupAllowFrom: allowFromSchema,
            allowFrom: allowFromSchema,
            requireMention: {
                type: "boolean",
            },
            employeeMode: {
                $ref: "#/definitions/employeeMode",
            },
            workScopes: {
                $ref: "#/definitions/workScopes",
            },
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
            employeeMode: employeeModeSchema,
            workScope: workScopeSchema,
            workScopes: workScopesSchema,
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
        webhookPath: {
            label: "Webhook path",
            help: "OpenClaw plugin HTTP route used by Zoho Cliq Bot handlers.",
            advanced: true,
        },
        allowFrom: {
            label: "Allowed Cliq senders",
            help: "Zoho Cliq user ids allowed to DM this channel or complete pairing.",
        },
        groupAllowFrom: {
            label: "Allowed Cliq group senders",
            help: "Zoho Cliq user/channel ids allowed to trigger group/channel intake.",
            advanced: true,
        },
        groupPolicy: {
            label: "Group policy",
            help: "Default is allowlist; open mode emits a security warning.",
            advanced: true,
        },
        requireMention: {
            label: "Require mention",
            help: "Require an explicit bot mention in group/channel conversations.",
        },
        employeeMode: {
            label: "Scoped employee mode",
            help: "Blocks chat-originated debug, install, config-write, secret-read, shell/system, and policy-bypass requests.",
            advanced: true,
        },
        workScopes: {
            label: "Employee work scopes",
            help: "Defines the business surfaces and review requirements available from Cliq.",
            advanced: true,
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
        section.webhookPath ||
        section.dmPolicy ||
        section.groupPolicy ||
        section.defaultTo ||
        section.requireMention !== undefined ||
        section.employeeMode ||
        section.workScopes ||
        (Array.isArray(section.groupAllowFrom) && section.groupAllowFrom.length > 0) ||
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
function mergeWorkScopes(...configs) {
    const merged = {};
    for (const config of configs) {
        for (const [profile, scope] of Object.entries(config ?? {})) {
            merged[profile] = {
                ...(merged[profile] ?? {}),
                ...scope,
            };
        }
    }
    return merged;
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
        webhookPath: entry.webhookPath || section.webhookPath || DEFAULT_CLIQ_WEBHOOK_PATH,
        dmPolicy: entry.dmPolicy ||
            entry.dmSecurity ||
            section.dmPolicy ||
            section.dmSecurity ||
            "pairing",
        groupPolicy: entry.groupPolicy || section.groupPolicy || "allowlist",
        groupAllowFrom: Array.isArray(entry.groupAllowFrom)
            ? entry.groupAllowFrom
            : Array.isArray(section.groupAllowFrom)
                ? section.groupAllowFrom
                : [],
        allowFrom: Array.isArray(entry.allowFrom)
            ? entry.allowFrom
            : Array.isArray(section.allowFrom)
                ? section.allowFrom
                : [],
        requireMention: entry.requireMention ?? section.requireMention ?? true,
        employeeMode: {
            ...DEFAULT_CLIQ_EMPLOYEE_MODE,
            ...(section.employeeMode ?? {}),
            ...(entry.employeeMode ?? {}),
        },
        workScopes: mergeWorkScopes(DEFAULT_CLIQ_WORK_SCOPES, section.workScopes, entry.workScopes),
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
        account.webhookPath !== DEFAULT_CLIQ_WEBHOOK_PATH ||
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
        webhookPath: account.webhookPath,
        credentialSource: inputSource(account.accountEmail) || inputSource(account.configPath),
        dmPolicy: account.dmPolicy,
        allowFrom: account.allowFrom.map(String),
        audit: {
            groupPolicy: account.groupPolicy,
            groupAllowFrom: account.groupAllowFrom.map(String),
            requireMention: account.requireMention,
            employeeMode: {
                enabled: account.employeeMode.enabled,
                scopeProfile: account.employeeMode.scopeProfile,
                policy: account.employeeMode.policy,
            },
        },
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
        webhookPath: params.input.webhookPath ??
            accounts[params.accountId]?.webhookPath ??
            DEFAULT_CLIQ_WEBHOOK_PATH,
        defaultTo: params.input.audience ?? accounts[params.accountId]?.defaultTo,
        dmPolicy: accounts[params.accountId]?.dmPolicy ?? "pairing",
        groupPolicy: accounts[params.accountId]?.groupPolicy ?? "allowlist",
        requireMention: accounts[params.accountId]?.requireMention ?? true,
        employeeMode: accounts[params.accountId]?.employeeMode ?? {
            ...DEFAULT_CLIQ_EMPLOYEE_MODE,
        },
        workScopes: accounts[params.accountId]?.workScopes ?? {
            ...DEFAULT_CLIQ_WORK_SCOPES,
        },
        allowFrom: params.input.dmAllowlist ?? accounts[params.accountId]?.allowFrom ?? [],
        groupAllowFrom: params.input.groupChannels ?? accounts[params.accountId]?.groupAllowFrom ?? [],
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
