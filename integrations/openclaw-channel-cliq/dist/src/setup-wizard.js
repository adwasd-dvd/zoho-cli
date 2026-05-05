import { defaultCliqAccountId, envSecretRef, isCliqAccountConfigured, patchCliqAccountConfig, resolveCliqAccount, setCliqAccountEnabled, } from "./config.js";
import { CLIQ_CHANNEL_ID, DEFAULT_ZOHO_CLI, OPENCLAW_PLUGIN_API_RANGE, } from "./constants.js";
export const CLIQ_SETUP_STATE_COPY = {
    host_too_old: {
        copy: "OpenClaw is too old for this plugin.",
        nextAction: `Upgrade OpenClaw to ${OPENCLAW_PLUGIN_API_RANGE}.`,
    },
    zoho_missing: {
        copy: "Zoho CLI was not found.",
        nextAction: "Install zoho-cli and make sure the zoho command is on PATH.",
    },
    not_logged_in: {
        copy: "Zoho login is required.",
        nextAction: "Run zoho login --with-cliq, then retry setup.",
    },
    missing_scope: {
        copy: "Cliq permissions are incomplete.",
        nextAction: "Re-auth with Cliq scopes and run zoho cliq status --check-auth.",
    },
    network_missing: {
        copy: "Cliq network is not selected.",
        nextAction: "Set channels.cliq.accounts.<id>.network.",
    },
    webhook_unverified: {
        copy: "Webhook delivery is not verified.",
        nextAction: "Configure webhookSecret or choose the polling fallback slice later.",
    },
    allowlist_empty: {
        copy: "Group and DM allowlist is empty.",
        nextAction: "Add trusted Zoho Cliq user ids to allowFrom.",
    },
    employee_scope_empty: {
        copy: "Scoped employee mode needs a work scope.",
        nextAction: "Set employeeMode.scopeProfile and matching workScopes entry.",
    },
};
function hasValue(value) {
    if (typeof value === "string")
        return value.trim().length > 0;
    return Boolean(value);
}
function displayConfigValue(value) {
    if (typeof value === "string")
        return value;
    if (value && typeof value === "object" && "source" in value && "id" in value) {
        const ref = value;
        return `${String(ref.source)}:${String(ref.id)}`;
    }
    return "not set";
}
function normalizeCliqDmPolicy(value) {
    return value === "pairing" ||
        value === "allowlist" ||
        value === "open" ||
        value === "disabled"
        ? value
        : "pairing";
}
function splitAllowFrom(raw) {
    return raw
        .split(/[\s,]+/u)
        .map((entry) => entry.trim())
        .filter(Boolean);
}
function normalizeAllowFromId(raw) {
    const value = raw.trim();
    if (!value)
        return null;
    if (value === "*")
        return value;
    if (value.startsWith("user:"))
        return value.slice("user:".length) || null;
    if (value.startsWith("@"))
        return value.slice(1) || null;
    return /^[A-Za-z0-9_.:@-]+$/u.test(value) ? value : null;
}
function describeAuthState(account) {
    if (hasValue(account.configPath)) {
        return `zoho config: ${displayConfigValue(account.configPath)}`;
    }
    if (hasValue(account.tokenPassword)) {
        return `token password: ${displayConfigValue(account.tokenPassword)}`;
    }
    return "zoho config: not set";
}
function hasEmployeeScope(account) {
    if (account.employeeMode.enabled === false)
        return true;
    const scopeProfile = account.employeeMode.scopeProfile || "default";
    return Boolean(account.workScopes[scopeProfile]);
}
export function resolveCliqSetupStateCodes(params) {
    const account = resolveCliqAccount(params.cfg, params.accountId);
    const env = params.env ?? process.env;
    const states = [];
    if (!hasValue(account.accountEmail) && !env.ZOHO_ACCOUNT) {
        states.push("not_logged_in");
    }
    if (!hasValue(account.configPath) && !env.ZOHO_CONFIG) {
        states.push("not_logged_in");
    }
    if (!account.network) {
        states.push("network_missing");
    }
    if (!hasValue(account.webhookSecret) && !env.ZOHO_CLIQ_WEBHOOK_SECRET) {
        states.push("webhook_unverified");
    }
    if (((normalizeCliqDmPolicy(account.dmPolicy) === "allowlist" &&
        account.allowFrom.length === 0) ||
        (account.groupPolicy === "allowlist" &&
            account.groupAllowFrom.length === 0 &&
            account.allowFrom.length === 0))) {
        states.push("allowlist_empty");
    }
    if (!hasEmployeeScope(account)) {
        states.push("employee_scope_empty");
    }
    return Array.from(new Set(states));
}
export function resolveCliqSetupStatusLines(params) {
    const account = resolveCliqAccount(params.cfg, params.accountId);
    const states = resolveCliqSetupStateCodes({
        cfg: params.cfg,
        accountId: params.accountId,
    });
    const lines = [
        `account: ${displayConfigValue(account.accountEmail)}`,
        `network: ${account.network || "not set"}`,
        `cli: ${account.cliPath || DEFAULT_ZOHO_CLI}`,
        `webhook: ${account.webhookPath}`,
        describeAuthState(account),
        `dm policy: ${normalizeCliqDmPolicy(account.dmPolicy)}`,
        `group policy: ${account.groupPolicy}`,
        `require mention: ${account.requireMention ? "yes" : "no"}`,
        `allowFrom: ${account.allowFrom.length}`,
        `groupAllowFrom: ${account.groupAllowFrom.length}`,
        `employee scope: ${account.employeeMode.scopeProfile || "default"}`,
        "inbound: polling + Bot webhook",
        "lifecycle: status/read diagnostics enabled",
        "turn ledger: duplicate/active/dead-letter protection enabled",
    ];
    if (states.length === 0 && params.configured) {
        return [
            ...lines,
            "auth_check: run zoho cliq status --check-auth before live use.",
            "send_check: controlled outbound smoke is available for a trusted target.",
            "bot_check: trusted Bot webhook smoke can validate receive/lifecycle/ledger.",
        ];
    }
    return [
        ...lines,
        ...states.map((state) => {
            const info = CLIQ_SETUP_STATE_COPY[state];
            return `${state}: ${info.nextAction}`;
        }),
    ];
}
function applyTextPatch(cfg, accountId, patch) {
    return patchCliqAccountConfig({
        cfg,
        accountId,
        patch: {
            ...patch,
            enabled: true,
        },
    });
}
export const cliqSetupWizard = {
    channel: CLIQ_CHANNEL_ID,
    status: {
        configuredLabel: "Zoho Cliq is configured.",
        unconfiguredLabel: "Zoho Cliq needs setup.",
        configuredHint: "Run zoho cliq status --check-auth before enabling live traffic.",
        unconfiguredHint: "Configure account, network, zoho-cli auth, webhook/polling choice, and allowlist.",
        configuredScore: 80,
        unconfiguredScore: 20,
        resolveConfigured: ({ cfg, accountId }) => isCliqAccountConfigured(resolveCliqAccount(cfg, accountId)),
        resolveStatusLines: resolveCliqSetupStatusLines,
        resolveSelectionHint: ({ configured }) => configured
            ? "Ready for controlled channel smoke; live verification is the remaining production gate."
            : "Run setup before selecting Zoho Cliq for agents.",
        resolveQuickstartScore: ({ cfg, accountId, configured }) => {
            const states = resolveCliqSetupStateCodes({ cfg, accountId });
            return configured && states.length === 0 ? 80 : 25;
        },
    },
    introNote: {
        title: "Zoho Cliq setup",
        lines: [
            "Use zoho-cli for OAuth and Zoho API compatibility.",
            "Use SecretRef/env values for token password and webhook secret.",
            "Do not paste OAuth tokens, bot tokens, app tokens, or private keys.",
            "Scoped employee mode blocks chat-originated debug, installs, config writes, shell/system requests, and secret reads.",
        ],
    },
    envShortcut: {
        prompt: "Use ZOHO_ACCOUNT, ZOHO_CONFIG, ZOHO_TOKEN_PASSWORD, and ZOHO_CLIQ_WEBHOOK_SECRET from the environment.",
        preferredEnvVar: "ZOHO_TOKEN_PASSWORD",
        isAvailable: () => Boolean(process.env.ZOHO_ACCOUNT ||
            process.env.ZOHO_CONFIG ||
            process.env.ZOHO_TOKEN_PASSWORD ||
            process.env.ZOHO_CLIQ_WEBHOOK_SECRET),
        apply: ({ cfg, accountId }) => patchCliqAccountConfig({
            cfg,
            accountId,
            patch: {
                accountEmail: envSecretRef("ZOHO_ACCOUNT"),
                configPath: envSecretRef("ZOHO_CONFIG"),
                tokenPassword: envSecretRef("ZOHO_TOKEN_PASSWORD"),
                webhookSecret: envSecretRef("ZOHO_CLIQ_WEBHOOK_SECRET"),
                enabled: true,
            },
        }),
    },
    resolveShouldPromptAccountIds: ({ cfg, shouldPromptAccountIds }) => shouldPromptAccountIds || defaultCliqAccountId(cfg) !== "default",
    stepOrder: "text-first",
    credentials: [],
    textInputs: [
        {
            inputKey: "name",
            message: "Account label",
            placeholder: "Zoho Cliq",
            currentValue: ({ cfg, accountId }) => resolveCliqAccount(cfg, accountId).name,
            applySet: ({ cfg, accountId, value }) => applyTextPatch(cfg, accountId, { name: value.trim() }),
        },
        {
            inputKey: "userId",
            message: "Zoho account email",
            placeholder: "bot@example.com",
            required: true,
            currentValue: ({ cfg, accountId }) => {
                const value = resolveCliqAccount(cfg, accountId).accountEmail;
                return typeof value === "string" ? value : undefined;
            },
            shouldPrompt: ({ currentValue }) => !currentValue,
            validate: ({ value }) => value.trim().includes("@") ? undefined : "Enter a Zoho account email.",
            normalizeValue: ({ value }) => value.trim(),
            applySet: ({ cfg, accountId, value }) => applyTextPatch(cfg, accountId, { accountEmail: value }),
        },
        {
            inputKey: "region",
            message: "Cliq network",
            placeholder: "happydistrouklimited",
            required: true,
            currentValue: ({ cfg, accountId }) => resolveCliqAccount(cfg, accountId).network,
            shouldPrompt: ({ currentValue }) => !currentValue,
            validate: ({ value }) => value.trim().length > 0 ? undefined : "Enter a Cliq network.",
            normalizeValue: ({ value }) => value.trim(),
            applySet: ({ cfg, accountId, value }) => applyTextPatch(cfg, accountId, { network: value }),
        },
        {
            inputKey: "cliPath",
            message: "zoho command path",
            placeholder: "zoho",
            currentValue: ({ cfg, accountId }) => resolveCliqAccount(cfg, accountId).cliPath || DEFAULT_ZOHO_CLI,
            normalizeValue: ({ value }) => value.trim() || DEFAULT_ZOHO_CLI,
            applySet: ({ cfg, accountId, value }) => applyTextPatch(cfg, accountId, { cliPath: value }),
        },
        {
            inputKey: "tokenFile",
            message: "zoho-cli config path",
            placeholder: "/secrets/zoho-config.json",
            currentValue: ({ cfg, accountId }) => {
                const value = resolveCliqAccount(cfg, accountId).configPath;
                return typeof value === "string" ? value : undefined;
            },
            helpTitle: "Zoho config",
            helpLines: [
                "Leave empty when ZOHO_CONFIG is provided by SecretRef/env.",
                "Run zoho login --with-cliq once before non-interactive use.",
            ],
            normalizeValue: ({ value }) => value.trim(),
            applySet: ({ cfg, accountId, value }) => applyTextPatch(cfg, accountId, { configPath: value }),
        },
        {
            inputKey: "audience",
            message: "Default outbound target",
            placeholder: "channel:<id> or user:<id>",
            currentValue: ({ cfg, accountId }) => resolveCliqAccount(cfg, accountId).defaultTo,
            normalizeValue: ({ value }) => value.trim(),
            applySet: ({ cfg, accountId, value }) => applyTextPatch(cfg, accountId, { defaultTo: value }),
        },
    ],
    dmPolicy: {
        label: "Zoho Cliq DM access",
        channel: CLIQ_CHANNEL_ID,
        policyKey: "dmPolicy",
        allowFromKey: "allowFrom",
        resolveConfigKeys: (_cfg, accountId = "default") => ({
            policyKey: `channels.cliq.accounts.${accountId}.dmPolicy`,
            allowFromKey: `channels.cliq.accounts.${accountId}.allowFrom`,
        }),
        getCurrent: (cfg, accountId) => normalizeCliqDmPolicy(resolveCliqAccount(cfg, accountId).dmPolicy),
        setPolicy: (cfg, policy, accountId = "default") => patchCliqAccountConfig({
            cfg,
            accountId,
            patch: {
                dmPolicy: policy,
                enabled: true,
            },
        }),
    },
    allowFrom: {
        helpTitle: "Allowed Zoho Cliq senders",
        helpLines: [
            "Use Zoho Cliq user ids for people allowed to talk to the agent.",
            "Keep this list narrow; group/channel intake also uses groupAllowFrom.",
        ],
        message: "Allowed Cliq user ids",
        placeholder: "123456789, user:987654321",
        invalidWithoutCredentialNote: "Add at least one trusted Cliq user id before live testing.",
        parseInputs: splitAllowFrom,
        parseId: normalizeAllowFromId,
        resolveEntries: async ({ entries }) => entries.map((entry) => {
            const id = normalizeAllowFromId(entry);
            return {
                input: entry,
                resolved: Boolean(id),
                id,
            };
        }),
        apply: ({ cfg, accountId, allowFrom }) => patchCliqAccountConfig({
            cfg,
            accountId,
            patch: {
                allowFrom,
                groupAllowFrom: allowFrom,
                dmPolicy: "allowlist",
                groupPolicy: "allowlist",
                enabled: true,
            },
        }),
    },
    completionNote: {
        title: "Before live use",
        lines: [
            "Run zoho cliq status --check-auth --network <network>.",
            "Run controlled webhook, polling, lifecycle, native dispatch, and redacted diagnostics smokes before production.",
            "Keep webhook secrets and token passwords in SecretRef/env values.",
            "Keep dmPolicy=pairing and groupPolicy=allowlist unless an operator accepts the audit warning.",
        ],
    },
    disable: (cfg) => {
        const accountId = defaultCliqAccountId(cfg);
        return setCliqAccountEnabled({
            cfg,
            accountId,
            enabled: false,
        });
    },
};
