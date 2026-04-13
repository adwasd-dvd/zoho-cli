# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` app-get detail hardening advanced**: `zoho cliq app-get` now unwraps `data.records.record[]` rows carrying nested `item` wrappers (focused unit coverage green).
3. **Next step is one focused live verification pass for this slice** (`cliq status --check-auth` + `cliq app-get`), then continue the next smallest cliq-193 output-hardening increment.

## Next
1. `cliq-193`: run one focused live `cliq app-get` verification for the new `data.records.record[].item` hardening and archive evidence.
2. `cliq-193`: ship the next smallest app-governance output-hardening increment with focused tests.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
