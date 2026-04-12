# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` are blocked by API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-192` focused live verification is now archived**: `zoho cliq databases --network happydistrouklimited --limit 10` currently returns `oauth_scope_invalid` with `ZohoCliq.Databases.READ` guidance, while `cliq status --check-auth` remains healthy (`oauthReady: true`, `exportOauthReady: true`) (`tests/auto_pilot/reports/cliq192_probe_summary_20260412_214538.json`).
3. **Keep blocker-skipping loop active**: do not stall while waiting on admin-side activation or additional live scopes.

## Next
1. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
2. `cliq-192`: take the next smallest platform-extension command/client slice (`widget` or `map tickers`) with targeted tests.
3. `cliq-192`: rerun focused live verification for the newly added slice and archive endpoint behavior.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
