# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` permission payload-envelope hardening is now in**: `cliq app-permissions` and `cliq app-permission-get` now unwrap deeper wrapper stacks (`payload` + nested `response`/`result`/`data.records.record.item`) by extending permission-row unwrap depth; focused tests are green.
3. **Next smallest step**: run one focused live rerun for that permission payload hardening (`cliq status --check-auth` + `cliq app-permission-get ...`) and archive evidence.

## Next
1. `cliq-193`: run one focused live rerun for the permission payload-envelope hardening increment and archive artifacts.
2. `cliq-193`: take the next small app-governance output-hardening increment with focused tests.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
