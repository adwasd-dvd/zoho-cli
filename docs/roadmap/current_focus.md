# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` list output hardening advanced**: `cliq app-permissions`, `cliq app-installs`, and `cliq app-commands` now unwrap list-row `item` wrappers in maintenance payloads, with focused tests green.
3. **Run one focused live verification for this new slice**: archive one `cliq status --check-auth` + one app-governance list command pass, then continue blocker-skipping output-hardening increments.

## Next
1. `cliq-193`: run one focused live verification pass for the latest list-row `item`-wrapper hardening slice and archive evidence.
2. `cliq-193`: ship the next smallest app-governance output-hardening increment with focused tests.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
