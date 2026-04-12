# WAITING ON

- Gmail gog OAuth may be unconfigured.
- Some historical mail-export file paths under `/Volumes/Happy Work Drive/...` may no longer exist.
- Cron prompt and workspace root may still need manual alignment in `jobs.json`.
- CRM live verification remains blocked until a CRM-enabled org account is available.
- Cliq native local multipart sends (voice/image/file) still fail on tested user/channel targets with endpoint-level `request_url_invalid` / `operation_failed`; endpoint+field matrix evidence is still being collected for cliq-155 closure.
- Zoho token refresh can still throttle (`Access Denied` too many requests) during bursty live probe batches; retrieval probes need cooldown-safe reruns.
- Cliq maintenance export verification is now blocked by API-side `inactive_appaccount_user` even after maintenance export scopes (`ZohoCliq.OrganizationChats.READ` + `ZohoCliq.OrganizationMessages.READ`) were granted; `cliq export-chats` list + `--chat-id` both hit this blocker.
- Nightly broad verification (2026-04-12T14:19:04Z) is green (`make release-gate && make ci`, 321 tests), but this does not clear the live Cliq endpoint/scope blockers above.
