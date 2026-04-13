# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` focused live app-get verification refreshed**: after the latest `data.records.record[].item` detail hardening, `cliq status --check-auth` still reports healthy auth (`oauthReady: true`, `exportOauthReady: true`) while `cliq app-get` remains endpoint-limited (`error: not_supported`) on happydistrouklimited.
3. **Next step is the next smallest cliq-193 output-hardening increment** with focused unit coverage, then one focused live verification rerun for that new slice.

## Next
1. `cliq-193`: ship the next smallest app-governance output-hardening increment with focused tests.
2. `cliq-193`: run one focused live verification pass for that new slice and archive evidence.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
