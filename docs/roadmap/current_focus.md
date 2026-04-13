# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` has started**: first app-governance code slice is now in place (`zoho cliq apps` + `ZohoCliqClient.list_apps`) with targeted tests passing.
3. **Keep blocker-skipping active**: continue moving on testable Cliq work while app-account activation and extra live scopes remain external.

## Next
1. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
2. `cliq-193`: run one focused live `cliq apps --limit 10` verification pass and archive the first evidence bundle.
3. `cliq-193`: take the next smallest app-governance command/client slice with targeted tests.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
