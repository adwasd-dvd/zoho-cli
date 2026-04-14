# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Latest focused `cliq-193` live rerun is complete**: `cliq status --check-auth` + `cliq app-command-get APP_PROBE_FAKE_20260414_090313 CMD_PROBE_FAKE_20260414_090313` kept auth/export readiness healthy (`oauthReady: true`, `exportOauthReady: true`) while app-command detail endpoints remained `not_supported`.
3. **Next smallest step**: take the next smallest `cliq-193` output-hardening increment with focused tests, then run one matching focused live rerun and archive evidence.

## Next
1. `cliq-193`: take the next smallest output-hardening increment with focused tests.
2. `cliq-193`: run one matching focused live rerun (`cliq status --check-auth` + one `cliq app-command-get ...`) and archive evidence.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
