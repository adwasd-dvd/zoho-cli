# WAITING ON

- Gmail gog OAuth may be unconfigured.
- Some historical mail-export file paths under `/Volumes/Happy Work Drive/...` may no longer exist.
- Cron prompt and workspace root may still need manual alignment in `jobs.json`.
- Membrane bridge commands are now wired in CLI, but local runtime still needs Membrane CLI install (`npm install -g @membranehq/cli`) before live bridge execution.
- Cliq native local multipart sends (voice/image/file) still fail on tested user/channel targets with endpoint-level `request_url_invalid` / `operation_failed`; endpoint+field matrix evidence is still being collected for cliq-155 closure.
- Zoho token refresh can still throttle (`Access Denied` too many requests) during bursty live probe batches; retrieval probes need cooldown-safe reruns.
- Cliq maintenance export verification is blocked by API-side `inactive_appaccount_user` even after maintenance export scopes (`ZohoCliq.OrganizationChats.READ` + `ZohoCliq.OrganizationMessages.READ`) were granted; `cliq export-chats` list + `--chat-id` both hit this blocker.
- Latest focused Cliq status probe (`tests/auto_pilot/reports/cliq193_status_20260417_140826.json`) shows Cliq auth/export readiness remains healthy (`oauthReady: true`, `exportOauthReady: true`); no additional auth action is currently pending for comparable live verification.
- Cliq app-governance app-command list verification (`cliq app-commands`) remains externally blocked on happydistrouklimited (latest focused run `tests/auto_pilot/reports/cliq193_app_commands_probe_summary_20260417_140826.json` shows `appCommandsError: empty_output`, with CLI returning `error: not_supported` to stderr); this endpoint has crossed the 3-strike unsupported threshold and is now post-release deferred behind capability-gated isolation.
- Runtime/test guidance changed: default/global Zoho config is now the primary test config (no sandbox `/tmp/zoho-test-config.json` required). If config/auth failures surface, archive the exact error output and route to human-assisted config remediation.
