# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` output-shape hardening is now in**: `zoho cliq apps` and `zoho cliq app-get` now normalize nested app list wrappers (`data.apps`, `apps`, `list`, `items`, `results`) so app-governance reads do not silently collapse to empty/default output.
3. **Keep blocker-skipping active**: continue moving on testable Cliq work while app-account activation and extra live scopes remain external.

## Next
1. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
2. `cliq-193`: run one focused live verification pass for the new output-shape hardening (`cliq status --check-auth` + `cliq apps` + `cliq app-get`) and archive evidence.
3. `cliq-193`: take the next smallest app-governance command/client slice with targeted tests.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
