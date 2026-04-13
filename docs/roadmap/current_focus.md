# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` app-detail live classification is now archived**: focused `zoho cliq app-get` verification on happydistrouklimited keeps auth healthy and classifies app-detail endpoints as `not_supported`.
3. **Keep blocker-skipping active**: continue moving on testable Cliq work while app-account activation and extra live scopes remain external.

## Next
1. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
2. `cliq-193`: take the next smallest app-governance command/client slice with targeted tests.
3. `cliq-193`: run one focused live verification pass for that new slice and archive evidence.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
