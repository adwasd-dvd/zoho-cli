# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Latest `cliq-193` unit hardening is complete**: `cliq app-commands` + `cliq app-command-get` now accept camelCase command-name aliases (`commandName` / `actionName`) in list/detail payloads, so maintenance responses without snake_case aliases no longer fall back to `unknown` names.
3. **Next smallest step**: run one matching focused live rerun (`cliq status --check-auth` + `cliq app-command-get ...`) and archive evidence.

## Next
1. `cliq-193`: run one focused live rerun for the new command-name alias hardening and archive evidence.
2. `cliq-193`: take the next smallest output-hardening increment with focused tests.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
