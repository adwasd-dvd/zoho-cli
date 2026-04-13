# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Latest `cliq-193` focused live verification is archived**: `cliq status --check-auth` + `cliq app-permissions APP_PROBE_FAKE_20260413_202213` kept auth healthy (`oauthReady: true`, `exportOauthReady: true`) while app-permissions endpoints remain `not_supported` (`tests/auto_pilot/reports/cliq193_app_permissions_probe_summary_20260413_202213.json`).
3. **Next step is the next smallest `cliq-193` output-hardening increment** with focused tests, then one focused live rerun.

## Next
1. `cliq-193`: ship the next smallest app-governance output-hardening increment with focused unit coverage.
2. `cliq-193`: run one focused live verification pass for that new slice and archive evidence.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
