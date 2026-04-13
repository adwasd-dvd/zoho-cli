# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` detail output hardening advanced again**: `cliq app-permission-get`, `cliq app-install-get`, and `cliq app-command-get` now recursively unwrap nested top-level wrapper list rows (for example `[{permission:{permission:{...}}}]`) so maintenance-style wrapper rows do not degrade detail output.
3. **Keep blocker-skipping active**: continue shipping/testable Cliq app-governance hardening slices while app-account activation remains external.

## Next
1. `cliq-193`: run one focused live verification pass for the new nested wrapper-row detail hardening (`cliq status --check-auth` + one detail command) and archive evidence.
2. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
3. `cliq-193`: take the next smallest app-governance output-hardening slice with focused tests.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
