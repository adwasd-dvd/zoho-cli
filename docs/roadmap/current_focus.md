# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Latest unit hardening increment is complete**: `cliq app-commands` + `cliq app-command-get` now also accept Pascal/camel action-id aliases (`ActionId` / `ActionID` / `actionID`) in addition to `actionId` / `action_id`, with focused tests green.
3. **Next smallest step**: run one focused live rerun (`cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_<stamp>`) and archive evidence.

## Next
1. `cliq-193`: run one matching focused live rerun (`cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_<stamp>`) and archive evidence.
2. `cliq-193`: implement the next smallest output-hardening increment with focused CLI unit tests.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
