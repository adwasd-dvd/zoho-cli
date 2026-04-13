# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` remains active with a new unit hardening slice**: `cliq app-get` now unwraps top-level `app` list rows that still carry nested singular `app` wrappers; focused unit coverage is in place and the next step is a focused live verification pass.
3. **Keep blocker-skipping active**: continue moving on testable Cliq app-governance hardening slices while app-account activation remains external.

## Next
1. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
2. `cliq-193`: run one focused live verification pass for the latest `cliq app-get` wrapper-row hardening slice and archive evidence.
3. `cliq-193`: take the next smallest app-governance output-hardening slice with focused unit coverage.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
