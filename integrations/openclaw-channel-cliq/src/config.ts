import type {
  ChannelAccountSnapshot,
  ChannelConfigSchema,
  ChannelSetupInput,
  OpenClawConfig,
} from "openclaw/plugin-sdk";
import type { SecretInput } from "openclaw/plugin-sdk/secret-ref-runtime";

import {
  CLIQ_CHANNEL_ID,
  DEFAULT_ACCOUNT_ID,
  DEFAULT_ZOHO_CLI,
} from "./constants.js";

export type CliqAccountConfig = {
  name?: string;
  enabled?: boolean;
  accountEmail?: string;
  network?: string;
  cliPath?: string;
  tokenPassword?: SecretInput;
  webhookSecret?: SecretInput;
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
  accountEmail?: string;
  network?: string;
  cliPath: string;
  tokenPassword?: SecretInput;
  webhookSecret?: SecretInput;
  dmPolicy?: string;
  allowFrom: Array<string | number>;
  defaultTo?: string;
};

export const cliqChannelConfigSchema: ChannelConfigSchema = {
  schema: {
    type: "object",
    additionalProperties: false,
    properties: {},
  },
  uiHints: {},
};

type ConfigWithChannels = OpenClawConfig & {
  channels?: Record<string, unknown>;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function readCliqSection(cfg: OpenClawConfig): CliqChannelConfig {
  const channels = (cfg as ConfigWithChannels).channels;
  const raw = channels?.[CLIQ_CHANNEL_ID];
  return isRecord(raw) ? (raw as CliqChannelConfig) : {};
}

function readAccounts(section: CliqChannelConfig): Record<string, CliqAccountConfig> {
  return isRecord(section.accounts)
    ? (section.accounts as Record<string, CliqAccountConfig>)
    : {};
}

function hasTopLevelAccount(section: CliqChannelConfig): boolean {
  return Boolean(
    section.enabled ||
      section.accountEmail ||
      section.network ||
      section.cliPath ||
      section.tokenPassword ||
      section.webhookSecret ||
      section.defaultTo ||
      (Array.isArray(section.allowFrom) && section.allowFrom.length > 0),
  );
}

function mergeAccount(
  section: CliqChannelConfig,
  accountId: string,
): CliqAccountConfig {
  const accounts = readAccounts(section);
  const { accounts: _accounts, ...topLevel } = section;
  void _accounts;
  return {
    ...topLevel,
    ...accounts[accountId],
  };
}

export function listCliqAccountIds(cfg: OpenClawConfig): string[] {
  const section = readCliqSection(cfg);
  const ids = Object.keys(readAccounts(section));
  if (ids.length > 0) return ids;
  return hasTopLevelAccount(section) ? [DEFAULT_ACCOUNT_ID] : [];
}

export function defaultCliqAccountId(cfg: OpenClawConfig): string {
  const section = readCliqSection(cfg);
  if (section.defaultAccount) return section.defaultAccount;
  return listCliqAccountIds(cfg)[0] ?? DEFAULT_ACCOUNT_ID;
}

export function resolveCliqAccount(
  cfg: OpenClawConfig,
  accountId?: string | null,
): CliqResolvedAccount {
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

export function isCliqAccountConfigured(account: CliqResolvedAccount): boolean {
  return Boolean(
    account.accountEmail ||
      account.network ||
      account.tokenPassword ||
      account.webhookSecret ||
      account.defaultTo,
  );
}

export function describeCliqAccount(
  account: CliqResolvedAccount,
): ChannelAccountSnapshot {
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

export function hasCliqConfiguredState(params?: {
  cfg?: OpenClawConfig;
  env?: NodeJS.ProcessEnv;
}): boolean {
  const cfg = params?.cfg;
  const env = params?.env ?? process.env;
  if (env.ZOHO_ACCOUNT || env.ZOHO_CONFIG || env.ZOHO_TOKEN_PASSWORD) {
    return true;
  }
  return cfg ? listCliqAccountIds(cfg).length > 0 : false;
}

export function hasCliqAuthState(params?: {
  cfg?: OpenClawConfig;
  env?: NodeJS.ProcessEnv;
}): boolean {
  const cfg = params?.cfg;
  const env = params?.env ?? process.env;
  if (env.ZOHO_TOKEN_PASSWORD || env.ZOHO_CONFIG) return true;
  if (!cfg) return false;
  return listCliqAccountIds(cfg).some((accountId) => {
    const account = resolveCliqAccount(cfg, accountId);
    return Boolean(account.tokenPassword || account.accountEmail);
  });
}

export function applyCliqAccountConfig(params: {
  cfg: OpenClawConfig;
  accountId: string;
  input: ChannelSetupInput;
}): OpenClawConfig {
  const next = { ...(params.cfg as ConfigWithChannels) } as ConfigWithChannels;
  next.channels = { ...(next.channels ?? {}) };
  const section = {
    ...(isRecord(next.channels[CLIQ_CHANNEL_ID])
      ? (next.channels[CLIQ_CHANNEL_ID] as Record<string, unknown>)
      : {}),
  } as CliqChannelConfig;
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
  return next as OpenClawConfig;
}

export function validateCliqSetupInput(params: {
  input: ChannelSetupInput;
}): string | null {
  const input = params.input;
  if (input.token || input.accessToken || input.password) {
    return "Zoho Cliq setup must use zoho-cli auth or SecretRef/env references, not plaintext token input.";
  }
  return null;
}
