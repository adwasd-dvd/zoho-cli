# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Focused cliq-193 live verification is refreshed**: `cliq status --check-auth` + `cliq app-permissions APP_PROBE_FAKE_20260413_182315` kept auth/export readiness healthy (`oauthReady: true`, `exportOauthReady: true`) and classified app-permissions endpoints as `not_supported` (evidence: `tests/auto_pilot/reports/cliq193_app_permissions_probe_summary_20260413_182315.json`).
3. **Next step is the next smallest cliq-193 output-hardening increment** with focused unit coverage, followed by one focused live verification pass.

## Next
1. `cliq-193`: ship one smallest app-governance output-hardening increment with focused tests.
2. `cliq-193`: run one focused live verification pass (`cliq status --check-auth` + one app-governance command) and archive evidence.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
