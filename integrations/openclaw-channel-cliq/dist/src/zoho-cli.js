export class ZohoCliqCommandError extends Error {
    command;
    exitCode;
    stderr;
    constructor(params) {
        super(`zoho-cli command failed with exit code ${params.exitCode ?? "unknown"}: ${params.command.join(" ")}`);
        this.name = "ZohoCliqCommandError";
        this.command = params.command;
        this.exitCode = params.exitCode;
        this.stderr = redactCliqDiagnostics(params.stderr);
    }
}
function redactCliqDiagnostics(raw) {
    return raw
        .replace(/(ZOHO_TOKEN_PASSWORD=)[^\s]+/g, "$1<redacted>")
        .replace(/(ZOHO_CLIQ_WEBHOOK_SECRET=)[^\s]+/g, "$1<redacted>")
        .replace(/(access_token["']?\s*[:=]\s*["']?)[^"',\s]+/gi, "$1<redacted>");
}
function networkArgs(account) {
    return account.network ? ["--network", account.network] : [];
}
export async function runZohoCliqJson(_account, args) {
    throw new ZohoCliqCommandError({
        command: ["zoho", "cliq", ...args],
        exitCode: null,
        stderr: redactCliqDiagnostics("zoho-cli process execution is implemented in cliq-channel-404."),
    });
}
export function buildCliqSendArgs(params) {
    const target = params.to.trim();
    const args = ["send", "--text", params.text, ...networkArgs(params.account)];
    if (target.startsWith("channel:")) {
        return [...args, "--channel-id", target.slice("channel:".length)];
    }
    if (target.startsWith("user:")) {
        return [...args, "--user-id", target.slice("user:".length)];
    }
    if (target.startsWith("@")) {
        return [...args, "--user-id", target.slice(1)];
    }
    return [...args, "--channel-id", target];
}
export async function sendCliqText(params) {
    await runZohoCliqJson(params.account, buildCliqSendArgs(params));
    return {};
}
