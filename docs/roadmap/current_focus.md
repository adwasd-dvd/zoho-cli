# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` third slice is now in code**: added `cliq app-permissions` plus `ZohoCliqClient.list_app_permissions` fallback routing (`/apps/{id}/permissions`, `/app/{id}/permissions`, `/admin/apps/{id}/permissions`, `/admin/app/{id}/permissions`) with focused tests.
3. **Keep blocker-skipping active**: continue moving on testable Cliq app-governance work while app-account activation and extra live scopes remain external.

## Next
1. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
2. `cliq-193`: run one focused live verification pass for `cliq app-permissions` (`cliq status --check-auth` + `cliq app-permissions <app-id>`) and archive evidence.
3. `cliq-193`: take the next smallest app-governance command/client slice with targeted tests.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
