# WAITING ON

- Gmail gog OAuth may be unconfigured.
- Some historical mail-export file paths under `/Volumes/Happy Work Drive/...` may no longer exist.
- Cron prompt and workspace root may still need manual alignment in `jobs.json`.
- Cliq native local multipart sends (voice/image/file) still fail on tested user/channel targets with endpoint-level `request_url_invalid` / `operation_failed`; endpoint+field matrix evidence is still being collected for cliq-155 closure.
- Zoho token refresh can still throttle (`Access Denied` too many requests) during bursty live probe batches; retrieval probes need cooldown-safe reruns.
- Cliq maintenance export verification is blocked by API-side `inactive_appaccount_user` even after maintenance export scopes (`ZohoCliq.OrganizationChats.READ` + `ZohoCliq.OrganizationMessages.READ`) were granted; `cliq export-chats` list + `--chat-id` both hit this blocker.
- Latest focused Cliq status probe (`tests/auto_pilot/reports/cliq193_status_20260417_033228.json`) shows the test-config token is missing all Cliq scopes (`oauthReady: false`, `exportOauthReady: false`); one Cliq re-auth (`zoho login --with-cliq --with-cliq-export`) is required before next comparable live verification.
- Cliq app-governance app-command list verification (`cliq app-commands`) remains externally blocked on happydistrouklimited (latest focused run `tests/auto_pilot/reports/cliq193_app_commands_probe_summary_20260417_033228.json` shows `appCommandsError: empty_output`, with CLI returning `error: not_supported` to stderr).
