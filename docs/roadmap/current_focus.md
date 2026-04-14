# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **`cliq-193` focused live rerun is refreshed**: `cliq status --check-auth` + `cliq app-permission-get` (`APP_PROBE_FAKE_20260414_022317` / `PERMISSION_PROBE_FAKE_20260414_022317`) keeps auth/export readiness healthy (`oauthReady: true`, `exportOauthReady: true`) while app-permission detail endpoints remain `not_supported` (evidence: `tests/auto_pilot/reports/cliq193_app_permission_get_probe_summary_20260414_022317.json`).
3. **Next smallest step**: take the next small `cliq-193` app-governance output-hardening increment with focused tests.

## Next
1. `cliq-193`: take the next small app-governance output-hardening increment with focused tests.
2. `cliq-193`: run one matching focused live rerun and archive evidence.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
