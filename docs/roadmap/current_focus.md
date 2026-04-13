# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` app-installs code slice is now in place**: `zoho cliq app-installs` + `ZohoCliqClient.list_app_installs` fallback routing landed with targeted CLI/client tests; the immediate follow-up is one focused live verification pass for this new slice.
3. **Keep blocker-skipping active**: continue moving on testable Cliq app-governance slices while app-account activation remains external.

## Next
1. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
2. `cliq-193`: run one focused live verification pass for `cliq app-installs` and archive evidence.
3. `cliq-193`: take the next smallest app-governance command/client slice with targeted tests.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
