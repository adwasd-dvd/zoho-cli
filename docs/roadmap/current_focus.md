# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` output-shape hardening remains active while app-account activation is blocked**: app-governance list commands (`cliq apps`, `cliq app-permissions`, `cliq app-installs`, `cliq app-commands`) accept singleton dict payloads in nested `data` and top-level response objects and now unwrap top-level singular wrapper payloads (`app`/`permission`/`install`/`command`), app-governance detail commands (`cliq app-get`, `cliq app-permission-get`, `cliq app-install-get`, `cliq app-command-get`) accept top-level plural wrapper dict payloads plus list-row nested wrapper objects and now also unwrap top-level singular wrapper list payloads (`app`/`permission`/`install`/`command`), and command list/detail flows now unwrap nested singular `action` wrappers (`action`/`data.action`) so action labels populate command names. Latest focused regression slice is green (4 passed).
3. **Keep blocker-skipping active**: continue moving on testable Cliq app-governance slices while app-account activation remains external.

## Next
1. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
2. `cliq-193`: run one focused live verification pass (`cliq status --check-auth` + `cliq app-command-get`) to archive evidence after the `action` wrapper hardening.
3. `cliq-193`: take the next smallest app-governance command/client/output-hardening slice with focused tests.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
