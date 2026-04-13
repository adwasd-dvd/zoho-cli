# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **cliq-193 list output hardening advanced**: app-governance list extractors now unwrap `data.records.record.item` wrapper rows for `cliq apps`, `cliq app-permissions`, `cliq app-installs`, and `cliq app-commands`, with focused unit coverage green.
3. **Next step is a focused live verification pass** for this slice (`cliq status --check-auth` + `cliq apps --limit 10`), then the next smallest cliq-193 output-hardening increment.

## Next
1. `cliq-193`: run one focused live verification pass (`cliq status --check-auth` + `cliq apps --limit 10`) and archive evidence for the new `data.records.record.item` wrapper hardening.
2. `cliq-193`: ship the next smallest app-governance output-hardening increment with focused tests.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
