# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Focused live rerun for latest `cliq-193` app-get hardening is complete**: `cliq status --check-auth` and `cliq app-get APP_PROBE_FAKE_20260414_050344` were rerun and archived at `tests/auto_pilot/reports/cliq193_app_get_probe_summary_20260414_050344.json`; auth/export readiness stayed healthy (`oauthReady: true`, `exportOauthReady: true`) and app-detail endpoint remains `error: not_supported`.
3. **Next smallest step**: ship the next `cliq-193` app-governance output-hardening increment with focused tests.

## Next
1. `cliq-193`: implement the next smallest output-hardening increment and run focused tests.
2. `cliq-193`: run one matching focused live rerun and archive evidence.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
