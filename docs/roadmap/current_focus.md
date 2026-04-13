# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` app-command envelope hardening just landed**: `cliq app-commands` + `cliq app-command-get` now unwrap top-level `response`/`result` envelopes (including nested `data.records.record.item`) with focused unit coverage.
3. **Next focused verification is queued**: run `cliq status --check-auth` + `cliq app-command-get` once to archive fresh live evidence for the new hardening slice.

## Next
1. `cliq-193`: run the focused live rerun for the app-command envelope hardening slice and archive artifacts.
2. `cliq-193`: ship the next smallest app-governance output-hardening increment with focused tests.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
