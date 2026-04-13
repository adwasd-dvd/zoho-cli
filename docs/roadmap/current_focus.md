# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` output-shape hardening remains active while app-account activation is blocked**: app-governance list commands (`cliq apps`, `cliq app-permissions`, `cliq app-installs`, `cliq app-commands`) accept singleton dict payloads in nested `data` and top-level response objects, and app-governance detail commands (`cliq app-permission-get`, `cliq app-install-get`, `cliq app-command-get`) now accept top-level plural wrapper dict payloads (`permissions`/`installs`/`commands`). Latest focused regression slice is green (12 passed).
3. **Keep blocker-skipping active**: continue moving on testable Cliq app-governance slices while app-account activation remains external.

## Next
1. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
2. `cliq-193`: take the next smallest app-governance command/client slice with focused tests.
3. `cliq-193`: run one focused live verification pass for that new slice and archive evidence.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
