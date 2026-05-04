import type { CliqResolvedAccount } from "./config.js";
export type ZohoCliJsonResult<T = unknown> = {
    command: string[];
    stdout: T;
    stderr: string;
};
export declare class ZohoCliqCommandError extends Error {
    readonly command: string[];
    readonly exitCode: number | null;
    readonly stderr: string;
    constructor(params: {
        command: string[];
        exitCode: number | null;
        stderr: string;
    });
}
export declare function runZohoCliqJson<T = unknown>(_account: CliqResolvedAccount, args: string[]): Promise<ZohoCliJsonResult<T>>;
export declare function buildCliqSendArgs(params: {
    account: CliqResolvedAccount;
    to: string;
    text: string;
}): string[];
export declare function sendCliqText(params: {
    account: CliqResolvedAccount;
    to: string;
    text: string;
}): Promise<{
    messageId?: string;
}>;
