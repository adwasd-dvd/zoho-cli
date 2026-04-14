# Current Focus

## Immediate
1. **`cliq-165` remains the top blocker**: maintenance export scopes are granted, but both `cliq export-chats` list and `--chat-id` still return API-side `inactive_appaccount_user` until Cliq admin-side app-account activation is completed.
2. **Latest `cliq-193` focused live rerun is complete**: `cliq status --check-auth` + `cliq apps --limit 10` evidence is archived at `tests/auto_pilot/reports/cliq193_apps_probe_summary_20260414_054242.json`; auth/export readiness remains healthy (`oauthReady: true`, `exportOauthReady: true`) while app-list endpoints remain `not_supported`.
3. **Next smallest step**: take the next `cliq-193` output-hardening increment with focused tests.

## Next
1. `cliq-193`: take the next smallest output-hardening increment with focused tests.
2. `cliq-193`: run one matching focused live rerun and archive evidence.
3. `cliq-165`: rerun export verification immediately after app-account activation (`list` + one `--chat-id` export) and archive first success JSON.
4. `crm-002`: remain blocked until CRM-enabled org access is available.
