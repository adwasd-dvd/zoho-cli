# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Focused live rerun for install payload envelopes is refreshed**: `cliq status --check-auth` + `cliq app-install-get APP_PROBE_FAKE_20260414_012300 INSTALL_PROBE_FAKE_20260414_012300` was rerun and archived (`tests/auto_pilot/reports/cliq193_app_install_get_probe_summary_20260414_012300.json`); auth/export readiness remains healthy (`oauthReady: true`, `exportOauthReady: true`) while app-install detail endpoints remain `not_supported`.
3. **Next smallest implementation step**: deliver the next small `cliq-193` app-governance output-hardening increment with focused tests, then run one matching focused live rerun and archive evidence.

## Next
1. `cliq-193`: deliver the next small app-governance output-hardening increment with focused tests.
2. `cliq-193`: run one focused live rerun for that new increment and archive artifacts.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
