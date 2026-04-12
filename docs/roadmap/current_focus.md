# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-192` code slices are in place with fallback hardening**: platform-extension reads now cover `databases`, `widgets`, `map-tickers`, `custom-domains`, and `custom-emails`; latest hardening also probes singular admin endpoints for custom domains/emails (`/admin/customdomain`, `/admin/customemail`) with targeted regression coverage.
3. **Keep blocker-skipping active**: continue moving on testable Cliq work while app-account activation and extra live scopes remain external.

## Next
1. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
2. `cliq-192`: run one focused live platform-extension verification bundle (`cliq databases/widgets/map-tickers/custom-domains/custom-emails`) and archive endpoint behavior.
3. `cliq-193`: start the next smallest app-governance command/client slice with targeted tests.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
