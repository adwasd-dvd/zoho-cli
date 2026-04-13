# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Latest `cliq-193` unit hardening is complete**: app-governance detail extraction now unwraps deeper `data.records.record[].item` nested wrappers for `cliq app-permission-get`, `cliq app-install-get`, and `cliq app-command-get` (focused tests green).
3. **Next step is one focused live verification rerun** for this slice, then continue the next smallest `cliq-193` output-hardening increment.

## Next
1. `cliq-193`: run one focused live pass (`cliq status --check-auth` + one app-governance detail command) and archive evidence.
2. `cliq-193`: ship the next smallest app-governance output-hardening increment with focused unit coverage.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
