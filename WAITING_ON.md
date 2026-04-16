# WAITING ON

- Gmail gog OAuth may be unconfigured.
- Some historical mail-export file paths under `/Volumes/Happy Work Drive/...` may no longer exist.
- Cron prompt and workspace root may still need manual alignment in `jobs.json`.
- CRM live verification remains blocked until a CRM-enabled org account is available.
- Cliq native local multipart sends (voice/image/file) still fail on tested user/channel targets with endpoint-level `request_url_invalid` / `operation_failed`; endpoint+field matrix evidence is still being collected for cliq-155 closure.
- Zoho token refresh can still throttle (`Access Denied` too many requests) during bursty live probe batches; retrieval probes need cooldown-safe reruns.
- Cliq maintenance export verification is blocked by API-side `inactive_appaccount_user` even after maintenance export scopes (`ZohoCliq.OrganizationChats.READ` + `ZohoCliq.OrganizationMessages.READ`) were granted; `cliq export-chats` list + `--chat-id` both hit this blocker.
- Cliq app-governance app-command list verification (`cliq app-commands`) remains externally blocked on happydistrouklimited (latest focused run `tests/auto_pilot/reports/cliq193_app_commands_probe_summary_20260416_131927.json` shows `appCommandsError: empty_output`, with CLI returning `error: not_supported` to stderr).
