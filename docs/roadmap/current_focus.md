# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` are blocked by API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-192` second code slice is in place**: `zoho cliq widgets` and `ZohoCliqClient.list_widgets` are now implemented with fallback routing/tests; latest focused live databases evidence is still `oauth_scope_invalid` for `ZohoCliq.Databases.READ` while auth remains healthy (`oauthReady: true`, `exportOauthReady: true`) (`tests/auto_pilot/reports/cliq192_probe_summary_20260412_214538.json`).
3. **Keep blocker-skipping loop active**: do not stall while waiting on admin-side activation or additional live scopes.

## Next
1. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
2. `cliq-192`: take the next smallest platform-extension command/client slice (`map tickers`) with targeted tests.
3. `cliq-192`: rerun focused live verification for `cliq widgets` and archive endpoint behavior.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
