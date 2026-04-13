# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` output-shape hardening remains active while app-account activation is blocked**: app-governance list commands (`cliq apps`, `cliq app-permissions`, `cliq app-installs`, `cliq app-commands`) now accept singleton dict payloads in both nested `data` objects and top-level response objects; detail commands continue to accept list-wrapped `data` payloads. Latest focused regression slice is green (8 passed).
3. **Keep blocker-skipping active**: continue moving on testable Cliq app-governance slices while app-account activation remains external.

## Next
1. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
2. `cliq-193`: take the next smallest app-governance command/client slice with focused tests.
3. `cliq-193`: run one focused live verification pass for that new slice and archive evidence.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
