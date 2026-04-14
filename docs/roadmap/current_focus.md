# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Latest `cliq-193` unit hardening is complete**: `cliq app-commands` and `cliq app-command-get` now treat `command_name` / `action_name` as first-class command-name aliases so maintenance payloads without canonical `name` fields no longer degrade to `unknown`; focused tests are green.
3. **Next smallest step**: run one matching focused live rerun (`cliq status --check-auth` + `cliq app-command-get APP_PROBE_FAKE_<stamp> CMD_PROBE_FAKE_<stamp>`) and archive evidence, then continue the next smallest `cliq-193` output-hardening increment.

## Next
1. `cliq-193`: run one matching focused live rerun (`cliq status --check-auth` + `cliq app-command-get ...`) and archive evidence.
2. `cliq-193`: take the next smallest output-hardening increment with focused tests.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
