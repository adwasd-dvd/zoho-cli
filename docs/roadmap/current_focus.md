# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Latest `cliq-193` focused live rerun is complete**: reran `cliq status --check-auth` + `cliq app-commands APP_PROBE_FAKE_20260414_042232`; auth/export readiness remains healthy (`oauthReady: true`, `exportOauthReady: true`) while app-command list endpoints remain `not_supported` (evidence: `tests/auto_pilot/reports/cliq193_app_commands_probe_summary_20260414_042232.json`).
3. **Next smallest step**: take the next small `cliq-193` app-governance output-hardening increment with focused tests, then run one matching focused live rerun and archive evidence.

## Next
1. `cliq-193`: take the next smallest app-governance output-hardening increment with focused tests.
2. `cliq-193`: run one matching focused live rerun and archive evidence.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
