# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` are blocked by API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-192` first code slice is in place**: `zoho cliq databases` + `ZohoCliqClient.list_databases` fallback routing landed with targeted tests; focused live verification is now the next execution step.
3. **Keep blocker-skipping loop active**: do not stall while waiting on admin-side activation.

## Next
1. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
2. `cliq-192`: run one focused live `cliq databases` verification pass and archive endpoint-behavior evidence.
3. `cliq-192`: take the next smallest platform-extension command/client slice (`widget` or `map tickers`) with targeted tests.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
