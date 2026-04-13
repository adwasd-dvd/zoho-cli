# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Focused `cliq-192` live platform-extension bundle is now archived**: on `happydistrouklimited`, auth is healthy (`oauthReady: true`, `exportOauthReady: true`), but results split by blocker type: `databases` + `custom-domains` return `oauth_scope_invalid` (need `ZohoCliq.Databases.READ` + `ZohoCliq.CustomDomains.READ`), while `widgets` + `map-tickers` + `custom-emails` return `not_supported`.
3. **Keep blocker-skipping active**: continue moving on testable Cliq work while app-account activation and extra live scopes remain external.

## Next
1. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
2. `cliq-192`: after additional scope grant, rerun focused checks for scope-gated endpoints (`cliq databases`, `cliq custom-domains`) and compare with existing bundle evidence.
3. `cliq-193`: start the next smallest app-governance command/client slice with targeted tests.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
